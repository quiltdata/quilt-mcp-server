# Migration: All MCP Tools → QuiltOps

## Goal

Complete migration of all MCP tools from QuiltService to QuiltOps exclusively, then delete QuiltService.

## Status

**✅ Already Migrated:**

- `packages_list()` tool → Uses `quilt_ops.search_packages()`
- `package_browse()` tool → Uses `quilt_ops.browse_content()`

**❌ Needs Migration:**

- `package_create()` tool → Uses `quilt_service.create_package_revision()`
- `package_create_from_s3()` tool → Uses `quilt_service.create_package_revision()`
- `package_update()` tool → Uses `quilt_service.browse_package()`
- `package_diff()` tool → Uses `quilt_service.browse_package()`
- `search._get_graphql_endpoint()` helper → Uses `quilt_service` session methods
- `stack_buckets._get_stack_buckets_via_graphql()` helper → Uses `quilt_service` session methods

## Problem

QuiltOps interface missing 2 critical operations that tools need:

1. **Package diffing** - `package_diff()` needs to compare two package versions
2. **Package updates** - `package_update()` needs to add files to existing packages

Additionally, GraphQL helpers use QuiltService session methods that should be replaced with `QuiltOps.execute_graphql_query()`.

## Work Required

### 1. Extend QuiltOps Interface

Add 2 new abstract methods to QuiltOps:

**`diff_packages()` method:**

```python
def diff_packages(
    package1_name: str,
    package2_name: str,
    registry: str,
    package1_hash: Optional[str] = None,
    package2_hash: Optional[str] = None,
) -> Dict[str, List[str]]
```

Returns dict with keys: `added`, `deleted`, `modified` (lists of file paths).

**`update_package_revision()` method:**

```python
def update_package_revision(
    package_name: str,
    s3_uris: List[str],
    registry: str,
    metadata: Optional[Dict] = None,
    message: str = "Package updated via QuiltOps",
    auto_organize: bool = False,
    copy: str = "none",
) -> Package_Creation_Result
```

Loads existing package, adds files, pushes update.

### 2. Implement in Quilt3 Backend

Add implementations to `Quilt3_Backend` (quilt3_backend_packages.py):

**`diff_packages()`:**

- Browse both packages with `quilt3.Package.browse()`
- Call `pkg1.diff(pkg2)`
- Transform result to domain dict

**`update_package_revision()`:**

- Browse existing package
- Add S3 URIs using `pkg.set()` or `pkg.set_dir()`
- Handle auto_organize for folder structure
- Call `pkg.push()` with selector_fn for copy mode
- Return Package_Creation_Result

### 3. Update Tests

Add test coverage in `tests/unit/backends/test_quilt3_backend_packages.py`:

- `test_diff_packages_basic`
- `test_diff_packages_with_hashes`
- `test_update_package_revision_basic`
- `test_update_package_revision_with_metadata`
- `test_update_package_revision_auto_organize`

### 4. Migrate Package Tools

Replace QuiltService with QuiltOpsFactory in packages.py:

**`package_create()` (line 1103):**

- Already uses `quilt_service.create_package_revision()`
- Change to `quilt_ops = QuiltOpsFactory.create()`
- Call `quilt_ops.create_package_revision()`
- Update result handling

**`package_create_from_s3()` (line 1661):**

- Same changes as package_create()

**`package_update()` (line 1338):**

- Replace `quilt_service.browse_package()` call
- Use `quilt_ops.update_package_revision()` directly

**`package_diff()` (line 963):**

- Replace two `quilt_service.browse_package()` calls
- Use `quilt_ops.diff_packages()` directly

### 5. Migrate GraphQL Helpers

**search.py `_get_graphql_endpoint()` (line 363):**

Replace entire function:

```python
def _get_graphql_endpoint():
    """Return QuiltOps instance or None."""
    try:
        return QuiltOpsFactory.create()
    except Exception:
        return None
```

Update `search_graphql()` to use `quilt_ops.execute_graphql_query()` instead of session.post().

**stack_buckets.py `_get_stack_buckets_via_graphql()` (line 42):**

Replace QuiltService session usage with:

```python
quilt_ops = QuiltOpsFactory.create()
result = quilt_ops.execute_graphql_query(query=BUCKET_CONFIGS_QUERY)
```

### 6. Delete QuiltService

After all migrations complete:

- Verify no remaining imports: `grep -r "from.*quilt_service import" src/`
- Verify no usage: `grep -r "quilt_service\." src/`
- Delete `src/quilt_mcp/services/quilt_service.py`
- Delete `tests/unit/test_quilt_service.py`

## Files to Change

- [src/quilt_mcp/ops/quilt_ops.py](src/quilt_mcp/ops/quilt_ops.py) - Add abstract methods
- [src/quilt_mcp/backends/quilt3_backend_packages.py](src/quilt_mcp/backends/quilt3_backend_packages.py) - Implement methods
- [src/quilt_mcp/tools/packages.py:963](src/quilt_mcp/tools/packages.py#L963) - Migrate package_diff
- [src/quilt_mcp/tools/packages.py:1103](src/quilt_mcp/tools/packages.py#L1103) - Migrate package_create
- [src/quilt_mcp/tools/packages.py:1338](src/quilt_mcp/tools/packages.py#L1338) - Migrate package_update
- [src/quilt_mcp/tools/packages.py:1661](src/quilt_mcp/tools/packages.py#L1661) - Migrate package_create_from_s3
- [src/quilt_mcp/tools/search.py:363](src/quilt_mcp/tools/search.py#L363) - Migrate _get_graphql_endpoint
- [src/quilt_mcp/tools/stack_buckets.py:42](src/quilt_mcp/tools/stack_buckets.py#L42) - Migrate _get_stack_buckets_via_graphql
- [tests/unit/backends/test_quilt3_backend_packages.py](tests/unit/backends/test_quilt3_backend_packages.py) - Add tests

## Files to Delete

- [src/quilt_mcp/services/quilt_service.py](src/quilt_mcp/services/quilt_service.py)
- [tests/unit/test_quilt_service.py](tests/unit/test_quilt_service.py)

## Success Criteria

- QuiltOps has diff_packages() and update_package_revision()
- All 6 tools/helpers use QuiltOpsFactory exclusively
- No QuiltService imports remain in src/
- QuiltService.py deleted
- All tests pass: `make test-all`
- Linting passes: `make lint`
