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
SPECIFIC_TOOL=""
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

# Simple HTTP request wrapper
http_request() {
    local method="$1" endpoint="$2" data="$3" auth_token="$4" session_id="$5"
    
    local headers=("-H" "Content-Type: application/json" "-H" "Accept: application/json, text/event-stream")
    [ -n "$auth_token" ] && headers+=("-H" "Authorization: Bearer $auth_token")
    [ -n "$session_id" ] && headers+=("-H" "Mcp-Session-Id: $session_id")
    
    if [ "$method" = "GET" ]; then
        curl -s "${headers[@]}" "$endpoint"
    else
        curl -s -X "$method" "${headers[@]}" -d "$data" "$endpoint"
    fi
}

# Extract JSON from SSE response if needed
parse_response() {
    local response="$1"
    if echo "$response" | grep -q "^data: "; then
        echo "$response" | grep "^data: " | sed 's/^data: //' | head -1
    else
        echo "$response"
    fi
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
    echo "  $0 -t                 # Run tools tests"
    echo "  $0 -l -t              # Run tools tests against local server"
    echo ""
    echo -e "${BLUE}To modify test parameters, edit:${NC} $TEST_TOOLS_FILE"
}

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Test MCP endpoint functionality. Remote tests require JWT auth."
    echo ""
    echo "Default behavior:"
    echo "  - If --local is NOT set:"
    echo "      • Use API_ENDPOINT from ./.config (written by deploy) OR --endpoint"
    echo "      • Retrieve JWT via scripts/get-token.sh (or use --token)"
    echo "      • Run basic health (GET), tools/list, and initialize"
    echo "  - If --tools or --full is NOT set:"
    echo "      • Run health checks"
    echo "Options:"
    echo "  -v, --verbose      Enable verbose output"
    echo "  -f, --full         Run comprehensive Claude.ai simulation tests"
    echo "  -t, --tools [NAME] Run tools tests (or specific tool if NAME provided)"
    echo "  -l, --local        Start and test local FastMCP server (auto-starts on port 8000)"
    echo "  -e, --endpoint     Direct endpoint URL"
    echo "  --token TOKEN      Use specific JWT token for authentication"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Remote test using ./.config API_ENDPOINT"
    echo "  $0 -v                                 # Test with verbose output"
    echo "  $0 -t                                 # Add tools tests against remote endpoint"
    echo "  $0 -t package_create                  # Test specific tool"
    echo "  $0 -l                                 # Start local server and run health checks"
    echo "  $0 -l -t                              # Local tools tests"
    echo "  $0 -l -t bucket_list                  # Test specific tool locally"
    echo "  $0 -f                                 # Run full Claude.ai simulation"
    echo "  $0 --token \$TOKEN                    # Use a provided JWT token"
    echo "  $0 -e https://api.example.com/mcp/    # Override endpoint"
    echo ""
    echo "Authentication:"
    echo "  Remote tests require JWT authentication. By default we auto-retrieve a token"
    echo "  using scripts/get-token.sh (configured via ./.config). You may also pass"
    echo "  --token to use a specific JWT. Local tests do not use JWT."
}

dump_logs_on_failure() {
    # Only dump logs for remote (non-local) endpoints
    if [ "$LOCAL_TEST" != true ] && [ -f ".config" ]; then
        echo -e "${YELLOW}📋 Dumping recent Lambda logs for debugging...${NC}"
        ./scripts/check-logs.sh -s 5m 2>/dev/null | tail -20 || echo "Failed to retrieve logs"
    fi
}

# Load configuration from files
load_config() {
    # Load .env if exists
    [ -f ".env" ] && { [ "$VERBOSE" = true ] && log_info "Loading .env"; set -a && source .env && set +a; }
    
    # Load .config if exists and no endpoint provided
    if [ -z "$ENDPOINT" ] && [ -f ".config" ]; then
        [ "$VERBOSE" = true ] && echo -e "${BLUE}Loading .config${NC}"
        set -a && source .config && set +a
        ENDPOINT="${API_ENDPOINT}"
    fi
}

