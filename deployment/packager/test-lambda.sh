#!/bin/bash
set -e

# Script to test Lambda function with predefined or custom events
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$PROJECT_ROOT/scripts/common.sh"

# Default values
TEST_TYPE="tools-list"
CUSTOM_EVENT=""
VERBOSE=false
KEEP_EVENT=false

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Test Lambda function locally with predefined or custom events

Options:
  -t, --test TYPE        Test type: tools-list, resources-list, health-check, custom
                         (default: tools-list)
  -e, --event FILE       Use custom event file (overrides --test)
  -c, --custom-body STR  Custom request body for custom test type
  -v, --verbose          Enable verbose output
  -k, --keep-event       Keep generated event file after test
  -h, --help             Show this help message

Examples:
  $0                                       # Test tools/list endpoint
  $0 -t resources-list                     # Test resources/list endpoint  
  $0 -t health-check                       # Test health check endpoint
  $0 -t custom -c '{"test": "data"}'       # Test with custom body
  $0 -e my-event.json                      # Test with custom event file
  $0 -v -k                                 # Verbose mode, keep event file

Available test types:
  - tools-list:     Tests MCP tools/list method
  - resources-list: Tests MCP resources/list method
  - health-check:   Tests health check endpoint (GET)
  - custom:         Custom test with --custom-body
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--test)
            TEST_TYPE="$2"
            shift 2
            ;;
        -e|--event)
            CUSTOM_EVENT="$2"
            shift 2
            ;;
        -c|--custom-body)
            CUSTOM_BODY="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -k|--keep-event)
            KEEP_EVENT=true
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

# Validate test type
case "$TEST_TYPE" in
    tools-list|resources-list|health-check|custom)
        ;;
    *)
        log_error "❌ Invalid test type: $TEST_TYPE"
        log_info "Valid types: tools-list, resources-list, health-check, custom"
        exit 1
        ;;
esac

# Handle custom event file
if [ -n "$CUSTOM_EVENT" ]; then
    if [ ! -f "$CUSTOM_EVENT" ]; then
        log_error "❌ Custom event file not found: $CUSTOM_EVENT"
        exit 1
    fi
    EVENT_FILE="$CUSTOM_EVENT"
    KEEP_EVENT=true  # Don't delete user-provided files
    
    if [ "$VERBOSE" = true ]; then
        log_info "Using custom event file: $EVENT_FILE"
    fi
else
    # Use Makefile-generated event file
    EVENT_FILE="$PROJECT_ROOT/tests/events/${TEST_TYPE}.json"
    
    if [ "$VERBOSE" = true ]; then
        log_info "Using Makefile-generated test event for: $TEST_TYPE"
        log_info "Event file: $EVENT_FILE"
    fi
    
    # Generate event using Makefile if it doesn't exist
    if [ ! -f "$EVENT_FILE" ]; then
        if [ "$VERBOSE" = true ]; then
            log_info "Generating event file using Makefile..."
        fi
        (cd "$PROJECT_ROOT" && make "tests/events/${TEST_TYPE}.json")
        
        if [ ! -f "$EVENT_FILE" ]; then
            log_error "Failed to generate event file: $EVENT_FILE"
            exit 1
        fi
    fi
    
    if [ $? -ne 0 ]; then
        log_error "❌ Failed to generate event file"
        exit 1
    fi
    
    if [ "$VERBOSE" = true ]; then
        log_success "✅ Event generated successfully"
    fi
fi

# Run the Lambda function
log_info "🧪 Testing Lambda function with $TEST_TYPE event..."

if [ "$VERBOSE" = true ]; then
    "$SCRIPT_DIR/run-lambda.sh" -e "$EVENT_FILE" -v
else
    "$SCRIPT_DIR/run-lambda.sh" -e "$EVENT_FILE"
fi

LAMBDA_EXIT_CODE=$?

# Cleanup event file if not keeping it
if [ "$KEEP_EVENT" = false ] && [ -n "$EVENT_FILE" ] && [ "$EVENT_FILE" != "$CUSTOM_EVENT" ]; then
    rm -f "$EVENT_FILE"
    if [ "$VERBOSE" = true ]; then
        log_info "Cleaned up generated event file"
    fi
fi

# Report results
if [ $LAMBDA_EXIT_CODE -eq 0 ]; then
    log_success "🎉 Lambda test completed successfully!"
else
    log_error "❌ Lambda test failed"
    exit 1
fi