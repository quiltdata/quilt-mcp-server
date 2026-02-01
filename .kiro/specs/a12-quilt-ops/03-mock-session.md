# A12 QuiltOps Migration: Comprehensive Test Failure Analysis

**Date:** 2026-01-31
**Issue:** QuiltOpsFactory authentication breaking tests across multiple test suites
**Status:** Root cause identified, comprehensive fix designed

---

## Executive Summary

The QuiltOps migration (commit bf51fca and earlier) introduced `QuiltOpsFactory.create()` which validates authentication by calling `quilt3.session.get_session_info()`. This broke 15 test methods across 4 test files that don't mock this authentication check.

**Impact:**
- 15 test methods currently failing
- 3 outdated tests should be deleted
- 200+ other tests unaffected (proper mocking patterns)

**Solution:**
- Add `quilt3.session.get_session_info()` mock to affected tests
- Delete obsolete migration tests
- Zero production code changes required

---

## Root Cause Analysis

### The Authentication Layer

**File:** [src/quilt_mcp/ops/factory.py:88](../../../src/quilt_mcp/ops/factory.py#L88)

```python
@staticmethod
def _detect_quilt3_session() -> Optional[dict]:
    """Detect and validate quilt3 session."""
    if quilt3 is None:
        return None

    try:
        # THIS IS THE CRITICAL LINE
        session_info = quilt3.session.get_session_info()
        if session_info:
            return session_info
        else:
            return None
    except Exception as e:
        return None
```

**What happens:**
1. Any function calling `QuiltOpsFactory.create()` triggers session validation
2. If `quilt3.session.get_session_info()` returns `None` or isn't mocked, factory raises `AuthenticationError`
3. The function never reaches the actual operation (browse, list, etc.)
4. Tests expecting success get authentication errors instead

### Functions Using QuiltOpsFactory

Only **2 functions** in production code use the factory:

1. **`packages_list()`** - [src/quilt_mcp/tools/packages.py:668](../../../src/quilt_mcp/tools/packages.py#L668)
   ```python
   quilt_ops = QuiltOpsFactory.create()
   with suppress_stdout():
       package_infos = quilt_ops.search_packages(query="", registry=normalized_registry)
   ```

2. **`package_browse()`** - [src/quilt_mcp/tools/packages.py:812](../../../src/quilt_mcp/tools/packages.py#L812)
   ```python
   quilt_ops = QuiltOpsFactory.create()
   with suppress_stdout():
       content_infos = quilt_ops.browse_content(package_name, registry=normalized_registry, path="")
   ```

### Why Tests Break

**Old Flow (Pre-Migration):**
```
Test mocks quilt3.list_packages()
→ Function calls quilt3.list_packages()
→ Mock intercepts
→ Test passes ✓
```

**New Flow (Post-Migration):**
```
Test mocks quilt3.list_packages()
→ Function calls QuiltOpsFactory.create()
→ Factory calls quilt3.session.get_session_info() (NOT MOCKED!)
→ Returns None
→ Factory raises AuthenticationError ✗
→ quilt3.list_packages() mock never reached
→ Test fails ✗
```

---

## Affected Test Files

### Summary Table

| File | Location | Tests | Status | Action |
|------|----------|-------|--------|--------|
| test_quilt_tools.py | tests/e2e | 7 | ❌ Failing | Add session mocks |
| test_mcp_server.py | tests/unit | 1 | ❌ Failing | Add session mock |
| test_packages_integration.py | tests/integration | 5 | ❌ Failing | Add session fixture |
| test_packages_migration.py | tests/e2e | 3 | 🗑️ Outdated | Delete file |

### File 1: tests/e2e/test_quilt_tools.py

**7 affected test methods:**

1. `test_packages_list_success` (line 46)
2. `test_packages_list_with_prefix` (line 69)
3. `test_packages_list_error` (line 90)
4. `test_package_browse_success` (line 100)
5. `test_package_browse_error` (line 129)
6. `test_package_diff_browse_error` (line 362)
7. `test_package_diff_diff_error` (line 376)

**Current mocking pattern:**
```python
with patch("quilt3.list_packages", return_value=mock_packages):
    result = packages_list(registry="s3://...")
```

**Issue:**
- Mocks old quilt3 API (`quilt3.list_packages`)
- Doesn't mock `quilt3.session.get_session_info()`
- Factory fails before reaching mocked functions

**Required fix:**
```python
with (
    patch("quilt3.session.get_session_info", return_value={"registry": "s3://test"}),
    patch("quilt3.search_util.search_api", return_value=[...]),
):
```

**Note:** Also need to update mock target from `quilt3.list_packages` → `quilt3.search_util.search_api` because QuiltOps uses the search API internally.

### File 2: tests/unit/test_mcp_server.py

**1 affected test method:**

- `test_quilt_tools` (line 17)

**Current code:**
```python
def test_quilt_tools():
    result = packages_list(registry="s3://quilt-ernest-staging")
    assert hasattr(result, 'success')
```

**Issue:** Calls `packages_list()` directly without any mocking

**Required fix:**
```python
@patch("quilt3.session.get_session_info", return_value={"registry": "s3://quilt-ernest-staging"})
@patch("quilt3.search_util.search_api", return_value=[])
def test_quilt_tools(mock_search, mock_session):
    result = packages_list(registry="s3://quilt-ernest-staging")
```

### File 3: tests/integration/test_packages_integration.py

**5 affected test methods:**

1. `test_package_create_update_delete_workflow` (line 31)
2. `test_packages_list_integration` (line 131)
3. `test_package_browse_requires_registry` (line 292)
4. Plus 2 error validation tests

**Current pattern:** No mocking (designed for real AWS integration)

**Issue:** Tests fail when no real quilt3 session exists

**Required fix:** Add session fixture:
```python
@pytest.fixture
def mock_quilt_session(self):
    """Mock quilt3 session for integration tests."""
    with patch("quilt3.session.get_session_info", return_value={"registry": "s3://quilt-ernest-staging"}):
        yield
```

Then update each test to use the fixture:
```python
def test_packages_list_integration(self, mock_quilt_session):
```

### File 4: tests/e2e/test_packages_migration.py

**3 test methods (all outdated):**

1. `test_packages_list_uses_quilt_service` (line 22)
2. `test_package_browse_uses_quilt_service` (line 36)
3. `test_package_diff_uses_quilt_service` (line 60)

**Why outdated:**
- Tests validate old `QuiltService` class
- `QuiltService` no longer exists in codebase
- Current implementation uses `QuiltOpsFactory` (new pattern)
- Tests reference non-existent imports

**Action:** Delete entire file

---

## Unaffected Tests (Proper Patterns)

### Backend Unit Tests (100+ tests)

**Files:**
- `tests/unit/backends/test_quilt3_backend_packages.py` (50+ tests)
- `tests/unit/backends/test_quilt3_backend_content.py` (15+ tests)
- `tests/unit/backends/test_quilt3_backend_session.py`
- `tests/unit/backends/test_quilt3_backend_buckets.py`
- `tests/unit/backends/test_quilt3_backend_errors.py` (20+ tests)
- `tests/unit/backends/test_quilt3_backend_core.py`

**Why they pass:**
```python
@patch('quilt3')
def test_search_packages(self, mock_quilt3):
    # Tests the backend directly, not through factory
    backend = Quilt3_Backend(session_info={"test": "session"})
    result = backend.search_packages(...)
```

**Pattern:** Tests instantiate backend directly with mock session, bypassing factory

### Factory Unit Tests (40+ tests)

**File:** `tests/unit/ops/test_factory.py`

**Why they pass:**
```python
@patch('quilt_mcp.ops.factory.quilt3')
def test_create_with_quilt3_session(self, mock_quilt3):
    mock_quilt3.session.get_session_info.return_value = {"catalog_url": "..."}
    factory = QuiltOpsFactory.create()
```

**Pattern:** Properly mocks `quilt3.session.get_session_info()` at factory level

### Integration Tests (30+ tests)

**Files:**
- `tests/integration/test_end_to_end_workflows.py` (6 tests)
- `tests/integration/test_error_handling.py` (7 tests)
- `tests/integration/test_server_initialization.py` (18 tests)

**Why they pass:**
```python
with patch('quilt3.logged_in', return_value=True):
    with patch('quilt3.session.get_session', return_value=mock_session):
        with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
            # Test code
```

**Pattern:** Comprehensive quilt3 session mocking

### QuiltOps Migration Tests (15+ tests)

**File:** `tests/unit/tools/test_packages_quiltops_migration.py`

**Why they pass:**
```python
@patch('quilt_mcp.ops.factory.QuiltOpsFactory')
def test_packages_list_uses_quilt_ops_search_packages(self, mock_factory):
    mock_quilt_ops = Mock()
    mock_factory.create.return_value = mock_quilt_ops
```

**Pattern:** Mocks factory at tool level, avoiding authentication layer entirely

---

## Implementation Strategy

### Standard Mock Pattern

```python
patch("quilt3.session.get_session_info", return_value={"registry": "s3://test-bucket"})
```

**Why this works:**
1. Factory calls `quilt3.session.get_session_info()`
2. Mock returns non-empty dict
3. Factory validation passes
4. Factory creates `Quilt3_Backend` instance
5. Backend calls quilt3 functions (which are also mocked)
6. Test proceeds normally

### Mock Return Value Structure

**Minimal valid session:**
```python
{"registry": "s3://test-bucket"}
```

**Full session:**
```python
{
    "catalog_url": "https://test.quiltdata.com",
    "registry": "s3://test-bucket",
    "refresh_token": "mock-token"
}
```

Any non-empty dict passes validation, but including `registry` is semantically correct.

### Search API Change

**Important:** `packages_list()` now uses QuiltOps search API internally.

**Old mock (doesn't work):**
```python
patch("quilt3.list_packages", return_value=["user/pkg1", "user/pkg2"])
```

**New mock (correct):**
```python
patch("quilt3.search_util.search_api", return_value=[
    {"name": "user/pkg1", "metadata": {"description": "..."}},
    {"name": "user/pkg2", "metadata": {}},
])
```

**Why:**
- `Quilt3_Backend.search_packages()` calls `quilt3.search_util.search_api()`
- Returns list of dicts (Package_Info structure)
- `packages_list()` extracts names: `[pkg_info.name for pkg_info in package_infos]`

---

## Detailed Fix Implementation

### Fix Pattern A: E2E Tests (Context Manager)

**For:** `tests/e2e/test_quilt_tools.py`

**Before:**
```python
def test_packages_list_success(self):
    mock_packages = ["user/package1", "user/package2"]

    with patch("quilt3.list_packages", return_value=mock_packages):
        result = packages_list(registry="s3://quilt-ernest-staging")
```

**After:**
```python
def test_packages_list_success(self):
    with (
        patch("quilt3.session.get_session_info", return_value={"registry": "s3://quilt-ernest-staging"}),
        patch("quilt3.search_util.search_api", return_value=[
            {"name": "user/package1", "metadata": {"description": "Test"}},
            {"name": "user/package2", "metadata": {"description": "Test"}},
        ]),
    ):
        result = packages_list(registry="s3://quilt-ernest-staging")
```

**Changes:**
1. Add session mock first
2. Update target: `quilt3.list_packages` → `quilt3.search_util.search_api`
3. Update return value: list of strings → list of Package_Info dicts
4. Use parenthesized context managers for multiple patches

### Fix Pattern B: Unit Tests (Decorator)

**For:** `tests/unit/test_mcp_server.py`

**Before:**
```python
def test_quilt_tools():
    result = packages_list(registry="s3://quilt-ernest-staging")
    assert hasattr(result, 'success')
```

**After:**
```python
@patch("quilt3.session.get_session_info", return_value={"registry": "s3://quilt-ernest-staging"})
@patch("quilt3.search_util.search_api", return_value=[])
def test_quilt_tools(mock_search, mock_session):
    result = packages_list(registry="s3://quilt-ernest-staging")
    assert hasattr(result, 'success')
```

**Changes:**
1. Add decorators (reverse order: bottom decorator runs first)
2. Add mock parameters to function signature
3. Session mock allows factory to succeed
4. Search API mock provides empty result list

### Fix Pattern C: Integration Tests (Fixture)

**For:** `tests/integration/test_packages_integration.py`

**Add fixture after class definition:**
```python
class TestPackagesIntegration:
    """Integration tests for package operations."""

    @pytest.fixture
    def mock_quilt_session(self):
        """Mock quilt3 session for integration tests."""
        with patch("quilt3.session.get_session_info", return_value={"registry": "s3://quilt-ernest-staging"}):
            yield
```

**Update test methods:**
```python
def test_packages_list_integration(self, mock_quilt_session):
    """Test packages_list with real AWS calls."""
    # Test code (unchanged)
```

**Alternative (per-method decorator):**
```python
@patch("quilt3.session.get_session_info", return_value={"registry": "s3://quilt-ernest-staging"})
def test_packages_list_integration(self, mock_session):
    """Test packages_list with real AWS calls."""
    # Test code (unchanged)
```

---

## Verification Strategy

### Phase 1: Individual Test Verification

**E2E Tests:**
```bash
# Run each failing test
uv run pytest tests/e2e/test_quilt_tools.py::TestQuiltTools::test_packages_list_success -xvs
uv run pytest tests/e2e/test_quilt_tools.py::TestQuiltTools::test_packages_list_with_prefix -xvs
uv run pytest tests/e2e/test_quilt_tools.py::TestQuiltTools::test_packages_list_error -xvs
uv run pytest tests/e2e/test_quilt_tools.py::TestQuiltTools::test_package_browse_success -xvs
uv run pytest tests/e2e/test_quilt_tools.py::TestQuiltTools::test_package_browse_error -xvs
uv run pytest tests/e2e/test_quilt_tools.py::TestQuiltTools::test_package_diff_browse_error -xvs
uv run pytest tests/e2e/test_quilt_tools.py::TestQuiltTools::test_package_diff_diff_error -xvs

# Expected: All 7 pass
```

**Unit Tests:**
```bash
uv run pytest tests/unit/test_mcp_server.py::test_quilt_tools -xvs
# Expected: Passes
```

**Integration Tests:**
```bash
uv run pytest tests/integration/test_packages_integration.py -v --tb=short
# Expected: All pass (may be skipped in CI)
```

### Phase 2: Test Suite Verification

```bash
# E2E suite
uv run pytest tests/e2e/ -v

# Unit suite
uv run pytest tests/unit/ -v

# Integration suite
uv run pytest tests/integration/ -v
```

### Phase 3: Full Test Suite

```bash
# Standard (unit tests only)
make test

# Comprehensive (all tests)
make test-all
```

### Phase 4: Checklist

- [ ] 7 E2E tests pass (test_quilt_tools.py)
- [ ] 1 unit test passes (test_mcp_server.py)
- [ ] 5 integration tests pass (test_packages_integration.py)
- [ ] Outdated file deleted (test_packages_migration.py)
- [ ] No regressions in other test files
- [ ] Linting passes: `make lint`
- [ ] Type checking passes (included in lint)

---

## Risk Assessment

### Low Risk

**Why:**
1. **Zero production code changes** - Only test modifications
2. **Well-understood pattern** - 200+ tests already use proper mocking
3. **Isolated changes** - Each test file independent
4. **Existing coverage** - Backend and factory already well-tested

### Potential Issues

**Issue 1: Mock return value structure**
- **Risk:** Factory might validate session dict structure
- **Mitigation:** Use minimal valid structure `{"registry": "s3://..."}`
- **Fallback:** Check factory tests for expected structure

**Issue 2: Search API return format**
- **Risk:** Tests might expect old list-of-strings format
- **Mitigation:** Update test assertions if needed
- **Note:** `packages_list()` extracts names internally, so result format unchanged

**Issue 3: Integration tests still fail**
- **Risk:** Integration tests might need real AWS credentials
- **Mitigation:** Tests marked with `@pytest.mark.integration`, can skip in CI
- **Note:** Session mock allows tests to run without credentials

---

## Future Recommendations

### 1. Test Fixture Library

Create shared test fixtures for common mocking patterns:

**File:** `tests/conftest.py`

```python
@pytest.fixture
def mock_quilt_session():
    """Mock quilt3 session for all tests."""
    with patch("quilt3.session.get_session_info", return_value={"registry": "s3://test-bucket"}):
        yield

@pytest.fixture
def mock_quilt_backend():
    """Mock QuiltOpsFactory to return mock backend."""
    with patch("quilt_mcp.ops.factory.QuiltOpsFactory") as mock_factory:
        mock_backend = Mock()
        mock_factory.create.return_value = mock_backend
        yield mock_backend
```

**Usage:**
```python
def test_something(mock_quilt_session):
    # Session automatically mocked
    result = packages_list(...)
```

### 2. Test Documentation

Add documentation explaining:
- Why session mocking is required
- When to use different mocking patterns
- Examples from passing tests

**File:** `tests/README.md` (create if doesn't exist)

### 3. CI/CD Integration

Ensure CI pipeline runs all test suites:
```yaml
- make test        # Unit tests (fast, always run)
- make test-all    # All tests (slower, run on PR)
```

### 4. Test Naming Conventions

Consider reorganizing tests:
- `test_quilt_tools.py` → `test_packages_tools_e2e.py` (more specific)
- Delete `test_packages_migration.py` (outdated)
- Keep clear separation: unit / integration / e2e

---

## Commit Strategy

### Commit 1: Add session mocks to E2E tests
```
fix(tests): add quilt3 session mocks to e2e tests

- Add session.get_session_info() mocks to 7 test methods in test_quilt_tools.py
- Update quilt3.list_packages → quilt3.search_util.search_api
- Update mock return values to match Package_Info structure
- Fixes failing tests after QuiltOpsFactory migration

Affected tests:
- test_packages_list_success
- test_packages_list_with_prefix
- test_packages_list_error
- test_package_browse_success
- test_package_browse_error
- test_package_diff_browse_error
- test_package_diff_diff_error
```

### Commit 2: Add session mock to unit tests
```
fix(tests): add quilt3 session mock to test_mcp_server

- Add session mock decorator to test_quilt_tools()
- Fixes test failure after QuiltOpsFactory migration
```

### Commit 3: Add session fixture to integration tests
```
fix(tests): add quilt3 session fixture to integration tests

- Add mock_quilt_session fixture to TestPackagesIntegration
- Update 5 test methods to use fixture
- Allows integration tests to run without real AWS credentials
```

### Commit 4: Remove outdated migration tests
```
refactor(tests): remove outdated QuiltService migration tests

- Delete tests/e2e/test_packages_migration.py
- Tests reference non-existent QuiltService class
- Current implementation uses QuiltOpsFactory (validated by other tests)
```

---

## Related Documentation

**Migration Commits:**
- bf51fca - "fix: complete permissions service RequestContext refactoring"
- f2c4aed - "test: update backend tests for pragmatic error handling"
- 9def38b - "fix: resolve all ruff and mypy linting errors"
- Earlier commits introducing QuiltOpsFactory

**Related Files:**
- [src/quilt_mcp/ops/factory.py](../../../src/quilt_mcp/ops/factory.py) - Factory implementation
- [src/quilt_mcp/backends/quilt3_backend.py](../../../src/quilt_mcp/backends/quilt3_backend.py) - Backend implementation
- [src/quilt_mcp/tools/packages.py](../../../src/quilt_mcp/tools/packages.py) - Tool implementations

**Passing Test Examples:**
- [tests/unit/ops/test_factory.py](../../../tests/unit/ops/test_factory.py) - Factory test patterns
- [tests/unit/tools/test_packages_quiltops_migration.py](../../../tests/unit/tools/test_packages_quiltops_migration.py) - Tool test patterns
- [tests/integration/test_end_to_end_workflows.py](../../../tests/integration/test_end_to_end_workflows.py) - Integration test patterns

---

## Conclusion

The QuiltOps migration successfully modernized the architecture but exposed a gap in test mocking patterns. The fix is straightforward: add `quilt3.session.get_session_info()` mocks to 15 test methods across 3 files, and delete 1 outdated test file.

**Key Takeaway:** When introducing authentication layers, all tests calling through that layer must mock the authentication check. The 200+ passing tests demonstrate proper mocking patterns that can be followed for future test development.

**Status:** Ready for implementation
**Estimated Time:** 30-45 minutes
**Risk Level:** Low
**Production Impact:** None (test-only changes)
