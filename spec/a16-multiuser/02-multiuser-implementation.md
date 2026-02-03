# Spec 18: Multiuser Implementation Refinement

**Status**: Planning
**Priority**: High
**Type**: Refactoring + Feature Enhancement
**Impact**: Architecture simplification, production readiness
**Depends On**: [Spec 17: Multiuser Terminology](./01-multiuser-terminology.md)

---

## Executive Summary

After renaming "multitenant" to "multiuser" terminology (Spec 17), this spec completes the architectural alignment:

1. **Remove**: ALL tenant tracking (each deployment = one tenant, implicit)
2. **Simplify**: Focus on per-USER identity only
3. **Add**: Missing multiuser production features (JWT auth, cloud storage)
4. **Fix**: Tests to validate multiuser (different users), not multitenant (different tenants)

**Key Insight**: Each Quilt stack deployment serves ONE organization/tenant. We don't need to track which tenant - it's implicit. We only need to track which USER within that tenant.

---

## Problem Statement

### Core Architecture Principle

**Every Quilt MCP server deployment is a standalone tenant:**
- One deployment = One organization = One Quilt catalog
- Multiple users within that single tenant
- No need to track "which tenant" - it's implicit in the deployment
- Only need to track "which user" for authentication and audit

### What We Have (Current State)

❌ **Multitenant-style architecture:**
```python
# Everywhere in the code
tenant_id: str                          # Unnecessary!
extract_tenant_id(auth_state)           # Shouldn't exist!
RequestContext(tenant_id=..., user_id=...) # Tenant tracking unneeded!
WorkflowStorage.save(tenant_id, workflow_id, ...) # Extra parameter!
```

❌ **Tests validate multitenant scenarios:**
```python
# tests/integration/test_multiuser.py
def test_cross_tenant_isolation():
    """Users in different tenants see different data."""
    # THIS IS WRONG! We have ONE tenant per deployment!
```

### What We Should Have (Target State)

✅ **Single-tenant, multiuser architecture:**
```python
# Simplified - no tenant tracking
user_id: str                            # Only identity needed!
extract_user_id(auth_state)             # From JWT 'sub' claim
RequestContext(user_id=..., request_id=...) # No tenant!
WorkflowStorage.save(workflow_id, ...)  # No tenant parameter!
```

✅ **Tests validate multiuser scenarios:**
```python
# tests/integration/test_multiuser.py
def test_multiple_users_same_catalog():
    """Multiple users can access same catalog with different credentials."""
    # THIS IS RIGHT! Same tenant, different users!
```

### Why This Matters

**Current complexity is unnecessary:**
- Tracking `tenant_id` adds parameters to every function
- Validating tenant isolation adds unnecessary checks
- Tests validate scenarios that will never happen (cross-tenant access)
- Storage backends partition by tenant unnecessarily

**Simplified architecture:**
- Remove ~30% of parameters across codebase
- Remove tenant validation logic
- Focus tests on actual use case (multiple users)
- Simpler storage (no tenant partitioning)

---

## Scope

### 1. Remove Tenant Tracking

**Remove from entire codebase:**

| What to Remove | Where | Why Unnecessary |
|----------------|-------|-----------------|
| `tenant_id` parameters | All function signatures | Each deployment = one tenant |
| `extract_tenant_id()` | `context/tenant_extraction.py` | User ID is sufficient |
| `TenantValidationError` | `context/exceptions.py` | No tenant to validate |
| Tenant claim extraction | JWT parsing | Only need user claims |
| Tenant directory isolation | Workflow storage | Single tenant = no isolation needed |
| Cross-tenant tests | Integration tests | Impossible scenario |

**Example - Before:**
```python
class RequestContextFactory:
    def create_context(
        self,
        tenant_id: Optional[str] = None,  # ❌ Remove
        request_id: Optional[str] = None,
    ) -> RequestContext:
        extracted_tenant = extract_tenant_id(auth_state)  # ❌ Remove
        resolved_tenant = self._resolve_tenant(tenant_id, extracted_tenant)  # ❌ Remove

        return RequestContext(
            request_id=resolved_request_id,
            tenant_id=resolved_tenant,  # ❌ Remove
            user_id=user_id,
            ...
        )
```

**Example - After:**
```python
class RequestContextFactory:
    def create_context(
        self,
        request_id: Optional[str] = None,
    ) -> RequestContext:
        user_id = extract_user_id(auth_state)  # ✅ Only user identity

        return RequestContext(
            request_id=resolved_request_id,
            user_id=user_id,  # ✅ Simplified
            ...
        )
```

### 2. Simplify to User-Only Identity

