#!/bin/bash

# Test Lambda function with various MCP events
# Usage: ./test_lambda.sh [function-name] [region]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Set AWS profile for deployment
export AWS_PROFILE=open

# Default values
FUNCTION_NAME="${1:-QuiltMcpStack-QuiltMcpFunctionA0EE64F7-YOVUz8gvahWX}"
REGION="${2:-us-east-1}"
TEST_DIR="/tmp/lambda-test"

echo -e "${BLUE}🧪 Testing Lambda function: ${FUNCTION_NAME}${NC}"
echo -e "${BLUE}📍 Region: ${REGION}${NC}"
echo

# Create test directory
mkdir -p "$TEST_DIR"

# Test 1: MCP tools/list
echo -e "${YELLOW}Test 1: MCP tools/list${NC}"
python3 tests/generate_lambda_events.py --event-type tools-list --output "$TEST_DIR/tools-list-event.json"
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
echo -e "${YELLOW}Test 2: MCP resources/list${NC}"
python3 tests/generate_lambda_events.py --event-type resources-list --output "$TEST_DIR/resources-list-event.json"
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
echo -e "${YELLOW}Test 3: Health check${NC}"
python3 tests/generate_lambda_events.py --event-type health-check --output "$TEST_DIR/health-check-event.json"
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
echo -e "${BLUE}📋 Recent Lambda logs:${NC}"
LOG_GROUP="/aws/lambda/$FUNCTION_NAME"
aws logs tail "$LOG_GROUP" --region "$REGION" --since 5m 2>/dev/null || echo "  No logs available yet"

echo
echo -e "${GREEN}✅ Lambda testing complete!${NC}"
echo -e "Test files saved in: $TEST_DIR"
