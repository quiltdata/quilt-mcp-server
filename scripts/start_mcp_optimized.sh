#!/bin/bash
"""
Start MCP Server with Optimization and Telemetry

This script starts the MCP server with optimization and telemetry enabled.
"""

echo "🚀 Starting MCP Server with Optimization"
echo "========================================"

# Set optimization and telemetry environment variables
export MCP_OPTIMIZATION_ENABLED=true
export MCP_TELEMETRY_ENABLED=true
export MCP_TELEMETRY_LOCAL_ONLY=true
export MCP_TELEMETRY_LEVEL=standard
export MCP_TELEMETRY_PRIVACY_LEVEL=standard

echo "⚡ Optimization: ENABLED"
echo "📊 Telemetry: ENABLED (local file)"
echo "🔒 Privacy: STANDARD level"
echo "📁 Telemetry file: ~/.quilt/mcp_telemetry.jsonl"
echo ""

# Check if we want HTTP or stdio transport
if [ "$1" = "http" ]; then
    echo "🌐 Starting HTTP server on http://localhost:8000/mcp"
    export FASTMCP_TRANSPORT=http
    cd app && python main.py
else
    echo "📡 Starting STDIO server (for MCP clients)"
    export FASTMCP_TRANSPORT=stdio
    cd app && python main.py
fi

