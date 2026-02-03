# Test Comparison Analysis: test-mcp-docker vs test-mcp-stateless

**Date:** 2026-01-29
**Branch:** a11-jwt-client
**Commit:** a1e401e (refactor: Use jwt_helper as library in mcp-test.py with --jwt flag)

## Executive Summary

This document compares two MCP server testing modes:

- **test-mcp-docker**: Stdio transport with Docker container (default test mode)
- **test-mcp-stateless**: HTTP+JWT transport with stateless security constraints

### Key Findings

| Metric | test-mcp-docker | test-mcp-stateless | Difference |
|--------|-----------------|---------------------|------------|
| **Tools Tested** | 24/55 (idempotent only) | 55/55 (all tools) | +31 tools tested |
| **Tools Passed** | 24/24 (100%) | 51/55 (93%) | -4 failures |
| **Resources Tested** | 15/15 | 15/15 | Same |
| **Resources Passed** | 15/15 (100%) | 15/15 (100%) | Same |
| **Transport** | stdio | HTTP with JWT auth | Different |
| **Container Constraints** | Standard Docker | Read-only, no-new-privileges, 512MB RAM | More restrictive |
| **Overall Status** | ✅ PASSED | ❌ FAILED (4 tool failures) | - |

---

## Test Configuration Comparison

### test-mcp-docker (Stdio Mode)

**Purpose:** Fast integration testing with idempotent tools only

**Configuration:**

```yaml
Transport: stdio
Container: Standard Docker container
Security: Default Docker security
Test Scope: 24 idempotent tools + 15 resources
Selection Criteria: Skips non-idempotent tools (configure, create, remove, update)
```

**Make Target:**

```makefile
test-mcp-docker: docker-build
    @uv run python scripts/tests/test_mcp.py --docker --image quilt-mcp:test -v
```

**Container Launch:**

- Standard Docker security
- Stdio transport (no network)
- Tests filtered to idempotent-only

### test-mcp-stateless (HTTP+JWT Mode)

**Purpose:** Stateless deployment testing with full tool coverage and JWT authentication

**Configuration:**

```yaml
Transport: HTTP (port 8002)
Authentication: JWT with catalog session extraction
Container: Hardened, read-only filesystem
Security Constraints:
  - Read-only root filesystem
  - No new privileges
  - All capabilities dropped
  - 512MB memory limit
  - CPU quota: 1 core
  - Tmpfs only for /tmp and /run
Test Scope: ALL 55 tools + 15 resources
```

**Make Target:**

```makefile
test-mcp-stateless: docker-build
    @bash scripts/tests/start-stateless-docker.sh
    @uv run python scripts/mcp-test.py http://localhost:8002/mcp \
        --jwt --role-arn "${QUILT_TEST_JWT_TOKEN}" \
        --secret "test-secret-key..." \
        --tools-test --resources-test \
        --config scripts/tests/mcp-test.yaml
    @bash scripts/tests/stop-stateless-docker.sh
```

**Container Launch (via helper script):**

```bash
docker run -d --name mcp-stateless-test \
    --read-only \
    --security-opt=no-new-privileges:true \
    --cap-drop=ALL \
    --tmpfs=/tmp:size=100M,mode=1777 \
    --tmpfs=/run:size=10M,mode=755 \
    --memory=512m --memory-swap=512m \
    --cpu-quota=100000 --cpu-period=100000 \
    -e MCP_REQUIRE_JWT=true \
    -e MCP_JWT_SECRET="test-secret-key..." \
    -e QUILT_MCP_STATELESS_MODE=true \
    -e FASTMCP_TRANSPORT=http \
    -e FASTMCP_HOST=0.0.0.0 \
    -e FASTMCP_PORT=8000 \
    -p 8002:8000 \
    quilt-mcp:test
```

---

## Test Results Breakdown

### Tool Testing Results

#### test-mcp-docker Results

```
🔧 TOOLS (24/55 tested, 31 skipped)
   Selection: Idempotent only
   ✅ 24 passed (100%)

   Skipped categories:
   - configure: 6 tools
   - create: 15 tools
   - remove: 5 tools
   - update: 5 tools
```