**What remains:**
- `user_id` - Primary identity (from JWT `sub` claim)
- `email` - Optional (from JWT `email` claim)
- `role` - Optional (from JWT `role` claim)
- `access_token` - JWT for downstream API calls

**No organization/tenant tracking needed** - it's implicit in:
- Environment variables: `QUILT_CATALOG_URL`, `QUILT_REGISTRY_URL`
- AWS credentials: Single set of credentials per deployment
- Deployment isolation: Each stack serves one tenant

### 3. Fix Terminology

**Remove "tenant" from code and docs:**

| Current Term | Action | Rationale |
|--------------|--------|-----------|
| `tenant_id` | **DELETE** | Not needed |
| `extract_tenant_id()` | **DELETE** | Not needed |
| `TenantValidationError` | **DELETE** | Not needed |
| "tenant" in docs | **REMOVE** | Confusing |
| "tenant" in comments | **REMOVE** | Wrong model |

**The ONLY place to keep "tenant":**
- Historical notes explaining why we removed it
- Comments like "Note: Each deployment is single-tenant, no tracking needed"

### 4. Simplify Storage

**Workflow storage - Before:**
```python
class FileBasedWorkflowStorage:
    def _tenant_dir(self, tenant_id: str) -> Path:
        return self._base_dir / tenant_id  # ❌ Unnecessary subdirectory

    def save(self, tenant_id: str, workflow_id: str, workflow: Dict):
        path = self._tenant_dir(tenant_id) / f"{workflow_id}.json"  # ❌
```

**Workflow storage - After:**
```python
class FileBasedWorkflowStorage:
    def save(self, workflow_id: str, workflow: Dict):
        path = self._base_dir / f"{workflow_id}.json"  # ✅ Flat structure
```

**DynamoDB storage - Before:**
```python
# Partition key includes tenant
PK: f"ORG#{tenant_id}"  # ❌ Unnecessary
SK: f"WORKFLOW#{workflow_id}"
```

**DynamoDB storage - After:**
```python
# Simple partition by workflow
PK: f"WORKFLOW#{workflow_id}"  # ✅ One tenant = simple keys
# Optional: Add user_id as attribute for audit
```

### 5. Fix Tests

**Remove cross-tenant tests:**
```python
# ❌ DELETE - tests impossible scenario
def test_cross_tenant_isolation():
    """Users in different tenants see different data."""

# ❌ DELETE - tests impossible scenario
def test_tenant_validation_required():
    """Multiuser mode requires tenant_id."""

# ❌ DELETE - tests impossible scenario
def test_workflow_storage_tenant_isolation():
    """Workflows isolated by tenant."""
```

**Add multiuser tests:**
```python
# ✅ ADD - tests actual use case
def test_multiple_users_same_catalog():
    """Multiple users can list same catalog buckets."""
    user_a_jwt = make_jwt(user_id="alice")
    user_b_jwt = make_jwt(user_id="bob")

    buckets_a = client.list_buckets(auth=user_a_jwt)
    buckets_b = client.list_buckets(auth=user_b_jwt)

    # Same catalog, both succeed
    assert buckets_a == buckets_b

# ✅ ADD - tests audit trail
def test_workflows_track_user():
    """Workflows record which user created them."""
    workflow = create_workflow(user_id="alice", ...)
    assert workflow.created_by == "alice"

# ✅ ADD - tests permissions
def test_user_permissions_respected():
    """Users with different roles have different access."""
    admin_jwt = make_jwt(user_id="alice", role="admin")
    viewer_jwt = make_jwt(user_id="bob", role="viewer")

    # Admin can create package
    assert client.create_package(auth=admin_jwt).success

    # Viewer cannot create package
    with pytest.raises(PermissionDenied):
        client.create_package(auth=viewer_jwt)
```

---

## Implementation Plan

### Phase 1: Remove Tenant Tracking from Core

**Goal**: Eliminate tenant_id from RequestContext and factory

#### Tasks

1. **Simplify RequestContext**
   - File: `src/quilt_mcp/context/request_context.py`
   - Remove: `tenant_id` field
   - Keep: `user_id`, `request_id`, services

   ```python
   # Before
   @dataclass(frozen=True)
   class RequestContext:
       request_id: str
       tenant_id: str      # ❌ Remove
       user_id: Optional[str]
       auth_service: AuthService
       permission_service: PermissionService
       workflow_service: WorkflowService

   # After
   @dataclass(frozen=True)
   class RequestContext:
       request_id: str
       user_id: str        # ✅ Always required in multiuser
       auth_service: AuthService
       permission_service: PermissionService
       workflow_service: WorkflowService
   ```

