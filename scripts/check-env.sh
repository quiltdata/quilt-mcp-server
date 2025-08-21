#!/bin/bash
# Environment validation script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Parse command line arguments
CLIENT_TYPE="${1:-default}"

# Load shared utilities
source "$SCRIPT_DIR/common.sh"

log_info "🔍 Checking environment configuration..."

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    log_error "⚠️  No .env file found. Copy env.example to .env and configure."
    exit 1
fi

log_success "✅ .env file exists"

# Load environment variables
set -a
source "$PROJECT_ROOT/.env"
set +a

# Display environment summary
log_info "📋 Environment Summary:"
echo "  AWS Account: ${CDK_DEFAULT_ACCOUNT:-${AWS_ACCOUNT_ID:-Not set}}"
echo "  AWS Region: ${CDK_DEFAULT_REGION:-${AWS_DEFAULT_REGION:-Not set}}"
echo "  ECR Registry: ${ECR_REGISTRY:-Will be auto-derived}"
echo "  Quilt Bucket: ${QUILT_DEFAULT_BUCKET:-Not set}"
echo "  Catalog Domain: ${QUILT_CATALOG_DOMAIN:-Not set}"
echo "  ngrok Domain: ${NGROK_DOMAIN:-Auto-assigned (optional)}"
echo ""

# Validate required environment variables
log_info "🔍 Validating required environment variables..."

if [ -z "${CDK_DEFAULT_ACCOUNT}" ] && [ -z "${AWS_ACCOUNT_ID}" ]; then
    log_error "❌ Missing CDK_DEFAULT_ACCOUNT or AWS_ACCOUNT_ID"
    exit 1
fi

if [ -z "${CDK_DEFAULT_REGION}" ] && [ -z "${AWS_DEFAULT_REGION}" ]; then
    log_error "❌ Missing CDK_DEFAULT_REGION or AWS_DEFAULT_REGION"
    exit 1
fi

if [ -z "${QUILT_DEFAULT_BUCKET}" ]; then
    log_error "❌ Missing QUILT_DEFAULT_BUCKET"
    exit 1
fi

if [ -z "${QUILT_CATALOG_DOMAIN}" ]; then
    log_error "❌ Missing QUILT_CATALOG_DOMAIN"
    exit 1
fi

log_success "✅ Environment validation complete"

# Provide client-specific instructions if requested
case "$CLIENT_TYPE" in
    claude)
        log_info "📋 CLAUDE DESKTOP NEXT STEPS:"
        echo "  1. Generate MCP configuration: python scripts/make_mcp_config.py claude"
        echo "  2. Copy the generated config to your Claude Desktop settings"
        echo "  3. Restart Claude Desktop"
        ;;
    vscode)
        log_info "📋 VS CODE NEXT STEPS:"
        echo "  1. Generate MCP configuration: python scripts/make_mcp_config.py vscode"
        echo "  2. Install the MCP Client extension in VS Code"
        echo "  3. Add the generated config to VS Code MCP settings"
        echo "  4. Restart VS Code"
        ;;
    cursor)
        log_info "📋 CURSOR NEXT STEPS:"
        echo "  1. Generate MCP configuration: python scripts/make_mcp_config.py claude"
        echo "  2. Copy the generated config to your Cursor settings"
        echo "  3. Restart Cursor"
        ;;
    http)
        log_info "📋 HTTP MCP SERVER NEXT STEPS:"
        echo "  1. Start the server: make app"
        echo "  2. Server will be available at: http://127.0.0.1:8000/mcp"
        echo "  3. For remote access: make run-app-tunnel"
        ;;
    default)
        # Default behavior - no additional instructions
        ;;
    *)
        log_error "❌ Unknown client type: $CLIENT_TYPE"
        log_info "Available types: claude, vscode, cursor, http"
        exit 1
        ;;
esac