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
if [ -f ".env" ]; then
    echo -e "${GREEN}Loading environment from .env file${NC}"
    set -a  # automatically export all variables
    source .env
    set +a  # turn off automatic export
elif [ -f "env.example" ]; then
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

# Debug: Check if environment variables are properly exported
echo -e "${BLUE}Debug - Environment variables for CDK:${NC}"
echo -e "  QUILT_READ_POLICY_ARN: ${QUILT_READ_POLICY_ARN}"

# Install Python dependencies for CDK
echo -e "${BLUE}Installing CDK dependencies...${NC}"
uv sync --group deploy

# Package Lambda function with dependencies
echo -e "${BLUE}Packaging Lambda function...${NC}"

# Create a temporary directory for Lambda packaging
LAMBDA_PACKAGE_DIR=$(mktemp -d)
echo "Packaging to: $LAMBDA_PACKAGE_DIR"

# Check if Docker is available for Linux packaging
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "Using Dockerfile to build Linux-compatible package..."
  
  # Build the Docker image with all dependencies
  echo "Building Docker image with dependencies..."
  docker build --platform linux/amd64 -t quilt-mcp-builder .
  
  # Create a container to extract the built environment
  echo "Extracting dependencies from Docker container..."
  docker run --rm \
    -v "$LAMBDA_PACKAGE_DIR":/output \
    --entrypoint="" \
    quilt-mcp-builder \
    bash -c "
      # Copy system Python site-packages (since we installed with --system)
      echo \"Copying system site-packages...\"
      cp -r /usr/local/lib/python3.11/site-packages/* /output/
      # Copy our source files
      cp /app/quilt/*.py /output/ 2>/dev/null || echo \"Warning: Could not copy quilt source files\"
      # Ensure permissions are correct
      chmod -R 755 /output/
      # List what we copied for debugging
      echo \"Packaged files:\"
      ls -la /output/ | head -20
    "
  
  echo "✅ Docker-based packaging completed using Dockerfile"
  
else
  echo "Docker not available, using fallback approach..."
  
  # Copy source files first
  cp quilt/*.py "$LAMBDA_PACKAGE_DIR/"
  
  # Use uv to install dependencies
  uv pip install --target "$LAMBDA_PACKAGE_DIR" --no-build-isolation \
    "quilt3>=5.6.0" \
    "fastmcp>=0.1.0" \
    "boto3>=1.34.0" \
    "botocore>=1.34.0"

  echo "❌ Using macOS binaries - Lambda will likely fail with pydantic_core import error"
  echo "💡 Install Docker to use the Dockerfile for proper Linux builds"
fi

# Create deployment package
export LAMBDA_PACKAGE_DIR="$LAMBDA_PACKAGE_DIR"

# Bootstrap CDK (if needed)
echo -e "${BLUE}Checking CDK bootstrap...${NC}"
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $CDK_DEFAULT_REGION >/dev/null 2>&1; then
    echo -e "${YELLOW}Bootstrapping CDK...${NC}"
    uv run cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION --app "python app.py"
fi

# Deploy the stack
echo -e "${BLUE}Deploying CDK stack...${NC}"
uv run cdk deploy --require-approval never --app "python app.py"

# Clean up temporary package directory
echo -e "${BLUE}Cleaning up temporary files...${NC}"
rm -rf "$LAMBDA_PACKAGE_DIR"

# Get deployment outputs
echo -e "${BLUE}Retrieving deployment outputs...${NC}"

# Get the API endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" --output text)

# Get Lambda function name and log group for debugging
LAMBDA_FUNCTION_NAME=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='LambdaFunctionName'].OutputValue" --output text)
LOG_GROUP_NAME=$(aws cloudformation describe-stacks --stack-name QuiltMcpStack --region $CDK_DEFAULT_REGION --query "Stacks[0].Outputs[?OutputKey=='LogGroupName'].OutputValue" --output text)

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${GREEN}📝 Claude MCP Server Configuration:${NC}"
echo -e "  URL: ${API_ENDPOINT}"
echo -e "  Type: Streamable HTTP (no authentication)"
echo
echo -e "${BLUE}🔧 Debugging Information:${NC}"
echo -e "  Lambda Function: ${LAMBDA_FUNCTION_NAME}"
echo -e "  Lambda Log Group: ${LOG_GROUP_NAME}"
echo -e "  View Lambda logs: aws logs tail ${LOG_GROUP_NAME} --follow --region ${CDK_DEFAULT_REGION}"
echo

# Test the endpoint 
echo -e "${BLUE}🧪 Testing endpoint...${NC}"

# Test basic connectivity
echo -e "  Testing MCP tools/list endpoint..."
MCP_RESPONSE=$(curl -s -X POST \
  "${API_ENDPOINT}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}')

if echo "$MCP_RESPONSE" | grep -q "tools"; then
    echo -e "${GREEN}  ✅ MCP endpoint is working correctly${NC}"
    echo -e "  Response: ${MCP_RESPONSE:0:100}..."
else
    echo -e "${RED}  ❌ MCP endpoint test failed${NC}"
    echo -e "  Response: $MCP_RESPONSE"
fi

echo
echo -e "${BLUE}To connect from Claude:${NC}"
echo -e "1. Add a new remote MCP server"
echo -e "2. Set URL to: ${API_ENDPOINT}"
echo -e "3. Set Type to: Streamable HTTP (no authentication needed for testing)"
echo