#!/usr/bin/env bash
# Helper script to stop and remove a stateless MCP Docker container
# Can be sourced by other scripts or run standalone

set -e

CONTAINER_NAME="${MCP_CONTAINER_NAME:-mcp-stateless-test}"

echo "🛑 Stopping stateless MCP Docker container..."
echo "   Container: ${CONTAINER_NAME}"

# Check if container exists
if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "   Container not found (already removed)"
    exit 0
fi

# Stop the container
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "   Stopping container..."
    docker stop "${CONTAINER_NAME}"
fi

# Remove the container
echo "   Removing container..."
docker rm "${CONTAINER_NAME}"

echo "✅ Stateless MCP container stopped and removed"
