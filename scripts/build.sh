#!/bin/bash
set -e

# Integrated build system for Quilt MCP Server
# This script provides a unified interface for building, testing, and deploying

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default values
MODE="build"
VERBOSE=false
SKIP_TESTS=false
OUTPUT_DIR=""
TEST_TYPE="tools-list"

show_help() {
    cat << EOF
Usage: $0 [MODE] [OPTIONS]

Unified build, test, and deployment system for Quilt MCP Server

MODES:
  build                  Build Lambda package with Docker and test locally
  deploy                 Build, test, and deploy to AWS
  test                   Test existing deployment
  clean                  Clean build artifacts

OPTIONS:
  -o, --output DIR       Output directory for build artifacts
  -v, --verbose          Enable verbose output
  --skip-tests           Skip testing phases
  -t, --test-type TYPE   Test type (tools-list, resources-list, health-check)
  -h, --help             Show this help message

EXAMPLES:
  $0 build               # Build and test locally
  $0 build -v            # Build with verbose output
  $0 deploy              # Full build, test, and deploy pipeline
  $0 deploy --skip-tests # Deploy without running tests (NOT recommended)
  $0 test                # Test existing deployment
  $0 clean               # Clean all build artifacts

WORKFLOW:
  build:  Docker package → Local test → Success report
  deploy: Docker package → Local test → CDK deploy → Endpoint test → Success report
  test:   Endpoint test with JWT auth → Log analysis on failures
  clean:  Remove Docker images, build artifacts, CDK outputs

The build system ensures consistency between local testing and deployment:
- Same Docker packaging process for local and remote
- Comprehensive testing at each stage  
- Automatic failure diagnosis and reporting
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        build|deploy|test|clean)
            MODE="$1"
            shift
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        -t|--test-type)
            TEST_TYPE="$2"
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

# Verbose flag for sub-scripts
VERBOSE_FLAG=""
if [ "$VERBOSE" = true ]; then
    VERBOSE_FLAG="-v"
fi

# Load environment
load_environment
validate_environment
setup_aws_defaults

# Mode implementations
build_mode() {
    log_info "🔨 Building Quilt MCP Lambda package"
    
    # Create build directory if specified
    if [ -n "$OUTPUT_DIR" ]; then
        mkdir -p "$OUTPUT_DIR"
        BUILD_DIR="$(cd "$OUTPUT_DIR" && pwd)"
        log_info "Using build directory: $BUILD_DIR"
    else
        BUILD_DIR=""
    fi
    
    # Build with Docker packaging
    if [ -n "$BUILD_DIR" ]; then
        "$PROJECT_ROOT/packager/package-lambda.sh" -o "$BUILD_DIR" $VERBOSE_FLAG
    else
        # Use quiet mode to capture just the directory path
        BUILD_DIR=$("$PROJECT_ROOT/packager/package-lambda.sh" 2>/dev/null | tail -1)
        if [ "$VERBOSE" = true ]; then
            log_info "Lambda package built to: $BUILD_DIR"
        fi
    fi
    
    if [ $? -ne 0 ]; then
        log_error "❌ Build failed during packaging"
        exit 1
    fi
    
    # Test locally if not skipping tests
    if [ "$SKIP_TESTS" = false ]; then
        log_info "🧪 Testing Lambda package locally"
        if ! "$PROJECT_ROOT/packager/test-lambda.sh" -t "$TEST_TYPE" $VERBOSE_FLAG; then
            log_error "❌ Local testing failed"
            exit 1
        fi
    fi
    
    log_success "✅ Build completed successfully"
    log_info "Build artifacts: $BUILD_DIR"
    
    # Export build directory for deploy mode
    export LAMBDA_PACKAGE_DIR="$BUILD_DIR"
    
    # Save the package directory to a temporary file for deploy mode
    echo "$BUILD_DIR" > /tmp/lambda_package_dir.txt
}

deploy_mode() {
    log_info "🚀 Deploying Quilt MCP Server"
    
    # Build first (this sets LAMBDA_PACKAGE_DIR)  
    BUILD_OUTPUT=$(build_mode 2>&1)
    BUILD_EXIT_CODE=$?
    
    if [ $BUILD_EXIT_CODE -ne 0 ]; then
        log_error "❌ Build failed, aborting deployment"
        exit 1
    fi
    
    # Get LAMBDA_PACKAGE_DIR from temporary file
    if [ -f "/tmp/lambda_package_dir.txt" ]; then
        export LAMBDA_PACKAGE_DIR=$(cat /tmp/lambda_package_dir.txt)
        rm -f /tmp/lambda_package_dir.txt
    else
        log_error "❌ Failed to get build directory from build phase"
        exit 1
    fi
    
    if [ -z "$LAMBDA_PACKAGE_DIR" ] || [ ! -d "$LAMBDA_PACKAGE_DIR" ]; then
        log_error "❌ Invalid build directory: $LAMBDA_PACKAGE_DIR"
        exit 1
    fi
    
    log_info "Deploying with package: $LAMBDA_PACKAGE_DIR"
    
    # Install CDK dependencies
    log_info "Installing CDK dependencies..."
    uv sync --group deploy
    
    # CDK Bootstrap check
    if ! check_cdk_bootstrap "$CDK_DEFAULT_REGION"; then
        bootstrap_cdk "$CDK_DEFAULT_ACCOUNT" "$CDK_DEFAULT_REGION"
    else
        log_success "✅ CDK already bootstrapped"
    fi
    
    # Deploy with CDK
    log_info "Deploying to AWS..."
    if ! uv run cdk deploy --require-approval never --app "python app.py"; then
        log_error "❌ CDK deployment failed"
        exit 1
    fi
    
    log_success "✅ CDK deployment completed"
    
    # Post-deployment configuration
    log_info "Configuring deployment..."
    if ! "$SCRIPT_DIR/post-deploy.sh" --skip-api-test; then
        log_error "❌ Post-deployment configuration failed"
        exit 1
    fi
    
    # Test deployed endpoint if not skipping tests
    if [ "$SKIP_TESTS" = false ]; then
        log_info "🧪 Testing deployed endpoint"
        if ! test_deployment; then
            log_error "❌ Deployment testing failed"
            show_failure_analysis
            exit 1
        fi
    fi
    
    log_success "🎉 Deployment completed successfully!"
    show_deployment_summary
}

