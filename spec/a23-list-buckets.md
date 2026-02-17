# List Buckets Tool Spec

## Overview

MCP tool to list S3 buckets accessible to the authenticated user via the Quilt platform.

## Implementation Location

- **QuiltOps** class directly (no separate backend implementations)
- Consolidates logic previously split across Quilt3Backend and QuiltOpsBackend

## Upstream API

Uses GraphQL `bucketConfigs` query from `~/GitHub/enterprise/registry/quilt_server/graphql/buckets.py`:

- Query: `bucketConfigs` (line 126)
- Returns: Buckets filtered by `auth.get_buckets_listable_by(context.get_user())`
- Respects user permissions and role-based access

## Tool Interface

**Name**: `bucket_list`

**Input**: None (uses authenticated user context from JWT)

**Output**: List of bucket configurations with:

- `name` (string, required)
- `title` (string)
- `description` (string, optional)
- `iconUrl` (string, optional)
- `relevanceScore` (int)
- `browsable` (bool)
- `tags` (array, optional)

## Auth Requirements

- Requires valid JWT in request context
- Returns only buckets user has permission to list
- Empty list if no accessible buckets (not an error)

## Error Cases

- **401 Unauthorized**: Missing/invalid JWT
- **Network errors**: Standard retry/backoff
- **GraphQL errors**: Map to tool-level errors with message

## Related Components

- JWT discovery: `src/quilt_mcp/auth/jwt_discovery.py`
- Context management: `src/quilt_mcp/context/request_context.py`
- Tool registration: `src/quilt_mcp/tools/buckets.py`

## Test Requirements

### Unit Tests (`tests/unit/tools/test_buckets.py`)

**Implemented:**

- ✅ `test_bucket_list_success` - Mock GraphQL response with full bucket data
- ✅ `test_bucket_list_empty` - Empty bucket list response
- ✅ `test_bucket_list_graphql_error` - GraphQL query failure handling
- ✅ `test_bucket_list_missing_data` - Missing data field in response

**Coverage:** Complete - all error paths and success cases covered

### E2E Tests (Real Platform Integration)

**Required:**

- `tests/e2e/tools/test_bucket_list_e2e.py` - Real bucket list with authenticated user
  - Test with valid JWT authentication
  - Verify actual buckets returned from platform
  - Validate bucket structure and fields
  - Test with both quilt3 and platform backends
  - Verify empty list handling (if user has no buckets)

### Functional Tests (Mocked Multi-Module)

**Required:**

- `tests/func/test_bucket_list_func.py` - Mocked QuiltOps integration
  - Test QuiltOpsFactory integration
  - Verify GraphQL query construction
  - Test auth context propagation
  - Validate response mapping

### Integration Tests (E2E Workflow Context)

**Required:**

- Add bucket_list to existing workflow tests:
  - `tests/e2e/backend/workflows/test_data_discovery.py` - Use bucket_list to discover available buckets before search
  - `tests/e2e/backend/integration/test_search_to_access.py` - Validate bucket access against bucket_list results

### Security Tests

**Required:**

- `tests/security/test_bucket_list_auth.py`
  - Test missing JWT (401)
  - Test invalid JWT
  - Test bucket filtering based on user permissions
  - Test that inaccessible buckets are not returned

### Performance Tests

**Optional:**

- `tests/e2e/backend/performance/test_bucket_list_scale.py`
  - Test with users having many buckets (50+)
  - Test response time under load

## Test Execution

```bash
# Unit tests only (fast)
uv run pytest tests/unit/tools/test_buckets.py::test_bucket_list -v

# E2E tests (requires authentication)
uv run pytest tests/e2e/tools/test_bucket_list_e2e.py -v

# Functional tests (mocked)
uv run pytest tests/func/test_bucket_list_func.py -v

# Security tests
uv run pytest tests/security/test_bucket_list_auth.py -v

# All bucket_list tests
uv run pytest -k bucket_list -v
```