# Setup authentication token
setup_authentication() {
    [ -n "$ACCESS_TOKEN" ] && { [ "$VERBOSE" = true ] && echo -e "${GREEN}Using provided token${NC}"; return; }
    
    [ "$VERBOSE" = true ] && echo -e "${BLUE}Retrieving JWT token...${NC}"
    
    local get_token_script="$SCRIPT_DIR/../scripts/get-token.sh"
    if [ ! -f "$get_token_script" ]; then
        echo -e "${RED}❌ get-token.sh not found${NC}"
        echo -e "${YELLOW}Use --token or configure ./.config${NC}"
        exit 1
    fi
    
    ACCESS_TOKEN=$("$get_token_script" 2>/dev/null)
    if [ $? -ne 0 ] || [ -z "$ACCESS_TOKEN" ]; then
        echo -e "${RED}❌ Failed to get token${NC}"
        exit 1
    fi
    
    [ "$VERBOSE" = true ] && echo -e "${GREEN}✅ Token retrieved${NC}"
}


# Test a single tool
test_tool() {
    local endpoint="$1" auth_token="$2" tool_name="$3" tool_id="$4" session_id="$5"
    
    # Get test arguments from config
    local test_config="$SCRIPT_DIR/test-tools.json"
    local args="{}"
    [ -f "$test_config" ] && args=$(jq -c ".tools.\"$tool_name\".arguments // {}" "$test_config" 2>/dev/null)
    args=$(substitute_env_vars "$args")
    
    # Call the tool
    local request="{\"jsonrpc\":\"2.0\",\"id\":$tool_id,\"method\":\"tools/call\",\"params\":{\"name\":\"$tool_name\",\"arguments\":$args}}"
    local response=$(http_request "POST" "$endpoint" "$request" "$auth_token" "$session_id")
    local result=$(parse_response "$response")
    
    # Check if successful
    if echo "$result" | grep -q '"content"' && ! echo "$result" | grep -q '"isError":true'; then
        echo -e "  ${GREEN}✅ PASS${NC}"
        [ "$VERBOSE" = true ] && echo "$result" | jq -r '.result.content[0].text' 2>/dev/null | head -c 100 | sed 's/^/    /'
        return 0
    else
        echo -e "  ${RED}❌ FAIL${NC}"
        [ "$VERBOSE" = true ] && echo "$result" | jq -r '.error.message // .result.content[0].text' 2>/dev/null | head -c 200 | sed 's/^/    /'
        return 1
    fi
}

# Test multiple tools
test_tools() {
    local endpoint="$1" auth_token="$2" specific_tool="$3" session_id="$4"
    
    echo -e "${BLUE}=================== TESTING TOOLS ===================${NC}"
    
    # Get session if not provided
    if [ -z "$session_id" ]; then
        session_id=$(init_session "$endpoint" "$auth_token")
        [ -z "$session_id" ] && { echo -e "${RED}❌ Failed to establish session${NC}"; return 1; }
    fi
    
    # Get available tools
    local available_tools=$(list_tools "$endpoint" "$auth_token" "$session_id")
    
    if [ -z "$available_tools" ]; then
        echo -e "${RED}❌ No tools available${NC}"
        return 1
    fi
    
    # Filter to specific tool if requested
    if [ -n "$specific_tool" ]; then
        if echo "$available_tools" | grep -q "^$specific_tool$"; then
            available_tools="$specific_tool"
            echo -e "${BLUE}Testing: $specific_tool${NC}"
        else
            echo -e "${RED}❌ Tool '$specific_tool' not found${NC}"
            echo -e "${BLUE}Available: $(echo "$available_tools" | tr '\n' ' ')${NC}"
            return 1
        fi
    fi
    
    # Test each tool
    local count=0 passed=0 failed=0
    for tool in $available_tools; do
        count=$((count + 1))
        echo -e "${BLUE}[$count] $tool${NC}"
        
        if test_tool "$endpoint" "$auth_token" "$tool" "$count" "$session_id"; then
            passed=$((passed + 1))
        else
            failed=$((failed + 1))
        fi
    done
    
    echo -e "${BLUE}Results: ${GREEN}$passed passed${NC}, ${RED}$failed failed${NC}"
    [ "$failed" -gt 0 ] && return 1
}


