# Bugs in Current `make test-mcp` Implementation

**Date:** 2025-11-12
**Status:** Documented - Awaiting Fix
**Related:** [07-unified-test-client.md](./07-unified-test-client.md)

## Overview

This document captures identified bugs in the current `make test-mcp` implementation that need to be addressed before the test suite can be considered production-ready.

## Bug 1: Using 'open' Catalog Instead of QUILT_CATALOG_DOMAIN

**Location:** [scripts/tests/mcp-test.yaml:16](../../scripts/tests/mcp-test.yaml#L16)

**Current Behavior:**
```yaml
test_tools:
  catalog_configure:
    arguments:
      catalog_url: s3://quilt-ernest-staging  # ❌ Wrong - this is a bucket, not a catalog
```

**Expected Behavior:**
The test should use the `QUILT_CATALOG_DOMAIN` environment variable defined in the same file:

```yaml
environment:
  QUILT_CATALOG_DOMAIN: nightly.quilttest.com  # ✅ Correct catalog domain
```

**Impact:**
- Tests are not validating against the correct catalog configuration
- The `catalog_configure` tool receives an S3 bucket URI instead of a catalog domain
- This likely causes the tool to use a default/fallback catalog ('open') instead of the intended test catalog

**Root Cause:**
The test configuration generator ([scripts/mcp-list.py](../../scripts/mcp-list.py)) is using `QUILT_DEFAULT_BUCKET` for catalog_configure instead of `QUILT_CATALOG_DOMAIN`.

---

## Bug 2: Tests Do NOT Fail on `status:error` Responses

**Location:** [scripts/tests/test_mcp.py:322-330](../../scripts/tests/test_mcp.py#L322-L330)

**Current Behavior:**
```python
result = json.loads(response)
if "error" in result:
    fail_count += 1
    print(f"  ❌ {tool_name}: {result['error'].get('message', 'Unknown error')} ({elapsed:.2f}s)")
else:
    success_count += 1
    print(f"  ✅ {tool_name} ({elapsed:.2f}s)")
```

**Problem:**
The test only checks for JSON-RPC level errors (malformed requests, protocol errors), but **does NOT check the tool result content** for `status: "error"` responses.

**Example of Undetected Failure:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"status\": \"error\", \"message\": \"Access denied\"}"
      }
    ]
  }
}
```

This response would be marked as ✅ **PASSED** even though the tool execution failed!

**Expected Behavior:**
The test should:
1. Parse the tool result content
2. Check for `status: "error"` in the response
3. Mark the test as FAILED if status is error
4. Only mark as PASSED if status is "success" or the operation completed successfully

**Impact:**
- False positive test results
- Tools that fail internally are reported as passing
- Test suite provides false confidence in functionality

---

## Bug 3: Search Operations Run AFTER Bucket Operations

**Location:** [scripts/tests/test_mcp.py:290-352](../../scripts/tests/test_mcp.py#L290-L352)
**Config Location:** [scripts/tests/mcp-test.yaml:311-341](../../scripts/tests/mcp-test.yaml#L311-L341)

**Current Behavior:**
Tests run in the order they appear in `mcp-test.yaml`:
1. Catalog operations (catalog_configure, catalog_uri, catalog_url)
2. Bucket operations (bucket_object_fetch, bucket_object_info, etc.)
3. Package operations (package_browse, package_diff)
4. **Search operations (search_catalog, search_explain, search_suggest)** ← Too late!

**Problem:**
Search operations should run **before** bucket operations to:
1. Discover available packages/objects to test with
2. Use real search results to populate test parameters for subsequent operations
3. Validate that search functionality works before depending on it

**Expected Behavior:**
Test order should be:
1. Catalog operations (setup)
2. **Search operations (discovery)** ← Move here
3. Bucket operations (using search results)
4. Package operations (using search results)

**Impact:**
- Tests use hardcoded/static test data instead of discovered data
- Cannot validate end-to-end workflows that depend on search
- Missed opportunity to make tests more realistic and data-driven

**Example Improved Workflow:**
```python
# 1. Configure catalog
catalog_configure(catalog_url="nightly.quilttest.com")

# 2. Search for test packages (NEW - moved earlier)
results = search_catalog(query="test", limit=10)
if results and len(results) > 0:
    first_package = results[0]['package_name']
    first_object = results[0]['s3_uri']

    # 3. Use discovered data for bucket operations
    bucket_object_info(s3_uri=first_object)

    # 4. Use discovered data for package operations
    package_browse(package_name=first_package)
```

---

## Bug 4: Input Validation Errors Marked as PASSED

**Evidence from Test Output:**
```
Response: {"jsonrpc":"2.0","id":12,"result":{"content":[{"type":"text","text":"Input validation error: 'CONFIGURE_ORGANIZED_STRUCTURE' is not of type 'object'"}],"isError":true}}
  ✅ generate_package_visualizations (0.00s)
     Result: Input validation error: 'CONFIGURE_ORGANIZED_STRUCTURE' is not of type 'object'
