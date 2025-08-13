#!/bin/bash
set -e

# Load common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default values
VERBOSE=false
FULL_TEST=false
TOOLS_TEST=false
LOCAL_TEST=false
TOOL_NUMBER=""
LOCAL_TOOL_NAME=""
STACK_NAME="QuiltMcpStack"
REGION=""
USE_AUTH=true
ACCESS_TOKEN=""

#==============================================================================
# HELPER FUNCTIONS
#==============================================================================

# Helper: fetch env var by name
get_env_value() {
    local name="$1"; eval echo "\${$name}" 2>/dev/null
}

# Helper: substitute environment variables in JSON string
substitute_env_vars() {
    local json="$1"
    # Find all ${VAR_NAME} patterns and substitute them
    local result="$json"
    local pattern='\$\{([A-Z_][A-Z0-9_]*)\}'
    
    while [[ $result =~ $pattern ]]; do
        local var_name="${BASH_REMATCH[1]}"
        local var_value=$(get_env_value "$var_name")
        if [ -n "$var_value" ]; then
            result="${result//\$\{$var_name\}/$var_value}"
        else
            log_warning "Environment variable $var_name not set"
            break
        fi
    done
    echo "$result"
}

#==============================================================================
# FUNCTION DEFINITIONS
#==============================================================================

list_test_tools() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    TEST_TOOLS_FILE="$SCRIPT_DIR/test-tools.json"
    
    if [ ! -f "$TEST_TOOLS_FILE" ]; then
        echo -e "${RED}❌ test-tools.json not found at: $TEST_TOOLS_FILE${NC}"
        return 1
    fi
    
    echo -e "${BLUE}Available test tools:${NC}"
    echo "====================="
    
    # Get all tool names and descriptions
    jq -r '.tools | to_entries[] | "\(.key): \(.value.description)"' "$TEST_TOOLS_FILE" 2>/dev/null | while IFS=: read -r tool_name tool_desc; do
        echo -e "${GREEN}  $tool_name${NC}:$tool_desc"
    done
    
    echo ""
    echo -e "${BLUE}Usage:${NC}"
    echo "  $0 -l <tool_name>     # Test specific tool"
    echo "  $0 -l -v <tool_name>  # Test with verbose output"
    echo ""
    echo -e "${BLUE}To modify test parameters, edit:${NC} $TEST_TOOLS_FILE"
}

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Test MCP endpoint functionality with JWT authentication support"
    echo ""
    echo "Options:"
    echo "  -v, --verbose      Enable verbose output"
    echo "  -f, --full         Run comprehensive Claude.ai simulation tests"
    echo "  -t, --tools [N]    Test each available MCP tool (or just tool N)"
    echo "  -l, --local [TOOL] Test local FastMCP server with session management (optionally test specific tool)"
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
    echo "  $0 -l package_create                   # Test specific tool on local server"
    echo "  $0 -l --list-tools                     # Show available test tools"
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