2. **Simplify RequestContextFactory**
   - File: `src/quilt_mcp/context/factory.py`
   - Remove: `tenant_id` parameter
   - Remove: `extract_tenant_id()` call
   - Remove: `_resolve_tenant()` method
   - Add: `extract_user_id()` function

   ```python
   # New simplified function
   def extract_user_id(auth_state: Optional[RuntimeAuthState]) -> Optional[str]:
       """Extract user ID from JWT 'sub' claim."""
       if not auth_state or not auth_state.claims:
           return None
       return auth_state.claims.get("sub")
   ```

3. **Delete tenant extraction module**
   - File: `src/quilt_mcp/context/tenant_extraction.py` - **DELETE**
   - Move `extract_user_id()` to `src/quilt_mcp/context/user_extraction.py` (new)

4. **Update exception hierarchy**
   - File: `src/quilt_mcp/context/exceptions.py`
   - Delete: `TenantValidationError` class
   - Keep: `ContextError`, `AuthenticationError`

5. **Update ModeConfig**
   - File: `src/quilt_mcp/config.py`
   - Remove: `tenant_mode` property
   - Keep: `is_multiuser`, `is_local_dev`, `requires_jwt`

#### Files Modified/Deleted

**Modified** (5 files):
- `src/quilt_mcp/context/request_context.py` - Remove tenant_id field
- `src/quilt_mcp/context/factory.py` - Simplify context creation
- `src/quilt_mcp/context/exceptions.py` - Delete TenantValidationError
- `src/quilt_mcp/config.py` - Remove tenant_mode property
- `src/quilt_mcp/runtime_context.py` - Update RuntimeContextState

**Added** (1 file):
- `src/quilt_mcp/context/user_extraction.py` - Extract user identity

**Deleted** (1 file):
- `src/quilt_mcp/context/tenant_extraction.py` - No longer needed

#### Testing

- [ ] All existing tests updated to remove tenant_id
- [ ] Context creation tests pass without tenant
- [ ] User extraction tests (from JWT)
- [ ] No regression in functionality

#### Success Criteria

- [ ] No `tenant_id` in RequestContext
- [ ] No `extract_tenant_id()` calls
- [ ] All core tests pass
- [ ] ~200 fewer lines of code

---

### Phase 2: Remove Tenant from Storage Layer (Local Dev Only)

**Goal**: Remove tenant tracking from workflow storage (local dev mode only)

**IMPORTANT**: Workflows only exist in local dev mode. This phase simplifies local dev storage, NOT for multiuser mode.

#### Tasks

1. **Simplify WorkflowService (local dev only)**
   - File: `src/quilt_mcp/services/workflow_service.py`
   - Remove: `tenant_id` from constructor
   - Remove: `self._tenant_id` attribute
   - Remove: `tenant_id` parameter from all methods
   - Keep: File-based storage for local dev only

   ```python
   # Before
   class WorkflowService:
       def __init__(self, tenant_id: str, storage: WorkflowStorage):
           self._tenant_id = tenant_id
           self._storage = storage

       def create_workflow(self, workflow_id: str, ...) -> Dict:
           self._storage.save(self._tenant_id, workflow_id, workflow)

   # After
   class WorkflowService:
       def __init__(self, storage: WorkflowStorage):
           self._storage = storage

       def create_workflow(self, workflow_id: str, ...) -> Dict:
           # No tenant tracking - local dev is single user/single tenant
           self._storage.save(workflow_id, workflow)
   ```

2. **Update WorkflowStorage interface**
   - File: `src/quilt_mcp/storage/workflow_storage.py`
   - Remove: `tenant_id` parameter from all methods

   ```python
   # Before
   class WorkflowStorage(ABC):
       @abstractmethod
       def save(self, tenant_id: str, workflow_id: str, workflow: Dict):
           pass

   # After
   class WorkflowStorage(ABC):
       @abstractmethod
       def save(self, workflow_id: str, workflow: Dict):
           pass
   ```

3. **Simplify FileBasedWorkflowStorage**
   - File: `src/quilt_mcp/storage/file_storage.py`
   - Remove: `_tenant_dir()` method
   - Remove: `tenant_id` partitioning
   - Flat structure: `~/.quilt/workflows/{workflow_id}.json`

   ```python
   # Before
   def _workflow_path(self, tenant_id: str, workflow_id: str) -> Path:
       tenant_dir = self._base_dir / quote(tenant_id, safe="")
       return tenant_dir / f"{workflow_id}.json"

   # After
   def _workflow_path(self, workflow_id: str) -> Path:
       # Flat structure for local dev
       return self._base_dir / f"{workflow_id}.json"
   ```

4. **Remove cloud storage implementations**
   - Delete: Any DynamoDB/S3 workflow storage backends
   - Reason: Workflows are local dev only, no cloud storage needed

#### Files Modified

