#!/usr/bin/env python3
"""CDK app entry point."""

import os
import aws_cdk as cdk
from deployment.cdk.quilt_mcp_stack import QuiltMcpStack

app = cdk.App()

# Get environment variables with defaults
account = os.getenv('CDK_DEFAULT_ACCOUNT', cdk.Aws.ACCOUNT_ID)
region = os.getenv('CDK_DEFAULT_REGION', 'us-east-1')

QuiltMcpStack(app, "QuiltMcpStack",
    env=cdk.Environment(account=account, region=region))

app.synth()