# Test Claude.ai compatibility
run_claude_simulation_tests() {
    echo -e "${BLUE}=================== CLAUDE.AI TESTS ===================${NC}"
    
    # CORS test
    echo -e "${BLUE}CORS Preflight${NC}"
    local cors=$(curl -s -w '%{http_code}' -o /dev/null -X OPTIONS "$ENDPOINT" -H "Origin: https://claude.ai")
    if [ "$cors" -eq 200 ] || [ "$cors" -eq 204 ]; then
        echo -e "  ${GREEN}✅ Works (HTTP $cors)${NC}"
    else
        echo -e "  ${RED}❌ Failed (HTTP $cors)${NC}"
    fi
    
    # Claude initialize test
    echo -e "${BLUE}Claude Initialize${NC}"
    local init_data='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{"roots":{"listChanged":true}},"clientInfo":{"name":"Claude","version":"3.0"}}}'
    local response=$(http_request "POST" "$ENDPOINT" "$init_data" "$AUTH_TOKEN")
    
    if echo "$response" | grep -q '"result"'; then
        echo -e "  ${GREEN}✅ Initialize works${NC}"
        if echo "$response" | grep -q '"tools"'; then
            echo -e "  ${GREEN}✅ Tools capability${NC}"
        fi
    else
        echo -e "  ${RED}❌ Initialize failed${NC}"
    fi
}


# Check basic connectivity and get session
check_connectivity() {
    local endpoint="$1" auth_token="$2"
    echo -e "${BLUE}Connectivity${NC}"
    
    local session_id=$(init_session "$endpoint" "$auth_token")
    
    if [ -n "$session_id" ]; then
        echo -e "  ${GREEN}✅ Server responding (session: ${session_id:0:8}...)${NC}"
        echo "$session_id"
        return 0
    else
        echo -e "  ${RED}❌ Server not responding${NC}"
        dump_logs_on_failure
        return 1
    fi
}

# Initialize MCP session and get session ID
init_session() {
    local endpoint="$1" auth_token="$2"
    
    local init_request='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}'
    
    local response=$(curl -s -i -X POST "$endpoint" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        $([ -n "$auth_token" ] && echo "-H 'Authorization: Bearer $auth_token'") \
        -d "$init_request")
    
    local session_id=$(echo "$response" | grep -i "mcp-session-id:" | head -1 | sed 's/.*mcp-session-id: *\([^ \r]*\).*/\1/' | tr -d '\r')
    
    if [ -n "$session_id" ]; then
        # Send initialized notification
        http_request "POST" "$endpoint" '{"jsonrpc":"2.0","method":"notifications/initialized"}' "$auth_token" "$session_id" >/dev/null
        echo "$session_id"
    fi
}

# Get list of available tools from server
list_tools() {
    local endpoint="$1" auth_token="$2" session_id="$3"
    
    local response=$(http_request "POST" "$endpoint" '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' "$auth_token" "$session_id")
    local json=$(parse_response "$response")
    
    if echo "$json" | grep -q "tools"; then
        echo "$json" | jq -r '.result.tools[].name' 2>/dev/null
    fi
}

# Show available tools
show_tools() {
    local endpoint="$1" auth_token="$2" session_id="$3"
    echo -e "${BLUE}Available tools${NC}"
    
    local tools=$(list_tools "$endpoint" "$auth_token" "$session_id")
    
    if [ -n "$tools" ]; then
        local count=$(echo "$tools" | wc -l | tr -d ' ')
        echo -e "  ${GREEN}✅ Found $count tools:${NC}"
        echo "$tools" | sed 's/^/    - /'
    else
        echo -e "  ${YELLOW}⚠️  No tools available${NC}"
    fi
}

