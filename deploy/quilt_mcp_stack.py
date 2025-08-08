from constructs import Construct
from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_iam as iam,
    CfnOutput,
)
from aws_cdk.aws_iam import ServicePrincipal
import os


class QuiltMcpStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, quilt_read_policy_arn: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Lambda execution role
        lambda_role = iam.Role(
            self, "QuiltMcpLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"), # type: ignore
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_managed_policy_arn(self, "QuiltReadPolicy", quilt_read_policy_arn)
            ]
        )

        # Get the Lambda package directory from environment
        lambda_package_dir = os.environ.get('LAMBDA_PACKAGE_DIR', '../quilt')
        
        # Create Lambda function
        lambda_fn = _lambda.Function(
            self, "QuiltMcpFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_handler.handler",
            code=_lambda.Code.from_asset(lambda_package_dir),
            role=lambda_role, # type: ignore
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "ENV": "production",
                "LOG_LEVEL": "INFO",
            }
        )

        # Create API Gateway
        api = apigateway.RestApi(
            self, "QuiltMcpApi",
            rest_api_name="Quilt MCP Server",
            description="Claude-compatible MCP server for Quilt data access",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"]
            )
        )

        # Create API key
        api_key = api.add_api_key(
            "QuiltMcpApiKey",
            api_key_name="quilt-mcp-key"
        )

        # Create usage plan
        usage_plan = api.add_usage_plan(
            "QuiltMcpUsagePlan",
            name="QuiltMcpUsagePlan",
            throttle=apigateway.ThrottleSettings(
                rate_limit=100,
                burst_limit=200
            ),
            quota=apigateway.QuotaSettings(
                limit=10000,
                period=apigateway.Period.DAY
            )
        )

        usage_plan.add_api_key(api_key)

        # Create Lambda integration
        lambda_integration = apigateway.LambdaIntegration(
            lambda_fn, # type: ignore
            request_templates={"application/json": '{"statusCode": "200"}'}
        )

        # Add MCP resource and methods
        mcp_resource = api.root.add_resource("mcp")
        
        # Add methods with API key requirement
        mcp_resource.add_method(
            "GET", 
            lambda_integration,
            api_key_required=True
        )
        mcp_resource.add_method(
            "POST", 
            lambda_integration,
            api_key_required=True
        )

        # Add catch-all proxy resource for MCP sub-paths
        proxy_resource = mcp_resource.add_resource("{proxy+}")
        proxy_resource.add_method(
            "ANY", 
            lambda_integration,
            api_key_required=True
        )

        # Add usage plan to deployment stage
        usage_plan.add_api_stage(
            stage=api.deployment_stage
        )

        # Outputs
        CfnOutput(
            self, "ApiEndpoint",
            value=f"{api.url}mcp/",
            description="MCP Server API Endpoint"
        )

        CfnOutput(
            self, "ApiKeyId",
            value=api_key.key_id,
            description="API Key ID (use 'aws apigateway get-api-key --api-key <key-id> --include-value' to get the key)"
        )