import pytest
import aws_cdk as cdk
from aws_cdk import assertions
import sys
import os

# Add the parent directory to the path to import the stack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from quilt_mcp_stack import QuiltMcpStack

class TestQuiltMcpStack:
    """Test suite for the simplified CDK stack without Cognito."""
    
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
        
        # Verify only one IAM role exists (Lambda execution role)
        template.resource_count_is("AWS::IAM::Role", 1)
        
    def test_no_cognito_resources(self):
        """Test that no Cognito resources exist in the simplified stack."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify no Cognito resources
        template.resource_count_is("AWS::Cognito::UserPool", 0)
        template.resource_count_is("AWS::Cognito::UserPoolClient", 0)
        template.resource_count_is("AWS::ApiGateway::Authorizer", 0)
        
    def test_api_methods_no_auth(self):
        """Test that API methods don't require authentication."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify methods have no authentication
        template.has_resource_properties("AWS::ApiGateway::Method", {
            "HttpMethod": "GET",
            "AuthorizationType": "NONE"
        })
        
        template.has_resource_properties("AWS::ApiGateway::Method", {
            "HttpMethod": "POST", 
            "AuthorizationType": "NONE"
        })
        
    def test_cors_configuration(self):
        """Test CORS configuration."""
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
        
    def test_lambda_configuration(self):
        """Test Lambda function configuration."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify Lambda configuration
        template.has_resource_properties("AWS::Lambda::Function", {
            "Timeout": 30,
            "MemorySize": 512,
            "Environment": {
                "Variables": {
                    "ENV": "production",
                    "LOG_LEVEL": "INFO"
                }
            }
        })
        
    def test_outputs_exist(self):
        """Test that required stack outputs exist."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        outputs = template.find_outputs("*")
        
        # Verify required outputs exist (no Cognito outputs)
        assert "ApiEndpoint" in outputs
        assert "LambdaFunctionName" in outputs  
        assert "LogGroupName" in outputs
        
        # Verify Cognito outputs don't exist
        assert "CognitoUserPoolId" not in outputs
        assert "CognitoClientId" not in outputs
        
    def test_lambda_role_permissions(self):
        """Test Lambda role has correct permissions."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify Lambda role has managed policies
        template.has_resource_properties("AWS::IAM::Role", {
            "ManagedPolicyArns": [
                {
                    "Fn::Join": [
                        "",
                        [
                            "arn:",
                            {"Ref": "AWS::Partition"},
                            ":iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                        ]
                    ]
                },
                self.quilt_policy_arn
            ]
        })
