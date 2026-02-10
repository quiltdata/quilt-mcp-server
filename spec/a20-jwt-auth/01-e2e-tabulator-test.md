# E2E Tabulator Test with Dynamic Backend Switching

**Spec ID:** a20-jwt-auth/01-e2e-tabulator-test
**Status:** Draft
**Created:** 2026-02-09
**Author:** System Design

---

## Context & Motivation

### Current State

- `scripts/tests/test_tabulator.py` exists as a standalone integration test script (594 lines)
- Tests full tabulator lifecycle: create, list, get, rename, query (Athena), delete
- Uses `QuiltOpsFactory.create()` with hardcoded backend selection
- Has manual credential checking, state management, and subprocess-based Athena querying
- Companion script `tabulator_query.py` handles Athena SQL queries separately
- Not integrated with pytest infrastructure
- No reusable auth helpers

### Why This Matters

1. **First GraphQL E2E Test:** Tabulator operations are our first real test of GraphQL-based functionality in E2E context
2. **Auth Pattern Template:** This will establish the pattern for all future GraphQL E2E tests
3. **Backend Flexibility:** Need to test both quilt3 (local dev) and platform (production) backends
4. **JWT Auth Testing:** Platform backend requires proper JWT auth handling
5. **Test Infrastructure Gap:** E2E tests currently don't have auth helpers or backend switching

### Business Value

- Validates tabulator functionality works end-to-end across both backends
- Catches integration issues before production
- Provides regression protection for tabulator features
- Establishes reusable patterns for future GraphQL tests

---

## Goals

### Primary Goals

1. **Convert Script to Pytest:** Transform `test_tabulator.py` into proper `tests/e2e/test_tabulator.py`
2. **Auth Helper Infrastructure:** Create reusable auth helpers in `tests/e2e/conftest.py`
3. **Dynamic Backend Switching:** Support both quilt3 and platform backends via pytest parametrization
4. **Athena Integration:** Properly integrate Athena querying into the test flow
5. **Clean Test Patterns:** Establish patterns that other E2E tests can follow

### Secondary Goals

- Maintain test coverage from original script (all 6 lifecycle steps)
- Add better error reporting and diagnostics
- Make tests independently runnable (no state persistence needed)
- Enable parallel test execution where possible

---

## Design Overview

### Architecture Principles

```
┌─────────────────────────────────────────────────────────────┐
│                    pytest Test Runner                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ├──> backend_mode fixture (quilt3|platform)
                       │    ├──> Sets environment variables
                       │    ├──> Configures auth context
                       │    └──> Returns backend instance
                       │
                       ├──> auth_helper fixture
                       │    ├──> Provides get_auth_headers()
                       │    ├──> Provides get_graphql_endpoint()
                       │    └──> Handles JWT for platform mode
                       │
                       └──> tabulator_backend fixture
                            ├──> Uses QuiltOpsFactory.create()
                            ├──> Returns backend with tabulator methods
                            └──> Automatically cleaned up after test
```

### Key Design Decisions

**Decision 1: Use Existing `backend_mode` Fixture**

- ✅ Leverage `tests/conftest.py::backend_mode` fixture (lines 213-276)
- ✅ Supports `TEST_BACKEND_MODE` env var: `quilt3`, `platform`, or `both` (default)
- ✅ Already handles JWT generation and runtime context for platform mode

**Decision 2: Auth Helper as New Fixture**

- ✅ Create `auth_backend` fixture in `tests/e2e/conftest.py`
- ✅ Wraps backend with helper methods for auth operations
- ✅ Provides clean API for tests: `auth.get_headers()`, `auth.get_endpoint()`

**Decision 3: Integrate Athena Directly**

- ✅ Use existing `athena_service_factory` from `tests/conftest.py`
- ✅ Replace subprocess call to `tabulator_query.py` with direct Python calls
- ✅ Better error handling and faster execution

**Decision 4: No State Persistence**

- ❌ Remove StateManager class (lines 119-188 in original)
- ✅ Each test is self-contained and stateless
- ✅ Use pytest fixtures for setup/teardown

