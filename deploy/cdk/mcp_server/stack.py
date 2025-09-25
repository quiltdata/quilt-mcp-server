"""AWS CDK stack that mirrors the Terraform MCP server module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, MutableMapping, Optional, Sequence

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


@dataclass(frozen=True)
class SecretMapping:
    """Lightweight helper describing a container secret mapping."""

    name: str
    arn: str


class McpServerStack(Stack):
    """Provision an HTTP-enabled Quilt MCP server behind an ALB."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        container_image: str,
        domain_name: str,
        listener_host: str,
        listener_path: str,
        desired_count: int = 1,
        cpu: int = 512,
        memory_mib: int = 1024,
        container_port: int = 8000,
        health_check_path: str = "/healthz",
        listener_priority: int = 100,
        enable_execute_command: bool = False,
        egress_cidr_blocks: Optional[Sequence[str]] = None,
        secret_arns: Optional[Sequence[Mapping[str, str]]] = None,
        environment: Optional[Mapping[str, str]] = None,
        vpc: Optional[ec2.IVpc] = None,
        cluster: Optional[ecs.ICluster] = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = vpc or ec2.Vpc(self, "Vpc", max_azs=2)
        cluster = cluster or ecs.Cluster(self, "Cluster", vpc=vpc)

        log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=f"/ecs/{construct_id}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM role used by the Quilt MCP task",
        )

        task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            cpu=cpu,
            memory_limit_mib=memory_mib,
            task_role=task_role,
        )

        container = task_definition.add_container(
            "McpContainer",
            image=ecs.ContainerImage.from_registry(container_image),
            logging=ecs.LogDriver.aws_logs(stream_prefix="ecs", log_group=log_group),
            health_check=ecs.HealthCheck(
                command=[
                    "CMD-SHELL",
                    f"curl -f http://127.0.0.1:{container_port}{health_check_path} || exit 1",
                ],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )
        container.add_port_mappings(ecs.PortMapping(container_port=container_port))

        env_values: MutableMapping[str, str] = {
            "FASTMCP_TRANSPORT": "http",
            "FASTMCP_HOST": "0.0.0.0",
            "FASTMCP_PORT": str(container_port),
            "QUILT_CATALOG_URL": f"https://{domain_name}",
        }
        if environment:
            env_values.update({key: str(value) for key, value in environment.items()})
        for key, value in env_values.items():
            container.add_environment(key, value)

        for secret in secret_arns or []:
            mapping = SecretMapping(name=secret["name"], arn=secret["arn"])
            secret_ref = secretsmanager.Secret.from_secret_partial_arn(
                self,
                f"ImportedSecret{mapping.name}",
                mapping.arn,
            )
            container.add_secret(mapping.name, ecs.Secret.from_secrets_manager(secret_ref))

        alb = elbv2.ApplicationLoadBalancer(
            self,
            "Alb",
            vpc=vpc,
            internet_facing=True,
            load_balancer_name=f"{construct_id}-alb",
        )

        listener = alb.add_listener("HttpListener", port=80, open=True, default_action=elbv2.ListenerAction.fixed_response(status_code=404, content_type="text/plain", message_body="Service routing not configured"))

        service_sg = ec2.SecurityGroup(
            self,
            "ServiceSecurityGroup",
            description="Security group for Quilt MCP service",
            vpc=vpc,
            allow_all_outbound=False,
        )
        service_sg.add_ingress_rule(
            alb.connections.security_groups[0], ec2.Port.tcp(container_port)
        )

        egress_blocks = list(egress_cidr_blocks or ["0.0.0.0/0"])
        for idx, cidr in enumerate(egress_blocks):
            service_sg.add_egress_rule(
                ec2.Peer.ipv4(cidr),
                ec2.Port.tcp_range(0, 65535),
                description=f"Egress {idx}",
            )

        task_definition.apply_removal_policy(RemovalPolicy.DESTROY)

        service = ecs.FargateService(
            self,
            "Service",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=desired_count,
            assign_public_ip=False,
            vpc_subnets=ec2.SubnetSelection(subnets=vpc.private_subnets),
            security_groups=[service_sg],
            enable_execute_command=enable_execute_command,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
        )

        target_group = elbv2.ApplicationTargetGroup(
            self,
            "TargetGroup",
            port=container_port,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[service],
            vpc=vpc,
            health_check=elbv2.HealthCheck(
                path=health_check_path,
                healthy_http_codes="200-399",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(6),
            ),
        )

        elbv2.ApplicationListenerRule(
            self,
            "ListenerRule",
            listener=listener,
            priority=listener_priority,
            action=elbv2.ListenerAction.forward([target_group]),
            conditions=[
                elbv2.ListenerCondition.host_headers([listener_host]),
                elbv2.ListenerCondition.path_patterns([listener_path]),
            ],
        )

        # Surface useful endpoint information
        self.alb_dns_name = alb.load_balancer_dns_name
        self.target_group = target_group
        self.service = service
