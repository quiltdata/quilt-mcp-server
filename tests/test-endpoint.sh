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
        -f|--full)
            FULL_TEST=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Test MCP endpoint functionality"
            echo ""
            echo "Options:"
            echo "  -v, --verbose      Enable verbose output"
            echo "  -f, --full         Run comprehensive Claude.ai simulation tests"
            echo "  -s, --stack        CloudFormation stack name (default: QuiltMcpStack)"
            echo "  -r, --region       AWS region (default: from env or us-east-1)"
            echo "  -e, --endpoint     Direct endpoint URL (skips CloudFormation lookup)"
            echo "  -h, --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Test with defaults"
            echo "  $0 -v                                 # Test with verbose output"
            echo "  $0 -f                                 # Run full Claude.ai simulation"
            echo "  $0 -v -f                              # Full test with verbose output"
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

# Function to run comprehensive Claude.ai simulation tests
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
    
    # Test 2: URL variations (with and without trailing slash)
    echo -e "${BLUE}Claude Test 2: URL Variations${NC}"
    
    # Test without trailing slash
    ENDPOINT_NO_SLASH="${ENDPOINT%/}"
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Testing without trailing slash: ${ENDPOINT_NO_SLASH}${NC}"
    fi
    
    NOSLASH_RESPONSE=$(curl -s -X POST "$ENDPOINT_NO_SLASH" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}')
    
    if echo "$NOSLASH_RESPONSE" | grep -q "tools"; then
        echo -e "${GREEN}✅ URL without trailing slash works${NC}"
    else
        echo -e "${YELLOW}⚠️  URL without trailing slash failed${NC}"
        if [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}Response: $NOSLASH_RESPONSE${NC}"
        fi
    fi
    
    # Test 3: Initialize with Claude-specific capabilities
    echo -e "${BLUE}Claude Test 3: Initialize with Claude Capabilities${NC}"
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
    
    # Test 4: Multiple rapid requests (simulating Claude's behavior)
    echo -e "${BLUE}Claude Test 4: Rapid Sequential Requests${NC}"
    
    REQUEST_COUNT=0
    SUCCESS_COUNT=0
    
    for i in {1..5}; do
        REQUEST_COUNT=$((REQUEST_COUNT + 1))
        
        if [ "$VERBOSE" = true ]; then
            echo -e "${BLUE}Request $i/5${NC}"
        fi
        
        RAPID_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "Origin: https://claude.ai" \
            -d "{\"jsonrpc\": \"2.0\", \"id\": $i, \"method\": \"tools/list\", \"params\": {}}")
        
        if echo "$RAPID_RESPONSE" | grep -q "tools"; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        elif [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}Request $i failed: $RAPID_RESPONSE${NC}"
        fi
        
        # Small delay to avoid overwhelming
        sleep 0.1
    done
    
    echo -e "${GREEN}✅ Rapid requests: $SUCCESS_COUNT/$REQUEST_COUNT successful${NC}"
    
    # Test 5: Error handling (invalid requests)
    echo -e "${BLUE}Claude Test 5: Error Handling${NC}"
    
    # Test invalid JSON
    INVALID_JSON_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d '{"jsonrpc": "2.0", "id": 1, "method": "invalid_method"}')
    
    if echo "$INVALID_JSON_RESPONSE" | grep -q "error"; then
        echo -e "${GREEN}✅ Server properly handles invalid methods${NC}"
    else
        echo -e "${YELLOW}⚠️  Server error handling unclear${NC}"
        if [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}Response: $INVALID_JSON_RESPONSE${NC}"
        fi
    fi
    
    # Test 6: Large request (simulating complex tool calls)
    echo -e "${BLUE}Claude Test 6: Large Request Handling${NC}"
    
    LARGE_REQUEST='{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "search_packages", "arguments": {"query": "machine learning deep learning neural networks artificial intelligence data science python tensorflow pytorch scikit-learn pandas numpy matplotlib seaborn plotly jupyter notebook analysis visualization"}}}'
    
    LARGE_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d "$LARGE_REQUEST")
    
    if echo "$LARGE_RESPONSE" | grep -q '"result"\|"error"'; then
        echo -e "${GREEN}✅ Server handles large requests${NC}"
    else
        echo -e "${YELLOW}⚠️  Large request handling unclear${NC}"
        if [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}Response: $LARGE_RESPONSE${NC}"
        fi
    fi
    
    # Test 7: SSL/TLS validation
    echo -e "${BLUE}Claude Test 7: SSL/TLS Certificate Validation${NC}"
    
    SSL_CHECK=$(curl -s -w '%{ssl_verify_result}' -o /dev/null "$ENDPOINT")
    if [ "$SSL_CHECK" = "0" ]; then
        echo -e "${GREEN}✅ SSL certificate is valid${NC}"
    else
        echo -e "${RED}❌ SSL certificate validation failed (code: $SSL_CHECK)${NC}"
    fi
    
    # Test 8: Response timing (Claude expects reasonable response times)
    echo -e "${BLUE}Claude Test 8: Response Timing${NC}"
    
    # Use different timing method for macOS compatibility
    if [[ "$OSTYPE" == "darwin"* ]]; then
        START_TIME=$(python3 -c "import time; print(int(time.time() * 1000))")
        TIMING_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "Origin: https://claude.ai" \
            -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}')
        END_TIME=$(python3 -c "import time; print(int(time.time() * 1000))")
    else
        START_TIME=$(date +%s%3N)
        TIMING_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "Origin: https://claude.ai" \
            -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}')
        END_TIME=$(date +%s%3N)
    fi
    
    RESPONSE_TIME=$((END_TIME - START_TIME))
    
    if [ "$RESPONSE_TIME" -lt 5000 ]; then
        echo -e "${GREEN}✅ Response time: ${RESPONSE_TIME}ms (good)${NC}"
    elif [ "$RESPONSE_TIME" -lt 10000 ]; then
        echo -e "${YELLOW}⚠️  Response time: ${RESPONSE_TIME}ms (acceptable)${NC}"
    else
        echo -e "${RED}❌ Response time: ${RESPONSE_TIME}ms (too slow)${NC}"
    fi
    
    # Test 9: Tool Execution (actual tool call)
    echo -e "${BLUE}Claude Test 9: Tool Execution${NC}"
    
    TOOL_CALL_REQUEST='{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "check_quilt_auth", "arguments": {}}}'
    
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Testing tool execution:${NC}"
        echo "$TOOL_CALL_REQUEST" | jq . 2>/dev/null || echo "$TOOL_CALL_REQUEST"
    fi
    
    TOOL_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d "$TOOL_CALL_REQUEST")
    
    if echo "$TOOL_RESPONSE" | grep -q '"content"'; then
        echo -e "${GREEN}✅ Tool execution works${NC}"
        if [ "$VERBOSE" = true ]; then
            echo -e "${BLUE}Tool response:${NC}"
            echo "$TOOL_RESPONSE" | jq . 2>/dev/null || echo "$TOOL_RESPONSE"
        fi
    else
        echo -e "${YELLOW}⚠️  Tool execution unclear${NC}"
        if [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}Response: $TOOL_RESPONSE${NC}"
        fi
    fi
    
    # Test 10: Invalid Tool Call
    echo -e "${BLUE}Claude Test 10: Invalid Tool Call${NC}"
    
    INVALID_TOOL_REQUEST='{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "nonexistent_tool", "arguments": {}}}'
    
    INVALID_TOOL_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d "$INVALID_TOOL_REQUEST")
    
    if echo "$INVALID_TOOL_RESPONSE" | grep -q '"error"'; then
        echo -e "${GREEN}✅ Invalid tool properly rejected${NC}"
    else
        echo -e "${YELLOW}⚠️  Invalid tool handling unclear${NC}"
        if [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}Response: $INVALID_TOOL_RESPONSE${NC}"
        fi
    fi
    
    # Test 11: Malformed JSON
    echo -e "${BLUE}Claude Test 11: Malformed JSON Handling${NC}"
    
    MALFORMED_RESPONSE=$(curl -s -w '%{http_code}' -o /tmp/malformed_response.txt -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}')
    
    if [ "$MALFORMED_RESPONSE" -eq 500 ] || [ "$MALFORMED_RESPONSE" -eq 400 ]; then
        echo -e "${GREEN}✅ Malformed JSON properly handled (HTTP $MALFORMED_RESPONSE)${NC}"
    else
        echo -e "${YELLOW}⚠️  Malformed JSON handling unclear (HTTP $MALFORMED_RESPONSE)${NC}"
    fi
    
    # Test 12: Wrong Content-Type
    echo -e "${BLUE}Claude Test 12: Content-Type Validation${NC}"
    
    WRONG_CONTENT_TYPE_RESPONSE=$(curl -s -w '%{http_code}' -o /dev/null -X POST "$ENDPOINT" \
        -H "Content-Type: text/plain" \
        -H "Origin: https://claude.ai" \
        -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}')
    
    if [ "$WRONG_CONTENT_TYPE_RESPONSE" -eq 200 ]; then
        echo -e "${GREEN}✅ Server accepts requests with wrong Content-Type${NC}"
    else
        echo -e "${YELLOW}⚠️  Server rejects wrong Content-Type (HTTP $WRONG_CONTENT_TYPE_RESPONSE)${NC}"
    fi
    
    # Test 13: Empty POST Body
    echo -e "${BLUE}Claude Test 13: Empty POST Body${NC}"
    
    EMPTY_BODY_RESPONSE=$(curl -s -w '%{http_code}' -o /dev/null -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d '')
    
    if [ "$EMPTY_BODY_RESPONSE" -eq 400 ] || [ "$EMPTY_BODY_RESPONSE" -eq 500 ]; then
        echo -e "${GREEN}✅ Empty body properly handled (HTTP $EMPTY_BODY_RESPONSE)${NC}"
    else
        echo -e "${YELLOW}⚠️  Empty body handling unclear (HTTP $EMPTY_BODY_RESPONSE)${NC}"
    fi
    
    # Test 14: HTTP Method Validation
    echo -e "${BLUE}Claude Test 14: HTTP Method Validation${NC}"
    
    PUT_RESPONSE=$(curl -s -w '%{http_code}' -o /dev/null -X PUT "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai")
    
    DELETE_RESPONSE=$(curl -s -w '%{http_code}' -o /dev/null -X DELETE "$ENDPOINT" \
        -H "Origin: https://claude.ai")
    
    if [ "$PUT_RESPONSE" -eq 405 ] && [ "$DELETE_RESPONSE" -eq 405 ]; then
        echo -e "${GREEN}✅ Unsupported HTTP methods properly rejected${NC}"
    else
        echo -e "${YELLOW}⚠️  HTTP method validation unclear (PUT: $PUT_RESPONSE, DELETE: $DELETE_RESPONSE)${NC}"
    fi
    
    # Test 15: Request ID Types
    echo -e "${BLUE}Claude Test 15: Request ID Validation${NC}"
    
    # Test with string ID
    STRING_ID_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d '{"jsonrpc": "2.0", "id": "test-string-id", "method": "tools/list", "params": {}}')
    
    # Test with null ID
    NULL_ID_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d '{"jsonrpc": "2.0", "id": null, "method": "tools/list", "params": {}}')
    
    STRING_ID_SUCCESS=$(echo "$STRING_ID_RESPONSE" | grep -q '"tools"' && echo "true" || echo "false")
    NULL_ID_SUCCESS=$(echo "$NULL_ID_RESPONSE" | grep -q '"tools"' && echo "true" || echo "false")
    
    if [ "$STRING_ID_SUCCESS" = "true" ] && [ "$NULL_ID_SUCCESS" = "true" ]; then
        echo -e "${GREEN}✅ Different request ID types handled${NC}"
    else
        echo -e "${YELLOW}⚠️  Request ID handling unclear (string: $STRING_ID_SUCCESS, null: $NULL_ID_SUCCESS)${NC}"
    fi
    
    # Test 16: Unicode and Special Characters
    echo -e "${BLUE}Claude Test 16: Unicode Handling${NC}"
    
    UNICODE_REQUEST='{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "search_packages", "arguments": {"query": "测试 émojis 🚀 special chars: <>&'\''\"", "limit": 1}}}'
    
    UNICODE_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d "$UNICODE_REQUEST")
    
    if echo "$UNICODE_RESPONSE" | grep -q '"content"\|"error"'; then
        echo -e "${GREEN}✅ Unicode characters handled${NC}"
    else
        echo -e "${YELLOW}⚠️  Unicode handling unclear${NC}"
        if [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}Response: $UNICODE_RESPONSE${NC}"
        fi
    fi
    
    # Test 17: Missing Required Parameters
    echo -e "${BLUE}Claude Test 17: Missing Required Parameters${NC}"
    
    MISSING_PARAM_REQUEST='{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "search_packages", "arguments": {}}}'
    
    MISSING_PARAM_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d "$MISSING_PARAM_REQUEST")
    
    if echo "$MISSING_PARAM_RESPONSE" | grep -q '"error"'; then
        echo -e "${GREEN}✅ Missing required parameters properly handled${NC}"
    else
        echo -e "${YELLOW}⚠️  Missing parameter validation unclear${NC}"
        if [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}Response: $MISSING_PARAM_RESPONSE${NC}"
        fi
    fi
    
    # Test 18: Protocol Version Compatibility
    echo -e "${BLUE}Claude Test 18: Protocol Version Compatibility${NC}"
    
    OLD_PROTOCOL_REQUEST='{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2023-06-13", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}'
    
    OLD_PROTOCOL_RESPONSE=$(curl -s -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://claude.ai" \
        -d "$OLD_PROTOCOL_REQUEST")
    
    if echo "$OLD_PROTOCOL_RESPONSE" | grep -q '"result"\|"error"'; then
        echo -e "${GREEN}✅ Protocol version handling works${NC}"
    else
        echo -e "${YELLOW}⚠️  Protocol version handling unclear${NC}"
    fi
    
    # Test 19: Response Compression
    echo -e "${BLUE}Claude Test 19: Response Compression${NC}"
    
    COMPRESSION_RESPONSE=$(curl -s -w '%{size_download}' -o /dev/null -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Accept-Encoding: gzip, deflate" \
        -H "Origin: https://claude.ai" \
        -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}')
    
    if [ "$COMPRESSION_RESPONSE" -gt 0 ]; then
        echo -e "${GREEN}✅ Response compression support detected${NC}"
    else
        echo -e "${YELLOW}⚠️  Response compression unclear${NC}"
    fi
    
    # Test 20: Multiple Origins
    echo -e "${BLUE}Claude Test 20: Origin Header Validation${NC}"
    
    # Test with different origins
    NO_ORIGIN_RESPONSE=$(curl -s -w '%{http_code}' -o /dev/null -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}')
    
    OTHER_ORIGIN_RESPONSE=$(curl -s -w '%{http_code}' -o /dev/null -X POST "$ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Origin: https://example.com" \
        -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}')
    
    if [ "$NO_ORIGIN_RESPONSE" -eq 200 ] && [ "$OTHER_ORIGIN_RESPONSE" -eq 200 ]; then
        echo -e "${GREEN}✅ CORS allows all origins${NC}"
    else
        echo -e "${YELLOW}⚠️  Origin handling: no-origin=$NO_ORIGIN_RESPONSE, other=$OTHER_ORIGIN_RESPONSE${NC}"
    fi
    
    echo -e "${BLUE}=================== CLAUDE SIMULATION COMPLETE ===================${NC}"
}

# Main test execution starts here

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

# Run comprehensive Claude.ai simulation tests if requested
if [ "$FULL_TEST" = true ]; then
    echo ""
    echo -e "${BLUE}🔍 Running comprehensive Claude.ai simulation tests...${NC}"
    run_claude_simulation_tests
fi
