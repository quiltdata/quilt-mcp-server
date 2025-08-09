#!/bin/bash
set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Package Lambda function using Docker
package_lambda() {
    local output_dir="$1"
    
    log_info "Packaging Lambda function..."
    
    # Check Docker availability
    check_docker
    
    # Create temporary directory if not provided
    if [ -z "$output_dir" ]; then
        output_dir=$(mktemp -d)
        echo "$output_dir"  # Return the directory path
    fi
    
    log_info "Building Docker image for Lambda..."
    docker build --platform linux/amd64 -t quilt-mcp-builder . >/dev/null 2>&1
    
    log_info "Extracting Lambda package to: $output_dir"
    docker run --rm --platform linux/amd64 \
        -v "$output_dir":/output \
        --entrypoint="" \
        quilt-mcp-builder \
        bash -c "
            cp -r /usr/local/lib/python3.11/site-packages/* /output/
            cp /app/quilt/*.py /output/ 2>/dev/null || true
            chmod -R 755 /output/
        " >/dev/null 2>&1
    
    log_success "✅ Lambda package built successfully"
    
    # Return output directory if we created it
    if [ -n "$1" ]; then
        return 0
    else
        echo "$output_dir"
    fi
}

# Main execution when called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Parse command line arguments
    OUTPUT_DIR=""
    VERBOSE=false
    
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
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Package Lambda function for deployment"
                echo ""
                echo "Options:"
                echo "  -o, --output DIR   Output directory (default: temporary directory)"
                echo "  -v, --verbose      Enable verbose output"
                echo "  -h, --help         Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                     # Package to temporary directory"
                echo "  $0 -o ./lambda-pkg     # Package to specific directory"
                echo "  $0 -v                  # Package with verbose output"
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
        TEMP_DIR=$(package_lambda)
        log_success "Lambda function packaged to: $TEMP_DIR"
        log_warning "⚠️  Temporary directory will be cleaned up after use"
    fi
fi