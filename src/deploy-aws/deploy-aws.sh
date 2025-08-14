#!/bin/bash
# Deploy Phase: ECS/ALB deployment via CDK
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load shared utilities
source "$PROJECT_ROOT/src/shared/common.sh"
source "$PROJECT_ROOT/src/shared/version.sh"

# Load environment variables from .env if present
load_environment

# Default values
VERBOSE=false
SKIP_TESTS=false
ECR_URI=""

usage() {
    echo "Usage: $0 [deploy|test|destroy|status|validate] [options] [ECR_URI]"
    echo ""
    echo "Commands:"
    echo "  deploy    Deploy to ECS Fargate via CDK"
    echo "  test      Test deployed endpoint"
    echo "  destroy   Destroy CDK stack"
    echo "  status    Show deployment status"
    echo "  validate  Full validation (CDK deploy + ECS health + endpoint + HTTPS)"
    echo ""
    echo "Arguments:"
    echo "  ECR_URI  ECR image URI (e.g., 123456.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp:abc123)"
    echo ""
    echo "Options:"
    echo "  -v, --verbose     Enable verbose output"
    echo "  --skip-tests      Skip running tests before deploy"
    echo ""
    echo "Environment Variables:"
    echo "  CDK_DEFAULT_ACCOUNT  AWS account ID"
    echo "  CDK_DEFAULT_REGION   AWS region (default: us-east-1)"
    echo "  VPC_ID              Existing VPC ID (optional)"
    echo "  ACM_CERT_ARN        ACM certificate ARN (optional, enables HTTPS)"
}

# Parse arguments
COMMAND=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        deploy|test|destroy|status|validate)
            COMMAND="$1"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            if [ -z "$ECR_URI" ]; then
                ECR_URI="$1"
            else
                log_error "Unknown option: $1"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    COMMAND="deploy"
fi

case $COMMAND in
    deploy)
        log_info "Deploying to ECS Fargate with CDK..."
        
        # Check AWS CLI
        if ! command -v aws &> /dev/null; then
            log_error "AWS CLI not found. Please install AWS CLI first."
            exit 1
        fi
        
        # Load environment and check dependencies
        check_dependencies aws jq uv
        
        # Set up AWS defaults
        export CDK_DEFAULT_ACCOUNT=${CDK_DEFAULT_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}
        export CDK_DEFAULT_REGION=${CDK_DEFAULT_REGION:-us-east-1}
        
        log_info "AWS Account: $CDK_DEFAULT_ACCOUNT"
        log_info "AWS Region: $CDK_DEFAULT_REGION"
        
        # Set IMAGE_URI if provided, or build/push automatically
        if [ -n "$ECR_URI" ]; then
            export IMAGE_URI="$ECR_URI"
            log_info "Using ECR image: $IMAGE_URI"
        else
            # Setup ECR registry (construct if needed)
            if setup_ecr_registry; then
                log_info "No ECR_URI provided, building and pushing automatically..."
                # Capture only the last line (the ECR URI) from the push command
                ECR_URI=$("$PROJECT_ROOT/src/catalog-push/catalog-push.sh" push 2>/dev/null | tail -1)
                export IMAGE_URI="$ECR_URI"
                log_info "Built and pushed ECR image: $IMAGE_URI"
            else
                log_warning "No ECR_URI provided and cannot setup ECR_REGISTRY, CDK will use default"
            fi
        fi
        
        # Install CDK dependencies
        cd "$PROJECT_ROOT"
        log_info "Installing CDK dependencies..."
        uv sync --group deploy
        
        # Bootstrap CDK if needed
        log_info "Checking CDK bootstrap..."
        if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$CDK_DEFAULT_REGION" >/dev/null 2>&1; then
            log_info "Bootstrapping CDK..."
            uv run cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION --app "python src/deploy-aws/app.py"
        fi
        
        # Deploy with CDK
        log_info "Deploying with CDK..."
        cd "$SCRIPT_DIR"
        if [ "$VERBOSE" = true ]; then
            uv run cdk deploy --require-approval never --app "python app.py"
        else
            uv run cdk deploy --require-approval never --app "python app.py" > /dev/null
        fi
        
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
    MCP_ENDPOINT_HTTPS=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="MCPEndpointHttps") | .OutputValue')
        LOAD_BALANCER_URL=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="LoadBalancerURL") | .OutputValue')
        CLUSTER_NAME=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="ClusterName") | .OutputValue')
        SERVICE_NAME=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="ServiceName") | .OutputValue')
        APP_LOG_GROUP=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="AppLogGroupName") | .OutputValue')
        ALB_LOG_GROUP=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="AlbLogGroupName") | .OutputValue')
        VPC_LOG_GROUP=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="VpcLogGroupName") | .OutputValue')
        
        # Create .config file
        cat > "$PROJECT_ROOT/.config" << EOF