- `src/quilt_mcp/services/workflow_service.py` - Remove tenant tracking
- `src/quilt_mcp/storage/workflow_storage.py` - Update interface
- `src/quilt_mcp/storage/file_storage.py` - Flat structure

#### Files Deleted

- Any cloud storage backend implementations (DynamoDB, S3, etc.)
- These are unnecessary - workflows are local dev only

#### Testing

- [ ] Workflow storage tests pass without tenant (local dev mode)
- [ ] File paths correct (flat structure in `~/.quilt/`)
- [ ] No cross-tenant isolation tests (delete them)
- [ ] No multiuser workflow tests (workflows disabled in multiuser)

#### Success Criteria

- [ ] No `tenant_id` in storage layer
- [ ] Simplified local dev storage structure
- [ ] No cloud storage backends (not needed)
- [ ] ~100 fewer lines of code

---

### Phase 3: Enforce Catalog JWT Only (Security)

**Goal**: Ensure ONLY Quilt catalog JWTs are accepted - anything else is a security hole

**CRITICAL**: The ONLY valid JWT format is from Quilt catalog: `tests/fixtures/data/sample-catalog-jwt.json`

#### Real Catalog JWT Structure

```json
{
  "id": "81a35282-0149-4eb3-bb8e-627379db6a1c",
  "uuid": "3caa49a9-3752-486e-b979-51a369d6df69",
  "exp": 1776817104
}
```

Claims:
- `id` - User ID (primary)
- `uuid` - Alternative user identifier
- `exp` - Expiration timestamp
- **NO** `sub`, `email`, `role`, `tenant_id`, `org_id`, or any other made-up claims

#### Current Correct Implementation

```python
# src/quilt_mcp/services/jwt_auth_service.py (line 87)
"user_id": claims.get("id") or claims.get("uuid") or claims.get("sub"),
```

This correctly prioritizes catalog JWT claims (`id`, `uuid`) with fallback to standard `sub`.

#### Tasks

1. **Audit all JWT test generation**
   - Find any code that generates fake/test JWTs
   - Ensure tests ONLY use the real catalog JWT from `tests/fixtures/data/sample-catalog-jwt.json`
   - Remove any test helpers that create arbitrary JWTs

2. **Remove tenant claim extraction**
   - File: `src/quilt_mcp/context/tenant_extraction.py` (deleted in Phase 1)
   - Verify JWT decoder never tries to extract `tenant_id`, `org_id`, `organization_id`
   - Only valid claims: `id`, `uuid`, `exp` (from catalog JWT)

3. **Security audit**
   - Search for any JWT generation outside of Quilt catalog
   - Ensure no test creates JWTs with arbitrary claims
   - Validate that JWT middleware rejects non-catalog JWTs

#### Files to Audit

- `tests/jwt_helpers.py` - Should NOT generate arbitrary JWTs
- All test files that use JWT - should use real catalog JWT
- JWT decoder - should only accept catalog JWT structure

#### Testing

- [ ] All tests use real catalog JWT from fixtures
- [ ] No test generates fake JWTs with arbitrary claims
- [ ] JWT decoder rejects non-catalog JWT structures
- [ ] Security: Only catalog-issued JWTs accepted

#### Success Criteria

- [ ] No code generates test JWTs (use real catalog JWT only)
- [ ] No JWT code accepts `tenant_id`, `org_id`, or made-up claims
- [ ] All tests pass using real catalog JWT
- [ ] Security validated: catalog JWT only

---

### Phase 4: Fix Tests for Multiuser (Not Multitenant)

**Goal**: Replace multitenant tests with proper multiuser tests

#### Tests to Delete

**Cross-tenant isolation** (impossible scenario):
```python
# tests/integration/test_multiuser.py
def test_cross_tenant_isolation()  # ❌ DELETE
def test_tenant_validation_required()  # ❌ DELETE
def test_invalid_tenant_rejection()  # ❌ DELETE

# tests/security/test_multiuser_security.py
def test_workflow_cross_tenant_access_denied()  # ❌ DELETE

# tests/unit/context/test_tenant_extraction.py  # ❌ DELETE ENTIRE FILE
```

#### Tests to Add

