import os
import sys

import aws_cdk as cdk
import pytest
from aws_cdk import assertions

# Add the project root to the path to import the stack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from deployment.cdk.quilt_mcp_stack import QuiltMcpStack


class TestQuiltMcpStack:
    """Test suite for the CDK stack with Cognito OAuth 2.0 client credentials."""

    @classmethod
    def setup_class(cls):
        """Set up class-level fixtures - stack created once per test class."""
        cls.app = cdk.App()
        cls.quilt_policy_arn = "arn:aws:iam::123456789012:policy/TestQuiltReadPolicy"

        # Set up a valid Lambda package directory for testing
        # Point to the quilt directory relative to the test
        test_dir = os.path.dirname(__file__)
        quilt_dir = os.path.dirname(test_dir)  # quilt/tests -> quilt
        project_root = os.path.dirname(quilt_dir)  # quilt -> project root
        os.environ['LAMBDA_PACKAGE_DIR'] = quilt_dir
        
        # Create stack once for all tests
        cls.stack = QuiltMcpStack(
            cls.app,
            "TestQuiltMcpStack",
            quilt_read_policy_arn=cls.quilt_policy_arn
        )
        cls.template = assertions.Template.from_stack(cls.stack)

    def test_stack_creation(self):
        """Test that the stack can be created."""
        # Verify Lambda function exists with FROM_IMAGE configuration
        self.template.resource_count_is("AWS::Lambda::Function", 1)

        # Verify HTTP API exists
        self.template.has_resource_properties("AWS::ApiGatewayV2::Api", {
            "Name": "Quilt MCP Server"
        })

        # Verify Lambda role exists
        self.template.resource_count_is("AWS::IAM::Role", 1)

    def test_cognito_resources_exist(self):
        """Test that required Cognito resources exist."""
        # Verify Cognito resources exist
        self.template.resource_count_is("AWS::Cognito::UserPool", 1)
        self.template.resource_count_is("AWS::Cognito::UserPoolClient", 1)
        self.template.resource_count_is("AWS::Cognito::UserPoolDomain", 1)
        self.template.resource_count_is("AWS::Cognito::UserPoolResourceServer", 1)

    def test_api_routes_with_jwt_auth(self):
        """Test that API routes have JWT authorization."""
        # Verify HTTP API routes exist (GET, POST, proxy)
        self.template.resource_count_is("AWS::ApiGatewayV2::Route", 3)

        # Verify JWT authorizer exists
        self.template.has_resource_properties("AWS::ApiGatewayV2::Authorizer", {
            "AuthorizerType": "JWT"
        })

    def test_cors_configuration(self):
        """Test CORS configuration on HTTP API."""
        # Verify HTTP API has CORS configuration
        self.template.has_resource_properties("AWS::ApiGatewayV2::Api", {
            "CorsConfiguration": {
                "AllowOrigins": ["*"],
                "AllowMethods": ["GET", "POST", "OPTIONS"]
            }
        })

    def test_lambda_configuration(self):
        """Test Lambda function configuration."""
        # Verify Lambda configuration
        self.template.has_resource_properties("AWS::Lambda::Function", {
            "Timeout": 30,
            "MemorySize": 512,
            "Environment": {
                "Variables": {
                    "RUNTIME": "lambda",
                    "LOG_LEVEL": "INFO",
                    "FASTMCP_TRANSPORT": "streamable-http"
                }
            }
        })

    def test_outputs_exist(self):
        """Test that required stack outputs exist."""
        outputs = self.template.find_outputs("*")

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
        # Verify Lambda role has managed policies
        self.template.has_resource_properties("AWS::IAM::Role", {
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