```

**Problem:**
Multiple tools have **placeholder configuration values** (e.g., `CONFIGURE_ORGANIZED_STRUCTURE`, `CONFIGURE_ENABLED`) that cause input validation errors, yet these are still marked as ✅ **PASSED**.

**Affected Tools:**
1. `generate_package_visualizations` - `CONFIGURE_ORGANIZED_STRUCTURE` (not an object)
2. `generate_quilt_summarize_json` - Multiple `CONFIGURE_*` placeholders
3. `tabulator_open_query_toggle` - `CONFIGURE_ENABLED` (not a boolean)
4. `workflow_template_apply` - `CONFIGURE_TEMPLATE_NAME` (invalid enum value)
5. `search_suggest` - `CONFIGURE_PARTIAL_QUERY` (not a meaningful test)

**Impact:**
- 5+ tools are not actually being tested, just returning validation errors
- Test configuration is incomplete/invalid
- False positive results (claiming 22/22 passed when many are validation errors)

**Root Cause:**
The test configuration generator ([scripts/mcp-list.py](../../scripts/mcp-list.py)) creates placeholder values for complex parameters instead of valid test data.

---

## Bug 5: Tests Pass Despite Tool Execution Failures

**Evidence from Test Output:**
```
Response: {"jsonrpc":"2.0","id":5,"result":{"content":[{"type":"text","text":"{\"error\":\"Failed to get object: An error occurred (NoSuchKey)...
  ✅ bucket_object_fetch (0.40s)
     Result: {"error":"Failed to get object: An error occurred (NoSuchKey)...
```

**Problem:**
Tools that return `"error"` or `"success": false` in their response are marked as ✅ **PASSED**. This is a manifestation of Bug #2 but worth documenting with actual examples.

**Affected Tools with Failures Marked as Passed:**
1. `catalog_configure` - `"status":"error"` (failed to configure catalog)
2. `bucket_object_fetch` - `"error":"Failed to get object: NoSuchKey"`
3. `bucket_object_info` - `"error":"Failed to head object: 404 Not Found"`
4. `bucket_object_text` - `"error":"Failed to get object: NoSuchKey"`
5. `athena_query_execute` - `"success":false, "error":"SQL execution error"`
6. `athena_query_validate` - `"success":false, "valid":false`
7. `tabulator_bucket_query` - `"success":false, "error":"SQL execution error"`
8. `tabulator_open_query_status` - `"success":false, "error":"Unauthorized"`
9. `tabulator_table_rename` - `"success":false, "error":"Unauthorized"`

**Impact:**
- **At least 9 out of 22 tests (41%) are actually failing but reported as passing**
- Test suite claims "22/22 passed" when reality is closer to "13/22 passed"
- Critical loss of test signal - cannot trust test results at all

---

## Bug 6: Invalid Test Data (Hardcoded Paths Don't Exist)

**Evidence:**
```
Arguments: {"s3_uri": "s3://quilt-ernest-staging/README.md", "max_bytes": 10}
Result: {"error":"Failed to get object: NoSuchKey"}
```

**Problem:**
Test configuration uses hardcoded S3 paths (`README.md` at bucket root) that don't actually exist in the test bucket.

**Affected Tests:**
- `bucket_object_fetch` - Tests against non-existent `README.md`
- `bucket_object_info` - Tests against non-existent `README.md`
- `bucket_object_text` - Tests against non-existent `README.md`
- `bucket_objects_list` - Searches for prefix `README.md` (returns 0 objects)

**Expected Behavior:**
Tests should either:
1. Use the search results to find real objects to test against (Bug #3)
2. Discover actual bucket contents dynamically
3. Set up known test fixtures in the test bucket

**Impact:**
- Tests are not validating actual functionality, just error handling
- Cannot distinguish between "tool works" vs "test data missing"
- No coverage of successful code paths

---

## Bug 7: Invalid SQL Queries Used for Athena Tests

**Evidence:**
```
Arguments: {"query": "test", "max_results": 10}
Result: {"success":false,"error":"...mismatched input 'test'. Expecting: 'ALTER', 'ANALYZE', 'CALL'..."}
```

**Problem:**
Athena tools are being tested with the literal string `"test"` as a SQL query, which is invalid SQL.

**Affected Tools:**
- `athena_query_execute` - `query: "test"` (invalid SQL)
- `athena_query_validate` - `query: "test"` (invalid SQL)
- `tabulator_bucket_query` - `query: "test"` (invalid SQL)

**Expected Behavior:**
Should use valid SQL like:
- `"SELECT 1"` - Simple validation query
- `"SHOW TABLES"` - List available tables
- `"SELECT * FROM table_name LIMIT 10"` - Actual data query

**Impact:**
- Not testing actual SQL execution capability
- Only testing error handling, not success paths
- Missing validation of query parsing, result formatting, etc.

---

## Bug 8: Authorization Failures Not Distinguished from Tool Failures

**Evidence:**
```
Response: {"success":false,"error":"Failed to get open query status: Unauthorized"...}
  ✅ tabulator_open_query_status (0.11s)
```

**Problem:**
Tools that fail due to authorization/permissions issues are treated the same as tools that execute successfully. Cannot distinguish between:
- "Tool works but user lacks permissions" (expected in some environments)
- "Tool is broken" (needs to be fixed)

**Affected Tools:**
- `tabulator_open_query_status` - Unauthorized (may be expected)
- `tabulator_table_rename` - Unauthorized (may be expected)

**Expected Behavior:**
Tests should:
1. Skip tests that require admin permissions when not available
2. Mark authorization failures as "SKIP" rather than "PASS" or "FAIL"
3. Document which tests require elevated permissions

---

## Bug 9: Container Cleanup Timeout Warning

**Evidence:**
```
🛑 Stopping container mcp-test-3db51d7d...
⚠️  Timeout, force killing...
✅ Container cleaned up
```

**Problem:**
The Docker container doesn't gracefully shutdown within the timeout period and must be force-killed.

**Location:** [scripts/tests/test_mcp.py:143-148](../../scripts/tests/test_mcp.py#L143-L148)

**Impact:**
- Slower test execution (10 second timeout + force kill)
- Potential resource leaks if force kill fails
- May indicate MCP server isn't handling shutdown signals properly

**Possible Causes:**
1. MCP server doesn't handle SIGTERM gracefully
2. Timeout is too short (currently 10 seconds)
3. stdio transport doesn't support clean shutdown protocol

---

## Bug 10: False Positive "open.quiltdata.com" Catalog Configuration

**Evidence:**
```
Response: ...,"catalog_host":"open.quiltdata.com"}
```

**Problem:**
Multiple catalog-related tools default to `open.quiltdata.com` even though the environment specifies `QUILT_CATALOG_DOMAIN: nightly.quilttest.com`.

**Affected Tools:**
- `catalog_uri` - Returns `catalog=open.quiltdata.com` in URI
- `catalog_url` - Returns URLs pointing to `open.quiltdata.com`

**Root Cause:**
This is the manifestation of Bug #1 - because `catalog_configure` fails, subsequent tools fall back to the hardcoded default catalog.

**Impact:**
- Tests run against wrong catalog environment
- Can't validate catalog-specific functionality
- May accidentally test production catalog instead of test/staging

---

## Recommended Fix Priority

1. **CRITICAL: Bug #5** - 41% of tests failing but marked as passing
   - Immediate false confidence in test suite
   - Must check for `"success": false`, `"error"` keys, and `"status": "error"` in responses
   - Blocks all other fixes (can't trust current results)

2. **CRITICAL: Bug #2** - Related to Bug #5, broader issue
   - Need proper status/error checking in test framework
   - Must parse JSON responses and validate success criteria

3. **HIGH: Bug #4** - Invalid test configuration with placeholders
   - 5+ tools not really being tested
   - Need to generate valid test parameters
   - Affects test coverage significantly

4. **HIGH: Bug #1** - Wrong catalog configuration
   - Cascades to cause Bug #10
   - Tests run against wrong environment
   - Should use `QUILT_CATALOG_DOMAIN` not `QUILT_DEFAULT_BUCKET`

5. **HIGH: Bug #6** - Invalid test data (missing S3 objects)
   - Need dynamic test data discovery or fixture setup
   - Related to Bug #3 (test ordering)

6. **MEDIUM: Bug #7** - Invalid SQL queries
   - Easy fix (use valid SQL)
   - Blocks testing of Athena functionality

7. **MEDIUM: Bug #8** - Authorization failures not distinguished
   - Should skip rather than fail/pass
   - Need better test categorization

8. **LOW: Bug #3** - Test execution order
   - Enhancement for better test realism
   - Would help solve Bug #6

9. **LOW: Bug #9** - Container cleanup timeout
   - Slowdown but not blocking
   - May indicate deeper issue

10. **LOW: Bug #10** - Consequence of Bug #1
    - Will be fixed when Bug #1 is resolved

---

## Related Issues

- Test configuration generation: [scripts/mcp-list.py](../../scripts/mcp-list.py)
- Test execution: [scripts/tests/test_mcp.py](../../scripts/tests/test_mcp.py)
- Test data: [scripts/tests/mcp-test.yaml](../../scripts/tests/mcp-test.yaml)

---

## Next Steps

1. Document fix approaches for each bug
2. Implement fixes with tests
3. Validate that fixes don't break existing test infrastructure
4. Update documentation to reflect corrected behavior
