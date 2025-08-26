# MCP Client Log Analysis Procedures

This document describes procedures for analyzing MCP client logs to validate successful server connections and diagnose issues.

## Quick Start

```bash
# Check if Claude Desktop is successfully connected
python uat/scripts/log-analyzer.py --client claude_desktop --check-connection

# Generate comprehensive report for all clients
python uat/scripts/log-analyzer.py --report

# Analyze specific client with detailed output
python uat/scripts/log-analyzer.py --client claude_desktop
```

## Log File Locations

### Claude Desktop

**macOS**: `~/Library/Logs/Claude/mcp-server-quilt.log`
**Windows**: `%APPDATA%\Claude\logs\mcp-server-quilt.log`
**Linux**: `~/.config/claude/logs/mcp-server-quilt.log`

### VS Code

VS Code MCP logs are available through:
1. Open Command Palette (`Cmd/Ctrl + Shift + P`)
2. Run "Developer: Toggle Developer Tools"
3. Check Console tab for MCP-related messages
4. Filter by "MCP" or "mcpServers"

### Cursor

Similar to VS Code:
1. Open Command Palette (`Cmd/Ctrl + Shift + P`)
2. Run "Developer: Toggle Developer Tools"
3. Check Console tab for MCP-related messages

## Success Patterns

### Claude Desktop Success Indicators

```
Server started and connected successfully
Message from client: {"method":"initialize",...}
```

### Common Success Patterns (All Clients)

- Server initialization messages
- Client handshake completion
- MCP protocol version negotiation
- Successful tool/resource registration

## Failure Patterns

### Claude Desktop Failure Indicators

```
spawn <command> ENOENT
Server disconnected
can't open file
No such file or directory
Failed to spawn: <command>
```

### Common Failure Patterns (All Clients)

- Command not found errors (`ENOENT`, "No such file")
- Path resolution failures
- Permission denied errors
- Network/socket connection failures
- Protocol version mismatches

## Automated Analysis Commands

### Basic Connection Check

```bash
# Exit code 0 = success, 1 = failure
python uat/scripts/log-analyzer.py --client claude_desktop --check-connection
echo "Exit code: $?"
```

### JSON Output for Integration

```bash
# Get machine-readable analysis
python uat/scripts/log-analyzer.py --client claude_desktop --json
```

### Comprehensive Reporting

```bash
# Generate full report with all clients
python uat/scripts/log-analyzer.py --report

# Generate JSON report for automation
python uat/scripts/log-analyzer.py --report --json
```

## Manual Analysis Procedures

### Step 1: Locate Log Files

Use the log analyzer to find client-specific log locations:

```bash
python uat/scripts/log-analyzer.py --client claude_desktop
```

### Step 2: Check Recent Activity

```bash
# View recent log entries (Claude Desktop)
tail -f ~/Library/Logs/Claude/mcp-server-quilt.log
```

### Step 3: Search for Patterns

```bash
# Look for connection attempts
grep -i "initializing\|connecting\|started" ~/Library/Logs/Claude/mcp-server-quilt.log

# Look for errors
grep -i "error\|failed\|enoent" ~/Library/Logs/Claude/mcp-server-quilt.log
```

## Troubleshooting Guide

### Issue: `spawn uv run quilt-mcp ENOENT`

**Cause**: Incorrect command configuration or missing executable
**Solution**: 
1. Verify MCP configuration uses `make -C app run`
2. Ensure project root has Makefile
3. Test manual server startup: `make -C app run`

### Issue: `can't open file '//main.py'`

**Cause**: Path concatenation error in configuration
**Solution**:
1. Check `cwd` field in MCP configuration
2. Verify no double slashes in paths
3. Use absolute paths for `cwd` field

### Issue: Server starts but disconnects immediately

**Cause**: Server crashes during initialization
**Solution**:
1. Check server dependencies: `uv sync --group test`
2. Test server manually: `cd app && uv run python main.py`
3. Review server error output in logs

### Issue: No log entries found

**Cause**: Client not attempting MCP connection
**Solution**:
1. Verify MCP configuration is in correct location
2. Restart client application after config changes
3. Check client-specific MCP enable settings

## Integration with CI/CD

### Automated Validation

```bash
#!/bin/bash
# Example CI validation script

echo "Testing MCP client configurations..."

# Test configuration generation
make mcp-config BATCH=1 > /tmp/test-config.json

# Validate configuration
python uat/scripts/log-analyzer.py --validate-config /tmp/test-config.json

# Test server startup
timeout 30s make -C app run > /tmp/server-test.log 2>&1 &
SERVER_PID=$!

sleep 5

if kill -0 $SERVER_PID 2>/dev/null; then
    echo "✅ Server startup test passed"
    kill $SERVER_PID
else
    echo "❌ Server startup test failed"
    cat /tmp/server-test.log
    exit 1
fi
```

### Log Monitoring

```bash
# Monitor for connection issues
python uat/scripts/log-analyzer.py --client claude_desktop --check-connection
if [ $? -ne 0 ]; then
    echo "❌ MCP connection failure detected"
    python uat/scripts/log-analyzer.py --client claude_desktop --report
    exit 1
fi
```

## Pattern File Customization

Edit `uat/logs/patterns.json` to customize success/failure patterns:

```json
{
  "clients": {
    "claude_desktop": {
      "success_patterns": [
        "Server started and connected successfully",
        "Custom success pattern here"
      ],
      "failure_patterns": [
        "spawn .* ENOENT",
        "Custom failure pattern here"
      ]
    }
  }
}
```

## Best Practices

### For Development

1. **Always check logs after configuration changes**
2. **Test server startup manually before client integration**
3. **Use automated analysis for consistent validation**
4. **Keep log patterns updated with new failure modes**

### For Production

1. **Monitor logs continuously for connection issues**
2. **Set up alerts for failure pattern detection**
3. **Maintain log retention for historical analysis**
4. **Document new failure patterns as they're discovered**

### For Debugging

1. **Start with automated analysis for overview**
2. **Use manual log inspection for detailed investigation**
3. **Test configuration changes incrementally**
4. **Verify server functionality independently before client testing**