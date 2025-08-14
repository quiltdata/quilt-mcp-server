# Quilt MCP Server - Claude Code Configuration

This repository contains a secure MCP (Model Context Protocol) server for accessing Quilt data. All code and configurations are designed for defensive security purposes only.

## Repository Overview

**Purpose**: Deploy and manage a Claude-compatible MCP server for Quilt data access with JWT authentication
**Tech Stack**: Python, AWS CDK, Docker, ECS Fargate, Application Load Balancer, ECR
**Security**: JWT authentication, IAM roles, secure credential management

## Architecture

This project uses a **4-phase deployment pipeline**:

```
src/
├── app/           # Phase 0: Local MCP server (Python)
├── build-docker/  # Phase 1: Docker containerization
├── catalog-push/  # Phase 2: ECR registry operations
├── deploy-aws/     # Phase 3: ECS/ALB deployment
└── shared/        # Common utilities and pipeline orchestration
```

## Pre-approved Commands

Claude Code has permission to run the following commands without asking:

### Phase-based Build System

```bash
# Individual phase scripts
./src/app/app.sh run
./src/app/app.sh test
./src/app/app.sh clean

./src/build-docker/build-docker.sh build
./src/build-docker/build-docker.sh test
./src/build-docker/build-docker.sh run
./src/build-docker/build-docker.sh clean
./src/build-docker/build-docker.sh build -v
./src/build-docker/build-docker.sh test -v

./src/catalog-push/catalog-push.sh push
./src/catalog-push/catalog-push.sh pull
./src/catalog-push/catalog-push.sh test
./src/catalog-push/catalog-push.sh login
./src/catalog-push/catalog-push.sh push -v
./src/catalog-push/catalog-push.sh test -v

./src/deploy-aws/deploy-aws.sh deploy
./src/deploy-aws/deploy-aws.sh test
./src/deploy-aws/deploy-aws.sh destroy
./src/deploy-aws/deploy-aws.sh status
./src/deploy-aws/deploy-aws.sh deploy -v
./src/deploy-aws/deploy-aws.sh deploy --skip-tests

# Pipeline orchestration
./src/shared/pipeline.sh full
./src/shared/pipeline.sh app
./src/shared/pipeline.sh build-docker
./src/shared/pipeline.sh catalog
./src/shared/pipeline.sh deploy
./src/shared/pipeline.sh full -v
./src/shared/pipeline.sh full --skip-tests

# Makefile shortcuts
make app
make build
make catalog
make deploy
make full
make test-app
make test-build
make test-deploy
make clean
make status
make destroy
```

### Docker Operations

```bash
# Docker commands for ECS deployment
docker build --platform linux/amd64 -t quilt-mcp:* -f src/build-docker/Dockerfile .
docker run --rm -p 8000:8000 quilt-mcp:*
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
# Phase-specific testing
./src/app/app.sh test
./src/build-docker/build-docker.sh test
./src/catalog-push/catalog-push.sh test
./src/deploy-aws/deploy-aws.sh test

# End-to-end pipeline testing
./src/shared/pipeline.sh full
./src/shared/pipeline.sh full --skip-tests

# MCP endpoint testing
curl -X POST http://localhost:8000/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
curl -X POST * -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Python testing
uv run python -m pytest src/app/tests/ -v
uv run python -m pytest *
```

### AWS Operations

```bash
# CDK operations (from src/deploy-aws/)
cd src/deploy && uv run cdk deploy --require-approval never --app "python app.py"
cd src/deploy && uv run cdk destroy --app "python app.py"
cd src/deploy && uv run cdk bootstrap --app "python app.py"
cd src/deploy && uv run cdk synth --app "python app.py"
cd src/deploy && uv run cdk diff --app "python app.py"

# CloudFormation & AWS CLI
aws cloudformation describe-stacks --stack-name QuiltMcpFargateStack --region *
aws cloudformation describe-stack-resources --stack-name QuiltMcpFargateStack --region *
aws cloudformation *
aws sts get-caller-identity
aws sts *

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
aws logs *
```

### Environment & Dependencies

