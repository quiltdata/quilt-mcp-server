# Search Fix Verification Guide

## Issue Summary

The search tool was not returning individual package results, only summary statistics. This has been fixed in `src/quilt_mcp/search/backends/graphql.py` by updating `_search_packages_global` to use the `firstPage` field.

## Changes Made

### Before (Broken)
```python
# Only returned summary statistics - NO individual packages
searchPackages(buckets: [], searchString: $searchString) {
    ... on PackagesSearchResultSet {
        total
        stats {
            modified { min max }
            size { min max sum }
        }
    }
}
# Result: Single "package_summary" result with aggregate stats
```

### After (Fixed)
```python
# Returns individual package results
searchPackages(buckets: [], searchString: $searchString) {
    ... on PackagesSearchResultSet {
        total
        firstPage(size: $pageSize) {
            hits {
                id score bucket name pointer hash
                size modified totalEntriesCount comment workflow
            }
        }
    }
}
# Result: Array of individual package SearchResult objects
```

## Verification Steps

### Step 1: Test Global Package Search (Empty Query)

This should return ALL packages across all accessible buckets.

```bash
curl -X POST https://demo.quiltdata.com/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${QUILT_JWT_TOKEN}" \
  -d '{
    "query": "query SearchPackages($searchString: String!, $pageSize: Int!) { searchPackages(buckets: [], searchString: $searchString) { ... on PackagesSearchResultSet { total firstPage(size: $pageSize) { hits { id score bucket name pointer hash size modified totalEntriesCount comment workflow } } } ... on EmptySearchResultSet { _ } } }",
    "variables": {
      "searchString": "",
      "pageSize": 10
    }
  }' | jq
```

**Expected Result:**
```json
{
  "data": {
    "searchPackages": {
      "total": 103,
      "firstPage": {
        "hits": [
          {
            "id": "...",
            "score": 1.0,
            "bucket": "quilt-sandbox-bucket",
            "name": "some-package-name",
            "pointer": "latest",
            "hash": "abc123...",
            "size": 1234567,
            "modified": "2025-10-01T12:00:00Z",
            "totalEntriesCount": 42,
            "comment": "Package description",
            "workflow": {}
          },
          // ... 9 more packages
        ]
      }
    }
  }
}
```

**Success Criteria:**
- ✅ `firstPage.hits` is an array with 10 items
- ✅ Each hit has `bucket`, `name`, `hash`, `size`, etc.
- ✅ No errors in response

### Step 2: Test Global Package Search (Keyword Query)

This should return packages matching "demo".

```bash
curl -X POST https://demo.quiltdata.com/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${QUILT_JWT_TOKEN}" \
  -d '{
    "query": "query SearchPackages($searchString: String!, $pageSize: Int!) { searchPackages(buckets: [], searchString: $searchString) { ... on PackagesSearchResultSet { total firstPage(size: $pageSize) { hits { id score bucket name hash size modified totalEntriesCount } } } ... on EmptySearchResultSet { _ } } }",
    "variables": {
      "searchString": "demo",
      "pageSize": 5
    }
  }' | jq '.data.searchPackages | {total, hits_count: (.firstPage.hits | length), packages: [.firstPage.hits[] | {bucket, name, size}]}'
```

**Expected Result:**
```json
{
  "total": 12,
  "hits_count": 5,
  "packages": [
    {"bucket": "quilt-sandbox-bucket", "name": "demo/package1", "size": 123456},
    {"bucket": "quilt-sandbox-bucket", "name": "demo/package2", "size": 234567},
    ...
  ]
}
```

**Success Criteria:**
- ✅ Returns packages with "demo" in their name
- ✅ `hits_count` matches the number of packages returned (up to pageSize)
- ✅ All packages have valid metadata

### Step 3: Test Bucket-Specific Search

This should return packages in `quilt-sandbox-bucket` only.

```bash
curl -X POST https://demo.quiltdata.com/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${QUILT_JWT_TOKEN}" \
  -d '{
    "query": "query BucketPackages($bucket: String!, $filter: String, $page: Int!, $perPage: Int!) { packages(bucket: $bucket, filter: $filter) { total page(number: $page, perPage: $perPage) { bucket name modified } } }",
    "variables": {
      "bucket": "quilt-sandbox-bucket",
      "filter": null,
      "page": 1,
      "perPage": 10
    }
  }' | jq '.data.packages | {total, page_count: (.page | length), packages: [.page[] | {name, modified}]}'
```

