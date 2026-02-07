# A18-04: Fix Tabulator MCP Tools - Add Catalog Config to Auth_Status

**Status**: Draft
**Created**: 2026-02-06
**Priority**: High
**Scope**: Fix tabulator tool failures in MCP test suite

## Problem Statement

Tabulator MCP tools (`tabulator_bucket_query`, `tabulator_list_buckets`, `tabulator_query_execute`) fail with:

```
Error: tabulator_data_catalog not configured. This requires a Tabulator-enabled catalog.
```

However, the standalone test script `scripts/tests/test_tabulator.py` successfully executes all 6 tabulator lifecycle steps (create, list, get, rename, query, delete).

## Root Cause Analysis

### Why Standalone Test Works

**File**: `scripts/tests/test_tabulator.py:530`

```
backend = QuiltOpsFactory.create()
result = backend.list_tabulator_tables(bucket)
```

- Creates backend directly via `QuiltOpsFactory`
- Calls backend methods that internally fetch catalog config
- Methods extract `tabulator_data_catalog` from config on-demand
- Location: `src/quilt_mcp/ops/quilt_ops.py:962`

### Why MCP Tools Fail

**Chain of failure:**

1. **MCP Tool Entry Point** - `src/quilt_mcp/services/athena_read_service.py:723-728`
   - Tools check `info.get("tabulator_data_catalog")` upfront
   - Fail immediately if `None`

2. **Auth Metadata Fetching** - `src/quilt_mcp/services/auth_metadata.py:57`
   - Uses `getattr(auth_status, 'tabulator_data_catalog', None)`
   - Expects field to exist on `Auth_Status` object

3. **Missing Fields** - `src/quilt_mcp/domain/auth_status.py:25-28`
   - `Auth_Status` dataclass only has 4 fields:
     - `is_authenticated: bool`
     - `logged_in_url: Optional[str]`
     - `catalog_name: Optional[str]`
     - `registry_url: Optional[str]`
   - **Missing**: `region: Optional[str]`
   - **Missing**: `tabulator_data_catalog: Optional[str]`

4. **Backend Creation** - `src/quilt_mcp/backends/quilt3_backend_session.py:73`
   - Creates `Auth_Status(...)` with only 4 fields
   - Never fetches or populates catalog configuration

5. **Result**: `getattr()` returns `None` → Tools fail

### Architecture Gap

```
Standalone Test Path (WORKS):
  QuiltOpsFactory.create()
    └─> Backend method call
        └─> Fetch catalog config on-demand
            └─> Extract tabulator_data_catalog
                └─> Use in operation

MCP Tool Path (FAILS):
  MCP tool invoked
    └─> Check auth_metadata.get("tabulator_data_catalog")
        └─> getattr(auth_status, "tabulator_data_catalog", None)
            └─> Auth_Status lacks field → None
                └─> ERROR: "tabulator_data_catalog not configured"
```

## Design Solution

### Core Principle

**Auth_Status should be a complete snapshot of catalog configuration, not just authentication state.**

The `Auth_Status` dataclass represents what the user is authenticated *to* - this includes catalog infrastructure details like region and tabulator configuration.

### Design Changes

#### 1. Expand Auth_Status Domain Model

**File**: `src/quilt_mcp/domain/auth_status.py`

Add fields:
- `region: Optional[str]` - AWS region of the catalog
- `tabulator_data_catalog: Optional[str]` - Athena data catalog for tabulator

**Reasoning**:
- These are catalog configuration properties, not session state
- They're stable per catalog (don't change during session)
- They're required for tabulator operations
- They logically belong with `registry_url` as catalog metadata

#### 2. Implement Template Method in QuiltOps

**File**: `src/quilt_mcp/ops/quilt_ops.py:649`

**Current State**: `get_auth_status()` is marked `@abstractmethod` - each backend implements separately

**New Design**: Convert to **Template Method** pattern (like `search_packages()`)

