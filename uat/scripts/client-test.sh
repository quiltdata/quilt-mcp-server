#!/bin/bash
# Test MCP client configuration
# Usage: ./client-test.sh <client_name> [--deploy]

set -e

CLIENT=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -z "$CLIENT" ]]; then
    echo "Usage: $0 <client_name> [--deploy]"
    echo "Available clients: claude_desktop, vscode, cursor"
    exit 1
fi

echo "Testing MCP configuration for $CLIENT..."
echo "Project root: $PROJECT_ROOT"

# Change to project root
cd "$PROJECT_ROOT"

# 1. Generate config in batch mode
echo "1. Generating MCP configuration..."
make mcp-config BATCH=1 > /tmp/mcp-config.json

# 2. Validate JSON structure
echo "2. Validating JSON structure..."
python3 -c "import json; config = json.load(open('/tmp/mcp-config.json')); print('✅ Valid JSON structure')" || {
    echo "❌ Invalid JSON structure"
    exit 1
}

# 3. Validate required fields
echo "3. Validating MCP configuration fields..."
python3 -c "
import json
config = json.load(open('/tmp/mcp-config.json'))
servers = config.get('mcpServers', {})
if not servers:
    raise ValueError('No mcpServers section found')
quilt_server = servers.get('quilt', {})
if not quilt_server:
    raise ValueError('No quilt server configuration found')
required_fields = ['command', 'args', 'cwd', 'env', 'description']
for field in required_fields:
    if field not in quilt_server:
        raise ValueError(f'Missing required field: {field}')
print('✅ All required fields present')
" || {
    echo "❌ Missing required configuration fields"
    exit 1
}

# 4. Test server startup with generated config (basic validation)
echo "4. Testing MCP server startup..."
if command -v make >/dev/null 2>&1; then
    # Use different port to avoid conflicts
    export FASTMCP_PORT=8003
    timeout 10s make -C app run > /tmp/mcp-server-test.log 2>&1 &
    SERVER_PID=$!
    sleep 3
    
    if kill -0 $SERVER_PID 2>/dev/null; then
        echo "✅ MCP server started successfully on port 8003"
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
    else
        echo "❌ MCP server failed to start"
        echo "Server output:"
        cat /tmp/mcp-server-test.log
        
        # Check if it's just a port conflict and try again
        if grep -q "address already in use" /tmp/mcp-server-test.log; then
            echo "Port conflict detected, trying port 8004..."
            export FASTMCP_PORT=8004
            timeout 10s make -C app run > /tmp/mcp-server-test2.log 2>&1 &
            SERVER_PID2=$!
            sleep 3
            
            if kill -0 $SERVER_PID2 2>/dev/null; then
                echo "✅ MCP server started successfully on port 8004"
                kill $SERVER_PID2 2>/dev/null || true
                wait $SERVER_PID2 2>/dev/null || true
            else
                echo "❌ MCP server failed to start even with different port"
                cat /tmp/mcp-server-test2.log
                exit 1
            fi
        else
            exit 1
        fi
    fi
else
    echo "⚠️  Make not available, skipping server startup test"
fi

# 5. Deploy config (if requested)
if [[ "$2" == "--deploy" ]]; then
    echo "5. Deploying configuration to $CLIENT..."
    make mcp-config CLIENT=$CLIENT
    echo "✅ Configuration deployed to $CLIENT"
else
    echo "5. Skipping deployment (use --deploy to enable)"
fi

# 6. Clean up
rm -f /tmp/mcp-config.json /tmp/mcp-server-test.log

echo "✅ MCP configuration test passed for $CLIENT"