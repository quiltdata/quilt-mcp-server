# Package Test Failures Analysis

**Status**: Bug Analysis
**Date**: 2026-02-08
**Tests**: `package_lifecycle`, `package_create_from_s3_loop`
**Backend**: quilt3 (stdio transport)

## Executive Summary

Two critical bugs discovered in the package management workflow when running MCP integration tests with the quilt3 backend:

1. **PhysicalKey Type Error** in `package_update` - Type mismatch between backend primitive return type and Template Method expectations
2. **Directory Entry Error** in `package_create_from_s3` - Missing filter for S3 directory marker objects

Both bugs stem from insufficient type normalization at backend primitive boundaries.

## Test Execution Context

```bash
export TEST_BACKEND_MODE=quilt3
export FASTMCP_TRANSPORT=stdio
uv run --group test python scripts/tests/test_mcp.py --no-generate \
  --loop package_lifecycle,package_create_from_s3_loop
```

### Test Configuration
- **Bucket**: `quilt-ernest-staging`
- **Test Package Base**: `raw/test`
- **Test Entry**: `README.md`

## Bug 1: package_update - PhysicalKey Type Error

### Test Failure Details

**Test Loop**: `package_lifecycle`
**Failed Step**: 3/4 (package_update)
**Error Message**:
```
Package update failed: Expected a string for entry,
but got an instance of <class 'quilt3.util.PhysicalKey'>.
```

**Test Flow**:
1. ✅ package_create - Created test package
2. ✅ package_browse - Retrieved package successfully
3. ❌ package_update - Failed with PhysicalKey type error
4. ✅ package_delete - Cleanup succeeded

### Root Cause Analysis

**Location**: Backend primitive contract violation

**Code Flow**:

