# User Acceptance Testing (UAT) for MCP Server Auto-Configuration

This directory contains semi-automated tests and procedures for validating that the auto-configured MCP server works correctly with real clients in real-world scenarios.

## Purpose

While our automated tests verify that configurations are generated correctly and the server starts, UAT validates:
- **Real client integration**: Actual Claude Desktop, VS Code, Cursor behavior
- **Configuration reload**: How clients handle config changes
- **End-to-end workflows**: Complete user scenarios from config to MCP usage
- **Error recovery**: How clients handle server failures and reconnections

## Directory Structure

```
uat/
├── README.md           # This file - comprehensive testing guide
├── scripts/            # Semi-automated test scripts
│   ├── client-test.sh  # Test MCP client configurations
│   ├── log-analyzer.py # Parse and analyze MCP client logs
│   └── config-deploy.sh # Deploy and validate configurations
├── logs/               # Log analysis tools and patterns
│   ├── patterns.json   # Expected log patterns for success/failure
│   └── analysis.md     # Log analysis procedures
└── scenarios/          # User acceptance test scenarios
    ├── claude-desktop.md # Claude Desktop integration tests
    ├── vscode.md         # VS Code integration tests
    └── cursor.md         # Cursor integration tests
```

## Quick Start

### 1. Generate and Test MCP Configuration

```bash
# Generate configuration (automated)
make mcp-config

# Deploy to specific client (semi-automated)
./uat/scripts/config-deploy.sh claude_desktop

# Validate deployment (automated)
./uat/scripts/client-test.sh claude_desktop
```

### 2. Manual Validation Steps

1. **Restart the client** (Claude Desktop, VS Code, etc.)
2. **Check client logs** for successful MCP server connection
3. **Test MCP functionality** (e.g., try MCP commands in the client)
4. **Verify error handling** (stop server, restart, check reconnection)

### 3. Automated Log Analysis

```bash
# Analyze MCP client logs for success/failure patterns
python uat/scripts/log-analyzer.py --client claude_desktop --check-connection

# Generate test report
python uat/scripts/log-analyzer.py --report
```

## Test Categories

### Category 1: Configuration Deployment (Semi-Automated)

**Purpose**: Verify generated configurations work with real clients

**Process**:
1. **Automated**: Generate MCP config using `make mcp-config`
2. **Automated**: Deploy config to client configuration file
3. **Manual**: Restart client application
4. **Automated**: Parse client logs to verify successful connection
5. **Manual**: Test basic MCP functionality in client

**Success Criteria**: Client logs show successful MCP server connection and initialization

### Category 2: Server Robustness (Automated + Manual)

**Purpose**: Verify server handles real-world client connection patterns

**Process**:
1. **Automated**: Start MCP server using generated config
2. **Automated**: Simulate client connection/disconnection cycles
3. **Manual**: Force server restart while client is connected
4. **Automated**: Verify client reconnects successfully
5. **Automated**: Validate no data corruption or connection leaks

**Success Criteria**: Server maintains stability across connection cycles

### Category 3: Cross-Platform Validation (Manual)

**Purpose**: Verify auto-configuration works across different operating systems

**Process**:
1. **Manual**: Run `make mcp-config` on macOS, Windows, Linux
2. **Automated**: Validate generated paths are platform-appropriate
3. **Manual**: Test client integration on each platform
4. **Automated**: Parse logs from different platforms for consistency

**Success Criteria**: Configuration works identically across all supported platforms

## Client-Specific Procedures

### Claude Desktop

**Log Location**: `~/Library/Logs/Claude/mcp-server-quilt.log` (macOS)

**Success Pattern**: 
```
[info] Server started and connected successfully
[info] Message from client: {"method":"initialize",...}
```

**Failure Patterns**:
```
[error] spawn ... ENOENT
[error] Server disconnected
```

**Manual Test**: Try using Quilt MCP commands in Claude Desktop chat

### VS Code

**Log Location**: Developer Console in VS Code

**Success Pattern**: MCP server appears in VS Code's MCP extension status

