# Tool Migration Categories and Detailed Checklists

## Category 1: Package Management Tools (HIGH PRIORITY)

### File: `src/quilt_mcp/tools/packages.py`

**Impact:** Critical - Core package operations used by most workflows

**Current QuiltService Usage:**

- `quilt_service.list_packages(registry)` - Package listing
- `quilt_service.browse_package(name, registry, top_hash)` - Package browsing  
- `quilt_service.create_package_revision(...)` - Package creation

**Migration Plan:**

1. **packages_list function:**
   - Replace `quilt_service.list_packages()` with `QuiltOps.search_packages(query="", registry)`
   - Transform results to `Package_Info` objects
   - Use `dataclasses.asdict()` for MCP response formatting

2. **package_browse function:**
   - Replace `quilt_service.browse_package()` with `QuiltOps.browse_content(package_name, registry, path="")`
   - Transform results to `Content_Info` objects
   - Maintain directory/file type detection

3. **package_diff function:**
   - Use `QuiltOps.browse_content()` for both packages
   - Compare `Content_Info` objects instead of raw quilt3 objects

4. **SPECIAL CASE - Package Creation:**
   - `create_package_revision()` has no QuiltOps equivalent
   - Options: Add to QuiltOps interface OR keep as direct quilt3 usage
   - Decision needed before migration

**Testing Requirements:**

- Integration tests for all package operations
- Response format compatibility tests
- Error handling consistency tests

---

## Category 2: Authentication & Session Tools (MEDIUM PRIORITY)

### Files: `src/quilt_mcp/tools/search.py`, `src/quilt_mcp/tools/stack_buckets.py`

**Impact:** Medium - GraphQL functionality, not core domain operations

**Current QuiltService Usage:**

- `quilt_service.has_session_support()` - Session validation
- `quilt_service.get_session()` - GraphQL access
- `quilt_service.get_registry_url()` - GraphQL endpoint construction

**Migration Plan:**

1. **Move authentication logic to QuiltOpsFactory:**
   - Replace session checks with factory-based authentication
   - Use factory error handling for authentication failures

2. **Keep GraphQL functionality separate:**
   - GraphQL operations are not part of QuiltOps domain
   - Maintain direct session access for GraphQL endpoints
   - Use QuiltOpsFactory for authentication validation only

**Testing Requirements:**

- Authentication flow tests
- GraphQL endpoint construction tests
- Error message clarity tests

---

## Category 3: Bucket Operations Tools (LOW PRIORITY)

### File: `src/quilt_mcp/tools/buckets.py`

**Impact:** Low - Only imports QuiltService, no actual usage

**Current QuiltService Usage:**

- Import statement only, no method calls

**Migration Plan:**

1. **Remove unused import:**
   - Clean up import statement
   - No functional changes needed

**Testing Requirements:**

- Verify no regression in bucket operations
- Confirm import removal doesn't break anything

---

## Category 4: Catalog & Configuration Tools (LOW PRIORITY)

### File: `src/quilt_mcp/tools/catalog.py`

**Impact:** Low - Documentation reference only

**Current QuiltService Usage:**

- Documentation reference to `QuiltService.set_config`

**Migration Plan:**

1. **Update documentation:**
   - Update references to use QuiltOps patterns
   - No functional code changes needed

**Testing Requirements:**

- Documentation accuracy verification

---

## Migration Sequence Priority

### Phase 1: Core Package Operations

1. `packages.py` - packages_list function
2. `packages.py` - package_browse function  
3. `packages.py` - package_diff function

### Phase 2: Authentication Integration

1. `search.py` - Session management
2. `stack_buckets.py` - Session management

### Phase 3: Cleanup

1. `buckets.py` - Remove unused imports
2. `catalog.py` - Update documentation

---

## Domain Object Mapping Reference

### Package_Info Mapping

```python
# From quilt3.Package metadata
Package_Info(
    name=package_name,
    description=pkg.meta.get('description'),
    tags=pkg.meta.get('tags', []),
    modified_date=pkg.modified.isoformat(),
    registry=registry,
    bucket=extract_bucket_from_registry(registry),
    top_hash=pkg.top_hash
)
```

### Content_Info Mapping

```python
# From quilt3 package browsing
Content_Info(
    path=logical_key,
    size=entry.size if hasattr(entry, 'size') else None,
    type='file' if is_file else 'directory',
    modified_date=entry.modified.isoformat() if hasattr(entry, 'modified') else None,
    download_url=None  # Generated separately via get_content_url
)
```

### Response Format Compatibility

- All responses must use `dataclasses.asdict()` for MCP compatibility
- Maintain existing response structure for backward compatibility
- Preserve error message formats and clarity