**Multiple users, same catalog**:
```python
# tests/integration/test_multiuser_access.py (new)

async def test_multiple_users_list_same_buckets():
    """Multiple users can list same catalog buckets."""
    user_a = make_jwt(user_id="alice")
    user_b = make_jwt(user_id="bob")

    buckets_a = await client.call_tool("bucket_list", auth=user_a)
    buckets_b = await client.call_tool("bucket_list", auth=user_b)

    # Same deployment = same catalog = same buckets
    assert buckets_a == buckets_b
    assert len(buckets_a) > 0

async def test_stateless_operations_only():
    """Multiuser mode supports only stateless operations."""
    alice_jwt = make_catalog_jwt(user_id="alice")

    # Stateless operations work
    buckets = await client.call_tool("bucket_list", auth=alice_jwt)
    assert len(buckets) > 0

    # Stateful operations disabled
    with pytest.raises(OperationNotSupportedError):
        await client.call_tool("workflow_create", auth=alice_jwt)

async def test_user_permissions_enforced():
    """Users with different roles have different permissions."""
    admin_jwt = make_jwt(user_id="admin", role="admin")
    viewer_jwt = make_jwt(user_id="viewer", role="viewer")

    # Admin can create package
    result = await client.create_package(auth=admin_jwt, ...)
    assert result.success

    # Viewer cannot create package
    with pytest.raises(PermissionDenied):
        await client.create_package(auth=viewer_jwt, ...)
```

**User identity (no audit storage in multiuser)**:
```python
# tests/integration/test_multiuser_identity.py (new)

async def test_user_identity_extracted_from_jwt():
    """User identity extracted from catalog JWT."""
    jwt = make_catalog_jwt(user_id="alice")  # Real catalog JWT format

    # Make tool call
    result = await client.call_tool("bucket_list", auth=jwt)

    # User identity tracked in context (not persisted)
    assert result.context["user_id"] == "alice"
    assert result.success

async def test_concurrent_users_stateless():
    """Concurrent requests from different users are stateless."""
    alice_jwt = make_catalog_jwt(user_id="alice")
    bob_jwt = make_catalog_jwt(user_id="bob")

    # Concurrent requests - completely stateless
    results = await asyncio.gather(
        client.call_tool("bucket_list", auth=alice_jwt),
        client.call_tool("bucket_list", auth=bob_jwt),
    )

    # Both succeed independently, no shared state
    assert all(r.success for r in results)
```

**Load testing** (realistic workload):
```python
# tests/load/test_multiuser_load.py (update)

async def test_concurrent_users_sustained_load():
    """100 concurrent users making sustained requests."""
    users = [make_jwt(user_id=f"user-{i}") for i in range(100)]

    async def user_session(jwt):
        """Simulate realistic user session."""
        await client.call_tool("bucket_list", auth=jwt)
        await asyncio.sleep(0.1)  # Think time
        await client.call_tool("bucket_objects_list", bucket="test", auth=jwt)
        await asyncio.sleep(0.1)
        await client.call_tool("package_list", registry="s3://test", auth=jwt)

    # All users concurrently
    await asyncio.gather(*[user_session(jwt) for jwt in users])
```

#### Test Files Modified/Deleted

**Deleted** (entire files):
- `tests/unit/context/test_tenant_extraction.py` - Not needed
- Cross-tenant test functions (keep files, delete functions)

**Modified** (existing files):
- `tests/integration/test_multiuser.py` - Remove cross-tenant tests
- `tests/security/test_multiuser_security.py` - Focus on user permissions
- `tests/load/test_multiuser_load.py` - Realistic workload

**Added** (new files):
- `tests/integration/test_multiuser_access.py` - Same-catalog access
- `tests/integration/test_multiuser_audit.py` - User identity tracking
- `tests/unit/context/test_user_extraction.py` - User ID extraction

#### Testing Infrastructure

**Update fixtures** (`tests/conftest.py`):
```python
@pytest.fixture
def make_catalog_jwt():
    """Factory for creating test JWTs matching catalog format.

    IMPORTANT: Only uses real catalog JWT structure from
    tests/fixtures/data/sample-catalog-jwt.json

    Catalog JWT claims:
    - id: User ID (primary)
    - uuid: Alternative user identifier
    - exp: Expiration timestamp

    NO other claims (sub, email, role, tenant_id, etc.)
    """
    def _make(user_id: str):
        return generate_catalog_jwt(
            id=user_id,
            uuid=str(uuid.uuid4()),
            exp=int(time.time()) + 3600
        )
    return _make

@pytest.fixture
async def multiuser_client():
    """HTTP client for multiuser MCP server (stateless, catalog JWT auth)."""
    async with MultiuserMCPClient(
        base_url="http://localhost:8080",
        mode="multiuser"  # Stateless mode
    ) as client:
        yield client
```

#### Success Criteria

- [ ] No cross-tenant tests remain
- [ ] All tests validate multiuser scenarios (different users, same catalog)
- [ ] Load tests use realistic workloads (tool calls, not just context creation)
- [ ] Test coverage >90% for multiuser code
- [ ] All tests pass: `make test-all`

---

### Phase 5: Disable Stateful Features in Multiuser Mode

**Goal**: Make multiuser mode completely stateless - NO workflows, NO metadata templates, NO persistent storage

