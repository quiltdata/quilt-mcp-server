# Auto-Configure MCP Server Specification

## Overview

This specification defines the behavior for automatically configuring **local development** MCP (Model Context Protocol) server setup for common clients including Claude Desktop, VS Code, Cursor, and other MCP-compatible editors.

**Scope:** This specification covers **local development usage only** - running the MCP server directly from a git repository clone using `uv run`. Production usage via packaged installation (e.g., `uvx install quilt-mcp`) is covered by separate issue #67.

**GitHub Issue:** #60 - Auto-configure local MCP server for common clients (Claude Desktop, VS Code, Cursor, etc.)

## Problem Statement

The existing README's instructions for manually configuring a local MCP server are:

- **Duplicative** - Same configuration repeated across multiple client documentation
- **Incomplete** - Missing edge cases and error handling scenarios
- **Manual** - Requires users to manually edit JSON configuration files with risk of syntax errors
- **Incorrect** - It doesn't have the proper commands / make targets for actually running the server.

Users need a streamlined and accurate way to configure their local MCP server that reduces friction and potential configuration errors.

## Functional Requirements

### FR0: Accurate, Concise README

The README needs to:

1. Be optimized for end users seeking to simply install/run the Quilt MCP server
1. Prioritize the DXT, then autoconfig, then manual invocation
1. Be completely accurate and tested

### FR1: Configuration Entry Generation

**Behavior:** The system shall generate valid MCP server configuration entries

**Acceptance Criteria:**

- Include current working directory context in configuration (automatically set `cwd` to project root)
- Allow customization of catalog domain via command line flag, environment variable, or .env file
- Generate proper JSON structure compatible with MCP client expectations
- Configuration must use `uv run quilt-mcp` command for local development

### FR2: Multi-Client Support  

**Behavior:** The system shall support multiple MCP client configurations

**Acceptance Criteria:**

- Support Claude Desktop configuration file locations
- Support VS Code configuration file locations
- Support Cursor configuration file locations
- Detect appropriate configuration file paths based on operating system

### FR3: Cross-Platform Compatibility

**Behavior:** The system shall work across different operating systems

**Acceptance Criteria:**

- Handle macOS configuration file locations (`~/Library/Application Support/...`)
- Handle Windows configuration file locations (`%APPDATA%/...`)
- Handle Linux/Unix configuration file locations (`~/.config/...`)
- Gracefully handle platform detection failures

### FR4: File System Operations

**Behavior:** The system shall safely modify existing configuration files

**Acceptance Criteria:**

- Create new configuration files if they don't exist
- Preserve existing configuration when adding MCP server entries
- Handle malformed JSON files gracefully without data loss
- Create necessary parent directories automatically
- Provide clear error messages for permission issues

### FR5: Interactive Auto-Detection and Configuration

**Behavior:** The system shall intelligently detect existing client configurations and offer interactive modification

**Acceptance Criteria:**

- **Auto-detect existing client config files** on the current OS and report their status (exists/missing)
- **Interactive mode**: When no specific action is requested, prompt user to select which detected clients to configure
- **Batch mode**: Support non-interactive flag for scripting/CI usage
- **Smart client discovery**: Check all known client locations and show which clients are installed
- **Direct modification**: Offer to directly edit detected configuration files with user confirmation
- **Rollback capability**: Create backups before modification and offer rollback on errors
- **Progress feedback**: Show clear success/failure status for each configuration operation

### FR6: Externalized Client Configuration

**Behavior:** The system shall support externalized client definitions for easy extensibility

**Acceptance Criteria:**

- **Client definitions file**: Store client configurations (paths, formats, detection logic) in external JSON/YAML file
- **Easy extensibility**: Adding new MCP clients should only require updating the config file, not code changes
- **Version compatibility**: Support different client versions with different config file locations
- **Custom client support**: Allow users to define custom client configurations via config file
- **Validation**: Validate client configuration schema on startup

### FR7: Make Target Integration

**Behavior:** The system shall integrate with the project's Make-based build system

**Acceptance Criteria:**

