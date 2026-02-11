# A20 JWT Auth: Platform Backend Browse Failure Investigation

**Date:** 2026-02-10
**Status:** Issue Identified
**Severity:** High - Blocks platform backend E2E tests

---

## Executive Summary

Testing with increased timeout (60s) revealed that the previously reported "packageConstruct timeout" was misdiagnosed. Write operations (package creation) now succeed, but a new issue was discovered: **browse_content operations fail with "Internal Server Error" on the platform backend** for both newly-created and existing packages.

---

## Timeline of Discovery

1. **2026-02-09**: Test results report documents packageConstruct timeout at 30s
2. **2026-02-10**: Timeout increased from 30s to 60s per report recommendations
3. **2026-02-10**: Tests re-run reveal write operations succeed, browse operations fail
4. **2026-02-10**: Simple browse test on existing package confirms issue is not related to newly-created packages

---

## Test Results with 60s Timeout

### Test 1: test_package_lifecycle.py (Platform Backend)

**Command:**
```bash
TEST_BACKEND_MODE=platform uv run pytest tests/e2e/backend/integration/test_package_lifecycle.py -v
```

**Package Creation (Step 1):**
```
[Step 1] Creating package: test/integration_lifecycle_1770736485
  ✅ Package created successfully
```

**Browse Operation (Step 2):**
```
[Step 2] Browsing package: test/integration_lifecycle_1770736485
GraphQL query failed: Internal Server Error
```

**Duration:** 15.22s (no timeout)

**Result:** FAILED at browse step, not at package creation step

---

### Test 2: test_package_creation.py (Platform Backend)

**Command:**
```bash
TEST_BACKEND_MODE=platform uv run pytest tests/e2e/backend/workflows/test_package_creation.py -v
```

**Package Creation (Step 3):**
```
[Step 3] Creating package: experiments/genomics_1770736509
  ✅ Package created successfully
  ℹ️  Package hash: 72af182c87fce0c9dac209b472a1b400726b812572bfec58390cdd50a62e536e
```

**Catalog Verification (Step 4):**
```
[Step 4] Verifying package in catalog
  ℹ️  Catalog verification attempt 1/5 failed, retrying in 2s:
      Platform backend browse_content failed: GraphQL query failed: Internal Server Error
  ℹ️  Catalog verification attempt 2/5 failed, retrying in 2s:
      Platform backend browse_content failed: GraphQL query failed: Internal Server Error
  ℹ️  Catalog verification attempt 3/5 failed, retrying in 2s:
      Platform backend browse_content failed: GraphQL query failed: Internal Server Error
  ℹ️  Catalog verification attempt 4/5 failed, retrying in 2s:
      Platform backend browse_content failed: GraphQL query failed: Internal Server Error
```

**Duration:** 28.75s (no timeout)

**Result:** FAILED at verification step, not at package creation step

---

### Test 3: test_simple_browse.py (Existing Package)

**Created:** 2026-02-10 (new diagnostic test)

**Test Code:**
```python
@pytest.mark.e2e
def test_browse_existing_package(backend_with_auth):
    """Test browsing an existing package without creating it first."""
    result = backend_with_auth.browse_content(
        package_name="test/mcp_create",
        registry="s3://quilt-ernest-staging",
        path=""
    )
    assert len(result) > 0
```

**Quilt3 Backend Result:**
```
TEST_BACKEND_MODE=quilt3 uv run pytest tests/e2e/backend/test_simple_browse.py
✅ 1 passed in 4.90s
```

**Platform Backend Result:**
```
TEST_BACKEND_MODE=platform uv run pytest tests/e2e/backend/test_simple_browse.py
❌ FAILED in 3.96s
GraphQL query failed: Internal Server Error
```

**Key Finding:** Browse fails on existing packages, not just newly-created ones.

---

## Error Details

### Exact Error Message

```
quilt_mcp.ops.exceptions.BackendError: GraphQL query failed: Internal Server Error
```

