# Quilt MCP Server

A secure MCP (Model Context Protocol) server for accessing Quilt data with JWT authentication, deployed on AWS ECS Fargate.

## Quick Start

```bash
# Setup environment
cp env.example .env
# Edit .env with your AWS configuration

# Validate environment
make check-env

# Run locally
make app

# Run MCP optimization (NEW!)
python optimize_mcp.py

# Full deployment pipeline
make validate
```

## 🚀 NEW: MCP Optimization System

This server now includes an **autonomous optimization system** that can:

- 🔍 **Analyze Performance**: Automatically detect optimization opportunities
- ⚡ **Improve Efficiency**: Reduce tool calls and response times by 25-50%
- 🧪 **Test Real Scenarios**: Comprehensive testing with real-world workflows
- 🤖 **Self-Optimize**: Autonomous improvements without manual intervention
- 📊 **Provide Insights**: Detailed analytics and actionable recommendations

### Quick Optimization

```bash
# Run immediate optimization analysis
python optimize_mcp.py

# Run comprehensive analysis with all test scenarios  
python optimize_mcp.py analyze
```

See [MCP Optimization Documentation](docs/MCP_OPTIMIZATION.md) for complete details.

## Using with Claude Desktop (DXT)

The easiest way to use this MCP server in Claude Desktop is via the packaged DXT.

1) Download the latest `.dxt` from the project releases
   - Open the repository releases in your browser
   - Download `quilt-mcp-<version>.dxt`
   - Optional: download and run `check-prereqs.sh` to verify your system

2) Install the DXT
   - Double‑click the `.dxt` file, or in Claude Desktop open Settings → Extensions → Install from File and pick the `.dxt`

3) Configure the catalog domain
   - In Claude Desktop Settings → Extensions → Quilt MCP, set your Quilt catalog domain (e.g. `demo.quiltdata.com`)
   - Ensure Python 3.11+ is available on your user PATH (see Requirements)

4) Verify in Claude
   - In a new chat, open the Tools panel and confirm Quilt MCP is listed
   - Try a tool, e.g. “list Quilt packages”

Screenshots (to be added once captured/approved):

![Claude Desktop – Install DXT](docs/images/claude-install-dxt.png)
![Claude Desktop – Configure Extension](docs/images/claude-configure-extension.png)

Troubleshooting
- Run `./check-prereqs.sh` from the release assets to validate Python and environment
- If Python isn’t detected, ensure `python3 --version` reports 3.11+ in your login shell

## Using with Cursor

You can run the MCP server locally and point Cursor to it.

Run the server with uv (pick one):

```bash
# Run in-repo (development)
uv run quilt-mcp

# Or run via uvx (no local install needed)
uvx quilt-mcp
```

Configure Cursor to launch the server (GUI or JSON):

- Cursor Settings → MCP (or Command Palette → “MCP: Configure Servers”) → Add New Server
  - Command: `uvx`
  - Args: `quilt-mcp`
  - Working directory: repository root (optional)

Or add JSON to your Cursor settings (example):

```json
{
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["quilt-mcp"],
      "env": {
        "QUILT_CATALOG_DOMAIN": "demo.quiltdata.com"
      }
    }
  }
}
```

Screenshot (to be added once captured/approved):

![Cursor – MCP Server Configuration](docs/images/cursor-mcp-config.png)

## Using with VS Code

For VS Code assistants that support MCP servers, configure a command‑based server entry pointing to this CLI.

Run the server with uv (pick one):

```bash
# Development
uv run quilt-mcp

# Ephemeral
uvx quilt-mcp
```

Example MCP server configuration (JSON) for extensions that support `mcpServers`:

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

Screenshot (to be added once captured/approved):

![VS Code – MCP Server Configuration](docs/images/vscode-mcp-config.png)

## Architecture

This project uses a **4-phase deployment pipeline**:

```tree
fast-mcp-server/
├── app/           # Phase 1: Local MCP server (Python)
├── build-docker/  # Phase 2: Docker containerization  
├── catalog-push/  # Phase 3: ECR registry operations
├── deploy-aws/    # Phase 4: ECS/ALB deployment
└── shared/        # Common utilities (validation, testing)
```

Each phase is **atomic** and **testable** independently, following SPEC.md validation requirements.

## MCP Tools

This server provides 13 secure tools for Quilt data operations:

