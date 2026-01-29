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
  -e QUILT_CATALOG_URL=https://your-catalog.quiltdata.com \
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
        "QUILT_CATALOG_URL": "https://quilt-stack.yourcompany.com"
      }
    }
  }
}
```

## Configuration

Configure or refresh quilt3 credentials with:

```bash
# Configure catalog and authenticate (interactive)
quilt3 config

# Or set directly
quilt3 config https://your-stack.your-company.com

# Login (opens browser for SSO, or prompts for credentials)
quilt3 login
```

By default, quilt-mcp uses IAM credentials from your environment, AWS profiles, or quilt3 sessions.

For multitenant deployments, enable **JWT mode** by setting `MCP_REQUIRE_JWT=true`. In JWT mode the server requires
`Authorization: Bearer <token>` on every request and assumes AWS roles based on JWT claims.

See `docs/AUTHENTICATION.md` for full configuration details and examples.

### Environment Variables

Override defaults via environment or MCP config:

- `QUILT_CATALOG_URL` - Your Quilt catalog URL (e.g., `https://your-catalog.quiltdata.com`)
- `AWS_PROFILE` - AWS credentials profile for S3 access (if not default)
- `QUILT_SERVICE_TIMEOUT` - HTTP timeout for service calls in seconds (default: 60)
- `MCP_REQUIRE_JWT` - Enable JWT auth mode (true/false, default: false)
- `MCP_JWT_SECRET` - HS256 shared secret for JWT validation (JWT mode)
- `MCP_JWT_SECRET_SSM_PARAMETER` - SSM parameter name for JWT secret (JWT mode)
- `MCP_JWT_ISSUER` - Expected JWT issuer (optional)
- `MCP_JWT_AUDIENCE` - Expected JWT audience (optional)

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
- [Quilt Documentation](https://docs.quilt.bio)
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
