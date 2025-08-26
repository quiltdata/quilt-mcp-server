# Claude Desktop Integration Testing

This document provides comprehensive testing procedures for Quilt MCP server integration with Claude Desktop.

## Prerequisites

- Claude Desktop application installed
- Quilt MCP server project set up locally
- Administrative access to modify configuration files

## Test Environment Setup

### 1. Backup Existing Configuration

```bash
# Backup current Claude Desktop configuration
cp ~/Library/Application\ Support/Claude/claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json.backup
```

### 2. Verify Project Setup

```bash
# Ensure project dependencies are installed
cd /path/to/quilt-mcp-server
uv sync --group test

# Test server can start manually
make -C app run
# Should start without errors, Ctrl+C to stop
```

## Automated Testing

### Configuration Generation Test

```bash
# Generate Claude Desktop configuration
make mcp-config CLIENT=claude_desktop

# Verify configuration was applied
python uat/scripts/log-analyzer.py --client claude_desktop --json
```

### Connection Validation Test

```bash
# Test configuration deployment
./uat/scripts/client-test.sh claude_desktop --deploy

# Check connection success
python uat/scripts/log-analyzer.py --client claude_desktop --check-connection
```

## Manual Testing Procedures

### Test Case 1: Fresh Configuration

**Objective**: Verify MCP server works with clean Claude Desktop installation

**Steps**:
1. Remove existing MCP configuration:
   ```bash
   # Remove mcpServers section from config
   python -c "
   import json
   from pathlib import Path
   config_file = Path.home() / 'Library/Application Support/Claude/claude_desktop_config.json'
   if config_file.exists():
       with open(config_file, 'r') as f:
           config = json.load(f)
       config.pop('mcpServers', None)
       with open(config_file, 'w') as f:
           json.dump(config, f, indent=2)
   "
   ```

2. Generate and deploy configuration:
   ```bash
   make mcp-config CLIENT=claude_desktop
   ```

3. Restart Claude Desktop application

4. Check logs for successful connection:
   ```bash
   tail -f ~/Library/Logs/Claude/mcp-server-quilt.log
   ```

**Expected Results**:
- Configuration file contains valid MCP server entry
- Claude Desktop logs show successful server startup
- No ENOENT or path-related errors

### Test Case 2: Configuration Update

**Objective**: Verify existing MCP configurations are updated correctly

**Steps**:
1. Ensure existing MCP configuration exists
2. Run configuration update:
   ```bash
   make mcp-config CLIENT=claude_desktop
   ```
3. Restart Claude Desktop
4. Verify both old and new configurations work

**Expected Results**:
- Existing configurations preserved
- New Quilt MCP configuration added/updated
- No conflicts between MCP servers

### Test Case 3: Error Recovery

**Objective**: Test Claude Desktop behavior when MCP server is unavailable

**Steps**:
1. Configure Claude Desktop with valid MCP settings
2. Stop the MCP server (if running)
3. Start Claude Desktop
4. Observe error handling
5. Start MCP server
6. Check if Claude Desktop reconnects

**Expected Results**:
- Claude Desktop starts successfully even with failed MCP connection
- Appropriate error messages in logs
- Automatic reconnection when server becomes available

### Test Case 4: Functional Validation

**Objective**: Verify MCP commands work within Claude Desktop

**Steps**:
1. Ensure MCP server is connected successfully
2. Open Claude Desktop chat
3. Try MCP-related commands/features
4. Verify responses and functionality

**Expected Results**:
- MCP tools/resources available in Claude Desktop
- Commands execute successfully
- Appropriate responses returned

## Log Analysis

### Success Indicators

Look for these patterns in `~/Library/Logs/Claude/mcp-server-quilt.log`:

```
[info] Server started and connected successfully
[info] Message from client: {"method":"initialize","params":{"protocolVersion":"2025-06-18"
```

### Failure Indicators

Watch for these error patterns:

```
[error] spawn uv run quilt-mcp ENOENT
[error] Server disconnected
[info] Server transport closed unexpectedly
can't open file '//main.py'
Failed to spawn: `quilt-mcp`
```

### Automated Log Monitoring

```bash
# Real-time connection monitoring
python uat/scripts/log-analyzer.py --client claude_desktop --check-connection

# Detailed analysis with recent activity
python uat/scripts/log-analyzer.py --client claude_desktop
```

## Configuration Validation

### Verify Generated Configuration

```bash
# Check Claude Desktop configuration file
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | jq '.mcpServers.quilt'
```

Expected structure:
```json
{
  "command": "make",
  "args": ["-C", "app", "run"],
  "cwd": "/full/path/to/quilt-mcp-server",
  "env": {
    "QUILT_CATALOG_DOMAIN": "demo.quiltdata.com"
  },
  "description": "Quilt MCP Server"
}
```

### Validate Configuration Fields

```bash
python -c "
import json
from pathlib import Path

config_file = Path.home() / 'Library/Application Support/Claude/claude_desktop_config.json'
with open(config_file, 'r') as f:
    config = json.load(f)

quilt_config = config['mcpServers']['quilt']
assert quilt_config['command'] == 'make'
assert quilt_config['args'] == ['-C', 'app', 'run']
assert 'cwd' in quilt_config
assert 'QUILT_CATALOG_DOMAIN' in quilt_config['env']
print('✅ Configuration validation passed')
"
```

## Troubleshooting

### Common Issues

#### Issue: `spawn uv run quilt-mcp ENOENT`

**Cause**: Configuration using old command format
**Solution**: Regenerate configuration with new make-based approach:
```bash
make mcp-config CLIENT=claude_desktop
```

#### Issue: Path contains double slashes (`//`)

**Cause**: Incorrect path concatenation
**Solution**: Verify `cwd` field uses absolute path without trailing slash

#### Issue: Claude Desktop won't start

**Cause**: Invalid JSON in configuration file
**Solution**: 
```bash
# Validate JSON
python -c "import json; json.load(open('~/Library/Application Support/Claude/claude_desktop_config.json'))"

# Restore from backup if needed
cp ~/Library/Application\ Support/Claude/claude_desktop_config.json.backup ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

#### Issue: MCP server starts but no functionality

**Cause**: Client-server protocol mismatch
**Solution**:
1. Check MCP protocol version compatibility
2. Verify server implements expected MCP methods
3. Review server logs for initialization errors

### Recovery Procedures

#### Restore Original Configuration

```bash
# Restore from backup
cp ~/Library/Application\ Support/Claude/claude_desktop_config.json.backup ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

#### Remove MCP Configuration

```bash
# Remove only MCP servers, keep other settings
python -c "
import json
from pathlib import Path
config_file = Path.home() / 'Library/Application Support/Claude/claude_desktop_config.json'
with open(config_file, 'r') as f:
    config = json.load(f)
config.pop('mcpServers', None)
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)
print('MCP configuration removed')
"
```

## Test Checklist

Before considering Claude Desktop integration complete:

- [ ] Configuration generation works without errors
- [ ] Generated JSON is valid and contains required fields
- [ ] Claude Desktop starts successfully after configuration
- [ ] MCP server connection established (check logs)
- [ ] No ENOENT or path-related errors in logs
- [ ] MCP functionality works within Claude Desktop
- [ ] Error recovery works (server restart scenarios)
- [ ] Configuration updates don't break existing setup
- [ ] Backup and restore procedures work correctly

## Reporting Results

Use the provided tools to generate test reports:

```bash
# Generate comprehensive report
python uat/scripts/log-analyzer.py --client claude_desktop --report

# JSON output for automated processing
python uat/scripts/log-analyzer.py --client claude_desktop --report --json
```