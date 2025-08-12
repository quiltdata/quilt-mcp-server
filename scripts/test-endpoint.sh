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
FULL_TEST=false
TOOLS_TEST=false
LOCAL_TEST=false
TOOL_NUMBER=""
STACK_NAME="QuiltMcpStack"
REGION=""
USE_AUTH=true
ACCESS_TOKEN=""

#==============================================================================
# FUNCTION DEFINITIONS
#==============================================================================

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Test MCP endpoint functionality with JWT authentication support"
    echo ""
    echo "Options:"
    echo "  -v, --verbose      Enable verbose output"
    echo "  -f, --full         Run comprehensive Claude.ai simulation tests"
    echo "  -t, --tools [N]    Test each available MCP tool (or just tool N)"
    echo "  -l, --local        Test local FastMCP server with session management"
    echo "  -s, --stack        CloudFormation stack name (default: QuiltMcpStack)"
    echo "  -r, --region       AWS region (default: from env or us-east-1)"
    echo "  -e, --endpoint     Direct endpoint URL (skips CloudFormation lookup)"
    echo "  --no-auth          Test without JWT authentication (legacy mode)"
    echo "  --token TOKEN      Use specific JWT token for authentication"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Test with auto JWT authentication"
    echo "  $0 -v                                 # Test with verbose output"
    echo "  $0 -t                                 # Test each available tool"
    echo "  $0 -l                                 # Test local FastMCP server"
    echo "  $0 -f                                 # Run full Claude.ai simulation"
    echo "  $0 --no-auth                          # Test without authentication (legacy)"
    echo "  $0 --token \$TOKEN                    # Test with specific JWT token"
    echo "  $0 -e https://api.example.com/mcp/    # Test specific endpoint"
    echo "  $0 -v -s MyStack -r us-west-2         # Test custom stack"
    echo ""
    echo "Authentication:"
    echo "  By default, tests use JWT authentication with auto-token retrieval."
    echo "  Requires .config file or deployment configuration for auth parameters."
    echo "  Use --no-auth for testing legacy unauthenticated endpoints."
}

setup_authentication() {
    if [ "$USE_AUTH" = false ]; then
        if [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}Running in no-auth mode (legacy)${NC}"
        fi
        return 0
    fi
    
    # Try to get token if not provided
    if [ -z "$ACCESS_TOKEN" ]; then
        if [ "$VERBOSE" = true ]; then
            echo -e "${BLUE}Retrieving JWT access token...${NC}"
        fi
        
        # Check if we have get_token.sh script
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
        if [ -f "$SCRIPT_DIR/scripts/get_token.sh" ]; then
            ACCESS_TOKEN=$("$SCRIPT_DIR/scripts/get_token.sh" 2>/dev/null)
            if [ $? -ne 0 ] || [ -z "$ACCESS_TOKEN" ]; then
                echo -e "${RED}❌ Failed to retrieve access token${NC}"
                echo -e "${YELLOW}Use --no-auth for unauthenticated testing or --token to provide token${NC}"
                exit 1
            fi
            if [ "$VERBOSE" = true ]; then
                echo -e "${GREEN}✅ Access token retrieved${NC}"
            fi
        else
            echo -e "${RED}❌ get_token.sh script not found${NC}"
            echo -e "${YELLOW}Use --no-auth for unauthenticated testing or --token to provide token${NC}"
            exit 1
        fi
    else
        if [ "$VERBOSE" = true ]; then
            echo -e "${GREEN}Using provided access token${NC}"
        fi
    fi
}

get_auth_headers() {
    if [ "$USE_AUTH" = true ] && [ -n "$ACCESS_TOKEN" ]; then
        echo "-H \"Authorization: Bearer $ACCESS_TOKEN\""
    fi
}

