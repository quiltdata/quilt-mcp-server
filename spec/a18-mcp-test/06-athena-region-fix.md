# A18-06: Fix Athena Query Region Configuration

**Status:** Draft
**Created:** 2026-02-06
**Issue:** Athena queries fail/timeout in mcp-test due to hardcoded region mismatch

## Problem Statement

### Current Behavior (Broken)

MCP test Athena queries timeout after 5 seconds and fail to execute. The root cause is **hardcoded region values** in the Athena service layer:

```
athena_service.py:99  → region = "us-east-1"  # Hardcoded!
athena_service.py:196 → get_boto3_client("glue", region="us-east-1")
athena_service.py:203 → create_client("glue", region_name="us-east-1")
athena_service.py:207 → boto3.client("glue", region_name="us-east-1")
```

### Why This Breaks

1. **Cross-Region Limitation**: AWS Athena cannot query Glue Data Catalog tables across regions
2. **Region Mismatch**:
   - Athena queries execute in `us-east-1` (hardcoded)
   - User's Glue catalog may be in a different region (e.g., `us-west-2`, `eu-west-1`)
   - Result: Athena cannot access the Glue catalog → queries timeout/fail
3. **Configuration Ignored**: The catalog's configured region (available in `Catalog_Config.region`) is ignored

### Impact

- **All Athena tools fail**: `athena_query_execute`, `athena_tables_list`, `athena_table_schema`
- **Test suite shows timeouts**: Discovery phase times out after 5 seconds
- **User experience degraded**: Athena features unusable for non-us-east-1 catalogs

## Solution Architecture

### Design Principle

**"Region follows catalog configuration"** - All AWS service clients (Athena, Glue, S3) should use the catalog's configured region as their default.

### Component Changes

#### 1. AthenaQueryService Region Resolution

**New Method: `_get_catalog_region()`**

Purpose: Centralized region resolution with fallback chain
```
Priority:
1. Catalog config region (from backend.get_catalog_config().region)
2. AWS_DEFAULT_REGION environment variable
3. Fallback to "us-east-1"
```

**Updated Methods:**
- `_create_sqlalchemy_engine()`: Use `_get_catalog_region()` instead of hardcoded value
- `_create_glue_client()`: Pass resolved region to client creation
- Constructor: Accept optional `region` parameter for explicit override

#### 2. Quilt3Backend Region Defaulting

**Enhanced: `get_boto3_client(service_name, region=None)`**

