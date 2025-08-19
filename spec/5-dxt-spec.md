# DXT Specification for Quilt MCP Server

## Overview

Package the Quilt MCP server as a Claude Desktop Extension (DXT) to enable one-click installation for Claude Desktop users, eliminating the need for Python/AWS/Docker knowledge.

## Technical Architecture

### Package Structure

```tree
quilt-mcp.dxt (ZIP archive)
├── manifest.json         # DXT configuration and metadata
├── server/               # MCP server implementation
│   ├── app/              # Existing app/ directory
│   ├── requirements.txt  # Python dependencies
│   └── main.py           # Entry point
├── python/               # Bundled Python runtime (optional)
├── dependencies/         # All required packages/libraries
└── icon.png              # Quilt logo

### Manifest Configuration

```json
{
  "dxt_version": "0.1",
  "name": "quilt-mcp",
  "version": "1.0.0",
  "description": "Access Quilt data packages through Claude Desktop",
  "server": {
    "type": "python",
    "entry_point": "server/main.py",
    "mcp_config": {
      "command": "python",
      "args": ["${__dirname}/server/main.py"],
      "transport": "stdio"
    }
  },
  "user_config": [
    {
      "name": "catalog_domain",
      "type": "string",
      "label": "Quilt Catalog Domain",
      "description": "Your organization's Quilt catalog domain",
      "required": true
    },
    {
      "name": "aws_profile",
      "type": "string", 
      "label": "AWS Profile",
      "description": "AWS profile for authentication (optional)",
      "required": false
    }
  ]
}
```

## Implementation Strategy

### Phase 1: Basic DXT (stdio transport)

- **Transport**: stdio (simplest for DXT integration)
- **Dependencies**: Bundle all Python packages in archive
- **Configuration**: Basic catalog domain input
- **Authentication**: Use system AWS credentials with graceful fallback

### Phase 2: Enhanced Configuration

- **User Interface**: Configuration fields for catalog domain and AWS profile
- **Credential Detection**: Runtime validation of AWS credentials with clear error messages
- **Fallback Modes**: List-only mode when search credentials unavailable

### Phase 3: Advanced Features

- **Auto-detection**: Discover available AWS profiles automatically
- **Enhanced Error Handling**: Detailed troubleshooting for common setup issues
- **Optional HTTP Mode**: Debug transport for development

## Configuration Management

### AWS Credentials

- Check standard locations: `~/.aws/credentials`, environment variables, IAM roles
- Validate credentials at runtime with informative error messages
- Graceful degradation: disable search features if credentials unavailable

### Quilt3 Configuration

- Detect existing quilt3 config in user's home directory
- Provide configuration wizard for first-time users
- Support both CLI-configured and programmatic authentication

### Transport Selection

- **Default**: stdio (no port conflicts, direct Claude integration)
- **Alternative**: HTTP server for debugging and development
- **Configuration**: Allow transport override via manifest user config

## Build Process

### Development Workflow

```bash
# Build DXT locally during development
make build-dxt

# Test DXT installation
make test-dxt-install

# Validate DXT functionality
make validate-dxt
```

### CI/CD Integration

- Automated DXT building on PR merge
- Release artifacts include .dxt file and installation README
- Cross-platform testing (macOS, Windows, Linux)

## User Experience

### Installation Process

1. Download `quilt-mcp.dxt` from releases
2. Double-click to install in Claude Desktop
3. Configure catalog domain in Claude Desktop settings
4. Optionally specify AWS profile

### Runtime Behavior

- Automatic credential detection and validation
- Clear error messages for missing or invalid credentials
- Seamless integration with Claude Desktop's MCP system

## Success Criteria

### Technical Requirements
-  Single-file installation (.dxt archive)
-  No external dependencies required on user system
-  Responds correctly to MCP `tools/list` and `tools/call`
-  Proper AWS authentication with user's existing credentials
-  Works on clean systems without pre-installed Python/dependencies

### User Experience Requirements  
-  One-click installation in Claude Desktop
-  Clear configuration interface for catalog settings
-  Informative error messages for common issues
-  Documentation for end-user installation and troubleshooting

### Quality Assurance
-  Automated CI testing for DXT generation and installation
-  Cross-platform compatibility testing
-  Integration testing with Claude Desktop

## Advantages of DXT Packaging

- **Eliminates complexity**: No AWS/Docker/Python knowledge required
- **Consistent deployment**: Same package works across all environments
- **Maintains security**: Uses system AWS configuration, no credentials in package
- **Preserves functionality**: All existing MCP tools remain available
- **Standard integration**: Native Claude Desktop extension system
