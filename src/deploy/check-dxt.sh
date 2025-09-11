#!/bin/bash

# DXT prerequisites validation script for Quilt MCP DXT
# Checks Python and Claude Desktop requirements for end users
# (DXT = Desktop Extension)

set -e

echo "🔍 Checking Quilt MCP DXT Prerequisites..."
echo

# Check Python version
check_python() {
    echo "Checking Python installation..."
    
    # Check user's default Python (what Claude Desktop will use)  
    # Simulate Claude Desktop's environment - clean login shell without project paths
    cd "$HOME"
    clean_path=$(echo $PATH | tr ":" "\n" | grep -v "$(pwd)" | grep -v "\.venv" | tr "\n" ":")
    python_cmd=$(bash -l -c "export PATH='$clean_path'; command -v python3" 2>/dev/null)
    
    if [ -n "$python_cmd" ]; then
        python_version=$(bash -l -c "export PATH='$clean_path'; $python_cmd --version" 2>&1 | awk '{print $2}')
        major=$(echo $python_version | cut -d. -f1)
        minor=$(echo $python_version | cut -d. -f2)
        
        if [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; then
            echo "✅ User default Python $python_version found at $python_cmd (required: 3.11+)"
            echo "   This is the Python that Claude Desktop will use"
        else
            echo "❌ User default Python $python_version found at $python_cmd, but 3.11+ is required"
            echo "   Claude Desktop requires Python 3.11+ in the user's login environment"
            echo "   Note: If you have pyenv installed, ensure it's properly initialized in your shell profile"
            return 1
        fi
    else
        echo "❌ User default Python 3 not found in login environment"
        echo "   Claude Desktop requires Python 3.11+ accessible from user's login shell"
        echo "   Try adding Python to your shell profile (.bashrc, .zshrc, etc.)"
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
    echo "📋 DXT Prerequisites Summary:"
    echo "   Python 3.11+: Required for running the MCP server"
    echo "   AWS Credentials: Required for accessing Quilt data"
    echo "   Claude Desktop: Required for using the DXT extension"
    echo
    echo "💡 Next Steps:"
    echo "   1. Double-click the Quilt MCP DXT to install in Claude Desktop"
    echo "   2. Enter catalog domain when prompted"
    echo "   3. Enable the extension"
    echo
}

# Main execution
main() {
    check_python
    echo
    check_aws  
    echo
    check_claude_desktop
    echo
    show_summary
    
    echo "✅ DXT prerequisites check complete!"
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi