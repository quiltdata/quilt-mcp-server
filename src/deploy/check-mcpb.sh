#!/bin/bash

# MCPB prerequisites validation script for Quilt MCP Bundle
# Checks UVX and Claude Desktop requirements for end users
# (MCPB = MCP Bundle)

set -e

echo "🔍 Checking Quilt MCP Bundle Prerequisites..."
echo

# Check UVX installation
check_uvx() {
    echo "Checking UVX installation..."

    # Check if uvx is available
    if command -v uvx >/dev/null 2>&1; then
        uvx_version=$(uvx --version 2>&1 | head -n1)
        echo "✅ UVX found: $uvx_version"
        echo "   This will be used by Claude Desktop to run the MCP server"

        # Check if quilt-mcp package is available
        if uvx list 2>/dev/null | grep -q "quilt-mcp" || pip show quilt-mcp >/dev/null 2>&1; then
            echo "✅ quilt-mcp package is available"
        else
            echo "⚠️  quilt-mcp package not found"
            echo "   It will be automatically installed when the MCPB is loaded"
        fi
    else
        echo "❌ UVX not found"
        echo "   Claude Desktop requires UVX to run MCPB packages"
        echo "   Install with: pip install uvx"
        echo "   Or install UV: curl -LsSf https://astral.sh/uv/install.sh | sh"
        return 1
    fi
}

# Check AWS configuration
check_aws() {
    echo "Checking AWS configuration..."
    
    # Check AWS CLI
    if command -v aws >/dev/null 2>&1; then
        echo "✅ AWS CLI found"
        
        # Check AWS credentials
        if aws sts get-caller-identity >/dev/null 2>&1; then
            identity=$(aws sts get-caller-identity --query 'Account' --output text 2>/dev/null)
            echo "✅ AWS credentials configured (Account: $identity)"
        else
            echo "⚠️  AWS CLI found but credentials not configured or invalid"
            echo "   Configure credentials with: aws configure"
            echo "   Or set AWS_PROFILE environment variable"
        fi
    else
        echo "⚠️  AWS CLI not found"
        echo "   Install with: pip install awscli"
        echo "   Or use AWS environment variables for authentication"
    fi
}

# Check Claude Desktop
check_claude_desktop() {
    echo "Checking Claude Desktop..."
    
    # macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if [ -d "/Applications/Claude.app" ]; then
            echo "✅ Claude Desktop found on macOS"
        else
            echo "⚠️  Claude Desktop not found in /Applications/"
            echo "   Download from: https://claude.ai/download"
        fi
    # Windows
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
        if [ -d "$APPDATA/Claude" ] || [ -d "$LOCALAPPDATA/Claude" ]; then
            echo "✅ Claude Desktop found on Windows"
        else
            echo "⚠️  Claude Desktop not found"
            echo "   Download from: https://claude.ai/download"
        fi
    # Linux
    else
        if command -v claude >/dev/null 2>&1 || [ -f "$HOME/.local/bin/claude" ]; then
            echo "✅ Claude Desktop found on Linux"
        else
            echo "⚠️  Claude Desktop not found"
            echo "   Download from: https://claude.ai/download"
        fi
    fi
}

# Summary function
show_summary() {
    echo
    echo "📋 MCPB Prerequisites Summary:"
    echo "   UVX: Required for running the MCP server package"
    echo "   AWS Credentials: Required for accessing Quilt data"
    echo "   Claude Desktop: Required for using the MCPB bundle"
    echo
    echo "💡 Next Steps:"
    echo "   1. Double-click the Quilt MCP Bundle (.mcpb) to install in Claude Desktop"
    echo "   2. Enter catalog domain when prompted"
    echo "   3. Enable the extension"
    echo
}

# Main execution
main() {
    check_uvx
    echo
    check_aws
    echo
    check_claude_desktop
    echo
    show_summary

    echo "✅ MCPB prerequisites check complete!"
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi