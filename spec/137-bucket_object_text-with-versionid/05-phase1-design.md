<!-- markdownlint-disable MD013 -->
# Phase 1 Design Document: Test Infrastructure Foundation

**Issue**: #137 - Add versionId support to bucket_object_text function  
**Phase**: 1 - Test Infrastructure Foundation

## Problem

Tests are failing because they mock `boto3.client()` but production code uses `get_s3_client()` helper function.

**Affected Tests**:

- `test_bucket_object_link_error()` in `test_bucket_tools.py`
- Multiple tests in `test_utils.py`

## Solution

### Fix Mock Targets

Change mocks from `boto3.client` to the actual helper functions:

```python
# Current (broken):
@patch("boto3.client") 

# Fixed:
@patch("quilt_mcp.tools.buckets.get_s3_client")  # for bucket_tools tests
@patch("quilt_mcp.utils.get_s3_client")          # for utils tests
```

### Measure Coverage Baseline

Run `make coverage` after fixes to establish accurate baseline for bucket_object_* functions.

### Add Missing Integration Test

Add `test_bucket_object_link_integration()` to complete test coverage for all four bucket_object_* functions.

## Implementation

1. **Fix mocks** - Update import paths in failing tests
2. **Measure coverage** - Document baseline percentages
3. **Add integration test** - Follow existing patterns in `test_integration.py`

## Success Criteria

- `make test` passes
- Coverage baseline documented
- All bucket_object_* functions have integration tests
