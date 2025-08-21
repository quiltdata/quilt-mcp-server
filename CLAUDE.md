# Quilt MCP Server - Claude Code Configuration

This repository contains a secure MCP (Model Context Protocol) server for accessing Quilt data. All code and configurations are designed for defensive security purposes only.

## Repository Overview

**Purpose**: Local MCP server for Quilt data access
**Tech Stack**: Python, Docker (optional)
**Security**: Local development focused

## Architecture

This project provides a local MCP server with optional Docker containerization:

```tree
quilt-mcp-server/
├── app/           # Phase 1: Local MCP server (Python)
├── build-docker/  # Phase 2: Docker containerization  
├── catalog-push/  # Phase 3: ECR registry operations
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

## Manual Testing Commands

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

## Environment Configuration

Edit `.env` with your settings:

```bash
# AWS Configuration
AWS_PROFILE=default

# Quilt Configuration
QUILT_CATALOG_DOMAIN=your-catalog-domain.com
QUILT_DEFAULT_BUCKET=s3://your-quilt-bucket
QUILT_TEST_PACKAGE=yournamespace/testpackage
QUILT_TEST_ENTRY=README.md
```

## Pre-approved Commands

Claude Code has permission to run the following commands without asking:

### Makefile Targets (Recommended)

```bash
# Environment Setup
make check-env              # Validate .env configuration

# Phase Commands
make app                    # Phase 1: Run local MCP server
make build                  # Phase 2: Build Docker container  
make catalog                # Phase 3: Push to ECR registry

# Validation Commands (SPEC-compliant)
make validate               # Validate all phases sequentially
make validate-app           # Validate Phase 1 only
make validate-build         # Validate Phase 2 only
make validate-catalog       # Validate Phase 3 only
make validate-deploy        # Validate Phase 4 only

# Testing Commands
make test-app               # Phase 1 testing only
make test-build             # Phase 2 testing only
make coverage               # Run tests with coverage (fails if <85%)

# Verification Commands (MCP Endpoint Testing)
make verify-app             # Verify Phase 1 MCP endpoint
make verify-build           # Verify Phase 2 MCP endpoint
make verify-catalog         # Verify Phase 3 MCP endpoint

# Initialization Commands (Precondition Checks)
make init-app               # Check Phase 1 preconditions
make init-build             # Check Phase 2 preconditions
make init-catalog           # Check Phase 3 preconditions

# Cleanup Commands
make clean                  # Clean build artifacts
make zero-app               # Stop Phase 1 processes
make zero-build             # Stop Phase 2 containers
make zero-catalog           # Stop Phase 3 containers

# Utilities
```

### Direct Phase Scripts (Alternative)

```bash
# Phase 1: App (Local MCP Server)
./app/app.sh run
./app/app.sh test
./app/app.sh coverage
./app/app.sh validate
./app/app.sh clean

# Phase 2: Build-Docker (Containerization)
./build-docker/build-docker.sh build
./build-docker/build-docker.sh test
./build-docker/build-docker.sh run
./build-docker/build-docker.sh validate
./build-docker/build-docker.sh clean

# Phase 3: Catalog-Push (ECR Registry)
./catalog-push/catalog-push.sh push
./catalog-push/catalog-push.sh pull
./catalog-push/catalog-push.sh test
./catalog-push/catalog-push.sh login
./catalog-push/catalog-push.sh validate

```

### Shared Utilities

```bash
# Environment and validation
./shared/validate.sh all
./shared/validate.sh app
./shared/validate.sh build
./shared/validate.sh catalog

# MCP endpoint testing
./shared/test-endpoint.sh -p app -t
./shared/test-endpoint.sh -p build -t
./shared/test-endpoint.sh -p catalog -t
```

### Docker Operations

```bash
# Docker commands for ECS deployment
docker build --platform linux/amd64 -t quilt-mcp:* -f build-docker/Dockerfile .
docker run --rm -p 8000:8000 quilt-mcp:*
docker run --rm -p 8001:8000 quilt-mcp:*  # Phase 2 testing
docker run --rm -p 8002:8000 quilt-mcp:*  # Phase 3 testing
docker tag quilt-mcp:* *
docker push *
docker pull *
docker images quilt-mcp
docker rmi quilt-mcp:*
docker stop *
docker logs *
docker inspect *
```

### Testing & Validation

```bash
# Unit and integration testing
uv run python -m pytest app/tests/ -v
uv run python -m pytest app/tests/ --cov=quilt_mcp --cov-report=term-missing --cov-fail-under=85

