# A10: Eliminate DEFAULT_REGISTRY Code Smell

## Executive Summary

**Core Insight:** The MCP server is conflating three distinct scenarios that should be handled
separately:

1. **Testing Configuration** - Test code needs fixtures, not production defaults
2. **Catalog-Wide Operations** - Search should work across ALL accessible buckets
3. **Bucket-Specific Operations** - Package mutations require explicit bucket from LLM client

**The Fix:** Remove ALL default bucket state management from the MCP server. Let the LLM handle
context and bucket selection.

## The Three-Scenario Framework

### Scenario 1: Testing Configuration

**Problem:** Tests import `DEFAULT_REGISTRY` from production constants

**Current (WRONG):**

```python
# src/quilt_mcp/constants.py
DEFAULT_BUCKET = os.getenv("QUILT_DEFAULT_BUCKET", "")
DEFAULT_REGISTRY = DEFAULT_BUCKET  # Used by tests AND production

# tests/unit/test_s3_package.py
from quilt_mcp.constants import DEFAULT_REGISTRY  # Production constant!
result = package_create(target_registry=DEFAULT_REGISTRY)
```

**Correct Approach:**

```python
# tests/conftest.py
QUILT_TEST_BUCKET = os.getenv("QUILT_TEST_BUCKET", "")

@pytest.fixture
def test_registry():
    """Test bucket fixture - only for tests."""
    if not QUILT_TEST_BUCKET:
        pytest.skip("QUILT_TEST_BUCKET not set")
    return QUILT_TEST_BUCKET
```

**Rationale:**

- Test configuration should NEVER leak into production code
- Environment variable name should be explicit: `QUILT_TEST_BUCKET`
- Tests that need a bucket should explicitly declare dependency via fixture
- Production code should never import test configuration

### Scenario 2: Catalog-Wide Operations (Already Correct)

**Operations that should work across ALL buckets:**

- `search_catalog()` - Already works! Optional bucket parameter
- `search_suggest()` - Already works! No bucket parameter
- `search_graphql()` - Already works! No bucket parameter
- `packages_list()` - **SHOULD** work catalog-wide but currently requires registry

**Current Implementation (search.py):**

```python
def search_catalog(
    query: str,
    bucket: str = "",  # ✅ CORRECT: Empty means "all buckets"
    ...
) -> SearchSuccess:
    """Search across catalog. Bucket parameter is optional."""
```

**Problem: packages_list() requires registry:**

```python
def packages_list(
    registry: str = DEFAULT_REGISTRY,  # ❌ WRONG: Forces single bucket
    ...
) -> PackagesListSuccess:
```

**Should Be:**

```python
def packages_list(
    registry: str = "",  # ✅ CORRECT: Empty means "all registries"
    limit: int = 0,
    prefix: str = "",
) -> PackagesListSuccess:
    """
    List packages across catalog.

    Args:
        registry: Optional S3 bucket to scope results. Empty string searches all accessible buckets.
        limit: Maximum packages to return
        prefix: Filter by package name prefix
    """
    if not registry:
        # List packages across ALL accessible buckets
        return _list_packages_catalog_wide(limit, prefix)
    else:
        # List packages in specific registry
        return _list_packages_in_registry(registry, limit, prefix)
```

**Rationale:**

- LLM should be able to say "show me all packages" without knowing bucket
- Discovery operations should work across entire catalog
- Consistent with `search_catalog()` design pattern
- User can scope to specific bucket if desired

### Scenario 3: Bucket-Specific Operations (Require Explicit Parameter)

**Operations that MUST have explicit bucket - no defaults:**

- `package_create()` - Creating package in specific bucket
- `package_update()` - Modifying package in specific bucket
- `package_delete()` - Deleting package from specific bucket
- `package_browse()` - Browsing package in specific bucket
- `package_diff()` - Comparing packages (may span buckets)
- `bucket_objects_put()` - Writing objects to specific bucket
- All bucket mutation operations

**Current (WRONG):**

```python
def package_create(
    package: str,
    registry: str = DEFAULT_REGISTRY,  # ❌ WRONG: Hidden default
    ...
) -> PackageCreateSuccess:
```

**Correct:**

