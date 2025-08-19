#!/bin/bash
# Simple MCP endpoint test script
set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

VERBOSE=false
TOOLS_TEST=false
LIST_TOOLS=false
SPECIFIC_TOOL=""
ENDPOINT=""

usage() {
    echo "Usage: $0 [-t] [-T tool_name] [-v] [--list-tools] <endpoint>"
    echo ""
    echo "Options:"
    echo "  -t              Run tools test (test all server tools with test configs)"
    echo "  -T tool_name    Test specific tool by name"
    echo "  -v              Verbose output"
    echo "  --list-tools    List available tools from MCP server with test coverage"
    echo ""
    echo "Arguments:"
    echo "  endpoint        MCP endpoint URL to test"
}

list_test_tools() {
    local endpoint="$1"
    local test_tools_file="$SCRIPT_DIR/test-tools.json"
    
    if [ -z "$endpoint" ]; then
        log_error "❌ Endpoint required for --list-tools"
        echo "Usage: $0 --list-tools <endpoint>"
        return 1
    fi
    
    log_info "Querying MCP server for available tools..."
    
    # Initialize session first
    local init_request='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}'
    
    local init_response
    init_response=$(curl -s -i -X POST "$endpoint" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d "$init_request" \
        --max-time 10 \
        --connect-timeout 5) || {
        log_error "Failed to connect to endpoint: $endpoint"
        return 1
    }
    
    # Extract session ID
    local session_id
    session_id=$(echo "$init_response" | grep -i "mcp-session-id:" | head -1 | sed 's/.*mcp-session-id: *\([^ \r]*\).*/\1/' | tr -d '\r')
    
    if [ -n "$session_id" ]; then
        # Send initialized notification
        curl -s -X POST "$endpoint" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -H "Mcp-Session-Id: $session_id" \
            -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null
    fi
    
    # Get tools list from server
    local tools_request='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
    local tools_response
    
    if [ -n "$session_id" ]; then
        tools_response=$(curl -s -X POST "$endpoint" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -H "Mcp-Session-Id: $session_id" \
            -d "$tools_request" \
            --max-time 10 \
            --connect-timeout 5)
    else
        tools_response=$(curl -s -X POST "$endpoint" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -d "$tools_request" \
            --max-time 10 \
            --connect-timeout 5)
    fi
    
    # Extract JSON from SSE format
    local json_response
    if echo "$tools_response" | grep -q "^data: "; then
        json_response=$(echo "$tools_response" | grep "^data: " | sed 's/^data: //' | head -1)
    else
        json_response="$tools_response"
    fi
    
    # Parse server response
    if ! echo "$json_response" | jq empty >/dev/null 2>&1; then
        log_error "Invalid JSON response from server"
        return 1
    fi
    
    if ! echo "$json_response" | jq -e '.result.tools' >/dev/null 2>&1; then
        log_error "Server did not return tools list"
        return 1
    fi
    
    echo "Available tools from MCP server:"
    echo "================================"
    
    # Get server tools and match with test configuration
    local server_tools
    server_tools=$(echo "$json_response" | jq -r '.result.tools[].name' 2>/dev/null)
    
    for tool_name in $server_tools; do
        # Get server description
        local server_desc
        server_desc=$(echo "$json_response" | jq -r --arg name "$tool_name" '.result.tools[] | select(.name == $name) | .description // "No description"' 2>/dev/null)
        
        # Check if we have test configuration for this tool
        local test_info=""
        if [ -f "$test_tools_file" ]; then
            local has_test_config
            has_test_config=$(jq -r --arg name "$tool_name" '.tools[$name] // null' "$test_tools_file" 2>/dev/null)
            if [ "$has_test_config" != "null" ] && [ -n "$has_test_config" ]; then
                test_info=" [✓ testable]"
            else
                test_info=" [⚠ no test config]"
            fi
        fi
        
        echo -e "${GREEN}  $tool_name${NC}: $server_desc$test_info"
    done
    
    echo ""
    if [ -f "$test_tools_file" ]; then
        local testable_count
        testable_count=$(echo "$server_tools" | while read -r tool; do
            if jq -e --arg name "$tool" '.tools[$name]' "$test_tools_file" >/dev/null 2>&1; then
                echo "1"
            fi
        done | wc -l | tr -d ' ')
        
        local total_count
        total_count=$(echo "$server_tools" | wc -l | tr -d ' ')
        
        echo "Test coverage: $testable_count/$total_count tools have test configurations"
    fi
    
    echo ""
    echo "Usage:"
    echo "  $0 -T <tool_name> <endpoint>  # Test specific tool"
    echo "  $0 -t <endpoint>              # Test all tools with test configs"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tools)
            TOOLS_TEST=true
            shift
            ;;
        -T|--tool)
            SPECIFIC_TOOL="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --list-tools)
            LIST_TOOLS=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        http*)
            ENDPOINT="$1"
            shift
            ;;
        *)
            if [[ -z "$ENDPOINT" ]]; then
                ENDPOINT="$1"
                shift
            else
                echo "Unknown option: $1"
                usage
                exit 1
            fi
            ;;
    esac