test_local_fastmcp() {
    local LOCAL_ENDPOINT="http://localhost:8000/mcp"
    echo -e "${BLUE}=================== LOCAL FASTMCP SESSION TEST ===================${NC}"
    
    # Test 1: Initialize session
    echo -e "${BLUE}Step 1: Initialize session${NC}"
    INIT_REQUEST='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}'
    
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Sending initialize request to $LOCAL_ENDPOINT${NC}"
        echo "$INIT_REQUEST" | jq . 2>/dev/null || echo "$INIT_REQUEST"
    fi
    
    # Get response with headers to extract session ID
    INIT_RESPONSE=$(curl -s -i -X POST "$LOCAL_ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d "$INIT_REQUEST")
    
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Initialize response:${NC}"
        echo "$INIT_RESPONSE"
        echo ""
    fi
    
    # Extract session ID from response headers
    SESSION_ID=$(echo "$INIT_RESPONSE" | grep -i "mcp-session-id:" | head -1 | sed 's/.*mcp-session-id: *\([^ \r]*\).*/\1/' | tr -d '\r')
    
    if [ -n "$SESSION_ID" ]; then
        echo -e "${GREEN}✅ Session initialized with ID: $SESSION_ID${NC}"
        
        # Send initialized notification to complete the MCP handshake
        if [ "$VERBOSE" = true ]; then
            echo -e "${BLUE}Sending initialized notification...${NC}"
        fi
        curl -s -X POST "$LOCAL_ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -H "Mcp-Session-Id: $SESSION_ID" \
            -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null
        
        SESSION_HEADER="-H \"Mcp-Session-Id: $SESSION_ID\""
    else
        echo -e "${YELLOW}⚠️  No session ID returned, proceeding without session management${NC}"
        SESSION_HEADER=""
    fi
    
    # Test 2: Tools list with session
    echo -e "${BLUE}Step 2: Test tools/list with session${NC}"
    TOOLS_REQUEST='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
    
    if [ -n "$SESSION_ID" ]; then
        TOOLS_RESPONSE=$(curl -s -X POST "$LOCAL_ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -H "Mcp-Session-Id: $SESSION_ID" \
            -d "$TOOLS_REQUEST")
    else
        TOOLS_RESPONSE=$(curl -s -X POST "$LOCAL_ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -d "$TOOLS_REQUEST")
    fi
    
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Tools response:${NC}"
        echo "$TOOLS_RESPONSE"
        echo ""
    fi
    
    # Extract JSON from SSE format or use as-is if it's plain JSON
    if echo "$TOOLS_RESPONSE" | grep -q "^data: "; then
        TOOLS_JSON=$(echo "$TOOLS_RESPONSE" | grep "^data: " | sed 's/^data: //' | head -1)
    else
        TOOLS_JSON="$TOOLS_RESPONSE"
    fi
    
    if echo "$TOOLS_JSON" | grep -q "tools"; then
        echo -e "${GREEN}✅ Tools list successful${NC}"
    else
        echo -e "${RED}❌ Tools list failed${NC}"
        echo -e "${YELLOW}Response: $TOOLS_JSON${NC}"
        return 1
    fi
    
    # Test 3: Simple tool call with session
    echo -e "${BLUE}Step 3: Test tool call with session${NC}"
    TOOL_REQUEST='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"check_quilt_auth","arguments":{}}}'
    
    if [ -n "$SESSION_ID" ]; then
        TOOL_RESPONSE=$(curl -s -X POST "$LOCAL_ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -H "Mcp-Session-Id: $SESSION_ID" \
            -d "$TOOL_REQUEST")
    else
        TOOL_RESPONSE=$(curl -s -X POST "$LOCAL_ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -d "$TOOL_REQUEST")
    fi
    
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Tool response:${NC}"
        echo "$TOOL_RESPONSE"
        echo ""
    fi
    
    # Extract JSON from SSE format or use as-is if it's plain JSON
    if echo "$TOOL_RESPONSE" | grep -q "^data: "; then
        TOOL_JSON=$(echo "$TOOL_RESPONSE" | grep "^data: " | sed 's/^data: //' | head -1)
    else
        TOOL_JSON="$TOOL_RESPONSE"
    fi
    
    if echo "$TOOL_JSON" | grep -q '"content"'; then
        echo -e "${GREEN}✅ Tool call successful${NC}"
    else
        echo -e "${RED}❌ Tool call failed${NC}"
        echo -e "${YELLOW}Response: $TOOL_JSON${NC}"
    fi
    
    echo -e "${BLUE}=================== LOCAL FASTMCP TEST COMPLETE ===================${NC}"
}

run_claude_simulation_tests() {
    echo -e "${BLUE}=================== CLAUDE.AI SIMULATION TESTS ===================${NC}"
    
    # Test 1: CORS Preflight (what Claude does first)
    echo -e "${BLUE}Claude Test 1: CORS Preflight Request${NC}"
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Testing preflight with Origin: https://claude.ai${NC}"
    fi
    
    CORS_STATUS=$(curl -s -w '%{http_code}' -o /dev/null -X OPTIONS "$ENDPOINT" \
        -H "Origin: https://claude.ai" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: content-type")
    
    if [ "$CORS_STATUS" -eq 200 ] || [ "$CORS_STATUS" -eq 204 ]; then
        echo -e "${GREEN}✅ CORS preflight successful (HTTP $CORS_STATUS)${NC}"
        
        if [ "$VERBOSE" = true ]; then
            echo -e "${BLUE}Full CORS response headers:${NC}"
            curl -s -I -X OPTIONS "$ENDPOINT" \
                -H "Origin: https://claude.ai" \
                -H "Access-Control-Request-Method: POST" \
                -H "Access-Control-Request-Headers: content-type" | grep -i "access-control"
        fi
    else
        echo -e "${RED}❌ CORS preflight failed (HTTP $CORS_STATUS)${NC}"
        return 1
    fi
    
    # Test 2: Initialize with Claude-specific capabilities
    echo -e "${BLUE}Claude Test 2: Initialize with Claude Capabilities${NC}"
    CLAUDE_INIT_REQUEST='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {"roots": {"listChanged": true}, "sampling": {}}, "clientInfo": {"name": "Claude", "version": "3.0"}}}'
    
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Claude initialize request:${NC}"
        echo "$CLAUDE_INIT_REQUEST" | jq . 2>/dev/null || echo "$CLAUDE_INIT_REQUEST"
        echo ""
    fi
    
    CLAUDE_INIT_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -H "User-Agent: Claude/3.0" \
        $(get_auth_headers) \
        -d "$CLAUDE_INIT_REQUEST")
    
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Response:${NC}"
        echo "$CLAUDE_INIT_RESPONSE" | jq . 2>/dev/null || echo "$CLAUDE_INIT_RESPONSE"
        echo ""
    fi
    
    if echo "$CLAUDE_INIT_RESPONSE" | grep -q '"result"'; then
        echo -e "${GREEN}✅ Claude-style initialize works${NC}"
        
        # Check if server supports expected capabilities
        if echo "$CLAUDE_INIT_RESPONSE" | grep -q '"tools"'; then
            echo -e "${GREEN}✅ Server advertises tools capability${NC}"
        else
            echo -e "${YELLOW}⚠️  Server missing tools capability${NC}"
        fi
    else
        echo -e "${RED}❌ Claude-style initialize failed${NC}"
        echo -e "${YELLOW}Response: $CLAUDE_INIT_RESPONSE${NC}"
    fi
    
    echo -e "${BLUE}=================== CLAUDE SIMULATION COMPLETE ===================${NC}"
}

run_tools_tests() {
    echo -e "${BLUE}=================== TESTING MCP TOOLS ===================${NC}"
    
    # First get the list of available tools
    echo -e "${BLUE}Getting list of available tools...${NC}"
    TOOLS_LIST_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        $(get_auth_headers) \
        -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}')
    
    if ! echo "$TOOLS_LIST_RESPONSE" | grep -q "tools"; then
        echo -e "${RED}❌ Failed to get tools list${NC}"
        return 1
    fi
    
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Tools list response:${NC}"
        echo "$TOOLS_LIST_RESPONSE" | jq . 2>/dev/null || echo "$TOOLS_LIST_RESPONSE"
        echo ""
    fi
    
    # Extract all available tools
    AVAILABLE_TOOLS=$(echo "$TOOLS_LIST_RESPONSE" | jq -r '.result.tools[].name' 2>/dev/null)
    
    if [ -z "$AVAILABLE_TOOLS" ]; then
        echo -e "${YELLOW}⚠️  No tools found${NC}"
        return 1
    fi
    
    echo -e "${BLUE}Available tools to test:${NC}"
    echo "$AVAILABLE_TOOLS" | sed 's/^/  - /'
    
    # Test each available tool
    TOOL_COUNT=1
    for TOOL_NAME in $AVAILABLE_TOOLS; do
        echo -e "${BLUE}Tool Test $TOOL_COUNT: $TOOL_NAME${NC}"
        
        # Create appropriate test arguments based on tool type
        case "$TOOL_NAME" in
            "check_quilt_auth"|"check_filesystem_access")
                TOOL_ARGUMENTS="{}"
                ;;
            "list_packages")
                TOOL_ARGUMENTS='{"limit": 3}'
                ;;
            "search_packages")
                TOOL_ARGUMENTS='{"query": "test", "limit": 2}'
                ;;
            "browse_package")
                TOOL_ARGUMENTS='{"package_name": "akarve/amazon-reviews"}'
                ;;
            "search_package_contents")
                TOOL_ARGUMENTS='{"package_name": "akarve/amazon-reviews", "query": "data"}'
                ;;
            *)
                TOOL_ARGUMENTS="{}"
                ;;
        esac
        
        TOOL_REQUEST="{\"jsonrpc\": \"2.0\", \"id\": $TOOL_COUNT, \"method\": \"tools/call\", \"params\": {\"name\": \"$TOOL_NAME\", \"arguments\": $TOOL_ARGUMENTS}}"
        TOOL_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
            -H "Content-Type: application/json" \
            $(get_auth_headers) \
            -d "$TOOL_REQUEST")
        
        if echo "$TOOL_RESPONSE" | grep -q '"content"'; then
            # Check if the content contains an error
            if echo "$TOOL_RESPONSE" | jq -r '.result.content[0].text' 2>/dev/null | grep -q '"error"'; then
                echo -e "${RED}❌ $TOOL_NAME failed (returned error)${NC}"
                if [ "$VERBOSE" = true ]; then
                    echo -e "${YELLOW}Response:${NC}"
                    echo "$TOOL_RESPONSE" | jq . 2>/dev/null || echo "$TOOL_RESPONSE"
                    echo ""
                fi
            else
                echo -e "${GREEN}✅ $TOOL_NAME works${NC}"
                if [ "$VERBOSE" = true ]; then
                    echo -e "${BLUE}Response:${NC}"
                    echo "$TOOL_RESPONSE" | jq . 2>/dev/null || echo "$TOOL_RESPONSE"
                    echo ""
                fi
            fi
        elif echo "$TOOL_RESPONSE" | grep -q '"error"'; then
            echo -e "${RED}❌ $TOOL_NAME failed${NC}"
            if [ "$VERBOSE" = true ]; then
                echo -e "${YELLOW}Response: $TOOL_RESPONSE${NC}"
            fi
        else
            echo -e "${RED}❌ $TOOL_NAME failed (unexpected response)${NC}"
            echo -e "${YELLOW}Response: $TOOL_RESPONSE${NC}"
        fi
        
        TOOL_COUNT=$((TOOL_COUNT + 1))
    done
    
    echo -e "${BLUE}=================== TOOLS TESTING COMPLETE ===================${NC}"
}

