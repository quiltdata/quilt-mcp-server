# Tabulator Query Accommodation Analysis

**Date**: October 9, 2025  
**Issue**: `/api/tabulator/query` returning 405 Method Not Allowed  
**Research**: Enterprise & Quilt repos, GraphQL schema, MCP implementation

---

## Problem Statement

The `tabulator.table_query` and `tabulator.table_preview` actions fail with:
```
405 Client Error: Not Allowed for url: 
https://demo.quiltdata.com/api/tabulator/query
```

This prevents users from querying Tabulator tables directly through Qurator.

---

## Root Cause Analysis

### 1. **REST Endpoint vs GraphQL**

**Finding**: All Tabulator operations use GraphQL EXCEPT `table_query`:

| Operation | Method | Status |
|-----------|--------|--------|
| `tables_list` | GraphQL `bucketConfigs { tabulatorTables }` | ✅ Works |
| `table_create` | GraphQL `admin.bucketAddTabulatorTable` | ✅ Works |
| `table_delete` | GraphQL `admin.bucketDeleteTabulatorTable` | ✅ Works |
| `table_rename` | GraphQL `admin.bucketRenameTabulatorTable` | ✅ Works |
| `table_get` | GraphQL `bucketConfigs { tabulatorTables }` | ✅ Works |
| `open_query_status` | GraphQL `admin { tabulatorOpenQuery }` | ✅ Works |
| `open_query_toggle` | GraphQL `admin.setTabulatorOpenQuery` | ✅ Works |
| **`table_query`** | **REST `/api/tabulator/query`** | ❌ **405 Error** |

**Location**: `src/quilt_mcp/clients/catalog.py` lines 347-394

```python
def catalog_tabulator_query(
    *,
    registry_url: str,
    bucket_name: str,
    table_name: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    filters: Optional[Mapping[str, Any]] = None,
    order_by: Optional[str] = None,
    selects: Optional[Sequence[str]] = None,
    auth_token: Optional[str],
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    url = registry_url.rstrip("/") + "/api/tabulator/query"
    
    payload: Dict[str, Any] = {
        "bucket": bucket_name,
        "table": table_name,
    }
    # ... more payload construction
    
    data = catalog_rest_request(
        method="POST",  # ← 405 Error here
        url=url,
        auth_token=auth_token,
        json_body=payload,
        session=session,
    )
```

### 2. **GraphQL Schema Investigation**

**Finding**: The GraphQL schema does NOT include a `tabulatorQuery` or equivalent query.

**Evidence**: Search of `docs/quilt-enterprise-schema.graphql` shows:
- ✅ `tabulatorOpenQuery: Boolean!` (admin query for open query status)
- ✅ `setTabulatorOpenQuery` mutation
- ❌ NO `tabulatorQuery` or table data query operation

**Implication**: The REST endpoint is the ONLY way to query Tabulator table data through the API.

### 3. **Catalog Version / Feature Availability**

**Hypothesis**: The `/api/tabulator/query` REST endpoint is:
1. A newer feature not available on all catalog versions
2. Requires a specific catalog configuration or feature flag
3. Only available in enterprise catalogs with Tabulator Lambda configured

