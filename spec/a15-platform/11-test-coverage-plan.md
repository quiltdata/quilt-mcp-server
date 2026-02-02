# Platform Backend Test Coverage Enhancement Plan

## Executive Summary

The Platform_Backend implementation is **monolithic** (969 lines in one file) while Quilt3_Backend uses a **mixin-based architecture** (7 files, 2,639 lines). Despite this architectural difference, Platform_Backend is **missing domain-specific test files**, resulting in incomplete test coverage.

**Current State:**
- 1 test file: `test_platform_backend_core.py` (363 lines, 18 tests)
- Covers: Basic auth, config, GraphQL execution, and minimal read operations
- Missing: Comprehensive package, content, and bucket operation tests

**Target State:**
- 4 test files mirroring Quilt3_Backend test structure
- Comprehensive coverage of all Platform_Backend public methods (18 methods)
- Test organization aligned with domain responsibilities

---

## Architecture Analysis

### Platform_Backend Structure (Monolithic)

```python
# src/quilt_mcp/backends/platform_backend.py (969 lines)
class Platform_Backend(TabulatorMixin, QuiltOps):
    # Auth & Config (lines 43-80)
    - get_auth_status()
    - get_graphql_endpoint()
    - get_graphql_auth_headers()
    - configure_catalog()

    # Read Operations (lines 130-329)
    - search_packages()
    - get_package_info()
    - browse_content()
    - list_buckets()
    - list_all_packages()
    - diff_packages()

    # Content URLs (lines 329-379)
    - get_content_url()

    # Write Operations (lines 380-676)
    - create_package_revision()
    - update_package_revision()

    # Admin Operations (lines 677-678)
    - get_admin_status() [stub - raises NotImplementedError]

    # 17 private helper methods (lines 680-969)
```

### Quilt3_Backend Structure (Mixin-Based)

```python
# src/quilt_mcp/backends/quilt3_backend.py (78 lines - composer)
class Quilt3_Backend(
    Quilt3_Backend_Session,      # 441 lines
    TabulatorMixin,
    Quilt3_Backend_Buckets,      # 116 lines
    Quilt3_Backend_Content,      # 163 lines
    Quilt3_Backend_Packages,     # 784 lines
    Quilt3_Backend_Admin,        # 756 lines
    Quilt3_Backend_Base,         # 301 lines
    QuiltOps,
):
```

### Test Structure Comparison

| Domain | Quilt3 Tests | Platform Tests | Gap |
|--------|--------------|----------------|-----|
| **Core/Structure** | `test_quilt3_backend_core.py` | `test_platform_backend_core.py` ✓ | None |
| **Package Operations** | `test_quilt3_backend_packages.py` | Missing ❌ | 6 methods untested |
| **Content Operations** | Part of packages tests | Missing ❌ | 2 methods untested |
| **Bucket Operations** | Part of core tests | Minimal ❌ | 1 method minimally tested |
| **Admin Operations** | `test_quilt3_backend_admin.py` | N/A | Admin stub only |

---

## Implementation Plan

### Phase 1: Create `test_platform_backend_packages.py`

**File:** `tests/unit/backends/test_platform_backend_packages.py`

**Test Coverage:**

1. **Search Operations**
   - `test_search_packages_basic_query` - Test basic search with results
   - `test_search_packages_transforms_metadata` - Verify JSON metadata parsing
   - `test_search_packages_empty_results` - Handle empty result sets
   - `test_search_packages_pagination` - Verify firstPage handling
   - `test_search_packages_malformed_meta` - Handle invalid JSON in meta field

2. **Package Info Retrieval**
   - `test_get_package_info_success` - Basic package info retrieval
   - `test_get_package_info_missing_package` - Raise NotFoundError for null package
   - `test_get_package_info_transforms_metadata` - Parse metadata JSON
   - `test_get_package_info_handles_null_fields` - Handle optional fields

3. **Package Listing**
   - `test_list_all_packages_single_page` - List packages < 100 (no pagination)
   - `test_list_all_packages_pagination` - Test pagination with 101+ packages
   - `test_list_all_packages_empty_bucket` - Handle zero packages

4. **Package Diffing**
   - `test_diff_packages_detects_added_files` - Identify new files
   - `test_diff_packages_detects_modified_files` - Detect size/hash changes
   - `test_diff_packages_detects_removed_files` - Identify deleted files
   - `test_diff_packages_identical_packages` - Handle no changes
   - `test_diff_packages_complex_scenario` - Mixed adds/modifies/removes

5. **Package Creation**
   - `test_create_package_revision_basic` - Create package with files
   - `test_create_package_revision_with_metadata` - Include package metadata
   - `test_create_package_revision_copy_mode` - Test copy vs symlink
   - `test_create_package_revision_aws_credentials` - Verify credential context manager usage

6. **Package Updates**
   - `test_update_package_revision_adds_files` - Add files to existing package
   - `test_update_package_revision_updates_metadata` - Merge metadata
   - `test_update_package_revision_preserves_existing` - Don't lose existing files

