# Sample README for Testing

This is a sample README file used for testing the README command extraction functionality.

## Installation

### Option A: Cloud Installation
Use our cloud service for easy setup.

### Option B: Local Development

For development or custom configurations:

```bash
# 1. Clone and setup
git clone https://github.com/quiltdata/quilt-mcp-server.git
cd quilt-mcp-server
cp env.example .env
# Edit .env with your AWS credentials and Quilt settings

# 2. Install dependencies
uv sync

# 3. Run server
make app
# Server available at http://127.0.0.1:8000/mcp
```

### Option C: Docker Installation
Use Docker for containerized setup.

## Usage

After installation, you can use the server for various operations.