# Packaging Tools Curl Testing Guide

## Overview

This guide covers curl-based testing for the core packaging actions: **browse**, **create**, and **delete**.

> **Note**: `discover` and `list` actions have been removed. Use `search.unified_search()` instead.

## Quick Start

```bash
# 1. Set your JWT token
export QUILT_TEST_TOKEN="your-jwt-token"

# 2. Start the server (in another terminal)
make run

# 3. Run all packaging tests
make test-packaging-curl
```

## Test Targets

### Run All Tests
```bash
make test-packaging-curl
```
Runs both browse and create tests.

### Browse Test
```bash
make test-packaging-browse
```

**What it tests**:
- Package contents retrieval via GraphQL
- Entry counting
- Response validation
- Error handling

**Environment variables**:
- `QUILT_TEST_TOKEN` (required) - Your JWT authentication token
- `TEST_PACKAGE_NAME` (optional) - Package to browse (default: `demo-team/visualization-showcase`)

**Output**: `build/test-results/packaging-browse.json`

**Example output**:
```
🔍 Testing packaging.browse via curl...
Testing package browse: demo-team/visualization-showcase

→ Calling packaging.browse with package name...
{
  "jsonrpc": "2.0",
  "id": 102,
  "result": {
    "success": true,
    "package": {
      "name": "demo-team/visualization-showcase",
      "entries": [...]
    }
  }
}

✅ Package browse successful
   Found 42 entries in package

✅ Package browse test completed
```

### Create Test
```bash
make test-packaging-create
```

**What it tests**:
1. **Dry run validation** - Tests package creation with metadata
2. **Missing name error** - Validates error handling
3. **Missing files error** - Validates file requirement
4. **Organization features** - Tests auto-organize and metadata

**Environment variables**:
- `QUILT_TEST_TOKEN` (required) - Your JWT authentication token
- `TEST_S3_URI` (optional) - S3 URI for testing (default: example URI)

**Outputs**:
- `build/test-results/packaging-create-dry-run.json`
- `build/test-results/packaging-create-error-name.json`
- `build/test-results/packaging-create-error-files.json`
- `build/test-results/packaging-create-organized.json`

**Example output**:
```
🔍 Testing packaging.create via curl...
⚠️  Package creation requires pre-uploaded S3 files

Test 1: Dry run validation with valid S3 URI...
{
  "jsonrpc": "2.0",
  "id": 103,
  "result": {
    "success": true,
    "dry_run": true,
    "package_name": "quilt-example/test-pkg-curl",
    ...
  }
}
✅ Dry run validation successful

Test 2: Error handling with missing package name...
✅ Error handling working (missing name detected)

Test 3: Error handling with missing files...
✅ Error handling working (missing files detected)

Test 4: Metadata and organization features...
✅ Metadata and organization features working

✅ All package create tests completed
```

## Manual Curl Commands

### Browse a Package
```bash
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
        "action": "browse",
        "params": {
          "name": "demo-team/visualization-showcase"
        }
      }
    }
  }' | python3 -m json.tool
```

### Create Package (Dry Run)
```bash
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
        "action": "create",
        "params": {
          "name": "quilt-example/test-package",
          "files": ["s3://bucket/path/file.csv"],
          "description": "Test package",
          "metadata": {
            "version": "1.0.0",
            "author": "test"
          },
          "dry_run": true
        }
      }
    }
  }' | python3 -m json.tool
```

### Create Package (Actual Creation)
```bash
# Important: Files must already exist in S3
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
        "action": "create",
        "params": {
          "name": "your-bucket/your-package",
          "files": ["s3://your-bucket/path/file1.csv"],
          "description": "My new package",
          "metadata": {"version": "1.0.0"},
          "dry_run": false
        }
      }
    }
  }' | python3 -m json.tool
```

### Delete Package (Requires Confirmation)
Use a dry run first to verify which package will be removed, then add `confirm: true` to execute the deletion.

```bash
# Preview deletion
curl -s -X POST http://127.0.0.1:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $QUILT_TEST_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "packaging",
      "arguments": {
        "action": "delete",
        "params": {
          "name": "your-bucket/your-package",
          "bucket": "your-bucket",
          "dry_run": true
        }
      }
    }
  }' | python3 -m json.tool

# Execute deletion (irreversible)
curl -s -X POST http://127.0.0.1:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $QUILT_TEST_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tools/call",
    "params": {
      "name": "packaging",
      "arguments": {
        "action": "delete",
        "params": {
          "name": "your-bucket/your-package",
          "bucket": "your-bucket",
          "confirm": true
        }
      }
    }
  }' | python3 -m json.tool
```

