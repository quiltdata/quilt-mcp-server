#!/bin/bash

# MCP Authentication Test Script
# This script tests the complete MCP authentication flow

set -e

BASE_URL="https://demo.quiltdata.com/mcp/"
SESSION_ID=""
REQUEST_ID=1

echo "🧪 Starting MCP Authentication Test"
echo "Target URL: $BASE_URL"

# Function to make MCP request
make_request() {
    local method="$1"
    local params="$2"
    local request_id="$3"
    
    echo ""
    echo "=== Making request: $method ==="
    echo "Request ID: $request_id"
    
    local headers=(
        "Content-Type: application/json"
        "Accept: application/json, text/event-stream"
        "MCP-Protocol-Version: 2025-06-18"
    )
    
    if [ -n "$SESSION_ID" ]; then
        headers+=("mcp-session-id: $SESSION_ID")
        echo "Using session ID: $SESSION_ID"
    fi
    
    echo "Headers: ${headers[*]}"
    echo "Payload: $params"
    
    local response
    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "${headers[0]}" \
        -H "${headers[1]}" \
        -H "${headers[2]}" \
        ${SESSION_ID:+ -H "mcp-session-id: $SESSION_ID"} \
        -d "$params" \
        "$BASE_URL")
    
    local http_code
    http_code=$(echo "$response" | tail -n1)
    local body
    body=$(echo "$response" | head -n -1)
    
    echo "HTTP Status: $http_code"
    echo "Response: $body"
    
    # Extract session ID from headers if this is initialize
    if [ "$method" = "initialize" ]; then
        SESSION_ID=$(curl -s -I \
            -X POST \
            -H "${headers[0]}" \
            -H "${headers[1]}" \
            -H "${headers[2]}" \
            -d "$params" \
            "$BASE_URL" | grep -i "mcp-session-id:" | cut -d' ' -f2 | tr -d '\r')
        
        if [ -n "$SESSION_ID" ]; then
            echo "✅ Extracted session ID: $SESSION_ID"
        else
            echo "❌ Failed to extract session ID"
        fi
    fi
    
    echo "$body"
}

# Step 1: Initialize
echo ""
echo "=== STEP 1: INITIALIZE ==="
INIT_PARAMS='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0"}}}'
INIT_RESPONSE=$(make_request "initialize" "$INIT_PARAMS" 1)

echo "Initialize response: $INIT_RESPONSE"

# Check if initialization was successful
if echo "$INIT_RESPONSE" | grep -q '"result"'; then
    echo "✅ MCP initialization successful"
else
    echo "❌ MCP initialization failed"
    exit 1
fi

# Step 2: Wait for initialization to complete
echo ""
echo "=== STEP 2: WAITING FOR INITIALIZATION ==="
echo "⏳ Waiting 3 seconds for initialization to complete..."
sleep 3

# Step 3: List tools
echo ""
echo "=== STEP 3: LIST TOOLS ==="
TOOLS_PARAMS='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
TOOLS_RESPONSE=$(make_request "tools/list" "$TOOLS_PARAMS" 2)

echo "Tools list response: $TOOLS_RESPONSE"

# Check if tools list was successful
if echo "$TOOLS_RESPONSE" | grep -q '"result"'; then
    echo "✅ Tools list successful"
else
    echo "❌ Tools list failed"
    echo "Error details: $TOOLS_RESPONSE"
fi

# Step 4: Test authentication
echo ""
echo "=== STEP 4: TEST AUTH STATUS ==="
AUTH_PARAMS='{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"auth_status","arguments":{"random_string":"test"}}}'
AUTH_RESPONSE=$(make_request "tools/call" "$AUTH_PARAMS" 3)

echo "Auth status response: $AUTH_RESPONSE"

# Check if auth status was successful
if echo "$AUTH_RESPONSE" | grep -q '"result"'; then
    echo "✅ Auth status successful"
    
    # Extract and display auth information
    AUTH_STATUS=$(echo "$AUTH_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    AUTH_METHOD=$(echo "$AUTH_RESPONSE" | grep -o '"auth_method":"[^"]*"' | cut -d'"' -f4)
    CATALOG_NAME=$(echo "$AUTH_RESPONSE" | grep -o '"catalog_name":"[^"]*"' | cut -d'"' -f4)
    
    echo "  Status: $AUTH_STATUS"
    echo "  Method: $AUTH_METHOD"
    echo "  Catalog: $CATALOG_NAME"
    
    if [ "$AUTH_STATUS" = "authenticated" ]; then
        echo "🎉 Authentication test PASSED!"
        exit 0
    else
        echo "⚠️  Authentication test PARTIAL - not fully authenticated"
        exit 1
    fi
else
    echo "❌ Auth status failed"
    echo "Error details: $AUTH_RESPONSE"
    exit 1
fi
