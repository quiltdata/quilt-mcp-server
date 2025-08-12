# Quilt MCP Server - Claude Code Configuration

This repository contains a secure MCP (Model Context Protocol) server for accessing Quilt data. All code and configurations are designed for defensive security purposes only.

## Repository Overview

**Purpose**: Deploy and manage a Claude-compatible MCP server for Quilt data access with JWT authentication
**Tech Stack**: Python, AWS CDK, Docker, Lambda, API Gateway, Cognito
**Security**: JWT authentication, IAM roles, secure credential management

## Pre-approved Commands

Claude Code has permission to run the following commands without asking:

### Build & Deploy

```bash
# Integrated build system
./scripts/build.sh build
./scripts/build.sh deploy
./scripts/build.sh test
./scripts/build.sh clean
./scripts/build.sh deploy --skip-tests
./scripts/build.sh build -v
./scripts/build.sh deploy -v
./scripts/build.sh test -v

```

### Docker & Packaging  

```bash
# Lambda packaging
./packager/package-lambda.sh
./packager/package-lambda.sh -v
./packager/package-lambda.sh -t
./packager/package-lambda.sh -b
./packager/test-lambda.sh
./packager/run-lambda.sh

# Docker commands for Lambda building
docker build --platform linux/amd64 -t quilt-mcp-builder -f packager/Dockerfile .
docker run --rm --platform linux/amd64 -v *:/output --entrypoint="" quilt-mcp-builder *
docker images -q quilt-mcp-builder
docker rmi quilt-mcp-builder
```

### Testing & Validation

```bash
# Endpoint testing
./scripts/test-endpoint.sh
./scripts/test-endpoint.sh -v
./scripts/test-endpoint.sh -f
./scripts/test-endpoint.sh -t
./scripts/test-endpoint.sh --no-auth
./scripts/test-endpoint.sh --token *

# Lambda testing
./scripts/test_lambda.sh
uv run python -m pytest quilt/tests/
uv run python quilt/tests/test_*.py
```

### AWS Operations

```bash
# CDK operations  
uv run cdk deploy --require-approval never --app "python app.py"
uv run cdk destroy --app "python app.py"
uv run cdk bootstrap
uv run cdk synth --app "python app.py"
uv run cdk diff --app "python app.py"

# CloudFormation & AWS CLI
aws cloudformation describe-stacks --stack-name QuiltMcpStack --region *
aws cloudformation describe-stack-resources --stack-name QuiltMcpStack --region *
aws cloudformation *
aws sts get-caller-identity
aws sts *

# Lambda functions  
aws lambda list-functions
aws lambda get-function-configuration --function-name *
aws lambda invoke --function-name * *

# Logs
aws logs tail /aws/lambda/* --follow
aws logs describe-log-groups
aws logs *

# Authentication testing
./scripts/get_token.sh
./scripts/check_logs.sh
./scripts/check_logs.sh -s 10m
./scripts/post-deploy.sh
./scripts/post-deploy.sh --skip-api-test
./scripts/test-mcp-inspector.sh
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
chmod +x scripts/*
chmod +x packager/*
chmod +x tests/*
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
- `LAMBDA_PACKAGE_DIR` - Directory for Lambda package
- `AWS_REGION` - AWS region override
- `AWS_PROFILE` - AWS CLI profile to use

## Security Notes

- All Lambda functions use IAM roles with minimal required permissions
- API endpoints are protected with Cognito JWT authentication  
- Docker builds are isolated and use official base images
- No secrets are logged or exposed in responses
- All authentication uses OAuth 2.0 Client Credentials flow

## Workflow Documentation

1. **Build**: `./scripts/build.sh build` - Docker package + local test
2. **Deploy**: `./scripts/build.sh deploy` - CDK deploy with pre-built package  
3. **Test**: `./scripts/build.sh test` - End-to-end endpoint testing
4. **Debug**: `./scripts/check_logs.sh` - View Lambda logs for troubleshooting

For comprehensive testing: `./scripts/build.sh deploy && ./scripts/test-endpoint.sh -v -f`
