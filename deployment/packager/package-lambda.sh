#!/bin/bash
set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$PROJECT_ROOT/scripts/common.sh"

# Check if SAM CLI is available
check_sam() {
    if ! command_exists sam; then
        log_error "❌ AWS SAM CLI not installed. Install it for local testing."
        log_info "Install with: brew install aws-sam-cli"
        return 1
    fi
    log_success "✅ AWS SAM CLI available"
}

# Package Lambda function using Docker
package_lambda() {
    local output_dir="$1"
    local quiet="${2:-false}"
    
    if [ "$quiet" != "true" ]; then
        log_info "Packaging Lambda function..."
    fi
    
    # Check Docker availability
    if [ "$quiet" != "true" ]; then
        check_docker
    else
        if ! command_exists docker || ! docker info >/dev/null 2>&1; then
            return 1
        fi
    fi
    
    # Create temporary directory if not provided
    local created_temp_dir=false
    if [ -z "$output_dir" ]; then
        output_dir=$(mktemp -d)
        created_temp_dir=true
    fi
    
    if [ "$quiet" != "true" ]; then
        log_info "Building Docker image for Lambda..."
    fi
    cd "$PROJECT_ROOT"
    docker build --platform linux/amd64 -t quilt-mcp-builder -f packager/Dockerfile . >/dev/null 2>&1
    
    if [ "$quiet" != "true" ]; then
        log_info "Extracting Lambda package to: $output_dir"
    fi
    
    # Ensure output directory exists and is absolute
    mkdir -p "$output_dir"
    output_dir=$(cd "$output_dir" && pwd)
    
    if ! docker run --rm --platform linux/amd64 \
        -v "$output_dir":/output \
        --entrypoint="" \
        quilt-mcp-builder \
        bash -c "
            mkdir -p /output
            cp -r /usr/local/lib/python3.11/site-packages/* /output/
            cp /app/quilt/*.py /output/ 2>/dev/null || true
            chmod -R 755 /output/
        " >/dev/null 2>&1; then
        log_error "❌ Failed to extract Lambda package from Docker"
        return 1
    fi
    
    if [ "$quiet" != "true" ]; then
        log_success "✅ Lambda package built successfully"
    fi
    
    # Return output directory if we created it, otherwise return success
    if [ "$created_temp_dir" = true ]; then
        echo "$output_dir"
    else
        if [ "$quiet" = "true" ]; then
            echo "$output_dir"
        fi
        return 0
    fi
}

# Note: SAM testing has been replaced with direct Docker testing
# using run-lambda.sh and test-lambda.sh for better reliability

# Main execution when called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Parse command line arguments
    OUTPUT_DIR=""
    VERBOSE=false
    TEST_LOCAL=false
    BUILD_ONLY=false
    TEST_TYPE="tools-list"
    TEST_EVENT=""
    KEEP_EVENT=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -o|--output)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -b|--build-only)
                BUILD_ONLY=true
                shift
                ;;
            -t|--test)
                TEST_LOCAL=true
                if [[ "$2" =~ ^(tools-list|resources-list|health-check|custom)$ ]]; then
                    TEST_TYPE="$2"
                    shift 2
                else
                    shift
                fi
                ;;
            -e|--event)
                TEST_EVENT="$2"
                shift 2
                ;;
            -k|--keep-event)
                KEEP_EVENT=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Package and optionally test Lambda function"
                echo ""
                echo "Options:"
                echo "  -o, --output DIR       Output directory (default: temporary directory)"
                echo "  -v, --verbose          Enable verbose output"
                echo "  -b, --build-only       Build Docker image and package only (no testing)"
                echo "  -t, --test [TYPE]      Build, package, and test locally"
                echo "                         TYPE: tools-list, resources-list, health-check, custom"
                echo "                         (default: tools-list)"
                echo "  -e, --event FILE       Custom test event file (overrides --test type)"
                echo "  -k, --keep-event       Keep generated test event file"
                echo "  -h, --help             Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                         # Package to temporary directory"
                echo "  $0 -o ./lambda-pkg         # Package to specific directory"
                echo "  $0 -b -v                   # Build and package only (verbose)"
                echo "  $0 -t                      # Build, package, and test with tools-list"
                echo "  $0 -t resources-list       # Build, package, and test with resources-list"
                echo "  $0 -t -e custom.json       # Build, package, and test with custom event"
                echo "  $0 -t -v -k                # Test with verbose output, keep event file"
                echo ""
                echo "Test types:"
                echo "  tools-list:     Tests MCP tools/list method (default)"
                echo "  resources-list: Tests MCP resources/list method"
                echo "  health-check:   Tests health check endpoint"
                echo "  custom:         Tests with custom event file (-e required)"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                log_info "Use -h or --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Package Lambda function
    if [ -n "$OUTPUT_DIR" ]; then
        mkdir -p "$OUTPUT_DIR"
        package_lambda "$OUTPUT_DIR"
        log_success "Lambda function packaged to: $OUTPUT_DIR"
    else
        TEMP_DIR=$(package_lambda "" "true")
        echo "$TEMP_DIR"
        if [ "$VERBOSE" = true ]; then
            log_success "Lambda function packaged to: $TEMP_DIR"
        fi
        if [ "$BUILD_ONLY" = false ] && [ "$TEST_LOCAL" = false ] && [ "$VERBOSE" = true ]; then
            log_warning "⚠️  Temporary directory will be cleaned up after use"
        fi
    fi
    
    # Exit early if build-only mode
    if [ "$BUILD_ONLY" = true ]; then
        log_info "🔨 Build completed (build-only mode)"
        exit 0
    fi
    
    # Run local test if requested
    if [ "$TEST_LOCAL" = true ]; then
        echo ""
        log_info "🧪 Running local Lambda tests..."
        
        # Prepare test-lambda.sh arguments
        TEST_ARGS=""
        if [ "$VERBOSE" = true ]; then
            TEST_ARGS="$TEST_ARGS -v"
        fi
        if [ "$KEEP_EVENT" = true ]; then
            TEST_ARGS="$TEST_ARGS -k"
        fi
        
        # Use custom event file if provided, otherwise use test type
        if [ -n "$TEST_EVENT" ]; then
            if [ ! -f "$TEST_EVENT" ]; then
                log_error "❌ Custom event file not found: $TEST_EVENT"
                exit 1
            fi
            TEST_ARGS="$TEST_ARGS -e $TEST_EVENT"
        else
            TEST_ARGS="$TEST_ARGS -t $TEST_TYPE"
        fi
        
        # Run the test
        if ! "$SCRIPT_DIR/test-lambda.sh" $TEST_ARGS; then
            log_error "❌ Lambda testing failed"
            exit 1
        fi
        
        log_success "🎉 Package and test completed successfully!"
    fi
fi