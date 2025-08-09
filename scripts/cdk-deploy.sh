#!/bin/bash
set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."
    uv sync --group deploy
    log_success "✅ Dependencies installed"
}

# Deploy CDK stack
deploy_cdk_stack() {
    local lambda_package_dir="$1"
    local account="$2"
    local region="$3"
    
    # Set Lambda package directory environment variable
    export LAMBDA_PACKAGE_DIR="$lambda_package_dir"
    
    # Bootstrap CDK if needed
    if ! check_cdk_bootstrap "$region"; then
        bootstrap_cdk "$account" "$region"
    else
        log_success "✅ CDK already bootstrapped"
    fi
    
    # Deploy the stack
    log_info "Deploying CDK stack to AWS..."
    uv run cdk deploy --require-approval never --app "python app.py"
    log_success "✅ CDK deployment completed"
}

# Destroy CDK stack
destroy_cdk_stack() {
    local region=${1:-$CDK_DEFAULT_REGION}
    
    log_warning "⚠️  Destroying CDK stack..."
    read -p "Are you sure you want to destroy the stack? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        uv run cdk destroy --force --app "python app.py"
        log_success "✅ CDK stack destroyed"
        
        # Remove config file
        if [ -f ".config" ]; then
            rm .config
            log_info "Removed .config file"
        fi
    else
        log_info "Stack destruction cancelled"
    fi
}

# Show CDK diff
show_cdk_diff() {
    local lambda_package_dir="$1"
    
    if [ -n "$lambda_package_dir" ]; then
        export LAMBDA_PACKAGE_DIR="$lambda_package_dir"
    fi
    
    log_info "Showing CDK diff..."
    uv run cdk diff --app "python app.py"
}

# Main execution when called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Parse command line arguments
    ACTION="deploy"
    LAMBDA_PACKAGE_DIR=""
    SKIP_DEPS=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            deploy|destroy|diff)
                ACTION="$1"
                shift
                ;;
            -p|--package-dir)
                LAMBDA_PACKAGE_DIR="$2"
                shift 2
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [ACTION] [OPTIONS]"
                echo ""
                echo "Deploy, destroy, or diff CDK stack"
                echo ""
                echo "Actions:"
                echo "  deploy     Deploy the CDK stack (default)"
                echo "  destroy    Destroy the CDK stack"
                echo "  diff       Show differences between current and deployed"
                echo ""
                echo "Options:"
                echo "  -p, --package-dir DIR  Lambda package directory"
                echo "  --skip-deps           Skip dependency installation"
                echo "  -h, --help            Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                           # Deploy stack"
                echo "  $0 deploy -p ./lambda-pkg    # Deploy with specific package"
                echo "  $0 destroy                   # Destroy stack"
                echo "  $0 diff                      # Show diff"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                log_info "Use -h or --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Load environment
    load_environment
    validate_environment
    setup_aws_defaults
    
    # Install dependencies unless skipped
    if [ "$SKIP_DEPS" = false ]; then
        install_dependencies
    fi
    
    # Execute action
    case "$ACTION" in
        deploy)
            if [ -z "$LAMBDA_PACKAGE_DIR" ]; then
                log_error "❌ Lambda package directory required for deployment"
                log_info "Use -p flag to specify package directory or run ./deploy.sh"
                exit 1
            fi
            deploy_cdk_stack "$LAMBDA_PACKAGE_DIR" "$CDK_DEFAULT_ACCOUNT" "$CDK_DEFAULT_REGION"
            ;;
        destroy)
            destroy_cdk_stack "$CDK_DEFAULT_REGION"
            ;;
        diff)
            show_cdk_diff "$LAMBDA_PACKAGE_DIR"
            ;;
    esac
fi