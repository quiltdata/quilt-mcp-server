#!/bin/bash
set -e

# Script to run Lambda function locally using Docker
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$PROJECT_ROOT/scripts/common.sh"

# Default values
EVENT_FILE=""
VERBOSE=false

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Run Lambda function locally using Docker

Options:
  -e, --event FILE       Lambda event JSON file
  -v, --verbose          Enable verbose output
  -h, --help             Show this help message

Examples:
  $0 -e test-event.json                    # Run with specific event
  $0 -e <(echo '{"test": "data"}')         # Run with inline event

The script will:
1. Use the existing Docker image (quilt-mcp-builder)
2. Mount the event file into the container
3. Execute the Lambda handler with the event
4. Return the response

Event file should be a valid Lambda event JSON structure.
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--event)
            EVENT_FILE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
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

# Validate required parameters
if [ -z "$EVENT_FILE" ]; then
    log_error "❌ Event file is required. Use -e to specify an event file."
    exit 1
fi

if [ ! -f "$EVENT_FILE" ]; then
    log_error "❌ Event file not found: $EVENT_FILE"
    exit 1
fi

# Check if Docker image exists
if ! docker image inspect quilt-mcp-builder >/dev/null 2>&1; then
    log_error "❌ Docker image 'quilt-mcp-builder' not found."
    log_info "Run './packager/package-lambda.sh' first to build the image."
    exit 1
fi

# Convert event file to absolute path
EVENT_FILE="$(cd "$(dirname "$EVENT_FILE")" && pwd)/$(basename "$EVENT_FILE")"

if [ "$VERBOSE" = true ]; then
    log_info "Running Lambda function locally..."
    log_info "Event file: $EVENT_FILE"
    log_info "Docker image: quilt-mcp-builder"
fi

# Run Lambda function in Docker container
log_info "🚀 Executing Lambda handler..."

docker run --rm --platform linux/amd64 \
    -v "$EVENT_FILE":/test-event.json \
    -e "LOG_LEVEL=INFO" \
    -e "LAMBDA_MODE=true" \
    quilt-mcp-builder \
    python -c "
import json
import sys
import os

# Set up path for imports
sys.path.insert(0, '/app/quilt')

# Import handler
try:
    from lambda_handler import handler
except ImportError as e:
    print(f'Error importing lambda_handler: {e}')
    sys.exit(1)

# Load event
try:
    with open('/test-event.json', 'r') as f:
        event = json.load(f)
except Exception as e:
    print(f'Error loading event: {e}')
    sys.exit(1)

# Create mock context
class MockLambdaContext:
    def __init__(self):
        self.aws_request_id = 'local-test-' + str(hash(str(event)))
        self.log_group_name = '/aws/lambda/local-test'
        self.log_stream_name = 'local-test-stream'
        self.function_name = 'local-test-function'
        self.memory_limit_in_mb = 256
        self.function_version = '\$LATEST'
        self.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:local-test'
        self.remaining_time_in_millis = lambda: 30000

context = MockLambdaContext()

# Execute handler
try:
    print('=== Lambda Event ===')
    print(json.dumps(event, indent=2))
    print()
    print('=== Lambda Response ===')
    
    result = handler(event, context)
    print(json.dumps(result, indent=2))
    
    print()
    print('=== Execution Complete ===')
    
except Exception as e:
    print(f'Lambda execution failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    log_success "✅ Lambda execution completed successfully"
else
    log_error "❌ Lambda execution failed"
    exit 1
fi