#!/bin/bash
# Common utilities for deployment scripts

# Colors for output
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export NC='\033[0m'

# Default values
export STACK_NAME="QuiltMcpFargateStack"
export DEFAULT_REGION="us-east-1"

# Logging functions
log_info() {
    echo -e "${BLUE}$1${NC}"
}

log_success() {
    echo -e "${GREEN}$1${NC}"
}

log_warning() {
    echo -e "${YELLOW}$1${NC}"
}

log_error() {
    echo -e "${RED}$1${NC}"
}

# Load environment variables (optional)
load_environment() {
    if [ -f ".env" ]; then
        log_info "Loading environment from .env"
        set -a && source .env && set +a
    fi
}

# Check required tools
check_dependencies() {
    local tools=("$@")
    local missing=()
    
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing+=("$tool")
        fi
    done
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "❌ Missing required tools: ${missing[*]}"
        case "${missing[0]}" in
            jq)
                log_error "Install with: brew install jq (macOS) or apt-get install jq (Ubuntu)"
                ;;
            aws)
                log_error "Install AWS CLI: https://aws.amazon.com/cli/"
                ;;
            curl)
                log_error "Install with: brew install curl (macOS) or apt-get install curl (Ubuntu)"
                ;;
        esac
        exit 1
    fi
}

# Set AWS defaults
setup_aws_defaults() {
    export CDK_DEFAULT_ACCOUNT=${CDK_DEFAULT_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}
    export CDK_DEFAULT_REGION=${CDK_DEFAULT_REGION:-$DEFAULT_REGION}
    
    log_success "AWS Account: ${CDK_DEFAULT_ACCOUNT}"
    log_success "AWS Region: ${CDK_DEFAULT_REGION}"
}

# Set ECR registry - construct if not provided
setup_ecr_registry() {
    if [ -z "$ECR_REGISTRY" ]; then
        # Try to construct from AWS account and region
        if [ -n "$CDK_DEFAULT_ACCOUNT" ] && [ -n "$CDK_DEFAULT_REGION" ]; then
            export ECR_REGISTRY="$CDK_DEFAULT_ACCOUNT.dkr.ecr.$CDK_DEFAULT_REGION.amazonaws.com"
            log_info "Constructed ECR_REGISTRY: $ECR_REGISTRY"
        elif [ -n "$AWS_ACCOUNT_ID" ] && [ -n "$AWS_DEFAULT_REGION" ]; then
            export ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com"
            log_info "Constructed ECR_REGISTRY: $ECR_REGISTRY"
        else
            log_error "ECR_REGISTRY not provided and cannot construct from environment"
            log_info "Either set ECR_REGISTRY or provide CDK_DEFAULT_ACCOUNT+CDK_DEFAULT_REGION"
            log_info "Example: export ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com"
            return 1
        fi
    fi
    
    # Set default repository name
    export ECR_REPOSITORY=${ECR_REPOSITORY:-quilt-mcp}
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Docker is available and running
check_docker() {
    if ! command_exists docker; then
        log_error "❌ Docker not installed. Install Docker for proper Lambda builds."
        exit 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        log_error "❌ Docker daemon not running. Start Docker for proper Lambda builds."
        exit 1
    fi
    
    log_success "✅ Docker available"
}

# Check if jq is available
check_jq() {
    if ! command_exists jq; then
        log_error "❌ jq not installed. Install jq for JSON processing."
        exit 1
    fi
}

# Get stack outputs
get_stack_outputs() {
    local region=${1:-$CDK_DEFAULT_REGION}
    log_info "Retrieving deployment outputs from CloudFormation..."
    
    # Disable colors for this AWS call to prevent contamination
    NO_COLOR=1 aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$region" \
        --query "Stacks[0].Outputs" \
        --output json
}

# Extract specific output value from stack outputs
extract_output_value() {
    local outputs="$1"
    local key="$2"
    echo "$outputs" | jq -r ".[] | select(.OutputKey==\"$key\") | .OutputValue"
}


# Load configuration
load_config() {
    if [ ! -f ".config" ]; then
        log_error "❌ .config file not found. Run './scripts/build.sh deploy' first"
        exit 1
    fi
    
    log_info "Loading configuration from .config"
    set -a && source .config && set +a
    
    # Validate required variables for ECS deployment
    local required_vars=(
        "STACK_NAME"
        "REGION"
        "MCP_ENDPOINT"
        "CLUSTER_NAME"
        "SERVICE_NAME"
        "APP_LOG_GROUP"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "❌ Missing required configuration: $var"
            log_error "Run './scripts/build.sh deploy' to regenerate .config"
            exit 1
        fi
    done
}

# Display quick commands
show_quick_commands() {
    local mcp_endpoint="$1"
    
    echo ""
    log_info "🔧 Quick Commands:"
    log_info "View logs: ./scripts/logs.sh"
    log_info "Test API: ./scripts/test.sh"
    log_info "Manual test:"
    echo -e "${BLUE}  curl -X POST ${mcp_endpoint} -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}'${NC}"
}

# Check if CDK is bootstrapped
check_cdk_bootstrap() {
    local region=${1:-$CDK_DEFAULT_REGION}
    
    log_info "Checking CDK bootstrap..."
    if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$region" >/dev/null 2>&1; then
        return 1
    fi
    return 0
}

# Bootstrap CDK
bootstrap_cdk() {
    local account="$1"
    local region="$2"
    
    log_warning "Bootstrapping CDK..."
    uv run cdk bootstrap "aws://$account/$region" --app "python app.py"
}

# Cleanup temporary directories
cleanup_temp_dir() {
    local temp_dir="$1"
    if [ -n "$temp_dir" ] && [ -d "$temp_dir" ]; then
        rm -rf "$temp_dir"
        log_info "Cleaned up temporary directory: $temp_dir"
    fi
}