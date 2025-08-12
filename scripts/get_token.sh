#!/bin/bash
set -e

# Load common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default values
VERBOSE=false
OUTPUT_FORMAT="token"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -f|--format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Get OAuth 2.0 access token for MCP server authentication"
            echo ""
            echo "Options:"
            echo "  -v, --verbose      Show verbose output"
            echo "  -f, --format TYPE  Output format: token|json|full (default: token)"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Output formats:"
            echo "  token    - Just the access token (for use in scripts)"
            echo "  json     - Full JSON response from token endpoint"
            echo "  full     - Formatted output with token details"
            echo ""
            echo "Examples:"
            echo "  $0                           # Get token"
            echo "  $0 -f full                   # Get formatted token info"
            echo "  export TOKEN=\$($0)          # Use in scripts"
            echo "  curl -H \"Authorization: Bearer \$($0)\" ..."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Load environment variables
if [ -f ".env" ]; then
    if [ "$VERBOSE" = true ]; then
        log_info "Loading environment from .env" >&2
    fi
    set -a && source .env && set +a
fi

# Load configuration
load_config

# Validate required variables
if [ -z "$TOKEN_ENDPOINT" ] || [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ] || [ -z "$OAUTH_SCOPES" ]; then
    log_error "❌ Required authentication configuration missing" >&2
    log_warning "💡 Run ./deploy.sh to regenerate .config with authentication details" >&2
    exit 1
fi

if [ "$VERBOSE" = true ]; then
    log_info "🔐 Getting OAuth 2.0 access token..." >&2
    log_info "Token Endpoint: ${TOKEN_ENDPOINT}" >&2
    log_info "Client ID: ${CLIENT_ID}" >&2
    log_info "Scopes: ${OAUTH_SCOPES}" >&2
fi

# Prepare scopes parameter (replace spaces with + for URL encoding)
SCOPES_PARAM=$(echo "$OAUTH_SCOPES" | tr ' ' '+')

# Get access token using client credentials flow
TOKEN_RESPONSE=$(curl -s -X POST "$TOKEN_ENDPOINT" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -u "$CLIENT_ID:$CLIENT_SECRET" \
    -d "grant_type=client_credentials&scope=$SCOPES_PARAM")

# Check if request was successful
if ! echo "$TOKEN_RESPONSE" | grep -q "access_token"; then
    log_error "❌ Failed to get access token" >&2
    log_warning "Error response: $TOKEN_RESPONSE" >&2
    exit 1
fi

# Output based on format
case "$OUTPUT_FORMAT" in
    "token")
        echo "$TOKEN_RESPONSE" | jq -r '.access_token'
        ;;
    "json")
        echo "$TOKEN_RESPONSE"
        ;;
    "full")
        ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')
        EXPIRES_IN=$(echo "$TOKEN_RESPONSE" | jq -r '.expires_in')
        TOKEN_TYPE=$(echo "$TOKEN_RESPONSE" | jq -r '.token_type')
        
        log_success "✅ Access token retrieved successfully"
        log_info "Token Type: ${TOKEN_TYPE}"
        log_info "Expires In: ${EXPIRES_IN} seconds ($(($EXPIRES_IN / 60)) minutes)"
        log_info "Token: ${ACCESS_TOKEN:0:50}..."
        echo ""
        log_warning "💡 Use this token in Authorization header:"
        log_info "Authorization: Bearer $ACCESS_TOKEN"
        ;;
    *)
        log_error "❌ Unknown output format: $OUTPUT_FORMAT" >&2
        exit 1
        ;;
esac

if [ "$VERBOSE" = true ] && [ "$OUTPUT_FORMAT" = "token" ]; then
    log_success "✅ Token retrieved successfully" >&2
fi