**Decision 5: Keep Companion Script**

- ✅ Keep `scripts/tests/tabulator_query.py` for manual testing
- ✅ E2E test uses direct Python calls, not subprocess

---

## Component Design

### 1. Auth Helper (`tests/e2e/conftest.py`)

#### Purpose

Provide clean, reusable auth abstractions for E2E tests that work with both backends.

#### Design

```python
class AuthBackend:
    """Backend-agnostic auth helper for E2E tests.

    Wraps a QuiltOps backend and provides simplified auth methods
    that work regardless of whether it's quilt3 or platform mode.
    """

    def __init__(self, backend: QuiltOps, backend_mode: str):
        self.backend = backend
        self.mode = backend_mode  # "quilt3" or "platform"

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for GraphQL requests.

        - quilt3 mode: Uses session from ~/.quilt/config.yml
        - platform mode: Uses JWT from runtime context
        """

    def get_graphql_endpoint(self) -> str:
        """Get GraphQL endpoint URL.

        - quilt3 mode: From catalog config
        - platform mode: From QUILT_REGISTRY_URL env var
        """

    def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
        """Get catalog configuration."""

    def verify_auth(self) -> bool:
        """Verify authentication is working.

        Returns True if auth is valid, False otherwise.
        """
```

#### Fixture Definition

```python
@pytest.fixture
def auth_backend(backend_mode) -> AuthBackend:
    """Provide authenticated backend for E2E tests.

    Automatically selects quilt3 or platform backend based on
    backend_mode parametrization.

    Args:
        backend_mode: From tests/conftest.py (quilt3|platform)

    Returns:
        AuthBackend: Wrapper with auth helper methods

    Raises:
        pytest.skip: If required credentials not available
    """
    # Create backend using factory (respects backend_mode env vars)
    backend = QuiltOpsFactory.create()

    # Verify credentials are available
    if not _check_auth_available(backend_mode):
        pytest.skip(f"Authentication not available for {backend_mode} mode")

    # Return wrapped backend
    return AuthBackend(backend, backend_mode)
```

#### Helper Functions

```python
def _check_auth_available(mode: str) -> bool:
    """Check if required authentication is available.

    - quilt3: Check ~/.quilt/config.yml exists
    - platform: Check JWT is set in runtime context
    """

def _check_test_bucket_available() -> str:
    """Get test bucket or skip test if not available."""

def _check_athena_available() -> bool:
    """Check if Athena workgroup is accessible."""
```

---

### 2. Tabulator Backend Fixture

#### Purpose

Provide a backend instance with tabulator methods ready to use.

#### Design

```python
@pytest.fixture
def tabulator_backend(auth_backend) -> QuiltOps:
    """Provide backend with tabulator operations.

    This is just an alias for clarity - auth_backend.backend
    already has tabulator methods via TabulatorMixin.
    """
    return auth_backend.backend
```

---

### 3. Test Structure

#### File Organization

```
tests/e2e/
├── conftest.py                    # Auth helpers and fixtures (NEW)
├── test_tabulator.py              # Main tabulator test (NEW)
└── test_tabulator_query.py        # Athena query tests (FUTURE)
```

#### Test Class Structure

```python
@pytest.mark.e2e
@pytest.mark.usefixtures("backend_mode")  # Parametrizes quilt3/platform
class TestTabulatorLifecycle:
    """E2E tests for full tabulator lifecycle.

    Tests run against both quilt3 and platform backends unless
    TEST_BACKEND_MODE environment variable restricts it.
    """

    def test_create_table(self, tabulator_backend, test_bucket):
        """Step 1: Create tabulator table via GraphQL."""

    def test_list_tables(self, tabulator_backend, test_bucket):
        """Step 2: List tables in bucket via GraphQL."""

    def test_get_table(self, tabulator_backend, test_bucket):
        """Step 3: Get specific table metadata via GraphQL."""

    def test_rename_table(self, tabulator_backend, test_bucket):
        """Step 4: Rename table via GraphQL."""

    def test_query_table_athena(self, tabulator_backend, test_bucket, athena_service_factory):
        """Step 5: Query table data via Athena SQL."""

    def test_delete_table(self, tabulator_backend, test_bucket):
        """Step 6: Delete table via GraphQL."""

    def test_full_lifecycle(self, tabulator_backend, test_bucket, athena_service_factory):
        """Integration test: Run all steps in sequence."""
```

