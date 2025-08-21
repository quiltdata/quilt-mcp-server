# Quilt MCP Server

A local MCP (Model Context Protocol) server for accessing Quilt data with secure tools for package management, S3 operations, and system utilities.

## Quick Start

### For Claude Desktop Users

See **[build-dxt/assets/README.md](build-dxt/assets/README.md)** for downloading and installing the pre-built DXT extension.

### Manual Local Setup

1. **Configure environment:**

   ```bash
   cp env.example .env
   # Edit .env with your AWS credentials and Quilt settings (see env.example for options)
   make check-env
   ```

2. **Run local MCP server:**

   ```bash
   make app
   # Server runs on http://127.0.0.1:8000/mcp
   ```

3. **Configure your MCP client** (Claude Desktop, VS Code, etc.) to connect to:
   - **Server**: `http://127.0.0.1:8000/mcp`
   - **Method**: HTTP POST with JSON-RPC 2.0

### Remote Access (via ngrok)

For web apps or remote clients:

```bash
# Terminal 1: Start local server
make app

# Terminal 2: Expose via ngrok
make run-app-tunnel
# Use the ngrok HTTPS URL in your MCP client
```

## Available Tools

To see all available tools dynamically:

```bash
cd app && make run-inspector
# Opens MCP Inspector at http://127.0.0.1:6274
```

Or check **[CLAUDE.md](CLAUDE.md)** for detailed tool documentation and usage examples.

## Requirements

- **Python 3.11+** and [uv](https://docs.astral.sh/uv/)
- **AWS credentials** configured for S3 access
- **Docker** (optional, for containerization)

> **Note**: Claude Desktop uses Python from your login shell environment. Ensure Python 3.11+ is accessible via `python3` in your shell profile.
