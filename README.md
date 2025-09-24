# Quilt MCP Server

MCP server for Quilt data catalog - search, analyze, and manage data packages with 84+ tools. Features comprehensive permission management with tool-based access control for secure AWS operations.

[![Tests](https://github.com/quiltdata/quilt-mcp-server/actions/workflows/push.yml/badge.svg)](https://github.com/quiltdata/quilt-mcp-server/actions/workflows/push.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE.txt)

## Quick Start

### 1. Terminal (Direct)

```bash
# Run directly with uvx (requires uv: https://docs.astral.sh/uv/)
uvx quilt-mcp

# Or install globally
uv tool install quilt-mcp
quilt-mcp
```

### 2. Claude Desktop (One-Click)

1. Download `.mcpb` from [releases](https://github.com/quiltdata/quilt-mcp-server/releases)
2. Double-click to install or drag to Claude Desktop
3. Configure catalog in Settings → Extensions → Quilt MCP

### 3. Claude CLI

```bash
# One-liner setup
npx @anthropic/claude-cli mcp add quilt-mcp
```

### 4. Custom MCP Clients

Add to your `mcp.json`:

```json
{
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["quilt-mcp"],
      "env": {
        "QUILT_CATALOG_DOMAIN": "quilt-stack.yourcompany.com"
      }
    }
  }
}
```

## Configuration

Set via environment or MCP config:

- `QUILT_CATALOG_DOMAIN` - Your Quilt catalog URL
- `QUILT_DEFAULT_BUCKET` - Default S3 bucket
- `AWS_PROFILE` - AWS credentials profile

## Permission Management

The MCP server features a comprehensive permission system that provides fine-grained access control for AWS operations:

### Key Features

- **Tool-Based Permissions**: Each MCP tool has specific AWS permissions mapped to it
- **Role-Based Access Control**: Flexible role definitions with tool-based permissions
- **JWT Token Authentication**: Secure authentication using OAuth2 bearer tokens
- **Self-Service Debugging**: Tools to validate permissions and discover available operations

### Permission Tools

- `validate_tool_access(tool_name, bucket_name)` - Check if you can use a specific tool
- `list_available_tools()` - See all available tools and your permissions
- `get_user_permissions()` - Get your current authorization level

### Supported Roles

- **ReadWriteQuiltV2-sales-prod**: Full access to sales production buckets
- **ReadOnlyQuilt**: Read-only access to sandbox bucket
- **AdminQuilt**: Administrative access to all buckets

For detailed information, see [Comprehensive Permission Scheme](./docs/architecture/COMPREHENSIVE_PERMISSION_SCHEME.md).

## Development

```bash
# Clone and setup
git clone https://github.com/quiltdata/quilt-mcp-server.git
cd quilt-mcp-server

# Install and run
uv sync
make run

# Test
make test
```

## Documentation

- [MCP Protocol](https://modelcontextprotocol.io)
- [Quilt Documentation](https://docs.quiltdata.com)
- [API Reference](./docs/api.md)
- [Contributing](./docs/developer/CONTRIBUTING.md)

## Support

- [GitHub Issues](https://github.com/quiltdata/quilt-mcp-server/issues)
- [Quilt Support](support@quilt.bio)

## License

Apache 2.0 - See [LICENSE.txt](LICENSE.txt)