```python
def package_create(
    package: str,
    registry: str,  # ✅ CORRECT: Required, no default
    ...
) -> PackageCreateSuccess:
    """
    Create a new package in specified registry.

    Args:
        package: Package name (e.g., "namespace/dataset")
        registry: S3 bucket URI (e.g., "s3://my-bucket"). REQUIRED.
    """
    if not registry:
        return ErrorResponse(
            success=False,
            error="Registry parameter is required for package creation. "
                  "Specify target bucket (e.g., registry='s3://my-bucket')",
            error_type="ConfigurationError",
        )
```

**Rationale:**

- Package mutations have consequences - must be explicit
- LLM has conversation context and knows which bucket user is working with
- No "default" bucket exists - each org/user has their own
- Clear error message guides LLM to provide required parameter
- **MCP server should NOT manage this state** - that's the LLM's job

## Implementation Plan

### Phase 1: Create Test-Only Configuration

#### File: tests/conftest.py (NEW)

```python
"""Pytest configuration and shared fixtures."""
import os
import pytest

# Test-only environment variable - NEVER used in production code
QUILT_TEST_BUCKET = os.getenv("QUILT_TEST_BUCKET", "")

@pytest.fixture
def test_bucket():
    """Provide test bucket S3 URI."""
    if not QUILT_TEST_BUCKET:
        pytest.skip("QUILT_TEST_BUCKET environment variable not set")
    return QUILT_TEST_BUCKET

@pytest.fixture
def test_bucket_name():
    """Provide test bucket name (without s3:// prefix)."""
    if not QUILT_TEST_BUCKET:
        pytest.skip("QUILT_TEST_BUCKET environment variable not set")
    return QUILT_TEST_BUCKET.replace("s3://", "")
```

#### File: env.example

```bash
# TEST CONFIGURATION (only for running test suite)
# This should ONLY be set in test environments
QUILT_TEST_BUCKET=s3://your-test-bucket

# DEPRECATED: QUILT_DEFAULT_BUCKET removed - MCP server no longer manages default bucket state
# LLM clients should provide explicit bucket parameters based on conversation context
```

### Phase 2: Remove DEFAULT_REGISTRY from Production Code

#### File: src/quilt_mcp/constants.py

```python
"""Constants used throughout the Quilt MCP server."""
import os

# REMOVED: DEFAULT_BUCKET and DEFAULT_REGISTRY
# Rationale: MCP server should not manage default bucket state
# LLM clients provide explicit bucket parameters based on conversation context

# Test package configuration (can reference any package in any bucket)
KNOWN_TEST_PACKAGE = os.getenv("QUILT_TEST_PACKAGE", "test/raw")
KNOWN_TEST_ENTRY = os.getenv("QUILT_TEST_ENTRY", "README.md")

# REMOVED: KNOWN_TEST_S3_OBJECT
# Tests should construct full S3 URIs using test fixtures
```

### Phase 3: Update Package Operations

**Pattern for Mutation Operations (REQUIRED registry):**

```python
def package_create(
    package: Annotated[str, Field(description="Package name (namespace/name)")],
    registry: Annotated[str, Field(description="S3 bucket URI (REQUIRED)")],
    ...
) -> PackageCreateSuccess | ErrorResponse:
    """Create package in specified registry - registry parameter REQUIRED."""
    if not registry:
        return ErrorResponse(
            success=False,
            error="Registry parameter is required. Specify target S3 bucket.",
            error_type="ConfigurationError",
        )
    # ... implementation
```

**Apply to:**

- `package_create()` - Line 1069
- `package_update()` - Line 1289
- `package_delete()` - Line 1501

**Pattern for Discovery Operations (OPTIONAL registry):**

```python
def packages_list(
    registry: Annotated[
        str,
        Field(
            default="",
            description="Optional S3 bucket URI. Empty string lists all accessible packages.",
        ),
    ] = "",
    limit: Annotated[int, Field(default=0, ge=0)] = 0,
    prefix: Annotated[str, Field(default="")] = "",
) -> PackagesListSuccess:
    """List packages across catalog or in specific registry."""
    if not registry:
        # List packages catalog-wide
        return _list_packages_all_buckets(limit, prefix)
    else:
        # List packages in specific registry
        return _list_packages_in_bucket(registry, limit, prefix)
```

**Apply to:**

- `packages_list()` - Line 588 (change to catalog-wide)
- Keep `package_browse()` as required (viewing specific package in specific location)
- Keep `package_diff()` as it may span buckets (evaluate if registries should be optional)