```bash
# UV package management
uv sync
uv sync --group deploy
uv run *
uv lock
uv add *
uv remove *

# Python execution
python -c "*"
python tests/generate_lambda_events.py
python app.py

# Environment setup
set -a && source .env && set +a
source .env
source *
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
chmod +x src/*/*.sh
chmod +x *.sh
ls -la *
head *
tail *
grep -r * .
cat *
make *
curl *

# Process management
timeout * *
sleep *
```

### Special Cases

```bash
# GitHub CLI (for CI/CD setup)
gh auth *
brew install aws-sam-cli
brew install *

# SAM (if available)  
sam build
sam local start-api
sam local invoke *

# Test endpoints with authentication
curl -H "Authorization: Bearer $(./scripts/get_token.sh)" -X POST * -H "Content-Type: application/json" -d "*"
curl -s -X POST * -H "Content-Type: application/json" -d "*"
curl -s -w '%{http_code}' -o /dev/null *
```

## Test Commands

These commands are specifically for testing and validation:

```bash
# Integrated workflow testing
./scripts/build.sh deploy && ./scripts/build.sh test

# Individual component testing  
./packager/package-lambda.sh -t tools-list
./scripts/test-endpoint.sh -v -f
uv run python quilt/tests/test_lambda_handler.py

# Authentication flow testing
TOKEN=$(./scripts/get_token.sh) && curl -H "Authorization: Bearer $TOKEN" -X POST https://*/mcp/ -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Environment Variables

The following environment variables are safe to use:

- `CDK_DEFAULT_ACCOUNT` - AWS account ID
- `CDK_DEFAULT_REGION` - AWS region (default: us-east-1)  
- `AWS_REGION` - AWS region override
- `AWS_PROFILE` - AWS CLI profile to use
- `ECR_REGISTRY` - ECR registry URL (required for catalog-push/deploy phases)
- `ECR_REPOSITORY` - ECR repository name (default: quilt-mcp)
- `VPC_ID` - Existing VPC ID (optional)
- `IMAGE_URI` - Docker image URI for deployment

## Security Notes

- All ECS tasks use IAM roles with minimal required permissions
- API endpoints are protected with JWT authentication via ALB
- Docker builds are isolated and use official base images
- No secrets are logged or exposed in responses
- All network traffic goes through ALB with security groups

## Tool Testing Configuration

MCP tool testing is configured via `scripts/test-tools.json`, which defines test arguments for each tool:

```bash
# List all available test tools
./scripts/test-endpoint.sh -l --list-tools

# Test specific tools locally  
./scripts/test-endpoint.sh -l package_create
./scripts/test-endpoint.sh -l -v bucket_objects_list

# Edit test-tools.json to customize test parameters
```

The test configuration includes realistic test data for all MCP tools including:

- Authentication and filesystem checks
- Package operations (create, update, delete, browse, search)
- S3 bucket operations (list, fetch, put, metadata)

## Development Server Options

### Local Development

```bash
make remote-run        # Local server on http://127.0.0.1:8000/mcp
make remote-hotload    # FastMCP hot reload development server
```

### External Access via ngrok

```bash
make remote-export     # Expose local server via ngrok tunnel
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

## Workflow Documentation

### Phase-based Development Workflow

1. **App Phase**: `./src/app/app.sh run` - Local MCP server development
2. **Build Phase**: `./src/build-docker/build-docker.sh build` - Docker containerization
3. **Catalog Phase**: `./src/catalog-push/catalog-push.sh push` - Push to ECR registry  
4. **Deploy Phase**: `./src/deploy-aws/deploy-aws.sh deploy` - Deploy to ECS Fargate

### Pipeline Orchestration

- **Full Pipeline**: `./src/shared/pipeline.sh full` - Complete end-to-end deployment
- **Individual Phases**: `./src/shared/pipeline.sh [app|build-docker|catalog|deploy]`
- **Makefile Shortcuts**: `make [app|build|catalog|deploy|full]`

### Version Management

All phases use **git SHA** as version tag to prevent skew:
- Local image: `quilt-mcp:abc123f`  
- ECR image: `${ECR_REGISTRY}/quilt-mcp:abc123f`
- ECS service: Deployed with `abc123f`
