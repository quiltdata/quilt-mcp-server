# Package Metadata Gaps

**Status:** Discovery
**Date:** 2026-02-11
**Context:** E2E test coverage for package browse

## Summary

The `Package_Info` domain object does not include package-level metadata. Package metadata (stored in `package.meta` for quilt3 packages) is retrieved separately but not included in the standard package information structure.

## Current Architecture

### Package_Info Domain Object

Location: `src/quilt_mcp/domain/package_info.py`

```python
@dataclass(frozen=True)
class Package_Info:
    name: str
    description: Optional[str]
    tags: List[str]
    modified_date: str
    registry: str
    bucket: str
    top_hash: str
    # ❌ No metadata field
```

### Backend Metadata Retrieval

Backends provide separate methods for metadata:

**quilt3 backend** (`src/quilt_mcp/backends/quilt3_backend.py:225`):
```python
def _backend_get_package_metadata(self, package: Any) -> Dict[str, Any]:
    """Get metadata from quilt3 package (backend primitive)."""
    return package.meta or {}
```

**Platform backend** (`src/quilt_mcp/backends/platform_backend.py:664`):
```python
def _backend_get_package_metadata(self, package: Any) -> Dict[str, Any]:
    """Get metadata from platform package response."""
    # Implementation retrieves userMeta from GraphQL response
```

### Package Info Transformation

In `src/quilt_mcp/backends/quilt3_backend_packages.py:121-129`:

```python
package_info = Package_Info(
    name=quilt3_package.name,
    description=description,
    tags=tags,
    modified_date=modified_date,
    registry=quilt3_package.registry,
    bucket=quilt3_package.bucket,
    top_hash=quilt3_package.top_hash,
    # ❌ quilt3_package.meta is NOT captured
)
```

## MCP Tool Implementation

The `package_browse` tool (`src/quilt_mcp/tools/packages.py:804-811`) retrieves metadata separately:

```python
try:
    package_obj = quilt_ops._backend_get_package(package_name, registry=normalized_registry)
    pkg_metadata = quilt_ops._backend_get_package_metadata(package_obj)
except Exception as meta_error:
    logger.warning(f"Could not retrieve package metadata: {meta_error}")
    pkg_metadata = None
```

The metadata is included in the response (`packages.py:908`):

```python
return PackageBrowseSuccess(
    package_name=package_name,
    registry=registry,
    total_entries=len(entries),
    summary=summary,
    view_type="recursive" if recursive else "flat",
    file_tree=file_tree if recursive and file_tree else None,
    entries=entries,
    metadata=pkg_metadata,  # ✅ Included in tool response
)
```

## Package Metadata Contents

Package metadata commonly includes fields like:

- `QUILT_CATALOG_URL` - Catalog URL where package was created
- `catalog` - Catalog domain name
- `context` - Package creation context/message
- `region` - AWS region
- `updated_at` - Timestamp
- `updated_by` - Creator identification

Example from user screenshot:
```json
{
    "catalog": "nightly.quilttest.com",
    "context": "Added README with catalog connection info f",
    "region": "us-east-1",
    "updated_at": "2026-02-09T22:05Z",
    "updated_by": "Claude via Quilt MCP"
}
```

## E2E Test Coverage

**Current test:** `tests/e2e/backend/test_simple_browse.py`

The test only checks that items are returned:

```python
def test_browse_existing_package(backend_with_auth):
    result = backend_with_auth.browse_content(
        package_name="test/mcp_create", registry="s3://quilt-ernest-staging", path=""
    )

    assert len(result) > 0, "Should find at least one item in package"
    # ❌ Does not check package metadata
```

**Gap:** The test does not verify package-level metadata, including `QUILT_CATALOG_URL`.

## Data Flow

```
MCP Tool (package_browse)
    ↓
QuiltOps.browse_content() → Returns List[Content_Info]
    AND (separately)
QuiltOps._backend_get_package() → Returns package object
QuiltOps._backend_get_package_metadata(package) → Returns Dict[str, Any]
    ↓
PackageBrowseSuccess(entries=..., metadata=pkg_metadata)
```

**Key observation:** Metadata retrieval is separate from package info retrieval.

## Architecture Implications

1. **Package_Info is minimal** - Contains only core identifying fields, not metadata
2. **Metadata is optional** - Can fail without blocking content browsing
3. **Two-step retrieval** - Tools must explicitly request both package info and metadata
4. **No standard interface** - `get_package_info()` doesn't return metadata; must use primitives

## Related Files

- `src/quilt_mcp/domain/package_info.py` - Domain object definition
- `src/quilt_mcp/backends/quilt3_backend_packages.py` - Package info transformation
- `src/quilt_mcp/backends/quilt3_backend.py:225` - Metadata retrieval primitive
- `src/quilt_mcp/backends/platform_backend.py:664` - Platform metadata retrieval
- `src/quilt_mcp/tools/packages.py:804-811` - Tool-level metadata handling
- `tests/e2e/backend/test_simple_browse.py` - E2E test for package browse
