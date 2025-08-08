import pytest
import aws_cdk as cdk
from aws_cdk import assertions
import sys
import os

# Add the deploy directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'deploy'))

from quilt_mcp_stack import QuiltMcpStack  # type: ignore

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
        
        # Verify IAM roles exist (Lambda role + API Gateway CloudWatch role + Cognito authenticated role)
        template.resource_count_is("AWS::IAM::Role", 3)
        
    def test_cognito_creation(self):
        """Test that Cognito User Pool and related resources are created."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify Cognito User Pool exists
        template.has_resource_properties("AWS::Cognito::UserPool", {
            "UserPoolName": "quilt-mcp-users"
        })
        
        # Verify Cognito User Pool Client exists
        template.has_resource_properties("AWS::Cognito::UserPoolClient", {
            "ClientName": "quilt-mcp-client",
            "GenerateSecret": True
        })
        
        # Verify Cognito Domain exists
        template.resource_count_is("AWS::Cognito::UserPoolDomain", 1)
        
        # Verify Cognito Authorizer exists
        template.has_resource_properties("AWS::ApiGateway::Authorizer", {
            "Name": "quilt-mcp-authorizer",
            "Type": "COGNITO_USER_POOLS"
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
        
    def test_api_methods_require_cognito_auth(self):
        """Test that API methods require Cognito authorization."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Check that GET and POST methods require Cognito authorization
        template.has_resource_properties("AWS::ApiGateway::Method", {
            "HttpMethod": "GET",
            "AuthorizationType": "COGNITO_USER_POOLS"
        })
        
        template.has_resource_properties("AWS::ApiGateway::Method", {
            "HttpMethod": "POST",
            "AuthorizationType": "COGNITO_USER_POOLS"
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
        assert "CognitoUserPoolId" in outputs
        assert "CognitoClientId" in outputs
        assert "CognitoClientSecret" in outputs
        assert "CognitoDomain" in outputs
        assert "LambdaFunctionName" in outputs
        assert "LogGroupName" in outputs
        
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