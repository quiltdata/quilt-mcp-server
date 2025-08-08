from constructs import Construct
from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_logs as logs,
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
                allow_headers=["Content-Type", "Authorization", "X-Amz-Date"]
            ),
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True
            )
        )

        # Create Lambda integration
        lambda_integration = apigateway.LambdaIntegration(
            lambda_fn, # type: ignore
            request_templates={"application/json": '{"statusCode": "200"}'}
        )

        # Add MCP resource and methods
        mcp_resource = api.root.add_resource("mcp")
        
        # Add methods without authorization for now (to debug core functionality)
        mcp_resource.add_method(
            "GET", 
            lambda_integration
        )
        mcp_resource.add_method(
            "POST", 
            lambda_integration
        )

        # Add catch-all proxy resource for MCP sub-paths
        proxy_resource = mcp_resource.add_resource("{proxy+}")
        proxy_resource.add_method(
            "ANY", 
            lambda_integration
        )

        # Outputs
        CfnOutput(
            self, "ApiEndpoint",
            value=f"{api.url}mcp/",
            description="MCP Server API Endpoint"
        )

        CfnOutput(
            self, "LambdaFunctionName",
            value=lambda_fn.function_name,
            description="Lambda function name for debugging"
        )

        CfnOutput(
            self, "LogGroupName",
            value=f"/aws/lambda/{lambda_fn.function_name}",
            description="CloudWatch log group name for Lambda logs"
        )

        CfnOutput(
            self, "ApiLogGroupName",
            value=f"/aws/apigateway/{api.rest_api_id}/prod",
            description="CloudWatch log group name for API Gateway logs"
        )