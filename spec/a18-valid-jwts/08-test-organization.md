# Test Organization: Stateless vs E2E

**Date:** 2026-02-05
**Status:** IMPLEMENTED WITH CORRECTIONS
**Related:** `07-fix-mcp-test.md`

## ✅ IMPLEMENTATION STATUS

**Completed:**

1. ✅ Created `tests/conftest.py` with shared Docker fixtures
2. ✅ Updated `tests/stateless/conftest.py` to import from parent
3. ✅ Removed `backend_mode` from `tests/e2e/conftest.py`
4. ✅ JWT tests remain in `tests/stateless/` (see correction below)

## ⚠️ CRITICAL CORRECTION: JWT Tests Stay in Stateless

**Original spec proposed moving JWT tests to `tests/e2e/` - this was WRONG.**

**Why JWT tests belong in `tests/stateless/`, NOT `tests/e2e/`:**

1. **JWT authentication is platform/multiuser-only**
   - Quilt3 local mode doesn't use JWT at all
   - JWT is a stateless deployment constraint, not a universal feature

2. **The `stateless_container` fixture is platform-specific**

   ```python
   environment={
       "QUILT_MULTIUSER_MODE": "true",  # ← Platform/multiuser mode ONLY
       "MCP_JWT_SECRET": "test-secret",
       ...
   }
   ```

3. **JWT tests are NOT backend-agnostic**
   - They test stateless deployment constraints
   - They validate multiuser mode enforcement
   - Moving them to e2e/ would be architecturally incorrect

**Final decision:** JWT tests remain in `tests/stateless/test_jwt_authentication.py`

## ⚠️ OTHER CORRECTIONS APPLIED

**Original spec had these WRONG assumptions:**

1. ❌ E2E tests should parametrize over backends (quilt3/platform)
2. ❌ E2E tests should be "backend-agnostic" but know about backend modes
3. ❌ Make targets just need to build Docker images
4. ❌ JWT tests should move to e2e/ (WRONG - see above!)

**CORRECTED approach:**

1. ✅ E2E tests are **completely backend-agnostic** - no backend awareness AT ALL
2. ✅ E2E tests only use `container_url` fixture - they test MCP protocol behavior
3. ✅ Make targets **start containers** via pytest fixtures, not just build images
4. ✅ Tests validate HTTP/MCP protocol surface, not backend implementation
5. ✅ **JWT tests STAY in `tests/stateless/`** - they're platform-specific!

**Key insight:** E2E tests validate the MCP protocol contract. The container could be
running ANY backend implementation - tests shouldn't know or care. They make HTTP
requests to `container_url` and validate responses.

## Executive Summary

We have two test directories that are poorly organized:

- `tests/stateless/` - Has proper Docker infrastructure, tests stateless-specific constraints
- `tests/e2e/` - Has NO infrastructure, tests are broken and can't run

**Goal:** Reorganize tests so:

- `test-stateless` runs stateless-specific tests (Docker constraints, read-only filesystem)
- `test-e2e` runs backend-agnostic functional tests (works for both quilt3 and platform backends)

## Current State

### tests/stateless/ - WORKING

**Infrastructure:**

- `conftest.py` - Docker fixtures, container management
- `stateless_container` fixture - Starts containerized server with constraints
- `container_url` fixture - HTTP endpoint for testing

**Tests:**

- `test_basic_execution.py` - Container starts, constraints enforced
- `test_jwt_authentication.py` - JWT authentication enforcement (158 lines)
- `test_persistent_state.py` - No state persists across restarts

**Make target:**

```bash
make test-stateless  # Runs: pytest tests/stateless/
```

**What it tests:**

- Read-only filesystem enforcement
- Security constraints (no-new-privileges, cap-drop)
- Memory/CPU limits
- JWT-only authentication
- No persistent state

**Backend:** Platform/stateless only (containerized deployment)

### tests/e2e/ - BROKEN

**Infrastructure:** NONE

**Tests:**

- `test_jwt_enforcement.py` - Comprehensive JWT tests (301 lines, BROKEN)
  - Tries to define own fixtures (`mcp_endpoint`, `valid_jwt`)
  - Fixtures not found at runtime
  - Connection errors: `[Errno 61] Connection refused`