---

### 4. Backend Switching Mechanism

#### How It Works

```
1. Test Execution
   └─> pytest runs test with backend_mode fixture

2. Backend Mode Parametrization (tests/conftest.py)
   └─> TEST_BACKEND_MODE=both → runs test twice (quilt3, platform)
   └─> TEST_BACKEND_MODE=quilt3 → runs test once (quilt3)
   └─> TEST_BACKEND_MODE=platform → runs test once (platform)

3. Environment Configuration
   └─> backend_mode fixture sets env vars:
       - QUILT_MULTIUSER_MODE=false (quilt3) or true (platform)
       - QUILT_CATALOG_URL, QUILT_REGISTRY_URL (platform only)
       - MCP_JWT_SECRET (platform only)

4. Auth Context Setup
   └─> backend_mode fixture pushes JWT into runtime context (platform)
   └─> Runtime context cleared after test completes

5. Backend Creation
   └─> QuiltOpsFactory.create() reads environment
   └─> Returns Quilt3_Backend or Platform_Backend

6. Test Execution
   └─> Test uses backend.create_tabulator_table() etc.
   └─> Backend routes to appropriate implementation
```

#### Environment Variables

**For quilt3 mode:**

```bash
TEST_BACKEND_MODE=quilt3
QUILT_MULTIUSER_MODE=false
QUILT_TEST_BUCKET=your-test-bucket
# Credentials from ~/.quilt/config.yml
```

**For platform mode:**

```bash
TEST_BACKEND_MODE=platform
QUILT_MULTIUSER_MODE=true
PLATFORM_TEST_ENABLED=true
QUILT_CATALOG_URL=https://example.quiltdata.com
QUILT_REGISTRY_URL=https://registry.example.quiltdata.com
PLATFORM_TEST_JWT_SECRET=your-secret
PLATFORM_TEST_JWT_TOKEN=eyJ...  # Optional (generated if not provided)
QUILT_TEST_BUCKET=your-test-bucket
```

---

### 5. Athena Integration

#### Current Approach (Script)

```python
# Subprocess call to companion script
cmd = ["uv", "run", "python", "tabulator_query.py", "--bucket", bucket, "--table", table]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
```

#### New Approach (E2E Test)

```python
# Direct Python call using AthenaQueryService
athena = athena_service_factory(use_quilt_auth=True)
result = athena.query_tabulator_table(
    bucket=bucket,
    table=table,
    catalog=catalog_name,
    limit=5
)
```

#### Benefits

- ✅ Faster (no subprocess overhead)
- ✅ Better error handling (Python exceptions vs exit codes)
- ✅ Access to result data structures directly
- ✅ Easier to debug

---

## Migration Strategy

### Phase 1: Create Auth Infrastructure (Priority: High)

**Tasks:**

1. Create `tests/e2e/conftest.py` with auth fixtures
2. Implement `AuthBackend` wrapper class
3. Add `auth_backend` fixture
4. Add helper functions for credential checking
5. Write unit tests for auth helpers

**Deliverables:**

- `tests/e2e/conftest.py` with working fixtures
- Auth helpers tested in isolation

---

### Phase 2: Convert Core Test Logic (Priority: High)

**Tasks:**

1. Create `tests/e2e/test_tabulator.py` skeleton
2. Convert `demo_create_table()` → `test_create_table()`
3. Convert `demo_list_tables()` → `test_list_tables()`
4. Convert `demo_get_table()` → `test_get_table()`
5. Convert `demo_rename_table()` → `test_rename_table()`
6. Convert `demo_delete_table()` → `test_delete_table()`

