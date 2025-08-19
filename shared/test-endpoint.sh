#!/bin/bash
# Simple MCP endpoint test script
set -e

VERBOSE=false
TOOLS_TEST=false
ENDPOINT=""

usage() {
    echo "Usage: $0 [-t] [-v] <endpoint>"
    echo ""
    echo "Options:"
    echo "  -t            Run tools test (test tools/list method)"
    echo "  -v            Verbose output"
    echo ""
    echo "Arguments:"
    echo "  endpoint      MCP endpoint URL to test (required)"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tools)
            TOOLS_TEST=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
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

# Check if endpoint is provided
if [[ -z "$ENDPOINT" ]]; then
    echo "Error: endpoint URL is required"
    usage
    exit 1
fi

log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

log_success() {
    echo "[SUCCESS] $1"
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

test_mcp_endpoint "$ENDPOINT"

log_success "MCP endpoint test completed successfully"