**Make target:**

```bash
make test-e2e  # Runs: pytest tests/e2e/
```

**What it TRIES to test:**

- Valid JWT allows access (positive tests)
- Invalid JWT denied (negative tests)
- Expired JWT rejected
- Signature validation
- Per-request JWT enforcement
- Token lifecycle

**Backend:** Should work for both (currently works for neither)

## Problem Analysis

### Issue 1: Duplicate JWT Tests

Both directories test JWT authentication:

**tests/stateless/test_jwt_authentication.py:**

- Environment variable checks ✅
- Missing JWT fails ✅
- Malformed JWT fails ✅

**tests/e2e/test_jwt_enforcement.py:**

- Valid JWT succeeds ❌ (no server)
- Missing JWT fails ❌ (no server)
- Malformed JWT fails ❌ (no server)
- Expired JWT fails ❌ (no server)
- Wrong signature fails ❌ (no server)
- Per-request enforcement ❌ (no server)

**Overlap:** Both test JWT rejection (malformed/missing)

### Issue 2: No Shared Infrastructure

`tests/stateless/` has Docker infrastructure but `tests/e2e/` doesn't.

**Current approach:**

```
tests/
├── stateless/
│   ├── conftest.py          # Docker fixtures
│   └── test_*.py            # Use Docker fixtures
└── e2e/
    └── test_*.py            # No fixtures, broken
```

**Problem:** Can't reuse Docker infrastructure across directories

### Issue 3: Unclear Test Boundaries

What's the difference between "stateless test" and "e2e test"?

**Current confusion:**

- JWT auth tests in both places
- Docker infrastructure only in stateless/
- e2e tests can't run without infrastructure

## Proposed Solution

### Principle: Separate by Concern

