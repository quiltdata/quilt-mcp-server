#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
        echo -e "${BLUE}Loading environment from .env${NC}" >&2
    fi
    set -a && source .env && set +a
fi

# Load configuration
if [ ! -f ".config" ]; then
    echo -e "${RED}❌ .config file not found. Run ./deploy.sh first${NC}" >&2
    exit 1
fi

if [ "$VERBOSE" = true ]; then
    echo -e "${BLUE}Loading configuration from .config${NC}" >&2
fi
set -a && source .config && set +a

# Validate required variables
if [ -z "$TOKEN_ENDPOINT" ] || [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ] || [ -z "$OAUTH_SCOPES" ]; then
    echo -e "${RED}❌ Required authentication configuration missing${NC}" >&2
    echo -e "${YELLOW}💡 Run ./deploy.sh to regenerate .config with authentication details${NC}" >&2
    exit 1
fi

if [ "$VERBOSE" = true ]; then
    echo -e "${BLUE}🔐 Getting OAuth 2.0 access token...${NC}" >&2
    echo -e "${BLUE}Token Endpoint: ${TOKEN_ENDPOINT}${NC}" >&2
    echo -e "${BLUE}Client ID: ${CLIENT_ID}${NC}" >&2
    echo -e "${BLUE}Scopes: ${OAUTH_SCOPES}${NC}" >&2
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
    echo -e "${RED}❌ Failed to get access token${NC}" >&2
    echo -e "${YELLOW}Error response: $TOKEN_RESPONSE${NC}" >&2
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
        
        echo -e "${GREEN}✅ Access token retrieved successfully${NC}"
        echo -e "${BLUE}Token Type: ${TOKEN_TYPE}${NC}"
        echo -e "${BLUE}Expires In: ${EXPIRES_IN} seconds ($(($EXPIRES_IN / 60)) minutes)${NC}"
        echo -e "${BLUE}Token: ${ACCESS_TOKEN:0:50}...${NC}"
        echo ""
        echo -e "${YELLOW}💡 Use this token in Authorization header:${NC}"
        echo -e "${BLUE}Authorization: Bearer $ACCESS_TOKEN${NC}"
        ;;
    *)
        echo -e "${RED}❌ Unknown output format: $OUTPUT_FORMAT${NC}" >&2
        exit 1
        ;;
esac

if [ "$VERBOSE" = true ] && [ "$OUTPUT_FORMAT" = "token" ]; then
    echo -e "${GREEN}✅ Token retrieved successfully${NC}" >&2
fi