# Quilt MCP Server - Claude Code Configuration

This repository contains a secure MCP (Model Context Protocol) server for accessing Quilt data. All code and configurations are designed for defensive security purposes only.

## Repository Overview

**Purpose**: Deploy and manage a Claude-compatible MCP server for Quilt data access with JWT authentication
**Tech Stack**: Python, AWS CDK, Docker, ECS Fargate, Application Load Balancer, ECR
**Security**: JWT authentication, IAM roles, secure credential management

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
make deploy                 # Phase 4: Deploy to ECS Fargate

# Validation Commands (SPEC-compliant)
make validate               # Validate all phases sequentially
make validate-app           # Validate Phase 1 only
make validate-build         # Validate Phase 2 only
make validate-catalog       # Validate Phase 3 only
make validate-deploy        # Validate Phase 4 only

# Testing Commands
make test-app               # Phase 1 testing only
make test-build             # Phase 2 testing only
make test-deploy            # Phase 4 testing only
make coverage               # Run tests with coverage (fails if <85%)

# Verification Commands (MCP Endpoint Testing)
make verify-app             # Verify Phase 1 MCP endpoint
make verify-build           # Verify Phase 2 MCP endpoint
make verify-catalog         # Verify Phase 3 MCP endpoint
make verify-deploy          # Verify Phase 4 MCP endpoint

# Initialization Commands (Precondition Checks)
make init-app               # Check Phase 1 preconditions
make init-build             # Check Phase 2 preconditions
make init-catalog           # Check Phase 3 preconditions
make init-deploy            # Check Phase 4 preconditions

# Cleanup Commands
make clean                  # Clean build artifacts
make zero-app               # Stop Phase 1 processes
make zero-build             # Stop Phase 2 containers
make zero-catalog           # Stop Phase 3 containers
make zero-deploy            # Disable Phase 4 endpoint (preserve stack)

# Utilities
make status                 # Show deployment status
make destroy                # Clean up AWS resources
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

# Phase 4: Deploy-AWS (ECS/ALB Deployment)
./deploy-aws/deploy-aws.sh deploy
./deploy-aws/deploy-aws.sh test
./deploy-aws/deploy-aws.sh status
./deploy-aws/deploy-aws.sh validate
./deploy-aws/deploy-aws.sh destroy
```

### Shared Utilities

```bash
# Environment and validation
./shared/validate.sh all
./shared/validate.sh app
./shared/validate.sh build
./shared/validate.sh catalog
./shared/validate.sh deploy

# MCP endpoint testing
./shared/test-endpoint.sh -p app -t
./shared/test-endpoint.sh -p build -t
./shared/test-endpoint.sh -p catalog -t
./shared/test-endpoint.sh -p deploy -t
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

### AWS Operations

```bash
# CDK operations (from deploy-aws/)
cd deploy-aws && uv run cdk deploy --require-approval never --app "python app.py"
cd deploy-aws && uv run cdk destroy --app "python app.py"
cd deploy-aws && uv run cdk bootstrap --app "python app.py"
cd deploy-aws && uv run cdk synth --app "python app.py"
cd deploy-aws && uv run cdk diff --app "python app.py"

# CloudFormation & AWS CLI
aws cloudformation describe-stacks --stack-name QuiltMcpFargateStack --region *
aws cloudformation describe-stack-resources --stack-name QuiltMcpFargateStack --region *
aws sts get-caller-identity

# ECS & ECR operations
aws ecs describe-clusters --cluster *
aws ecs describe-services --cluster * --services *
aws ecs list-tasks --cluster *
aws ecs describe-tasks --cluster * --tasks *
aws ecr describe-repositories
aws ecr describe-images --repository-name *
aws ecr get-login-password --region * | docker login --username AWS --password-stdin *

# Logs (ECS/ALB)
aws logs tail /ecs/* --follow --region *
aws logs tail /aws/elasticloadbalancing/* --follow --region *
aws logs describe-log-groups
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
git checkout -b *
git checkout *
git branch *
git merge *

# GitHub CLI operations (for WORKFLOW.md)
gh issue view *
gh issue list
gh pr create --base * --title "*" --body "*"
gh pr list
gh pr merge --squash
gh pr view *

# File operations
find . -name "*.py" -type f
mkdir -p *
mv * *
cp * *
rm -f *
rm -rf *
touch *

# System utilities  
chmod +x */.*sh
ls -la *
head *
tail *
cat *
curl *
grep -r * *

# Process management
timeout * *
sleep *
kill *
pkill *
```

### WORKFLOW.md Specific Permissions

```bash
# Workflow operations (as defined in WORKFLOW.md)
mkdir -p spec/
touch spec/*.md
git checkout -b spec/*
git checkout -b impl/*
git push -u origin spec/*
git push -u origin impl/*

# Test operations
npm test
npm run test:coverage
npm run test:integration
pytest
./scripts/check-env.sh

# Branch and PR operations
gh pr create --base spec/* --title "test: *" --body "*"
gh pr create --base * --title "feat: *" --body "*"
gh pr merge --squash

# Issue analysis
gh issue view $(git branch --show-current | grep -o '[0-9]\+')
```

## Environment Variables

Environment variables are automatically loaded from `.env` and managed by `shared/common.sh`. Use `make check-env` to validate your configuration.

Key variables (see `env.example` for complete list):
- `CDK_DEFAULT_ACCOUNT` - AWS account ID (auto-derived from AWS CLI)
- `CDK_DEFAULT_REGION` - AWS region (default: us-east-1)
- `ECR_REGISTRY` - ECR registry URL (auto-constructed if not set)
- `QUILT_DEFAULT_BUCKET` - S3 bucket for Quilt data
- `QUILT_CATALOG_DOMAIN` - Quilt catalog domain

## Port Configuration

Each phase uses different ports to avoid conflicts:

| Phase | Description | Port | Endpoint |
|-------|-------------|------|----------|
| Phase 1 | Local app | 8000 | `http://127.0.0.1:8000/mcp` |
| Phase 2 | Docker build | 8001 | `http://127.0.0.1:8001/mcp` |
| Phase 3 | ECR catalog | 8002 | `http://127.0.0.1:8002/mcp` |
| Phase 4 | AWS deploy | 443/80 | `https://your-alb-url/mcp` |

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
make validate-deploy

# Execution pipeline (no validation)
make app build catalog deploy

# Testing pipeline
make test-app test-build test-deploy
```

### Version Management

All phases use **git SHA** as version tag to prevent skew:

- Local image: `quilt-mcp:abc123f`  
- ECR image: `${ECR_REGISTRY}/quilt-mcp:abc123f`
- ECS service: Deployed with `abc123f`

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

- All ECS tasks use IAM roles with minimal required permissions
- API endpoints are protected with JWT authentication via ALB
- Docker builds are isolated and use official base images
- No secrets are logged or exposed in responses
- All network traffic goes through ALB with security groups

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.