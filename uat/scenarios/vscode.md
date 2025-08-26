# VS Code Integration Testing

This document provides comprehensive testing procedures for Quilt MCP server integration with Visual Studio Code.

## Prerequisites

- Visual Studio Code installed
- MCP extension for VS Code (if available)
- Quilt MCP server project set up locally
- Administrative access to modify VS Code settings

## Test Environment Setup

### 1. Backup Existing Configuration

```bash
# macOS
cp ~/Library/Application\ Support/Code/User/settings.json ~/Library/Application\ Support/Code/User/settings.json.backup

# Windows
cp "%APPDATA%\Code\User\settings.json" "%APPDATA%\Code\User\settings.json.backup"

# Linux
cp ~/.config/Code/User/settings.json ~/.config/Code/User/settings.json.backup
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

### 3. Check MCP Extension

1. Open VS Code
2. Go to Extensions (Cmd/Ctrl + Shift + X)
3. Search for "MCP" or "Model Context Protocol"
4. Install if available, or note if manual setup required

## Automated Testing

### Configuration Generation Test

```bash
# Generate VS Code configuration
make mcp-config CLIENT=vscode

# Verify configuration was applied
cat ~/Library/Application\ Support/Code/User/settings.json | jq '.mcpServers'
```

### Basic Validation Test

```bash
# Test configuration deployment
./uat/scripts/client-test.sh vscode --deploy

# Check if VS Code can parse the configuration
code --list-extensions | grep -i mcp
```

## Manual Testing Procedures

### Test Case 1: Fresh Configuration

**Objective**: Verify MCP server works with clean VS Code installation

**Steps**:
1. Remove existing MCP configuration:
   ```bash
   python -c "
   import json
   from pathlib import Path
   import platform
   
   if platform.system() == 'Darwin':
       config_file = Path.home() / 'Library/Application Support/Code/User/settings.json'
   elif platform.system() == 'Windows':
       config_file = Path.home() / 'AppData/Roaming/Code/User/settings.json'
   else:
       config_file = Path.home() / '.config/Code/User/settings.json'
   
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
   make mcp-config CLIENT=vscode
   ```

3. Restart VS Code

4. Check Developer Console for MCP-related messages:
   - Open Command Palette (Cmd/Ctrl + Shift + P)
   - Run "Developer: Toggle Developer Tools"
   - Check Console tab for MCP messages

**Expected Results**:
- Configuration file contains valid MCP server entry
- VS Code loads without configuration errors
- Developer Console shows MCP initialization (if MCP extension present)

### Test Case 2: MCP Extension Integration

**Objective**: Test integration with VS Code MCP extensions

**Steps**:
1. Ensure MCP configuration is deployed
2. Install any available MCP extension for VS Code
3. Restart VS Code
4. Check extension status and MCP server connection
5. Test MCP functionality within VS Code

**Expected Results**:
- MCP extension recognizes configuration
- Server connection established successfully
- MCP commands available in Command Palette

### Test Case 3: Settings UI Validation

**Objective**: Verify configuration appears correctly in VS Code settings

**Steps**:
1. Open VS Code Settings (Cmd/Ctrl + ,)
2. Search for "mcp" or "mcpServers"
3. Verify configuration appears in settings UI
4. Test editing configuration through UI

**Expected Results**:
- MCP settings visible in Settings UI
- Configuration matches generated values
- UI editing works correctly

### Test Case 4: Command Palette Integration

**Objective**: Test MCP command availability in VS Code

**Steps**:
1. Ensure MCP server is configured and running
2. Open Command Palette (Cmd/Ctrl + Shift + P)
3. Search for MCP-related commands
4. Test available MCP functionality

**Expected Results**:
- MCP commands appear in Command Palette
- Commands execute successfully
- Appropriate responses/results displayed

## Log Analysis

### VS Code Developer Console

Since VS Code doesn't have a dedicated MCP log file, use Developer Console:

1. **Open Developer Tools**:
   - Command Palette → "Developer: Toggle Developer Tools"
   - Or Help → "Toggle Developer Tools"

2. **Monitor Console Output**:
   ```javascript
   // Filter console for MCP messages
   // Look for messages containing "MCP", "mcp", or "mcpServers"
   ```

### Success Indicators

Look for these patterns in Developer Console:

```
MCP server connected successfully
mcpServers configuration loaded
Extension Host: MCP ready
MCP tools registered
```

### Failure Indicators

Watch for these error patterns:

```
MCP server connection failed
Error loading mcpServers configuration
MCP extension initialization failed
spawn ENOENT
Configuration parsing error
```

### Automated Analysis (Limited)

```bash
# VS Code doesn't provide log files, so automated analysis is limited
# Use manual inspection of Developer Console
echo "VS Code requires manual log inspection via Developer Console"
echo "See uat/scenarios/vscode.md for detailed procedures"
```

## Configuration Validation

### Verify Generated Configuration

```bash
# Check VS Code settings file (macOS)
cat ~/Library/Application\ Support/Code/User/settings.json | jq '.mcpServers.quilt'

# Windows
# cat "%APPDATA%\Code\User\settings.json" | jq '.mcpServers.quilt'

# Linux  
# cat ~/.config/Code/User/settings.json | jq '.mcpServers.quilt'
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

### Validate Configuration Integration

```bash
# Test VS Code can parse the configuration
code --version
echo "Check VS Code Settings UI for mcpServers section"
```

## Extension-Specific Testing

### MCP Extension Status