done

# Handle list tools mode
if [ "$LIST_TOOLS" = true ]; then
    list_test_tools "$ENDPOINT"
    exit 0
fi

# Check if endpoint is provided
if [[ -z "$ENDPOINT" ]]; then
    echo "Error: endpoint URL is required"
    usage
    exit 1
fi

# Check dependencies
check_dependencies jq curl

# Test individual tool using test-tools.json configuration
test_individual_tool() {
    local endpoint="$1"
    local tool_name="$2"
    local session_id="$3"
    local test_tools_file="$SCRIPT_DIR/test-tools.json"
    
    if [ ! -f "$test_tools_file" ]; then
        log_warning "⚠️  test-tools.json not found, using empty arguments"
        local tool_request="{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"$tool_name\",\"arguments\":{}}}"
    else
        # Get tool configuration from test-tools.json
        local tool_config
        tool_config=$(jq -c --arg name "$tool_name" '.tools[$name] // null' "$test_tools_file" 2>/dev/null)
        
        if [ "$tool_config" = "null" ] || [ -z "$tool_config" ]; then
            log_warning "⚠️  Tool '$tool_name' not found in test-tools.json, using empty arguments"
            local tool_request="{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"$tool_name\",\"arguments\":{}}}"
        else
            local arguments
            arguments=$(echo "$tool_config" | jq -c '.arguments // {}')
            
            if [ "$VERBOSE" = true ]; then
                log_info "Using arguments from test-tools.json:"
                echo "$arguments" | jq . 2>/dev/null || echo "$arguments"
            fi
            
            local tool_request
            tool_request=$(jq -n \
                --arg name "$tool_name" \
                --argjson args "$arguments" \
                '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":$name,"arguments":$args}}')
        fi
    fi
    
    log_info "Testing tool: $tool_name"
    
    local response
    if [ -n "$session_id" ]; then
        response=$(curl -s -X POST "$endpoint" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -H "Mcp-Session-Id: $session_id" \
            -d "$tool_request" \
            --max-time 30 \
            --connect-timeout 5)
    else
        response=$(curl -s -X POST "$endpoint" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -d "$tool_request" \
            --max-time 30 \
            --connect-timeout 5)
    fi
    
    if [ "$VERBOSE" = true ]; then
        echo "Tool response: $response"
    fi
    
    # Extract JSON from SSE format or use as-is if it's plain JSON
    local json_response
    if echo "$response" | grep -q "^data: "; then
        json_response=$(echo "$response" | grep "^data: " | sed 's/^data: //' | head -1)
    else
        json_response="$response"
    fi
    
    # Check if response is valid JSON and has content
    if echo "$json_response" | jq empty >/dev/null 2>&1; then
        if echo "$json_response" | jq -e '.result.content' >/dev/null 2>&1; then
            log_success "✅ Tool '$tool_name' executed successfully"
            
            if [ "$VERBOSE" = true ]; then
                echo "$json_response" | jq '.result.content' 2>/dev/null || echo "$json_response"
            fi
            return 0
        elif echo "$json_response" | jq -e '.error' >/dev/null 2>&1; then
            local error_msg
            error_msg=$(echo "$json_response" | jq -r '.error.message // "Unknown error"' 2>/dev/null)
            log_error "❌ Tool '$tool_name' failed: $error_msg"
            return 1
        else
            log_warning "⚠️  Tool '$tool_name' returned unexpected response format"
            return 1
        fi
    else
        log_error "❌ Tool '$tool_name' returned invalid JSON"
        return 1
    fi
}

