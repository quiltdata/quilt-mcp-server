#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Deploying Quilt MCP Server to AWS Lambda${NC}"

# Load environment
if [ -f ".env" ]; then
    echo -e "${GREEN}Loading environment from .env${NC}"
    set -a && source .env && set +a
else
    echo -e "${RED}❌ .env file not found. Copy env.example to .env and configure it${NC}"
    exit 1
fi

# Validate required variables
if [ -z "$QUILT_READ_POLICY_ARN" ]; then
    echo -e "${RED}❌ QUILT_READ_POLICY_ARN is required in .env${NC}"
    exit 1
fi

# Set defaults
export CDK_DEFAULT_ACCOUNT=${CDK_DEFAULT_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}
export CDK_DEFAULT_REGION=${CDK_DEFAULT_REGION:-us-east-1}

echo -e "${GREEN}Deploying to account ${CDK_DEFAULT_ACCOUNT} in ${CDK_DEFAULT_REGION}${NC}"

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
uv sync --group deploy

# Package Lambda function
echo -e "${BLUE}Packaging Lambda function...${NC}"
LAMBDA_PACKAGE_DIR=$(mktemp -d)

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "Building Docker image for Lambda..."
  docker build --platform linux/amd64 -t quilt-mcp-builder . >/dev/null 2>&1
  
  echo "Extracting Lambda package..."
  docker run --rm --platform linux/amd64 \
    -v "$LAMBDA_PACKAGE_DIR":/output \
    --entrypoint="" \
    quilt-mcp-builder \
    bash -c "
      cp -r /usr/local/lib/python3.11/site-packages/* /output/
      cp /app/quilt/*.py /output/ 2>/dev/null || true
      chmod -R 755 /output/
    " >/dev/null 2>&1
    
  echo "✅ Lambda package built successfully"
else
  echo -e "${RED}❌ Docker not available. Install Docker for proper Lambda builds.${NC}"
  exit 1
fi

export LAMBDA_PACKAGE_DIR="$LAMBDA_PACKAGE_DIR"

# Bootstrap CDK if needed
echo -e "${BLUE}Checking CDK bootstrap...${NC}"
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $CDK_DEFAULT_REGION >/dev/null 2>&1; then
    echo -e "${YELLOW}Bootstrapping CDK...${NC}"
    uv run cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION --app "python app.py"
fi

# Deploy
echo -e "${BLUE}Deploying to AWS...${NC}"
uv run cdk deploy --require-approval never --app "python app.py"

# Cleanup
rm -rf "$LAMBDA_PACKAGE_DIR"

# Get outputs
API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" --output text)
LOG_GROUP_NAME=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='LogGroupName'].OutputValue" --output text)
API_LOG_GROUP_NAME=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='ApiLogGroupName'].OutputValue" --output text)

echo -e "${GREEN}🎉 Deployment completed!${NC}"
echo -e "${GREEN}Claude MCP Server URL: ${API_ENDPOINT}${NC}"
echo -e "${BLUE}View Lambda logs: aws logs tail ${LOG_GROUP_NAME} --follow --region ${CDK_DEFAULT_REGION}${NC}"
echo -e "${BLUE}View API Gateway logs: aws logs tail ${API_LOG_GROUP_NAME} --follow --region ${CDK_DEFAULT_REGION}${NC}"

# Test endpoint
echo -e "${BLUE}Testing endpoint...${NC}"
MCP_RESPONSE=$(curl -s -X POST "${API_ENDPOINT}" -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}')

if echo "$MCP_RESPONSE" | grep -q "tools"; then
    echo -e "${GREEN}✅ MCP endpoint is working${NC}"
else
    echo -e "${RED}❌ MCP endpoint test failed${NC}"
fi