#!/usr/bin/env python3
import os
import aws_cdk as cdk
from quilt_mcp_stack import QuiltMcpStack

app = cdk.App()

# Get environment variables with defaults
account = os.getenv('CDK_DEFAULT_ACCOUNT', cdk.Aws.ACCOUNT_ID)
region = os.getenv('CDK_DEFAULT_REGION', 'us-east-1')
quilt_read_policy_arn = os.getenv('QUILT_READ_POLICY_ARN')

if not quilt_read_policy_arn:
    raise ValueError("QUILT_READ_POLICY_ARN environment variable is required")

QuiltMcpStack(
    app, 
    "QuiltMcpStack",
    quilt_read_policy_arn=quilt_read_policy_arn,
    env=cdk.Environment(account=account, region=region),
    description="Quilt MCP Server deployed as Lambda with API Gateway"
)

app.synth()