### Package Management

- **`packages_list`** - List packages in a registry with optional filtering
- **`packages_search`** - Search packages using ElasticSearch  
- **`package_browse`** - Examine package contents and structure
- **`package_contents_search`** - Search within a specific package
- **`package_create`** - Create new packages from S3 objects
- **`package_update`** - Update existing packages with new files
- **`package_delete`** - Remove packages from registry

### S3 Operations

- **`bucket_objects_list`** - List objects in S3 buckets
- **`bucket_object_info`** - Get metadata for specific objects
- **`bucket_object_text`** - Read text content from objects
- **`bucket_objects_put`** - Upload objects to S3
- **`bucket_object_fetch`** - Download object data

### System Tools

- **`auth_check`** - Verify Quilt authentication status
- **`filesystem_check`** - Check system environment details

## Requirements

- **AWS Account** with CLI configured  
- **Python 3.11+** in user's login environment (required for Claude Desktop usage)
- **[uv](https://docs.astral.sh/uv/) package manager** for development
- **Docker** for containerization
- **IAM Policy ARN** for S3 access to your Quilt buckets

> **Note**: Claude Desktop uses Python from your user's login shell environment, not from virtual environments. Ensure Python 3.11+ is accessible via `python3` in your shell profile (.bashrc, .zshrc, etc.).

## Configuration

```bash
# Copy and edit environment configuration
cp env.example .env
make check-env
```

Edit `.env` with your settings:

```bash
# AWS Configuration (auto-derived from AWS CLI if not set)
CDK_DEFAULT_ACCOUNT=123456789012
CDK_DEFAULT_REGION=us-east-1
AWS_PROFILE=default

# ECR Configuration (auto-constructed if not set)
ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com
ECR_REPOSITORY=quilt-mcp

# Quilt Configuration
QUILT_CATALOG_DOMAIN=your-catalog-domain.com
QUILT_DEFAULT_BUCKET=s3://your-quilt-bucket
QUILT_TEST_PACKAGE=yournamespace/testpackage
QUILT_TEST_ENTRY=README.md
```

## Makefile Commands

### Phase Commands

```bash
make app                          # Phase 1: Run local MCP server
make build                        # Phase 2: Build Docker container
make catalog                      # Phase 3: Push to ECR registry
make deploy                       # Phase 4: Deploy to ECS Fargate
```

### Validation Commands (SPEC-compliant)

```bash
make validate                     # Validate all phases sequentially
make validate-app                 # Validate Phase 1 only
make validate-build               # Validate Phase 2 only
make validate-catalog             # Validate Phase 3 only
make validate-deploy              # Validate Phase 4 only
```

### Testing Commands

```bash
make test-app                     # Phase 1 testing only
make test-build                   # Phase 2 testing only
make test-deploy                  # Phase 4 testing only
make coverage                     # Run tests with coverage (fails if <85%)
```

### Verification Commands (MCP Endpoint Testing)

```bash
make verify-app                   # Verify Phase 1 MCP endpoint
make verify-build                 # Verify Phase 2 MCP endpoint
make verify-catalog               # Verify Phase 3 MCP endpoint
make verify-deploy                # Verify Phase 4 MCP endpoint
```

### Initialization & Cleanup

```bash
make init-app                     # Check Phase 1 preconditions
make init-build                   # Check Phase 2 preconditions
make init-catalog                 # Check Phase 3 preconditions
make init-deploy                  # Check Phase 4 preconditions

make zero-app                     # Stop Phase 1 processes
make zero-build                   # Stop Phase 2 containers
make zero-catalog                 # Stop Phase 3 containers
make zero-deploy                  # Disable Phase 4 endpoint (preserve stack)
```

### Utilities

```bash
make check-env                    # Validate .env configuration
make clean                        # Clean build artifacts
make status                       # Show deployment status
make destroy                      # Clean up AWS resources
```

## Port Configuration

Each phase uses different ports to avoid conflicts:

| Phase | Description | Port | Endpoint |
|-------|-------------|------|----------|
| Phase 1 | Local app | 8000 | `http://127.0.0.1:8000/mcp` |
| Phase 2 | Docker build | 8001 | `http://127.0.0.1:8001/mcp` |
| Phase 3 | ECR catalog | 8002 | `http://127.0.0.1:8002/mcp` |
| Phase 4 | AWS deploy | 443/80 | `https://your-alb-url/mcp` |

## Development Workflow

### Local Development

```bash
make app                          # Local server on http://127.0.0.1:8000/mcp
```

### SPEC-Compliant Pipeline

```bash
# Complete validation (recommended)
make validate

# Step-by-step development
make init-app                     # Check preconditions
make app                          # Run phase
make test-app                     # Test artifacts
make -C app test-tools            # Run tool-focused tests (metadata, buckets, quilt tools)
make verify-app                   # Verify MCP endpoint
make zero-app                     # Cleanup processes
```

### Testing Individual Phases

```bash
# Test specific phases
make verify-build                 # Test Docker container
make verify-catalog               # Test ECR image
make verify-deploy                # Test deployed service
```

## Environment Management

The system automatically loads environment variables from `.env` via `shared/common.sh`:

- Variables are auto-derived when possible (e.g., ECR_REGISTRY from AWS account)
- Use `make check-env` to see current configuration
- ECR_REGISTRY is constructed automatically if not provided
- AWS credentials use your configured AWS CLI profile

## Manual Testing

### MCP Endpoint Testing

```bash
# Test local server
curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Test Docker container (Phase 2)
curl -X POST http://localhost:8001/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Test ECR image (Phase 3)
curl -X POST http://localhost:8002/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### AWS Service Testing

```bash
# View deployment status
make status

# View ECS logs
aws logs tail /ecs/quilt-mcp --follow --region us-east-1

# Test deployed endpoint (requires authentication)
# See docs/CLAUDE.md for full authentication setup
```

## Cleanup

```bash
# Clean local artifacts
make clean

# Stop all running containers/processes
make zero-app zero-build zero-catalog

# Remove AWS resources
make destroy
```

## Security

- All ECS tasks use IAM roles with minimal required permissions
- API endpoints are protected with JWT authentication via ALB
- Docker builds are isolated and use official base images
- No secrets are logged or exposed in responses
- Environment variables are managed via `.env` (not committed)

## Using with Claude Desktop (DXT)

The easiest way to use this MCP server in Claude Desktop is via the packaged DXT.

1) Download the latest `.dxt` from the project releases
   - Open the repository releases in your browser
   - Download `quilt-mcp-<version>.dxt`
   - Optional: download and run `check-prereqs.sh` to verify your system

2) Install the DXT
   - Double‑click the `.dxt` file, or in Claude Desktop open Settings → Extensions → Install from File and pick the `.dxt`

3) Configure the catalog domain
   - In Claude Desktop Settings → Extensions → Quilt MCP, set your Quilt catalog domain (e.g. `demo.quiltdata.com`)
   - Ensure Python 3.11+ is available on your user PATH (see Requirements)

4) Verify in Claude
   - In a new chat, open the Tools panel and confirm Quilt MCP is listed
   - Try a tool, e.g. “list Quilt packages”

Troubleshooting
- Run `./check-prereqs.sh` from the release assets to validate Python and environment
- If Python isn’t detected, ensure `python3 --version` reports 3.11+ in your login shell

## Using with Cursor

You can run the MCP server locally and point Cursor to it.

Run the server with uv (pick one):

```bash
# Run in-repo (development)
uv run quilt-mcp

# Or run via uvx (no local install needed)
uvx quilt-mcp
```

Configure Cursor to launch the server (GUI or JSON):

- Cursor Settings → MCP (or Command Palette → “MCP: Configure Servers”) → Add New Server
  - Command: `uvx`
  - Args: `quilt-mcp`
  - Working directory: repository root (optional)

Or add JSON to your Cursor settings (example):

```json
{
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["quilt-mcp"],
      "env": {
        "QUILT_CATALOG_DOMAIN": "demo.quiltdata.com"
      }
    }
  }
}
```

## Using with VS Code

For VS Code assistants that support MCP servers, configure a command‑based server entry pointing to this CLI.

Run the server with uv (pick one):

```bash
# Development
uv run quilt-mcp

# Ephemeral
uvx quilt-mcp
```

Example MCP server configuration (JSON) for extensions that support `mcpServers`:

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

Notes
- If your editor expects a static TCP/WebSocket endpoint instead of a command, you can expose the local server with `make remote-export` and point the client at the printed URL’s `/mcp` path.
- Ensure your shell environment includes any required Quilt settings (see Configuration) before launching the server.