**Implementation Notes:**
- Mock `execute_graphql_query()` to return controlled GraphQL responses
- Mock `quilt3.Package` for write operations
- Mock `_with_aws_credentials()` context manager
- Use existing `_make_backend()` helper pattern from `test_platform_backend_core.py`

### Phase 2: Create `test_platform_backend_content.py`

**File:** `tests/unit/backends/test_platform_backend_content.py`

**Test Coverage:**

1. **Content Browsing**
   - `test_browse_content_root_directory` - List root-level files/dirs
   - `test_browse_content_subdirectory` - Browse with logical_key path
   - `test_browse_content_mixed_children` - Files and directories together
   - `test_browse_content_empty_directory` - Handle empty directories
   - `test_browse_content_single_file` - When path points to a file, not dir
   - `test_browse_content_transforms_types` - PackageFile vs PackageDir mapping

2. **Content URL Generation**
   - `test_get_content_url_presigned_s3` - Generate S3 presigned URL
   - `test_get_content_url_resolves_physical_key` - Verify GraphQL query for physicalKey
   - `test_get_content_url_missing_file` - Handle file not found in package
   - `test_get_content_url_custom_expiration` - Test expiration parameter
   - `test_get_content_url_aws_credentials` - Verify credential context manager

**Implementation Notes:**
- Mock `execute_graphql_query()` with GraphQL package content responses
- Mock `get_boto3_client()` for S3 presigned URL generation
- Mock `_with_aws_credentials()` context manager
- Test both `dir` and `file` GraphQL response paths

### Phase 3: Create `test_platform_backend_buckets.py`

**File:** `tests/unit/backends/test_platform_backend_buckets.py`

**Test Coverage:**

1. **Bucket Listing**
   - `test_list_buckets_basic` - List buckets from GraphQL
   - `test_list_buckets_transforms_to_bucket_info` - Verify Bucket_Info construction
   - `test_list_buckets_empty_result` - Handle no buckets configured
   - `test_list_buckets_includes_name` - Verify name extraction

2. **Catalog Configuration**
   - `test_configure_catalog_sets_catalog_url` - Store catalog URL
   - `test_configure_catalog_derives_registry_url` - Convert catalog → registry URL
   - `test_configure_catalog_handles_custom_domains` - Test nightly.quilttest.com → nightly-registry.quilttest.com
   - `test_configure_catalog_preserves_existing_registry` - Don't override if already set

3. **Catalog Config Retrieval**
   - `test_get_catalog_config_success` - Fetch config.json from catalog
   - `test_get_catalog_config_parses_stack_prefix` - Extract stack prefix from analyticsBucket
   - `test_get_catalog_config_handles_missing_fields` - Handle optional fields

**Implementation Notes:**
- Mock `execute_graphql_query()` for bucket listing
- Mock `_session.get()` for catalog config.json retrieval
- Test registry URL derivation logic from `configure_catalog()`
- Verify `_catalog_url` and `_registry_url` state management

### Phase 4: Create `test_platform_backend_admin.py`

**File:** `tests/unit/backends/test_platform_backend_admin.py`

**Test Coverage:**

1. **Admin Status (Stub)**
   - `test_get_admin_status_not_implemented` - Verify NotImplementedError is raised
   - Document future admin operations that would go here

**Implementation Notes:**
- Single test verifying current stub behavior
- Document that Platform_Backend intentionally doesn't implement admin operations
- Add comments for future expansion if admin GraphQL APIs become available

---

## Critical Files

### Files to Modify

None (all new test files)

### New Test Files to Create

1. `tests/unit/backends/test_platform_backend_packages.py` (~500 lines)
2. `tests/unit/backends/test_platform_backend_content.py` (~250 lines)
3. `tests/unit/backends/test_platform_backend_buckets.py` (~200 lines)
4. `tests/unit/backends/test_platform_backend_admin.py` (~50 lines)

### Reference Files

1. `tests/unit/backends/test_platform_backend_core.py` - Existing helper patterns
2. `tests/unit/backends/test_quilt3_backend_packages.py` - Test structure reference
3. `src/quilt_mcp/backends/platform_backend.py` - Implementation to test

---

## Test Organization Patterns

### Helper Functions (Reuse from Core Tests)

```python
def _push_jwt_context(claims=None):
    """Create runtime context with JWT auth."""
    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="test-token",
        claims=claims or {
            "catalog_token": "test-catalog-token",
            "catalog_url": "https://example.quiltdata.com",
            "registry_url": "https://registry.quiltdata.com",
        },
    )
    return push_runtime_context(environment=get_runtime_environment(), auth=auth_state)

def _make_backend(monkeypatch, claims=None):
    """Create Platform_Backend instance with mocked environment."""
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context(claims)
    try:
        from quilt_mcp.backends.platform_backend import Platform_Backend
        return Platform_Backend()
    finally:
        reset_runtime_context(token)
```

### Mock Pattern for GraphQL Responses

```python
def test_operation(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            # Mock GraphQL response structure
        }
    }
    result = backend.method_under_test()
    # Assertions
```

