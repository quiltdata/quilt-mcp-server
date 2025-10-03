# Packaging Tools Testing - Quick Start Guide

## Prerequisites

1. **JWT Token**: Obtain from Quilt catalog
   ```bash
   export QUILT_TEST_TOKEN="your-jwt-token-here"
   ```

2. **Server Running**: MCP server must be running locally
   ```bash
   make run
   # Or in another terminal for testing
   ```

3. **Optional Environment Variables**:
   ```bash
   export TEST_PACKAGE_NAME="demo-team/visualization-showcase"  # For browse test
   export TEST_S3_URI="s3://bucket/path/file.csv"              # For create test
   ```

## Running Tests

### Run All Packaging Tests
```bash
make test-packaging-curl
```

### Run Individual Tests

**1. Discover Packages**
```bash
make test-packaging-discover
# Output: build/test-results/packaging-discover.json
```

**2. List Packages**
```bash
make test-packaging-list
# Output: build/test-results/packaging-list.json
```

**3. Browse Package Contents**
```bash
# Uses default package or TEST_PACKAGE_NAME
make test-packaging-browse
# Output: build/test-results/packaging-browse.json
```

**4. Create Package (Dry Run)**
```bash
# Tests package creation validation without actually creating
make test-packaging-create
# Output: build/test-results/packaging-create-dry-run.json
```

## Example Responses

### Successful Discovery
```json
{
  "jsonrpc": "2.0",
  "id": 100,
  "result": {
    "success": true,
    "packages": [
      {
        "name": "demo-team/visualization-showcase",
        "description": "Package description",
        "bucket": "demo-team",
        "modified": "2025-10-03T12:00:00Z",
        "size": 12345,
        "accessible": true
      }
    ],
    "total_packages": 1
  }
}
```

### Successful Browse
```json
{
  "jsonrpc": "2.0",
  "id": 102,
  "result": {
    "success": true,
    "package": {
      "name": "demo-team/visualization-showcase",
      "entries": [
        {
          "logicalKey": "README.md",
          "physicalKey": "s3://bucket/.quilt/packages/.../README.md",
          "size": 1234,
          "hash": "sha256:..."
        }
      ]
    }
  }
}
```

### Error Response (Missing Token)
```json
{
  "jsonrpc": "2.0",
  "id": 100,
  "result": {
    "success": false,
    "error": "Authorization token required for package discovery"
  }
}
```

## Troubleshooting

### Issue: "QUILT_TEST_TOKEN not set"
**Solution**: Export your JWT token
```bash
export QUILT_TEST_TOKEN="eyJ..."
```

### Issue: "Connection refused"
**Solution**: Start the MCP server
```bash
make run
# Wait for "Server starting on http://127.0.0.1:8001/mcp/"
```

### Issue: "Package not found" in browse test
**Solution**: Set a valid package name
```bash
export TEST_PACKAGE_NAME="your-bucket/your-package"
make test-packaging-browse
```

### Issue: Test hangs or times out
**Solution**: Check server logs and ensure catalog URL is configured
```bash
# In .env file
QUILT_CATALOG_URL=https://demo.quiltdata.com
```

## Direct Curl Commands

If you prefer to run curl commands directly:

```bash
# Package Discovery
curl -s -X POST http://127.0.0.1:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $QUILT_TEST_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "packaging",
      "arguments": {
        "action": "discover",
        "params": {"limit": 50}
      }
    }
  }' | python3 -m json.tool

# Package List
curl -s -X POST http://127.0.0.1:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $QUILT_TEST_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "packaging",
      "arguments": {
        "action": "list",
        "params": {"limit": 20, "prefix": ""}
      }
    }
  }' | python3 -m json.tool

# Package Browse
curl -s -X POST http://127.0.0.1:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $QUILT_TEST_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "packaging",
      "arguments": {
        "action": "browse",
        "params": {"name": "demo-team/visualization-showcase"}
      }
    }
  }' | python3 -m json.tool
```

## Testing Against Production

To test against a production MCP server:

```bash
# Set the endpoint
export DEV_ENDPOINT="https://your-production-server.com/mcp/"

# Run tests
make test-packaging-curl
```

## Viewing Test Results

Test results are saved as formatted JSON files:

```bash
# View all results
ls -lh build/test-results/packaging-*.json

# Pretty-print a result
cat build/test-results/packaging-discover.json | python3 -m json.tool

# Check for errors
grep -l '"success": false' build/test-results/packaging-*.json
```

## Integration with CI/CD

Add to your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Test Packaging Tools
  env:
    QUILT_TEST_TOKEN: ${{ secrets.QUILT_TEST_TOKEN }}
  run: |
    make run &
    sleep 5  # Wait for server to start
    make test-packaging-curl
```

## Next Steps

- Review the comprehensive analysis: `docs/architecture/PACKAGING_TOOLS_ANALYSIS.md`
- Read the full summary: `PACKAGING_TOOLS_TEST_SUMMARY.md`
- Check unit tests: `tests/unit/test_packaging_stateless.py`

## Support

For issues or questions:
1. Check server logs when running `make run`
2. Verify JWT token is valid and not expired
3. Ensure QUILT_CATALOG_URL is set correctly
4. Review the analysis document for detailed information

