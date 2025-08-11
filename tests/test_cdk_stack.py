import pytest
import aws_cdk as cdk
from aws_cdk import assertions
import sys
import os

# Add the parent directory to the path to import the stack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from quilt_mcp_stack import QuiltMcpStack

class TestQuiltMcpStack:
    """Test suite for the CDK stack with Cognito OAuth 2.0 client credentials."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = cdk.App()
        self.quilt_policy_arn = "arn:aws:iam::123456789012:policy/TestQuiltReadPolicy"
        
        # Set up a valid Lambda package directory for testing
        # Point to the quilt directory relative to the test
        test_dir = os.path.dirname(__file__)
        project_root = os.path.dirname(test_dir)
        quilt_dir = os.path.join(project_root, 'quilt')
        os.environ['LAMBDA_PACKAGE_DIR'] = quilt_dir
        
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
        
        # Verify HTTP API exists
        template.has_resource_properties("AWS::ApiGatewayV2::Api", {
            "Name": "Quilt MCP Server"
        })
        
        # Verify Lambda role exists
        template.resource_count_is("AWS::IAM::Role", 1)
        
    def test_cognito_resources_exist(self):
        """Test that required Cognito resources exist."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify Cognito resources exist
        template.resource_count_is("AWS::Cognito::UserPool", 1)
        template.resource_count_is("AWS::Cognito::UserPoolClient", 1)
        template.resource_count_is("AWS::Cognito::UserPoolDomain", 1)
        template.resource_count_is("AWS::Cognito::UserPoolResourceServer", 1)
        
    def test_api_routes_with_jwt_auth(self):
        """Test that API routes have JWT authorization."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify HTTP API routes exist (GET, POST, proxy)
        template.resource_count_is("AWS::ApiGatewayV2::Route", 3)
        
        # Verify JWT authorizer exists
        template.has_resource_properties("AWS::ApiGatewayV2::Authorizer", {
            "AuthorizerType": "JWT"
        })
        
    def test_cors_configuration(self):
        """Test CORS configuration on HTTP API."""
        stack = QuiltMcpStack(
            self.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=self.quilt_policy_arn
        )
        
        template = assertions.Template.from_stack(stack)
        
        # Verify HTTP API has CORS configuration
        template.has_resource_properties("AWS::ApiGatewayV2::Api", {
            "CorsConfiguration": {
                "AllowOrigins": ["*"],
                "AllowMethods": ["GET", "POST", "OPTIONS"]
            }
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
        
        # Verify required outputs exist
        assert "ApiEndpoint" in outputs
        assert "LambdaFunctionName" in outputs  
        assert "LogGroupName" in outputs
        
        # Verify Cognito outputs exist
        assert "TokenEndpoint" in outputs
        assert "ClientId" in outputs
        assert "UserPoolId" in outputs
        assert "ResourceServerIdentifier" in outputs
        
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