**CRITICAL PRINCIPLE**: Multiuser mode must be horizontally scalable with zero server-side state.

#### Multiuser Mode = Stateless

**What multiuser mode DOES:**

- ✅ Read Quilt catalog/buckets/packages (via catalog API)
- ✅ Use catalog JWT authentication
- ✅ Stateless operations only
- ✅ Horizontally scalable (any number of containers)

**What multiuser mode DOES NOT DO:**

- ❌ NO workflows - stateful, requires storage
- ❌ NO metadata templates - stateful, requires storage
- ❌ NO persistent storage (file-based OR cloud)
- ❌ NO server-side state of any kind

#### Local Dev Mode = Stateful (Unchanged)

**Local dev mode keeps all stateful features:**

- ✅ Workflows (file-based: `~/.quilt/workflows/`)
- ✅ Metadata templates (file-based: `~/.quilt/templates/`)
- ✅ IAM credentials (no JWT)
- ✅ Single user, not horizontally scaled

#### Implementation Tasks

1. **Disable workflows in multiuser mode**
   - File: `src/quilt_mcp/tools/workflow_tools.py`
   - Add mode check that raises clear error:

   ```python
   def workflow_tool_handler(ctx: RequestContext, ...):
       if ctx.config.is_multiuser:
           raise OperationNotSupportedError(
               "Workflows are not available in multiuser mode. "
               "Use local dev mode for stateful features."
           )
       # Existing workflow logic...
   ```

2. **Disable metadata templates in multiuser mode**
   - File: `src/quilt_mcp/tools/template_tools.py`
   - Add same mode check:

   ```python
   def template_tool_handler(ctx: RequestContext, ...):
       if ctx.config.is_multiuser:
           raise OperationNotSupportedError(
               "Metadata templates are not available in multiuser mode. "
               "Use local dev mode for stateful features."
           )
       # Existing template logic...
   ```

3. **Remove workflow service from multiuser context**
   - File: `src/quilt_mcp/context/factory.py`
   - Only create WorkflowService in local dev mode:

   ```python
   def create_context(self, ...) -> RequestContext:
       # In multiuser mode, workflow_service is None
       workflow_service = None
       if self.config.is_local_dev:
           workflow_service = WorkflowService(storage=FileBasedWorkflowStorage())

       return RequestContext(
           request_id=request_id,
           user_id=user_id,
           workflow_service=workflow_service,  # None in multiuser!
           ...
       )
   ```

4. **Update tool registry**
   - File: `src/quilt_mcp/main.py`
   - Don't register workflow/template tools in multiuser mode:

   ```python
   def register_tools(server: Server, config: Config):
       # Always register stateless tools
       register_bucket_tools(server)
       register_package_tools(server)
       register_content_tools(server)

       # Only register stateful tools in local dev mode
       if config.is_local_dev:
           register_workflow_tools(server)
           register_template_tools(server)
   ```

5. **Add clear error messages**
   - File: `src/quilt_mcp/exceptions.py`
   - New exception for unsupported operations:

   ```python
   class OperationNotSupportedError(QuiltMCPError):
       """Operation not supported in current mode."""
       def __init__(self, message: str, mode: str = "multiuser"):
           super().__init__(
               f"{message} (Current mode: {mode})",
               error_code="OPERATION_NOT_SUPPORTED"
           )
   ```

#### Files Modified

- `src/quilt_mcp/tools/workflow_tools.py` - Add mode check
- `src/quilt_mcp/tools/template_tools.py` - Add mode check
- `src/quilt_mcp/context/factory.py` - Conditional service creation
- `src/quilt_mcp/main.py` - Conditional tool registration
- `src/quilt_mcp/exceptions.py` - New exception class

#### Testing (Phase 5)

**Multiuser mode tests:**
```python
# tests/integration/test_multiuser_stateless.py (new)

async def test_workflows_disabled_in_multiuser():
    """Workflows are disabled in multiuser mode."""
    jwt = make_catalog_jwt(user_id="alice")

    with pytest.raises(OperationNotSupportedError, match="Workflows are not available"):
        await client.call_tool("workflow_create", auth=jwt)

async def test_templates_disabled_in_multiuser():
    """Metadata templates are disabled in multiuser mode."""
    jwt = make_catalog_jwt(user_id="alice")

    with pytest.raises(OperationNotSupportedError, match="templates are not available"):
        await client.call_tool("template_create", auth=jwt)

async def test_only_stateless_tools_registered():
    """Only stateless tools are available in multiuser mode."""
    tools = await client.list_tools()
    tool_names = [t["name"] for t in tools]

    # Stateless tools available
    assert "bucket_list" in tool_names
    assert "package_list" in tool_names
    assert "bucket_objects_list" in tool_names

    # Stateful tools NOT available
    assert "workflow_create" not in tool_names
    assert "template_create" not in tool_names
```