run_basic_tests() {
    # Test 1: Basic connectivity (GET request)
    echo -e "${BLUE}Test 1: Basic connectivity (GET)${NC}"
    if [ "$USE_AUTH" = true ]; then
        echo -e "${BLUE}Testing with JWT authentication...${NC}"
        if [ "$VERBOSE" = true ]; then
            echo -e "${BLUE}Running: curl -s -w '%{http_code}' -o /dev/null -H \"Authorization: Bearer \$ACCESS_TOKEN\" ${ENDPOINT}${NC}"
        fi
        HTTP_STATUS=$(curl -s -w '%{http_code}' -o /dev/null -H "Authorization: Bearer $ACCESS_TOKEN" "$ENDPOINT")
    else
        if [ "$VERBOSE" = true ]; then
            echo -e "${BLUE}Running: curl -s -w '%{http_code}' -o /dev/null ${ENDPOINT}${NC}"
        fi
        HTTP_STATUS=$(curl -s -w '%{http_code}' -o /dev/null "$ENDPOINT")
    fi

    if [ "$HTTP_STATUS" -eq 200 ] || [ "$HTTP_STATUS" -eq 405 ]; then
        echo -e "${GREEN}✅ Endpoint is reachable (HTTP $HTTP_STATUS)${NC}"
    elif [ "$HTTP_STATUS" -eq 401 ] && [ "$USE_AUTH" = false ]; then
        echo -e "${GREEN}✅ Endpoint is protected (HTTP 401 without auth, as expected)${NC}"
    else
        echo -e "${RED}❌ Endpoint connectivity failed (HTTP $HTTP_STATUS)${NC}"
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
        $(get_auth_headers) \
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
        $(get_auth_headers) \
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
}