dump_logs_on_failure() {
    if [ -f ".config" ]; then
        echo -e "${YELLOW}📋 Dumping recent Lambda logs for debugging...${NC}"
    ./scripts/check-logs.sh -s 5m 2>/dev/null | tail -20 || echo "Failed to retrieve logs"
    fi
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
        
        # Check if we have get-token.sh script
        SCRIPT_DIR="$(cd \"$(dirname \"${BASH_SOURCE[0]}\")/..\" && pwd)"
        if [ -f "$SCRIPT_DIR/scripts/get-token.sh" ]; then
            ACCESS_TOKEN=$("$SCRIPT_DIR/scripts/get-token.sh" 2>/dev/null)
            if [ $? -ne 0 ] || [ -z "$ACCESS_TOKEN" ]; then
                echo -e "${RED}❌ Failed to retrieve access token${NC}"
                echo -e "${YELLOW}Use --no-auth for unauthenticated testing or --token to provide token${NC}"
                exit 1
            fi
            if [ "$VERBOSE" = true ]; then
                echo -e "${GREEN}✅ Access token retrieved${NC}"
            fi
        else
            echo -e "${RED}❌ get-token.sh script not found${NC}"
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
    log_info "=================== LOCAL FASTMCP SESSION TEST ==================="
    
    # Test 1: Initialize session
    log_info "Step 1: Initialize session"
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
        dump_logs_on_failure
        return 1
    fi
    
    # Test 3: Tool call with session
    if [ -n "$LOCAL_TOOL_NAME" ]; then
        echo -e "${BLUE}Step 3: Test specific tool: $LOCAL_TOOL_NAME${NC}"
        
        # Load tool configuration from JSON file
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        TEST_TOOLS_FILE="$SCRIPT_DIR/test-tools.json"
        
        if [ -f "$TEST_TOOLS_FILE" ]; then
            # Get tool arguments from JSON file
            TOOL_ARGS=$(jq -r ".tools.\"$LOCAL_TOOL_NAME\".arguments // {}" "$TEST_TOOLS_FILE" 2>/dev/null)
            TOOL_DESC=$(jq -r ".tools.\"$LOCAL_TOOL_NAME\".description // \"Test $LOCAL_TOOL_NAME\"" "$TEST_TOOLS_FILE" 2>/dev/null)
            
            if [ "$TOOL_ARGS" != "null" ] && [ -n "$TOOL_ARGS" ]; then
                # Substitute environment variables in TOOL_ARGS
                TOOL_ARGS=$(substitute_env_vars "$TOOL_ARGS")
                
                if [ "$VERBOSE" = true ]; then
                    echo -e "${BLUE}Tool description: $TOOL_DESC${NC}"
                    echo -e "${BLUE}Using arguments from test-tools.json:${NC}"
                    echo "$TOOL_ARGS" | jq . 2>/dev/null || echo "$TOOL_ARGS"
                fi
                
                # Build the full request with arguments from JSON
                TOOL_REQUEST="{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"$LOCAL_TOOL_NAME\",\"arguments\":$TOOL_ARGS}}"
            else
                echo -e "${YELLOW}⚠️  Tool '$LOCAL_TOOL_NAME' not found in test-tools.json, using empty arguments${NC}"
                TOOL_REQUEST="{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"$LOCAL_TOOL_NAME\",\"arguments\":{}}}"
            fi
        else
            echo -e "${YELLOW}⚠️  test-tools.json not found, using empty arguments${NC}"
            TOOL_REQUEST="{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"$LOCAL_TOOL_NAME\",\"arguments\":{}}}"
        fi
    else
        echo -e "${BLUE}Step 3: Test tool call with session${NC}"
        TOOL_REQUEST='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"auth_status","arguments":{}}}'
    fi
    
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

test_local_fastmcp_all_tools() {
    local LOCAL_ENDPOINT="http://localhost:8000/mcp"
    log_info "=================== LOCAL FASTMCP ALL TOOLS TEST ==================="
    
    # Step 1: Initialize session (reuse logic from test_local_fastmcp)
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
    
    # Extract session ID from response headers
    SESSION_ID=$(echo "$INIT_RESPONSE" | grep -i "mcp-session-id:" | head -1 | sed 's/.*mcp-session-id: *\([^ \r]*\).*/\1/' | tr -d '\r')
    
    if [ -n "$SESSION_ID" ]; then
        echo -e "${GREEN}✅ Session initialized with ID: $SESSION_ID${NC}"
        
        # Send initialized notification to complete the MCP handshake
        curl -s -X POST "$LOCAL_ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -H "Mcp-Session-Id: $SESSION_ID" \
            -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null
    else
        echo -e "${YELLOW}⚠️  No session ID returned, proceeding without session management${NC}"
    fi
    
    # Step 2: Get tools list
    echo -e "${BLUE}Step 2: Get tools list${NC}"
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
    
    # Extract JSON from SSE format
    if echo "$TOOLS_RESPONSE" | grep -q "^data: "; then
        TOOLS_JSON=$(echo "$TOOLS_RESPONSE" | grep "^data: " | sed 's/^data: //' | head -1)
    else
        TOOLS_JSON="$TOOLS_RESPONSE"
    fi
    
    # Extract available tools
    AVAILABLE_TOOLS=$(echo "$TOOLS_JSON" | jq -r '.result.tools[].name' 2>/dev/null)
    
    if [ -z "$AVAILABLE_TOOLS" ]; then
        echo -e "${RED}❌ Failed to get tools list${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Found tools to test:${NC}"
    echo "$AVAILABLE_TOOLS" | sed 's/^/  - /'
    echo ""
    
    # Step 3: Test each tool from test-tools.json
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    TEST_TOOLS_FILE="$SCRIPT_DIR/test-tools.json"
    
    if [ ! -f "$TEST_TOOLS_FILE" ]; then
        echo -e "${RED}❌ test-tools.json not found at: $TEST_TOOLS_FILE${NC}"
        return 1
    fi
    
    # Get tools from test-tools.json
    TEST_TOOLS=$(jq -r '.tools | keys[]' "$TEST_TOOLS_FILE" 2>/dev/null)
    TOOL_COUNT=0
    SUCCESS_COUNT=0
    FAIL_COUNT=0
    
    for TOOL_NAME in $TEST_TOOLS; do
        TOOL_COUNT=$((TOOL_COUNT + 1))
        echo -e "${BLUE}Tool Test $TOOL_COUNT: $TOOL_NAME${NC}"
        
        # Get tool arguments from test-tools.json
        TOOL_ARGS=$(jq -c ".tools.\"$TOOL_NAME\".arguments // {}" "$TEST_TOOLS_FILE" 2>/dev/null)
        TOOL_DESC=$(jq -r ".tools.\"$TOOL_NAME\".description // \"Test $TOOL_NAME\"" "$TEST_TOOLS_FILE" 2>/dev/null)
        
        # Substitute environment variables in TOOL_ARGS
        TOOL_ARGS=$(substitute_env_vars "$TOOL_ARGS")
        
        if [ "$VERBOSE" = true ]; then
            echo -e "${BLUE}  Description: $TOOL_DESC${NC}"
            echo -e "${BLUE}  Arguments: $TOOL_ARGS${NC}"
        fi
        
        # Build tool request
        TOOL_REQUEST="{\"jsonrpc\":\"2.0\",\"id\":$((TOOL_COUNT + 2)),\"method\":\"tools/call\",\"params\":{\"name\":\"$TOOL_NAME\",\"arguments\":$TOOL_ARGS}}"
        
        # Make tool call
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
        
        # Extract JSON from SSE format
        if echo "$TOOL_RESPONSE" | grep -q "^data: "; then
            TOOL_JSON=$(echo "$TOOL_RESPONSE" | grep "^data: " | sed 's/^data: //' | head -1)
        else
            TOOL_JSON="$TOOL_RESPONSE"
        fi
        
        # Check if tool call was successful
        if echo "$TOOL_JSON" | grep -q '"content"' && ! echo "$TOOL_JSON" | grep -q '"isError":true'; then
            echo -e "${GREEN}  ✅ PASSED${NC}"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
            if [ "$VERBOSE" = true ]; then
                echo -e "${BLUE}  Response: ${NC}$(echo "$TOOL_JSON" | jq -r '.result.content[0].text' 2>/dev/null | head -c 100)..."
            fi
        else
            echo -e "${RED}  ❌ FAILED${NC}"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            if [ "$VERBOSE" = true ]; then
                echo -e "${YELLOW}  Error: ${NC}$(echo "$TOOL_JSON" | jq -r '.error.message // .result.content[0].text' 2>/dev/null | head -c 200)"
            fi
        fi
        echo ""
    done
    
    # Summary
    echo -e "${BLUE}=================== TEST SUMMARY ===================${NC}"
    echo -e "${GREEN}✅ Passed: $SUCCESS_COUNT${NC}"
    echo -e "${RED}❌ Failed: $FAIL_COUNT${NC}"
    echo -e "${BLUE}📋 Total:  $TOOL_COUNT${NC}"
    
    if [ "$FAIL_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}💡 Run with individual tool names for detailed error output${NC}"
        return 1
    fi
    
    echo -e "${BLUE}=================== LOCAL FASTMCP ALL TOOLS TEST COMPLETE ===================${NC}"
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
    
    # Path to test tools config
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    TEST_TOOLS_FILE="$SCRIPT_DIR/test-tools.json"
    if [ ! -f "$TEST_TOOLS_FILE" ]; then
        echo -e "${YELLOW}⚠️  test-tools.json not found, skipping detailed tool validations${NC}"
    fi

    # Helper: fetch env var by name from contains_env directive
    get_env_value() {
        local name="$1"; eval echo "\${$name}" 2>/dev/null
    }
    
    # Helper: substitute environment variables in JSON string
    substitute_env_vars() {
        local json="$1"
        # Find all ${VAR_NAME} patterns and substitute them
        local result="$json"
        local pattern='\$\{([A-Z_][A-Z0-9_]*)\}'
        
        while [[ $result =~ $pattern ]]; do
            local var_name="${BASH_REMATCH[1]}"
            local var_value=$(get_env_value "$var_name")
            if [ -n "$var_value" ]; then
                result="${result//\$\{$var_name\}/$var_value}"
            else
                echo "Warning: Environment variable $var_name not set" >&2
                break
            fi
        done
        echo "$result"
    }

    # Test each available tool with config-driven arguments & validations
    TOOL_COUNT=1
    for TOOL_NAME in $AVAILABLE_TOOLS; do
        echo -e "${BLUE}Tool Test $TOOL_COUNT: $TOOL_NAME${NC}"
        # Pull arguments from json file if present else empty
        if [ -f "$TEST_TOOLS_FILE" ]; then
            TOOL_ARGUMENTS=$(jq -c --arg name "$TOOL_NAME" '.tools[$name].arguments // {}' "$TEST_TOOLS_FILE" 2>/dev/null)
            VALIDATIONS=$(jq -c --arg name "$TOOL_NAME" '.tools[$name].validations // {}' "$TEST_TOOLS_FILE" 2>/dev/null)
        else
            TOOL_ARGUMENTS="{}"; VALIDATIONS="{}"
        fi

        [ -z "$TOOL_ARGUMENTS" ] || [ "$TOOL_ARGUMENTS" = "null" ] && TOOL_ARGUMENTS="{}"
        [ -z "$VALIDATIONS" ] || [ "$VALIDATIONS" = "null" ] && VALIDATIONS="{}"
        
        # Substitute environment variables in TOOL_ARGUMENTS
        TOOL_ARGUMENTS=$(substitute_env_vars "$TOOL_ARGUMENTS")

        TOOL_REQUEST="{\"jsonrpc\": \"2.0\", \"id\": $TOOL_COUNT, \"method\": \"tools/call\", \"params\": {\"name\": \"$TOOL_NAME\", \"arguments\": $TOOL_ARGUMENTS}}"
        TOOL_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
            -H "Content-Type: application/json" \
            $(get_auth_headers) \
            -d "$TOOL_REQUEST")

        RAW_TEXT=$(echo "$TOOL_RESPONSE" | jq -r '.result.content[0].text' 2>/dev/null || echo "")
        # Attempt to parse embedded JSON
        if echo "$RAW_TEXT" | jq . >/dev/null 2>&1; then
            RESULT_JSON="$RAW_TEXT"
        else
            # Fallback: sometimes tool returns direct object already
            RESULT_JSON=$(echo "$TOOL_RESPONSE" | jq '.result // empty')
        fi

        STATUS_ICON="${GREEN}✅${NC}"; FAILURE=false; FAILURE_REASONS=()
        if echo "$TOOL_RESPONSE" | grep -q '"error"' && ! echo "$TOOL_RESPONSE" | grep -q '"content"'; then
            FAILURE=true; FAILURE_REASONS+=("RPC error envelope")
        fi
        if echo "$RESULT_JSON" | grep -q '"error"'; then
            FAILURE=true; FAILURE_REASONS+=("Result contains error key")
        fi

        # Apply validations
        if [ "$VALIDATIONS" != "{}" ]; then
            # expect_keys
            for key in $(echo "$VALIDATIONS" | jq -r '.expect_keys[]?'); do
                if ! echo "$RESULT_JSON" | jq -e ". | has(\"$key\")" >/dev/null 2>&1; then
                    FAILURE=true; FAILURE_REASONS+=("missing key $key")
                fi
            done
            # enum validations
            echo "$VALIDATIONS" | jq -c '.enum // {}' | while read -r enumobj; do
                [ "$enumobj" = "{}" ] && continue
                for enum_key in $(echo "$enumobj" | jq -r 'keys[]'); do
                    allowed=$(echo "$enumobj" | jq -r --arg k "$enum_key" '.[$k][]')
                    value=$(echo "$RESULT_JSON" | jq -r --arg k "$enum_key" '.[$k] // empty')
                    if [ -n "$value" ]; then
                        match=false
                        for a in $allowed; do [ "$a" = "$value" ] && match=true; done
                        if [ "$match" = false ]; then FAILURE=true; FAILURE_REASONS+=("$enum_key value '$value' not in enum"); fi
                    fi
                done
            done
            # min_items
            for obj_key in $(echo "$VALIDATIONS" | jq -r '.min_items | keys[]?' 2>/dev/null); do
                min_required=$(echo "$VALIDATIONS" | jq -r --arg k "$obj_key" '.min_items[$k]')
                count=$(echo "$RESULT_JSON" | jq -r --arg k "$obj_key" '.[$k] | length' 2>/dev/null || echo 0)
                if [ "$count" -lt "$min_required" ]; then FAILURE=true; FAILURE_REASONS+=("$obj_key has $count < $min_required items"); fi
            done
            # contains_env
            for arr_key in $(echo "$VALIDATIONS" | jq -r '.contains_env | keys[]?' 2>/dev/null); do
                env_name=$(echo "$VALIDATIONS" | jq -r --arg k "$arr_key" '.contains_env[$k]')
                expected=$(get_env_value "$env_name")
                if [ -n "$expected" ]; then
                    if ! echo "$RESULT_JSON" | jq -e --arg k "$arr_key" --arg v "$expected" '.[$k][]? | select(. == $v)' >/dev/null 2>&1; then
                        FAILURE=true; FAILURE_REASONS+=("$arr_key missing expected env value $env_name=$expected")
                    fi
                fi
            done
            # min_number
            for num_key in $(echo "$VALIDATIONS" | jq -r '.min_number | keys[]?' 2>/dev/null); do
                min_required=$(echo "$VALIDATIONS" | jq -r --arg k "$num_key" '.min_number[$k]')
                value=$(echo "$RESULT_JSON" | jq -r --arg k "$num_key" '.[$k] // 0')
                if [ "$value" = "null" ] || [ "$value" -lt "$min_required" ]; then FAILURE=true; FAILURE_REASONS+=("$num_key=$value < $min_required"); fi
            done
            # min_text_length
            for txt_key in $(echo "$VALIDATIONS" | jq -r '.min_text_length | keys[]?' 2>/dev/null); do
                min_len=$(echo "$VALIDATIONS" | jq -r --arg k "$txt_key" '.min_text_length[$k]')
                value_len=$(echo "$RESULT_JSON" | jq -r --arg k "$txt_key" '.[$k] | length' 2>/dev/null || echo 0)
                if [ "$value_len" -lt "$min_len" ]; then FAILURE=true; FAILURE_REASONS+=("$txt_key length $value_len < $min_len"); fi
            done
            # one_of_keys_non_empty
            for group in $(echo "$VALIDATIONS" | jq -c '.one_of_keys_non_empty[]?' 2>/dev/null); do
                found=false
                for key in $(echo "$group" | jq -r '.[]'); do
                    if echo "$RESULT_JSON" | jq -e --arg k "$key" '.[$k] | length > 0' >/dev/null 2>&1; then found=true; break; fi
                done
                if [ "$found" = false ]; then FAILURE=true; FAILURE_REASONS+=("none of keys $(echo "$group" | jq -r '.[]' | paste -sd/,/) non-empty"); fi
            done
            # path_keys
            for pk in $(echo "$VALIDATIONS" | jq -r '.path_keys[]?' 2>/dev/null); do
                val=$(echo "$RESULT_JSON" | jq -r --arg k "$pk" '.[$k] // empty')
                if [ -n "$val" ] && [[ ! "$val" == /* ]]; then FAILURE=true; FAILURE_REASONS+=("$pk not absolute path: $val"); fi
            done
            # non_negative
            for nk in $(echo "$VALIDATIONS" | jq -r '.non_negative[]?' 2>/dev/null); do
                val=$(echo "$RESULT_JSON" | jq -r --arg k "$nk" '.[$k] // 0')
                if [ "$val" -lt 0 ]; then FAILURE=true; FAILURE_REASONS+=("$nk negative: $val"); fi
            done
        fi

        if [ "$FAILURE" = true ]; then
            echo -e "${RED}❌ $TOOL_NAME failed validations${NC}"
            if [ "$VERBOSE" = true ]; then
                echo -e "${YELLOW}Reasons:${NC} ${FAILURE_REASONS[*]}"
                echo -e "${BLUE}Raw tool response:${NC}"
                echo "$TOOL_RESPONSE" | jq . 2>/dev/null || echo "$TOOL_RESPONSE"
                echo -e "${BLUE}Parsed result JSON:${NC}"
                echo "$RESULT_JSON" | jq . 2>/dev/null || echo "$RESULT_JSON"
            fi
        else
            echo -e "${GREEN}✅ $TOOL_NAME passed${NC}"
            if [ "$VERBOSE" = true ]; then
                echo -e "${BLUE}Parsed result:${NC}"
                echo "$RESULT_JSON" | jq . 2>/dev/null || echo "$RESULT_JSON"
            fi
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
        dump_logs_on_failure
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
        dump_logs_on_failure
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
            # Check if next argument is a tool name or --list-tools
            if [[ $2 == "--list-tools" ]]; then
                list_test_tools
                exit 0
            elif [[ $2 && ! $2 =~ ^- ]]; then
                LOCAL_TOOL_NAME="$2"
                shift 2
            else
                shift
            fi
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

log_info "🧪 Testing MCP Endpoint"

# Load environment variables early (needed for local tests with env vars)
if [ -f ".env" ]; then
    if [ "$VERBOSE" = true ]; then
        log_info "Loading environment from .env"
    fi
    set -a && source .env && set +a
fi

# Handle local test mode 
if [ "$LOCAL_TEST" = true ]; then
    if [ "$TOOLS_TEST" = true ]; then
        # Run comprehensive local tools test
        test_local_fastmcp_all_tools
    else
        # Run single tool or basic local test
        test_local_fastmcp
    fi
    exit 0
fi

# Environment already loaded earlier

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