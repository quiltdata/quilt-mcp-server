# Search Bucket Scoping and Auto-Navigation Fix

**Date:** 2025-10-03  
**Issue:** Search was not scoping to bucket when `bucket` parameter was provided, and no automatic navigation was triggered

## Problems Identified

### 1. Bucket Parameter Not Mapped to Target
When the frontend sent:
```json
{
  "bucket": "quilt-sandbox-bucket",
  "scope": "bucket",
  "search_type": "objects",
  "query": ".csv"
}
```

The search wrapper was not mapping the `bucket` parameter to `target`, so the GraphQL backend received `target=""` and searched all buckets instead of the specified one.

### 2. No Navigation Suggestion in Response
When performing bucket-scoped searches, users expected to automatically navigate to the bucket page, but the search tool didn't provide any navigation information.

## Solutions Implemented

### Fix 1: Map `bucket` Parameter to `target`

**File:** `src/quilt_mcp/tools/search.py`

Added parameter mapping in three action handlers:

```python
# Map bucket parameter to target for bucket-scoped searches
if "bucket" in params and not mapped_params.get("target"):
    mapped_params["target"] = params["bucket"]
```

**Applied to:**
- `search_packages` action (line 378-379)
- `search_objects` action (line 425-426)
- `unified_search` action (line 466-467)

**How it works:**
1. Frontend sends `bucket: "quilt-sandbox-bucket"`
2. Wrapper maps it to `target: "quilt-sandbox-bucket"`
3. GraphQL backend receives `scope="bucket"` and `target="quilt-sandbox-bucket"`
4. Backend passes `buckets=["quilt-sandbox-bucket"]` to GraphQL query
5. Results are correctly filtered to only that bucket

### Fix 2: Add Navigation Suggestion to Search Response

**File:** `src/quilt_mcp/search/tools/unified_search.py`

Added automatic navigation suggestion when searches are scoped to specific buckets or packages.

**New method:**
```python
def _build_navigation_suggestion(self, scope: str, target: str) -> Dict[str, Any]:
    """Build navigation suggestion that matches frontend's navigate tool format."""
    if scope == "bucket":
        bucket_name = target.replace("s3://", "")
        return {
            "tool": "navigate",
            "params": {
                "route": {
                    "name": "bucket.overview",
                    "params": {
                        "bucket": bucket_name,
                    },
                },
            },
            "auto_execute": True,  # Frontend should auto-execute this navigation
            "description": f"Navigating to bucket: {bucket_name}",
            "url": f"/b/{bucket_name}",
        }
    # Similar for package scope...
```

**Response format:**
```json
{
  "success": true,
  "query": ".csv",
  "scope": "bucket",
  "target": "quilt-sandbox-bucket",
  "results": [...],
  "navigation": {
    "tool": "navigate",
    "params": {
      "route": {
        "name": "bucket.overview",
        "params": {
          "bucket": "quilt-sandbox-bucket"
        }
      }
    },
    "auto_execute": true,
    "description": "Navigating to bucket: quilt-sandbox-bucket",
    "url": "/b/quilt-sandbox-bucket"
  }
}
```

## Frontend Integration

The frontend MCP client can now automatically trigger navigation when it receives a search response with `navigation.auto_execute: true`:

```javascript
// Frontend MCP client processing search response
async function handleSearchResponse(response) {
  // Display search results
  displayResults(response.results);
  
  // Auto-navigate if suggested
  if (response.navigation?.auto_execute) {
    await navigate(response.navigation.params);
  }
}
```

## Architecture Notes

### Why Not Direct Tool Calls?

MCP tools (backend) cannot directly call frontend native tools like `navigate` because:
1. They run in different contexts (backend vs frontend)
2. MCP protocol is request-response based
3. Backend tools return data, frontend decides on UI actions

### The Solution Pattern

Instead, we use **navigation suggestions** in the response:
- Backend returns structured navigation data
- Frontend recognizes `auto_execute: true` flag
- Frontend automatically calls its native `navigate` tool
- This maintains separation of concerns and follows MCP architecture

## Testing

### Manual Test Case 1: Bucket-Scoped Object Search

**Input:**
```javascript
await mcpClient.callTool('search', {
  action: 'unified_search',
  params: {
    bucket: 'quilt-sandbox-bucket',
    scope: 'bucket',
    search_type: 'objects',
    query: '.csv'
  }
});
```

**Expected Behavior:**
1. Search results filtered to only `quilt-sandbox-bucket`
2. Response includes navigation suggestion
3. Frontend auto-navigates to `/b/quilt-sandbox-bucket`
4. User sees search results in bucket context

### Manual Test Case 2: Package-Scoped Search

**Input:**
```javascript
await mcpClient.callTool('search', {
  action: 'unified_search',
  params: {
    scope: 'package',
    target: 'quilt-sandbox-bucket/my-package',
    query: 'data files'
  }
});
```

**Expected Behavior:**
1. Search results filtered to the specified package
2. Response includes navigation to package page
3. Frontend auto-navigates to `/b/quilt-sandbox-bucket/packages/my-package`

## Benefits

1. **Better UX**: Users automatically navigate to the correct context
2. **Correct Results**: Search results properly scoped to specified bucket
3. **Clean Architecture**: Backend suggests, frontend executes
4. **Flexible**: Frontend can disable auto-navigation if desired
5. **Consistent**: Follows MCP protocol patterns

## Related Files

- `src/quilt_mcp/tools/search.py` - Search tool wrapper
- `src/quilt_mcp/search/tools/unified_search.py` - Unified search engine
- `src/quilt_mcp/search/backends/graphql.py` - GraphQL backend (no changes needed)

## Future Enhancements

1. Add navigation suggestions for object-level searches (navigate to specific file)
2. Support prefix/directory navigation for directory-scoped searches
3. Add "breadcrumb" navigation for hierarchical contexts
4. Support batch navigation for multi-target searches

