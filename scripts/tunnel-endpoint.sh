#!/bin/bash
# Tunnel endpoint script - creates ngrok tunnel for MCP endpoints
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load shared utilities
source "$SCRIPT_DIR/common.sh"

usage() {
    echo "Usage: $0 <endpoint-url> [--inspect]"
    echo ""
    echo "Arguments:"
    echo "  endpoint-url    The local endpoint URL (e.g., 'http://127.0.0.1:8000/mcp')"
    echo ""
    echo "Options:"
    echo "  --inspect       Launch MCP Inspector for visual testing"
    echo ""
    echo "Examples:"
    echo "  $0 http://127.0.0.1:8000/mcp              # Tunnel regular server"
    echo "  $0 http://127.0.0.1:8000/mcp --inspect    # Tunnel with MCP Inspector"
    echo "  $0 http://127.0.0.1:8001/mcp              # Tunnel build server"
}

if [ $# -lt 1 ]; then
    log_error "Missing endpoint URL argument"
    usage
    exit 1
fi

ENDPOINT_URL="$1"
USE_INSPECTOR=false

# Parse arguments
shift
while [[ $# -gt 0 ]]; do
    case $1 in
        --inspect)
            USE_INSPECTOR=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Extract port from URL
PORT=$(echo "$ENDPOINT_URL" | sed -n 's|.*://[^:]\+:\([0-9]\+\).*|\1|p')
if [ -z "$PORT" ]; then
    log_error "Could not extract port from endpoint URL: $ENDPOINT_URL"
    exit 1
fi

# Check for required tools
if ! command -v ngrok &> /dev/null; then
    log_error "ngrok not found. Please install ngrok first."
    exit 1
fi

if [ "$USE_INSPECTOR" = true ] && ! command -v npx &> /dev/null; then
    log_error "npx not found. Please install Node.js first (required for MCP Inspector)."
    exit 1
fi

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Set up signal handling for cleanup
cleanup() {
    log_info "Stopping tunnel and any launched processes..."
    if [ -n "$INSPECTOR_PID" ]; then
        kill $INSPECTOR_PID 2>/dev/null || true
    fi
    exit 0
}
trap cleanup INT

log_info "🌐 Starting ngrok tunnel for endpoint: $ENDPOINT_URL"
echo "   Local server: $ENDPOINT_URL"

if [ -n "$NGROK_DOMAIN" ]; then
    echo "   Public URL: https://$NGROK_DOMAIN/mcp"
    echo "   Using domain from NGROK_DOMAIN environment variable"
else
    echo "   ⚠️  NGROK_DOMAIN not set, using ngrok auto-assigned URL"
fi

if [ "$USE_INSPECTOR" = true ]; then
    echo "   🔍 Launching MCP Inspector..."
    echo "   Inspector UI: http://127.0.0.1:6274"
    # Launch inspector in background, connecting to the existing endpoint
    cd "$PROJECT_ROOT"
    npx @modelcontextprotocol/inspector --url "$ENDPOINT_URL" & INSPECTOR_PID=$!
    sleep 2
fi

echo "   Press Ctrl+C to stop tunnel and inspector"
echo ""

# Start ngrok tunnel
if [ -n "$NGROK_DOMAIN" ]; then
    ngrok http "$PORT" --domain="$NGROK_DOMAIN"
else
    ngrok http "$PORT"
fi

# Cleanup when ngrok exits
cleanup