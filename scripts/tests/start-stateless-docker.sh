#!/usr/bin/env bash
# Helper script to start a stateless MCP Docker container for testing
# Can be sourced by other scripts or run standalone

set -e

CONTAINER_NAME="${MCP_CONTAINER_NAME:-mcp-stateless-test}"
DOCKER_IMAGE="${TEST_DOCKER_IMAGE:-quilt-mcp:test}"
PORT="${MCP_PORT:-8002}"
JWT_SECRET="${MCP_JWT_SECRET:-test-secret-key-for-stateless-testing-only}"

# Check if QUILT_TEST_ROLE_ARN is set
if [ -z "${QUILT_TEST_ROLE_ARN}" ]; then
    echo "❌ QUILT_TEST_ROLE_ARN not set"
    echo "   Set to real AWS role ARN for testing"
    echo "   Example: export QUILT_TEST_ROLE_ARN=arn:aws:iam::123456789:role/QuiltMCPTestRole"
    exit 1
fi

echo "🐋 Starting stateless MCP Docker container..."
echo "   Container: ${CONTAINER_NAME}"
echo "   Image: ${DOCKER_IMAGE}"
echo "   Port: ${PORT}"
echo "   Role ARN: ${QUILT_TEST_ROLE_ARN}"

# Stop and remove existing container if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "   Removing existing container..."
    docker stop "${CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${CONTAINER_NAME}" 2>/dev/null || true
fi

# Start the container with security constraints matching stateless deployment
docker run -d --name "${CONTAINER_NAME}" \
    --read-only \
    --security-opt=no-new-privileges:true \
    --cap-drop=ALL \
    --tmpfs=/tmp:size=100M,mode=1777 \
    --tmpfs=/run:size=10M,mode=755 \
    --memory=512m \
    --memory-swap=512m \
    --cpu-quota=100000 \
    --cpu-period=100000 \
    -e MCP_REQUIRE_JWT=true \
    -e MCP_JWT_SECRET="${JWT_SECRET}" \
    -e QUILT_DISABLE_CACHE=true \
    -e HOME=/tmp \
    -e LOG_LEVEL=DEBUG \
    -e QUILT_MCP_STATELESS_MODE=true \
    -e FASTMCP_TRANSPORT=http \
    -e FASTMCP_HOST=0.0.0.0 \
    -e FASTMCP_PORT=8000 \
    -e AWS_REGION=us-east-1 \
    -p "${PORT}:8000" \
    "${DOCKER_IMAGE}"

# Wait for container to be healthy
echo "   Waiting for container to start..."
sleep 3

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "❌ Container failed to start"
    docker logs "${CONTAINER_NAME}" 2>/dev/null || true
    exit 1
fi

echo "✅ Stateless MCP container started successfully"
echo "   Access at: http://localhost:${PORT}/mcp"
echo "   Container logs: docker logs ${CONTAINER_NAME}"