**Deliverables:**

- 6 individual test methods
- Each test is independent and stateless
- Tests use fixtures instead of StateManager

---

### Phase 3: Integrate Athena Querying (Priority: Medium)

**Tasks:**

1. Add Athena integration helper to conftest
2. Convert `demo_query_table()` → `test_query_table_athena()`
3. Replace subprocess call with direct `AthenaQueryService` usage
4. Add proper error handling for Athena timeouts
5. Add query result validation

**Deliverables:**

- `test_query_table_athena()` working with both backends
- No subprocess dependencies

---

### Phase 4: Add Full Lifecycle Test (Priority: Medium)

**Tasks:**

1. Create `test_full_lifecycle()` integration test
2. Run all 6 steps in sequence
3. Add proper cleanup in case of mid-test failure
4. Add detailed assertion messages
5. Add timing measurements

**Deliverables:**

- `test_full_lifecycle()` that chains all operations
- Comprehensive error messages on failure

---

### Phase 5: Testing & Documentation (Priority: Medium)

**Tasks:**

1. Test with `TEST_BACKEND_MODE=quilt3`
2. Test with `TEST_BACKEND_MODE=platform`
3. Test with `TEST_BACKEND_MODE=both`
4. Add docstrings with examples
5. Update test documentation
6. Add troubleshooting guide

**Deliverables:**

- All tests passing in both modes
- Clear documentation for running tests
- Troubleshooting guide for common issues

---

## Task Breakdown

### Task 1: Auth Helper Infrastructure

**Subtasks:**

1. Create `AuthBackend` class in `tests/e2e/conftest.py`
   - [ ] Implement `__init__(backend, mode)`
   - [ ] Implement `get_auth_headers()`
   - [ ] Implement `get_graphql_endpoint()`
   - [ ] Implement `get_catalog_config()`
   - [ ] Implement `verify_auth()`

2. Create auth helper functions
   - [ ] Implement `_check_auth_available(mode)`
   - [ ] Implement `_check_test_bucket_available()`
   - [ ] Implement `_check_athena_available()`

3. Create fixtures
   - [ ] Implement `auth_backend` fixture
   - [ ] Implement `tabulator_backend` fixture
   - [ ] Add pytest markers (`@pytest.mark.e2e`, `@pytest.mark.tabulator`)

**Acceptance Criteria:**

- [ ] Fixtures work with both quilt3 and platform backends
- [ ] Auth verification works correctly
- [ ] Proper error messages when auth not available
- [ ] Tests skip gracefully when credentials missing

---

### Task 2: Convert Individual Test Steps

**Subtasks:**
For each step (create, list, get, rename, delete):

1. Convert function to test method
   - [ ] Remove state management code
   - [ ] Use fixtures for backend and bucket
   - [ ] Convert print statements to assertions
   - [ ] Add proper pytest assertions

2. Add error handling
   - [ ] Catch specific exceptions
   - [ ] Add helpful error messages
   - [ ] Add debug output on failure

3. Add cleanup
   - [ ] Use pytest fixtures for cleanup
   - [ ] Ensure tables are deleted after test
   - [ ] Handle cleanup failures gracefully

**Acceptance Criteria:**

- [ ] Each test can run independently
- [ ] Tests clean up after themselves
- [ ] Clear assertion messages on failure
- [ ] Tests work with both backends

---

### Task 3: Athena Query Integration

**Subtasks:**

1. Add Athena fixtures to `tests/e2e/conftest.py`
   - [ ] Import `athena_service_factory` from root conftest
   - [ ] Create convenience wrapper if needed

2. Convert query test
   - [ ] Replace subprocess call with direct Python
   - [ ] Use `AthenaQueryService.query_tabulator_table()`
   - [ ] Add result validation
   - [ ] Add timeout handling

3. Add catalog discovery
   - [ ] Get catalog name from bucket config
   - [ ] Handle catalog discovery failures
   - [ ] Add fallback to environment variable

**Acceptance Criteria:**

