from constructs import Construct
from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_cognito as cognito,
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

        # Create Cognito User Pool
        user_pool = cognito.UserPool(
            self, "QuiltMcpUserPool",
            user_pool_name="quilt-mcp-users",
            sign_in_aliases=cognito.SignInAliases(email=True, username=True),
            self_sign_up_enabled=False  # Admin creates users
        )

        # Create Cognito User Pool Client
        user_pool_client = user_pool.add_client(
            "QuiltMcpClient",
            user_pool_client_name="quilt-mcp-client",
            auth_flows=cognito.AuthFlow(
                user_srp=True,
                admin_user_password=True,
                custom=True,
                user_password=True
            ),
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    client_credentials=True
                )
            )
        )

        # Create Cognito User Pool Domain
        user_pool_domain = user_pool.add_domain(
            "QuiltMcpDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"quilt-mcp-{self.account}-{self.region}"
            )
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
            )
        )

        # Create Cognito Authorizer
        cognito_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self, "QuiltMcpAuthorizer",
            cognito_user_pools=[user_pool],
            authorizer_name="quilt-mcp-authorizer"
        )

        # Create Lambda integration
        lambda_integration = apigateway.LambdaIntegration(
            lambda_fn, # type: ignore
            request_templates={"application/json": '{"statusCode": "200"}'}
        )

        # Add MCP resource and methods
        mcp_resource = api.root.add_resource("mcp")
        
        # Add methods with Cognito authorization
        mcp_resource.add_method(
            "GET", 
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        mcp_resource.add_method(
            "POST", 
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )

        # Add catch-all proxy resource for MCP sub-paths
        proxy_resource = mcp_resource.add_resource("{proxy+}")
        proxy_resource.add_method(
            "ANY", 
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )

        # Outputs
        CfnOutput(
            self, "ApiEndpoint",
            value=f"{api.url}mcp/",
            description="MCP Server API Endpoint"
        )

        CfnOutput(
            self, "CognitoUserPoolId",
            value=user_pool.user_pool_id,
            description="Cognito User Pool ID"
        )

        CfnOutput(
            self, "CognitoClientId",
            value=user_pool_client.user_pool_client_id,
            description="Cognito Client ID"
        )

        CfnOutput(
            self, "CognitoClientSecret",
            value=user_pool_client.user_pool_client_secret.unsafe_unwrap(),
            description="Cognito Client Secret (keep secure!)"
        )

        CfnOutput(
            self, "CognitoDomain",
            value=f"{user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com",
            description="Cognito Auth Domain"
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