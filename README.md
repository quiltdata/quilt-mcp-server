# Quilt MCP Server

A secure, Claude-compatible MCP (Model Context Protocol) server for accessing Quilt data packages via AWS Lambda with JWT authentication.

## Quick Start

```bash
# 1. Configure your environment
cp env.example .env
# Edit .env with your QUILT_READ_POLICY_ARN

# 2. Deploy to AWS Lambda
./scripts/build.sh deploy

# 3. Use the output API endpoint and authentication details
```

## MCP Tools

This server provides secure access to Quilt data operations:

- **`search_packages`** - Search for packages across Quilt registries
- **`list_packages`** - List all packages in a registry  
- **`browse_package`** - Examine package structure and metadata

## Requirements

- **AWS Account** with CLI configured
- **Python 3.11+** and [uv](https://docs.astral.sh/uv/) package manager
- **Docker** for Lambda packaging
- **IAM Policy ARN** for S3 read access to your Quilt buckets

## Configuration

Copy `env.example` to `.env` and set:

```bash
# Required
QUILT_READ_POLICY_ARN=arn:aws:iam::123456789012:policy/YourQuiltReadPolicy

# Optional
CDK_DEFAULT_ACCOUNT=123456789012
CDK_DEFAULT_REGION=us-east-1
AWS_PROFILE=default
```

## Authentication

The deployed server uses OAuth 2.0 Client Credentials flow with AWS Cognito for secure access. Authentication is handled automatically by the deployment process.

## Commands

```bash
# Deploy and test
./scripts/build.sh deploy          # Full deployment pipeline
./scripts/build.sh test            # Test existing deployment

# Development
./scripts/build.sh build           # Build Lambda package locally
./scripts/build.sh clean           # Clean build artifacts

# Monitoring
./scripts/check_logs.sh            # View Lambda logs
./scripts/get_token.sh             # Get authentication token
```

## Testing with MCP Inspector

After deployment, test the MCP server using the official MCP Inspector:

```bash
# Test the deployed server (no installation needed - uses npx)
./scripts/test-mcp-inspector.sh
```

This will launch the MCP Inspector with your deployed server configuration, allowing you to:
- Browse available MCP tools
- Test tool functionality interactively  
- Verify authentication is working
- Debug any issues

## Manual API Testing

You can also test the raw API directly:

```bash
# Get access token and test API
TOKEN=$(./scripts/get_token.sh)
curl -H "Authorization: Bearer $TOKEN" \
     -X POST https://your-api-endpoint.com/mcp/ \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Cleanup

```bash
uv run cdk destroy --app "python app.py"
```