- [ ] Query test works without subprocess
- [ ] Proper error messages for Athena failures
- [ ] Timeout handling works correctly
- [ ] Results are validated

---

### Task 4: Full Lifecycle Test

**Subtasks:**

1. Create lifecycle test
   - [ ] Call all 6 steps in sequence
   - [ ] Use unique table name per test run
   - [ ] Add assertions between steps

2. Add cleanup strategy
   - [ ] Ensure table deleted even on failure
   - [ ] Use pytest finalizers
   - [ ] Log cleanup actions

3. Add diagnostics
   - [ ] Log each step execution
   - [ ] Add timing measurements
   - [ ] Add state inspection between steps

**Acceptance Criteria:**

- [ ] Full lifecycle test completes successfully
- [ ] Cleanup happens even on failure
- [ ] Clear diagnostics on failure
- [ ] Test is reproducible

---

### Task 5: Backend Switching

**Subtasks:**

1. Verify parametrization works
   - [ ] Test runs twice with `TEST_BACKEND_MODE=both`
   - [ ] Test runs once with `TEST_BACKEND_MODE=quilt3`
   - [ ] Test runs once with `TEST_BACKEND_MODE=platform`

2. Add backend-specific assertions
   - [ ] Verify correct backend class instantiated
   - [ ] Check auth headers format matches backend
   - [ ] Validate GraphQL endpoint URL

3. Add skip conditions
   - [ ] Skip platform tests if `PLATFORM_TEST_ENABLED` not set
   - [ ] Skip if credentials not available
   - [ ] Add clear skip messages

**Acceptance Criteria:**

- [ ] Parametrization works correctly
- [ ] Both backends execute successfully
- [ ] Skip conditions work as expected
- [ ] Clear test output shows which backend is running

---

### Task 6: Documentation & Testing

**Subtasks:**

1. Add docstrings
   - [ ] Document each test method
   - [ ] Add examples of running tests
   - [ ] Document fixtures

2. Update test documentation
   - [ ] Add E2E test guide
   - [ ] Document environment variables
   - [ ] Add troubleshooting section

3. Add integration to CI
   - [ ] Update CI config if needed
   - [ ] Add test job for E2E tests
   - [ ] Configure environment variables

**Acceptance Criteria:**

- [ ] All tests documented
- [ ] Running tests is documented
- [ ] Troubleshooting guide available
- [ ] CI runs E2E tests

---

## Success Criteria

### Functional Requirements

- ✅ All 6 tabulator operations work in E2E test
- ✅ Tests pass with both quilt3 and platform backends
- ✅ Athena querying works without subprocess
- ✅ Tests are independently runnable
- ✅ Cleanup happens reliably

### Code Quality Requirements

- ✅ Auth helpers are reusable for future tests
- ✅ Test code follows pytest best practices
- ✅ Clear, descriptive test names
- ✅ Comprehensive docstrings
- ✅ Proper error messages

### Performance Requirements

- ✅ Full lifecycle test completes in <60 seconds
- ✅ Individual tests complete in <10 seconds
- ✅ Tests can run in parallel (where possible)

### Maintainability Requirements

- ✅ Future tests can reuse auth infrastructure
- ✅ Backend switching is straightforward
- ✅ Adding new backends is easy
- ✅ Debugging failures is straightforward

---

## Non-Goals

### Explicitly Out of Scope

1. **Container-based E2E tests**
   - Current E2E tests use Docker containers
   - This test uses direct backend access
   - Container-based version is future work

2. **Migration of other scripts**
   - Only `test_tabulator.py` in this spec
   - Other scripts (`reproduce_search_bug.py`, etc.) are separate

3. **Performance optimization**
   - Not optimizing query performance
   - Not caching catalog configs
   - Performance improvements are future work

4. **Advanced Athena features**
   - Basic querying only
   - No partition handling
   - No complex SQL

5. **Multi-tenant testing**
   - Single user context only
   - Multi-user scenarios are future work

6. **State persistence**
   - Tests are stateless
   - No resume capability needed