- **Interactive by default**: `make mcp-config` runs in interactive mode, detecting and prompting for client selection
- **Non-interactive support**: `make mcp-config BATCH=1` for CI/scripting usage
- **Client-specific targets**: `make mcp-config CLIENT=claude_desktop` for direct client configuration
- **Delegate to app phase**: Follow existing Makefile delegation patterns
- **Include help text**: Update `make help` output with new interactive capabilities

## Non-Functional Requirements

### NFR1: Error Handling

- Gracefully handle file permission errors
- Provide meaningful error messages for troubleshooting
- Never corrupt existing configuration files
- Fail safely without side effects

### NFR2: Testing Requirements

- 100% test coverage on auto-configure module
- Comprehensive BDD tests covering all behavioral scenarios
- Cross-platform testing using mocked platform detection
- File system operations tested using temporary files
- Integration testing with make targets

### NFR3: User Experience

- Clear, actionable output messages
- Minimal command-line interface complexity
- Self-documenting help text and usage examples
- No destructive operations without explicit user consent

### NFR4: Documentation Testing

- README must include testable bash code examples
- Implement bash doctests to validate all README command examples
- Integrate bash doctests into CI pipeline or provide local testing capability
- All README commands must be verified to work as documented

**Implementation Plan (Based on Research):**

- **Primary Solution: Runme** - Modern tool for extracting and executing bash commands from Markdown
  - Provides CLI + GitHub Action for CI integration
  - Prevents documentation bitrot through automated testing
  - Can execute commands directly from README.md files
- **Alternative: Bats-core** - Proven bash testing framework with strong CI integration
- **Integration**: Add Runme GitHub Action to existing CI pipeline in `.github/workflows/`

### NFR5: Implementation Strategy

- Survey existing GitHub solutions for bash testing, README validation, and auto-configuration ✅
- Leverage existing tools and scripts where possible rather than building from scratch ✅
- Prefer proven, maintained solutions over custom implementations ✅
- Document any existing tools or patterns found during research ✅

**Research Findings:**

**Bash Testing Solutions Identified:**

1. **Runme** - Modern documentation testing platform
   - Parses and executes bash commands from Markdown
   - Built-in CI/CD integration capabilities
   - Prevents documentation drift through automated testing
   - Available as CLI tool and GitHub Action
2. **Bats-core** - Established bash testing framework
   - TAP-compliant testing for bash scripts
   - Strong ecosystem and CI integration
   - Can be used to test extracted markdown commands
3. **markdown-doctest** - JavaScript-focused but provides patterns for other languages

**Make Target Integration Pattern:**

- Existing `app/Makefile` follows consistent `.PHONY` declaration pattern
- Help text format: `make <target> - Description`
- Execution pattern: `@export PYTHONPATH="$(PWD)" && uv run python -m <module>`
- `mcp-config` target should follow: `@export PYTHONPATH="$(PWD)" && uv run python -m quilt_mcp.auto_configure`

## Technical Specifications

### Command-Line Interface

```bash
# Interactive mode: Auto-detect clients and prompt for selection
python -m quilt_mcp.auto_configure

# Non-interactive mode: Display config without prompts
python -m quilt_mcp.auto_configure --batch

# Configure specific detected client directly
python -m quilt_mcp.auto_configure --client claude_desktop

# List all detectable clients and their status
python -m quilt_mcp.auto_configure --list-clients

# Add configuration to specific file path (bypass auto-detection)
python -m quilt_mcp.auto_configure --config-file /path/to/config.json

# Use custom catalog domain with any mode:
python -m quilt_mcp.auto_configure --catalog-domain custom.quiltdata.com  # CLI flag
QUILT_CATALOG_DOMAIN=custom.quiltdata.com python -m quilt_mcp.auto_configure  # Environment variable
# OR set QUILT_CATALOG_DOMAIN in .env file and use common.sh integration

# Rollback last configuration changes (if backup exists)
python -m quilt_mcp.auto_configure --rollback
```

**Interactive Mode Behavior:**

1. Auto-detects all client config files on current OS
2. Shows status: "✅ Found" / "❌ Missing" / "⚠️  Invalid JSON"  
3. Prompts user to select which clients to configure
4. Creates backups before modification
5. Shows success/failure for each operation

