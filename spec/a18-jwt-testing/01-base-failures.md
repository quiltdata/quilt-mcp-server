# Problem: MCP Test Suite Showing 50% Tool Failure Rate

**Date:** 2026-02-05
**Branch:** a18-valid-jwts
**Test Command:** `make test-mcp`
**Status:** 🔴 CRITICAL FAILURE

## Executive Summary

The MCP integration test suite is reporting a 50% failure rate (12/24 tools failing) with cryptic validation errors that provide no actionable diagnostic information. All 15 MCP resources pass successfully, indicating the server initializes correctly and can handle resource requests.

## Test Results Overview

### Tools (24 tested, 31 skipped)
- ✅ **12 passed** (50%)
- ❌ **12 failed** (50%)
- ⏭️ **31 skipped** (non-idempotent: configure, create, remove, update operations)

### Resources (15 tested)
- ✅ **15 passed** (100%)
- ❌ **0 failed**

## Failed Tools Analysis

### Category 1: Core Bucket Operations (5 failures)
Critical tools for basic S3 object access all failing:

1. **bucket_object_fetch** - Validation error with `s3_uri: "quilt-ernest-staging/raw/test/.timestamp"`
2. **bucket_object_info** - Validation error with same S3 URI
3. **bucket_object_link** - Validation error with same S3 URI
4. **bucket_object_text** - Validation error with same S3 URI
5. **check_bucket_access** - 2 validation errors (no input shown)

**Impact:** Users cannot read files, get metadata, or check permissions.

### Category 2: Athena Tools (2 failures)
Database query tools failing:

6. **athena_table_schema** - 2 validation errors
7. **athena_tables_list** - 1 validation error

**Impact:** Users cannot query table schemas or list available tables.

### Category 3: Admin Tools (1 failure)
User management tool failing:

8. **admin_user_get** - 1 validation error

**Impact:** Cannot retrieve user information.

### Category 4: Discovery Tools (1 failure)
Permission discovery failing:

9. **discover_permissions** - Validation error with `check_buckets: ["quilt-ernest-staging"]`

**Impact:** Cannot programmatically discover bucket permissions.

### Category 5: Tabulator Tools (3 failures - Expected)
Two tools fail due to missing configuration (not validation errors):

10. **tabulator_bucket_query** - "tabulator_data_catalog not configured"
11. **tabulator_list_buckets** - "tabulator_data_catalog not configured"
12. **tabulator_tables_list** - 1 validation error

**Note:** First two are expected configuration issues, not validation bugs.

## Critical Diagnostic Gap

### What We See
```
❌ bucket_object_fetch: FAILED - Tool returned error response
   Error: Validation error: 1 validation error for call[bucket_object_fetch]
```

### What We DON'T See
- **Which parameter** is invalid
- **What value** was provided vs. expected
- **Why** the validation failed
- **What constraint** was violated

### Example of Truncated Error
The full Pydantic validation error likely contains:
- Field name (e.g., `s3_uri`, `bucket`, `key`)
- Error type (e.g., `missing`, `type_error`, `value_error`)
- Error message (e.g., "field required", "invalid format")
- Input value that failed validation

**None of this information is being surfaced in the test output.**

## Test Input Observations

The test harness **is** providing inputs that look reasonable:

```json
{
  "s3_uri": "quilt-ernest-staging/raw/test/.timestamp",
  "max_bytes": 200
}
```

```json
{
  "check_buckets": ["quilt-ernest-staging"]
}
```

Yet these are triggering validation errors without explanation.

## Pattern Analysis

### Consistent Failures
- All `bucket_object_*` tools fail with validation errors
- All use similar S3 URI format: `bucket-name/path/to/file`
- No URI shows `s3://` prefix in test inputs

### Inconsistent Success
- `bucket_objects_list` (list directory) - ✅ PASSES
- `bucket_object_info` (get object metadata) - ❌ FAILS

**Why does listing work but metadata retrieval doesn't?**

## Hypotheses (Not Solutions)

Several possible root causes exist:

1. **S3 URI format mismatch** - Test config may be passing URIs in wrong format
2. **Missing required parameters** - Tool schemas may have changed
3. **Type coercion issues** - String vs. BucketUri types mismatched
4. **JWT/auth token format** - Validation may be checking token structure
5. **Backend initialization** - Quilt3 backend may not be fully initialized
6. **Test harness bug** - Error reporting may be swallowing details

## Why This is Critical

### Blocks Production Use
These aren't edge cases - they're **core operations**:
- Reading files from S3
- Getting file metadata
- Listing database tables
- Checking permissions

### Breaks User Trust
A 50% failure rate on basic operations makes the MCP server appear broken.

### Impossible to Debug
Without seeing actual validation errors, developers cannot:
- Fix misconfigured tests
- Identify schema mismatches
- Verify correct tool usage
- Write proper documentation

## What We Know Works

### Successful Tools (12/24)
- `bucket_objects_list` - List S3 directory ✅
- `athena_query_validate` - Validate SQL syntax ✅
- `catalog_uri` / `catalog_url` - Generate catalog links ✅
- `get_resource` - Fetch MCP resources ✅
- `package_browse` / `package_diff` - Package operations ✅
- `search_catalog` (3 variants) - Search functionality ✅
- `search_explain` / `search_suggest` - Search helpers ✅

### All Resources Work (15/15) ✅
- Authentication resources
- Admin resources (users, roles, SSO config)
- Athena resources (databases, workgroups, query history)
- Metadata resources
- Workflow resources
- Tabulator resources

**This proves:**
- Server starts successfully
- MCP protocol communication works
- Backend initializes
- Resources can be read

**But tool calls with parameters are failing silently.**

## Environment Context

```
Working Directory: /Users/ernest/GitHub/quilt-mcp-server
AWS Profile: default
AWS Region: us-east-1
Test Bucket: quilt-ernest-staging
Server Mode: Local (stdio)
Python: .venv/bin/python3
Config Source: .env
```

## Next Steps Required

1. **Expose full validation errors** in test output
2. **Inspect actual error messages** from Pydantic
3. **Compare tool schemas** vs. test inputs
4. **Verify S3 URI format** requirements
5. **Check JWT token validation** logic

## Files Referenced

- Test configuration: [scripts/tests/mcp-test.yaml](scripts/tests/mcp-test.yaml)
- Test runner: [scripts/tests/mcp-test.py](scripts/tests/mcp-test.py)
- Tool metadata: [build/tools_metadata.json](build/tools_metadata.json)
- Test fixtures: [tests/fixtures/mcp-list.csv](tests/fixtures/mcp-list.csv)

## Severity Assessment

**🔴 CRITICAL** - This is not a production blocker only because:
- Resources work (authentication, discovery)
- Some tools work (search, catalog links, package ops)

**BUT** it becomes critical because:
- Core file operations are broken (50% of tested tools)
- No diagnostic path forward without error details
- Cannot verify if this is test harness issue or actual bugs
