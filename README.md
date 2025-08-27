# Quilt MCP Server

A secure MCP (Model Context Protocol) server for accessing Quilt data with comprehensive tools for package management, S3 operations, and system utilities.

## Quick Start

### Option A: Claude Desktop (DXT Extension - Recommended)

The easiest way to get started is with the pre-built DXT extension:

1. **Download the DXT**: Get the latest `.dxt` from [project releases](https://github.com/quiltdata/fast-mcp-server/releases)
2. **Install**: Double-click the `.dxt` file or use Claude Desktop → Settings → Extensions → Install from File
3. **Configure**: Set your Quilt catalog domain in Claude Desktop → Settings → Extensions → Quilt MCP
4. **Verify**: Open Tools panel in a new chat and confirm Quilt MCP is available

> **Requirements**: Python 3.11+ accessible in your login shell (`python3 --version`)

### Option B: Local Development Setup

For development or when you want to run the server locally:

```bash
# 1. Clone and setup environment
git clone https://github.com/quiltdata/fast-mcp-server.git
cd fast-mcp-server
cp env.example .env
# Edit .env with your AWS credentials and Quilt settings

# 2. Install dependencies
uv sync

# 3. Run local server
make app
# Server runs on http://127.0.0.1:8000/mcp
```

### Option C: Cursor Configuration

Configure Cursor to use the local development server:

```json
{
  "mcpServers": {
    "quilt": {
      "command": "/Users/your-username/path/to/fast-mcp-server/.venv/bin/python",
      "args": ["/Users/your-username/path/to/fast-mcp-server/app/main.py"],
      "env": {
        "PYTHONPATH": "/Users/your-username/path/to/fast-mcp-server/app",
        "QUILT_CATALOG_DOMAIN": "demo.quiltdata.com",
        "QUILT_DEFAULT_BUCKET": "s3://your-bucket"
      }
    }
  }
}
```

### Option D: VS Code Configuration

For VS Code with MCP support:

```json
{
  "mcpServers": {
    "quilt": {
      "command": "/Users/your-username/path/to/fast-mcp-server/.venv/bin/python",
      "args": ["/Users/your-username/path/to/fast-mcp-server/app/main.py"],
      "env": {
        "PYTHONPATH": "/Users/your-username/path/to/fast-mcp-server/app",
        "QUILT_CATALOG_DOMAIN": "demo.quiltdata.com"
      },
      "description": "Quilt MCP Server"
    }
  }
}
```

### Option E: Remote Access (ngrok)

For web applications or remote clients:

```bash
# Terminal 1: Start server
make app

# Terminal 2: Expose via ngrok  
make run-app-tunnel
# Use the provided ngrok HTTPS URL in your MCP client
```

## MCP Tools Available

This server provides **66+ comprehensive Quilt data operations**:

### Package Management
- **`packages_list`** - List packages in a registry with filtering
- **`packages_search`** - Search packages using ElasticSearch  
- **`package_browse`** - Examine package contents and structure
- **`package_contents_search`** - Search within specific packages
- **`package_create`** - Create new packages from S3 objects
- **`package_update`** - Update existing packages with new files
- **`package_delete`** - Remove packages from registry
- **`package_validate`** - Validate package integrity

### S3 Operations
- **`bucket_objects_list`** - List objects in S3 buckets
- **`bucket_object_info`** - Get metadata for specific objects
- **`bucket_object_text`** - Read text content from objects
- **`bucket_objects_put`** - Upload objects to S3
- **`bucket_object_fetch`** - Download object data
- **`bucket_objects_search`** - Search objects using Elasticsearch

### Analytics & SQL
- **`athena_databases_list`** - List available Athena databases
- **`athena_tables_list`** - List tables in a database
- **`athena_query_execute`** - Execute SQL queries via Athena
- **`tabulator_tables_list`** - List Quilt Tabulator tables
- **`unified_search`** - Multi-backend intelligent search

### System & Authentication
- **`auth_check`** - Verify Quilt authentication status
- **`filesystem_check`** - Check system environment details
- **`aws_permissions_discover`** - Discover available AWS permissions
- **`bucket_access_check`** - Validate bucket access permissions

### Advanced Features
- **`create_package_enhanced`** - Advanced package creation with templates
- **`workflow_create`** - Create multi-step workflows
- **`metadata_templates`** - Generate metadata templates (genomics, ML, etc.)
- **`generate_quilt_summarize_json`** - Create package summaries

**View all tools interactively:**
```bash
cd app && make run-inspector
# Opens MCP Inspector at http://127.0.0.1:6274
```

## Architecture

This project supports both **local development** and **cloud deployment**:

### Local-First Approach (Recommended)
```tree
fast-mcp-server/
├── app/           # Core MCP server (Python)
├── scripts/       # Setup and configuration tools
└── tests/         # Comprehensive test suite
```

### Full Pipeline (Advanced)
```tree
fast-mcp-server/
├── app/           # Phase 1: Local MCP server
├── build-docker/  # Phase 2: Docker containerization  
├── catalog-push/  # Phase 3: ECR registry operations
├── deploy-aws/    # Phase 4: ECS/ALB deployment (optional)
└── scripts/       # Common utilities and tools
```

## Requirements

- **Python 3.11+** and **[uv](https://docs.astral.sh/uv/)** package manager
- **AWS CLI configured** with credentials for S3 access
- **Docker** (optional, for containerization and cloud deployment)

> **Claude Desktop Note**: Ensure Python 3.11+ is accessible via `python3` in your login shell environment, not just in virtual environments.

## Configuration

### Basic Configuration
```bash
# Copy and edit environment
cp env.example .env
scripts/check-env.sh

# Key variables to set in .env:
QUILT_CATALOG_DOMAIN=your-catalog-domain.com
QUILT_DEFAULT_BUCKET=s3://your-quilt-bucket
AWS_PROFILE=default
```

### Advanced Configuration (Cloud Deployment)
```bash
# Additional variables for AWS deployment
CDK_DEFAULT_ACCOUNT=123456789012
CDK_DEFAULT_REGION=us-east-1
ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com
```

## Usage Examples

### Local Development
```bash
# Start local server
make app                          # Run on http://127.0.0.1:8000/mcp

# Test the server
curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Development Pipeline
```bash
# Complete local validation
make validate-app                 # Validate local server

# Full pipeline (if using cloud deployment)
make validate                     # Validate all phases
make app build catalog deploy     # Execute full pipeline
```

### Testing
```bash
# Run comprehensive tests
make coverage                     # Run tests with coverage (requires ≥85%)
make test-app                     # Test local server only

# Test specific components
cd app && make test-tools         # Test MCP tools specifically
```

## Available Commands

### Core Commands
```bash
make app                          # Run local MCP server
make build                        # Build Docker container
make catalog                      # Push to ECR registry
make deploy                       # Deploy to AWS ECS (if configured)
```

### Validation & Testing
```bash
make validate                     # Validate all configured phases
make validate-app                 # Validate local server only
make test-app                     # Test local server
make coverage                     # Run tests with coverage
```

### Utilities
```bash
make check-env                    # Validate environment configuration
make clean                        # Clean build artifacts
make status                       # Show deployment status
make destroy                      # Clean up AWS resources (if deployed)
```

### Development Tools
```bash
make run-app-tunnel               # Expose local server via ngrok
cd app && make run-inspector      # Open MCP Inspector for tool testing
```

## Port Configuration

| Usage | Port | Endpoint | Purpose |
|-------|------|----------|---------|
| Local Development | 8000 | `http://127.0.0.1:8000/mcp` | Primary local server |
| Docker Testing | 8001 | `http://127.0.0.1:8001/mcp` | Container validation |
| ECR Testing | 8002 | `http://127.0.0.1:8002/mcp` | Registry validation |
| AWS Deployment | 443/80 | `https://your-alb-url/mcp` | Production endpoint |
| MCP Inspector | 6274 | `http://127.0.0.1:6274` | Tool testing interface |

## Security

- **IAM Integration**: Uses AWS IAM roles and policies for secure S3 access
- **JWT Authentication**: Supports JWT-based authentication for cloud deployments
- **Minimal Permissions**: Follows principle of least privilege
- **Secure Defaults**: No secrets logged or exposed in responses
- **Environment Isolation**: Credentials managed via `.env` (not committed)

## Troubleshooting

### Common Issues

**Python Version**: 
```bash
python3 --version  # Should show 3.11+
which python3     # Should be in your PATH
```

**AWS Credentials**:
```bash
aws sts get-caller-identity  # Should show your AWS account
aws s3 ls s3://your-bucket  # Should list your bucket contents
```

**Environment Validation**:
```bash
scripts/check-env.sh         # Comprehensive environment check
scripts/check-env.sh claude  # Client-specific validation
```

**Module Import Errors**:
```bash
# Ensure PYTHONPATH is set correctly
export PYTHONPATH=/path/to/fast-mcp-server/app
cd /path/to/fast-mcp-server && make app
```

### Getting Help

- **Tool Documentation**: See [CLAUDE.md](CLAUDE.md) for detailed tool usage
- **MCP Inspector**: Use `cd app && make run-inspector` for interactive tool testing
- **Validation Scripts**: Run `make validate-app` for comprehensive checks

## Development

### Project Structure
- **`app/`** - Core MCP server implementation
- **`scripts/`** - Setup, configuration, and utility scripts  
- **`tests/`** - Comprehensive test suite with >85% coverage
- **`build-docker/`** - Docker containerization (optional)
- **`catalog-push/`** - ECR registry operations (optional)
- **`deploy-aws/`** - AWS ECS deployment (optional)

### Contributing
```bash
# Set up development environment
uv sync --group test
make validate-app
make coverage

# Run full validation before submitting
make validate
```

### Development Workflow

1. **Clone repository**: `git clone https://github.com/quiltdata/fast-mcp-server.git`
2. **Setup environment**: `cp env.example .env` and edit with your settings
3. **Install dependencies**: `uv sync`
4. **Run tests**: `make coverage`
5. **Start development**: `make app`
6. **Test changes**: Use MCP Inspector at `http://127.0.0.1:6274`

For more details, see the individual phase specifications in `spec/`.