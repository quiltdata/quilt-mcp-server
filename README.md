# Fast MCP Server - Quilt Edition

A Claude-compatible MCP server for searching and browsing Quilt data packages in S3.

## Quick Start

```bash
# 1. Configure your environment
cp env.example .env
# Edit .env with your QUILT_READ_POLICY_ARN

# 2. Deploy to AWS Lambda
./deploy.sh

# 3. Connect Claude with the output URL
```

## Tools Available

- `search_packages` - Search for packages across Quilt registries
- `list_packages` - List all packages in a registry  
- `browse_package` - Examine package structure and metadata
- `search_package_contents` - Search within a specific package
- `check_quilt_auth` - Verify Quilt authentication status

## Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.11+ and [uv](https://docs.astral.sh/uv/) package manager
- Docker (for building Linux-compatible Lambda packages)
- IAM policy ARN for S3 read access to your Quilt buckets

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

## Local Development

See [quilt/DEPLOY.md](quilt/DEPLOY.md) for running locally with ngrok.

## Testing

```bash
uv run pytest tests/ -v
```

## Management

```bash
# View Lambda logs (use output from deploy.sh)
aws logs tail <LOG_GROUP_NAME> --follow --region <REGION>

# Update deployment
./deploy.sh

# Delete infrastructure  
cdk destroy
```
