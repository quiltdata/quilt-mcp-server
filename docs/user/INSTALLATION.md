# Installation Guide

This guide provides detailed installation instructions for the Quilt MCP Server across different environments and use cases.

## 🎯 Quick Installation

### Claude Desktop (Recommended)

The fastest way to get started:

1. **Download Extension**: Get the latest `.dxt` from [releases](https://github.com/quiltdata/quilt-mcp-server/releases)
2. **Install**: Double-click the `.dxt` file or use Claude Desktop → Settings → Extensions → Install from File
3. **Configure**: Set your Quilt catalog domain in Claude Desktop → Settings → Extensions → Quilt MCP
4. **Test**: Open Tools panel in a new chat and confirm Quilt MCP tools are available

## 📋 Prerequisites

### System Requirements

- **Python 3.11+** (required)
- **[uv](https://docs.astral.sh/uv/)** package manager (recommended)
- **AWS CLI** configured with credentials
- **Git** for cloning the repository

### Verify Prerequisites

```bash
# Check Python version
python3 --version
# Should output: Python 3.11.x or higher

# Check uv installation
uv --version
# If not installed: curl -LsSf https://astral.sh/uv/install.sh | sh

# Check AWS CLI
aws --version
aws sts get-caller-identity  # Verify credentials

# Check Git
git --version
```

## 🚀 Installation Methods

### Method 1: Local Development Setup

Perfect for development, customization, or when you need full control:

```bash
# 1. Clone repository
git clone https://github.com/quiltdata/quilt-mcp-server.git
cd quilt-mcp-server

# 2. Set up environment
cp env.example .env
# Edit .env with your configuration (see Configuration section)

# 3. Install dependencies
uv sync

# 4. Validate installation
make validate-app

# 5. Start server
make app
# Server available at http://127.0.0.1:8000/mcp
```

### Method 2: IDE Integration

#### Cursor Configuration

Add to your Cursor settings (`~/.cursor/mcp_servers.json`):

```json
{
  \"mcpServers\": {
    \"quilt\": {
      \"command\": \"/path/to/quilt-mcp-server/.venv/bin/python\",
      \"args\": [\"/path/to/quilt-mcp-server/app/main.py\"],
      \"env\": {
        \"PYTHONPATH\": \"/path/to/quilt-mcp-server/app\",
        \"QUILT_CATALOG_DOMAIN\": \"demo.quiltdata.com\",
        \"QUILT_DEFAULT_BUCKET\": \"s3://your-bucket\"
      }
    }
  }
}
```

#### VS Code Configuration

Add to your VS Code settings:

```json
{
  \"mcpServers\": {
    \"quilt\": {
      \"command\": \"/path/to/quilt-mcp-server/.venv/bin/python\",
      \"args\": [\"/path/to/quilt-mcp-server/app/main.py\"],
      \"env\": {
        \"PYTHONPATH\": \"/path/to/quilt-mcp-server/app\",
        \"QUILT_CATALOG_DOMAIN\": \"demo.quiltdata.com\"
      },
      \"description\": \"Quilt MCP Server\"
    }
  }
}
```

### Method 3: Docker Installation

For containerized deployments:

```bash
# 1. Clone repository
git clone https://github.com/quiltdata/quilt-mcp-server.git
cd quilt-mcp-server

# 2. Build Docker image
make build

# 3. Run container
docker run -p 8000:8000 \\
  -e QUILT_CATALOG_DOMAIN=demo.quiltdata.com \\
  -e QUILT_DEFAULT_BUCKET=s3://your-bucket \\
  -e AWS_ACCESS_KEY_ID=your-key \\
  -e AWS_SECRET_ACCESS_KEY=your-secret \\
  quilt-mcp-server:latest

# Server available at http://127.0.0.1:8000/mcp
```

## ⚙️ Configuration

### Environment Variables

Create and edit `.env` file:

```bash
# Required Configuration
QUILT_CATALOG_DOMAIN=your-catalog.quiltdata.com
QUILT_DEFAULT_BUCKET=s3://your-quilt-bucket
AWS_PROFILE=default

# Optional Configuration
QUILT_CATALOG_URL=https://your-catalog.quiltdata.com
AWS_REGION=us-east-1
MCP_SERVER_PORT=8000
MCP_SERVER_HOST=127.0.0.1

# Advanced Configuration
QUILT_CONFIG_DIR=/tmp/quilt  # For restricted filesystems
LOG_LEVEL=INFO
ENABLE_TELEMETRY=true
```

### AWS Configuration

#### Option A: AWS Profile (Recommended)

```bash
# Configure AWS CLI with profile
aws configure --profile quilt-dev
# Enter your AWS Access Key ID, Secret, and Region

# Set profile in .env
echo \"AWS_PROFILE=quilt-dev\" >> .env
```

#### Option B: Environment Variables

```bash
# Add to .env file
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1
```

#### Option C: IAM Roles (Production)

For production deployments, use IAM roles instead of credentials:

```bash
# No credentials needed in .env when using IAM roles
# The server will automatically use the instance/container role
```

### Quilt Catalog Configuration

#### Public Catalogs

```bash
# Quilt Demo Catalog (public)
QUILT_CATALOG_DOMAIN=demo.quiltdata.com
QUILT_DEFAULT_BUCKET=s3://quilt-example

# Quilt Open Data
QUILT_CATALOG_DOMAIN=open.quiltdata.com
QUILT_DEFAULT_BUCKET=s3://quilt-open-data
```

#### Private Catalogs

```bash
# Your organization's catalog
QUILT_CATALOG_DOMAIN=catalog.yourcompany.com
QUILT_CATALOG_URL=https://catalog.yourcompany.com
QUILT_DEFAULT_BUCKET=s3://yourcompany-quilt-data
```

## ✅ Validation and Testing

### Basic Validation

```bash
# Validate environment setup
scripts/check-env.sh

# Validate MCP server
make validate-app

# Test server response
curl -X POST http://localhost:8000/mcp \\
     -H \"Content-Type: application/json\" \\
     -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}'
```

### Client-Specific Validation

```bash
# Validate for Claude Desktop
scripts/check-env.sh claude

# Validate for Cursor
scripts/check-env.sh cursor

# Validate for VS Code
scripts/check-env.sh vscode
```

### Comprehensive Testing

```bash
# Run unit tests
make coverage

# Run integration tests
make test-app

# Run real-world validation
python test_cases/sail_user_stories_real_test.py
```

## 🔧 Troubleshooting

### Common Issues

#### Python Version Problems

**Issue**: \"Python 3.11+ required\"
```bash
# Check current version
python3 --version

# Install Python 3.11+ (macOS with Homebrew)
brew install python@3.11

# Install Python 3.11+ (Ubuntu)
sudo apt update
sudo apt install python3.11 python3.11-venv

# Update PATH if needed
export PATH=\"/usr/local/bin:$PATH\"
```

#### AWS Credential Issues

**Issue**: \"Unable to locate credentials\"
```bash
# Check AWS configuration
aws configure list
aws sts get-caller-identity

# Reconfigure if needed
aws configure --profile default

# Test S3 access
aws s3 ls s3://your-bucket
```

#### Module Import Errors

**Issue**: \"ModuleNotFoundError: No module named 'quilt_mcp'\"
```bash
# Ensure PYTHONPATH is set correctly
export PYTHONPATH=/path/to/quilt-mcp-server/app

# Or use absolute paths in configuration
# command: \"/full/path/to/.venv/bin/python\"
# args: [\"/full/path/to/app/main.py\"]
```

#### Permission Errors

**Issue**: \"Permission denied\" when creating packages
```bash
# Check bucket permissions
aws s3 ls s3://your-bucket

# Test write permissions
aws s3 cp test.txt s3://your-bucket/test.txt

# Use permission discovery tool
python -c \"
from app.quilt_mcp.tools.permissions import aws_permissions_discover
result = aws_permissions_discover()
print(result)
\"
```

#### Claude Desktop Issues

**Issue**: Tools not appearing in Claude Desktop
```bash
# Check Python accessibility in login shell
which python3
python3 --version

# Ensure Python is in PATH for GUI applications (macOS)
echo 'export PATH=\"/usr/local/bin:$PATH\"' >> ~/.zshrc
echo 'export PATH=\"/usr/local/bin:$PATH\"' >> ~/.bash_profile

# Restart Claude Desktop after PATH changes
```

### Environment-Specific Issues

#### macOS Issues

```bash
# Fix PATH for GUI applications
sudo launchctl config user path /usr/local/bin:/usr/bin:/bin

# Install Command Line Tools if needed
xcode-select --install

# Fix Python SSL certificates (if needed)
/Applications/Python\\ 3.11/Install\\ Certificates.command
```

#### Linux Issues

```bash
# Install required system packages
sudo apt update
sudo apt install python3.11-dev python3.11-venv build-essential

# Fix locale issues
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
```

#### Windows Issues

```bash
# Use Windows Subsystem for Linux (WSL) for best compatibility
wsl --install

# Or use PowerShell with proper Python installation
# Ensure Python 3.11+ is installed from python.org
# Add Python to PATH during installation
```

### Performance Issues

#### Slow Response Times

```bash
# Check network connectivity
ping demo.quiltdata.com

# Test AWS connectivity
aws s3 ls --region us-east-1

# Enable performance monitoring
export LOG_LEVEL=DEBUG
export ENABLE_TELEMETRY=true
```

#### Memory Issues

```bash
# Monitor memory usage
python -c \"
import psutil
print(f'Memory usage: {psutil.virtual_memory().percent}%')
\"

# Reduce memory usage
export QUILT_CACHE_SIZE=100MB  # Default: 1GB
export MCP_MAX_WORKERS=2       # Default: 4
```

## 🔄 Updates and Maintenance

### Updating the Server

```bash
# Pull latest changes
git pull origin main

# Update dependencies
uv sync

# Run validation
make validate-app

# Restart server
make app
```

### Updating Claude Desktop Extension

1. Download latest `.dxt` from [releases](https://github.com/quiltdata/quilt-mcp-server/releases)
2. Remove old extension: Claude Desktop → Settings → Extensions → Remove
3. Install new extension: Install from File → Select new `.dxt`
4. Restart Claude Desktop

### Health Monitoring

```bash
# Check server health
curl http://localhost:8000/health

# Monitor logs
tail -f logs/mcp-server.log

# Check system resources
make status
```

## 🚀 Advanced Installation

### Production Deployment

For production environments, see our [Deployment Guide](DEPLOYMENT.md):

```bash
# AWS ECS deployment
make deploy

# Docker Swarm deployment
docker stack deploy -c docker-compose.prod.yml quilt-mcp

# Kubernetes deployment
kubectl apply -f k8s/
```

### Custom Build

```bash
# Build custom Docker image
docker build -t my-quilt-mcp:latest .

# Build DXT extension
cd build-dxt && make build

# Build with custom configuration
make build CUSTOM_CONFIG=production
```

### Development Setup

```bash
# Install development dependencies
uv sync --group dev

# Set up pre-commit hooks
pre-commit install

# Run development server with hot reload
make dev

# Run tests in watch mode
make test-watch
```

## 📞 Getting Help

If you encounter issues not covered here:

1. **Check Documentation**: Review our [comprehensive docs](../docs/)
2. **Search Issues**: Look through [existing issues](https://github.com/quiltdata/quilt-mcp-server/issues)
3. **Run Diagnostics**: Use `scripts/check-env.sh` for automated diagnosis
4. **Ask Questions**: Create a [question issue](https://github.com/quiltdata/quilt-mcp-server/issues/new?template=question.yml)
5. **Report Bugs**: Use our [bug report template](https://github.com/quiltdata/quilt-mcp-server/issues/new?template=bug_report.yml)

## ✅ Next Steps

After successful installation:

1. **Explore Tools**: Use `make run-inspector` to explore available tools
2. **Read User Guide**: Check out our [Tool Reference](TOOLS.md)
3. **Try Examples**: Follow examples in our [documentation](../docs/)
4. **Join Community**: Participate in [GitHub Discussions](https://github.com/quiltdata/quilt-mcp-server/discussions)

Congratulations! You now have a fully functional Quilt MCP Server. 🎉