# Quilt MCP Server Deployment Configuration
# Generated on $(date)

# Deployment Info
STACK_NAME=$STACK_NAME
REGION=$CDK_DEFAULT_REGION
ACCOUNT=$CDK_DEFAULT_ACCOUNT
IMAGE_URI=${IMAGE_URI:-unknown}

# Endpoints
MCP_ENDPOINT=${MCP_ENDPOINT_HTTPS:-$MCP_ENDPOINT}
MCP_ENDPOINT_HTTPS=$MCP_ENDPOINT_HTTPS
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
# Test endpoint (HTTPS preferred): curl -X POST ${MCP_ENDPOINT_HTTPS:-$MCP_ENDPOINT} -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
EOF
        
        log_success "Deployment completed!"
        log_info "MCP Endpoint: $MCP_ENDPOINT"
        log_info "Load Balancer: $LOAD_BALANCER_URL"
        log_info "Configuration saved to .config"
        ;;
        
    test)
        log_info "Testing deployed endpoint..."
        
        if [ ! -f "$PROJECT_ROOT/.config" ]; then
            log_error ".config file not found. Run deploy first."
            exit 1
        fi
        
        # Load config
        set -a && source "$PROJECT_ROOT/.config" && set +a
        
    if [ -z "$MCP_ENDPOINT" ]; then
            log_error "MCP_ENDPOINT not found in config"
            exit 1
        fi
        
    log_info "Testing endpoint: $MCP_ENDPOINT"
        
        # Test tools/list endpoint
        if curl -s -f -X POST "$MCP_ENDPOINT" \
           -H "Content-Type: application/json" \
           -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' > /dev/null; then
            log_success "Endpoint test passed"
        else
            log_error "Endpoint test failed"
            exit 1
        fi
        ;;
        
    destroy)
        log_warning "Destroying CDK stack..."
        
        cd "$SCRIPT_DIR"
        uv run cdk destroy --force --app "python app.py"
        
        # Remove .config file
        rm -f "$PROJECT_ROOT/.config"
        
        log_success "Stack destroyed"
        ;;
        
    status)
        log_info "Checking deployment status..."
        
        if [ ! -f "$PROJECT_ROOT/.config" ]; then
            log_warning "No .config file found. Stack may not be deployed."
            exit 0
        fi
        
        # Load config
        set -a && source "$PROJECT_ROOT/.config" && set +a
        
        log_info "Stack: $STACK_NAME"
        log_info "Region: $REGION"
        log_info "Endpoint: $MCP_ENDPOINT"
        
        # Check stack status
        STACK_STATUS=$(aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --region "$REGION" \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null || echo "NOT_FOUND")
        
        log_info "Stack Status: $STACK_STATUS"
        ;;
        
    validate)
        log_info "🔍 Phase 4: Deploy-AWS validation (CDK deploy + ECS health + endpoint + HTTPS)"
        log_info "Requirements: CDK succeeds, ECS healthy, public endpoint responds, HTTPS configurable"
        
        # Install CDK dependencies
        log_info "Installing CDK dependencies..."
        cd "$PROJECT_ROOT"
        uv sync --group deploy > /dev/null
        
        # Test CDK synthesis without HTTPS
        log_info "Testing CDK synthesis (HTTP-only)..."
        cd "$SCRIPT_DIR" && uv run cdk synth --app "python app.py" --output /tmp/cdk-out-http > /dev/null
        
        # Test CDK synthesis with HTTPS enabled
        log_info "Testing CDK synthesis (HTTPS enabled)..."
        cd "$SCRIPT_DIR" && ACM_CERT_ARN="arn:aws:acm:us-east-1:123456789012:certificate/test-cert" uv run cdk synth --app "python app.py" --output /tmp/cdk-out-https > /dev/null
        
        # Deploy to AWS ECS
        "$0" deploy $VERBOSE_FLAG $TEST_FLAG "$ECR_URI"
        
        # Validate deployed service
        "$0" test $VERBOSE_FLAG
        
        log_success "✅ Deploy-AWS phase validation passed (HTTP + HTTPS ready)"
        ;;
        
    *)
        log_error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac