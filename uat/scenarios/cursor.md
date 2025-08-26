# Cursor Integration Testing

This document provides comprehensive testing procedures for Quilt MCP server integration with Cursor IDE.

## Prerequisites

- Cursor IDE installed
- MCP extension for Cursor (if available)
- Quilt MCP server project set up locally
- Administrative access to modify Cursor settings

## Test Environment Setup

### 1. Backup Existing Configuration

```bash
# macOS
cp ~/Library/Application\ Support/Cursor/User/settings.json ~/Library/Application\ Support/Cursor/User/settings.json.backup

# Windows
cp "%APPDATA%\Cursor\User\settings.json" "%APPDATA%\Cursor\User\settings.json.backup"

# Linux
cp ~/.config/Cursor/User/settings.json ~/.config/Cursor/User/settings.json.backup
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

1. Open Cursor
2. Go to Extensions (Cmd/Ctrl + Shift + X)
3. Search for "MCP" or "Model Context Protocol"
4. Install if available, or note if manual setup required

## Automated Testing

### Configuration Generation Test

```bash
# Generate Cursor configuration
make mcp-config CLIENT=cursor

# Verify configuration was applied
cat ~/Library/Application\ Support/Cursor/User/settings.json | jq '.mcpServers'
```

### Basic Validation Test

```bash
# Test configuration deployment
./uat/scripts/client-test.sh cursor --deploy

# Check if Cursor can parse the configuration
cursor --list-extensions | grep -i mcp
```

## Manual Testing Procedures

### Test Case 1: Fresh Configuration

**Objective**: Verify MCP server works with clean Cursor installation

**Steps**:
1. Remove existing MCP configuration:
   ```bash
   python -c "
   import json
   from pathlib import Path
   import platform
   
   if platform.system() == 'Darwin':
       config_file = Path.home() / 'Library/Application Support/Cursor/User/settings.json'
   elif platform.system() == 'Windows':
       config_file = Path.home() / 'AppData/Roaming/Cursor/User/settings.json'
   else:
       config_file = Path.home() / '.config/Cursor/User/settings.json'
   
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
   make mcp-config CLIENT=cursor
   ```

3. Restart Cursor

4. Check Developer Console for MCP-related messages:
   - Open Command Palette (Cmd/Ctrl + Shift + P)
   - Run "Developer: Toggle Developer Tools"
   - Check Console tab for MCP messages

**Expected Results**:
- Configuration file contains valid MCP server entry
- Cursor loads without configuration errors
- Developer Console shows MCP initialization (if MCP extension present)

### Test Case 2: MCP Extension Integration

**Objective**: Test integration with Cursor MCP extensions

**Steps**:
1. Ensure MCP configuration is deployed
2. Install any available MCP extension for Cursor
3. Restart Cursor
4. Check extension status and MCP server connection
5. Test MCP functionality within Cursor

**Expected Results**:
- MCP extension recognizes configuration
- Server connection established successfully
- MCP commands available in Command Palette

### Test Case 3: AI Chat Integration

**Objective**: Test MCP server integration with Cursor's AI chat features

**Steps**:
1. Ensure MCP server is configured and running
2. Open Cursor's AI chat interface
3. Test if MCP tools/resources are available in AI context
4. Verify AI can access Quilt MCP functionality

**Expected Results**:
- AI chat recognizes MCP server
- Quilt MCP tools available to AI assistant
- Successful execution of MCP commands through AI

### Test Case 4: Settings UI Validation

**Objective**: Verify configuration appears correctly in Cursor settings

**Steps**:
1. Open Cursor Settings (Cmd/Ctrl + ,)
2. Search for "mcp" or "mcpServers"
3. Verify configuration appears in settings UI
4. Test editing configuration through UI

**Expected Results**:
- MCP settings visible in Settings UI
- Configuration matches generated values
- UI editing works correctly

## Log Analysis

### Cursor Developer Console

Since Cursor doesn't have a dedicated MCP log file, use Developer Console:

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
MCP extension loaded
AI context: MCP tools available
MCP server ready for requests
```

### Failure Indicators

Watch for these error patterns:

```
MCP server connection failed
Error loading mcpServers configuration
MCP extension initialization failed
spawn ENOENT
AI context: MCP server unavailable
```

### Automated Analysis (Limited)

```bash
# Cursor doesn't provide log files, so automated analysis is limited
# Use manual inspection of Developer Console
echo "Cursor requires manual log inspection via Developer Console"
echo "See uat/scenarios/cursor.md for detailed procedures"
```

## Configuration Validation

### Verify Generated Configuration

```bash
# Check Cursor settings file (macOS)
cat ~/Library/Application\ Support/Cursor/User/settings.json | jq '.mcpServers.quilt'

# Windows
# cat "%APPDATA%\Cursor\User\settings.json" | jq '.mcpServers.quilt'

# Linux  
# cat ~/.config/Cursor/User/settings.json | jq '.mcpServers.quilt'
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
# Test Cursor can parse the configuration
cursor --version
echo "Check Cursor Settings UI for mcpServers section"
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

### AI Integration Testing

Cursor's primary MCP integration is through AI features:

1. **AI Chat MCP Access**:
   - Open AI chat panel
   - Check if MCP tools appear in AI context
   - Test AI's ability to use MCP functions

2. **Code Generation with MCP**:
   - Request AI to use Quilt-specific functionality
   - Verify AI can access Quilt catalog through MCP
   - Test code generation using MCP resources

3. **Inline AI Features**:
   - Test if inline AI suggestions can use MCP
   - Verify MCP context is available for code completion

## Cursor-Specific Features

### 1. AI Composer Integration

Test MCP integration with Cursor's AI Composer:

```bash
# This requires manual testing within Cursor UI
echo "Manual test required:"
echo "1. Open AI Composer in Cursor"
echo "2. Check if Quilt MCP tools are available"
echo "3. Test using MCP functionality through Composer"
```

### 2. Chat Panel Integration

Test MCP server availability in Cursor's chat panel:

```bash
echo "Manual test required:"
echo "1. Open Cursor chat panel"
echo "2. Ask AI to list available MCP tools"
echo "3. Test Quilt-specific MCP commands"
```

### 3. Code Actions Integration

Test if MCP tools appear in Cursor's code actions:

```bash
echo "Manual test required:"
echo "1. Right-click in code editor"
echo "2. Check if MCP-based code actions are available"
echo "3. Test Quilt-specific code actions"
```

## Troubleshooting

### Common Issues

#### Issue: MCP not available in AI chat

**Cause**: MCP server not connected or AI integration disabled
**Solution**: 
1. Verify MCP server is running: `make -C app run`
2. Check Developer Console for connection errors
3. Restart Cursor after configuration changes
4. Verify AI features are enabled in Cursor settings

#### Issue: Configuration not recognized

**Cause**: MCP extension not installed or configuration in wrong location
**Solution**: 
1. Install MCP extension for Cursor (if available)
2. Verify configuration is in correct settings.json file
3. Check Cursor version compatibility with MCP

#### Issue: AI can't access MCP tools

**Cause**: MCP server connection issues or permission problems
**Solution**:
```bash
# Test server connectivity
cd /path/to/quilt-mcp-server
make -C app run

# Check configuration
python -c "
import json
from pathlib import Path
config_file = Path.home() / 'Library/Application Support/Cursor/User/settings.json'
with open(config_file, 'r') as f:
    config = json.load(f)
print('MCP Config:', config.get('mcpServers', {}))
"
```

#### Issue: Performance impact on AI features

**Cause**: MCP server consuming excessive resources
**Solution**:
1. Monitor server resource usage during AI interactions
2. Check for memory leaks in MCP server
3. Optimize MCP server response times
4. Consider MCP server caching strategies

### Recovery Procedures

#### Restore Original Configuration

```bash
# Restore from backup (macOS)
cp ~/Library/Application\ Support/Cursor/User/settings.json.backup ~/Library/Application\ Support/Cursor/User/settings.json

# Windows
# cp "%APPDATA%\Cursor\User\settings.json.backup" "%APPDATA%\Cursor\User\settings.json"

# Linux
# cp ~/.config/Cursor/User/settings.json.backup ~/.config/Cursor/User/settings.json
```

#### Remove MCP Configuration Only

```bash
python -c "
import json
from pathlib import Path
import platform

if platform.system() == 'Darwin':
    config_file = Path.home() / 'Library/Application Support/Cursor/User/settings.json'
elif platform.system() == 'Windows':
    config_file = Path.home() / 'AppData/Roaming/Cursor/User/settings.json' 
else:
    config_file = Path.home() / '.config/Cursor/User/settings.json'

with open(config_file, 'r') as f:
    config = json.load(f)
config.pop('mcpServers', None)
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)
print('MCP configuration removed')
"
```

## Test Checklist

Before considering Cursor integration complete:

- [ ] Configuration generation works without errors
- [ ] Generated JSON is valid and contains required fields
- [ ] Cursor starts successfully after configuration
- [ ] Settings UI shows MCP configuration correctly
- [ ] Developer Console shows no configuration errors
- [ ] MCP extension (if installed) recognizes configuration
- [ ] AI chat can access MCP tools and resources
- [ ] MCP functionality works through AI Composer
- [ ] No performance impact on Cursor's AI features
- [ ] Code actions integration works (if applicable)
- [ ] Backup and restore procedures work correctly

## Manual Validation Required

**Note**: Cursor MCP integration requires extensive manual validation because:

1. **No dedicated log files**: Must use Developer Console
2. **AI-centric integration**: Primary MCP usage is through AI features
3. **Extension dependency**: Functionality may depend on MCP extension availability
4. **Evolving features**: Cursor's MCP support is rapidly evolving

## Cursor-Specific Testing Scenarios

### Scenario 1: AI-Driven Development Workflow

Test complete development workflow using MCP:

1. **Project Setup**: Use AI to initialize project with Quilt MCP
2. **Code Generation**: AI generates code using Quilt resources via MCP
3. **Data Access**: AI accesses Quilt catalog through MCP tools
4. **Code Review**: AI reviews code with Quilt context via MCP

### Scenario 2: Interactive Data Exploration

Test data exploration workflow:

1. **Catalog Browsing**: Use AI to browse Quilt catalog via MCP
2. **Package Discovery**: AI helps discover relevant data packages
3. **Data Analysis**: AI generates analysis code using MCP resources
4. **Visualization**: AI creates visualizations with Quilt data

### Scenario 3: Collaborative Development

Test collaborative features with MCP:

1. **Shared Context**: Multiple developers use same MCP configuration
2. **AI Consistency**: AI provides consistent Quilt-related suggestions
3. **Knowledge Sharing**: MCP enables sharing Quilt catalog knowledge

## Reporting Results

Since automated log analysis is limited for Cursor:

```bash
# Generate basic configuration validation
echo "Cursor MCP Configuration Status:"
echo "==============================="

# Check if configuration exists
python -c "
import json
from pathlib import Path
import platform

if platform.system() == 'Darwin':
    config_file = Path.home() / 'Library/Application Support/Cursor/User/settings.json'
elif platform.system() == 'Windows':
    config_file = Path.home() / 'AppData/Roaming/Cursor/User/settings.json'
else:
    config_file = Path.home() / '.config/Cursor/User/settings.json'

try:
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    if 'mcpServers' in config and 'quilt' in config['mcpServers']:
        print('✅ MCP configuration present')
        print('✅ Quilt server configuration found')
        quilt_config = config['mcpServers']['quilt']
        print(f'✅ Command: {quilt_config.get(\"command\", \"missing\")}')
        print(f'✅ Args: {quilt_config.get(\"args\", \"missing\")}')
        print(f'✅ Working directory: {quilt_config.get(\"cwd\", \"missing\")}')
    else:
        print('❌ MCP configuration missing')
except Exception as e:
    print(f'❌ Error reading configuration: {e}')
"

echo ""
echo "Manual verification required:"
echo "1. Check Cursor Developer Console for MCP messages"
echo "2. Test AI chat access to MCP tools"
echo "3. Verify MCP functionality in AI Composer"
echo "4. Test code actions integration (if applicable)"
```