# Health check orchestration
run_health_check() {
    local endpoint="$1" auth_token="$2"
    
    echo -e "${BLUE}=================== HEALTH CHECK ===================${NC}"
    
    local session_id=$(check_connectivity "$endpoint" "$auth_token")
    [ -z "$session_id" ] && exit 1
    
    show_tools "$endpoint" "$auth_token" "$session_id"
    
    echo -e "${BLUE}=================== HEALTH CHECK COMPLETE ===================${NC}"
    
    # Return session ID for reuse
    echo "$session_id"
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
        -e|--endpoint)
            ENDPOINT="$2"
            shift 2
            ;;
        -f|--full)
            FULL_TEST=true
            shift
            ;;
        -t|--tools)
            if [ -n "$2" ] && [[ "$2" != -* ]]; then
                SPECIFIC_TOOL="$2"
                shift 2
            else
                TOOLS_TEST=true
                shift
            fi
            ;;
        -l|--local)
            LOCAL_TEST=true
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

# Load configuration
load_config

# Start local server if needed
start_local_server() {
    echo -e "${BLUE}Starting local FastMCP server...${NC}"
    
    # Check if server is already running
    if curl -s -H "Accept: text/event-stream" "http://localhost:8000/mcp" >/dev/null 2>&1; then
        echo -e "${YELLOW}Server already running on localhost:8000${NC}"
        return 0
    fi
    
    # Start server in background
    FASTMCP_TRANSPORT=streamable-http uv run python -m quilt_mcp &
    SERVER_PID=$!
    
    echo -e "${BLUE}Server starting (PID: $SERVER_PID)...${NC}"
    
    # Wait for server to start (max 10 seconds)
    local count=0
    while [ $count -lt 20 ]; do
        if curl -s -H "Accept: text/event-stream" "http://localhost:8000/mcp" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Server ready${NC}"
            return 0
        fi
        sleep 0.5
        count=$((count + 1))
    done
    
    echo -e "${RED}❌ Server failed to start${NC}"
    kill $SERVER_PID 2>/dev/null
    exit 1
}

stop_local_server() {
    if [ -n "$SERVER_PID" ]; then
        echo -e "${BLUE}Stopping server (PID: $SERVER_PID)...${NC}"
        kill $SERVER_PID 2>/dev/null
        wait $SERVER_PID 2>/dev/null
    fi
}

# Trap to cleanup server on exit
trap 'stop_local_server' EXIT INT TERM

# Determine endpoint and auth
if [ "$LOCAL_TEST" = true ]; then
    start_local_server
    ENDPOINT="http://localhost:8000/mcp"
    AUTH_TOKEN=""
else
    if [ -z "$ENDPOINT" ]; then
        echo -e "${RED}❌ No endpoint configured${NC}"
        echo -e "${YELLOW}Use --endpoint or configure .config${NC}"
        exit 1
    fi
    setup_authentication
    AUTH_TOKEN="$ACCESS_TOKEN"
fi

echo -e "${GREEN}Testing: $ENDPOINT${NC}"

# Always run health check (shows server tools and gets session)
SESSION_ID=$(run_health_check "$ENDPOINT" "$AUTH_TOKEN")

# Run additional tests if requested
if [ "$FULL_TEST" = true ]; then
    echo ""
    run_claude_simulation_tests
fi

if [ "$TOOLS_TEST" = true ] || [ -n "$SPECIFIC_TOOL" ]; then
    echo ""
    test_tools "$ENDPOINT" "$AUTH_TOKEN" "$SPECIFIC_TOOL" "$SESSION_ID"
fi

echo ""
echo -e "${GREEN}🎉 Tests complete!${NC}"