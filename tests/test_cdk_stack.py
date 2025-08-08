import pytest
import aws_cdk as cdk
from aws_cdk import assertions
import sys
import os

# Add the deploy directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'deploy'))

from quilt_mcp_stack import QuiltMcpStack

class TestQuiltMcpStack:
    """Test suite for CDK stack."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = cdk.App()
        self.quilt_policy_arn = "arn:aws:iam::123456789012:policy/TestQuiltReadPolicy"
        
    def test_stack_creation(self):
        """Test that the stack can be created."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify Lambda function exists
        template.has_resource_properties("AWS::Lambda::Function", {
            "Runtime": "python3.11",
            "Handler": "lambda_handler.handler"
        })
        
        # Verify API Gateway exists
        template.has_resource_properties("AWS::ApiGateway::RestApi", {
            "Name": "Quilt MCP Server"
        })
        
        # Verify IAM roles exist (Lambda role + API Gateway CloudWatch role)
        template.resource_count_is("AWS::IAM::Role", 2)
        
    def test_api_key_creation(self):
        """Test that API key and usage plan are created."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify API key exists
        template.has_resource_properties("AWS::ApiGateway::ApiKey", {
            "Name": "quilt-mcp-key"
        })
        
        # Verify usage plan exists
        template.has_resource_properties("AWS::ApiGateway::UsagePlan", {
            "UsagePlanName": "QuiltMcpUsagePlan",
            "Throttle": {
                "RateLimit": 100,
                "BurstLimit": 200
            },
            "Quota": {
                "Limit": 10000,
                "Period": "DAY"
            }
        })
        
    def test_cors_configuration(self):
        """Test CORS configuration on API Gateway."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify OPTIONS method for CORS
        template.has_resource_properties("AWS::ApiGateway::Method", {
            "HttpMethod": "OPTIONS",
            "AuthorizationType": "NONE"
        })
        
    def test_lambda_environment_variables(self):
        """Test Lambda function environment variables."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        template.has_resource_properties("AWS::Lambda::Function", {
            "Environment": {
                "Variables": {
                    "ENV": "production",
                    "LOG_LEVEL": "INFO"
                }
            }
        })
        
    def test_api_methods_require_key(self):
        """Test that API methods require API key."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Check that GET and POST methods require API key
        template.has_resource_properties("AWS::ApiGateway::Method", {
            "HttpMethod": "GET",
            "ApiKeyRequired": True
        })
        
        template.has_resource_properties("AWS::ApiGateway::Method", {
            "HttpMethod": "POST",
            "ApiKeyRequired": True
        })
        
    def test_outputs_exist(self):
        """Test that stack outputs are created."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify outputs exist
        outputs = template.to_json()["Outputs"]
        assert "ApiEndpoint" in outputs
        assert "ApiKeyId" in outputs
        
    def test_lambda_timeout_and_memory(self):
        """Test Lambda function timeout and memory configuration."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        template.has_resource_properties("AWS::Lambda::Function", {
            "Timeout": 30,
            "MemorySize": 512
        })