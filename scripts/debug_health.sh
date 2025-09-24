#!/bin/bash
# Health Check Debugging Script for MCP Server
# This script helps diagnose health check issues in both local and ECS environments

set -e

echo "========================================="
echo "MCP Server Health Check Debugging Script"
echo "========================================="
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get configuration from environment
PORT=${FASTMCP_PORT:-8080}
HOST=${FASTMCP_HOST:-localhost}
TRANSPORT=${FASTMCP_TRANSPORT:-http}

echo "Configuration:"
echo "  Transport: $TRANSPORT"
echo "  Host: $HOST"
echo "  Port: $PORT"
echo ""

# Check if server process is running
echo "1. Checking if MCP server process is running..."
if pgrep -f "quilt-mcp" > /dev/null 2>&1; then
    echo "   ✓ MCP server process is running"
    echo "   Process details:"
    ps aux | grep -E "quilt-mcp|python.*main.py" | grep -v grep | head -5
else
    echo "   ✗ MCP server process NOT found"
    echo "   Checking for Python processes..."
    ps aux | grep python | grep -v grep | head -5
fi
echo ""

# Check if port is listening
echo "2. Checking if port $PORT is listening..."
if command_exists netstat; then
    if netstat -tln 2>/dev/null | grep -q ":$PORT"; then
        echo "   ✓ Port $PORT is listening"
        echo "   Listening ports:"
        netstat -tln | grep ":$PORT"
    else
        echo "   ✗ Port $PORT is NOT listening"
        echo "   All listening ports:"
        netstat -tln | grep LISTEN
    fi
elif command_exists ss; then
    if ss -tln 2>/dev/null | grep -q ":$PORT"; then
        echo "   ✓ Port $PORT is listening"
        echo "   Listening ports:"
        ss -tln | grep ":$PORT"
    else
        echo "   ✗ Port $PORT is NOT listening"
        echo "   All listening ports:"
        ss -tln | grep LISTEN
    fi
else
    echo "   ⚠ Neither netstat nor ss available"
fi
echo ""

# Check connectivity to localhost
echo "3. Testing localhost connectivity..."
if ping -c 1 -W 1 localhost >/dev/null 2>&1; then
    echo "   ✓ localhost is reachable"
else
    echo "   ✗ localhost is NOT reachable"
fi
echo ""

# Check if curl is available
echo "4. Checking curl availability..."
if command_exists curl; then
    echo "   ✓ curl is available"
    curl --version | head -1
else
    echo "   ✗ curl is NOT available"
    exit 1
fi
echo ""

# Test health endpoint with different approaches
echo "5. Testing health endpoint..."
echo ""

echo "   a. Basic curl test:"
echo "      Command: curl -f http://localhost:$PORT/health"
if curl -f -s http://localhost:$PORT/health >/dev/null 2>&1; then
    echo "      ✓ Basic health check PASSED"
    echo "      Response:"
    curl -s http://localhost:$PORT/health | python -m json.tool 2>/dev/null || curl -s http://localhost:$PORT/health
else
    echo "      ✗ Basic health check FAILED (exit code: $?)"
fi
echo ""

echo "   b. Verbose curl test:"
echo "      Command: curl -v http://localhost:$PORT/health"
curl -v http://localhost:$PORT/health 2>&1 | head -20
echo ""

echo "   c. Test with explicit Host header:"
echo "      Command: curl -H 'Host: localhost' http://127.0.0.1:$PORT/health"
curl -s -H "Host: localhost" http://127.0.0.1:$PORT/health 2>&1
echo ""

echo "   d. Test with 0.0.0.0 binding:"
echo "      Command: curl http://0.0.0.0:$PORT/health"
curl -s http://0.0.0.0:$PORT/health 2>&1
echo ""

# Check environment variables
echo "6. Checking environment variables..."
echo "   MCP/FastMCP variables:"
env | grep -E "^(MCP_|FASTMCP_)" | sort | sed 's/^/      /'
echo ""
echo "   AWS/Quilt variables:"
env | grep -E "^(AWS_|QUILT_)" | head -10 | sed 's/^/      /'
echo ""

# Check recent logs
echo "7. Recent server logs (if available)..."
if [ -f /var/log/mcp-server.log ]; then
    echo "   From /var/log/mcp-server.log:"
    tail -20 /var/log/mcp-server.log | sed 's/^/      /'
elif [ -f /tmp/mcp-server.log ]; then
    echo "   From /tmp/mcp-server.log:"
    tail -20 /tmp/mcp-server.log | sed 's/^/      /'
else
    echo "   No log files found in standard locations"
fi
echo ""

# Check Docker/ECS specific
if [ -f /.dockerenv ] || [ -n "$ECS_CONTAINER_METADATA_URI" ]; then
    echo "8. Container environment detected..."

    if [ -n "$ECS_CONTAINER_METADATA_URI" ]; then
        echo "   Running in ECS"
        echo "   Task metadata endpoint: $ECS_CONTAINER_METADATA_URI"

        # Try to get task metadata
        if command_exists curl && [ -n "$ECS_CONTAINER_METADATA_URI_V4" ]; then
            echo "   Task metadata:"
            curl -s "$ECS_CONTAINER_METADATA_URI_V4/task" 2>/dev/null | python -m json.tool 2>/dev/null | head -20 | sed 's/^/      /'
        fi
    else
        echo "   Running in Docker (non-ECS)"
    fi
    echo ""
fi

# Summary
echo "========================================="
echo "Summary:"
echo "========================================="

ISSUES=0

if ! pgrep -f "quilt-mcp" > /dev/null 2>&1; then
    echo "❌ Server process not running"
    ISSUES=$((ISSUES + 1))
fi

if ! netstat -tln 2>/dev/null | grep -q ":$PORT" && ! ss -tln 2>/dev/null | grep -q ":$PORT"; then
    echo "❌ Port $PORT not listening"
    ISSUES=$((ISSUES + 1))
fi

if ! curl -f -s http://localhost:$PORT/health >/dev/null 2>&1; then
    echo "❌ Health endpoint not responding"
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    echo "✅ All checks passed - server appears healthy"
else
    echo "⚠️  Found $ISSUES issue(s) - see details above"
fi

echo ""
echo "Debugging tips:"
echo "1. Check if FASTMCP_PORT matches the port in your Dockerfile/CloudFormation"
echo "2. Ensure FASTMCP_HOST is set to '0.0.0.0' for container environments"
echo "3. Verify FASTMCP_TRANSPORT is set to 'http' for HTTP health checks"
echo "4. Check CloudWatch logs for startup errors"
echo "5. Ensure the container has enough memory/CPU"

exit $ISSUES