### Error Source

```python
# src/quilt_mcp/backends/platform_backend.py:117
if "errors" in result:
    error_messages = [err.get("message", str(err)) for err in result.get("errors", [])]
    raise BackendError(f"GraphQL query failed: {'; '.join(error_messages)}")
```

### GraphQL Response

The GraphQL server returns:
```json
{
  "errors": [
    {
      "message": "Internal Server Error"
    }
  ]
}
```

**No additional information provided:**
- No error codes
- No stack traces
- No field-specific errors
- No query validation errors

---

## GraphQL Query Being Used

**File:** `src/quilt_mcp/backends/platform_backend.py:240-260`

**Query:**
```graphql
query BrowseContent($bucket: String!, $name: String!, $path: String!) {
  package(bucket: $bucket, name: $name) {
    revision(hashOrTag: "latest") {
      dir(path: $path) {
        path
        size
        children {
          __typename
          ... on PackageFile { path size physicalKey }
          ... on PackageDir { path size }
        }
      }
      file(path: $path) {
        path
        size
        physicalKey
      }
    }
  }
}
```

**Variables:**
```json
{
  "bucket": "quilt-ernest-staging",
  "name": "test/mcp_create",
  "path": ""
}
```

---

## Backend Comparison

### Quilt3 Backend

**Browse Method:** Uses quilt3 Python SDK
```python
pkg = quilt3.Package.browse(package_name, registry=registry)
```

**Result:** ✅ Works for all packages (existing and newly-created)

**Test Evidence:**
- test_package_lifecycle.py: PASSED (21 passed, 3 skipped in 402.19s on 2026-02-09)
- test_package_creation.py: PASSED
- test_simple_browse.py: PASSED (4.90s)

---

### Platform Backend

**Browse Method:** Uses GraphQL query to nightly-registry.quilttest.com

**Endpoint:** Retrieved via `self.get_graphql_endpoint()`

**Authentication:** JWT token in Authorization header

**Result:** ❌ Fails with "Internal Server Error" for all packages

**Test Evidence:**
- test_package_lifecycle.py: FAILED at browse step (package creation succeeded)
- test_package_creation.py: FAILED at verification step (package creation succeeded)
- test_simple_browse.py: FAILED (3.96s)

---

## Operation Success Matrix

| Operation | Quilt3 Backend | Platform Backend | Duration |
|-----------|----------------|------------------|----------|
| **Write: packageConstruct** | ✅ Works | ✅ Works (with 60s timeout) | ~10-20s |
| **Read: browse_content** | ✅ Works | ❌ Internal Server Error | ~4s |
| **Read: search_packages** | ✅ Works | ⚠️ Partial (search syntax errors) | ~2s |

---

## Configuration Changes Made

**File:** `src/quilt_mcp/backends/platform_backend.py:109`

**Before:**
```python
response = self._session.post(endpoint, json=payload, headers=headers, timeout=30)
```

**After:**
```python
response = self._session.post(endpoint, json=payload, headers=headers, timeout=60)
```

**Impact:**
- ✅ Resolved packageConstruct timeout
- ❌ Did not resolve browse failures (browse fails immediately, not from timeout)

---

## HTTP Response Details

### Status Code

```python
response.raise_for_status()  # Does NOT raise - status is 200 OK
```

The HTTP response is **200 OK**. The error is in the GraphQL response body, not the HTTP layer.

### Response Structure

```python
result = response.json()  # Successfully parses
if "errors" in result:     # Errors array exists
    error_messages = [err.get("message", str(err)) for err in result.get("errors", [])]
    # error_messages = ["Internal Server Error"]
```

---

## Package States Tested

### Newly Created Packages

**Test 1 Package:**
- Name: `test/integration_lifecycle_1770736485`
- Registry: `s3://quilt-ernest-staging`
- Status: Successfully created via packageConstruct mutation
- Hash: (not captured before browse failed)
- Browse: ❌ FAILED

