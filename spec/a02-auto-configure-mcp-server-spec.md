# Auto-Configure MCP Server Specification

## Overview

This specification defines the behavior for automatically configuring local MCP (Model Context Protocol) server setup for common clients including Claude Desktop, VS Code, Cursor, and other MCP-compatible editors.

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

- Include current working directory context in configuration
- Allow customization of catalog domain (default: `demo.quiltdata.com`)
- Generate proper JSON structure compatible with MCP client expectations

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

### FR5: Flexible Usage Modes

**Behavior:** The system shall support both display-only and direct-modification modes

**Acceptance Criteria:**

- Display configuration entry when no specific action is requested
- Show all relevant configuration file locations for manual setup
- Allow direct modification of specified client configuration files
- Allow explicit file path specification to override client detection
- Provide success/failure feedback for file operations

### FR6: Make Target Integration

**Behavior:** The system shall integrate with the project's Make-based build system

**Acceptance Criteria:**

- Provide `make mcp_config` target in root Makefile
- Delegate to appropriate phase-specific Makefile
- Follow existing Makefile conventions and patterns
- Include help text in `make help` output

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

### NFR5: Implementation Strategy

- Survey existing GitHub solutions for bash testing, README validation, and auto-configuration
- Leverage existing tools and scripts where possible rather than building from scratch
- Prefer proven, maintained solutions over custom implementations
- Document any existing tools or patterns found during research

## Technical Specifications

### Command-Line Interface

```bash
# Display configuration entry and file locations
python -m quilt_mcp.auto_configure

# Add configuration to specific client
python -m quilt_mcp.auto_configure --client claude_desktop
python -m quilt_mcp.auto_configure --client cursor
python -m quilt_mcp.auto_configure --client vscode

# Add configuration to specific file path
python -m quilt_mcp.auto_configure --config-file /path/to/config.json

# Use development mode
python -m quilt_mcp.auto_configure --development

# Use custom catalog domain
python -m quilt_mcp.auto_configure --catalog-domain custom.quiltdata.com
```

### Make Target Integration

```bash
# Auto-configure for development
make mcp_config

# Auto-configure for specific client
make mcp_config CLIENT=claude_desktop

# Auto-configure with custom domain
make mcp_config DOMAIN=custom.quiltdata.com
```

### Configuration File Structure

Generated configuration entries shall follow this structure:

```json
{
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["quilt-mcp"],
      "env": {
        "QUILT_CATALOG_DOMAIN": "demo.quiltdata.com"
      },
      "description": "Quilt MCP Server"
    }
  }
}
```

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

## BDD Test Scenarios

### Scenario 1: Basic Configuration Generation

```gherkin
Given I want to generate an MCP server configuration
When I run the auto-configure script
Then it should generate a config with uvx command
And it should include the current working directory context
And it should use the default catalog domain
```

### Scenario 2: Development Mode Configuration

```gherkin
Given I want to generate a development configuration
When I run the auto-configure script with --development flag
Then it should generate a config with uv run command
And it should include development-appropriate settings
```

### Scenario 3: Cross-Platform File Location Detection

```gherkin
Given I am on a [macOS|Windows|Linux] system
When I request configuration file locations
Then it should return platform-appropriate paths
And it should include paths for all supported clients
```

### Scenario 4: Safe File Modification

```gherkin
Given an existing configuration file with other MCP servers
When I add the Quilt MCP server configuration
Then it should preserve the existing servers
And it should add the new Quilt server configuration
And the file should remain valid JSON
```

### Scenario 5: Error Handling

```gherkin
Given a configuration file with malformed JSON
When I attempt to add MCP configuration
Then it should detect the malformed JSON
And it should return an error without corrupting the file
And it should provide guidance for manual recovery
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