**Tested Tools (24):**

- All idempotent tools including:
  - Bucket operations (list, info, fetch, text)
  - Package operations (browse, diff)
  - Athena queries (validate, execute, list tables)
  - Resources access
  - Workflow read operations

#### test-mcp-stateless Results

```
🔧 TOOLS (55/55 tested)
   ✅ 51 passed (93%)
   ❌ 4 failed (7%)

   All tool categories tested:
   - configure: 6 tools ✅
   - create: 15 tools ✅
   - remove: 5 tools ✅
   - update: 5 tools ✅
   - admin: 14 tools ✅
   - Other: 10 tools (6 passed, 4 failed)
```

**Failed Tools (4):**

1. **discover_permissions**
   - Error: `HTTPConnectionPool(host='localhost', port=8002): Read timed out. (read timeout=10)`
   - Type: Timeout (>10 seconds)
   - Likely Cause: Permission discovery iterates through many buckets/prefixes
   - Impact: HIGH - This is a long-running operation that needs timeout adjustment

2. **search_catalog.global.no_bucket** ⚠️ REGRESSION
   - Input: `{"query": "README.md", "limit": 10, "scope": "global", "bucket": ""}`
   - Error: `Expected at least 1 results, got 0`
   - Type: **REGRESSION** - Works in stdio mode, fails in HTTP+JWT mode
   - Docker stdio result: ✅ PASSED - Returns results including test entry
   - Stateless result: ❌ FAILED - Returns 0 results
   - Impact: **CRITICAL** - Search functionality broken in stateless mode

3. **search_catalog.file.no_bucket** ⚠️ REGRESSION
   - Input: `{"query": "README.md", "limit": 10, "scope": "file", "bucket": ""}`
   - Error: `Expected at least 1 results, got 0`
   - Type: **REGRESSION** - Works in stdio mode, fails in HTTP+JWT mode
   - Docker stdio result: ✅ PASSED
   - Stateless result: ❌ FAILED - Returns 0 results
   - Impact: **CRITICAL**

4. **search_catalog.package.no_bucket** ⚠️ REGRESSION
   - Input: `{"query": "raw/test", "limit": 10, "scope": "package", "bucket": ""}`
   - Error: `Expected at least 1 results, got 0`
   - Type: **REGRESSION** - Works in stdio mode, fails in HTTP+JWT mode
   - Docker stdio result: ✅ PASSED
   - Stateless result: ❌ FAILED - Returns 0 results
   - Impact: **CRITICAL**

### Resource Testing Results

**Both test modes:** ✅ 15/15 resources passed (100%)

Resources tested successfully in both modes:

- `auth://status`
- `auth://catalog/info`
- `auth://filesystem/status`
- `admin://users`
- `admin://roles`
- `admin://config/sso`
- `admin://config/tabulator`
- `athena://databases`
- `athena://workgroups`
- `athena://query/history`
- `metadata://templates`
- `metadata://examples`
- `metadata://troubleshooting`
- `workflow://workflows`
- `tabulator://buckets`

---

## Success Patterns

### What Works in Stateless Mode (51 tools)

**All admin tools work perfectly (14/14):**

- User management (create, delete, roles, permissions)
- SSO configuration
- Tabulator configuration

**All create/update/remove tools work (25/25):**

- Package creation and updates
- Bucket object uploads
- Workflow creation and modification
- Table management
- Catalog configuration

**Most read-only tools work:**

- Bucket browsing and object access
- Package browsing and diffing
- Athena queries
- Visualization generation
- Schema validation

**Key Success:**

- JWT authentication works correctly
- Catalog session extraction functions
- All mutating operations succeed
- All admin operations succeed
- All resources accessible

---

## Failure Analysis

### Root Causes

#### 1. discover_permissions Timeout

**Issue:** Long-running operation exceeds 10-second timeout

**Why it times out:**