**Local dev mode tests:**

```python
# tests/integration/test_local_dev_stateful.py (update)

async def test_workflows_enabled_in_local_dev():
    """Workflows work in local dev mode."""
    # No JWT, uses IAM
    workflow = await client.call_tool("workflow_create", workflow_id="test")
    assert workflow["workflow_id"] == "test"

async def test_templates_enabled_in_local_dev():
    """Templates work in local dev mode."""
    template = await client.call_tool("template_create", template_id="test")
    assert template["template_id"] == "test"
```

#### Documentation Updates

**README.md** - Update architecture section:
```markdown
## Architecture

### Multiuser Mode (Production)
- **Stateless**: No server-side storage
- **JWT Auth**: Catalog-issued JWTs only
- **Read Operations**: Buckets, packages, objects
- **Scalable**: Horizontal scaling, any number of containers

### Local Dev Mode
- **Stateful**: File-based storage in `~/.quilt/`
- **IAM Auth**: AWS credentials
- **All Features**: Workflows, templates, full functionality
- **Single User**: Development and testing
```

#### Success Criteria

- [ ] Workflows completely disabled in multiuser mode
- [ ] Metadata templates completely disabled in multiuser mode
- [ ] No WorkflowService created in multiuser mode
- [ ] Workflow/template tools not registered in multiuser mode
- [ ] Clear error messages when attempting stateful operations
- [ ] All multiuser tests validate stateless-only behavior
- [ ] Local dev mode unchanged (all features work)
- [ ] Documentation clearly explains stateless vs stateful modes

---

## Removed Functionality Summary

### Code Removed

| What | Where | Lines Removed |
|------|-------|---------------|
| `tenant_id` field | `RequestContext` | ~5 |
| `tenant_id` parameters | All function signatures | ~200 |
| `extract_tenant_id()` | `context/tenant_extraction.py` | ~80 |
| `TenantValidationError` | `context/exceptions.py` | ~20 |
| `tenant_mode` property | `config.py` | ~10 |
| Tenant claim extraction | JWT parsing | ~30 |
| Tenant directory isolation | File storage (local dev) | ~40 |
| Cloud storage backends | DynamoDB/S3 implementations | ~300 |
| Cross-tenant tests | Test files | ~150 |
| **Total** | | **~835 lines** |

### Features Disabled in Multiuser Mode

| Feature | Status in Multiuser | Status in Local Dev | Reason |
|---------|---------------------|---------------------|--------|
| Workflows | Disabled | Enabled | Requires persistent storage |
| Metadata templates | Disabled | Enabled | Requires persistent storage |
| Persistent storage | None | File-based | Multiuser must be stateless |
| Tool registration | Stateless tools only | All tools | Horizontal scalability |

### Tests Removed

| Test Category | Count | Why |
|---------------|-------|-----|
| Cross-tenant isolation | 8 tests | Impossible scenario (one tenant per deployment) |
| Tenant validation | 5 tests | No tenant to validate |
| Tenant extraction | 10 tests | Not needed (only user extraction) |
| **Total** | **23 tests** | |

### Tests Added

| Test Category | Count | Why |
|---------------|-------|-----|
| Multiple users same catalog | 10 tests | Actual multiuser scenario |
| User identity tracking | 5 tests | Audit and permissions |
| Concurrent user isolation | 5 tests | State isolation between users |
| User permissions | 8 tests | Role-based access control |
| **Total** | **28 tests** | |

---

## Architecture: Proper Single-Tenant Multiuser

### Deployment Model

**Each deployment serves ONE tenant:**
```
┌─────────────────────────────────────┐
│  Quilt MCP Server (Single Tenant)   │
│  - QUILT_CATALOG_URL (implicit)     │
│  - QUILT_REGISTRY_URL (implicit)    │
│                                      │
│  ┌──────────┐  ┌──────────┐        │
│  │ User A   │  │ User B   │        │
│  │ (Alice)  │  │ (Bob)    │        │
│  │ JWT      │  │ JWT      │        │
│  └──────────┘  └──────────┘        │
│       │              │              │
│       └──────┬───────┘              │
│              │                      │
│     ┌────────▼────────┐             │
│     │ Same Catalog    │             │
│     │ Same Registry   │             │
│     └─────────────────┘             │
└─────────────────────────────────────┘
```

**Multiple tenants = Multiple deployments:**
```
Tenant A (Acme Corp)          Tenant B (Initech)
┌──────────────────┐          ┌──────────────────┐
│ MCP Server A     │          │ MCP Server B     │
│ - Alice (admin)  │          │ - Carol (admin)  │
│ - Bob (viewer)   │          │ - Dave (viewer)  │
└──────────────────┘          └──────────────────┘
        ↓                              ↓
   Catalog A                      Catalog B
   (acme bucket)                  (initech bucket)
```

