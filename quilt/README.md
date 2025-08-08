# Quilt MCP Server

A Model Context Protocol (MCP) server that provides tools for interacting with Quilt data packages. This server allows you to browse, list, and search through Quilt packages stored in S3 registries.

## Features

- **List Packages**: Browse all packages in a Quilt registry with optional prefix filtering
- **Browse Package**: Explore the contents and metadata of specific packages
- **Search Package Contents**: Search within package files and metadata for specific terms
- ~~**Search Packages**: Full-text search across packages~~ (currently disabled due to configuration issues)

## Installation

### Prerequisites

- **AWS Credentials**: Required for accessing Quilt packages stored in S3. Configure using one of:
  - AWS CLI: `aws configure`
  - Environment variables: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
  - IAM roles (if running on EC2)
  - AWS credentials file (`~/.aws/credentials`)

### Setup

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "quilt": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/fast-mcp-server/quilt",
        "run",
        "main.py"
      ]
    }
  }
}
```

**Important**: Replace `/path/to/fast-mcp-server/quilt` with the actual path to this directory on your system.

After adding the configuration, restart Claude Desktop to load the Quilt MCP server.

## Usage

### Available Tools

#### `list_packages`

Lists all packages in a Quilt registry.

**Parameters:**

- `registry` (str): S3 bucket URL for the Quilt registry (default: "s3://quilt-example")
- `prefix` (str, optional): Filter package names by prefix

**Example:**

```python
list_packages(registry="s3://quilt-example", prefix="akarve")
```

#### `browse_package`

Browse a specific package to see its files and metadata.

**Parameters:**

- `package_name` (str): Name of the package to browse
- `registry` (str): S3 bucket URL for the Quilt registry (default: "s3://quilt-example")
- `hash_or_tag` (str, optional): Specific version hash or tag

**Example:**

```python
browse_package("akarve/tmp", registry="s3://quilt-example")
```

#### `search_package_contents`

Search within the contents of a specific package for files and metadata.

**Parameters:**

- `package_name` (str): Name of the package to search within
- `query` (str): Search terms to find files/metadata
- `registry` (str): S3 bucket URL for the Quilt registry (default: "s3://quilt-example")
- `hash_or_tag` (str, optional): Specific version hash or tag

**Example:**

```python
search_package_contents("akarve/tmp", "README", registry="s3://quilt-example")
```

## Example Data

The tests and examples use the `akarve/tmp` package from `s3://quilt-example`, which contains:

- `README.md` (826 bytes)
- `deck.pdf` (50,804 bytes)

## Limitations

- Package search functionality is currently disabled due to Quilt search API configuration requirements
- Large result sets are limited to prevent overwhelming responses
- Requires valid AWS credentials for accessing S3 buckets (including public ones like `s3://quilt-example`)

## Development

### Local Development Setup

1. Install dependencies:

```bash
uv sync
```

1. Run the server directly:

```bash
uv run main.py
```

### Testing

The server includes comprehensive tests that validate functionality against real Quilt packages:

```bash
uv run pytest -v
```

Tests use the actual `akarve/tmp` package from `s3://quilt-example` to verify:

- Package listing and filtering
- Package browsing and file enumeration
- Content searching within packages
- Error handling for invalid inputs

### Dependencies

- `quilt3`: Python SDK for Quilt data packages
- `fastmcp`: Framework for building MCP servers
- `pytest`: Testing framework (dev dependency)