**tests/stateless/** - Tests stateless deployment constraints

- Focus: Container configuration, security, resource limits
- Infrastructure: Docker with read-only filesystem, security opts
- Backend: Platform/stateless only (container-specific)
- Examples:
  - Container starts with correct constraints
  - Filesystem is read-only
  - No state persists across restarts
  - Memory/CPU limits enforced

**tests/e2e/** - Tests MCP protocol behavior (backend-agnostic)

- Focus: MCP protocol correctness, API contracts, functional workflows
- Infrastructure: Docker containers (same fixtures as stateless)
- Backend: **Backend-agnostic** - tests don't know/care what's inside
- Examples:
  - JWT authentication enforcement (positive/negative cases)
  - Package operations work end-to-end
  - Search returns expected results
  - Visualization generation succeeds
  - Multi-step workflows complete

### Shared Infrastructure Approach

**Option A: Shared conftest.py in tests/**

```
tests/
├── conftest.py              # Shared fixtures (Docker, JWT, etc)
├── stateless/
│   └── test_*.py            # Use shared fixtures
└── e2e/
    └── test_*.py            # Use shared fixtures
```

**Option B: Stateless infrastructure, e2e imports**

```
tests/
├── stateless/
│   ├── conftest.py          # Docker fixtures
│   └── test_*.py
└── e2e/
    ├── conftest.py          # Import from stateless.conftest
    └── test_*.py
```

**Recommendation:** Option A (cleaner, pytest convention)

## Test Reorganization Plan

### Step 1: Move Fixtures to tests/conftest.py

Move from `tests/stateless/conftest.py` to `tests/conftest.py`:

- `docker_client` - Docker client fixture
- `docker_image_name` - Image name configuration
- `build_docker_image` - Docker build fixture
- `stateless_container` - Containerized server fixture
- `container_url` - HTTP endpoint fixture
- `make_test_jwt()` - JWT generation helper

**Rationale:** Both test suites need these

### Step 2: Keep Stateless-Specific Tests in tests/stateless/

Keep these tests focused on stateless deployment:

- `test_basic_execution.py` - Container constraints
- `test_persistent_state.py` - No state persistence

Move JWT tests to e2e (see Step 3).

### Step 3: Consolidate JWT Tests in tests/e2e/

Create `tests/e2e/test_jwt_enforcement.py` with comprehensive coverage:

**From tests/stateless/test_jwt_authentication.py (keep 2 tests):**

- `test_jwt_required_environment_variable()` - Container config ← KEEP in stateless
- `test_request_without_jwt_fails_clearly()` ← MOVE to e2e
- `test_request_with_malformed_jwt_fails_clearly()` ← MOVE to e2e

**From tests/e2e/test_jwt_enforcement.py (add all):**

- `test_valid_jwt_allows_access()` - Positive test
- `test_missing_jwt_denies_access()` - Negative test (DUPLICATE)
- `test_malformed_jwt_denies_access()` - Negative test (DUPLICATE)
- `test_expired_jwt_denies_access()` - Expiration check
- `test_wrong_signature_denies_access()` - Signature validation
- `test_tool_calls_require_jwt()` - Per-request enforcement
- `test_resources_require_jwt()` - Resource enforcement
- `test_jwt_refresh_not_required_within_expiry()` - Token lifecycle

**Result:** Single comprehensive JWT test suite in e2e/

### Step 4: ~~Add Backend Parametrization~~ Make E2E Tests Backend-Agnostic

**WRONG APPROACH (from original spec):**

```python
@pytest.mark.parametrize("backend_mode", ["platform", "quilt3"])  # ❌ NO!
def test_valid_jwt_allows_access(container_url: str, backend_mode: str):
    pass
```

**CORRECT APPROACH:**

```python
# tests/e2e/test_jwt_enforcement.py

def test_valid_jwt_allows_access(container_url: str):
    """Test JWT auth works - backend-agnostic."""
    # Test uses container_url fixture (Docker container running)
    # Test doesn't know or care what backend is inside
    # Test only validates MCP protocol behavior
    pass
```

**Why:** E2E tests validate the MCP protocol surface, not backend implementation details. The container could be running ANY backend - tests shouldn't care.

### Step 5: Update Make Targets to RUN Containers

**CRITICAL FIX:** Make targets must START containers, not just build them!

**make test-stateless:**

```makefile
test-stateless: docker-build
 @echo "Running stateless deployment constraint tests..."
 @export TEST_DOCKER_IMAGE=quilt-mcp:test && \
  export QUILT_DISABLE_CACHE=true && \
  export PYTHONPATH="src" && \
  uv run python -m pytest tests/stateless/ -v
```

**What it does:**

- Builds Docker image (`docker-build` dependency)
- Pytest fixtures START containerized server with constraints
- Tests validate container configuration
- Fixtures STOP and cleanup containers after tests

**What it tests:**

- Read-only filesystem enforcement
- Security constraints
- Resource limits
- No persistent state

**make test-e2e:**

```makefile
test-e2e: docker-build
 @echo "Running end-to-end MCP protocol tests..."
 @export TEST_DOCKER_IMAGE=quilt-mcp:test && \
  export QUILT_DISABLE_CACHE=true && \
  export PYTHONPATH="src" && \
  uv run python -m pytest tests/e2e/ -v
```

**What it does:**

- Builds Docker image (`docker-build` dependency)
- Pytest fixtures START containerized MCP server
- Tests make HTTP/MCP requests to `container_url`
- Tests are backend-agnostic (don't know what's inside)
- Fixtures STOP and cleanup containers after tests

**What it tests:**

- JWT authentication enforcement (comprehensive)
- Package operations (end-to-end)
- Search functionality
- Multi-step workflows
- MCP protocol correctness

## File-by-File Changes

### Move: tests/conftest.py (NEW)

**Create:** `tests/conftest.py`
**Content:** Move from `tests/stateless/conftest.py`:

- All Docker fixtures
- JWT helper functions
- Utility functions

### Update: tests/e2e/conftest.py

**CRITICAL REMOVAL:** Delete `backend_mode` from pytestmark!

**Current (WRONG):**

```python
pytestmark = pytest.mark.usefixtures(
    "test_env",
    "clean_auth",
    "cached_athena_service_constructor",
    "backend_mode",  # ❌ REMOVE THIS!
    "requires_catalog",
    "test_bucket",
    "test_registry",
)
```

**Corrected:**

```python
pytestmark = pytest.mark.usefixtures(
    "test_env",
    "clean_auth",
    "cached_athena_service_constructor",
    # "backend_mode" REMOVED - e2e tests are backend-agnostic!
    "requires_catalog",
    "test_bucket",
    "test_registry",
)
```

**Why:** E2E tests must NOT know about backend modes. They test the MCP protocol surface via `container_url` only.

### Update: tests/stateless/conftest.py

**Keep:**

- Stateless-specific fixtures (if any)
- Or delete if empty after move

**Import from parent:**

```python
# Import shared fixtures from tests/conftest.py
from ..conftest import *  # noqa
```

### Update: tests/stateless/test_jwt_authentication.py

**Keep:**

- `test_jwt_required_environment_variable()` - Checks container env vars

**Remove:**

- `test_request_without_jwt_fails_clearly()` - Move to e2e
- `test_request_with_malformed_jwt_fails_clearly()` - Move to e2e

**Rename file:** `test_multiuser_config.py` (better describes what's left)

### Create: tests/e2e/test_jwt_enforcement.py

**Merge:**

1. JWT tests from `tests/stateless/test_jwt_authentication.py`
2. JWT tests from `tests/e2e/test_jwt_enforcement.py` (broken version)

**Organize:**

```python
class TestJWTEnforcement:
    """Test JWT authentication enforcement (negative tests)."""

    def test_missing_jwt_denies_access(...)
    def test_malformed_jwt_denies_access(...)
    def test_expired_jwt_denies_access(...)
    def test_wrong_signature_denies_access(...)

class TestJWTAuthorization:
    """Test JWT authorization works (positive tests)."""

    def test_valid_jwt_allows_initialize(...)
    def test_valid_jwt_allows_tools_list(...)
    def test_valid_jwt_allows_tool_calls(...)
    def test_valid_jwt_allows_resource_reads(...)

class TestJWTPerRequestEnforcement:
    """Test JWT is required on EVERY request."""

    def test_tool_calls_require_jwt_per_request(...)
    def test_resources_require_jwt_per_request(...)

class TestJWTTokenLifecycle:
    """Test JWT token lifecycle."""

    def test_jwt_works_multiple_requests_within_expiry(...)
    def test_different_sessions_are_isolated(...)
```

### Delete: tests/e2e/test_jwt_enforcement.py (current broken version)

**Action:** Delete after merging useful content into new version

## Test Matrix After Reorganization

### tests/stateless/

| Test File | Focus | Backend | Infrastructure |
|-----------|-------|---------|----------------|
| test_basic_execution.py | Container starts correctly | Platform | Docker |
| test_persistent_state.py | No state persists | Platform | Docker |
| test_multiuser_config.py | QUILT_MULTIUSER_MODE set | Platform | Docker |

**Run:** `make test-stateless`
**Purpose:** Validate stateless deployment constraints

### tests/e2e/

| Test File | Focus | Backend | Infrastructure |
|-----------|-------|---------|----------------|
| test_jwt_enforcement.py | JWT authentication works | Both | Docker |
| test_package_operations.py | Package workflows | Both | Docker or direct |
| test_search.py | Search functionality | Both | Docker or direct |
| test_visualization.py | Viz generation | Both | Docker or direct |

**Run:** `make test-e2e`
**Purpose:** Validate functional correctness across backends

## Benefits of This Approach

### 1. Clear Separation of Concerns

**Stateless tests:** "Does the container run correctly?"
**E2E tests:** "Does the functionality work correctly?"

### 2. Reusable Infrastructure

Docker fixtures available to both test suites via `tests/conftest.py`

### 3. Backend Agnosticism

E2E tests are backend-agnostic - they test MCP protocol behavior:

```python
def test_package_browse(container_url: str):
    # Test works against ANY backend
    # Container could be running quilt3 or platform - test doesn't care
    # Test only validates MCP protocol contracts
    pass
```

### 4. No Test Duplication

JWT tests consolidated in one place (e2e), not spread across two directories

### 5. Faster Iteration

**Quick stateless check:** `make test-stateless` (fast, container-specific)
**Comprehensive validation:** `make test-e2e` (slower, functional)

## Migration Steps (Implementation Order)

### Phase 1: Infrastructure Consolidation

1. Create `tests/conftest.py`
2. Move Docker fixtures from `tests/stateless/conftest.py`
3. Update `tests/stateless/conftest.py` to import from parent
4. **CRITICAL:** Remove `backend_mode` from `tests/e2e/conftest.py` pytestmark
5. Verify `make test-stateless` still works

### Phase 2: JWT Test Consolidation

1. Create new `tests/e2e/test_jwt_enforcement.py` with comprehensive tests
2. Update to use shared fixtures from `tests/conftest.py`
3. Verify tests can run: `pytest tests/e2e/test_jwt_enforcement.py`
4. Remove JWT tests from `tests/stateless/test_jwt_authentication.py`
5. Rename remaining file to `test_multiuser_config.py`

### Phase 3: Cleanup

1. Delete old broken `tests/e2e/test_jwt_enforcement.py` if different
2. Update documentation in test files
3. Run full test suite: `make test-all`

### Phase 4: ~~Backend Parametrization~~ Verification

1. ~~Add backend parametrization~~ Verify e2e tests are backend-agnostic
2. ~~Test against both backends~~ Confirm tests use `container_url` fixture only
3. **COMPLETED:** Removed `backend_mode` from `tests/e2e/conftest.py` (Phase 1, step 4)
4. Verify no e2e test functions reference `backend_mode` parameter
5. Grep for any remaining `TEST_BACKEND_MODE` usage in e2e tests

## Open Questions

### Q1: Should e2e tests always use Docker?

**Answer:** YES - E2E tests MUST always use Docker containers.

**Option A (CORRECT):** Always containerized (consistent with production)

```python
def test_package_browse(container_url: str):
    # Always hits containerized server
    # Backend-agnostic - tests MCP protocol
```

**Option B (WRONG):** Direct backend calls

```python
def test_package_browse(backend: Quilt3Backend):  # ❌ NO!
    # Direct backend call - this is NOT e2e testing
    # This is unit/integration testing
    # Belongs in tests/unit/ or tests/func/
```

**Rationale:**

- E2E tests validate the full MCP protocol stack (HTTP transport, JWT auth, JSON-RPC)
- Direct backend calls bypass transport/auth layers
- Docker ensures realistic production-like environment
- Backend-agnostic tests can run against any container configuration

### Q2: How to handle quilt3 deprecation?

**Current state:** Quilt3 backend being deprecated in favor of platform backend

**Impact on tests:**

- Stateless tests: Platform only (already correct)
- E2E tests: **Already backend-agnostic** - no changes needed!

**Recommendation:**

- ~~Keep backend parametrization~~ E2E tests are already backend-agnostic
- When quilt3 deprecated, **no test changes needed**
- Just change the Docker container configuration (environment variables)
- Tests continue working unchanged (they only test MCP protocol)

### Q3: What about test-mcp-stateless target?

**Current:** Uses old `scripts/mcp-test.py` approach (from spec 07)

**Options:**

1. Delete it (redundant with `test-stateless` + `test-e2e`)
2. Keep as convenience wrapper
3. Migrate to pytest-based approach

**Recommendation:** Phase it out, document `test-stateless` + `test-e2e` as replacement

## Success Criteria

### After Implementation

✅ **Both test suites run successfully:**

```bash
make test-stateless  # Passes
make test-e2e        # Passes
```

✅ **Clear separation of concerns:**

- Stateless tests only check deployment constraints
- E2E tests only check functional correctness

✅ **No duplicate tests:**

- JWT tests only in e2e/
- Container constraint tests only in stateless/

✅ **Shared infrastructure:**

- Docker fixtures in tests/conftest.py
- Both suites can use them

✅ **Comprehensive JWT coverage:**

- Positive tests (valid JWT works)
- Negative tests (invalid JWT fails)
- Per-request enforcement
- Token lifecycle

## Summary

**Problem:** Tests are split across two directories with duplicate functionality and broken infrastructure

**Solution:**

- **tests/stateless/** - Deployment constraint tests (Docker-specific)
- **tests/e2e/** - Functional correctness tests (backend-agnostic)
- **tests/conftest.py** - Shared infrastructure (Docker fixtures, JWT helpers)

**Next Steps:** Implement Phase 1 (infrastructure consolidation) and verify tests still pass

---

**Document Status:** Ready for implementation
**Blocked by:** None
**Blocking:** JWT enforcement fixes (spec 07)