# Test all tools from test-tools.json
test_all_tools() {
    local endpoint="$1"
    local session_id="$2"
    local test_tools_file="$SCRIPT_DIR/test-tools.json"
    
    if [ ! -f "$test_tools_file" ]; then
        log_error "❌ test-tools.json not found at: $test_tools_file"
        return 1
    fi
    
    log_info "=================== TESTING ALL TOOLS ==================="
    log_info "Getting tools list from MCP server..."
    
    # Get tools list from server
    local tools_request='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
    local tools_response
    
    if [ -n "$session_id" ]; then
        tools_response=$(curl -s -X POST "$endpoint" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -H "Mcp-Session-Id: $session_id" \
            -d "$tools_request" \
            --max-time 10 \
            --connect-timeout 5)
    else
        tools_response=$(curl -s -X POST "$endpoint" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -d "$tools_request" \
            --max-time 10 \
            --connect-timeout 5)
    fi
    
    # Extract JSON from SSE format
    local json_response
    if echo "$tools_response" | grep -q "^data: "; then
        json_response=$(echo "$tools_response" | grep "^data: " | sed 's/^data: //' | head -1)
    else
        json_response="$tools_response"
    fi
    
    # Parse server response
    if ! echo "$json_response" | jq empty >/dev/null 2>&1; then
        log_error "❌ Failed to get tools list from server"
        return 1
    fi
    
    if ! echo "$json_response" | jq -e '.result.tools' >/dev/null 2>&1; then
        log_error "❌ Server did not return tools list"
        return 1
    fi
    
    # Get server tools and filter those with test configurations
    local server_tools
    server_tools=$(echo "$json_response" | jq -r '.result.tools[].name' 2>/dev/null)
    
    local testable_tools=""
    local skipped_tools=""
    
    for tool_name in $server_tools; do
        if jq -e --arg name "$tool_name" '.tools[$name]' "$test_tools_file" >/dev/null 2>&1; then
            testable_tools="$testable_tools $tool_name"
        else
            skipped_tools="$skipped_tools $tool_name"
        fi
    done
    
    if [ -z "$testable_tools" ]; then
        log_error "❌ No server tools have test configurations in test-tools.json"
        return 1
    fi
    
    if [ -n "$skipped_tools" ]; then
        log_info "⚠️  Skipping tools without test configs:$skipped_tools"
        echo ""
    fi
    
    local total_tools=0
    local passed_tools=0
    local failed_tools=0
    
    for tool_name in $testable_tools; do
        total_tools=$((total_tools + 1))
        echo ""
        log_info "Tool Test $total_tools: $tool_name"
        
        if test_individual_tool "$endpoint" "$tool_name" "$session_id"; then
            passed_tools=$((passed_tools + 1))
        else
            failed_tools=$((failed_tools + 1))
        fi
    done
    
    echo ""
    log_info "=================== TOOLS TEST SUMMARY ==================="
    log_info "Total tools tested: $total_tools"
    log_success "Passed: $passed_tools"
    if [ "$failed_tools" -gt 0 ]; then
        log_error "Failed: $failed_tools"
    else
        log_info "Failed: $failed_tools"
    fi
    
    if [ "$failed_tools" -eq 0 ]; then
        log_success "🎉 All tools tests passed!"
        return 0
    else
        log_error "❌ Some tools tests failed"
        return 1
    fi
}