```python
# discover_permissions iterates through:
# - All configured buckets
# - Multiple prefixes per bucket
# - Multiple operations per prefix (read, write, list)
# This can easily take 30-60 seconds
```

**Recommendations:**

- Increase timeout to 60 seconds for this tool
- Consider making this an async/background operation
- Cache permission results

#### 2. search_catalog Regression - CRITICAL BUG

**Issue:** All three search variants return 0 results in stateless mode but work correctly in stdio mode

**Evidence of Regression:**

Stdio mode (Docker):

```
✅ search_catalog.global.no_bucket: PASSED
✅ search_catalog.file.no_bucket: PASSED
✅ search_catalog.package.no_bucket: PASSED
Smart validation: "Global search across all buckets (_all index) should return results"
```

Stateless HTTP+JWT mode:

```
❌ search_catalog.global.no_bucket: FAILED - Expected at least 1 results, got 0
❌ search_catalog.file.no_bucket: FAILED - Expected at least 1 results, got 0
❌ search_catalog.package.no_bucket: FAILED - Expected at least 1 results, got 0
```

**Root Cause Analysis Needed:**

This is a transport/authentication-specific bug. Possible causes:

1. **JWT Catalog Session Issue:**
   - Search API may not be getting proper catalog session from JWT
   - JWT may not include search permissions/scopes
   - Catalog authentication extraction may be incomplete for search endpoints

2. **HTTP Transport Difference:**
   - Search may behave differently over HTTP vs stdio
   - Request serialization issue specific to HTTP transport
   - Timeout or connection issue to search backend

3. **Stateless Mode Configuration:**
   - Search may require persistent state/cache
   - Environment variables affecting search behavior
   - Search index access configuration missing in stateless mode

**Critical Actions Required:**

1. **Debug search_catalog in stateless mode:**
   - Add debug logging to see what catalog session is being used
   - Check if search API requests are reaching the catalog
   - Verify JWT token includes proper catalog credentials

2. **Compare request/response between modes:**
   - Log full requests in both stdio and HTTP modes
   - Check for differences in how catalog is accessed
   - Verify search API endpoint configuration

3. **Test search with explicit bucket:**
   - Try search with specific bucket (not global)
   - Determine if issue is global search specific or all search

4. **Check catalog session extraction:**
   - Verify JWT payload includes catalog session
   - Confirm session is properly extracted and used
   - Test if manual catalog configuration works

---

## Infrastructure Comparison

### Helper Scripts Created

Two new helper scripts make stateless testing reusable:

**scripts/tests/start-stateless-docker.sh:**

- Validates `QUILT_TEST_JWT_TOKEN` environment variable
- Configures container with security constraints
- Starts container with proper environment variables
- Validates container health
- Returns container info for testing

**scripts/tests/stop-stateless-docker.sh:**

- Stops running container
- Removes container
- Handles cleanup even if container doesn't exist

**Benefits:**

- Reusable by other make targets
- Consistent container configuration
- Easy to modify security constraints
- Proper cleanup handling

### Refactoring Improvements

**Before (inline Docker commands):**

```makefile
test-stateless-mcp:
    @docker run -d --name mcp-jwt-test \
        --read-only \
        ... (40+ lines of flags) ...
    @uv run python scripts/mcp-test.py ... && \
    docker stop mcp-jwt-test && docker rm mcp-jwt-test
```

**After (using helper scripts):**

```makefile
test-mcp-stateless: docker-build
    @bash scripts/tests/start-stateless-docker.sh
    @uv run python scripts/mcp-test.py ... && \
    bash scripts/tests/stop-stateless-docker.sh
```

**Improvements:**

- ✅ Cleaner, more maintainable make target
- ✅ Docker configuration centralized in helper script
- ✅ Can be reused by other targets
- ✅ Proper error handling and cleanup
- ✅ Environment variable validation
- ✅ Better logging and status messages

---

## Recommendations

### Immediate Actions

1. **Fix discover_permissions timeout:**

   ```python
   # In scripts/mcp-test.py
   TOOL_TIMEOUTS = {
       'discover_permissions': 60,  # Long-running operation
       'default': 10
   }
   ```

