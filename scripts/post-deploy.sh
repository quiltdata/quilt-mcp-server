#!/bin/bash
set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Extract deployment configuration
extract_deployment_config() {
    local region=${1:-$CDK_DEFAULT_REGION}
    
    check_jq
    
    # Get stack outputs with no color contamination
    local stack_outputs
    if [ -z "${NO_COLOR:-}" ]; then
        log_info "Retrieving deployment outputs from CloudFormation..."
    fi
    stack_outputs=$(NO_COLOR=1 aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$region" \
        --query "Stacks[0].Outputs" \
        --output json)
    
    if [ -z "$stack_outputs" ] || [ "$stack_outputs" = "null" ]; then
        log_error "❌ Failed to retrieve stack outputs"
        exit 1
    fi
    
    # Extract individual values
    local api_endpoint token_endpoint client_id user_pool_id resource_server_id
    local log_group_name lambda_function_name
    
    api_endpoint=$(extract_output_value "$stack_outputs" "ApiEndpoint")
    token_endpoint=$(extract_output_value "$stack_outputs" "TokenEndpoint") 
    client_id=$(extract_output_value "$stack_outputs" "ClientId")
    user_pool_id=$(extract_output_value "$stack_outputs" "UserPoolId")
    resource_server_id=$(extract_output_value "$stack_outputs" "ResourceServerIdentifier")
    log_group_name=$(extract_output_value "$stack_outputs" "LogGroupName")
    lambda_function_name=$(extract_output_value "$stack_outputs" "LambdaFunctionName")
    
    # Get client secret
    local client_secret
    if [ -z "${NO_COLOR:-}" ]; then
        log_info "Retrieving Cognito client secret..."
    fi
    client_secret=$(NO_COLOR=1 aws cognito-idp describe-user-pool-client \
        --user-pool-id "$user_pool_id" \
        --client-id "$client_id" \
        --region "$region" \
        --query "UserPoolClient.ClientSecret" \
        --output text)
    
    # Write configuration
    write_config "$api_endpoint" "$token_endpoint" "$client_id" "$client_secret" \
                 "$user_pool_id" "$resource_server_id" "$lambda_function_name" \
                 "$log_group_name" "$region"
    
    # Return configuration values for use by caller
    echo "API_ENDPOINT=$api_endpoint"
    echo "TOKEN_ENDPOINT=$token_endpoint"
    echo "CLIENT_ID=$client_id"
    echo "CLIENT_SECRET=$client_secret"
    echo "USER_POOL_ID=$user_pool_id"
    echo "RESOURCE_SERVER_ID=$resource_server_id"
    echo "LAMBDA_FUNCTION_NAME=$lambda_function_name"
    echo "LOG_GROUP_NAME=$log_group_name"
    echo "REGION=$region"
}

# Display deployment summary
show_deployment_summary() {
    local api_endpoint="$1"
    
    echo ""
    log_success "🎉 Deployment completed!"
    log_success "Claude MCP Server URL: ${api_endpoint}"
    log_success "Configuration saved to .config"
    
    show_quick_commands "$api_endpoint"
}

# Validate deployment
validate_deployment() {
    local api_endpoint="$1"
    
    log_info "🔍 Validating deployment..."
    
    # Test basic connectivity (should return 401 for unauthenticated requests)
    local http_status
    http_status=$(curl -s -o /dev/null -w '%{http_code}' "$api_endpoint" || echo "000")
    
    if [ "$http_status" = "401" ]; then
        log_success "✅ API endpoint is protected (HTTP 401 as expected)"
        return 0
    elif [ "$http_status" = "200" ] || [ "$http_status" = "405" ]; then
        log_warning "⚠️  API endpoint responding but may not be properly protected (HTTP $http_status)"
        return 0
    else
        log_error "❌ API endpoint validation failed (HTTP $http_status)"
        return 1
    fi
}

# Test authentication flow
test_authentication() {
    log_info "🔐 Testing authentication flow..."
    
    # Load config to get auth details
    load_config
    
    # Try to get access token
    local token_script="$SCRIPT_DIR/get_token.sh"
    if [ ! -f "$token_script" ]; then
        log_warning "⚠️  Token script not found, skipping auth test"
        return 1
    fi
    
    if ACCESS_TOKEN=$("$token_script" 2>/dev/null); then
        if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
            log_success "✅ OAuth 2.0 authentication successful"
            return 0
        fi
    fi
    
    log_error "❌ OAuth 2.0 authentication failed"
    return 1
}

# Run basic API test
test_api_functionality() {
    log_info "🧪 Testing API functionality..."
    
    load_config
    
    # Get access token
    local token_script="$SCRIPT_DIR/get_token.sh"
    if [ ! -f "$token_script" ]; then
        log_warning "⚠️  Cannot test API - token script not found"
        return 1
    fi
    
    local access_token
    if ! access_token=$("$token_script" 2>/dev/null); then
        log_error "❌ Cannot get access token for API test"
        return 1
    fi
    
    # Test tools/list endpoint
    local api_response
    api_response=$(curl -s -H "Authorization: Bearer $access_token" \
                        -X POST "$API_ENDPOINT" \
                        -H "Content-Type: application/json" \
                        -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}')
    
    if echo "$api_response" | grep -q '"tools"' 2>/dev/null; then
        log_success "✅ API functionality test passed"
        return 0
    else
        log_warning "⚠️  API functionality test inconclusive"
        log_info "Response: $api_response"
        return 1
    fi
}

# Main execution when called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Parse command line arguments
    SKIP_VALIDATION=false
    SKIP_AUTH_TEST=false
    SKIP_API_TEST=false
    REGION=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-validation)
                SKIP_VALIDATION=true
                shift
                ;;
            --skip-auth-test)
                SKIP_AUTH_TEST=true
                shift
                ;;
            --skip-api-test)
                SKIP_API_TEST=true
                shift
                ;;
            -r|--region)
                REGION="$2"
                shift 2
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Extract deployment configuration and validate deployment"
                echo ""
                echo "Options:"
                echo "  --skip-validation    Skip deployment validation"
                echo "  --skip-auth-test     Skip authentication test"
                echo "  --skip-api-test      Skip API functionality test"
                echo "  -r, --region REGION  AWS region (default: from environment)"
                echo "  -h, --help           Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                        # Full post-deployment setup"
                echo "  $0 --skip-validation      # Skip validation tests"
                echo "  $0 -r us-west-2           # Use specific region"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                log_info "Use -h or --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Load environment if available
    if [ -f ".env" ]; then
        load_environment
        setup_aws_defaults
    fi
    
    # Use provided region or default
    REGION=${REGION:-$CDK_DEFAULT_REGION}
    
    # Extract configuration with colors disabled and capture only the variable assignments
    CONFIG_VARS=$(NO_COLOR=1 extract_deployment_config "$REGION" 2>/dev/null | grep "^[A-Z_]*=")
    
    # Parse configuration variables
    eval "$CONFIG_VARS"
    
    # Show deployment summary
    show_deployment_summary "$API_ENDPOINT"
    
    # Run validation tests
    if [ "$SKIP_VALIDATION" = false ]; then
        validate_deployment "$API_ENDPOINT"
    fi
    
    if [ "$SKIP_AUTH_TEST" = false ]; then
        test_authentication
    fi
    
    if [ "$SKIP_API_TEST" = false ]; then
        test_api_functionality
    fi
    
    echo ""
    log_success "🎯 Post-deployment setup complete!"
fi