### Request Context

**Simplified structure:**
```python
@dataclass(frozen=True)
class RequestContext:
    """Per-request context for multiuser access."""
    request_id: str          # Unique request identifier
    user_id: str             # From JWT 'sub' claim
    auth_service: AuthService
    permission_service: PermissionService
    workflow_service: WorkflowService

    # No tenant_id - it's implicit in deployment!
```

### Authorization Model

**User-based, not tenant-based:**
```python
class PermissionService:
    def check_permission(self, user_id: str, action: str, resource: str) -> bool:
        """Check if user can perform action on resource."""
        # Query catalog API for user permissions
        # No tenant parameter - catalog is implicit
```

---

## Success Criteria

### Code Quality

- [ ] No references to "tenant" in source code (except historical comments)
- [ ] No references to "tenant" in top-level docs (README, architecture docs)
- [ ] No `tenant_id` parameters in any function signature
- [ ] No `extract_tenant_id()` calls
- [ ] No `TenantValidationError` exceptions
- [ ] ~835 fewer lines of code (including deleted cloud storage)

### Testing

- [ ] No cross-tenant isolation tests (deleted)
- [ ] All multiuser tests focus on stateless operations
- [ ] User identity extracted from catalog JWT only
- [ ] Load tests use realistic stateless workloads
- [ ] Test coverage >90% for multiuser code
- [ ] All tests pass: `make test-all`

### Functionality - Multiuser Mode

- [ ] **STATELESS**: No persistent storage whatsoever
- [ ] **Catalog JWT only**: Real catalog JWT format (`id`, `uuid`, `exp` claims)
- [ ] **Workflows disabled**: Clear error when attempted
- [ ] **Templates disabled**: Clear error when attempted
- [ ] **Tool registry**: Only stateless tools registered
- [ ] **User identity**: Extracted from JWT, tracked in context (not persisted)
- [ ] **Horizontally scalable**: No shared state between containers

### Functionality - Local Dev Mode

- [ ] Workflows enabled (file-based storage)
- [ ] Metadata templates enabled (file-based storage)
- [ ] No tenant tracking (single user/single tenant)
- [ ] IAM credentials work
- [ ] All features functional

### Documentation

- [ ] Architecture docs explain single-tenant model
- [ ] Deployment docs updated (no tenant configuration)
- [ ] Test docs updated (multiuser scenarios)
- [ ] Migration guide for removing tenant tracking

---

## Migration Path

### For Local Development

**No changes needed:**
- Local dev mode unaffected
- File-based storage still works
- IAM credentials still work

### For Production Deployments

**Simplification (remove tenant config):**

**Before:**
```bash
QUILT_MULTIUSER_MODE=true
QUILT_CATALOG_URL=https://acme.quiltdata.com
QUILT_TENANT_ID=acme  # ❌ Remove (unnecessary!)
```

**After:**
```bash
QUILT_MULTIUSER_MODE=true
QUILT_CATALOG_URL=https://acme.quiltdata.com
# No tenant ID needed - implicit in catalog URL!
```

### For Test Suites

**Update all tests to remove tenant_id:**
```python
# Before
def test_something():
    context = factory.create_context(tenant_id="test-tenant", user_id="alice")

# After
def test_something():
    context = factory.create_context(user_id="alice")
```

---

## Timeline Estimate

| Phase | Effort | Impact |
|-------|--------|--------|
| Phase 1: Remove Tenant from Core | 2 days | High (simplifies ~40% of code) |
| Phase 2: Remove Tenant from Storage (local dev) | 1 day | Medium (simplifies local storage) |
| Phase 3: Enforce Catalog JWT Only | 2-3 days | High (security critical) |
| Phase 4: Fix Tests | 2 days | High (validation) |
| Phase 5: Disable Stateful Features in Multiuser | 1-2 days | Critical (production architecture) |
| **Total** | **8-10 days** | **Major simplification + stateless architecture** |

---

## Related Specifications

- [Spec 17: Multiuser Terminology](./01-multiuser-terminology.md) - Prerequisite terminology fix
- [Spec 02: GraphQL Backend](../a15-platform/02-graphql.md) - Platform integration
- [Spec 04: JWT Authentication](../a10-multiuser/04-finish-jwt.md) - JWT implementation details
- [Spec 01: Stateless Architecture](../a10-multiuser/01-stateless.md) - Deployment model

---

**Author**: Claude
**Date**: 2026-02-03
**Status**: Planning - Ready for Review
**Key Insight**: Each deployment = one tenant. Focus on users, not tenants.