**Expected Result:**
```json
{
  "total": 103,
  "page_count": 10,
  "packages": [
    {"name": "package1", "modified": "2025-10-01T12:00:00Z"},
    {"name": "package2", "modified": "2025-10-02T13:00:00Z"},
    ...
  ]
}
```

**Success Criteria:**
- ✅ `total` should be 103 (as shown in your screenshot)
- ✅ `page_count` should be 10
- ✅ All packages are from `quilt-sandbox-bucket`

### Step 4: Test via MCP Tool (After Deployment)

Once the GraphQL queries are verified and the code is deployed, test the MCP tool:

```bash
curl -X POST https://demo.quiltdata.com/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${QUILT_JWT_TOKEN}" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search",
      "arguments": {
        "action": "unified_search",
        "params": {
          "query": "",
          "scope": "global",
          "limit": 10
        }
      }
    }
  }' | jq '.result.content[0].text | fromjson | {success, total: .total_results, result_count: (.results | length), first_package: .results[0] | {type, title, bucket: .metadata.bucket, name: .metadata.name}}'
```

**Expected Result:**
```json
{
  "success": true,
  "total": 103,
  "result_count": 10,
  "first_package": {
    "type": "package",
    "title": "quilt-sandbox-bucket/some-package",
    "bucket": "quilt-sandbox-bucket",
    "name": "some-package"
  }
}
```

**Success Criteria:**
- ✅ `success: true`
- ✅ `result_count` should be 10 (or the limit specified)
- ✅ Each result has `type: "package"` (not "package_summary")
- ✅ Each result has valid `bucket` and `name` in metadata
- ✅ Total matches the web UI (103 packages)

## Known Limitations

### Object Search Still Limited

The `_search_bucket_objects` function still returns empty results due to a backend bug with `searchObjects.firstPage` endpoint. This is documented in the code:

```python
async def _search_bucket_objects(self, query: str, bucket: str, ...) -> List[SearchResult]:
    """Search objects within a specific bucket using GraphQL.
    
    Note: The top-level objects() query doesn't exist in the GraphQL schema.
    Objects can only be searched via searchObjects, but searchObjects.firstPage
    has a backend bug. For now, we only return package results for bucket searches.
    TODO: Implement object search when backend bug is fixed
    """
    return []
```

**Impact:** Search results will only include packages, not individual files/objects.

**Workaround:** Users can browse package contents using `packaging.browse` after finding packages via search.

## Testing Checklist

Before deploying:
- [ ] Run Step 1 curl command - verify individual packages returned
- [ ] Run Step 2 curl command - verify search filtering works
- [ ] Run Step 3 curl command - verify bucket-scoped search works
- [ ] Check that no GraphQL errors are returned
- [ ] Verify total counts match web UI

After deploying:
- [ ] Run Step 4 MCP tool test
- [ ] Verify frontend receives individual packages (not summaries)
- [ ] Test with various search queries
- [ ] Verify pagination works correctly
- [ ] Check CloudWatch logs for any errors (with debug toggle)

## Rollback Plan

If issues are found after deployment:

1. Revert to previous version:
   ```bash
   ECS_CLUSTER=sales-prod ECS_SERVICE=sales-prod-mcp-server-production \
   aws ecs update-service \
     --cluster sales-prod \
     --service sales-prod-mcp-server-production \
     --task-definition quilt-mcp-task:136 \
     --region us-east-1
   ```

2. The previous version (0.6.49) is still available in ECR if needed.

## Next Steps

1. ✅ Fix implemented in `src/quilt_mcp/search/backends/graphql.py`
2. ⏳ **Run curl verification tests (REQUIRED BEFORE COMMIT)**
3. ⏳ Commit changes with message: "Fix global package search to return individual packages, not summary"
4. ⏳ Bump version to 0.6.50
5. ⏳ Build and push Docker image
6. ⏳ Deploy to ECS
7. ⏳ Run MCP tool verification tests
8. ⏳ Update frontend team on improved search results

