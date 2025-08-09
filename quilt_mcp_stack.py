from constructs import Construct
from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput,
)
from aws_cdk.aws_iam import ServicePrincipal
import os


class QuiltMcpStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, quilt_read_policy_arn: str, lambda_timeout_seconds: int = 30, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Cognito User Pool
        user_pool = cognito.UserPool(
            self, "QuiltMcpUserPool",
            user_pool_name="quilt-mcp-user-pool",
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create User Pool Domain (mandatory for /oauth2/token endpoint)
        user_pool_domain = cognito.UserPoolDomain(
            self, "QuiltMcpUserPoolDomain",
            user_pool=user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"quilt-mcp-{self.account}-{self.region}"
            )
        )

        # Create Resource Server with custom scopes for M2M
        read_scope = cognito.ResourceServerScope(
            scope_name="read",
            scope_description="Read access to Quilt data"
        )
        write_scope = cognito.ResourceServerScope(
            scope_name="write", 
            scope_description="Write access to Quilt data"
        )
        
        resource_server = cognito.UserPoolResourceServer(
            self, "QuiltMcpResourceServer",
            identifier="quilt-mcp-api",
            user_pool=user_pool,
            scopes=[read_scope, write_scope]
        )

        # Create User Pool Client for client credentials flow
        user_pool_client = cognito.UserPoolClient(
            self, "QuiltMcpUserPoolClient",
            user_pool=user_pool,
            generate_secret=True,
            auth_flows=cognito.AuthFlow(
                custom=False,
                user_password=False,
                user_srp=False,
                admin_user_password=False
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    client_credentials=True,
                    authorization_code_grant=False,
                    implicit_code_grant=False
                ),
                scopes=[
                    cognito.OAuthScope.resource_server(resource_server, read_scope),
                    cognito.OAuthScope.resource_server(resource_server, write_scope)
                ]
            )
        )

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
            timeout=Duration.seconds(lambda_timeout_seconds),
            memory_size=512,
            environment={
                "ENV": "production",
                "LOG_LEVEL": "INFO",
            }
        )

        # Create JWT Authorizer for HTTP API
        jwt_authorizer = apigwv2.CfnAuthorizer(
            self, "QuiltMcpJwtAuthorizer",
            api_id="placeholder",  # Will be set after HTTP API creation
            authorizer_type="JWT",
            identity_source=["$request.header.Authorization"],
            name="QuiltMcpJwtAuthorizer",
            jwt_configuration=apigwv2.CfnAuthorizer.JWTConfigurationProperty(
                issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
                audience=[user_pool_client.user_pool_client_id]
            )
        )

        # Create HTTP API (v2) 
        http_api = apigwv2.HttpApi(
            self, "QuiltMcpHttpApi",
            api_name="Quilt MCP Server",
            description="Claude-compatible MCP server for Quilt data access with JWT auth",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigwv2.CorsHttpMethod.GET, apigwv2.CorsHttpMethod.POST, apigwv2.CorsHttpMethod.OPTIONS],
                allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Requested-With", "Accept", "Origin", "Referer", "User-Agent"]
            )
        )

        # Update JWT authorizer with actual API ID
        jwt_authorizer.api_id = http_api.http_api_id

        # Create Lambda integration for HTTP API
        lambda_integration = integrations.HttpLambdaIntegration(
            "QuiltMcpLambdaIntegration",
            lambda_fn
        )

        # Add routes with JWT authorization
        http_api.add_routes(
            path="/mcp",
            methods=[apigwv2.HttpMethod.GET, apigwv2.HttpMethod.POST],
            integration=lambda_integration,
            authorizer=apigwv2.HttpJwtAuthorizer(
                "McpJwtAuth",
                jwt_audience=[user_pool_client.user_pool_client_id],
                jwt_issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}"
            )
        )

        # Add catch-all proxy route
        http_api.add_routes(
            path="/mcp/{proxy+}",
            methods=[apigwv2.HttpMethod.ANY],
            integration=lambda_integration,
            authorizer=apigwv2.HttpJwtAuthorizer(
                "McpProxyJwtAuth", 
                jwt_audience=[user_pool_client.user_pool_client_id],
                jwt_issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}"
            )
        )

        # Outputs
        CfnOutput(
            self, "ApiEndpoint",
            value=f"{http_api.url}mcp/",
            description="MCP Server HTTP API Endpoint"
        )

        CfnOutput(
            self, "TokenEndpoint",
            value=f"https://{user_pool_domain.domain_name}.auth.{self.region}.amazoncognito.com/oauth2/token",
            description="OAuth 2.0 Token Endpoint for client credentials"
        )

        CfnOutput(
            self, "ClientId",
            value=user_pool_client.user_pool_client_id,
            description="Cognito App Client ID for authentication"
        )

        CfnOutput(
            self, "UserPoolId",
            value=user_pool.user_pool_id,
            description="Cognito User Pool ID"
        )

        CfnOutput(
            self, "ResourceServerIdentifier", 
            value=resource_server.user_pool_resource_server_identifier,
            description="Resource Server identifier for scopes"
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