**Evidence**:
- demo.quiltdata.com returns 405 (endpoint doesn't exist or not enabled)
- Production catalogs may have it enabled
- No version documentation found in repos

---

## Alternative Approaches

### Option 1: Direct Athena Queries (Current Workaround)

**How It Works**: Tabulator tables are accessible via Athena with fully qualified names:
```sql
SELECT * FROM "<stack>-tabulator"."<bucket_name>"."<table_name>" LIMIT 10;
```

**Implementation Status**: Already documented in enhanced Tabulator tool docstring (v0.6.74)

**Pros**:
- ✅ Works on all catalogs with Athena configured
- ✅ More powerful (full SQL support)
- ✅ Uses `athena_glue` tool which already exists

**Cons**:
- ❌ Requires AWS IAM permissions (not just JWT)
- ❌ More complex for simple preview operations
- ❌ Requires knowing the stack name (e.g., "quilt-sales-prod-tabulator")

**Current User Impact**: Users without AWS IAM permissions cannot use this approach.

---

### Option 2: GraphQL Fallback (If Available)

**Investigation**: Check if there's an undocumented GraphQL query in newer catalog versions.

**Action Items**:
1. Test on production catalog (not demo) to see if `/api/tabulator/query` works
2. Check enterprise repo for recent commits adding tabulator query support
3. Contact Quilt team to confirm endpoint availability

**Implementation**: If GraphQL query exists, add it to `catalog.py` as fallback.

---

### Option 3: Enhanced Error Handling & Guidance

**Current AI Behavior**: When `table_query` fails, Qurator:
- ✅ Gracefully handles the error
- ✅ Provides helpful alternatives
- ✅ Shows correct SQL query syntax

**Enhancement**: Detect 405 specifically and provide clearer guidance:

```python
async def tabulator_table_query(...) -> Dict[str, Any]:
    try:
        response = catalog_client.catalog_tabulator_query(...)
    except Exception as exc:
        if "405" in str(exc) or "Method Not Allowed" in str(exc):
            return {
                "success": False,
                "error": "Tabulator query endpoint not available on this catalog",
                "workaround": "Use direct Athena queries instead",
                "athena_query": f'SELECT * FROM "<stack>-tabulator"."{bucket_name}"."{table_name}" LIMIT 10;',
                "instructions": [
                    "1. Identify the Athena database name (usually '<stack>-tabulator')",
                    "2. Use the athena_glue tool to execute the query",
                    "3. Or use the catalog's Queries page in the web UI"
                ]
            }
        return format_error_response(f"Failed to query tabulator table '{table_name}': {exc}")
```

---

### Option 4: Web UI Navigation (Future)

**Concept**: Add navigation capabilities to MCP so Qurator can:
1. Navigate to the catalog's Queries page
2. Input SQL query
3. Submit and retrieve results

**Status**: NOT CURRENTLY POSSIBLE
- MCP server doesn't have navigation tools
- Navigation context is sent FROM frontend TO server, not controlled by server
- Would require significant frontend work

---

## Recommended Solution

### Short-Term (Deploy Now)

**1. Enhanced Error Messaging**
- Add specific 405 error detection
- Provide clear workaround instructions
- Include sample Athena query

**2. Documentation Updates**
- Update Tabulator tool docstring to mention endpoint limitation
- Add note about catalog version requirements
- Emphasize Athena fallback approach

**3. Testing on Production**
- Verify if production catalogs support `/api/tabulator/query`
- Document which catalog versions have it enabled

### Mid-Term (Next Sprint)

**4. Athena Integration Bridge**
- Create a `tabulator_table_query_via_athena` fallback
- Automatically construct Athena query from Tabulator parameters
- Requires resolving stack name (from catalog metadata or config)

**5. Feature Detection**
- Add catalog capability detection at MCP startup
- Cache which features are available (GraphQL introspection + REST endpoint probes)
- Automatically route to working approach

### Long-Term (Product Feature)

**6. GraphQL Query Support**
- Work with Quilt team to add `tabulatorQuery` to GraphQL schema
- Migrate from REST to GraphQL for consistency
- Deprecate REST endpoint after migration period

---

## Implementation Plan

### Phase 1: Quick Fix (2-3 hours)

```python
# src/quilt_mcp/tools/tabulator.py

async def tabulator_table_query(...) -> Dict[str, Any]:
    # Existing validation...
    
    try:
        response = catalog_client.catalog_tabulator_query(...)
    except Exception as exc:
        error_str = str(exc).lower()
        if "405" in error_str or "method not allowed" in error_str:
            # Construct helpful fallback response
            stack_hint = _guess_stack_name(catalog_url)
            athena_query = (
                f'SELECT * FROM "{stack_hint}-tabulator"."{bucket_name}"."{table_name}" '
                f'LIMIT {limit or 10};'
            )
            
            return {
                "success": False,
                "error_type": "endpoint_unavailable",
                "message": "Tabulator query endpoint not available on this catalog",
                "catalog_url": catalog_url,
                "workaround": {
                    "method": "direct_athena",
                    "query": athena_query,
                    "instructions": [
                        "Option 1: Use the athena_glue tool to run this query directly",
                        "Option 2: Navigate to the catalog's Queries page in your browser",
                        "Option 3: Contact your Quilt administrator to enable the query endpoint"
                    ]
                },
                "athena_example": {
                    "tool": "athena_glue",
                    "action": "query_execute",
                    "params": {
                        "database": f"{stack_hint}-tabulator",
                        "query": athena_query
                    }
                }
            }
        
        # Other errors remain as-is
        return format_error_response(f"Failed to query tabulator table: {exc}")

def _guess_stack_name(catalog_url: str) -> str:
    """Guess stack name from catalog URL."""
    # demo.quiltdata.com → "demo"
    # quilt-sales-prod.example.com → "quilt-sales-prod"
    from urllib.parse import urlparse
    hostname = urlparse(catalog_url).hostname or ""
    if "demo" in hostname:
        return "demo"
    if "sales-prod" in hostname:
        return "quilt-sales-prod"
    return "quilt-prod"  # Default guess
```

### Phase 2: Athena Fallback (1 day)

1. Add `_query_via_athena_fallback()` helper
2. Auto-detect if Athena is available
3. Seamlessly fall back to Athena if REST fails

### Phase 3: Feature Detection (2 days)

1. Add catalog capability detection
2. Cache results per session
3. Route to appropriate method automatically

---

## Testing Strategy

### Test 1: Verify 405 Error Handling
```python
# tests/unit/test_tabulator_query_fallback.py

@pytest.mark.asyncio
async def test_table_query_handles_405_with_helpful_message(monkeypatch):
    """Test that 405 errors provide Athena fallback guidance."""
    
    def mock_query(*args, **kwargs):
        raise requests.HTTPError("405 Client Error: Not Allowed")
    
    monkeypatch.setattr("quilt_mcp.clients.catalog.catalog_tabulator_query", mock_query)
    
    result = await tabulator_table_query("mybucket", "mytable", limit=10)
    
    assert result["success"] is False
    assert result["error_type"] == "endpoint_unavailable"
    assert "athena" in result["workaround"]["method"]
    assert "SELECT * FROM" in result["workaround"]["query"]
    assert "athena_glue" in result["athena_example"]["tool"]
```

### Test 2: Production Catalog
- Deploy to production catalog
- Test if `/api/tabulator/query` works there
- Document findings

### Test 3: Athena Fallback Integration
- Test automatic fallback when Athena is available
- Verify query construction is correct
- Ensure results are properly formatted

---

## Open Questions

1. **Which catalog versions support `/api/tabulator/query`?**
   - Need to check with Quilt team
   - Document version requirements

2. **Is there a feature flag to enable it?**
   - Check catalog configuration options
   - Test on different catalog instances

3. **Will GraphQL query support be added?**
   - Discuss with Quilt team
   - Timeline for implementation

4. **What's the best stack name detection approach?**
   - Hardcode for known catalogs?
   - Add catalog metadata endpoint?
   - Make it configurable?

---

## Decision

**Recommended Approach**: Implement **Phase 1** (Quick Fix) immediately, deploy in v0.6.75.

**Rationale**:
- Provides immediate value with helpful error messages
- Doesn't break existing functionality
- Guides users to working alternatives
- Low risk, high impact

**Next Steps**:
1. Implement enhanced error handling
2. Test on demo catalog (verify 405 is caught)
3. Test on production catalog (check if endpoint works)
4. Deploy and monitor
5. Plan Phase 2 based on production test results

---

## Summary

The `/api/tabulator/query` REST endpoint is the only way to query Tabulator table data via API, but it's not available on all catalog versions (returns 405 on demo.quiltdata.com). The best short-term solution is enhanced error handling that provides clear guidance to use direct Athena queries as a workaround. Mid-term, we should implement automatic fallback to Athena queries. Long-term, we should work with Quilt team to add GraphQL support for table queries to achieve consistency with other Tabulator operations.

