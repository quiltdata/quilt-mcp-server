# IAM Mode (Local)

IAM mode uses your local AWS credentials and quilt3 session.

## Quick Start

```bash
export MCP_REQUIRE_JWT=false
export AWS_PROFILE=default
export QUILT_CATALOG_URL=https://your-catalog.quiltdata.com
uvx quilt-mcp
```

## Notes

- AWS credentials can come from env vars, profiles, or instance roles.
- JWT headers are ignored in IAM mode.