### Make Target Integration

```bash
# Interactive mode: Auto-detect and prompt for client selection  
make mcp-config

# Non-interactive mode: Display config only (for CI/scripts)
make mcp-config BATCH=1

# Configure specific client directly
make mcp-config CLIENT=claude_desktop

# List detectable clients and their status
make mcp-config LIST=1

# Use with custom catalog domain
QUILT_CATALOG_DOMAIN=custom.quiltdata.com make mcp-config

# Rollback last changes
make mcp-config ROLLBACK=1
```

**Note:** All Make targets use interactive mode by default. Use BATCH=1 for non-interactive usage in CI/scripts.

### Configuration File Structure

Generated configuration entries shall follow this structure:

```json
{
  "mcpServers": {
    "quilt": {
      "command": "uv",
      "args": ["run", "quilt-mcp"],
      "cwd": "/path/to/quilt-mcp-server",
      "env": {
        "QUILT_CATALOG_DOMAIN": "demo.quiltdata.com"
      },
      "description": "Quilt MCP Server"
    }
  }
}
```

**Key Requirements:**

- `command`: Must be `"uv"` for local development
- `args`: Must be `["run", "quilt-mcp"]` for local development  
- `cwd`: Must point to the project root directory (where `pyproject.toml` exists)
- `env.QUILT_CATALOG_DOMAIN`: User-configurable via CLI flag, environment variable, or .env file

### File Location Mapping

| Platform | Client | Configuration File Path |
|----------|---------|------------------------|
| macOS | Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| macOS | Cursor | `~/Library/Application Support/Cursor/User/settings.json` |
| macOS | VS Code | `~/Library/Application Support/Code/User/settings.json` |
| Windows | Claude Desktop | `%APPDATA%/Claude/claude_desktop_config.json` |
| Windows | Cursor | `%APPDATA%/Cursor/User/settings.json` |
| Windows | VS Code | `%APPDATA%/Code/User/settings.json` |
| Linux | Claude Desktop | `~/.config/claude/claude_desktop_config.json` |
| Linux | Cursor | `~/.config/Cursor/User/settings.json` |
| Linux | VS Code | `~/.config/Code/User/settings.json` |

### Client Configuration File

The system shall use an external configuration file to define client specifications:

**Location:** `app/quilt_mcp/clients.json`

**Structure:**

```json
{
  "clients": {
    "claude_desktop": {
      "name": "Claude Desktop",
      "config_type": "mcp_servers",
      "platforms": {
        "Darwin": "~/Library/Application Support/Claude/claude_desktop_config.json",
        "Windows": "%APPDATA%/Claude/claude_desktop_config.json", 
        "Linux": "~/.config/claude/claude_desktop_config.json"
      },
      "detection": {
        "check_executable": ["claude", "Claude Desktop.app"],
        "check_directory": true
      }
    },
    "cursor": {
      "name": "Cursor", 
      "config_type": "mcp_servers",
      "platforms": {
        "Darwin": "~/Library/Application Support/Cursor/User/settings.json",
        "Windows": "%APPDATA%/Cursor/User/settings.json",
        "Linux": "~/.config/Cursor/User/settings.json"
      },
      "detection": {
        "check_executable": ["cursor"],
        "check_directory": true  
      }
    },
    "vscode": {
      "name": "VS Code",
      "config_type": "mcp_servers", 
      "platforms": {
        "Darwin": "~/Library/Application Support/Code/User/settings.json",
        "Windows": "%APPDATA%/Code/User/settings.json",
        "Linux": "~/.config/Code/User/settings.json"
      },
      "detection": {
        "check_executable": ["code"],
        "check_directory": true
      }
    }
  }
}
```

**Benefits:**

- Easy to add new clients without code changes
- Supports platform-specific paths and detection logic
- Enables community contributions for additional clients
- Version-specific client support can be added via separate entries

## BDD Test Scenarios

### Scenario 1: Interactive Auto-Detection and Configuration

