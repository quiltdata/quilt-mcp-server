#!/bin/bash
set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source common utilities
source "$SCRIPT_DIR/scripts/common.sh"
source "$SCRIPT_DIR/packager/package-lambda.sh"

# Main deployment function
main() {
    local skip_tests=false
    local verbose=false
    local lambda_package_dir=""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-tests)
                skip_tests=true
                shift
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            -p|--package-dir)
                lambda_package_dir="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                log_info "Use -h or --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Show deployment header
    log_info "🚀 Deploying Quilt MCP Server to AWS Lambda"
    echo ""
    
    # Load and validate environment
    load_environment
    validate_environment
    setup_aws_defaults
    
    log_success "Deploying to account ${CDK_DEFAULT_ACCOUNT} in ${CDK_DEFAULT_REGION}"
    echo ""
    
    # Install dependencies
    log_info "Installing dependencies..."
    uv sync --group deploy
    log_success "✅ Dependencies installed"
    
    # Package Lambda function if not provided
    if [ -z "$lambda_package_dir" ]; then
        log_info "Packaging Lambda function..."
        check_docker
        lambda_package_dir=$(package_lambda "" "true")
        cleanup_required=true
        log_success "✅ Lambda package built successfully"
    else
        cleanup_required=false
        log_info "Using provided Lambda package: $lambda_package_dir"
    fi
    
    # Set environment variable for CDK
    export LAMBDA_PACKAGE_DIR="$lambda_package_dir"
    
    # Bootstrap and deploy CDK
    if ! check_cdk_bootstrap "$CDK_DEFAULT_REGION"; then
        bootstrap_cdk "$CDK_DEFAULT_ACCOUNT" "$CDK_DEFAULT_REGION"
    else
        log_success "✅ CDK already bootstrapped"
    fi
    
    log_info "Deploying to AWS..."
    uv run cdk deploy --require-approval never --app "python app.py"
    log_success "✅ CDK deployment completed"
    
    # Cleanup temporary Lambda package if we created it
    if [ "$cleanup_required" = true ]; then
        cleanup_temp_dir "$lambda_package_dir"
    fi
    
    # Extract deployment configuration and show summary
    log_info "Configuring deployment..."
    "$SCRIPT_DIR/scripts/post-deploy.sh" --skip-api-test
    
    # Run endpoint tests unless skipped
    if [ "$skip_tests" = false ]; then
        echo ""
        log_info "🧪 Running endpoint tests..."
        if [ -f "$SCRIPT_DIR/tests/test-endpoint.sh" ]; then
            # Load config to get API endpoint
            load_config
            "$SCRIPT_DIR/tests/test-endpoint.sh" -e "$API_ENDPOINT"
        else
            log_warning "⚠️  Test script not found, skipping endpoint tests"
        fi
    fi
    
    echo ""
    log_success "🎉 Deployment completed successfully!"
}

# Show help information
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Quilt MCP Server to AWS Lambda with Cognito authentication

Options:
  --skip-tests           Skip endpoint testing after deployment
  -v, --verbose          Enable verbose output
  -p, --package-dir DIR  Use existing Lambda package directory
  -h, --help             Show this help message

Examples:
  $0                     # Full deployment with tests
  $0 --skip-tests        # Deploy without running tests
  $0 -p ./lambda-pkg     # Use existing Lambda package

Sub-commands (run these individually):
  scripts/package-lambda.sh    # Package Lambda function only
  scripts/cdk-deploy.sh        # CDK operations (deploy/destroy/diff)
  scripts/post-deploy.sh       # Post-deployment configuration
  scripts/check_logs.sh        # View deployment logs
  scripts/get_token.sh         # Get OAuth access token

Environment:
  - Copy env.example to .env and configure required variables
  - QUILT_READ_POLICY_ARN is required
  - CDK_DEFAULT_ACCOUNT and CDK_DEFAULT_REGION will be auto-detected

Files created:
  - .config                    # Deployment configuration
  - CloudFormation stack       # AWS resources
  - Docker image               # Lambda build environment
EOF
}

# Trap for cleanup on exit
cleanup() {
    local exit_code=$?
    if [ -n "$lambda_package_dir" ] && [ "$cleanup_required" = true ]; then
        cleanup_temp_dir "$lambda_package_dir"
    fi
    exit $exit_code
}

trap cleanup EXIT

# Run main function
main "$@"