# MCP endpoint testing
curl -X POST http://localhost:8000/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
curl -X POST http://localhost:8001/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
curl -X POST http://localhost:8002/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```


### Environment & Dependencies

```bash
# UV package management
uv sync
uv sync --group test
uv run *
uv lock
uv add *
uv remove *

# Python execution
python -c "*"
python app/main.py
python app/tests/test_mcp_response_format.py

# Environment setup
make check-env                              # Validate environment
cp env.example .env                         # Set up environment file
set -a && source .env && set +a            # Load environment
source .env
printenv
echo *
```

### Development Tools

```bash
# Git operations
git status
git diff
git log --oneline -n 10
git add *
git commit -m "*"
git push
git clean -fd

# File operations
find . -name "*.py" -type f
mkdir -p *
mv * *
cp * *
rm -f *
rm -rf *

# System utilities  
chmod +x */.*sh
ls -la *
head *
tail *
cat *
curl *

# Process management
timeout * *
sleep *
kill *
pkill *
```

## Environment Variables

Environment variables are automatically loaded from `.env` and managed by `shared/common.sh`. Use `make check-env` to validate your configuration.

Key variables (see `env.example` for complete list):

- `QUILT_DEFAULT_BUCKET` - S3 bucket for Quilt data
- `QUILT_CATALOG_DOMAIN` - Quilt catalog domain

## Port Configuration

Each phase uses different ports to avoid conflicts:

| Phase | Description | Port | Endpoint |
|-------|-------------|------|----------|
| Phase 1 | Local app | 8000 | `http://127.0.0.1:8000/mcp` |
| Phase 2 | Docker build | 8001 | `http://127.0.0.1:8001/mcp` |
| Phase 3 | ECR catalog | 8002 | `http://127.0.0.1:8002/mcp` |

## Workflow Documentation

### SPEC-Compliant Validation Workflow

The validation system follows SPEC.md requirements:

1. **Check preconditions**: `make init-<phase>`
2. **Execute phase**: `make <phase>`  
3. **Test artifacts**: `make test-<phase>`
4. **Verify MCP endpoint**: `make verify-<phase>`
5. **Cleanup processes**: `make zero-<phase>`

### Full Pipeline Examples

```bash
# Complete validation (all phases)
make validate

# Individual phase validation
make validate-app
make validate-build  
make validate-catalog

# Execution pipeline (no validation)
make app build catalog

# Testing pipeline
make test-app test-build
```

### Version Management

Local phases use **git SHA** as version tag:

- Local image: `quilt-mcp:abc123f`  
- ECR image: `${ECR_REGISTRY}/quilt-mcp:abc123f`

## Development Server Options

### Local Development

```bash
make app                    # Local server on http://127.0.0.1:8000/mcp
```

### External Access via ngrok

```bash
make remote-export          # Expose local server via ngrok tunnel
```

The `remote-export` command:

- Starts the MCP server locally on port 8000
- Creates an ngrok tunnel with predictable URL: `https://uniformly-alive-halibut.ngrok-free.app`
- MCP endpoint available at: `https://uniformly-alive-halibut.ngrok-free.app/mcp`
- Automatically handles cleanup when stopped with Ctrl+C
- Requires ngrok installation and authtoken configuration

Use `remote-export` for:

- Testing with Claude Desktop from different machines
- Sharing your development server with team members (consistent URL)
- Testing MCP integrations from external services
- Demonstrating MCP functionality remotely

## Security Notes

- Docker builds are isolated and use official base images
- No secrets are logged or exposed in responses
- Local development focused with optional containerization

## Important Instruction Reminders

Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