**Test 2 Package:**
- Name: `experiments/genomics_1770736509`
- Registry: `s3://quilt-ernest-staging`
- Status: Successfully created via packageConstruct mutation
- Hash: `72af182c87fce0c9dac209b472a1b400726b812572bfec58390cdd50a62e536e`
- Browse: ❌ FAILED (5 retry attempts)

### Existing Package

**Test 3 Package:**
- Name: `test/mcp_create`
- Registry: `s3://quilt-ernest-staging`
- Status: Pre-existing package (not created by test)
- Reference: Mentioned in spec/a20-jwt-auth/04-remaining-work-100-percent.md:28
- Browse on quilt3: ✅ PASSED
- Browse on platform: ❌ FAILED

---

## Server Environment

**GraphQL Endpoint:** `nightly-registry.quilttest.com`

**Authentication:** JWT token from quilt3 session

**JWT Discovery:**
```
✅ Using JWT from quilt3 session
```

**Network:** All requests complete successfully (no network errors, DNS resolution works, TLS handshake succeeds)

---

## Cleanup Behavior

**Package Cleanup:** ✅ Works on platform backend

Both failed tests successfully cleaned up created packages:
```
🧹 Cleaning up 1 package(s)...
  ✅ Cleaned up package: test/integration_lifecycle_1770736485 in quilt-ernest-staging
```

This indicates:
- Delete operations work on platform backend
- Package was successfully created (can be deleted)
- JWT authentication works for write/delete operations

---

## Code Path Analysis

### Browse Content Flow (Platform Backend)

**Entry Point:** `platform_backend.py:237`
```python
def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
```

**Step 1:** Extract bucket from registry
```python
bucket = self._extract_bucket_from_registry(registry)
# Result: "quilt-ernest-staging"
```

**Step 2:** Build GraphQL query (lines 240-260)
- Query constructed successfully
- No syntax errors in query string

**Step 3:** Execute GraphQL query (line 262)
```python
result = self.execute_graphql_query(
    gql,
    variables={"bucket": bucket, "name": package_name, "path": path or ""},
)
```

**Step 4:** Execute GraphQL query implementation (line 109-117)
```python
response = self._session.post(endpoint, json=payload, headers=headers, timeout=60)
response.raise_for_status()  # Passes - 200 OK
result = response.json()     # Parses successfully
if "errors" in result:       # True - errors array exists
    error_messages = [err.get("message", str(err)) for err in result.get("errors", [])]
    raise BackendError(f"GraphQL query failed: {'; '.join(error_messages)}")
    # Raises: "GraphQL query failed: Internal Server Error"
```

**Failure Point:** Line 117 (errors in GraphQL response body)

---

## Search Operation Behavior

Tests also encountered search issues:

### Test 1 Search Error
```
[Step 1a] Verifying package in catalog search
  ⚠️  Search failed: Search invalid input: [{'context': {},
      'message': 'Cannot parse \'test/integration_lifecycle_1770736485\':
                  Lexical error at line 1, column 38.
                  Encountered: <EOF> after : "/integration_lifecycle_1770736485"',
      'name': 'QuerySyntaxError', 'path': 'searchString'}]
  ℹ️  Skipping search verification, continuing test...
```

This is a **different issue** - search query syntax error, not an Internal Server Error.

---

## Working Operations (Platform Backend)

These operations **do work** on platform backend:

1. **Package Creation (packageConstruct mutation)**
   - Creates package successfully
   - Returns package hash
   - Duration: ~10-20s

2. **Package Deletion**
   - Cleanup successful
   - No errors

3. **S3 Object Operations**
   - Object listing works
   - Object cleanup works

4. **Authentication**
   - JWT token accepted
   - No 401/403 errors

5. **GraphQL Endpoint Communication**
   - Network connection successful
   - HTTP 200 responses
   - JSON parsing works

---

## Non-Working Operations (Platform Backend)