```python
# QuiltOps base class
def get_auth_status(self) -> Auth_Status:
    """Get authentication status with catalog config enrichment (Template Method).

    Workflow:
        1. Get basic auth status (backend primitive)
        2. If authenticated, enrich with catalog config
        3. Return fully-populated Auth_Status
    """
    # STEP 1: Get basic auth from backend
    basic_auth = self._backend_get_auth_status()

    # STEP 2: Enrich with catalog config if authenticated
    if basic_auth.is_authenticated and basic_auth.logged_in_url:
        try:
            catalog_config = self.get_catalog_config(basic_auth.logged_in_url)
            # Return enriched Auth_Status with catalog fields
            return Auth_Status(
                is_authenticated=basic_auth.is_authenticated,
                logged_in_url=basic_auth.logged_in_url,
                catalog_name=basic_auth.catalog_name,
                registry_url=basic_auth.registry_url,
                region=catalog_config.region,
                tabulator_data_catalog=catalog_config.tabulator_data_catalog,
            )
        except Exception as e:
            # Degraded mode: return basic auth without catalog config
            logger.warning(f"Failed to fetch catalog config: {e}")
            return basic_auth

    # STEP 3: Return basic auth (unauthenticated or no catalog URL)
    return basic_auth

@abstractmethod
def _backend_get_auth_status(self) -> Auth_Status:
    """Backend primitive: Get basic authentication status.

    Returns Auth_Status with basic fields (no catalog config enrichment).
    Backends implement this without catalog config logic.
    """
    pass
```

**Why Template Method?**
- **DRY**: Catalog config enrichment logic in ONE place (QuiltOps)
- **Consistency**: Both backends automatically get enrichment
- **Pattern**: Matches existing QuiltOps architecture (see `search_packages()`)
- **Testability**: Test enrichment once in QuiltOps tests
- **Maintainability**: Future backend implementations get it for free

#### 3. Refactor Backend Implementations

**Files**:
- `src/quilt_mcp/backends/quilt3_backend_session.py:73`
- `src/quilt_mcp/backends/platform_backend.py:155`

**Changes**:
- Rename `get_auth_status()` → `_backend_get_auth_status()`
- Return Auth_Status with ONLY basic fields (4 original fields)
- Remove any catalog config fetching logic (if exists)
- QuiltOps base class handles enrichment

**Result**: Simpler backend code, shared enrichment logic

#### 4. Update Auth Metadata Service

**File**: `src/quilt_mcp/services/auth_metadata.py:57`

Current code already uses `getattr()`:
```python
"tabulator_data_catalog": getattr(auth_status, 'tabulator_data_catalog', None),
```

This will automatically work once `Auth_Status` has the field.

#### 4. Graceful Degradation

**Philosophy**: Tabulator tools should work if catalog config is available, but not block other MCP operations if it's not.

**Implementation**:
- If `tabulator_data_catalog` is `None`, tools return clear error message
- Non-tabulator tools continue to work normally
- Error message should suggest checking catalog configuration

## Implementation Tasks

### Phase 1: Domain Model Update

**Task 1.1**: Update Auth_Status dataclass
- File: `src/quilt_mcp/domain/auth_status.py`
- Add `region: Optional[str]` field
- Add `tabulator_data_catalog: Optional[str]` field
- Update docstring to document new fields
- Keep `frozen=True` for immutability

**Task 1.2**: Update type hints and validation
- Update `__post_init__` if needed for validation
- Update `__hash__` to include new fields
- Ensure backward compatibility (fields are optional)

### Phase 2: QuiltOps Template Method Implementation

**Task 2.1**: Implement Template Method in QuiltOps
- File: `src/quilt_mcp/ops/quilt_ops.py:649`
- Convert `get_auth_status()` from `@abstractmethod` to concrete Template Method
- Implement 3-step workflow:
  1. Call `_backend_get_auth_status()` for basic auth
  2. If authenticated, enrich with catalog config via `get_catalog_config()`
  3. Return enriched `Auth_Status` or degraded basic auth
- Add error handling: catch config fetch failures, log warning, return basic auth
- Add abstract method: `_backend_get_auth_status() -> Auth_Status`

**Task 2.2**: Refactor Quilt3 Backend
- File: `src/quilt_mcp/backends/quilt3_backend_session.py:73`
- Rename: `get_auth_status()` → `_backend_get_auth_status()`
- Simplify: Return `Auth_Status` with ONLY 4 basic fields (no catalog config)
- Remove: Any catalog config fetching logic (QuiltOps handles it now)
- Result: ~20 lines simpler, focused on quilt3-specific auth only