If MCP extension is installed:

1. **Check Extension Status**:
   - Extensions view → Find MCP extension
   - Verify it's enabled and active
   - Check for any error indicators

2. **Extension Settings**:
   - Right-click MCP extension → "Extension Settings"
   - Verify settings are accessible
   - Check for MCP server configuration options

3. **Extension Commands**:
   - Command Palette → Search for MCP commands
   - Test extension-provided functionality

### Custom MCP Integration

For manual MCP integration without dedicated extension:

1. **Workspace Configuration**:
   ```json
   // .vscode/settings.json in workspace
   {
     "mcpServers": {
       "quilt": {
         "command": "make",
         "args": ["-C", "app", "run"],
         "cwd": "${workspaceFolder}/../quilt-mcp-server",
         "env": {
           "QUILT_CATALOG_DOMAIN": "demo.quiltdata.com"
         }
       }
     }
   }
   ```

2. **Task Configuration**:
   ```json
   // .vscode/tasks.json
   {
     "version": "2.0.0",
     "tasks": [
       {
         "label": "Start Quilt MCP Server",
         "type": "shell",
         "command": "make",
         "args": ["-C", "app", "run"],
         "options": {
           "cwd": "${workspaceFolder}/../quilt-mcp-server"
         },
         "group": "build"
       }
     ]
   }
   ```

## Troubleshooting

### Common Issues

#### Issue: Configuration not recognized

**Cause**: MCP extension not installed or configuration in wrong location
**Solution**: 
1. Install MCP extension for VS Code
2. Verify configuration is in correct settings.json file
3. Check VS Code version compatibility

#### Issue: Server connection fails

**Cause**: Path or command issues in configuration
**Solution**:
```bash
# Test server manually
cd /path/to/quilt-mcp-server
make -C app run

# Verify configuration paths
python -c "
import json
from pathlib import Path
config_file = Path.home() / 'Library/Application Support/Code/User/settings.json'
with open(config_file, 'r') as f:
    config = json.load(f)
print(config['mcpServers']['quilt']['cwd'])
"
```

#### Issue: VS Code performance impact

**Cause**: MCP server consuming excessive resources
**Solution**:
1. Monitor server resource usage
2. Check for memory leaks or CPU spikes
3. Review MCP server implementation for efficiency

#### Issue: Settings UI doesn't show MCP configuration

**Cause**: Configuration format issues or VS Code version compatibility
**Solution**:
1. Validate JSON syntax in settings.json
2. Check VS Code version supports custom settings sections
3. Try workspace-level configuration instead

### Recovery Procedures

#### Restore Original Configuration

```bash
# Restore from backup (macOS)
cp ~/Library/Application\ Support/Code/User/settings.json.backup ~/Library/Application\ Support/Code/User/settings.json

# Windows
# cp "%APPDATA%\Code\User\settings.json.backup" "%APPDATA%\Code\User\settings.json"

# Linux
# cp ~/.config/Code/User/settings.json.backup ~/.config/Code/User/settings.json
```

#### Remove MCP Configuration Only

```bash
python -c "
import json
from pathlib import Path
import platform

if platform.system() == 'Darwin':
    config_file = Path.home() / 'Library/Application Support/Code/User/settings.json'
elif platform.system() == 'Windows':
    config_file = Path.home() / 'AppData/Roaming/Code/User/settings.json' 
else:
    config_file = Path.home() / '.config/Code/User/settings.json'

with open(config_file, 'r') as f:
    config = json.load(f)
config.pop('mcpServers', None)
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)
print('MCP configuration removed')
"
```

## Test Checklist

Before considering VS Code integration complete:

- [ ] Configuration generation works without errors
- [ ] Generated JSON is valid and contains required fields
- [ ] VS Code starts successfully after configuration
- [ ] Settings UI shows MCP configuration correctly
- [ ] Developer Console shows no configuration errors
- [ ] MCP extension (if installed) recognizes configuration
- [ ] MCP commands available in Command Palette (if applicable)
- [ ] Server connection works (manual testing required)
- [ ] No performance impact on VS Code startup/operation
- [ ] Backup and restore procedures work correctly

## Manual Validation Required

**Note**: Unlike Claude Desktop, VS Code MCP integration requires more manual validation because:

1. **No dedicated log files**: Must use Developer Console
2. **Extension dependency**: Functionality depends on MCP extension availability
3. **Variable integration**: MCP support varies by VS Code version and extensions

## Reporting Results

Since automated log analysis is limited for VS Code:

```bash
# Generate basic configuration validation
echo "VS Code MCP Configuration Status:"
echo "================================="

# Check if configuration exists
python -c "
import json
from pathlib import Path
import platform

if platform.system() == 'Darwin':
    config_file = Path.home() / 'Library/Application Support/Code/User/settings.json'
elif platform.system() == 'Windows':
    config_file = Path.home() / 'AppData/Roaming/Code/User/settings.json'
else:
    config_file = Path.home() / '.config/Code/User/settings.json'

try:
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    if 'mcpServers' in config and 'quilt' in config['mcpServers']:
        print('✅ MCP configuration present')
        print('✅ Quilt server configuration found')
    else:
        print('❌ MCP configuration missing')
except Exception as e:
    print(f'❌ Error reading configuration: {e}')
"

echo ""
echo "Manual verification required:"
echo "1. Check VS Code Developer Console for MCP messages"
echo "2. Verify MCP extension status (if applicable)"
echo "3. Test MCP functionality in VS Code interface"
```