### Phase 4: Update Health Check

#### File: src/quilt_mcp/tools/error_recovery.py

```python
def _check_package_operations() -> Dict[str, Any]:
    """Check package operations functionality using public demo bucket."""
    try:
        from .packages import packages_list

        # Use explicit public demo bucket for health checks
        # This is read-only public bucket suitable for testing connectivity
        PUBLIC_DEMO_BUCKET = "s3://quilt-example"
        result = packages_list(registry=PUBLIC_DEMO_BUCKET, limit=1)

        if not result.get("success"):
            raise Exception(result.get("error", "Package operations failed"))
        return {"package_ops_available": True}
    except Exception as e:
        raise Exception(f"Package operations failed: {e}")
```

### Phase 5: Update All Tests

**Pattern for test updates:**

```python
# BEFORE
from quilt_mcp.constants import DEFAULT_REGISTRY

def test_package_create():
    result = package_create(
        package="test/data",
        registry=DEFAULT_REGISTRY,
    )

# AFTER
def test_package_create(test_bucket):  # Use fixture
    result = package_create(
        package="test/data",
        registry=test_bucket,
    )
```

**Files to update:**

- `tests/unit/test_s3_package.py` - Remove DEFAULT_REGISTRY import, use fixtures
- `tests/integration/test_integration.py` - Use test_bucket fixture
- All other test files importing from constants

### Phase 6: Catalog-Wide Package Listing (New Feature)

**Implement catalog-wide package discovery:**

```python
def _list_packages_all_buckets(limit: int, prefix: str) -> PackagesListSuccess:
    """List packages across all accessible buckets."""
    from ..services.permissions_service import discover_permissions

    # Discover accessible buckets
    perms = discover_permissions(force_refresh=False)
    if not perms.get("success"):
        return ErrorResponse(
            success=False,
            error="Failed to discover accessible buckets",
        )

    accessible_buckets = perms.get("bucket_permissions", [])
    all_packages = []

    # List packages from each accessible bucket
    for bucket_info in accessible_buckets:
        bucket_uri = f"s3://{bucket_info['bucket']}"
        try:
            bucket_packages = _list_packages_in_bucket(bucket_uri, 0, prefix)
            if bucket_packages.success:
                all_packages.extend(bucket_packages.packages)
        except Exception as e:
            logger.warning(f"Failed to list packages in {bucket_uri}: {e}")
            continue

    # Apply limit if specified
    if limit > 0:
        all_packages = all_packages[:limit]

    return PackagesListSuccess(
        success=True,
        packages=all_packages,
        total=len(all_packages),
        catalog_wide=True,
    )
```

## Benefits of Three-Scenario Architecture

### 1. Separation of Concerns

- **Tests** use explicit test configuration (`QUILT_TEST_BUCKET`)
- **Discovery** works catalog-wide (no bucket needed)
- **Mutations** require explicit bucket (from LLM context)

### 2. LLM-Friendly Design

**LLM can maintain context:**

```text
User: "I'm working with s3://my-company-data"
LLM: [remembers bucket in conversation context]

User: "Create a package called analysis/results"
LLM: package_create(package="analysis/results", registry="s3://my-company-data")

User: "Show me all packages"
LLM: packages_list()  # Catalog-wide search, no bucket needed
```

### 3. No Hidden State

- MCP server doesn't manage "default" bucket
- All bucket decisions are explicit in tool calls
- Easy to debug and understand behavior
- No environment variables controlling production behavior

### 4. Consistent with Search Design

`search_catalog()` already uses optional bucket parameter:

- Empty = search everything
- Specified = scope to bucket

Package listing should follow same pattern.

### 5. Prevents Configuration Bugs

- Can't accidentally use test bucket in production
- Can't forget to configure default bucket
- Clear error messages when bucket required but not provided
- Tests explicitly declare their bucket dependency

## Breaking Changes

### YES - This is a Breaking Change

**What breaks:**

```python
# These calls will fail with clear error
package_create(package="foo/bar")  # Error: registry required
package_update(package="foo/bar")  # Error: registry required
```

**How to fix (for LLM clients):**

```python
# LLM maintains bucket in conversation context
package_create(package="foo/bar", registry="s3://my-bucket")
package_update(package="foo/bar", registry="s3://my-bucket")

# Discovery operations work catalog-wide
packages_list()  # Lists all packages user can access
```

