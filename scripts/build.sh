#!/bin/bash
# Simple build script for the FastMCP server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load common functions
source "$SCRIPT_DIR/common.sh"

# Default values
VERBOSE=false
SKIP_TESTS=false
PUSH_IMAGE=false
IMAGE_TAG="latest"

usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  build      Build Docker image"
    echo "  test       Run tests locally"
    echo "  run        Run server locally (development)"
    echo "  docker     Run server in Docker container"
    echo "  deploy     Deploy to ECS Fargate"
    echo "  clean      Clean build artifacts"
    echo ""
    echo "Options:"
    echo "  -v, --verbose    Enable verbose output"
    echo "  -t, --tag TAG    Docker image tag (default: latest)"
    echo "  --skip-tests     Skip running tests"
    echo "  --push           Push image to registry"
    echo "  -h, --help       Show this help"
}


# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --push)
            PUSH_IMAGE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        build|test|run|docker|deploy|clean)
            COMMAND="$1"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    log_error "No command specified"
    usage
    exit 1
fi

cd "$PROJECT_ROOT"

case $COMMAND in
    build)
        log_info "Building Docker image..."
        if [ "$VERBOSE" = true ]; then
            docker build -t "quilt-mcp:$IMAGE_TAG" .
        else
            docker build -t "quilt-mcp:$IMAGE_TAG" . > /dev/null
        fi
        
        if [ "$PUSH_IMAGE" = true ]; then
            log_info "Pushing image to registry..."
            docker push "quilt-mcp:$IMAGE_TAG"
        fi
        
        log_info "Build completed successfully"
        ;;
        
    test)
        log_info "Running tests..."
        if ! command -v uv &> /dev/null; then
            log_error "uv not found. Please install uv first."
            exit 1
        fi
        
        # Install dependencies
        uv sync --group test
        
        # Run tests
        if [ "$VERBOSE" = true ]; then
            uv run python -m pytest tests/ -v
        else
            uv run python -m pytest tests/
        fi
        
        log_info "Tests completed successfully"
        ;;
        
    run)
        log_info "Starting server locally..."
        if ! command -v uv &> /dev/null; then
            log_error "uv not found. Please install uv first."
            exit 1
        fi
        
        # Install dependencies
        uv sync
        
        # Run server
        log_info "Server starting on http://127.0.0.1:8000/mcp"
        uv run python main.py
        ;;
        
    docker)
        log_info "Running server in Docker..."
        
        # Build if image doesn't exist
        if ! docker image inspect "quilt-mcp:$IMAGE_TAG" > /dev/null 2>&1; then
            log_info "Image not found, building first..."
            docker build -t "quilt-mcp:$IMAGE_TAG" .
        fi
        
        # Run container
        log_info "Server starting on http://127.0.0.1:8000/mcp"
        docker run --rm -p 8000:8000 "quilt-mcp:$IMAGE_TAG"
        ;;
        
    deploy)
        log_info "Deploying to ECS Fargate with CDK..."
        
        # Build and test first
        if [ "$SKIP_TESTS" != true ]; then
            "$0" test
        fi
        "$0" build --tag "$IMAGE_TAG"
        
        # Check AWS CLI
        if ! command -v aws &> /dev/null; then
            log_error "AWS CLI not found. Please install AWS CLI first."
            exit 1
        fi
        
        # Load environment and check dependencies
        load_environment
        check_dependencies aws jq
        
        # Install CDK dependencies
        log_info "Installing CDK dependencies..."
        uv sync --group deploy
        
        # Set up AWS defaults
        setup_aws_defaults
        
        # Set IMAGE_URI if not provided (use local image for development)
        if [ -z "$IMAGE_URI" ]; then
            log_info "IMAGE_URI not set, using local Docker image"
            export IMAGE_URI="quilt-mcp:$IMAGE_TAG"
        fi
        
        log_info "Deployment settings:"
        log_info "  Account: $CDK_DEFAULT_ACCOUNT"
        log_info "  Region: $CDK_DEFAULT_REGION"
        log_info "  Image: $IMAGE_URI"
        if [ -n "$VPC_ID" ]; then
            log_info "  VPC: $VPC_ID"
        else
            log_info "  VPC: Will create new VPC"
        fi
        
        # Bootstrap CDK if needed
        log_info "Checking CDK bootstrap..."
        if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$CDK_DEFAULT_REGION" >/dev/null 2>&1; then
            log_info "Bootstrapping CDK..."
            uv run cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION
        fi
        
        # Deploy with CDK
        log_info "Deploying with CDK..."
        uv run cdk deploy --require-approval never
        
        # Get outputs and create .config
        log_info "Getting deployment outputs..."
        STACK_NAME="QuiltMcpFargateStack"
        
        # Get all stack outputs in one call
        STACK_OUTPUTS=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --region "$CDK_DEFAULT_REGION" \
            --query 'Stacks[0].Outputs' \
            --output json)
        
        
        # Parse outputs using jq
        MCP_ENDPOINT=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="MCPEndpoint") | .OutputValue')
        LOAD_BALANCER_URL=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="LoadBalancerURL") | .OutputValue')
        CLUSTER_NAME=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="ClusterName") | .OutputValue')
        SERVICE_NAME=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="ServiceName") | .OutputValue')
        APP_LOG_GROUP=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="AppLogGroupName") | .OutputValue')
        ALB_LOG_GROUP=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="AlbLogGroupName") | .OutputValue')
        VPC_LOG_GROUP=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="VpcLogGroupName") | .OutputValue')
        
        # Create .config file
        cat > .config << EOF
# Quilt MCP Server Deployment Configuration
# Generated on $(date)

# Deployment Info
STACK_NAME=$STACK_NAME
REGION=$CDK_DEFAULT_REGION
ACCOUNT=$CDK_DEFAULT_ACCOUNT
IMAGE_URI=$IMAGE_URI

# Endpoints
MCP_ENDPOINT=$MCP_ENDPOINT
LOAD_BALANCER_URL=$LOAD_BALANCER_URL

# AWS Resources
CLUSTER_NAME=$CLUSTER_NAME
SERVICE_NAME=$SERVICE_NAME
APP_LOG_GROUP=$APP_LOG_GROUP
ALB_LOG_GROUP=$ALB_LOG_GROUP
VPC_LOG_GROUP=$VPC_LOG_GROUP

# Quick Commands
# View app logs: aws logs tail $APP_LOG_GROUP --follow --region $CDK_DEFAULT_REGION
# View ALB logs: aws logs tail $ALB_LOG_GROUP --follow --region $CDK_DEFAULT_REGION
# View VPC logs: aws logs tail $VPC_LOG_GROUP --follow --region $CDK_DEFAULT_REGION
# Test endpoint: curl -X POST $MCP_ENDPOINT -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
# ECS service: aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $CDK_DEFAULT_REGION
EOF
        
        log_info "Deployment completed successfully!"
        log_info "MCP Endpoint: $MCP_ENDPOINT"
        log_info "Load Balancer: $LOAD_BALANCER_URL"
        log_info "Configuration saved to .config"
        ;;
        
    clean)
        log_info "Cleaning build artifacts..."
        
        # Remove Docker images
        docker images "quilt-mcp" -q | xargs -r docker rmi -f
        
        # Clean Python cache
        find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete 2>/dev/null || true
        
        # Clean coverage reports
        rm -rf htmlcov/ .coverage
        
        log_info "Clean completed"
        ;;
        
    *)
        log_error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac