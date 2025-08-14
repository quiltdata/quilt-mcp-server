#!/usr/bin/env python3
"""AWS CDK app for deploying Quilt MCP Server on ECS/Fargate."""

import os
import aws_cdk as cdk  # type: ignore[import-untyped]
from constructs import Construct  # type: ignore[import-untyped]
from aws_cdk import (  # type: ignore[import-untyped]
    Stack,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_logs as logs,
    aws_iam as iam,
    aws_certificatemanager as acm,
    aws_s3 as s3,
    aws_elasticloadbalancingv2 as elbv2,
)


class QuiltMcpFargateStack(Stack):
    """CDK Stack for Quilt MCP Server on ECS Fargate with ALB."""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Use existing VPC or create one
        vpc = self._get_or_create_vpc()
        
        # ECS Cluster
        cluster = ecs.Cluster(
            self, "QuiltMcpCluster",
            cluster_name="quilt-mcp-cluster",
            vpc=vpc,
            container_insights=True
        )
        
        # Log Groups for different components
        app_log_group = logs.LogGroup(
            self, "QuiltMcpAppLogGroup",
            log_group_name="/ecs/quilt-mcp/application",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )
        
        alb_log_group = logs.LogGroup(
            self, "QuiltMcpAlbLogGroup", 
            log_group_name="/aws/elasticloadbalancing/quilt-mcp-alb",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )
        
        # Optional: VPC Flow Logs (if creating new VPC)
        vpc_log_group = logs.LogGroup(
            self, "QuiltMcpVpcLogGroup",
            log_group_name="/aws/vpc/quilt-mcp-flowlogs", 
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )
        
        # Task Role (for the application)
        task_role = iam.Role(
            self, "QuiltMcpTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),  # type: ignore[arg-type]
            inline_policies={
                "QuiltS3Access": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject", 
                                "s3:DeleteObject",
                                "s3:ListBucket"
                            ],
                            resources=["arn:aws:s3:::*", "arn:aws:s3:::*/*"]
                        )
                    ]
                )
            }
        )
        
        # Execution Role (for ECS to pull images and write logs)
        execution_role = iam.Role(
            self, "QuiltMcpExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),  # type: ignore[arg-type]
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )
        
        # Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self, "QuiltMcpTaskDef",
            family="quilt-mcp-task",
            cpu=256,
            memory_limit_mib=512,
            task_role=task_role,  # type: ignore[arg-type]
            execution_role=execution_role  # type: ignore[arg-type]
        )
        
        # Get Docker image URI from environment or use default
        image_uri = os.environ.get("IMAGE_URI", "quilt-mcp:latest")
        
        # Container Definition
        _ = task_definition.add_container(
            "QuiltMcpContainer",
            image=ecs.ContainerImage.from_registry(image_uri),
            port_mappings=[
                ecs.PortMapping(
                    container_port=8000,
                    protocol=ecs.Protocol.TCP
                )
            ],
            environment={
                "LOG_LEVEL": "INFO",
                "FASTMCP_TRANSPORT": "streamable-http"
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="ecs",
                log_group=app_log_group
            ),
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/mcp || exit 1"],
                interval=cdk.Duration.seconds(30),
                timeout=cdk.Duration.seconds(10),
                retries=3,
                start_period=cdk.Duration.seconds(60)
            )
        )
        
        # Application Load Balancer
        alb = elbv2.ApplicationLoadBalancer(
            self, "QuiltMcpALB",
            vpc=vpc,
            internet_facing=True,
            load_balancer_name="quilt-mcp-alb"
        )
        
        # Optional: Enable ALB access logs to S3 when provided
        alb_log_bucket_name = os.environ.get("ALB_LOG_S3_BUCKET")
        if alb_log_bucket_name:
            logs_bucket = s3.Bucket.from_bucket_name(self, "AlbLogsBucket", alb_log_bucket_name)
            alb.log_access_logs(bucket=logs_bucket, prefix="alb-logs")
        
        # Target Group
        target_group = elbv2.ApplicationTargetGroup(
            self, "QuiltMcpTargets",
            vpc=vpc,
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/mcp",
                healthy_http_codes="200,404",  # 404 is OK for MCP endpoint without proper request
                interval=cdk.Duration.seconds(30),
                timeout=cdk.Duration.seconds(10),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3
            )
        )
        
        # ALB Listeners
        cert_arn = os.environ.get("ACM_CERT_ARN")
        https_enabled = False
        if cert_arn:
            # HTTPS listener with provided ACM certificate
            certificate = acm.Certificate.from_certificate_arn(self, "QuiltMcpCert", cert_arn)
            alb.add_listener(
                "QuiltMcpHttpsListener",
                port=443,
                certificates=[elbv2.ListenerCertificate.from_certificate_manager(certificate)],
                default_target_groups=[target_group]
            )
            # HTTP listener redirects to HTTPS
            alb.add_listener(
                "QuiltMcpHttpListener",
                port=80,
                default_action=elbv2.ListenerAction.redirect(protocol="HTTPS", port="443", permanent=True)
            )
            https_enabled = True
        else:
            # HTTP only
            alb.add_listener(
                "QuiltMcpListener",
                port=80,
                default_target_groups=[target_group]
            )
        
        # ECS Service
        service = ecs.FargateService(
            self, "QuiltMcpService",
            cluster=cluster,
            task_definition=task_definition,
            service_name="quilt-mcp-service",
            desired_count=2,
            assign_public_ip=True,  # Required for tasks in public subnets to reach internet
            platform_version=ecs.FargatePlatformVersion.LATEST
        )
        
        # Connect service to load balancer
        service.attach_to_application_target_group(target_group)
        
        # Output the load balancer URL
        scheme = "https" if https_enabled else "http"
        cdk.CfnOutput(
            self, "LoadBalancerURL",
            value=f"{scheme}://{alb.load_balancer_dns_name}",
            description="URL of the Application Load Balancer"
        )
        
        cdk.CfnOutput(
            self, "MCPEndpoint", 
            value=f"http://{alb.load_balancer_dns_name}/mcp",
            description="MCP endpoint URL (HTTP)"
        )
        if https_enabled:
            cdk.CfnOutput(
                self, "MCPEndpointHttps",
                value=f"https://{alb.load_balancer_dns_name}/mcp",
                description="MCP endpoint URL (HTTPS)"
            )
        
        cdk.CfnOutput(
            self, "ClusterName",
            value=cluster.cluster_name,
            description="ECS Cluster name"
        )
        
        cdk.CfnOutput(
            self, "ServiceName",
            value=service.service_name,
            description="ECS Service name"
        )
        
        cdk.CfnOutput(
            self, "AppLogGroupName",
            value=app_log_group.log_group_name,
            description="Application CloudWatch Log Group name"
        )
        
        cdk.CfnOutput(
            self, "AlbLogGroupName", 
            value=alb_log_group.log_group_name,
            description="ALB CloudWatch Log Group name"
        )
        
        cdk.CfnOutput(
            self, "VpcLogGroupName",
            value=vpc_log_group.log_group_name,
            description="VPC Flow Logs CloudWatch Log Group name"
        )
    
    def _get_or_create_vpc(self) -> ec2.IVpc:
        """Get existing VPC from environment or create a new one."""
        vpc_id = os.environ.get("VPC_ID")
        
        if vpc_id:
            # Use existing VPC
            return ec2.Vpc.from_lookup(self, "ExistingVPC", vpc_id=vpc_id)
        else:
            # Create new VPC with public subnets only for simplicity
            return ec2.Vpc(
                self, "QuiltMcpVPC",
                max_azs=2,
                subnet_configuration=[
                    ec2.SubnetConfiguration(
                        name="Public",
                        subnet_type=ec2.SubnetType.PUBLIC,
                        cidr_mask=24
                    )
                ]
            )


app = cdk.App()

# Environment
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1")
)

QuiltMcpFargateStack(app, "QuiltMcpFargateStack", env=env)

app.synth()