#==============================================================================
# ARGUMENT PARSING
#==============================================================================

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
        -f|--full)
            FULL_TEST=true
            shift
            ;;
        -t|--tools)
            TOOLS_TEST=true
            # Check if next argument is a number (tool number)
            if [[ $2 =~ ^[0-9]+$ ]]; then
                TOOL_NUMBER="$2"
                shift 2
            else
                shift
            fi
            ;;
        -l|--local)
            LOCAL_TEST=true
            shift
            ;;
        --no-auth)
            USE_AUTH=false
            shift
            ;;
        --token)
            ACCESS_TOKEN="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

#==============================================================================
# MAIN EXECUTION
#==============================================================================

echo -e "${BLUE}🧪 Testing MCP Endpoint${NC}"

# Handle local test mode - exit early
if [ "$LOCAL_TEST" = true ]; then
    test_local_fastmcp
    exit 0
fi

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

# Setup authentication
setup_authentication

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

# Run basic tests
run_basic_tests

echo ""
echo -e "${GREEN}🎉 All tests completed successfully!${NC}"
echo -e "${BLUE}Endpoint is ready for use with Claude.ai${NC}"

if [ "$VERBOSE" = false ]; then
    echo -e "${YELLOW}💡 Run with -v flag for detailed output${NC}"
fi

# Run comprehensive Claude.ai simulation tests if requested
if [ "$FULL_TEST" = true ]; then
    echo ""
    echo -e "${BLUE}🔍 Running comprehensive Claude.ai simulation tests...${NC}"
    run_claude_simulation_tests
fi

# Run tools tests if requested
if [ "$TOOLS_TEST" = true ]; then
    echo ""
    echo -e "${BLUE}🔧 Running MCP tools tests...${NC}"
    run_tools_tests
fi