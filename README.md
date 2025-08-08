# Fast MCP Server - Quilt Edition

A Claude-compatible Model Context Protocol (MCP) server that provides tools for searching and browsing Quilt data packages in S3.

## 🚀 Quick Start - AWS Lambda Deployment

Deploy your Quilt MCP server to AWS Lambda for production use:

```bash
# 1. Configure environment
cp env.example .env
# Edit .env with your QUILT_READ_POLICY_ARN

# 2. Deploy to AWS
./deploy.sh

# 3. Connect Claude with the output URL and Cognito credentials
```

## 🛠️ Available Tools

- `search_packages` - Search for packages across Quilt registries
- `list_packages` - List all packages in a registry
- `browse_package` - Examine package structure and metadata
- `search_package_contents` - Search within a specific package
- `check_quilt_auth` - Verify Quilt authentication status

## 📋 Prerequisites

### For AWS Lambda Deployment

- AWS CLI configured with appropriate permissions
- Python 3.12+ and [uv](https://docs.astral.sh/uv/) package manager
- AWS CDK CLI: `npm install -g aws-cdk`
- IAM policy ARN for S3 read access to your Quilt buckets

### For Local Development

- Python 3.12+ and [uv](https://docs.astral.sh/uv/) package manager
- ngrok (for exposing local server)
- Quilt credentials (optional, for authenticated registries)

## 🏗️ Architecture

### AWS Lambda (Production)

- **Lambda Function**: Python 3.11 runtime with Quilt MCP server
- **API Gateway**: HTTP API with CORS and Cognito authentication
- **IAM Role**: S3 read permissions via your managed policy
- **Cognito**: User pool with OAuth2 client credentials flow

### Local Development

- FastMCP HTTP server with ngrok tunnel
- Direct S3 access using local AWS credentials

## 📁 Project Structure

```tree
├── README.md              # This file - main documentation
├── deploy.sh             # Automated deployment script  
├── app.py                # CDK application
├── quilt_mcp_stack.py    # Infrastructure stack
├── cdk.json              # CDK configuration
├── pyproject.toml         # Modern Python dependency management
├── uv.lock               # Dependency lockfile
├── env.example           # Environment template
├── tests/                # Centralized test suite
│   ├── test_quilt_tools.py    # Unit tests for Quilt MCP tools
│   ├── test_lambda_handler.py # AWS Lambda wrapper tests
│   └── test_cdk_stack.py      # Infrastructure tests
├── quilt/                # MCP server implementation
│   ├── quilt.py          # Main MCP tools (5 functions)
│   ├── remote.py         # Local HTTP server
│   ├── lambda_handler.py # AWS Lambda wrapper
│   ├── main.py           # CLI entry point
│   └── DEPLOY.md         # Local development guide
├── cdk.out/              # CDK build artifacts (auto-generated)
└── weather/              # Example MCP server
    ├── weather.py        # Weather MCP server
    └── pyproject.toml    # Independent dependencies
```

## 🔧 Configuration

Copy `env.example` to `.env` and configure:

```bash
# Required for AWS deployment
QUILT_READ_POLICY_ARN=arn:aws:iam::123456789012:policy/YourQuiltReadPolicy

# Optional
CDK_DEFAULT_ACCOUNT=123456789012
CDK_DEFAULT_REGION=us-east-1
AWS_PROFILE=default
```

## 🧪 Testing

Run the test suite:

```bash
uv run pytest tests/ -v
```

## 📊 Usage & Costs

### AWS Lambda Costs

- **Free Tier**: 1M requests/month + 400k GB-seconds compute
- **After Free Tier**: ~$0.20 per 1M requests + compute time
- **API Gateway**: ~$3.50 per million API calls
- **Typical MCP usage**: < $1/month for most users

### Rate Limits

- Cognito OAuth2 token-based authentication
- No built-in request limits (configure via API Gateway throttling if needed)

## 🔐 Security

- Cognito OAuth2 authentication for all endpoints
- JWT token validation
- IAM role-based S3 access (no embedded credentials)
- CORS enabled for Claude web interface
- CloudWatch logging for audit trails

## 🛠️ Management

```bash
# View Lambda logs (function name provided by deploy.sh)
aws logs tail /aws/lambda/QuiltMcpStack-QuiltMcpFunction --follow

# View logs using exact log group name from deployment output
aws logs tail <LOG_GROUP_NAME> --follow --region <REGION>

# Create a Cognito user for authentication
aws cognito-idp admin-create-user --user-pool-id <USER_POOL_ID> --username <username> --temporary-password <temp-password> --region <REGION>

# Update deployment
./deploy.sh

# Delete infrastructure
cdk destroy
```

## 📚 Local Development

For local testing and development, see [quilt/DEPLOY.md](quilt/DEPLOY.md) for instructions on running the server locally with ngrok.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run the test suite
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.
