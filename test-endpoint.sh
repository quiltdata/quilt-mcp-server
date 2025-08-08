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
STACK_NAME="QuiltMcpStack"
REGION=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -s|--stack)
            STACK_NAME="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -e|--endpoint)
            ENDPOINT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Test MCP endpoint functionality"
            echo ""
            echo "Options:"
            echo "  -v, --verbose      Enable verbose output"
            echo "  -s, --stack        CloudFormation stack name (default: QuiltMcpStack)"
            echo "  -r, --region       AWS region (default: from env or us-east-1)"
            echo "  -e, --endpoint     Direct endpoint URL (skips CloudFormation lookup)"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Test with defaults"
            echo "  $0 -v                                 # Test with verbose output"
            echo "  $0 -e https://api.example.com/mcp/    # Test specific endpoint"
            echo "  $0 -v -s MyStack -r us-west-2        # Test custom stack"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Load environment if available
if [ -f ".env" ]; then
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Loading environment from .env${NC}"
    fi
    set -a && source .env && set +a
fi

# Set region default
if [ -z "$REGION" ]; then
    REGION=${CDK_DEFAULT_REGION:-us-east-1}
fi

echo -e "${BLUE}🧪 Testing MCP Endpoint${NC}"

# Get endpoint from CloudFormation if not provided directly
if [ -z "$ENDPOINT" ]; then
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Fetching endpoint from CloudFormation stack: ${STACK_NAME} in ${REGION}${NC}"
    fi
    
    ENDPOINT=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
        --output text 2>/dev/null)
    
    if [ -z "$ENDPOINT" ] || [ "$ENDPOINT" = "None" ]; then
        echo -e "${RED}❌ Failed to get endpoint from CloudFormation stack: ${STACK_NAME}${NC}"
        echo -e "${YELLOW}💡 Try specifying the endpoint directly with -e flag${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Testing endpoint: ${ENDPOINT}${NC}"

# Test 1: Basic connectivity (GET request)
echo -e "${BLUE}Test 1: Basic connectivity (GET)${NC}"
if [ "$VERBOSE" = true ]; then
    echo -e "${BLUE}Running: curl -s -w '%{http_code}' -o /dev/null ${ENDPOINT}${NC}"
fi

HTTP_STATUS=$(curl -s -w '%{http_code}' -o /dev/null "$ENDPOINT")
if [ "$HTTP_STATUS" -eq 200 ] || [ "$HTTP_STATUS" -eq 405 ]; then
    echo -e "${GREEN}✅ Endpoint is reachable (HTTP $HTTP_STATUS)${NC}"
else
    echo -e "${RED}❌ Endpoint connectivity failed (HTTP $HTTP_STATUS)${NC}"
    if [ "$VERBOSE" = true ]; then
        echo -e "${YELLOW}Response body:${NC}"
        curl -s "$ENDPOINT" || echo "No response body"
    fi
    exit 1
fi

# Test 2: MCP tools/list method
echo -e "${BLUE}Test 2: MCP tools/list method${NC}"
MCP_REQUEST='{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'

if [ "$VERBOSE" = true ]; then
    echo -e "${BLUE}Request payload:${NC}"
    echo "$MCP_REQUEST" | jq . 2>/dev/null || echo "$MCP_REQUEST"
    echo ""
fi

MCP_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$MCP_REQUEST")

if [ "$VERBOSE" = true ]; then
    echo -e "${BLUE}Response:${NC}"
    echo "$MCP_RESPONSE" | jq . 2>/dev/null || echo "$MCP_RESPONSE"
    echo ""
fi

if echo "$MCP_RESPONSE" | grep -q "tools"; then
    echo -e "${GREEN}✅ MCP tools/list method works${NC}"
    
    # Extract and display tools if verbose
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Available tools:${NC}"
        echo "$MCP_RESPONSE" | jq -r '.result.tools[]?.name' 2>/dev/null | sed 's/^/  - /' || echo "  Could not parse tools list"
    fi
else
    echo -e "${RED}❌ MCP tools/list method failed${NC}"
    echo -e "${YELLOW}Response: $MCP_RESPONSE${NC}"
    exit 1
fi

# Test 3: MCP initialize method
echo -e "${BLUE}Test 3: MCP initialize method${NC}"
INIT_REQUEST='{"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'

if [ "$VERBOSE" = true ]; then
    echo -e "${BLUE}Request payload:${NC}"
    echo "$INIT_REQUEST" | jq . 2>/dev/null || echo "$INIT_REQUEST"
    echo ""
fi

INIT_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$INIT_REQUEST")

if [ "$VERBOSE" = true ]; then
    echo -e "${BLUE}Response:${NC}"
    echo "$INIT_RESPONSE" | jq . 2>/dev/null || echo "$INIT_RESPONSE"
    echo ""
fi

if echo "$INIT_RESPONSE" | grep -q '"result"'; then
    echo -e "${GREEN}✅ MCP initialize method works${NC}"
    
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Server info:${NC}"
        echo "$INIT_RESPONSE" | jq -r '.result.serverInfo // "No server info"' 2>/dev/null || echo "  Could not parse server info"
    fi
else
    echo -e "${YELLOW}⚠️  MCP initialize method gave unexpected response${NC}"
    if [ "$VERBOSE" = true ]; then
        echo -e "${YELLOW}Response: $INIT_RESPONSE${NC}"
    fi
fi

echo ""
echo -e "${GREEN}🎉 All tests completed successfully!${NC}"
echo -e "${BLUE}Endpoint is ready for use with Claude.ai${NC}"

if [ "$VERBOSE" = false ]; then
    echo -e "${YELLOW}💡 Run with -v flag for detailed output${NC}"
fi
