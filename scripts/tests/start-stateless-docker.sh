#!/usr/bin/env bash
# Helper script to start a stateless MCP Docker container for testing
# Can be sourced by other scripts or run standalone

set -e

CONTAINER_NAME="${MCP_CONTAINER_NAME:-mcp-stateless-test}"
DOCKER_IMAGE="${TEST_DOCKER_IMAGE:-quilt-mcp:test}"
PORT="${MCP_PORT:-8002}"
JWT_SECRET="${MCP_JWT_SECRET:-test-secret-key-for-stateless-testing-only}"
CATALOG_URL="${QUILT_CATALOG_URL:-}"
REGISTRY_URL="${QUILT_REGISTRY_URL:-}"

# Check required Platform configuration
if [ -z "${CATALOG_URL}" ] || [ -z "${REGISTRY_URL}" ]; then
    echo "❌ QUILT_CATALOG_URL and QUILT_REGISTRY_URL must be set"
    echo "   Example:"
    echo "     export QUILT_CATALOG_URL=https://your-catalog.quiltdata.com"
    echo "     export QUILT_REGISTRY_URL=https://registry.your-catalog.quiltdata.com"
    exit 1
fi

echo "🐋 Starting stateless MCP Docker container..."
echo "   Container: ${CONTAINER_NAME}"
echo "   Image: ${DOCKER_IMAGE}"
echo "   Port: ${PORT}"
echo "   Catalog URL: ${CATALOG_URL}"
echo "   Registry URL: ${REGISTRY_URL}"

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
    -e QUILT_CATALOG_URL="${CATALOG_URL}" \
    -e QUILT_REGISTRY_URL="${REGISTRY_URL}" \
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

echo "✅ Stateless MCP container started successfully"
echo "   Access at: http://localhost:${PORT}/mcp"
echo "   Container logs: docker logs ${CONTAINER_NAME}"