test_mode() {
    log_info "🧪 Testing deployed Quilt MCP Server"
    
    if ! test_deployment; then
        log_error "❌ Deployment testing failed"
        show_failure_analysis
        exit 1
    fi
    
    log_success "✅ All tests passed!"
}

clean_mode() {
    log_info "🧹 Cleaning build artifacts"
    
    # Clean Docker images
    if docker images -q quilt-mcp-builder >/dev/null 2>&1; then
        docker rmi quilt-mcp-builder 2>/dev/null || true
        log_info "Cleaned Docker images"
    fi
    
    # Clean CDK output
    rm -rf cdk.out
    log_info "Cleaned CDK output"
    
    # Clean temporary directories
    find /tmp -name "tmp.*" -path "*/quilt-mcp-*" -type d -exec rm -rf {} + 2>/dev/null || true
    
    log_success "✅ Cleanup completed"
}

# Test deployed endpoint with proper JWT authentication  
test_deployment() {
    # Check if we have config
    if [ ! -f ".config" ]; then
        log_error "❌ No deployment configuration found. Run deployment first."
        return 1
    fi
    
    source .config
    
    # Test with JWT authentication
    log_info "Testing authenticated endpoint access..."
    
    # Get access token
    local access_token
    if ! access_token=$("$SCRIPT_DIR/get_token.sh" 2>/dev/null); then
        log_error "❌ Failed to get access token"
        return 1
    fi
    
    # Test tools/list endpoint
    local api_response
    api_response=$(curl -s -H "Authorization: Bearer $access_token" \
                       -X POST "$API_ENDPOINT" \
                       -H "Content-Type: application/json" \
                       -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
                       2>/dev/null)
    
    # Check if response contains expected tools
    if echo "$api_response" | grep -q '"tools"' 2>/dev/null; then
        log_success "✅ API endpoint functioning correctly"
        
        # Count tools for verification
        local tool_count
        tool_count=$(echo "$api_response" | jq -r '.result.tools | length' 2>/dev/null || echo "0")
        log_info "Found $tool_count Quilt MCP tools"
        
        # Run comprehensive tool tests
        log_info "🔧 Running comprehensive tool tests..."
        if ! "$PROJECT_ROOT/scripts/test-endpoint.sh" -t; then
            log_error "❌ Tool tests failed"
            return 1
        fi
        
        return 0
    else
        log_error "❌ API endpoint not responding correctly"
        log_info "Response: $api_response"
        return 1
    fi
}

# Show failure analysis with logs and diagnostics
show_failure_analysis() {
    log_error "=== FAILURE ANALYSIS ==="
    
    if [ -f ".config" ]; then
        source .config
        
        log_info "🔍 Checking Lambda logs for errors..."
        "$SCRIPT_DIR/check_logs.sh" -s 10m
        
        log_info "📊 Function configuration:"
        echo "  Function: $LAMBDA_FUNCTION_NAME"
        echo "  Region: $REGION"
        echo "  API: $API_ENDPOINT"
    else
        log_warning "⚠️  No deployment config found for detailed analysis"
    fi
    
    log_info "💡 Common issues:"
    log_info "  - Lambda import errors: Check package dependencies"
    log_info "  - Authentication failures: Verify Cognito configuration"
    log_info "  - Timeout errors: Check Lambda execution time"
}

# Show deployment summary
show_deployment_summary() {
    if [ -f ".config" ]; then
        source .config
        
        log_success "=== DEPLOYMENT SUMMARY ==="
        log_success "🌐 API Endpoint: $API_ENDPOINT"
        log_success "🔐 Token Endpoint: $TOKEN_ENDPOINT"
        log_success "📋 Function: $LAMBDA_FUNCTION_NAME"
        
        echo ""
        log_info "🔧 Quick Commands:"
        log_info "  Test API: $0 test"
        log_info "  View logs: scripts/check_logs.sh"
        log_info "  Get token: scripts/get_token.sh"
        
        echo ""
        log_info "🧪 Manual test:"
        echo "  curl -H 'Authorization: Bearer \$(scripts/get_token.sh)' -X POST $API_ENDPOINT -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}'"
    fi
}

# Execute mode
case "$MODE" in
    build)
        build_mode
        ;;
    deploy)
        deploy_mode
        ;;
    test)
        test_mode
        ;;
    clean)
        clean_mode
        ;;
    *)
        log_error "Unknown mode: $MODE"
        show_help
        exit 1
        ;;
esac