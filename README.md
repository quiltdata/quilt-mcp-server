# Quilt MCP Server

MCP server for Quilt data catalog - search, analyze, and manage data packages with 84+ tools.

[![Tests](https://github.com/quiltdata/quilt-mcp-server/actions/workflows/push.yml/badge.svg)](https://github.com/quiltdata/quilt-mcp-server/actions/workflows/push.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE.txt)

## Quick Start

### 1. Terminal (Direct)

```bash
# Run directly with uvx (requires uv: https://docs.astral.sh/uv/)
# Default deployment is "local" (platform + stdio)
uvx quilt-mcp

# Other deployment modes
uvx quilt-mcp --deployment remote  # platform + http
uvx quilt-mcp --deployment legacy  # quilt3 + stdio

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
  -e QUILT_REGISTRY_URL=https://registry.your-catalog.quiltdata.com \
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
        "QUILT_CATALOG_URL": "https://quilt-stack.yourcompany.com",
        "QUILT_REGISTRY_URL": "https://registry.quilt-stack.yourcompany.com"
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

By default, quilt-mcp uses the **local deployment mode** (`--deployment local`), which uses the platform backend and requires:

- `QUILT_CATALOG_URL`
- `QUILT_REGISTRY_URL`
- authentication (`quilt3 login` session)

Use deployment presets:

```bash
uvx quilt-mcp --deployment remote  # platform + http
uvx quilt-mcp --deployment local   # platform + stdio (default)
uvx quilt-mcp --deployment legacy  # quilt3 + stdio
```

`QUILT_DEPLOYMENT` env var can set the same modes:

```bash
QUILT_DEPLOYMENT=remote uvx quilt-mcp
QUILT_DEPLOYMENT=local uvx quilt-mcp
QUILT_DEPLOYMENT=legacy uvx quilt-mcp
```

Remote Docker + ngrok testing hack (for Claude.ai without OAuth):

```bash
make run-docker-remote
# Starts Docker container on localhost:8000 with auto-injected real JWT fallback
# Launches MCP Inspector at http://127.0.0.1:6274 for testing
# JWT discovery priority: PLATFORM_TEST_JWT_TOKEN -> quilt3 login session
#
# In another terminal, expose via ngrok:
ngrok http 8000 --domain=$NGROK_DOMAIN
```

Set `NGROK_DOMAIN` in `.env`, and configure Claude MCP URL as `https://<your-ngrok-domain>/mcp`.
Use this only for local development/testing.

Backward compatibility:
- `--backend` still works as an explicit backend override.
- `QUILT_MULTIUSER_MODE` is still supported as a legacy selector.

See `docs/AUTHENTICATION.md` for full configuration details and examples.

### Environment Variables

Override defaults via environment or MCP config:

- `QUILT_CATALOG_URL` - Your Quilt catalog URL (e.g., `https://your-catalog.quiltdata.com`)
- `QUILT_REGISTRY_URL` - Your Quilt registry URL (e.g., `https://registry.your-catalog.quiltdata.com`)
- `QUILT_DEPLOYMENT` - Deployment mode (`remote`, `local`, `legacy`)
- `QUILT_MULTIUSER_MODE` - Legacy backend selector (true -> platform, false -> quilt3)
- `AWS_PROFILE` - AWS credentials profile for S3 access (if not default)
- `QUILT_SERVICE_TIMEOUT` - HTTP timeout for service calls in seconds (default: 60)

## Architecture

Multiuser Mode (Production)

- Stateless: No server-side workflows or templates
- JWT auth: Catalog-issued JWTs only (claims: `id`, `uuid`, `exp`)
- Read/write operations go through the catalog API
- Horizontally scalable: any number of containers
- Single tenant per deployment (no tenant tracking)

Local Dev Mode

- Stateful: File-based storage in `~/.quilt/`
- IAM auth: Uses AWS credentials or quilt3 session
- Full feature set, including workflows
- Single-user development and testing

## Core Package Tools

| Tool | Operation | Backend path |
|---|---|---|
| `package_create` | Create package revision from S3 objects | `QuiltOps.create_package_revision()` |
| `package_update` | Update existing package revision | `QuiltOps.update_package_revision()` |
| `package_delete` | Delete package revisions | `QuiltOps.delete_package()` |

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
make test-func
make test-e2e
```

### Testing Infrastructure

The Quilt MCP Server includes a comprehensive testing framework (`quilt_mcp.testing`) for automated test generation and execution:

- **Automatic Test Generation**: Discovers tools, infers arguments, generates YAML configurations
- **Intelligent Classification**: Categorizes tools by effect (create/update/remove) and requirements
- **Tool Loop Execution**: Multi-step workflows for testing write operations (create → modify → verify → cleanup)
- **Comprehensive Validation**: Result validation, coverage analysis, failure pattern detection

**Quick Start**:

```bash
# Generate test configuration
make test-mcp-setup

# Run all MCP tests
make test-mcp

# Run specific test suites
uv run scripts/mcp-test.py --tools          # Test tools only
uv run scripts/mcp-test.py --resources      # Test resources only
uv run scripts/mcp-test.py --loops          # Test tool loops only
uv run scripts/mcp-test.py --idempotent-only # Test read-only operations

# Run with selectors
uv run scripts/mcp-test.py --tools-select "bucket_list,package_list"
```

**Module Structure**:

- `src/quilt_mcp/testing/` - Testing framework library (4,644 lines)
- `scripts/mcp-test.py` - Test execution script (1,599 lines)
- `scripts/mcp-test-setup.py` - Test generation script (302 lines)

See [Testing Framework Documentation](src/quilt_mcp/testing/README.md) for detailed API documentation and usage patterns.

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