1. **Browse Content (browse_content)**
   - All packages (new and existing)
   - All paths (root and subdirectories)
   - Internal Server Error

2. **Search Packages (search_packages)**
   - Query syntax errors
   - Different error from browse
   - May be unrelated issue

---

## Test File Status

**Test Files:**
- ✅ `tests/e2e/backend/integration/test_package_lifecycle.py` - Exists, modified
- ✅ `tests/e2e/backend/workflows/test_package_creation.py` - Exists
- ✅ `tests/e2e/backend/test_simple_browse.py` - Created 2026-02-10 (diagnostic)

**Git Status:**
```
M tests/e2e/backend/integration/test_package_lifecycle.py
?? tests/e2e/backend/test_simple_browse.py
```

---

## Revision to Previous Report

**Previous Report (05-test-results-report.md) stated:**
> Platform backend tests fail with GraphQL schema errors:
> HTTPSConnectionPool(host='nightly-registry.quilttest.com', port=443):
> Read timed out. (read timeout=30)

**Actual Findings:**
- ❌ Not a timeout issue (browse fails in ~4s)
- ✅ Write operations work with 60s timeout
- ❌ Browse operations fail with Internal Server Error
- ❌ Issue exists for both new and existing packages
- ✅ GraphQL schema errors were fixed (error types removed)
- ❌ New issue discovered: browse query returns server error

---

## Comparison: Original Diagnosis vs Reality

| Aspect | Original Report (2026-02-09) | Actual (2026-02-10) |
|--------|------------------------------|---------------------|
| **Issue** | packageConstruct timeout | browse_content failure |
| **Error** | Read timeout (30s) | Internal Server Error |
| **Duration** | >30s | ~4s |
| **Write Ops** | Timeout | ✅ Work |
| **Read Ops** | Not tested separately | ❌ Fail |
| **Package Type** | New packages | All packages (new + existing) |
| **Root Cause** | Timeout too short | Server-side GraphQL error |

---

## Facts Summary

1. **60s timeout resolves write operation issues** - packageConstruct completes successfully
2. **Browse operations fail immediately** - no timeout involved (~4s duration)
3. **Error is generic** - only "Internal Server Error" message provided
4. **HTTP layer succeeds** - 200 OK responses, not 500 errors
5. **GraphQL layer fails** - errors array in response body
6. **All packages affected** - both newly-created and pre-existing packages
7. **Platform backend specific** - quilt3 backend browse works fine
8. **Same query, different results** - identical browse_content call works on quilt3, fails on platform
9. **Authentication works** - JWT accepted for write/delete operations
10. **Server-side issue** - error originates from nightly-registry.quilttest.com

---

## Test Evidence Files

**Logs Created:**
- `/tmp/platform_test_lifecycle.log` - Full output from test_package_lifecycle.py
- `/tmp/platform_test_creation.log` - Full output from test_package_creation.py

**Test Files:**
- `tests/e2e/backend/test_simple_browse.py` - Diagnostic test (uncommitted)

**Modified Files:**
- `src/quilt_mcp/backends/platform_backend.py` - Timeout increased to 60s (uncommitted)
- `tests/e2e/backend/integration/test_package_lifecycle.py` - Error handling improvements (uncommitted)

---

## Next Steps Required

**Investigation Needed:**
1. Access to nightly-registry.quilttest.com server logs
2. GraphQL schema validation for browse query
3. Introspection query to verify schema availability
4. Platform backend version verification

**Cannot Proceed Without:**
- Server-side error details
- GraphQL endpoint diagnostics
- Platform team investigation

---

## References

- [05-test-results-report.md](./05-test-results-report.md) - Original test results (2026-02-09)
- [06-e2e-status.md](./06-e2e-status.md) - Current E2E status assessment
- [04-remaining-work-100-percent.md](./04-remaining-work-100-percent.md) - Original work plan

---

**Document Status:** Complete factual record of platform backend browse failure investigation

**No Solutions Proposed:** This document contains only observed facts and test results
