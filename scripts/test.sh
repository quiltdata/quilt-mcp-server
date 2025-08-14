#!/bin/bash
# Test the deployed Quilt MCP Server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default values
VERBOSE=false

usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Test the deployed Quilt MCP Server"
    echo ""
    echo "Options:"
    echo "  -v, --verbose        Show detailed output"
    echo "  -h, --help           Show this help"
    echo ""
    echo "Tests performed:"
    echo "  - Endpoint accessibility"
    echo "  - MCP tools/list method"
    echo "  - Health check"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Check dependencies
check_dependencies curl jq

# Load configuration
load_config

log_info "🧪 Testing Quilt MCP Server"
log_info "Endpoint: $MCP_ENDPOINT"
echo ""

# Test 1: Basic connectivity
log_info "Test 1: Basic connectivity"
if curl -s -f "$MCP_ENDPOINT" >/dev/null 2>&1; then
    log_success "✅ Endpoint is accessible"
else
    log_error "❌ Endpoint not accessible"
    log_error "Check if deployment is complete and load balancer is healthy"
    exit 1
fi

# Test 2: MCP tools/list
log_info "Test 2: MCP tools/list method"
RESPONSE=$(curl -s -X POST "$MCP_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}')

if [ $? -eq 0 ] && echo "$RESPONSE" | jq -e '.result.tools' >/dev/null 2>&1; then
    TOOL_COUNT=$(echo "$RESPONSE" | jq '.result.tools | length')
    log_success "✅ MCP tools/list returned $TOOL_COUNT tools"
    
    if [ "$VERBOSE" = true ]; then
        log_info "Available tools:"
        echo "$RESPONSE" | jq -r '.result.tools[].name' | sed 's/^/  - /'
    fi
else
    log_error "❌ MCP tools/list failed"
    if [ "$VERBOSE" = true ]; then
        log_error "Response: $RESPONSE"
    fi
    exit 1
fi

# Test 3: Sample tool call
log_info "Test 3: Sample tool call (auth_status)"
RESPONSE=$(curl -s -X POST "$MCP_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"auth_status","arguments":{}}}')

if [ $? -eq 0 ] && echo "$RESPONSE" | jq -e '.result' >/dev/null 2>&1; then
    log_success "✅ Sample tool call succeeded"
    
    if [ "$VERBOSE" = true ]; then
        log_info "Response:"
        echo "$RESPONSE" | jq '.result'
    fi
else
    log_warning "⚠️  Sample tool call failed (may be expected without auth)"
    if [ "$VERBOSE" = true ]; then
        log_info "Response: $RESPONSE"
    fi
fi

# Test 4: ECS service health
log_info "Test 4: ECS service health"
SERVICE_STATUS=$(aws ecs describe-services \
    --cluster "$CLUSTER_NAME" \
    --services "$SERVICE_NAME" \
    --region "$REGION" \
    --query 'services[0].status' \
    --output text)

RUNNING_COUNT=$(aws ecs describe-services \
    --cluster "$CLUSTER_NAME" \
    --services "$SERVICE_NAME" \
    --region "$REGION" \
    --query 'services[0].runningCount' \
    --output text)

DESIRED_COUNT=$(aws ecs describe-services \
    --cluster "$CLUSTER_NAME" \
    --services "$SERVICE_NAME" \
    --region "$REGION" \
    --query 'services[0].desiredCount' \
    --output text)

if [ "$SERVICE_STATUS" = "ACTIVE" ] && [ "$RUNNING_COUNT" = "$DESIRED_COUNT" ]; then
    log_success "✅ ECS service is healthy ($RUNNING_COUNT/$DESIRED_COUNT tasks running)"
else
    log_warning "⚠️  ECS service status: $SERVICE_STATUS ($RUNNING_COUNT/$DESIRED_COUNT tasks running)"
fi

echo ""
log_success "🎉 Testing completed!"
log_info "💡 Use './scripts/logs.sh -f' to view live logs"
log_info "💡 Use './scripts/logs.sh -t all' to view all log types"