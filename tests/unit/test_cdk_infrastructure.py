"""Tests for CDK and CloudFormation MCP server infrastructure definitions."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from aws_cdk import App
from aws_cdk.assertions import Template



from yaml.nodes import MappingNode, ScalarNode, SequenceNode


class CloudFormationLoader(yaml.SafeLoader):
    """YAML loader that treats CloudFormation tags as plain data."""


def _construct_cloudformation(loader: CloudFormationLoader, suffix: str, node):
    if isinstance(node, ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, MappingNode):
        return loader.construct_mapping(node)
    return None


CloudFormationLoader.add_multi_constructor('!', _construct_cloudformation)

def _first_resource_of_type(template_dict: dict, resource_type: str) -> dict:
    """Return the first resource dict matching the requested type."""
    for resource in template_dict["Resources"].values():
        if resource.get("Type") == resource_type:
            return resource
    raise AssertionError(f"Template missing resource of type {resource_type}")


def test_cdk_stack_defines_core_resources():
    """CDK stack should mirror Terraform resources and env wiring."""
    from deploy.cdk.mcp_server.stack import McpServerStack

    app = App()
    stack = McpServerStack(
        app,
        "TestMcpStack",
        container_image="public.ecr.aws/docker/library/python:3.11-slim",
        domain_name="demo.quiltdata.com",
        listener_host="demo.quiltdata.com",
        listener_path="/mcp/*",
        desired_count=2,
        secret_arns=[
            {"name": "MCP_ENHANCED_JWT_SECRET", "arn": "arn:aws:secretsmanager:us-east-1:111111111111:secret:jwt"},
            {"name": "MCP_ENHANCED_JWT_KID", "arn": "arn:aws:secretsmanager:us-east-1:111111111111:secret:kid"},
        ],
    )

    template_dict = Template.from_stack(stack).to_json()

    resource_types = {resource["Type"] for resource in template_dict["Resources"].values()}
    assert {
        "AWS::Logs::LogGroup",
        "AWS::ECS::TaskDefinition",
        "AWS::ECS::Service",
        "AWS::EC2::SecurityGroup",
        "AWS::ElasticLoadBalancingV2::TargetGroup",
        "AWS::ElasticLoadBalancingV2::ListenerRule",
    }.issubset(resource_types)

    task_definition = _first_resource_of_type(template_dict, "AWS::ECS::TaskDefinition")
    container = task_definition["Properties"]["ContainerDefinitions"][0]

    env_names = {item["Name"] for item in container.get("Environment", [])}
    assert {"FASTMCP_TRANSPORT", "FASTMCP_HOST", "FASTMCP_PORT"} <= env_names

    secrets = container.get("Secrets", [])
    assert secrets, "Container should map secrets from provided ARNs"
    secret_names = {secret["Name"] for secret in secrets}
    assert {"MCP_ENHANCED_JWT_SECRET", "MCP_ENHANCED_JWT_KID"} <= secret_names

    health_check = container.get("HealthCheck")
    assert health_check and "CMD-SHELL" in health_check["Command"][0]

    service = _first_resource_of_type(template_dict, "AWS::ECS::Service")
    assert service["Properties"]["DesiredCount"] == 2
    assert service["Properties"].get("EnableExecuteCommand") is False


def test_cloudformation_template_declares_expected_resources():
    """CloudFormation template should expose same core resources and wiring."""
    template_path = Path("deploy/cloudformation/mcp_server.yml")
    assert template_path.exists(), "CloudFormation template must be generated"

    template = yaml.load(template_path.read_text(), Loader=CloudFormationLoader)
    assert isinstance(template, dict), "Template must parse as YAML mapping"

    resources = template.get("Resources", {})
    assert resources, "Template must define resources"

    resource_types = {resource["Type"] for resource in resources.values()}
    assert {
        "AWS::Logs::LogGroup",
        "AWS::ECS::TaskDefinition",
        "AWS::ECS::Service",
        "AWS::ElasticLoadBalancingV2::TargetGroup",
        "AWS::ElasticLoadBalancingV2::ListenerRule",
        "AWS::EC2::SecurityGroup",
    }.issubset(resource_types)

    task_definition = _first_resource_of_type(template, "AWS::ECS::TaskDefinition")
    container = task_definition["Properties"]["ContainerDefinitions"][0]

    env_names = {item["Name"] for item in container.get("Environment", [])}
    assert {"FASTMCP_TRANSPORT", "FASTMCP_HOST", "FASTMCP_PORT"} <= env_names

    secrets = container.get("Secrets", [])
    assert secrets, "Container should declare runtime secrets"

    service = _first_resource_of_type(template, "AWS::ECS::Service")
    assert service["Properties"].get("EnableExecuteCommand") is False

    sg = _first_resource_of_type(template, "AWS::EC2::SecurityGroup")
    egress_rules = sg["Properties"]["SecurityGroupEgress"]
    assert egress_rules, "Security group must define egress rules"