```gherkin
Given I have Claude Desktop and Cursor installed on my system
When I run the auto-configure script in interactive mode
Then it should auto-detect both client config files
And it should show "✅ Found" for existing config files
And it should show "❌ Missing" for non-existent config files  
And it should prompt me to select which clients to configure
And it should create backups before modifying any files
And it should show success/failure status for each operation
```

### Scenario 2: Non-Interactive Batch Mode

```gherkin
Given I want to use auto-configure in a CI script
When I run the auto-configure script with --batch flag
Then it should display the generated config without prompts
And it should not attempt to modify any files
And it should exit cleanly for scripting usage
```

### Scenario 3: Client-Specific Direct Configuration

```gherkin
Given I want to configure only Claude Desktop
When I run the auto-configure script with --client claude_desktop
Then it should detect the Claude Desktop config file location
And it should configure only that client without prompting
And it should create a backup before modification
```

### Scenario 4: Client Status Listing

```gherkin
Given I want to see which MCP clients are available on my system
When I run the auto-configure script with --list-clients flag
Then it should show all supported clients for my platform
And it should indicate which config files exist
And it should show which clients are actually installed
And it should not modify any configuration files
```

### Scenario 5: Rollback Functionality

```gherkin
Given I have previously modified client configuration files
When I run the auto-configure script with --rollback flag
Then it should detect existing backup files
And it should restore the original configuration files
And it should show success/failure status for each rollback operation
And it should clean up backup files after successful rollback
```

### Scenario 6: Externalized Client Configuration

```gherkin
Given the client definitions are stored in an external JSON file
When I add a new client to the clients.json file
Then the auto-configure script should detect the new client
And it should support the new client without code changes
And it should validate the client configuration schema
```

### Scenario 7: Safe File Modification with Backup

```gherkin
Given an existing configuration file with other MCP servers
When I configure the Quilt MCP server
Then it should create a backup of the original file
And it should preserve the existing servers
And it should add the new Quilt server configuration  
And the file should remain valid JSON
And it should offer rollback if the operation fails
```

### Scenario 8: Error Handling and Recovery

```gherkin
Given a configuration file with malformed JSON
When I attempt to configure the MCP server
Then it should detect the malformed JSON
And it should show a clear error message
And it should not attempt to modify the file
And it should suggest manual recovery steps
```

## Integration Test Requirements

### IT1: Make Target Integration

- Verify `make mcp_config` executes successfully
- Verify integration with existing Makefile structure
- Test parameter passing through Make variables

### IT2: Real File System Integration

- Test actual file creation and modification (in isolated test environment)
- Verify directory creation behavior
- Test permission handling on different filesystems

### IT3: Client Configuration Compatibility

- Validate generated configurations work with actual MCP clients
- Test configuration loading in supported editors
- Verify environment variable handling

## Implementation Notes

### Module Structure

- `quilt_mcp.auto_configure` - Main module containing all functionality
- Command-line interface using `argparse`
- Platform detection using `platform.system()`
- JSON handling with proper error recovery
- Path handling using `pathlib.Path`

### Error Recovery Strategy

- Never overwrite files that cannot be parsed as JSON
- Always create backup copies of configuration files before modification
- Provide rollback capability for failed operations
- Log all file operations for debugging

### Security Considerations

- Validate all file paths to prevent directory traversal
- Ensure proper file permissions are maintained
- Never execute or evaluate user-provided content
- Sanitize all input parameters

## Success Criteria

This specification is considered successfully implemented when:

1. All BDD test scenarios pass with 100% coverage
2. Integration tests validate real-world usage
3. Make target integration works seamlessly
4. Cross-platform compatibility is verified
5. Error handling scenarios are thoroughly tested
6. Documentation is complete and accurate

## Future Considerations

### Potential Enhancements

- Support for additional MCP clients as they emerge
- Configuration validation and health checking
- Automated backup and restore functionality
- GUI-based configuration tool
- Integration with package managers for auto-installation

### Backward Compatibility

- Maintain compatibility with existing manual configuration approaches
- Support legacy configuration file formats during transition period
- Provide migration utilities for existing setups
