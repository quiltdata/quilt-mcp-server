# Quilt MCP Server

MCP server for Quilt data catalog - search, analyze, and manage data packages with 84+ tools.

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

### 3. Claude Code CLI

```bash
# Add to Claude Code CLI with environment variables
npx @anthropic-ai/claude-code mcp add quilt-mcp uvx quilt-mcp \
  -e QUILT_CATALOG_DOMAIN=your-catalog.quiltdata.com \
  -e AWS_PROFILE=your-profile
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

### Authentication

**quilt-mcp uses quilt3 for authentication.** Configure once, use everywhere:

```bash
# Configure catalog and authenticate (interactive)
quilt3 config

# Or set directly
quilt3 config https://your-catalog.quiltdata.com

# Login (opens browser for SSO, or prompts for credentials)
quilt3 login
```

Your credentials are stored in `~/.quilt/` and automatically used by quilt-mcp.

### Environment Variables

Override defaults via environment or MCP config:

- `QUILT_CATALOG_DOMAIN` - Your Quilt catalog URL (e.g., `your-catalog.quiltdata.com`)
- `QUILT_DEFAULT_BUCKET` - Default S3 bucket (e.g., `s3://your-bucket`)
- `AWS_PROFILE` - AWS credentials profile for S3 access

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

## Troubleshooting

### SyntaxWarning from jsonlines

You may see this warning during installation:

```text
SyntaxWarning: invalid escape sequence '\*'
```

**This is harmless.** It's from the `jsonlines` dependency (via `quilt3`) and doesn't affect functionality.
The warning appears on Python 3.12+ due to deprecated escape sequences in the library's docstrings.

## Support

- [GitHub Issues](https://github.com/quiltdata/quilt-mcp-server/issues)
- [Quilt Support](support@quilt.bio)

## License

Apache 2.0 - See [LICENSE.txt](LICENSE.txt)