**Migration for tests:**

```python
# Use pytest fixtures
def test_create(test_bucket):
    package_create(package="test/data", registry=test_bucket)
```

## Implementation Checklist

### Checklist Phase 1: Test Configuration

- [ ] Create `tests/conftest.py` with test fixtures
- [ ] Add `QUILT_TEST_BUCKET` to `env.example`
- [ ] Document test environment setup in README

### Checklist Phase 2: Remove Production Defaults

- [ ] Remove `DEFAULT_BUCKET` from `src/quilt_mcp/constants.py`
- [ ] Remove `DEFAULT_REGISTRY` from `src/quilt_mcp/constants.py`
- [ ] Remove `KNOWN_TEST_S3_OBJECT` from constants

### Checklist Phase 3: Update Package Operations

- [ ] Make `registry` required in `package_create()`
- [ ] Make `registry` required in `package_update()`
- [ ] Make `registry` required in `package_delete()`
- [ ] Make `registry` optional in `packages_list()` (catalog-wide)
- [ ] Add validation and clear error messages

### Checklist Phase 4: Update Health Check

- [ ] Use explicit `s3://quilt-example` in health check
- [ ] Remove `DEFAULT_REGISTRY` import

### Checklist Phase 5: Update Tests

- [ ] Update all tests to use `test_bucket` fixture
- [ ] Remove all `DEFAULT_REGISTRY` imports from tests
- [ ] Add tests for catalog-wide package listing
- [ ] Add tests for error cases (missing registry)

### Checklist Phase 6: Implement Catalog-Wide Listing

- [ ] Implement `_list_packages_all_buckets()`
- [ ] Update `packages_list()` to support empty registry
- [ ] Add tests for catalog-wide listing

### Checklist Phase 7: Documentation

- [ ] Update README with configuration changes
- [ ] Update CHANGELOG with breaking changes
- [ ] Document test environment setup
- [ ] Add examples of LLM usage patterns

## Phase 8: Test Coverage Improvements

### Problem: Coverage Dropped from 55.7% to 53.9%

After removing `DEFAULT_REGISTRY`, test coverage dropped by 1.8% because:

1. **Tests are being skipped** instead of failing when `QUILT_TEST_BUCKET` is not set
2. **Modified APIs lack coverage** - especially the new explicit-registry functions
3. **packages.py has only 27.3% coverage** (102 lines unit-only, 236 lines e2e-only)

### Fix 1: Make Tests Fail (Not Skip) Without Test Bucket

**Problem:** Current behavior silently skips tests:

```python
@pytest.fixture(scope="session")
def test_bucket() -> str:
    if not QUILT_TEST_BUCKET:
        pytest.skip("QUILT_TEST_BUCKET environment variable not set")  # ❌ SILENT
    return QUILT_TEST_BUCKET
```

**This is dangerous because:**

- CI may pass without running critical tests
- Developers don't realize tests aren't running
- Coverage can drop silently

**Solution:** Fail explicitly in CI, skip only for local dev:

```python
@pytest.fixture(scope="session")
def test_bucket() -> str:
    """Provide test bucket S3 URI for tests that require write access.

    Behavior:
    - CI/CD (CI=true): FAIL if QUILT_TEST_BUCKET not set
    - Local dev: SKIP if QUILT_TEST_BUCKET not set (allows partial testing)

    Returns:
        S3 URI of test bucket (e.g., "s3://my-test-bucket")

    Raises:
        pytest.skip: If QUILT_TEST_BUCKET not set and running locally
        RuntimeError: If QUILT_TEST_BUCKET not set and running in CI
    """
    if not QUILT_TEST_BUCKET:
        if os.getenv("CI"):
            pytest.fail(
                "QUILT_TEST_BUCKET environment variable is required in CI. "
                "Set this in your GitHub Actions workflow or CI configuration."
            )
        pytest.skip("QUILT_TEST_BUCKET not set (local dev - this is OK)")
    return QUILT_TEST_BUCKET
```

**Apply to:**

- `test_bucket()` fixture in `tests/conftest.py`
- `test_bucket_name()` fixture in `tests/conftest.py`

**Update GitHub Actions:**

```yaml
# .github/workflows/test.yml
env:
  QUILT_TEST_BUCKET: s3://quilt-ci-test-bucket  # Set in CI
  CI: true  # Tells fixtures to fail instead of skip
```

