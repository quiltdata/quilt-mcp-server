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

# Full deployment pipeline
make validate
```

## Architecture

This project uses a **4-phase deployment pipeline**:

```
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
- **Python 3.11+** and [uv](https://docs.astral.sh/uv/) package manager
- **Docker** for containerization
- **IAM Policy ARN** for S3 access to your Quilt buckets

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
# See CLAUDE.md for full authentication setup
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