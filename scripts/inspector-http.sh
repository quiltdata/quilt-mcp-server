#!/bin/bash
# Launch MCP Inspector with HTTP configuration instructions
# Usage: ./scripts/inspector-http.sh [port] [endpoint]

PORT=${1:-8000}
ENDPOINT=${2:-mcp}
URL="http://localhost:${PORT}/${ENDPOINT}"

echo "🔍 MCP Inspector Configuration for HTTP Transport"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  MCP Server URL: ${URL}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Manual Configuration Steps:"
echo "  1. Wait for Inspector UI to open in browser"
echo "  2. In the Inspector UI form:"
echo "     • Transport Type: Select 'Streamable HTTP'"
echo "     • URL: Enter '${URL}'"
echo "     • Connection Type: 'Direct'"
echo "  3. Click 'Connect'"
echo ""
echo "⏳ Launching Inspector UI..."
echo ""

# Launch Inspector
npx @modelcontextprotocol/inspector

# Note: Passing the URL as a parameter doesn't pre-populate the form
# The Inspector UI requires manual configuration for HTTP transport