2. **Adjust search_catalog expectations:**

   ```yaml
   # In mcp-test.yaml
   search_catalog:
     validation:
       allow_empty_results: true  # Or skip in CI
   ```

3. **Document search requirements:**
   - Add note about search infrastructure dependencies
   - Document which environments support search
   - Provide setup instructions for search testing

### Long-term Improvements

1. **Add Environment Detection:**
   - Skip search tests if search infrastructure unavailable
   - Detect and adapt to catalog capabilities
   - Provide clear messaging about skipped tests

2. **Optimize Long-running Operations:**
   - Cache permission discovery results
   - Make discover_permissions async
   - Add progress indicators

3. **Enhance Test Configuration:**
   - Per-tool timeout configuration
   - Environment-specific test suites
   - Better validation rules for different environments

---

## Conclusion

### Summary

The refactored `test-mcp-stateless` target successfully demonstrates:

✅ **Full tool coverage:** Tests all 55 tools vs 24 in stdio mode
✅ **JWT authentication:** Works for most operations
✅ **Stateless constraints:** Functions with read-only filesystem and security restrictions
✅ **Admin operations:** All 14 admin tools pass
✅ **Mutating operations:** All create/update/remove operations work
✅ **Helper scripts:** Reusable infrastructure for other targets

❌ **Critical Issues Found:**

1. **search_catalog REGRESSION (3 tools):**
   - Works perfectly in stdio mode (docker)
   - Completely broken in HTTP+JWT stateless mode
   - Returns 0 results when expecting ≥1
   - **This is a transport/authentication-specific bug**

2. **discover_permissions timeout:**
   - Takes >10 seconds (needs timeout increase)

### Test Coverage Comparison

- **test-mcp-docker:** Fast, reliable CI testing with stdio transport
- **test-mcp-stateless:** Comprehensive testing that **exposed critical search regression**

### Overall Assessment

**CRITICAL BUG IDENTIFIED:** Search functionality is broken in stateless HTTP+JWT mode.

The comparison testing successfully identified a **regression** where `search_catalog` works correctly via stdio transport but fails completely via HTTP+JWT transport. This is not an "environment issue" - it's a real bug in how stateless mode handles catalog search operations.

**Status:** 🚫 **NOT PRODUCTION-READY** until search regression is fixed

The 93% pass rate (51/55) is misleading because:

- The 3 search failures are the **same underlying issue** (search broken in stateless mode)
- This is a **regression** - stdio mode proves search should work
- Search is a core catalog feature, not optional

**Next Steps:**

1. Debug why search works in stdio but not HTTP+JWT
2. Check catalog session extraction for search operations
3. Verify JWT includes proper search permissions
4. Fix the root cause before deploying stateless mode

---

## Reproducing the Bug

A minimal standalone script has been created to reproduce this regression:

```bash
# Build Docker image
make docker-build

# Set test role (required)
export QUILT_TEST_JWT_TOKEN="arn:aws:iam::712023778557:role/QuiltMCPTestRole"

# Run reproduction script
uv run python scripts/tests/reproduce_search_bug.py
```

The script:

1. Starts a stateless Docker container with HTTP+JWT transport
2. Generates JWT token with embedded catalog credentials
3. Initializes MCP session via HTTP
4. Calls `search_catalog` with the same test cases that pass in stdio mode
5. Shows that search returns 0 results (the bug)
6. Cleans up automatically

**Expected Output:** All 3 search tests should fail with 0 results, confirming the regression.

---

## Files Generated

- `spec/a11-client-testing/19-test-mcp-docker-output.log` - Full stdio test output
- `spec/a11-client-testing/19-test-mcp-stateless-output.log` - Full HTTP+JWT test output
- `scripts/tests/start-stateless-docker.sh` - Helper script to start container
- `scripts/tests/stop-stateless-docker.sh` - Helper script to stop container
- `scripts/tests/reproduce_search_bug.py` - **Minimal bug reproduction script**
- `spec/a11-client-testing/19-test-comparison-analysis.md` - This document
