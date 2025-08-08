#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Quilt MCP Server to AWS Lambda${NC}"

# Check if .env file exists and source it
if [ -f "../.env" ]; then
    echo -e "${GREEN}Loading environment from .env file${NC}"
    export $(cat ../.env | grep -v '^#' | grep -v '^$' | xargs)
elif [ -f "../env.example" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Please copy env.example to .env and configure it${NC}"
    echo -e "${YELLOW}Required: QUILT_READ_POLICY_ARN${NC}"
    echo -e "${YELLOW}Optional: CDK_DEFAULT_ACCOUNT, CDK_DEFAULT_REGION, AWS_PROFILE${NC}"
    exit 1
fi

# Validate required environment variables
if [ -z "$QUILT_READ_POLICY_ARN" ]; then
    echo -e "${RED}❌ QUILT_READ_POLICY_ARN is required${NC}"
    exit 1
fi

# Set defaults
export CDK_DEFAULT_ACCOUNT=${CDK_DEFAULT_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}
export CDK_DEFAULT_REGION=${CDK_DEFAULT_REGION:-us-east-1}
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-$CDK_DEFAULT_REGION}

echo -e "${GREEN}Configuration:${NC}"
echo -e "  Account: ${CDK_DEFAULT_ACCOUNT}"
echo -e "  Region: ${CDK_DEFAULT_REGION}"
echo -e "  Quilt Policy ARN: ${QUILT_READ_POLICY_ARN}"
echo -e "  AWS Profile: ${AWS_PROFILE:-default}"

# Install Python dependencies for CDK
echo -e "${BLUE}Installing CDK dependencies...${NC}"
cd ..
uv sync --group deploy
cd deploy

# Package Lambda function with dependencies
echo -e "${BLUE}Packaging Lambda function...${NC}"
cd ../quilt

# Create a temporary directory for Lambda packaging
LAMBDA_PACKAGE_DIR=$(mktemp -d)
echo "Packaging to: $LAMBDA_PACKAGE_DIR"

# Copy source files
cp *.py "$LAMBDA_PACKAGE_DIR/"

# Install Lambda dependencies into the package directory
cd /Users/ernest/GitHub/fast-mcp-server
uv pip install --target "$LAMBDA_PACKAGE_DIR" "quilt3>=5.6.0" "fastmcp>=0.1.0" "boto3>=1.34.0" "botocore>=1.34.0"

# Create deployment package
cd /Users/ernest/GitHub/fast-mcp-server/deploy
export LAMBDA_PACKAGE_DIR="$LAMBDA_PACKAGE_DIR"

# Bootstrap CDK (if needed)
echo -e "${BLUE}Checking CDK bootstrap...${NC}"
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $CDK_DEFAULT_REGION >/dev/null 2>&1; then
    echo -e "${YELLOW}Bootstrapping CDK...${NC}"
    cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION
fi

# Deploy the stack
echo -e "${BLUE}Deploying CDK stack...${NC}"
cdk deploy --require-approval never

# Clean up temporary package directory
echo -e "${BLUE}Cleaning up temporary files...${NC}"
rm -rf "$LAMBDA_PACKAGE_DIR"

# Get Cognito credentials
echo -e "${BLUE}Retrieving Cognito credentials...${NC}"
COGNITO_USER_POOL_ID=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolId'].OutputValue" --output text)
COGNITO_CLIENT_ID=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='CognitoClientId'].OutputValue" --output text)
COGNITO_CLIENT_SECRET=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='CognitoClientSecret'].OutputValue" --output text)
COGNITO_DOMAIN=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='CognitoDomain'].OutputValue" --output text)

# Get the API endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" --output text)

# Get Lambda function name and log group for debugging
LAMBDA_FUNCTION_NAME=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='LambdaFunctionName'].OutputValue" --output text)
LOG_GROUP_NAME=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='LogGroupName'].OutputValue" --output text)

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${GREEN}📝 Claude MCP Server Configuration:${NC}"
echo -e "  URL: ${API_ENDPOINT}"
echo -e "  Type: Streamable HTTP with OAuth2"
echo
echo -e "${GREEN}🔐 Cognito Authentication Credentials:${NC}"
echo -e "  User Pool ID: ${COGNITO_USER_POOL_ID}"
echo -e "  Client ID: ${COGNITO_CLIENT_ID}"
echo -e "  Client Secret: ${COGNITO_CLIENT_SECRET}"
echo -e "  Auth Domain: https://${COGNITO_DOMAIN}"
echo
echo -e "${BLUE}🔧 Debugging Information:${NC}"
echo -e "  Lambda Function: ${LAMBDA_FUNCTION_NAME}"
echo -e "  Log Group: ${LOG_GROUP_NAME}"
echo -e "  View logs: aws logs tail ${LOG_GROUP_NAME} --follow --region ${CDK_DEFAULT_REGION}"
echo

# Test the endpoint with Cognito authentication
echo -e "${BLUE}🧪 Testing endpoint...${NC}"

# Get OAuth2 token using client credentials flow
echo -e "  Getting OAuth2 token..."
TOKEN_RESPONSE=$(curl -s -X POST \
  "https://${COGNITO_DOMAIN}/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "${COGNITO_CLIENT_ID}:${COGNITO_CLIENT_SECRET}" \
  -d "grant_type=client_credentials")

# Extract access token
ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -n "$ACCESS_TOKEN" ]; then
    echo -e "${GREEN}  ✅ OAuth2 token obtained successfully${NC}"
    
    # Test the MCP endpoint
    echo -e "  Testing MCP tools/list endpoint..."
    MCP_RESPONSE=$(curl -s -X POST \
      "${API_ENDPOINT}" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}')
    
    if echo "$MCP_RESPONSE" | grep -q "tools"; then
        echo -e "${GREEN}  ✅ MCP endpoint is working correctly${NC}"
        echo -e "  Response: ${MCP_RESPONSE:0:100}..."
    else
        echo -e "${RED}  ❌ MCP endpoint test failed${NC}"
        echo -e "  Response: $MCP_RESPONSE"
    fi
else
    echo -e "${RED}  ❌ Failed to get OAuth2 token${NC}"
    echo -e "  Response: $TOKEN_RESPONSE"
    echo -e "${YELLOW}  Note: You may need to create a user in Cognito first${NC}"
fi

echo
echo -e "${BLUE}To connect from Claude:${NC}"
echo -e "1. Add a new remote MCP server"
echo -e "2. Set URL to: ${API_ENDPOINT}"
echo -e "3. Set Type to: Streamable HTTP"
echo -e "4. Configure OAuth2 with the credentials above"
echo -e "5. Create a user in Cognito: aws cognito-idp admin-create-user --user-pool-id ${COGNITO_USER_POOL_ID} --username <username> --temporary-password <temp-password> --region ${CDK_DEFAULT_REGION}"
echo
echo -e "${YELLOW}💾 Save these credentials securely!${NC}"