---

## Dependencies

### Required Environment Variables

**Quilt3 mode:**

- `QUILT_TEST_BUCKET` - Test bucket name
- `~/.quilt/config.yml` - Quilt3 credentials

**Platform mode:**

- `QUILT_TEST_BUCKET` - Test bucket name
- `PLATFORM_TEST_ENABLED=true` - Enable platform tests
- `QUILT_CATALOG_URL` - Catalog URL
- `QUILT_REGISTRY_URL` - Registry URL
- `PLATFORM_TEST_JWT_SECRET` - JWT secret (or use generated)
- `PLATFORM_TEST_JWT_TOKEN` - JWT token (optional)

### External Dependencies

- `quilt3` library (for quilt3 backend)
- `requests` library (for GraphQL calls)
- `boto3` library (for Athena queries)
- `pytest` and plugins

---

## Testing Strategy

### Test Levels

**Unit Tests:**

- Test `AuthBackend` methods in isolation
- Test auth helper functions
- Test fixture behavior

**Integration Tests:**

- Individual lifecycle step tests
- Backend switching tests

**E2E Tests:**

- Full lifecycle test
- Real GraphQL calls
- Real Athena queries

### Test Execution Modes

**Local Development:**

```bash
# Run with quilt3 backend only (fast)
TEST_BACKEND_MODE=quilt3 pytest tests/e2e/test_tabulator.py -v

# Run with platform backend only
TEST_BACKEND_MODE=platform PLATFORM_TEST_ENABLED=true pytest tests/e2e/test_tabulator.py -v

# Run with both backends (default)
pytest tests/e2e/test_tabulator.py -v
```

**CI/CD:**

```bash
# Run all E2E tests
pytest tests/e2e/ -v --tb=short
```

---

## Risk Assessment

### High Risks

1. **JWT expiration in platform mode**
   - **Mitigation:** Generate fresh JWTs per test session
   - **Mitigation:** Use long expiration for test JWTs

2. **Athena query timeouts**
   - **Mitigation:** Set reasonable timeouts (60s)
   - **Mitigation:** Add retry logic if needed

3. **Credential availability**
   - **Mitigation:** Clear skip messages when credentials missing
   - **Mitigation:** Document credential setup

### Medium Risks

1. **Backend differences**
   - **Mitigation:** Test with both backends always
   - **Mitigation:** Abstract differences in fixtures

2. **Test bucket conflicts**
   - **Mitigation:** Use unique table names per test
   - **Mitigation:** Clean up in finalizers

3. **Catalog config caching**
   - **Mitigation:** Use fresh config per test
   - **Mitigation:** Clear caches in cleanup

### Low Risks

1. **Test execution order**
   - **Mitigation:** Tests are independent
   - **Mitigation:** No shared state

2. **Resource cleanup**
   - **Mitigation:** Use pytest finalizers
   - **Mitigation:** Fail gracefully on cleanup errors

---

## Future Work

### Phase 2 Enhancements

1. **Container-based variant**
   - Run tests against MCP server in container
   - Test full MCP protocol flow
   - Validate tool responses

2. **Performance benchmarking**
   - Add timing measurements
   - Compare quilt3 vs platform performance
   - Identify bottlenecks

3. **Advanced Athena tests**
   - Test complex queries
   - Test partition handling
   - Test query optimization

4. **Multi-user scenarios**
   - Test with multiple JWT users
   - Test permission boundaries
   - Test concurrent operations

5. **Error injection testing**
   - Test with invalid configs
   - Test with expired JWTs
   - Test with network failures

---

## References

### Related Specs

- `spec/a18-valid-jwts/08-test-organization.md` - Test organization
- `spec/a15-platform/04-tabulator-mixin.md` - Tabulator implementation

### Related Files

- `scripts/tests/test_tabulator.py` - Original script (source)
- `scripts/tests/tabulator_query.py` - Companion script
- `tests/conftest.py` - Root test fixtures
- `tests/e2e/conftest.py` - E2E test fixtures (to be created)
- `src/quilt_mcp/ops/factory.py` - Backend factory
- `src/quilt_mcp/ops/tabulator_mixin.py` - Tabulator operations

