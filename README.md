# Quilt MCP Server

A secure, Claude-compatible MCP (Model Context Protocol) server for accessing Quilt data packages via AWS Lambda with JWT authentication.

## Quick Start

```bash
# 1. Setup environment
make env                          # Copy env.example to .env
# Edit .env with your AWS account and Quilt bucket details

# 2. Deploy to AWS Lambda  
make deploy                       # Build and deploy everything

# 3. Test the deployment
make test                         # Verify everything works
```

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
- **Docker** for Lambda packaging
- **IAM Policy ARN** for S3 access to your Quilt buckets

## Configuration

```bash
# Copy and edit environment configuration
make env
```

Edit `.env` with your settings:

```bash
# Required: IAM policy for S3 access
QUILT_READ_POLICY_ARN=arn:aws:iam::123456789012:policy/YourQuiltReadPolicy

# Quilt Configuration  
QUILT_DEFAULT_BUCKET=s3://your-quilt-bucket
QUILT_TEST_PACKAGE=yournamespace/testpackage
QUILT_TEST_ENTERY=README.md

# AWS Configuration
CDK_DEFAULT_ACCOUNT=123456789012
CDK_DEFAULT_REGION=us-east-1
AWS_PROFILE=default
```

## Makefile Commands

### Build & Deploy
```bash
make build                        # Build Lambda package locally
make deploy                       # Build and deploy to AWS
make test                         # Test deployed endpoints
make all                          # Run pytest then deploy
```

### Development & Testing
```bash
make pytest                       # Run integration tests locally
make coverage                     # Run tests with coverage report
make clean                        # Clean build artifacts
```

### Local Development
```bash
make stdio-run                    # Run as stdio MCP server
make stdio-inspector              # Test stdio server with MCP Inspector
make remote-run                   # Run as HTTP server (localhost:8000)
make remote-test                  # Test local HTTP server
```

### Monitoring & Debug
```bash
make logs                         # View Lambda logs (last 10 minutes)
make token                        # Get OAuth access token
make remote-inspector             # Test deployed server with MCP Inspector
```

## Environment Switching

Use different environment files for different deployments:

```bash
# Development environment
make pytest                       # Uses .env (default)

# Staging environment  
ENV_FILE=.env.staging make pytest # Uses staging configuration
ENV_FILE=.env.staging make deploy  # Deploy to staging
```

## Testing with MCP Inspector

```bash
# Test deployed server
make remote-inspector

# Test local stdio server
make stdio-inspector
```

## Manual API Testing

```bash
# Get access token and test
make token
TOKEN=$(make token)
curl -H "Authorization: Bearer $TOKEN" \
     -X POST https://your-api-endpoint.com/mcp/ \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Cleanup

```bash
make clean                        # Remove local build artifacts
uv run cdk destroy --app "python app.py"  # Remove AWS resources
```
