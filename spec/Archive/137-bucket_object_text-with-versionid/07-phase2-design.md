<!-- markdownlint-disable MD013 -->
# Phase 2 Design: Extract URI Parsing Logic

## Overview

Phase 2 extracts the duplicate S3 URI parsing logic found in all four bucket_object_* functions into a shared utility function. This consolidation improves maintainability and prepares the codebase for Phase 3's version ID support.

## Design Details

### New Utility Function

Add to `/src/quilt_mcp/utils.py`:

```python
def parse_s3_uri(s3_uri: str) -> tuple[str, str, str | None]:
    """
    Parse S3 URI into bucket, key, and version_id components.
    
    Args:
        s3_uri: S3 URI in format 's3://bucket/key' or 's3://bucket/key?versionId=xyz'
        
    Returns:
        Tuple of (bucket, key, version_id) where version_id is always None in Phase 2
        
    Raises:
        ValueError: If URI format is invalid
    """
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI format: {s3_uri}")
    
    without = s3_uri[5:]  # Remove s3:// prefix
    bucket, key = without.split("/", 1)  # Split on first slash
    
    return bucket, key, None  # version_id always None in Phase 2
```

### Function Refactoring

Replace identical parsing code in these functions:

- `bucket_object_info()` (lines 89-92)
- `bucket_object_text()` (lines 124-127)
- `bucket_object_fetch()` (lines 233-236)
- `bucket_object_link()` (lines 298-301)

**Before:**

```python
without = s3_uri[5:]  # Remove s3:// prefix
bucket, key = without.split("/", 1)  # Split on first slash
```

**After:**

```python
bucket, key, _ = parse_s3_uri(s3_uri)
```

## Implementation Steps

1. **Add Utility Function**
   - Add `parse_s3_uri()` to `/src/quilt_mcp/utils.py`
   - Include comprehensive docstring

2. **Refactor Functions**
   - Replace parsing logic in all four bucket_object_* functions
   - Import `parse_s3_uri` at top of file
   - Maintain exact same behavior

3. **Add Tests**
   - Test valid S3 URIs
   - Test invalid URI formats
   - Test error handling
   - Verify version_id always returns None

## Success Criteria

- ✅ All existing tests pass (zero behavior changes)
- ✅ URI parsing logic consolidated into single function
- ✅ All four functions use shared utility
- ✅ 100% test coverage for `parse_s3_uri()`
- ✅ No functional changes to bucket_object_* functions

## Risk Mitigation

- **Behavior Preservation**: Extensive testing ensures no functional changes
- **Error Handling**: New utility maintains same error behavior as original code
- **Import Dependencies**: Minimal changes to existing function signatures
