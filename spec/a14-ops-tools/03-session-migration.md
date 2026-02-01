# Session Migration: Replace QuiltService with Backend

## Overview

QuiltService's `get_session()` and `create_botocore_session()` are fake abstractions that return raw session objects. The backend already has proper abstractions that should be used instead.

**Impact:** This eliminates 19 calls (31% of fake abstraction usage) across 2 methods.

## Current State

### QuiltService Fake Abstractions

```python
# quilt_service.py:256
def get_session(self) -> Any:
    """Get authenticated requests session."""
    return quilt3.session.get_session()  # Just returns raw session

# quilt_service.py:282
def create_botocore_session(self) -> Any:
    """Create authenticated botocore session."""
    return quilt3.session.create_botocore_session()  # Just returns raw session
```

### Backend Proper Abstractions (Already Exist!)

```python
# quilt3_backend_session.py:239
def execute_graphql_query(
    self,
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    registry_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute GraphQL query against catalog API.

    Handles session internally, returns structured result.
    """

# quilt3_backend_session.py:305
def get_boto3_client(
    self,
    service_name: str,
    region: Optional[str] = None,
) -> Any:
    """Get authenticated boto3 client for AWS services.

    Creates client from botocore session internally.
    """
```

## Migration Plan

### Phase 1: Migrate Athena Service (4 calls → 1 method)

**Current:** athena_service calls `create_botocore_session()` 4 times to get credentials

**Replacement:** Use backend's `get_boto3_client('athena', region='us-east-1')` directly

**Files:**
- [athena_service.py:90](../../src/quilt_mcp/services/athena_service.py#L90)
- [athena_service.py:190](../../src/quilt_mcp/services/athena_service.py#L190)
- [athena_service.py:204](../../src/quilt_mcp/services/athena_service.py#L204)
- [athena_service.py:495](../../src/quilt_mcp/services/athena_service.py#L495)

**Change:**
```python
# BEFORE
botocore_session = quilt_service.create_botocore_session()
credentials = botocore_session.get_credentials()
# ... use credentials for connection string

# AFTER
# Option 1: Use backend directly for Athena operations
athena_client = backend.get_boto3_client('athena', region='us-east-1')

# Option 2: If credentials needed for connection string
# Extract credentials from backend-provided client
```

### Phase 2: Migrate GraphQL Callers (3 calls → backend method)

**Current:** Tools get raw session and manually construct/execute GraphQL queries

**Replacement:** Use backend's `execute_graphql_query()`

#### 2.1 Search Tool

- **File:** [search.py:378](../../src/quilt_mcp/tools/search.py#L378)
- **Current:** Gets session, constructs GraphQL query manually
- **Replacement:** Call `backend.execute_graphql_query(query, variables)`

#### 2.2 Stack Buckets Tool

- **File:** [stack_buckets.py:49](../../src/quilt_mcp/tools/stack_buckets.py#L49)
- **Current:** Gets session, executes GraphQL via `_get_stack_buckets_via_graphql()`
- **Replacement:** Call `backend.execute_graphql_query(query)`

### Phase 3: Backend Internal Usage (2 calls → already internal)

**Files:**
- [quilt3_backend_session.py:73](../../src/quilt_mcp/backends/quilt3_backend_session.py#L73)
- [quilt3_backend_session.py:268](../../src/quilt_mcp/backends/quilt3_backend_session.py#L268)

**Status:** These are internal to the backend's own implementation. Already using `self.quilt3.session.get_session()` directly, which is fine since it's encapsulated within the backend abstraction.

**Action:** No change needed - backend can use raw quilt3 internally.

### Phase 4: Auth Services (4 calls → TBD)

**Files:**
- [jwt_auth_service.py:109](../../src/quilt_mcp/services/jwt_auth_service.py#L109)
- [auth_service.py:49](../../src/quilt_mcp/services/auth_service.py#L49)
- [iam_auth_service.py:54,58,65](../../src/quilt_mcp/services/iam_auth_service.py#L54)

**Issue:** Auth services use sessions for their own authentication logic, not for backend operations.

**Options:**
1. Auth services can call `quilt3.session.get_session()` directly (they're session management, after all)
2. Move session management to backend and expose as proper auth methods
3. Keep QuiltService for auth services only (smallest scope)

**Recommendation:** Auth services should access `quilt3.session` directly. They ARE the session management layer.

### Phase 5: Search Backend (1 call → already using backend!)

**File:** [elasticsearch.py:228](../../src/quilt_mcp/search/backends/elasticsearch.py#L228)

**Current:** Search backend gets session via QuiltService

**Fix:** Search backend should use the QuiltOps backend's `execute_graphql_query()` method instead.

### Phase 6: Scripts (1 call → low priority)

**File:** [list_all_indices.py:42](../../scripts/list_all_indices.py#L42)

**Status:** Diagnostic script, can access raw quilt3 directly if needed.

**Action:** Low priority - scripts can use quilt3 directly or be updated later.

### Phase 7: Delete QuiltService Methods

After migration complete:

1. **Delete from quilt_service.py:**
   - `get_session()` method (line 256)
   - `create_botocore_session()` method (line 282)

2. **Update tests:**
   - Remove tests for these methods from test_quilt_service.py
   - Add tests for new backend usage patterns

3. **Verify:**
   - `grep -r "\.get_session()" src/` should show no QuiltService usage
   - `grep -r "\.create_botocore_session()" src/` should show no QuiltService usage

## Summary

| Component | Calls | Migration Strategy |
|-----------|-------|-------------------|
| Athena Service | 4 | Use `backend.get_boto3_client('athena')` |
| MCP Tools | 2 | Use `backend.execute_graphql_query()` |
| Search Backend | 1 | Use `backend.execute_graphql_query()` |
| Backend Internal | 2 | No change - internal use is fine |
| Auth Services | 4 | Use `quilt3.session` directly |
| Scripts | 1 | Low priority - can use quilt3 directly |
| **Total Production** | **7** | **Migrate to backend methods** |
| Tests | 4 | Update to test backend methods instead |

## Impact

**Before Migration:**
- 19 calls to session fake abstractions
- Scattered session management across services
- Each caller handles raw session objects

**After Migration:**
- 7 production calls migrated to proper backend methods
- 4 auth service calls use quilt3 directly (appropriate for auth layer)
- Backend handles session internally
- Callers use high-level operations (execute_graphql_query, get_boto3_client)

## Success Criteria

1. ✅ Athena service uses `backend.get_boto3_client()`
2. ✅ Tools use `backend.execute_graphql_query()`
3. ✅ Auth services use `quilt3.session` directly (documented exception)
4. ✅ QuiltService methods deleted
5. ✅ All tests pass
6. ✅ No remaining QuiltService session calls in production code
