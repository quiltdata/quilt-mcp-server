#!/bin/bash
# Simple MCP endpoint test script
set -e

VERBOSE=false
LOCAL_TEST=false
ENDPOINT="http://127.0.0.1:8000/mcp"

usage() {
    echo "Usage: $0 [-l] [-t] [-v] [endpoint]"
    echo ""
    echo "Options:"
    echo "  -l            Test local endpoint (http://127.0.0.1:8000/mcp)"
    echo "  -t            Run tools test (test tools/list method)"
    echo "  -v            Verbose output"
    echo ""
    echo "Arguments:"
    echo "  endpoint      Custom endpoint URL"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -l|--local)
            LOCAL_TEST=true
            shift
            ;;
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
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

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
    
    # Test tools/list method
    local response
    response=$(curl -s -X POST "$endpoint" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
        --max-time 10 \
        --connect-timeout 5) || {
        log_error "Failed to connect to endpoint: $endpoint"
        return 1
    }
    
    if [ "$VERBOSE" = true ]; then
        echo "Response: $response"
    fi
    
    # Check if response is valid JSON
    if ! echo "$response" | python3 -m json.tool >/dev/null 2>&1; then
        log_error "Invalid JSON response from endpoint"
        echo "Response: $response"
        return 1
    fi
    
    # Check if response has jsonrpc field
    if ! echo "$response" | grep -q '"jsonrpc"'; then
        log_error "Response missing jsonrpc field"
        return 1
    fi
    
    # Check if response has result field (successful response)
    if echo "$response" | grep -q '"result"'; then
        local tool_count
        tool_count=$(echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tools = data.get('result', {}).get('tools', [])
    print(len(tools))
except:
    print('0')
" 2>/dev/null || echo "0")
        
        if [ "$TOOLS_TEST" = true ] || [ "$VERBOSE" = true ]; then
            echo "$response" | python3 - <<'PY'
import sys, json
data=json.load(sys.stdin)
tools=data.get('result',{}).get('tools',[])
for t in tools:
    name=t.get('name')
    if name:
        print(f"  - {name}")
PY
        fi
        log_success "MCP endpoint responded successfully with $tool_count tools"
        return 0
    elif echo "$response" | grep -q '"error"'; then
        local error_msg
        error_msg=$(echo "$response" | python3 -c "
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

# Start local server if testing locally
start_local_server() {
    log_info "Starting local MCP server..."
    
    # Check if server is already running
    if curl -s -H "Accept: application/json, text/event-stream" "$ENDPOINT" >/dev/null 2>&1; then
        log_info "Local server already running"
        return 0
    fi
    
    # Start server in background with HTTP-capable transport for curl tests
    cd src/app
    export PYTHONPATH="$(pwd)/src"
    uv run python main.py --transport streamable-http &
    SERVER_PID=$!
    
    # Wait for server to start
    local attempts=0
    while [ $attempts -lt 30 ]; do
        if curl -s -H "Accept: application/json, text/event-stream" "$ENDPOINT" >/dev/null 2>&1; then
            log_success "Local server started (PID: $SERVER_PID)"
            return 0
        fi
        sleep 1
        attempts=$((attempts + 1))
    done
    
    log_error "Local server failed to start within 30 seconds"
    kill $SERVER_PID 2>/dev/null || true
    return 1
}

cleanup() {
    if [ -n "$SERVER_PID" ]; then
        log_info "Stopping local server (PID: $SERVER_PID)"
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Main execution
if [ "$LOCAL_TEST" = true ]; then
    start_local_server
fi

test_mcp_endpoint "$ENDPOINT"

log_success "MCP endpoint test completed successfully"