### Documentation

- `docs/TESTING.md` - Test documentation (to be updated)
- `docs/ARCHITECTURE.md` - System architecture

---

## Appendix A: Example Test Output

### Successful Test Run

```
$ pytest tests/e2e/test_tabulator.py -v

tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_create_table[quilt3] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_list_tables[quilt3] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_get_table[quilt3] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_rename_table[quilt3] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_query_table_athena[quilt3] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_delete_table[quilt3] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_full_lifecycle[quilt3] PASSED

tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_create_table[platform] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_list_tables[platform] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_get_table[platform] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_rename_table[platform] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_query_table_athena[platform] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_delete_table[platform] PASSED
tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_full_lifecycle[platform] PASSED

========================= 14 passed in 45.23s =========================
```

### Skipped Test (Missing Credentials)

```
$ TEST_BACKEND_MODE=platform pytest tests/e2e/test_tabulator.py -v

tests/e2e/test_tabulator.py::TestTabulatorLifecycle::test_create_table[platform] SKIPPED
Reason: Platform functional tests disabled - set PLATFORM_TEST_ENABLED=true

========================= 1 skipped in 0.12s =========================
```

---

## Appendix B: Code Structure Comparison

### Before (Script Structure)

```
scripts/tests/test_tabulator.py (594 lines)
├── check_credentials_or_fail()         # Lines 63-116
├── StateManager class                  # Lines 119-188
│   ├── __init__()
│   ├── _load_state()
│   ├── save()
│   ├── reset()
│   ├── record_step()
│   └── get_status()
├── demo_create_table()                 # Lines 230-264
├── demo_list_tables()                  # Lines 267-300
├── demo_get_table()                    # Lines 303-330
├── demo_rename_table()                 # Lines 333-364
├── demo_query_table()                  # Lines 367-427 (subprocess)
├── demo_delete_table()                 # Lines 430-460
└── main()                              # Lines 463-593
```

### After (Pytest Structure)

```
tests/e2e/conftest.py (NEW)
├── AuthBackend class
│   ├── __init__()
│   ├── get_auth_headers()
│   ├── get_graphql_endpoint()
│   ├── get_catalog_config()
│   └── verify_auth()
├── auth_backend fixture
├── tabulator_backend fixture
└── Helper functions

tests/e2e/test_tabulator.py (NEW)
└── TestTabulatorLifecycle class
    ├── test_create_table()
    ├── test_list_tables()
    ├── test_get_table()
    ├── test_rename_table()
    ├── test_query_table_athena()
    ├── test_delete_table()
    └── test_full_lifecycle()
```

---

## Appendix C: Decision Log

### Decision 1: Reuse `backend_mode` Fixture

**Date:** 2026-02-09
**Status:** Accepted
**Rationale:** Existing fixture already handles environment setup, JWT generation, and runtime context. No need to duplicate this logic.

### Decision 2: Direct Athena Integration

**Date:** 2026-02-09
**Status:** Accepted
**Rationale:** Subprocess overhead is unnecessary. Direct Python calls are faster, easier to debug, and provide better error handling.

### Decision 3: No State Persistence

**Date:** 2026-02-09
**Status:** Accepted
**Rationale:** Pytest provides better mechanisms (fixtures, finalizers). State persistence adds complexity without benefit for E2E tests.

### Decision 4: AuthBackend Wrapper Class

**Date:** 2026-02-09
**Status:** Accepted
**Rationale:** Provides clean API for tests. Encapsulates backend differences. Makes future backend additions easier.

### Decision 5: Keep Companion Script

**Date:** 2026-02-09
**Status:** Accepted
**Rationale:** Useful for manual testing and debugging. E2E test doesn't need it, but developers might.

---

## Sign-off

**Specification Status:** Ready for Implementation
**Review Required:** Yes
**Approvers:** TBD
**Implementation Start:** TBD
