#!/bin/bash
set -e

# Get script directory and source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Main function
main() {
    log_info "🧪 Testing Quilt MCP Server with MCP Inspector"
    
    # Check if .config exists
    if [ ! -f ".config" ]; then
        log_error "❌ No deployment configuration found. Run deployment first:"
        log_info "    ./scripts/build.sh deploy"
        exit 1
    fi
    
    # Load configuration
    source .config
    
    # Check if MCP Inspector is installed
    if ! command -v npx >/dev/null 2>&1; then
        log_error "❌ Node.js/npx not found. Please install Node.js first:"
        log_info "    https://nodejs.org/"
        exit 1
    fi
    
    # Get access token
    log_info "Getting OAuth access token..."
    if ! ACCESS_TOKEN=$("$SCRIPT_DIR/get_token.sh" 2>/dev/null); then
        log_error "❌ Failed to get access token"
        log_info "Check your deployment configuration and try again"
        exit 1
    fi
    
    log_success "✅ Authentication successful"
    log_info "🚀 Launching MCP Inspector..."
    log_info ""
    log_info "MCP Server Details:"
    log_info "  Name: $MCP_SERVER_NAME"  
    log_info "  URL: $API_ENDPOINT"
    log_info "  Authentication: OAuth 2.0 (Bearer Token)"
    log_info ""
    log_info "The MCP Inspector will open in your browser."
    log_info "Use the server URL and access token shown above to connect."
    echo ""
    
    log_info "Starting MCP Inspector..."
    echo ""
    echo "🌐 MCP Inspector will open in your browser"
    echo "📋 Server URL: $API_ENDPOINT"
    echo "🔐 Access Token: $ACCESS_TOKEN"
    echo ""
    echo "📝 Connection Instructions:"
    echo "  1. Select 'HTTP Transport' in MCP Inspector"
    echo "  2. Enter Server URL: $API_ENDPOINT"
    echo "  3. Add Authorization header: Bearer $ACCESS_TOKEN"
    echo "  4. Click Connect"
    echo ""
    echo "Press any key to launch MCP Inspector..."
    read -n 1 -s
    
    # Launch MCP Inspector
    log_info "Launching MCP Inspector..."
    if ! npx @modelcontextprotocol/inspector 2>&1; then
        EXIT_CODE=$?
        echo ""
        log_error "❌ MCP Inspector failed to start (exit code: $EXIT_CODE)"
        log_info "💡 Common solutions:"
        log_info "  - If you see 'PORT IS IN USE' error:"
        log_info "    • Close any existing MCP Inspector instances"
        log_info "    • Kill processes using port: lsof -ti:3000 | xargs kill -9"
        log_info "    • Wait a moment and try again"
        log_info "  - Try manual launch: npx @modelcontextprotocol/inspector"
        echo ""
        log_info "🔄 You can retry by running this script again"
        return 1
    fi
    
    log_success "🎉 MCP Inspector session completed"
}

# Show help information
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Test the deployed Quilt MCP Server using MCP Inspector

Options:
  -h, --help         Show this help message

Requirements:
  - Node.js/npx installed
  - Deployed MCP server (.config file present)
  - Internet connection

Examples:
  $0                 # Launch MCP Inspector with deployed server

The script will:
1. Check deployment configuration
2. Get OAuth access token
3. Launch MCP Inspector with server details
4. Provide connection instructions

For manual connection:
- Server URL: Found in .config as API_ENDPOINT
- Authentication: Bearer token from ./scripts/get_token.sh
- Transport: HTTP/HTTPS
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            log_info "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main "$@"