**Task 2.3**: Refactor Platform Backend
- File: `src/quilt_mcp/backends/platform_backend.py:155`
- Same refactoring as Task 2.2
- Rename: `get_auth_status()` → `_backend_get_auth_status()`
- Return only basic fields
- Ensure consistency with Quilt3 backend

**Task 2.4**: Verify Template Method Pattern
- Both backends now implement `_backend_get_auth_status()` primitive
- QuiltOps enriches with catalog config automatically
- No duplication of enrichment logic
- Pattern matches existing `search_packages()` implementation

### Phase 3: Testing

**Task 3.1**: Update Unit Tests - Auth_Status
- File: `tests/unit/domain/test_auth_status.py` (create if doesn't exist)
- Test creation with new fields
- Test creation with fields as `None`
- Test immutability (frozen dataclass)
- Test hash includes new fields
- Test backward compatibility

**Task 3.2**: Update Unit Tests - Backend Auth Status
- Files:
  - `tests/unit/backends/test_quilt3_backend_session.py`
  - `tests/unit/backends/test_platform_backend_core.py`
- Mock `get_catalog_config()` to return test config
- Assert `Auth_Status` includes `region` and `tabulator_data_catalog`
- Test degraded mode (config fetch fails)
- Test non-tabulator catalog (field is `None`)

**Task 3.3**: Update Functional Tests
- File: `tests/func/test_backend_status.py`
- Update expected output to include new fields
- Lines to update: 144, 175 (currently have `"tabulator_data_catalog": None`)
- Mock catalog config for test scenarios

**Task 3.4**: Update Integration Tests
- File: `tests/e2e/test_tabulator_integration.py` (if exists)
- Verify real tabulator tools work end-to-end
- Test against actual catalog with tabulator enabled

**Task 3.5**: Verify MCP Test Suite
- Run: `uv run python scripts/mcp-test.py`
- Verify tabulator tools now pass:
  - `tabulator_bucket_query`
  - `tabulator_list_buckets`
  - `tabulator_query_execute`
- Check that other tools still pass (no regression)

### Phase 4: Documentation

**Task 4.1**: Update Auth_Status Documentation
- File: `src/quilt_mcp/domain/auth_status.py`
- Add detailed field descriptions for `region` and `tabulator_data_catalog`
- Explain when fields are `None` vs populated
- Add usage examples in docstring

**Task 4.2**: Update CHANGELOG
- Document new Auth_Status fields
- Explain impact on tabulator tools
- Note backward compatibility

**Task 4.3**: Update Architecture Documentation
- File: `.kiro/specs/quilt-service-to-quilt-ops-migration/design.md` (if relevant)
- Document that Auth_Status includes catalog config
- Explain the lazy-loading pattern (fetch on auth check)

## Validation Checklist

### Functional Validation

- [ ] Standalone test still works: `uv run python scripts/tests/test_tabulator.py`
- [ ] MCP tabulator tools pass: `uv run python scripts/mcp-test.py`
- [ ] Non-tabulator MCP tools still pass (no regression)
- [ ] Auth status returns region and tabulator_data_catalog when authenticated
- [ ] Auth status handles missing catalog config gracefully

### Technical Validation

- [ ] All unit tests pass: `make test`
- [ ] All functional tests pass: `make test-func`
- [ ] Type checking passes: `make lint`
- [ ] No performance regression (auth check < 500ms)

### Edge Case Validation

- [ ] Unauthenticated user: fields are `None`, tools fail with clear message
- [ ] Non-tabulator catalog: `tabulator_data_catalog` is `None`, tools fail gracefully
- [ ] Catalog config fetch fails: log warning, fields are `None`, tools fail gracefully
- [ ] Multiple catalogs: each gets correct config

## Migration Notes

### Backward Compatibility

- **Safe**: New fields are `Optional[str]`, default to `None`
- **Safe**: Existing code using `getattr(..., None)` continues to work
- **Safe**: Frozen dataclass prevents accidental field modification

### Breaking Changes

**None** - This is a pure addition, no breaking changes.

### Rollout Strategy

1. Deploy with new Auth_Status fields
2. Monitor logs for catalog config fetch errors
3. If errors exceed threshold, investigate catalog configuration
4. Collect metrics on tabulator tool usage

## Future Enhancements

### Potential Optimizations

1. **Caching**: Cache catalog config for session duration
   - Benefit: Reduce network calls
   - Complexity: Cache invalidation strategy

2. **Lazy Loading**: Only fetch config when tabulator tools are used
   - Benefit: Avoid unnecessary network calls
   - Complexity: More complex code paths

3. **Config Service**: Centralized catalog config management
   - Benefit: Single source of truth
   - Complexity: New service layer

### Related Work

- **A15-platform**: GraphQL-based catalog config fetching
- **A17-test-cleanup**: Comprehensive testing strategy
- **A18-jwt-testing**: Authentication testing framework

## References

### Code Locations

- Auth_Status: `src/quilt_mcp/domain/auth_status.py`
- Quilt3 Backend Auth: `src/quilt_mcp/backends/quilt3_backend_session.py:73`
- Platform Backend Auth: `src/quilt_mcp/backends/platform_backend.py:155`
- Auth Metadata Service: `src/quilt_mcp/services/auth_metadata.py:57`
- Athena Read Service: `src/quilt_mcp/services/athena_read_service.py:723-728`
- Catalog Config Transform: `src/quilt_mcp/ops/quilt_ops.py:917-975`

### Test Files

- Standalone Tabulator Test: `scripts/tests/test_tabulator.py`
- MCP Test Suite: `scripts/mcp-test.py`
- MCP Test Config: `scripts/tests/mcp-test.yaml:1705-1752`
- Backend Status Tests: `tests/func/test_backend_status.py:144,175`

## Decision Log

### Why Add to Auth_Status Instead of Separate Service?

**Decision**: Add fields to Auth_Status

**Rationale**:

1. Catalog config is authentication context - describes "what you're authenticated to"
2. Fields are stable per catalog (not session state)
3. Simplifies tool implementation (single object)
4. Consistent with existing `registry_url` field pattern
5. Minimal performance impact (one-time fetch per session)

**Alternatives Considered**:

- Separate CatalogConfigService: More complex, requires coordination
- Lazy loading in tools: Duplicated logic, inconsistent behavior
- Environment variables: Not dynamic, harder to manage

### Why Template Method in QuiltOps vs Backend Implementation?

**Decision**: Implement enrichment as Template Method in QuiltOps base class

**Rationale**:

1. **DRY Principle**: Enrichment logic written once, not duplicated in 2+ backends
2. **Pattern Consistency**: Matches existing QuiltOps architecture (see `search_packages()`)
3. **Automatic Propagation**: Future backends (HTTP, mock, etc.) get enrichment for free
4. **Testability**: Test enrichment logic once in QuiltOps, not per backend
5. **Maintainability**: Changes to enrichment logic update all backends instantly
6. **Separation of Concerns**: Backends handle auth primitives, QuiltOps handles composition

**Alternatives Considered**:

- Duplicate in both backends: Violates DRY, inconsistent behavior, harder to maintain
- Helper function: Better than duplication, but Template Method is clearer pattern
- Mixin class: Possible, but QuiltOps already uses Template Method pattern

### Why Fetch During Auth Check vs Lazy Loading?

**Decision**: Fetch during `get_auth_status()` Template Method

**Rationale**:

1. Auth status check is already infrequent (startup + status checks)
2. Ensures config is available before tools need it
3. Simpler error handling (fail early with degraded mode)
4. Consistent state throughout session
5. Minimal performance impact (catalog config is tiny JSON)
6. Template Method provides centralized error handling

**Alternatives Considered**:

- Lazy load in each tool: Duplicated code, inconsistent caching
- Background fetch: Complex, potential race conditions
- Manual configuration: Poor UX, error-prone

## Success Criteria

### Primary Goals

1. ✅ All tabulator MCP tools pass in test suite
2. ✅ No regression in existing MCP tools
3. ✅ Standalone tabulator test continues to work
4. ✅ All unit and functional tests pass

### Secondary Goals

1. ✅ Auth status includes catalog metadata (region, tabulator_data_catalog)
2. ✅ Graceful degradation when catalog config unavailable
3. ✅ Clear error messages for unsupported catalogs
4. ✅ Performance impact < 100ms per auth check

### Stretch Goals

1. ⭕ Implement caching for catalog config
2. ⭕ Add metrics for tabulator tool usage
3. ⭕ Create catalog config troubleshooting guide

---

**End of Specification**
