#!/bin/bash
# Common utilities for deployment scripts

# Colors for output
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export NC='\033[0m'

# Default values
export STACK_NAME="QuiltMcpStack"
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

# Load environment variables
load_environment() {
    if [ -f ".env" ]; then
        log_success "Loading environment from .env"
        set -a && source .env && set +a
    else
        log_error "❌ .env file not found. Copy env.example to .env and configure it"
        exit 1
    fi
}

# Validate required environment variables
validate_environment() {
    if [ -z "$QUILT_READ_POLICY_ARN" ]; then
        log_error "❌ QUILT_READ_POLICY_ARN is required in .env"
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

# Get Cognito client secret
get_client_secret() {
    local user_pool_id="$1"
    local client_id="$2"
    local region=${3:-$CDK_DEFAULT_REGION}
    
    log_info "Retrieving Cognito client secret..."
    NO_COLOR=1 aws cognito-idp describe-user-pool-client \
        --user-pool-id "$user_pool_id" \
        --client-id "$client_id" \
        --region "$region" \
        --query "UserPoolClient.ClientSecret" \
        --output text
}

# Write configuration file
write_config() {
    local api_endpoint="$1"
    local token_endpoint="$2"
    local client_id="$3"
    local client_secret="$4"
    local user_pool_id="$5"
    local resource_server_id="$6"
    local lambda_function_name="$7"
    local log_group_name="$8"
    local region="$9"
    local api_log_group_name="${10}"
    
    log_info "Writing deployment configuration to .config..."
    
    cat > .config << EOF
# Quilt MCP Server Deployment Configuration
# Generated on $(date)

# API Endpoints
API_ENDPOINT=${api_endpoint}
TOKEN_ENDPOINT=${token_endpoint}

# Authentication
CLIENT_ID=${client_id}
CLIENT_SECRET=${client_secret}
USER_POOL_ID=${user_pool_id}
RESOURCE_SERVER_ID=${resource_server_id}

# AWS Resources
LAMBDA_FUNCTION_NAME=${lambda_function_name}
LOG_GROUP_NAME=${log_group_name}
API_LOG_GROUP_NAME=${api_log_group_name}
STACK_NAME=${STACK_NAME}
REGION=${region}

# OAuth Scopes
OAUTH_SCOPES="${resource_server_id}/read ${resource_server_id}/write"

# MCP Inspector Configuration
MCP_SERVER_URL=\${API_ENDPOINT}
MCP_SERVER_NAME="Quilt MCP Server"
EOF

    log_success "✅ Configuration saved to .config"
}

# Load configuration
load_config() {
    if [ ! -f ".config" ]; then
        log_error "❌ .config file not found. Run ./deploy.sh first"
        exit 1
    fi
    
    log_info "Loading configuration from .config"
    set -a && source .config && set +a
}

# Display quick commands
show_quick_commands() {
    local api_endpoint="$1"
    
    echo ""
    log_info "🔧 Quick Commands:"
    log_info "View Lambda logs: scripts/check_logs.sh"
    log_info "Get access token: scripts/get_token.sh"
    log_info "Test API:"
    echo -e "${BLUE}  curl -H 'Authorization: Bearer \$(scripts/get_token.sh)' -X POST ${api_endpoint} -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}'${NC}"
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