# Test MCP endpoint
test_mcp_endpoint() {
    local endpoint="$1"
    
    log_info "Testing MCP endpoint: $endpoint"
    
    # Test 1: Initialize session
    log_info "Step 1: Initialize MCP session"
    local init_request='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}'
    
    local init_response
    init_response=$(curl -s -i -X POST "$endpoint" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d "$init_request" \
        --max-time 10 \
        --connect-timeout 5) || {
        log_error "Failed to connect to endpoint: $endpoint"
        return 1
    }
    
    # Extract session ID from response headers
    local session_id
    session_id=$(echo "$init_response" | grep -i "mcp-session-id:" | head -1 | sed 's/.*mcp-session-id: *\([^ \r]*\).*/\1/' | tr -d '\r')
    
    if [ -n "$session_id" ]; then
        log_info "Session initialized with ID: $session_id"
        
        # Send initialized notification to complete the MCP handshake
        curl -s -X POST "$endpoint" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -H "Mcp-Session-Id: $session_id" \
            -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null
    else
        log_info "No session ID returned, proceeding without session management"
    fi
    
    # Test 2: Tools list with session
    log_info "Step 2: Test tools/list method"
    local response
    if [ -n "$session_id" ]; then
        response=$(curl -s -X POST "$endpoint" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -H "Mcp-Session-Id: $session_id" \
            -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
            --max-time 10 \
            --connect-timeout 5)
    else
        response=$(curl -s -X POST "$endpoint" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json, text/event-stream" \
            -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
            --max-time 10 \
            --connect-timeout 5)
    fi
    
    if [ "$VERBOSE" = true ]; then
        echo "Response: $response"
    fi
    
    # Extract JSON from SSE format or use as-is if it's plain JSON
    local json_response
    if echo "$response" | grep -q "^data: "; then
        json_response=$(echo "$response" | grep "^data: " | sed 's/^data: //' | head -1)
    else
        json_response="$response"
    fi
    
    # Check if response is valid JSON
    if ! echo "$json_response" | python3 -m json.tool >/dev/null 2>&1; then
        log_error "Invalid JSON response from endpoint"
        echo "Response: $response"
        return 1
    fi
    
    # Check if response has jsonrpc field
    if ! echo "$json_response" | grep -q '"jsonrpc"'; then
        log_error "Response missing jsonrpc field"
        return 1
    fi
    
    # Check if response has result field (successful response)
    if echo "$json_response" | grep -q '"result"'; then
        local tool_count
        tool_count=$(echo "$json_response" | python3 -c "
import sys, json
try:
    content = sys.stdin.read().strip()
    if not content:
        print('0')
        sys.exit(0)
    data = json.loads(content)
    tools = data.get('result', {}).get('tools', [])
    print(len(tools))
except Exception as e:
    print('0')
" 2>/dev/null || echo "0")
        
        if [ "$TOOLS_TEST" = true ] || [ "$VERBOSE" = true ]; then
            echo "$json_response" | python3 -c "
import sys, json
try:
    content = sys.stdin.read().strip()
    if content:
        data = json.loads(content)
        tools = data.get('result', {}).get('tools', [])
        for t in tools:
            name = t.get('name')
            if name:
                print(f'  - {name}')
except:
    pass
"
        fi
        log_success "MCP endpoint responded successfully with $tool_count tools"
        return 0
    elif echo "$json_response" | grep -q '"error"'; then
        local error_msg
        error_msg=$(echo "$json_response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    error = data.get('error', {})
    print(f\"Code: {error.get('code', 'unknown')}, Message: {error.get('message', 'unknown')}\")
except:
    print('Unknown error format')
" 2>/dev/null || echo "Unknown error")
        
        log_error "MCP endpoint returned error: $error_msg"
        return 1
    else
        log_error "Unexpected response format"
        return 1
    fi
}

# Main execution

# First run basic endpoint test to get session
log_info "Testing MCP endpoint: $ENDPOINT"
session_id=""

# Test 1: Initialize session
log_info "Step 1: Initialize MCP session"
init_request='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}'

init_response=$(curl -s -i -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d "$init_request" \
    --max-time 10 \
    --connect-timeout 5) || {
    log_error "Failed to connect to endpoint: $ENDPOINT"
    exit 1
}

# Extract session ID from response headers
session_id=$(echo "$init_response" | grep -i "mcp-session-id:" | head -1 | sed 's/.*mcp-session-id: *\([^ \r]*\).*/\1/' | tr -d '\r')

if [ -n "$session_id" ]; then
    log_info "Session initialized with ID: $session_id"
    
    # Send initialized notification to complete the MCP handshake
    curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -H "Mcp-Session-Id: $session_id" \
        -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null
else
    log_info "No session ID returned, proceeding without session management"
fi

# Test 2: Tools list
log_info "Step 2: Test tools/list method"
tools_request='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

if [ -n "$session_id" ]; then
    tools_response=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -H "Mcp-Session-Id: $session_id" \
        -d "$tools_request" \
        --max-time 10 \
        --connect-timeout 5)
else
    tools_response=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d "$tools_request" \
        --max-time 10 \
        --connect-timeout 5)
fi

if [ "$VERBOSE" = true ]; then
    echo "Response: $tools_response"
fi

# Extract JSON from SSE format or use as-is if it's plain JSON
json_response=""
if echo "$tools_response" | grep -q "^data: "; then
    json_response=$(echo "$tools_response" | grep "^data: " | sed 's/^data: //' | head -1)
else
    json_response="$tools_response"
fi

# Check if response is valid JSON
if ! echo "$json_response" | jq empty >/dev/null 2>&1; then
    log_error "Invalid JSON response from endpoint"
    echo "Response: $tools_response"
    exit 1
fi

# Check if response has result field (successful response)
if echo "$json_response" | jq -e '.result' >/dev/null 2>&1; then
    tool_count=$(echo "$json_response" | jq -r '.result.tools | length' 2>/dev/null || echo "0")
    
    if [ "$VERBOSE" = true ]; then
        echo "$json_response" | jq -r '.result.tools[]? | "  - " + .name' 2>/dev/null
    fi
    
    log_success "MCP endpoint responded successfully with $tool_count tools"
elif echo "$json_response" | jq -e '.error' >/dev/null 2>&1; then
    error_msg=$(echo "$json_response" | jq -r '.error.message // "Unknown error"' 2>/dev/null)
    log_error "MCP endpoint returned error: $error_msg"
    exit 1
else
    log_error "Unexpected response format"
    exit 1
fi

# Now run the requested test mode
if [ -n "$SPECIFIC_TOOL" ]; then
    echo ""
    log_info "=================== TESTING SPECIFIC TOOL ==================="
    if test_individual_tool "$ENDPOINT" "$SPECIFIC_TOOL" "$session_id"; then
        log_success "MCP specific tool test completed successfully"
    else
        log_error "MCP specific tool test failed"
        exit 1
    fi
elif [ "$TOOLS_TEST" = true ]; then
    echo ""
    if test_all_tools "$ENDPOINT" "$session_id"; then
        log_success "MCP all tools test completed successfully"
    else
        log_error "MCP tools test failed"
        exit 1
    fi
else
    log_success "MCP endpoint test completed successfully"
fi