## GraphQL Operations

### Browse Action
Uses direct GraphQL query:
```graphql
query PackageEntries($name: String!, $max: Int) {
  package(name: $name) {
    revision(hashOrTag: "latest") {
      contentsFlatMap(max: $max)
    }
  }
}
```

### Create Action
Uses GraphQL mutation:
```graphql
mutation PackageConstruct($params: PackagePushParams!, $src: PackageConstructSource!) {
  packageConstruct(params: $params, src: $src) {
    ... on PackagePushSuccess {
      package { bucket name }
      revision { hash modified message metadata userMeta }
    }
    ... on InvalidInput { _: Boolean }
    ... on OperationError { _: Boolean }
  }
}
```

## Expected Responses

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
          "hash": "sha256:abc123..."
        },
        {
          "logicalKey": "data/dataset.csv",
          "physicalKey": "s3://bucket/.quilt/packages/.../dataset.csv",
          "size": 567890,
          "hash": "sha256:def456..."
        }
      ]
    }
  }
}
```

### Successful Create (Dry Run)
```json
{
  "jsonrpc": "2.0",
  "id": 103,
  "result": {
    "success": true,
    "dry_run": true,
    "package_name": "quilt-example/test-pkg-curl",
    "files": [
      {
        "logical_key": "README.md",
        "physical_key": "s3://quilt-example/path/README.md"
      }
    ],
    "metadata": {
      "source": "curl-test",
      "author": "mcp-server"
    },
    "warnings": [],
    "message": "Dry run completed successfully"
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
    "error": "Authorization token required for package browsing"
  }
}
```

### Error Response (Missing Package Name)
```json
{
  "jsonrpc": "2.0",
  "id": 101,
  "result": {
    "success": false,
    "error": "Could not determine registry bucket"
  }
}
```

## Troubleshooting

### "QUILT_TEST_TOKEN not set"
**Solution**: Export your JWT token
```bash
export QUILT_TEST_TOKEN="eyJ..."
```

### "Connection refused"
**Solution**: Ensure the MCP server is running
```bash
# In another terminal
make run
# Wait for "Server starting on http://127.0.0.1:8001/mcp/"
```

### "Package not found" in browse test
**Solution**: Specify a valid package
```bash
export TEST_PACKAGE_NAME="your-bucket/your-package"
make test-packaging-browse
```

### Create test fails with "Invalid S3 URI"
**Solution**: Provide a valid S3 URI for testing
```bash
export TEST_S3_URI="s3://your-bucket/path/file.csv"
make test-packaging-create
```

## Package Discovery Alternative

Since `discover` and `list` actions have been removed, use the search tool:

### Discover All Packages
```bash
curl -s -X POST http://127.0.0.1:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $QUILT_TEST_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search",
      "arguments": {
        "action": "unified_search",
        "params": {
          "query": "*",
          "scope": "catalog",
          "search_type": "packages",
          "limit": 50
        }
      }
    }
  }' | python3 -m json.tool
```

### List Packages with Prefix
```bash
curl -s -X POST http://127.0.0.1:8001/mcp/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $QUILT_TEST_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search",
      "arguments": {
        "action": "unified_search",
        "params": {
          "query": "demo*",
          "scope": "catalog",
          "search_type": "packages",
          "limit": 20
        }
      }
    }
  }' | python3 -m json.tool
```

## CI/CD Integration

Add to your GitHub Actions workflow:

```yaml
- name: Test Packaging Tools
  env:
    QUILT_TEST_TOKEN: ${{ secrets.QUILT_TEST_TOKEN }}
  run: |
    make run &
    sleep 5  # Wait for server to start
    make test-packaging-curl
    
- name: Upload Test Results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: packaging-test-results
    path: build/test-results/packaging-*.json
```

## Related Documentation

- **Architecture Analysis**: `docs/architecture/PACKAGING_TOOLS_ANALYSIS.md`
- **Final Summary**: `PACKAGING_FINAL_SUMMARY.md`
- **Unit Tests**: `tests/unit/test_packaging_stateless.py`

## Support

For issues or questions:
1. Check server logs when running `make run`
2. Verify JWT token is valid and not expired
3. Ensure QUILT_CATALOG_URL is set correctly (e.g., `https://demo.quiltdata.com`)
4. Review test output files in `build/test-results/`