**Manual Test**: Verify MCP commands available in VS Code command palette

### Cursor

**Log Location**: Similar to VS Code, check developer console

**Success Pattern**: MCP server listed in Cursor's MCP integration

**Manual Test**: Test MCP functionality within Cursor

## Automated Test Scripts

### `scripts/client-test.sh`

Tests MCP client configuration deployment and validation:

```bash
#!/bin/bash
# Test MCP client configuration
# Usage: ./client-test.sh <client_name>

CLIENT=$1
echo "Testing MCP configuration for $CLIENT..."

# 1. Generate config
make mcp-config BATCH=1 > /tmp/mcp-config.json

# 2. Validate JSON structure
python -c "import json; json.load(open('/tmp/mcp-config.json'))" || exit 1

# 3. Deploy config (if requested)
if [[ "$2" == "--deploy" ]]; then
    make mcp-config CLIENT=$CLIENT
fi

# 4. Test server startup with generated config
python uat/scripts/test-server-startup.py /tmp/mcp-config.json

echo "✅ MCP configuration test passed for $CLIENT"
```

### `scripts/log-analyzer.py`

Parses and analyzes MCP client logs:

```python
#!/usr/bin/env python3
"""
MCP Client Log Analyzer
Parses client logs and validates MCP server connection patterns
"""

import json
import argparse
from pathlib import Path

def analyze_claude_logs():
    """Analyze Claude Desktop logs for MCP connection success/failure"""
    log_file = Path.home() / "Library/Logs/Claude/mcp-server-quilt.log"
    # Implementation details...

def check_connection_success():
    """Check if MCP server connection was successful"""
    # Parse logs for success patterns
    # Return True/False + details

if __name__ == "__main__":
    # CLI interface for log analysis
    pass
```

## Integration with CI/CD

### Automated Testing Integration

Add to `.github/workflows/test.yml`:

```yaml
- name: Run UAT Automated Tests
  run: |
    # Run automated portions of UAT
    ./uat/scripts/client-test.sh claude_desktop
    ./uat/scripts/client-test.sh vscode
    python uat/scripts/log-analyzer.py --validate-patterns
```

### Manual Testing Checklist

Before releasing auto-configuration changes:

- [ ] Test `make mcp-config` generates valid configurations
- [ ] Deploy configurations to all supported clients
- [ ] Verify clients can connect to MCP server successfully
- [ ] Test basic MCP functionality in each client
- [ ] Verify error recovery (server restart, network issues)
- [ ] Cross-platform validation (if applicable)

## Troubleshooting

### Common Issues

1. **Client won't connect**: Check if client needs restart after config change
2. **Path errors**: Verify generated `cwd` and command paths are correct
3. **Permission errors**: Ensure client has permission to execute `make` commands
4. **Port conflicts**: Verify MCP server port isn't already in use

### Debug Commands

```bash
# Test generated config manually
make -C app run  # Should start MCP server successfully

# Check client logs
tail -f ~/Library/Logs/Claude/mcp-server-quilt.log

# Validate JSON structure
python -c "import json; print(json.load(open('config.json')))"
```

## Success Metrics

UAT is considered successful when:

1. **✅ All supported clients** can successfully connect using generated configurations
2. **✅ Server startup** works reliably across different environments  
3. **✅ Error recovery** handles common failure scenarios gracefully
4. **✅ Cross-platform** compatibility verified on target operating systems
5. **✅ Performance** meets acceptable connection/response time thresholds

## Contributing

When adding new MCP clients or changing auto-configuration logic:

1. **Add client-specific UAT procedures** in `scenarios/`
2. **Update automated test scripts** to include new clients
3. **Document expected log patterns** in `logs/patterns.json`
4. **Test manually** on at least one platform before submitting changes
5. **Update this README** with any new procedures or requirements

## Contact

For questions about UAT procedures or to report issues with client integration, please:

- Create an issue in the project repository
- Include relevant client logs and configuration details
- Specify operating system and client version information