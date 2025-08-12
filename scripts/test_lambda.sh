#!/bin/bash

# Test Lambda function with various MCP events
# Usage: ./test_lambda.sh [function-name] [region]

set -e

# Load common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Set AWS profile for deployment
export AWS_PROFILE=open

# Default values
FUNCTION_NAME="${1:-QuiltMcpStack-QuiltMcpFunctionA0EE64F7-YOVUz8gvahWX}"
REGION="${2:-us-east-1}"
TEST_DIR="/tmp/lambda-test"

log_info "🧪 Testing Lambda function: ${FUNCTION_NAME}"
log_info "📍 Region: ${REGION}"
echo

# Create test directory
mkdir -p "$TEST_DIR"

# Test 1: MCP tools/list
log_warning "Test 1: MCP tools/list"
python3 quilt/tests/generate_lambda_events.py --event-type tools-list --output "$TEST_DIR/tools-list-event.json"
echo "  Generated event: $TEST_DIR/tools-list-event.json"

echo "  Invoking Lambda..."
aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload "file://$TEST_DIR/tools-list-event.json" \
  --cli-binary-format raw-in-base64-out \
  --region "$REGION" \
  "$TEST_DIR/tools-list-response.json"

echo "  Response:"
cat "$TEST_DIR/tools-list-response.json" | jq '.' 2>/dev/null || cat "$TEST_DIR/tools-list-response.json"
echo

# Test 2: MCP resources/list
log_warning "Test 2: MCP resources/list"
python3 quilt/tests/generate_lambda_events.py --event-type resources-list --output "$TEST_DIR/resources-list-event.json"
echo "  Generated event: $TEST_DIR/resources-list-event.json"

echo "  Invoking Lambda..."
aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload "file://$TEST_DIR/resources-list-event.json" \
  --region "$REGION" \
  "$TEST_DIR/resources-list-response.json"

echo "  Response:"
cat "$TEST_DIR/resources-list-response.json" | jq '.' 2>/dev/null || cat "$TEST_DIR/resources-list-response.json"
echo

# Test 3: Health check
log_warning "Test 3: Health check"
python3 quilt/tests/generate_lambda_events.py --event-type health-check --output "$TEST_DIR/health-check-event.json"
echo "  Generated event: $TEST_DIR/health-check-event.json"

echo "  Invoking Lambda..."
aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload "file://$TEST_DIR/health-check-event.json" \
  --region "$REGION" \
  "$TEST_DIR/health-check-response.json"

echo "  Response:"
cat "$TEST_DIR/health-check-response.json" | jq '.' 2>/dev/null || cat "$TEST_DIR/health-check-response.json"
echo

# Show Lambda logs
log_info "📋 Recent Lambda logs:"
LOG_GROUP="/aws/lambda/$FUNCTION_NAME"
aws logs tail "$LOG_GROUP" --region "$REGION" --since 5m 2>/dev/null || echo "  No logs available yet"

echo
log_success "✅ Lambda testing complete!"
echo "Test files saved in: $TEST_DIR"
