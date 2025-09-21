<!-- markdownlint-disable MD013 MD025 -->
# Requirements Analysis - Issue #180: quilt-mcp run

**GitHub Issue**: #180
**Title**: quilt-mcp run
**Author**: drernie
**Status**: OPEN

## Problem Statement

The current `quilt-mcp` CLI entry point only provides a single server execution mode without offering users the flexibility and control needed for different use cases. Users need a comprehensive CLI interface that supports server operation, inspection, configuration management, and authentication workflows.

## User Stories

### 1. Server Operation

**As a** developer integrating Quilt MCP server
**I want** to run the server in stdio mode by default
**So that** I can easily integrate it with MCP clients without additional configuration

**As a** developer debugging integrations
**I want** to run the server with different transports and logging levels
**So that** I can troubleshoot connection and communication issues

### 2. Tool Inspection

**As a** developer implementing MCP client integrations
**I want** to inspect and dump all available tool information
**So that** I can understand the server's capabilities and plan my integrations

**As a** documentation writer
**I want** to export tool schemas and descriptions
**So that** I can create comprehensive integration guides

### 3. Configuration Management

**As a** system administrator
**I want** to configure catalog settings and logging levels
**So that** I can optimize the server for my environment

**As a** developer
**I want** to detect compatible MCP clients and add server configurations
**So that** I can streamline the setup process for my development environment

### 4. Authentication Management

**As a** user needing access to private Quilt data
**I want** to authenticate with Quilt services through the CLI
**So that** I can access restricted catalogs and packages

### 5. Help and Discoverability

**As a** new user of the Quilt MCP server
**I want** to see available commands and usage information
**So that** I can quickly understand how to use the tool

## Acceptance Criteria

### 1. Default Behavior (run command)

- [ ] `quilt-mcp run` starts server in stdio mode by default
- [ ] Server uses existing `run_server()` functionality for MCP compliance
- [ ] All existing tool registration and configuration is preserved
- [ ] Error handling maintains existing robustness

### 2. Tool Inspection (inspect command)

- [ ] `quilt-mcp inspect` outputs comprehensive tool information
- [ ] Output includes tool names, descriptions, and parameter schemas
- [ ] Output format is human-readable and machine-parseable (JSON)
- [ ] Covers all registered tools from existing tool modules

### 3. Configuration Management (config command)

- [ ] `quilt-mcp config --catalog <catalog>` sets catalog configuration [prompts user if not present]
- [ ] `quilt-mcp config --log-level <level>` configures logging verbosity [default error]
- [ ] `quilt-mcp config --yes` enables non-interactive mode
- [ ] Always display generic client configuration json
- [ ] Command detects compatible MCP clients (Claude Desktop, Continue, etc.)
- [ ] Prompts user (unless --yes) to add server configuration to detected clients

### 4. Authentication (auth command)

- [ ] `quilt-mcp auth` initiates Quilt catalog authentication flow
- [ ] Uses existing `quilt3.login()` functionality
- [ ] Provides clear feedback on authentication status
- [ ] Handles authentication errors gracefully

### 5. Help System (help command)

- [ ] `quilt-mcp help` shows comprehensive usage information
- [ ] `quilt-mcp` with no arguments shows help by default
- [ ] Each subcommand supports `--help` flag
- [ ] Help text is clear, actionable, and includes examples

### 6. Cross-Platform Compatibility

- [ ] All commands work on macOS, Linux, and Windows
- [ ] Client detection works across different operating systems
- [ ] File path handling is platform-appropriate
- [ ] Configuration file locations follow platform conventions

## Implementation Approach

### CLI Framework

- Utilize Python's `click` for robust command-line parsing
- DO NOT NEED TO Maintain backward compatibility with existing `quilt-mcp` script
- Follow established CLI patterns for subcommands and options

### Configuration Strategy

- Detect MCP client configurations in standard locations
- Support common clients: Claude Desktop, Continue, others
- Generate appropriate JSON configurations for each client type
- Provide preview mode for configuration changes

### Tool Inspection Design

- Leverage existing `register_tools()` functionality to enumerate tools
- Extract metadata from function signatures and docstrings
- Support both human-readable and JSON output formats
- Include examples and usage guidance where available

## Success Criteria

1. **Usability**: New users can set up Quilt MCP server in under 5 minutes
2. **Compatibility**: All existing integrations continue to work unchanged
3. **Discoverability**: Tool capabilities are easily discoverable through inspection
4. **Automation**: Configuration can be applied automatically to detected clients
5. **Reliability**: All commands handle errors gracefully with helpful messages

## Open Questions

1. **Client Detection Priority**: Which MCP clients should be prioritized for detection and configuration?
    1. Claude Code. VS Code. Cursor. ChatGPT Desktop.
2. **Configuration Format**: What specific JSON schema should be used for each supported client?
    1. Use CLI tools (eg. `claude` if present), else ~/.mcp.json, else lookup.
3. **Catalog Parameter**: How should the `--catalog` parameter integrate with existing Quilt authentication?
    1. It is required; must config before running auth user flow
4. **Tool Output Format**: Should tool inspection support multiple output formats (JSON, YAML, plain text)?
    1. NO. Just dump as human-formmatted JSON.
5. **Configuration Storage**: Should CLI settings be persisted locally, and if so, where?
    1. Not separately; auth and config do that implicitly.
6. **Version Compatibility**: How should the CLI handle different versions of MCP clients?
    1. Expect latest; prioritize simplicitly over completeness.
7. **Logging Integration**: How should CLI logging levels integrate with FastMCP and Quilt logging?
    1. Look at the code: how is `logger` used? error | info | warning | debug
