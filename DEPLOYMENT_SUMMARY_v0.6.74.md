# Deployment Summary: v0.6.74

**Date**: October 9, 2025  
**Time**: Deployment completed  
**Version**: 0.6.74  
**Status**: ✅ Successfully Deployed

## Overview

Deployed critical bucket filtering fix and enhanced Tabulator documentation to production.

## Changes Deployed

### 1. Bucket Filtering Fix (Critical Bug)
- **Issue**: Package search was returning wrong buckets
- **Fix**: Updated `_search_packages_global` to accept both `bucket` (singular) and `buckets` (plural) parameters
- **Impact**: Search results now correctly filter to the requested bucket
- **Tests**: 4 new tests added, all passing

### 2. Tabulator Documentation Enhancement
- **Issue**: Users lacked guidance on Tabulator configuration and troubleshooting
- **Fix**: Enhanced `tabulator` tool docstring with 147 lines of comprehensive documentation
- **Content**:
  - YAML configuration examples with named capture groups
  - Common error messages with causes and fixes
  - SQL query examples for Athena access
  - Auto-added columns documentation
- **Source**: Official Quilt docs at https://docs.quilt.bio/quilt-platform-administrator/advanced/tabulator

## Deployment Details

### Docker Image
- **Registry**: `850787717197.dkr.ecr.us-east-1.amazonaws.com`
- **Image**: `quilt-mcp-server:0.6.74`
- **Platform**: `linux/amd64`
- **Status**: ✅ Built and pushed successfully

### ECS Task Definition
- **Family**: `quilt-mcp-server`
- **Revision**: 184
- **Image**: `850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:0.6.74`
- **Status**: ✅ Registered and active

### ECS Service Update
- **Cluster**: `sales-prod`
- **Service**: `sales-prod-mcp-server-production`
- **Previous Revision**: 183
- **New Revision**: 184
- **Deployment Status**: ✅ Complete
  - New task (184) running: 1/1
  - Old task (183) draining: 0/0

## Verification Steps

### 1. Deployment Status ✅
```bash
aws ecs describe-services \
  --cluster sales-prod \
  --services sales-prod-mcp-server-production \
  --region us-east-1
```

Result: PRIMARY deployment (rev 184) running, DRAINING deployment (rev 183) complete

### 2. Test Bucket Filtering
Test the bucket filtering fix in browser on demo.quiltdata.com:

```javascript
// Test with singular 'bucket' parameter
search(action="unified_search", params={
    "query": "*",
    "scope": "catalog",
    "search_type": "packages",
    "filters": {"bucket": "nextflowtower"}
})

// Verify results only show nextflowtower packages
// Expected: All results should have bucket: "nextflowtower"
```

### 3. Test Tabulator Documentation
Ask AI to help configure a Tabulator table and verify it provides:
- Correct YAML structure
- Named capture group syntax
- Error troubleshooting guidance

## Files Modified

### Source Code
1. `src/quilt_mcp/search/backends/graphql.py` - Bucket filtering fix
2. `src/quilt_mcp/tools/tabulator.py` - Enhanced documentation
3. `pyproject.toml` - Version bump to 0.6.74

### Tests
4. `tests/unit/test_bucket_filtering.py` - New test file (4 tests, all passing)

### Configuration
5. `task-definition-clean.json` - Updated image to 0.6.74

### Documentation
6. `CLAUDE.md` - Key learnings documented
7. `BUCKET_FILTERING_AND_TABULATOR_FIX.md` - Detailed fix documentation
8. `TABULATOR_AND_SEARCH_REMEDIATION.md` - Issue analysis

## Test Results

### Unit Tests
```
✅ 4 new tests passing (bucket filtering)
✅ 15 existing tests still passing (search)
✅ 0 tests broken
```

### Build Verification
```
✅ Docker build successful (linux/amd64)
✅ Image pushed to ECR
✅ Task definition registered
✅ Service updated
✅ New task running and healthy
```

## Known Issues

### Tabulator "sail" Table DataFusion Error

**Status**: Outstanding (requires Quilt support)

**Problem**: Table fails with `INVALID_FUNCTION_ARGUMENT: undefined group option`

**Root Cause**: Tabulator Lambda uses outdated DataFusion version that doesn't support newer Parquet metadata formats

**Recommendation**: Contact Quilt support to update Lambda:
- Lambda: `sales-prod-TabulatorLambda-yXUridthb6qT`
- Region: `us-east-1`
- Account: `850787717197`

**Workaround**: Use direct Athena queries instead of Tabulator

## Rollback Plan

If issues are discovered:

```bash
# Rollback to previous revision (183)
aws ecs update-service \
  --cluster sales-prod \
  --service sales-prod-mcp-server-production \
  --task-definition quilt-mcp-server:183 \
  --force-new-deployment \
  --region us-east-1
```

## Success Metrics

1. ✅ Docker image built and pushed successfully
2. ✅ Task definition registered (revision 184)
3. ✅ Service updated and running new task
4. ✅ All unit tests passing
5. ⏳ Bucket filtering working in browser (pending user test)
6. ⏳ Tabulator documentation helpful to users (pending user feedback)

## Next Steps

1. ⏳ Monitor service health for 24 hours
2. ⏳ Test bucket filtering in browser on demo.quiltdata.com
3. ⏳ Contact Quilt support about Tabulator Lambda update
4. ⏳ Gather user feedback on Tabulator documentation
5. ⏳ Update VERSION environment variable globally if needed

## Version History

- **v0.6.73**: Benchling proxy integration, enhanced Tabulator query API
- **v0.6.74**: Bucket filtering fix, Tabulator documentation enhancement ← Current

## References

- **Official Tabulator Docs**: https://docs.quilt.bio/quilt-platform-administrator/advanced/tabulator
- **Issue Analysis**: `TABULATOR_AND_SEARCH_REMEDIATION.md`
- **Fix Details**: `BUCKET_FILTERING_AND_TABULATOR_FIX.md`
- **Tests**: `tests/unit/test_bucket_filtering.py`
- **ECR**: `850787717197.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:0.6.74`

---

**Deployment completed successfully. Version 0.6.74 is now live in production.**

