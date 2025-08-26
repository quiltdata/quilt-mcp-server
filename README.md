# Quilt MCP Server

A secure MCP (Model Context Protocol) server for accessing Quilt data repositories. Provides 13 tools for package management, S3 operations, and system utilities - designed for seamless integration with Claude Desktop, Cursor, VS Code, and other MCP-compatible editors.

## Quick Start

### Option 1: Claude Desktop (DXT) - Recommended ✨

The easiest way to use this MCP server is via the packaged DXT:

1. **Download the DXT**

   ```bash
   # Visit GitHub releases page and download:
   # quilt-mcp-<version>.dxt
   # check-prereqs.sh (optional)
   ```

   Visit GitHub releases page and download:
   - quilt-mcp-VERSION.dxt
   - check-prereqs.sh (optional)

2. **Install in Claude Desktop**
   - Double‑click the `.dxt` file, or
   - Claude Desktop → Settings → Extensions → Install from File

3. **Configure catalog domain**
   - Settings → Extensions → Quilt MCP
   - Set your catalog domain (e.g., `demo.quiltdata.com`)

4. **Verify installation**

   ```text
   In Claude: "List Quilt packages" → Check Tools panel shows Quilt MCP
   ```

### Option 2: Auto-Configure for Local Development 🚀

For development or when you have a local clone:

```bash
# Clone and setup
git clone https://github.com/quiltdata/quilt-mcp-server.git
cd quilt-mcp-server
cp env.example .env  # Edit with your settings

# Generate configuration for your editor
make mcp_config

# Follow the generated instructions to add to your editor
```

The `make mcp_config` command will:

- Generate proper MCP configuration for local development
- Show configuration file locations for all supported editors
- Optionally add configuration directly to your editor settings

**Supported editors:** Claude Desktop, Cursor, VS Code

### Option 3: Manual Configuration

If you prefer manual setup or need custom configuration:

```bash
# Install via uvx (no local setup needed)
uvx quilt-mcp

# Or run from local development clone
cd quilt-mcp-server
uv run quilt-mcp
```

## Configuration Examples

### Auto-Configure Commands

```bash
# Generate and display configuration for all editors
make mcp_config

# Generate with custom catalog domain
QUILT_CATALOG_DOMAIN=custom.quiltdata.com make mcp_config

# Add configuration directly to specific editor
python -m quilt_mcp.auto_configure --client cursor
python -m quilt_mcp.auto_configure --client claude_desktop
python -m quilt_mcp.auto_configure --client vscode

# Add to custom configuration file
python -m quilt_mcp.auto_configure --config-file /path/to/config.json
```

### Manual Configuration (if needed)

**Local Development (recommended for contributors):**

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

**Production/Installed (via uvx):**

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

### Configuration File Locations

| Platform | Editor | Configuration File |
|----------|--------|-------------------|
| macOS | Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| macOS | Cursor | `~/Library/Application Support/Cursor/User/settings.json` |
| macOS | VS Code | `~/Library/Application Support/Code/User/settings.json` |
| Windows | Claude Desktop | `%APPDATA%/Claude/claude_desktop_config.json` |
| Windows | Cursor | `%APPDATA%/Cursor/User/settings.json` |
| Windows | VS Code | `%APPDATA%/Code/User/settings.json` |
| Linux | Claude Desktop | `~/.config/claude/claude_desktop_config.json` |
| Linux | Cursor | `~/.config/Cursor/User/settings.json` |
| Linux | VS Code | `~/.config/Code/User/settings.json` |

## Features & Tools

### Available MCP Tools (13 total)

**Package Management:**

- `packages_list` - List packages with filtering
- `packages_search` - Search using ElasticSearch
- `package_browse` - Examine package contents
- `package_contents_search` - Search within packages
- `package_create` - Create packages from S3 objects
- `package_update` - Update packages with new files
- `package_delete` - Remove packages

**S3 Operations:**

- `bucket_objects_list` - List S3 objects
- `bucket_object_info` - Get object metadata
- `bucket_object_text` - Read text content
- `bucket_objects_put` - Upload objects
- `bucket_object_fetch` - Download objects

**System Tools:**

- `auth_check` - Verify authentication
- `filesystem_check` - Check environment

### Requirements

- **Python 3.11+** (required for all usage modes)
- **uv package manager** (for development)
- **Quilt catalog access** (configure via `QUILT_CATALOG_DOMAIN`)
- **AWS CLI configured** (for S3 operations)

> **Note:** Claude Desktop requires Python 3.11+ in your login shell environment, not just virtual environments.

## Configuration

### Environment Setup

```bash
# Copy and edit environment configuration
cp env.example .env
```

Edit `.env` with your Quilt settings:

```bash
# Required: Your Quilt catalog domain
QUILT_CATALOG_DOMAIN=demo.quiltdata.com

# Optional: Default S3 bucket for operations
QUILT_DEFAULT_BUCKET=s3://your-quilt-bucket

# Optional: Test package for validation
QUILT_TEST_PACKAGE=yournamespace/testpackage
QUILT_TEST_ENTRY=README.md
```

### AWS Configuration

For S3 operations, ensure AWS CLI is configured:

```bash
aws configure
# OR set AWS_PROFILE environment variable
```

## Development Commands

### Local Development

```bash
# Run MCP server locally
make app                          # Local server on http://127.0.0.1:8000/mcp

# Generate editor configuration
make mcp_config                   # Auto-configure for local development

# Testing and validation
make test                         # Run all tests
make coverage                     # Run tests with coverage (≥85%)
make validate                     # SPEC-compliant validation
```

### Configuration & Setup

```bash
make check-env                    # Validate .env configuration
make init-app                     # Check preconditions
make clean                        # Clean build artifacts
```

### Advanced (Production Deployment)

```bash
make build                        # Docker containerization
make catalog                      # ECR registry operations  
make deploy                       # ECS Fargate deployment
make destroy                      # Clean up AWS resources
```

## Testing & Verification

### Manual Testing

```bash
# Test local MCP server
curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Run comprehensive tests
make test
make coverage
```

### Integration with Editors

After configuration, test in your editor:

1. **Claude Desktop:** Open Tools panel, verify "Quilt MCP" appears
2. **Cursor:** Use Command Palette → "MCP: List Servers"
3. **VS Code:** Check MCP extension status

Try a simple command: "List Quilt packages" or "Show me the auth status"

## Troubleshooting

### Common Issues

**Python not found (Claude Desktop):**

```bash
# Ensure Python 3.11+ is in your login shell
python3 --version  # Should show 3.11+

# Download and run check-prereqs.sh from releases
./check-prereqs.sh
```

**Configuration not working:**

```bash
# Verify configuration was added correctly
make mcp_config

# Check file exists and is valid JSON
cat ~/.config/claude/claude_desktop_config.json | jq .
```

**MCP tools not appearing:**

- Restart your editor after configuration changes
- Check that `QUILT_CATALOG_DOMAIN` is set correctly
- Verify network access to your Quilt catalog

### Getting Help

- Review generated configuration: `make mcp_config`
- Test local server: `make app` then test endpoint
- Check logs and error messages in your editor's MCP settings
- Ensure AWS CLI is configured for S3 operations

---

## Architecture & Deployment

This repository supports both local development usage (covered above) and production deployment to AWS ECS Fargate with JWT authentication. For production deployment, Docker containerization, ECR operations, and AWS infrastructure management, see the [deployment documentation](docs/DEPLOYMENT.md) and use the advanced Make targets listed in the Development Commands section.