### Mock Pattern for Write Operations

```python
@contextmanager
def _noop_creds():
    yield

backend._with_aws_credentials = _noop_creds

class FakePackage:
    def __init__(self):
        self.meta = {}
    def push(self, *args, **kwargs):
        return "top-hash"

fake_quilt3 = SimpleNamespace(Package=FakePackage)
monkeypatch.setitem(sys.modules, "quilt3", fake_quilt3)
```

---

## Test Metrics

### Current Coverage
- **Test Files:** 1
- **Test Count:** 18 tests
- **Methods Tested:** ~8 of 18 public methods
- **Coverage Estimate:** ~45%

### Target Coverage
- **Test Files:** 4
- **Test Count:** ~60 tests
- **Methods Tested:** 17 of 18 public methods (excluding admin stub)
- **Coverage Estimate:** ~95%

---

## Verification Plan

### 1. Run New Tests

```bash
# Run all Platform backend tests
uv run pytest tests/unit/backends/test_platform_backend*.py -v

# Run specific domain tests
uv run pytest tests/unit/backends/test_platform_backend_packages.py -v
uv run pytest tests/unit/backends/test_platform_backend_content.py -v
uv run pytest tests/unit/backends/test_platform_backend_buckets.py -v
uv run pytest tests/unit/backends/test_platform_backend_admin.py -v
```

### 2. Coverage Analysis

```bash
# Generate coverage report for Platform backend
uv run pytest tests/unit/backends/test_platform_backend*.py \
  --cov=src/quilt_mcp/backends/platform_backend \
  --cov-report=html \
  --cov-report=term

# Target: >90% line coverage
```

### 3. Integration with CI

```bash
# Run full unit test suite
make test

# Run all tests including integration
make test-all

# Verify no regressions
uv run pytest tests/ -v
```

### 4. Validate Test Organization

- Verify each test file has clear docstrings
- Check that tests are grouped by operation type
- Ensure test names follow `test_<method>_<scenario>` pattern
- Validate that mocks are properly isolated between tests

---

## Success Criteria

1. ✅ All 4 new test files created and passing
2. ✅ ~60 total tests covering Platform_Backend operations
3. ✅ >90% line coverage for `platform_backend.py`
4. ✅ Test structure mirrors Quilt3_Backend organization
5. ✅ All tests pass in isolation and in suite
6. ✅ No regressions in existing tests
7. ✅ Clear documentation of test patterns and helpers

---

## Implementation Notes

### Why Separate Test Files?

Despite Platform_Backend being monolithic (1 file vs Quilt3_Backend's 7 files), separating tests by domain provides:

1. **Maintainability** - Easier to locate and update tests for specific operations
2. **Parallel Development** - Multiple developers can work on different test domains
3. **Consistency** - Aligns with Quilt3_Backend test structure for developer familiarity
4. **Organization** - Groups related tests together (packages, content, buckets, admin)
5. **Scalability** - If Platform_Backend is refactored into mixins, tests are already organized

### Test Isolation Strategy

- Each test file imports and uses `_make_backend()` helper
- Mock `execute_graphql_query()` for all GraphQL operations
- Mock `quilt3` module for package write operations
- Mock AWS credential context manager for S3 operations
- Use `monkeypatch` for environment variables
- Reset runtime context after each test

### GraphQL Response Mocking

Platform_Backend tests will mock GraphQL responses at the `execute_graphql_query()` level rather than mocking HTTP requests. This:

- Tests the transformation logic from GraphQL → domain objects
- Avoids brittleness from HTTP request format changes
- Focuses on Platform_Backend's responsibilities
- Simplifies test setup

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Test duplication with core tests | Low | Review existing `test_platform_backend_core.py`, move tests to appropriate domain files |
| GraphQL schema changes | Medium | Use consistent mock response structures; document GraphQL schema dependencies |
| Mock complexity for write operations | Medium | Reuse existing `FakePackage` pattern from core tests; create shared fixtures |
| Runtime context management | High | Use consistent `_push_jwt_context()` and `reset_runtime_context()` patterns |

---

## Timeline Estimate

- **Phase 1** (Packages): ~3-4 hours (largest file, most complex operations)
- **Phase 2** (Content): ~1-2 hours (simpler operations, fewer methods)
- **Phase 3** (Buckets): ~1-2 hours (straightforward bucket listing)
- **Phase 4** (Admin): ~0.5 hours (single stub test)
- **Verification & Polish**: ~1 hour (coverage analysis, CI integration)

**Total: ~7-10 hours of development time**

---

## Future Enhancements

1. **GraphQL Schema Validation** - Add tests that validate GraphQL query structure against schema
2. **Performance Tests** - Add benchmarks for pagination and large result sets
3. **Error Handling** - Add comprehensive GraphQL error scenario tests
4. **Admin Operations** - Implement real admin operations if Platform GraphQL API supports them
5. **Integration Tests** - Add E2E tests that hit real GraphQL endpoints (in `tests/integration/`)