When `region=None` (caller doesn't specify):
```
Priority:
1. Check if catalog config exists → use catalog_config.region
2. Fall back to boto3 default region resolution
```

This ensures that when services call `backend.get_boto3_client("glue")` without specifying region, they get the catalog's region automatically.

#### 3. Backend Region Access

**Ensure all backends expose catalog region:**
- `Quilt3_Backend`: Already has `get_catalog_config()` returning `Catalog_Config` with `region`
- `Platform_Backend`: Should return region in catalog info (verify)

### Data Flow

```
1. AthenaService initialization
   └─> Stores backend reference

2. Query execution triggered
   └─> _get_catalog_region() called
       ├─> backend.get_catalog_config()
       │   └─> Returns Catalog_Config(region="us-west-2", ...)
       └─> Returns "us-west-2"

3. Create Athena engine
   └─> Uses region="us-west-2" in connection string

4. Create Glue client
   └─> backend.get_boto3_client("glue", region="us-west-2")
       └─> Both Athena and Glue use SAME region

5. Query executes successfully
   └─> Athena (us-west-2) queries Glue catalog (us-west-2)
```

## Implementation Plan

### Phase 1: AthenaService Region Resolution

**Files:** `src/quilt_mcp/services/athena_service.py`

1. Add `_get_catalog_region()` method with fallback logic
2. Update `_create_sqlalchemy_engine()` to use `_get_catalog_region()`
3. Remove hardcoded `"us-east-1"` strings (4 locations)
4. Pass resolved region to all Glue client creation calls

**Testing:**
- Unit test: `_get_catalog_region()` with various backend states
- Unit test: Verify no hardcoded regions remain
- Integration test: Mock catalog config with different regions

### Phase 2: Backend Region Defaulting

**Files:** `src/quilt_mcp/backends/quilt3_backend_session.py`

1. Update `get_boto3_client()` to detect `region=None`
2. Add fallback to `get_catalog_config().region` when region not specified
3. Handle exceptions gracefully (catalog config not available)

**Testing:**
- Unit test: `get_boto3_client("glue", region=None)` → uses catalog region
- Unit test: `get_boto3_client("glue", region="eu-west-1")` → uses explicit region
- Unit test: Catalog config unavailable → falls back to boto3 default

### Phase 3: Athena Tools Verification

**Files:** All tools using AthenaQueryService

Verify that:
1. Tools don't pass explicit region (rely on service default)
2. Tools work with multi-region catalog configurations
3. Error messages mention region mismatch if it still occurs

### Phase 4: Test Suite Updates

**Files:** `scripts/mcp-test-setup.py`, `scripts/tests/mcp-test.yaml`

1. Update Athena tool test arguments (if any region-specific)
2. Verify discovery phase completes without timeout
3. Add region-aware validation to discovery

## Edge Cases & Considerations

### 1. Multi-Region Deployments

**Scenario:** Catalog in `us-west-2`, data in `us-east-1`

**Solution:** Glue catalog should be co-located with Athena queries. If data is cross-region:
- Use Glue crawlers to create catalog entries in query region
- Or use S3 bucket region for queries (not Glue cross-region)

### 2. No Catalog Configuration

**Scenario:** Backend doesn't have catalog config (early initialization)

**Solution:** Fallback chain handles this:
```
catalog region (missing) → AWS_DEFAULT_REGION → "us-east-1"
```

### 3. Platform Backend (JWT Mode)

**Scenario:** Platform backend doesn't have direct AWS access

**Impact:** Athena tools should return clear error: "AWS access not available in Platform mode"

**Note:** This is already handled by `Platform_Backend.get_boto3_client()` raising `AuthenticationError`

### 4. Workgroup Region vs Catalog Region

**Scenario:** Athena workgroup in different region than catalog

**Solution:**
- Workgroup discovery should happen in the same region as queries
- If workgroup not found in catalog region, fall back to "primary"
- Log warning about region mismatch

### 5. Explicit Region Override

**Scenario:** User wants to force specific region (testing, special cases)

**Solution:** Accept optional `region` parameter in `AthenaQueryService.__init__()`:
```python
AthenaQueryService(backend=backend, region="eu-central-1")
```
This overrides catalog config for that service instance.

## Testing Strategy

### Unit Tests

**Test:** `test_athena_service_region_resolution`
- Mock catalog config with various regions
- Verify `_get_catalog_region()` returns correct values
- Test fallback chain

**Test:** `test_backend_region_defaulting`
- Call `get_boto3_client()` with and without region
- Verify catalog region used when not specified

**Test:** `test_no_hardcoded_regions`
- Assert no `"us-east-1"` strings in region assignment
- Verify dynamic region resolution

### Integration Tests

**Test:** `test_athena_query_multi_region`
- Create mock catalog configs for different regions
- Execute sample queries
- Verify correct region used in boto3 calls

**Test:** `test_athena_glue_same_region`
- Verify Athena and Glue clients use identical region
- Test with multiple catalog configurations

### E2E Tests (mcp-test)

**Test:** `test_athena_query_execute`
- Run full discovery with real catalog
- Verify queries complete without timeout
- Check query results are valid

**Test:** `test_athena_tables_list`
- List tables in configured catalog region
- Verify tables from Glue catalog are returned

## Success Criteria

1. **Zero Hardcoded Regions**: No `"us-east-1"` strings in Athena service region logic
2. **Catalog Region Used**: All Athena/Glue operations use `catalog_config.region`
3. **Tests Pass**: Discovery phase completes successfully (no timeouts)
4. **Multi-Region Support**: Works with catalogs in any AWS region
5. **Fallback Robustness**: Handles missing catalog config gracefully

## Non-Goals

- **Cross-region Glue queries**: Not attempting to make Athena query Glue catalogs in different regions (AWS limitation)
- **Auto-detect data region**: Not inferring region from S3 bucket locations
- **Multi-catalog support**: Not supporting queries across multiple Glue catalogs simultaneously

## Documentation Updates

### Code Comments

Add docstrings explaining region resolution:
```python
def _get_catalog_region(self) -> str:
    """Get AWS region for Athena queries from catalog configuration.

    Region Resolution Priority:
    1. Catalog config region (from backend)
    2. AWS_DEFAULT_REGION environment variable
    3. Fallback to us-east-1

    Important: Athena and Glue must use the SAME region because
    Athena cannot query Glue Data Catalogs across regions.
    """
```

### User-Facing Docs

Update Athena tool documentation:
- Explain region configuration requirements
- Document AWS_DEFAULT_REGION environment variable
- Clarify single-region limitation

## Rollout Plan

### Phase 1: Development
1. Implement `_get_catalog_region()` method
2. Update all hardcoded region references
3. Add unit tests

### Phase 2: Integration Testing
1. Test with development catalog (multiple regions)
2. Verify discovery script works
3. Run full mcp-test suite

### Phase 3: Validation
1. Test with production-like catalogs
2. Verify cross-region catalogs work correctly
3. Confirm no regressions in existing functionality

### Phase 4: Deployment
1. Merge changes to main branch
2. Update documentation
3. Notify users of improved Athena region support

## Monitoring & Validation

### Metrics to Track

- **Query Success Rate**: Should increase from ~0% to >95%
- **Query Latency**: Should decrease from 5000ms (timeout) to <2000ms (typical)
- **Discovery Phase Duration**: Athena tools should complete in <2s each

### Logging Enhancements

Add debug logging:
```
[AthenaService] Using catalog region: us-west-2
[AthenaService] Created Athena engine in region: us-west-2
[AthenaService] Created Glue client in region: us-west-2
```

This helps diagnose region configuration issues.

## References

### Related Issues
- A18-03: MCP test setup and discovery
- A18-04: Tabulator auth status (may share region logic)

### AWS Documentation
- [Athena Glue Data Catalog Integration](https://docs.aws.amazon.com/athena/latest/ug/glue-athena.html)
- [Athena Workgroup Configuration](https://docs.aws.amazon.com/athena/latest/ug/workgroups.html)
- [Cross-Region Limitations](https://docs.aws.amazon.com/athena/latest/ug/querying-glue-catalog.html)

### Demo Scripts
- `/tmp/athena_region_demo.py` - Demonstrates the problem
- `/tmp/athena_fix_example.py` - Shows broken vs fixed implementations

## Appendix: Code Locations

### Files Requiring Changes

1. **`src/quilt_mcp/services/athena_service.py`** (Primary changes)
   - Line 99: Remove hardcoded region in `_create_sqlalchemy_engine()`
   - Line 196: Pass dynamic region to `backend.get_boto3_client()`
   - Line 203: Pass dynamic region to botocore session
   - Line 207: Pass dynamic region to boto3.client()
   - Add: `_get_catalog_region()` method

2. **`src/quilt_mcp/backends/quilt3_backend_session.py`** (Secondary changes)
   - Line 358-395: Enhance `get_boto3_client()` to default to catalog region

3. **`tests/unit/services/test_athena_service.py`** (New tests)
   - Add region resolution tests
   - Add multi-region integration tests

### No Changes Required

- **Tool implementations**: Already use service layer correctly
- **MCP tool definitions**: Region-agnostic
- **Frontend/UI**: No user-facing changes needed

---

**Next Steps:**
1. Review this spec with team
2. Create implementation branch
3. Execute Phase 1 (AthenaService changes)
4. Validate with mcp-test discovery