### Fix 2: Add Coverage for Modified Package APIs

**Current Coverage:** `packages.py` has 27.3% combined coverage

**Target:** Add tests for newly modified functions to restore 55%+ coverage

#### 2.1 Test `package_create()` with Explicit Registry

**What Changed:**

- `registry` parameter is now **required** (was optional with default)
- Should return clear error if registry not provided

**New Tests Needed:**

```python
# tests/unit/test_packages_api.py (NEW FILE)
import pytest
from quilt_mcp.tools.packages import package_create, package_update, package_delete

def test_package_create_requires_registry():
    """package_create() should fail with clear error if registry not provided."""
    result = package_create(
        package="test/data",
        registry="",  # Empty string
        message="Test",
    )

    assert not result["success"]
    assert "registry" in result["error"].lower()
    assert "required" in result["error"].lower()
    # Should suggest what to do
    assert "s3://" in result["error"]


def test_package_create_with_explicit_registry(test_bucket):
    """package_create() works when registry explicitly provided."""
    result = package_create(
        package="test/coverage-test",
        registry=test_bucket,  # Explicit
        message="Test coverage",
    )

    # Should succeed or fail with AWS error (not config error)
    if not result["success"]:
        assert "registry" not in result["error"].lower()


def test_package_update_requires_registry():
    """package_update() should fail if registry not provided."""
    result = package_update(
        package="test/data",
        registry="",
        message="Test",
    )

    assert not result["success"]
    assert "registry" in result["error"].lower()


def test_package_delete_requires_registry():
    """package_delete() should fail if registry not provided."""
    result = package_delete(
        package="test/data",
        registry="",
    )

    assert not result["success"]
    assert "registry" in result["error"].lower()
```

#### 2.2 Test `packages_list()` Catalog-Wide Behavior

**What Changed:**

- `registry` parameter is now **optional** (empty string = catalog-wide)
- Should work without any bucket specified

**New Tests Needed:**

```python
def test_packages_list_catalog_wide():
    """packages_list() should work without registry (catalog-wide search)."""
    result = packages_list(
        registry="",  # Empty = all buckets
        limit=10,
    )

    # Should succeed (even if no packages found)
    assert result["success"]
    assert "packages" in result
    assert isinstance(result["packages"], list)


def test_packages_list_specific_registry(test_bucket):
    """packages_list() should scope to specific registry when provided."""
    result = packages_list(
        registry=test_bucket,
        limit=10,
    )

    assert result["success"]
    # All packages should be from specified registry
    for pkg in result["packages"]:
        assert test_bucket in pkg.get("registry", "")
```

#### 2.3 Test `_normalize_registry()` Helper

**Coverage Gap:** Helper functions often lack coverage

```python
def test_normalize_registry_with_s3_uri():
    """_normalize_registry preserves s3:// URIs."""
    from quilt_mcp.tools.packages import _normalize_registry

    result = _normalize_registry("s3://my-bucket")
    assert result == "s3://my-bucket"


def test_normalize_registry_adds_s3_prefix():
    """_normalize_registry adds s3:// to bare bucket names."""
    from quilt_mcp.tools.packages import _normalize_registry

    result = _normalize_registry("my-bucket")
    assert result == "s3://my-bucket"
```

### Fix 3: Integration Tests for Package Workflows

**Coverage Gap:** packages.py has 102 lines that only unit tests cover, 236 lines only e2e covers

**Strategy:** Add integration tests that exercise real package workflows

