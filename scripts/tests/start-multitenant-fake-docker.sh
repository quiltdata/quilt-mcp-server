#!/usr/bin/env bash
# Helper script to start a stateless MCP Docker container for multitenant fake testing
# Uses fake role ARNs and JWT secrets for local development testing only

set -e

CONTAINER_NAME="${MCP_CONTAINER_NAME:-mcp-multitenant-fake-test}"
DOCKER_IMAGE="${TEST_DOCKER_IMAGE:-quilt-mcp:test}"
PORT="${MCP_PORT:-8003}"
JWT_SECRET="${MCP_JWT_SECRET:-test-secret}"

echo "🐋 Starting multitenant fake test MCP Docker container..."
echo "   Container: ${CONTAINER_NAME}"
echo "   Image: ${DOCKER_IMAGE}"
echo "   Port: ${PORT}"
echo "   Note: Using fake credentials for local testing only"

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
    -e QUILT_MULTITENANT_MODE=true \
    -e MCP_JWT_SECRET="${JWT_SECRET}" \
    -e MCP_JWT_ISSUER="mcp-test" \
    -e MCP_JWT_AUDIENCE="mcp-server" \
    -e QUILT_DISABLE_CACHE=true \
    -e HOME=/tmp \
    -e LOG_LEVEL=DEBUG \
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

echo "✅ Multitenant fake test MCP container started successfully"
echo "   Access at: http://localhost:${PORT}/mcp"
echo "   Container logs: docker logs ${CONTAINER_NAME}"