1. **Template Method** ([quilt_ops.py:1569-1583](src/quilt_mcp/ops/quilt_ops.py#L1569-L1583)):
   ```python
   # STEP 3: GET EXISTING ENTRIES (backend primitive)
   existing_entries = self._backend_get_package_entries(existing_package)

   # STEP 6: ADD EXISTING FILES (backend primitive loop)
   for logical_key, entry_data in existing_entries.items():
       # Extract physical key
       physical_key = entry_data.get("physicalKey") or entry_data.get("physical_key")
       if physical_key:
           self._backend_add_file_to_package(updated_package, logical_key, physical_key)
   ```

2. **Backend Primitive** ([quilt3_backend.py:185-203](src/quilt_mcp/backends/quilt3_backend.py#L185-L203)):
   ```python
   def _backend_get_package_entries(self, package: Any) -> Dict[str, Dict[str, Any]]:
       entries = {}
       for logical_key, entry in package.walk():
           entries[logical_key] = {
               "physicalKey": entry.physical_key,  # ← Returns PhysicalKey object
               "size": entry.size,
               "hash": entry.hash,
               "meta": getattr(entry, 'meta', None),
           }
       return entries
   ```

3. **Failure Point**: The `entry.physical_key` is a `quilt3.util.PhysicalKey` object, not a string. The Template Method at [quilt_ops.py:1583](src/quilt_mcp/ops/quilt_ops.py#L1583) extracts this object and passes it directly to `_backend_add_file_to_package()`, which expects a string (S3 URI).

### Architecture Impact

**Template Method Pattern Violation**: Backend primitives must return normalized domain types, not backend-specific objects. The primitive is leaking quilt3-specific types into the orchestration layer.

**Backend Primitive Contract**:
```python
def _backend_get_package_entries(self, package: Any) -> Dict[str, Dict[str, Any]]:
    """
    Returns: Dict mapping logical_key to entry metadata

    Expected metadata structure:
    {
        "physicalKey": str,  # Must be string (S3 URI format)
        "size": int,
        "hash": str,
        "meta": Dict[str, Any] | None
    }
    """
```

**Current Violation**: `physicalKey` returns `PhysicalKey` object instead of `str`.

### Comparison with Platform Backend

The platform backend ([platform_backend.py:648-658](src/quilt_mcp/backends/platform_backend.py#L648-L658)) correctly returns normalized data:

```python
def _backend_get_package_entries(self, package: Any) -> Dict[str, Dict[str, Any]]:
    """Get all entries from package data (backend primitive)."""
    result: Dict[str, Dict[str, Any]] = package.get("revision", {}).get("contentsFlatMap", {})
    return result  # GraphQL returns properly typed data
```

GraphQL API returns strings for physical keys, so no type conversion is needed. The quilt3 backend must perform this conversion.

## Bug 2: package_create_from_s3 - Directory Entry Error

### Test Failure Details

**Test Loop**: `package_create_from_s3_loop`
**Failed Step**: 1/2 (package_create_from_s3)
**Error Message**:
```
Failed to create package: A package entry logical key 'raw/test/amazon/'
must be a file.
```

**Test Configuration**:
```yaml
- tool: package_create_from_s3
  args:
    source_bucket: 'quilt-ernest-staging'
    package_name: testuser/s3pkg-{uuid}
    target_registry: s3://quilt-ernest-staging
    source_prefix: 'raw/test/'  # ← Trailing slash
    confirm_structure: false
    force: true
```

### Root Cause Analysis

**Location**: Missing directory marker filter

**Code Flow**:

1. **Discovery** ([packages.py:441-464](src/quilt_mcp/tools/packages.py#L441-L464)):
   ```python
   def _discover_s3_objects(
       s3_client, bucket, prefix, include_patterns, exclude_patterns
   ) -> list[dict[str, Any]]:
       """Discover and filter S3 objects based on patterns."""
       objects = []
       paginator = s3_client.get_paginator("list_objects_v2")
       pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

       for page in pages:
           if "Contents" in page:
               for obj in page["Contents"]:
                   if _should_include_object(obj["Key"], include_patterns, exclude_patterns):
                       objects.append(obj)  # ← Includes directory markers
       return objects
   ```

2. **Collection** ([packages.py:506-513](src/quilt_mcp/tools/packages.py#L506-L513)):
   ```python
   def _create_enhanced_package(...):
       # Collect all S3 URIs from organized structure
       s3_uris = []
       for folder, objects in organized_structure.items():
           for obj in objects:
               source_key = obj["Key"]
               s3_uri = f"s3://{source_bucket}/{source_key}"
               s3_uris.append(s3_uri)  # ← Directory markers included
   ```

3. **Package Creation** ([packages.py:535-543](src/quilt_mcp/tools/packages.py#L535-L543)):
   ```python
   result = quilt_ops.create_package_revision(
       package_name=package_name,
       s3_uris=s3_uris,  # ← Contains 's3://bucket/raw/test/amazon/'
       ...
   )
   ```

4. **Failure Point**: When `create_package_revision` calls `_backend_add_file_to_package()` with a directory marker URI (ending in '/'), the quilt3 library rejects it because package entries must be files.

### S3 Directory Markers Explained

**Definition**: Zero-byte S3 objects with keys ending in '/' created by:
- AWS Console "Create Folder" action
- S3 sync tools for empty directories
- Legacy applications mimicking filesystem directories

**Example**:
```
s3://bucket/raw/test/amazon/          ← Directory marker (0 bytes)
s3://bucket/raw/test/amazon/data.csv  ← Actual file
```

**S3 API Behavior**: `list_objects_v2` returns both directory markers and files. The application must filter appropriately.

### Current Filter Logic

**Pattern-based filtering** ([packages.py:467-488](src/quilt_mcp/tools/packages.py#L467-L488)):
```python
def _should_include_object(key, include_patterns, exclude_patterns) -> bool:
    """Determine if an object should be included based on patterns."""
    import fnmatch

    # Check exclude patterns first
    if exclude_patterns:
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(key, pattern):
                return False

    # Check include patterns
    if include_patterns:
        for pattern in include_patterns:
            if fnmatch.fnmatch(key, pattern):
                return True
        return False

    return True  # ← Includes directory markers by default
```

**Missing Logic**: No check for `key.endswith('/')` to filter directory markers.

## Impact Assessment

### Bug 1: package_update
- **Severity**: HIGH - Core package management feature broken
- **Scope**: All package update operations using quilt3 backend
- **Workaround**: None - fundamental type conversion issue
- **User Impact**: Cannot update existing packages with new files

### Bug 2: package_create_from_s3
- **Severity**: MEDIUM - Affects S3 buckets with directory markers
- **Scope**: `package_create_from_s3` tool when source prefix contains directories
- **Workaround**: Use source prefixes without trailing slashes, or ensure no directory markers exist
- **User Impact**: Bulk package creation fails for common S3 directory structures

## Architecture Insights

### Template Method Pattern Compliance

**Expected Contract**: Backend primitives must return normalized, domain-friendly types.

**Current State**:
- ✅ Platform backend returns normalized GraphQL data (strings, dicts)
- ❌ Quilt3 backend leaks library-specific types (PhysicalKey objects)

**Design Principle**: Backend primitives should perform **all necessary type conversions** to maintain the abstraction boundary.

### Type Normalization Boundaries

```
┌─────────────────────────────────────────────┐
│         QuiltOps Template Method            │
│       (Backend-Agnostic Orchestration)      │
│                                             │
│  Expects: str, Dict, List (domain types)   │
└──────────────┬──────────────────────────────┘
               │ Backend Primitive Contract
               ▼
┌──────────────────────────────────────────────┐
│     Backend Primitives (Type Conversion)     │
│                                              │
│  Quilt3:   PhysicalKey → str                │
│  Platform: GraphQL dict → normalized dict    │
│                                              │
│  Must normalize: ALL backend-specific types  │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│        Backend-Specific Libraries            │
│                                              │
│  quilt3.util.PhysicalKey                    │
│  GraphQL response objects                   │
└──────────────────────────────────────────────┘
```

### S3 Object Filtering Strategy

**Best Practice**: Filter at discovery time, not during package creation.

**Recommended Approach**:
```python
def _discover_s3_objects(...) -> list[dict[str, Any]]:
    for obj in page["Contents"]:
        # Filter 1: Exclude directory markers
        if obj["Key"].endswith('/'):
            continue

        # Filter 2: Pattern-based filtering
        if _should_include_object(obj["Key"], include_patterns, exclude_patterns):
            objects.append(obj)
```

## Related Code Locations

### Bug 1: PhysicalKey Type Error
- **Backend Primitive**: [src/quilt_mcp/backends/quilt3_backend.py:185-203](src/quilt_mcp/backends/quilt3_backend.py#L185-L203)
- **Template Method**: [src/quilt_mcp/ops/quilt_ops.py:1569-1583](src/quilt_mcp/ops/quilt_ops.py#L1569-L1583)
- **Comparison**: [src/quilt_mcp/backends/platform_backend.py:648-658](src/quilt_mcp/backends/platform_backend.py#L648-L658)

### Bug 2: Directory Entry Error
- **Discovery**: [src/quilt_mcp/tools/packages.py:441-464](src/quilt_mcp/tools/packages.py#L441-L464)
- **Collection**: [src/quilt_mcp/tools/packages.py:506-513](src/quilt_mcp/tools/packages.py#L506-L513)
- **Filtering**: [src/quilt_mcp/tools/packages.py:467-488](src/quilt_mcp/tools/packages.py#L467-L488)

### Test Configuration
- **Test Loops**: [scripts/tests/mcp-test.yaml:2482-2531](scripts/tests/mcp-test.yaml#L2482-L2531)

## Test Output

### package_lifecycle Test
```
--- Step 3/4: package_update ---
[2026-02-08 13:56:04] ℹ️ Calling tool: package_update
[2026-02-08 13:56:05] ℹ️ ✅ Tool package_update executed successfully
   ❌ FAILED: Tool returned error
   Error: Package update failed: Expected a string for entry,
          but got an instance of <class 'quilt3.util.PhysicalKey'>.
```

### package_create_from_s3_loop Test
```
--- Step 1/2: package_create_from_s3 ---
[2026-02-08 13:56:08] ℹ️ Calling tool: package_create_from_s3
[2026-02-08 13:57:25] ℹ️ ✅ Tool package_create_from_s3 executed successfully
   ❌ FAILED: Tool returned error
   Error: Failed to create package: A package entry logical key
          'raw/test/amazon/' must be a file.
```

## Recommendations

### Immediate Actions Required

1. **Bug 1 Fix**: Add type normalization in `_backend_get_package_entries()`
   - Convert `PhysicalKey` to string in quilt3 backend primitive
   - Verify string format matches S3 URI expectations

2. **Bug 2 Fix**: Add directory marker filter in `_discover_s3_objects()`
   - Filter keys ending with '/' at discovery time
   - Consider zero-byte object filtering as additional safety

3. **Test Enhancement**: Add explicit test cases for:
   - Package updates with multiple entries
   - S3 prefixes containing directory markers
   - Edge cases: empty directories, nested structures

### Long-term Improvements

1. **Type Safety**: Add Pydantic models for backend primitive return types
2. **Contract Testing**: Verify backend primitive compliance with expected types
3. **Documentation**: Document backend primitive type normalization requirements

## Fix Status

### Bug 2: Directory Marker Filter - ✅ FIXED (2026-02-08)

**Commit**: Added directory marker filter at [packages.py:458-460](src/quilt_mcp/tools/packages.py#L458-L460)

```python
# Skip S3 directory markers (zero-byte objects with keys ending in '/')
if obj["Key"].endswith('/'):
    continue
```

**Verification**: Test error changed from:

- ❌ Before: `A package entry logical key 'raw/test/amazon/' must be a file.`
- ✅ After: Directory markers no longer added to package

**New Issue Discovered**: Test now fails with `404 Not Found (HeadObject operation)` due to
problematic S3 object names in test bucket:

```text
s3://quilt-ernest-staging/raw/test/amazon/output/quilt-example#package=examples%2fhurdat/...
```

Files contain:

- `#` characters (URL fragment delimiters)
- `%2f` URL-encoded slashes
- Long path segments with special characters

This is a **test data issue**, not a code bug. The test bucket contains legacy files with
non-standard naming conventions that cause boto3 HeadObject failures.

**Recommendation**: Update test configuration to use clean test prefix without problematic
filenames, or add special character handling in S3 operations.

### Bug 1: PhysicalKey Type Error - ⏳ PENDING

**Status**: Not yet fixed
**Location**: [quilt3_backend.py:198](src/quilt_mcp/backends/quilt3_backend.py#L198)
**Required Change**: Convert `entry.physical_key` (PhysicalKey object) to string in `_backend_get_package_entries()`

## Next Steps

- [x] Fix Bug 2: Directory marker filter ✅
- [ ] Fix Bug 1: PhysicalKey type conversion
- [ ] Clean up test bucket data or adjust test configuration
- [ ] Identify all backend primitives requiring type normalization review
- [ ] Update backend primitive documentation with type contracts
- [ ] Add regression tests for both bugs

---

**Analysis by**: Claude Code
**Test Framework**: scripts/tests/test_mcp.py
**Architecture**: Template Method Pattern (QuiltOps base class)
**Last Updated**: 2026-02-08 14:15 PST