```python
# tests/integration/test_packages_integration.py (NEW FILE)
import pytest

@pytest.mark.integration
def test_package_create_update_delete_workflow(test_bucket):
    """Test complete package lifecycle with explicit registry."""
    from quilt_mcp.tools.packages import (
        package_create,
        package_update,
        package_browse,
        package_delete,
    )

    pkg_name = f"test/coverage-{int(time.time())}"

    # 1. Create package
    create_result = package_create(
        package=pkg_name,
        registry=test_bucket,
        message="Initial version",
    )
    assert create_result["success"], f"Create failed: {create_result.get('error')}"

    # 2. Browse to verify
    browse_result = package_browse(
        package=pkg_name,
        registry=test_bucket,
    )
    assert browse_result["success"]

    # 3. Update package
    update_result = package_update(
        package=pkg_name,
        registry=test_bucket,
        message="Updated version",
    )
    assert update_result["success"]

    # 4. Delete package
    delete_result = package_delete(
        package=pkg_name,
        registry=test_bucket,
    )
    assert delete_result["success"]


@pytest.mark.integration
def test_packages_list_integration(test_bucket):
    """Test packages_list with both catalog-wide and scoped queries."""
    from quilt_mcp.tools.packages import packages_list, package_create

    # Ensure at least one package exists
    pkg_name = f"test/list-test-{int(time.time())}"
    package_create(
        package=pkg_name,
        registry=test_bucket,
        message="Test package for listing",
    )

    # Test catalog-wide listing
    all_packages = packages_list(registry="", limit=100)
    assert all_packages["success"]

    # Test scoped listing
    scoped_packages = packages_list(registry=test_bucket, limit=100)
    assert scoped_packages["success"]

    # Verify our test package is in scoped results
    package_names = [p["name"] for p in scoped_packages["packages"]]
    assert pkg_name in package_names
```

### Fix 4: Low-Hanging Fruit in Other Modules

**Modules with 0% coverage that should be tested or removed:**

1. **`data_visualization.py` (306 lines, 0% coverage)**
   - Decision needed: Is this actively used?
   - If YES: Add basic tests for critical paths
   - If NO: Move to `experimental/` or remove

2. **`error_recovery.py` (213 lines, 0% coverage)**
   - Health check functions should be tested
   - Add unit tests for `_check_package_operations()`

3. **`stack_buckets.py` (87 lines, 0% coverage)**
   - Likely dead code - remove if not used
   - Or add to coverage exemptions if experimental

**Quick Win Tests:**

```python
# tests/unit/test_error_recovery.py (NEW FILE)
def test_check_package_operations_uses_public_bucket():
    """Health check should use explicit public bucket, not DEFAULT_REGISTRY."""
    from quilt_mcp.tools.error_recovery import _check_package_operations

    # Should not raise ConfigurationError about missing DEFAULT_REGISTRY
    result = _check_package_operations()

    # Should either succeed or fail with AWS error (not config error)
    assert "registry" not in str(result).lower() or "required" not in str(result).lower()
```

### Coverage Targets After Fixes

| Module | Current | Target | How to Achieve |
|--------|---------|--------|----------------|
| `packages.py` | 27.3% | 50%+ | Add unit tests for API validation, integration tests for workflows |
| `error_recovery.py` | 0% | 40%+ | Test health check functions |
| Overall combined | 53.9% | 55%+ | Above fixes should restore baseline |

### Phase 8 Implementation Checklist

- [ ] Update `test_bucket` fixture to fail in CI (not skip)
- [ ] Update `test_bucket_name` fixture to fail in CI
- [ ] Set `QUILT_TEST_BUCKET` in GitHub Actions
- [ ] Add unit tests for package API validation (registry required)
- [ ] Add unit tests for `packages_list()` catalog-wide behavior
- [ ] Add integration tests for package lifecycle workflows
- [ ] Test or remove `data_visualization.py`
- [ ] Test or remove `stack_buckets.py`
- [ ] Add basic tests for `error_recovery.py` health checks
- [ ] Verify coverage restored to 55%+

### Expected Coverage Gains

| Fix | Coverage Gain |
|-----|---------------|
| Package API validation tests | +0.5% |
| packages_list() catalog-wide tests | +0.3% |
| Integration tests (package lifecycle) | +1.0% |
| error_recovery.py tests | +0.5% |
| **Total Expected** | **+2.3% (to ~56.2%)** |

## Success Criteria

1. ✅ No `DEFAULT_REGISTRY` in production code
2. ✅ No `DEFAULT_BUCKET` in production code
3. ✅ Tests use explicit `test_bucket` fixture
4. ✅ `packages_list()` works catalog-wide
5. ✅ Mutation operations require explicit registry
6. ✅ Clear error messages when registry not provided
7. ✅ All tests pass
8. ✅ Health check uses explicit public bucket
9. ✅ **Tests FAIL (not skip) in CI when QUILT_TEST_BUCKET not set**
10. ✅ **Coverage restored to 55%+ baseline**

## Related

- PR #241: Remove hardcoded test bucket
- Issue #238: Improve test coverage from 55.7% to 75%+
- Original issue: Users getting "Access Denied" to `s3://quilt-ernest-staging`
