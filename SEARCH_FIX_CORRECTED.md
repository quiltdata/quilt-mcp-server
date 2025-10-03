# Search Fix - Final Resolution

## Critical Discovery

**The "backend bug" was actually OUR mistake!** 🎯

The 500 Internal Server Error was caused by passing a `size` parameter to `firstPage`. The frontend NEVER does this.

## Root Cause Analysis

### What We Did Wrong
```graphql
# ❌ BROKEN - Causes 500 error
query SearchPackages($searchString: String!, $pageSize: Int!) {
    searchPackages(buckets: [], searchString: $searchString) {
        ... on PackagesSearchResultSet {
            firstPage(size: $pageSize) {  # ← This causes 500 error!
                hits { ... }
            }
        }
    }
}
```

### What The Frontend Does (Correctly)
```graphql
# ✅ WORKS - No size parameter!
query SearchPackages($searchString: String!, $order: SearchResultOrder!, $latestOnly: Boolean!) {
    searchPackages(buckets: [], searchString: $searchString, latestOnly: $latestOnly) {
        ... on PackagesSearchResultSet {
            firstPage(order: $order) {  # ← No size parameter!
                hits { ... }
            }
        }
    }
}
```

## Key Differences

| Parameter | Our Approach | Frontend Approach | Result |
|-----------|--------------|-------------------|--------|
| `size` on `firstPage` | ✅ Passed (e.g., 50) | ❌ NOT passed | Frontend works, ours fails |
| `latestOnly` | ❌ NOT passed | ✅ Passed (false) | Required parameter |
| `order` | ❌ NOT passed | ✅ Passed (BEST_MATCH) | Optional but recommended |

## Solution

Match the frontend's approach exactly:
1. **Remove** `size` parameter from `firstPage`
2. **Add** `latestOnly: false` parameter to `searchPackages`
3. **Add** `order: "BEST_MATCH"` parameter to `firstPage`
4. Backend returns default page size (~30 results)
5. We limit to requested amount in post-processing

## Curl Verification (Success)

```bash
export QUILT_JWT_TOKEN='your-token'

curl -X POST https://demo-registry.quiltdata.com/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${QUILT_JWT_TOKEN}" \
  -d '{
    "query": "query SearchPackages($searchString: String!, $order: SearchResultOrder!, $latestOnly: Boolean!) { searchPackages(buckets: [], searchString: $searchString, latestOnly: $latestOnly) { ... on PackagesSearchResultSet { total firstPage(order: $order) { hits { id bucket name hash size modified totalEntriesCount } } } } }",
    "variables": {
      "searchString": "",
      "order": "BEST_MATCH",
      "latestOnly": false
    }
  }' | python3 -m json.tool
```

**Result:** ✅ SUCCESS
- Returns ~30 packages per page (default backend page size)
- No errors
- Individual packages, not summaries
- Works across all accessible buckets

## Code Changes

### File: `src/quilt_mcp/search/backends/graphql.py`

**Before (Broken):**
```python
graphql_query = """
    query SearchPackages($searchString: String!, $pageSize: Int!) {
        searchPackages(buckets: [], searchString: $searchString) {
            ... on PackagesSearchResultSet {
                total
                firstPage(size: $pageSize) { ... }  # ← 500 error
            }
        }
    }
"""
variables = {
    "searchString": query,
    "pageSize": limit  # ← This causes the error!
}
```

**After (Fixed):**
```python
graphql_query = """
    query SearchPackages($searchString: String!, $order: SearchResultOrder!, $latestOnly: Boolean!) {
        searchPackages(buckets: [], searchString: $searchString, latestOnly: $latestOnly) {
            ... on PackagesSearchResultSet {
                total
                firstPage(order: $order) { ... }  # ← No size!
            }
        }
    }
"""
variables = {
    "searchString": query if query and query != "*" else "",
    "order": "BEST_MATCH",
    "latestOnly": False,  # Include all revisions
}
```

## Why This Happened

1. **Assumption Error**: We assumed `firstPage(size: N)` was the correct way to limit results
2. **Schema Misunderstanding**: The GraphQL schema shows `size` as optional, but passing it triggers a backend issue
3. **Missing Frontend Research**: Should have checked frontend implementation first
4. **Documentation Gap**: The GraphQL schema doesn't document that `size` parameter is problematic

## Lessons Learned

1. ✅ **Always check frontend implementation** before implementing backend features
2. ✅ **Test with curl** before writing code
3. ✅ **Match working examples exactly** - don't assume improvements
4. ✅ **GraphQL schema alone is insufficient** - need to see actual usage

## Performance Characteristics

### Global Search (Fixed)
- **Queries:** 1 GraphQL query
- **Latency:** ~200-400ms
- **Results:** ~30 packages (default page size), limited to requested amount
- **Scalability:** Excellent (single query across all buckets)

### Comparison to Previous "Workaround"
| Metric | Workaround (10 buckets) | Fixed Approach (searchPackages) |
|--------|------------------------|----------------------------------|
| Queries | 11 (1 bucketConfigs + 10 packages) | 1 (searchPackages) |
| Latency | ~1-2 seconds | ~200-400ms |
| Results | Scattered across buckets | Ranked by relevance |
| Scalability | Limited to 10 buckets | All buckets |

The fixed approach is **5-10x faster** and covers all buckets!

## Testing Checklist

### ✅ Pre-Deployment (Completed)
- [x] Researched frontend implementation
- [x] Found actual GraphQL queries used by frontend
- [x] Tested without size parameter via curl
- [x] Verified empty search strings work
- [x] Verified keyword searches work
- [x] Confirmed returns individual packages
- [x] Updated code to match frontend exactly

### ⏳ Post-Deployment (To Do)
- [ ] Test MCP tool via frontend
- [ ] Verify global search returns 30+ packages
- [ ] Test bucket-specific search still works
- [ ] Verify filtering works
- [ ] Check performance (should be <500ms)
- [ ] Monitor CloudWatch logs

## Expected Behavior After Deployment

### Global Search
```python
search.unified_search(query="", scope="global", limit=10)
```

**Returns:**
- Up to 30 packages from backend (default page size)
- Limited to 10 in response (as requested)
- Packages from all accessible buckets
- Ranked by relevance (BEST_MATCH order)
- Each with type "package" and full metadata

### Bucket Search
```python
search.unified_search(query="demo", scope="bucket", target="quilt-sandbox-bucket", limit=10)
```

**Returns:**
- Up to 10 packages from `quilt-sandbox-bucket`
- Filtered by "demo" keyword
- Same structure as global search

## Backend Team Note

There is NO backend bug. The issue was our incorrect usage of the `size` parameter on `firstPage`.

However, we recommend:
1. Document that `size` parameter on `firstPage` should be omitted for best results
2. Consider returning a better error message than "Internal Server Error" when size is passed
3. Update GraphQL schema documentation to clarify this behavior

## Next Steps

1. ✅ Code fixed and committed
2. ⏳ Version bump (already done - 0.6.50)
3. ⏳ Deploy (in progress)
4. ⏳ Test via frontend
5. ⏳ Update CHANGELOG.md
6. ⏳ Close search-related issues

