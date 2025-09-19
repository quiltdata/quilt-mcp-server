<!-- markdownlint-disable MD013 -->
# Gap Analysis - Minimal QuiltService Implementation

**GitHub Issue**: #155 "[isolate quilt3](https://github.com/quiltdata/quilt-mcp-server/issues/155)"

**Objective**: Eliminate all direct `import quilt3` statements outside of `quilt_service.py`.

## Executive Summary

**Required**: Implement **1 method** in QuiltService to eliminate all remaining direct quilt3 dependencies.

**Status**: Only `create_botocore_session()` needs implementation - all other abstractions already exist.

## Required Implementation

### Single Missing Method

**Implement `create_botocore_session()` in QuiltService**

**Where Used**: `src/quilt_mcp/aws/athena_service.py` (lines 70, 157, 171, 451)

```python
def create_botocore_session(self) -> Any:
    """Create authenticated botocore session."""
    return quilt3.session.create_botocore_session()
```

**Note**: The `quilt3.Bucket()` usage in `elasticsearch.py` line 126 should use the existing `create_bucket()` method instead - no new QuiltService methods needed.

**Result**: Eliminates all direct quilt3 imports outside of `quilt_service.py`

## Verification

**Test**: Confirm no direct quilt3 imports remain outside of `quilt_service.py`

```bash
# Should return only quilt_service.py after implementation
grep -r "import quilt3" src/ --exclude-dir=services
```

**Success**: Zero direct quilt3 dependencies in application code
