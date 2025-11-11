# Search Catalog Issues - Investigation Report

**Date**: 2025-11-11
**Context**: User reported two semantic errors with search functionality

## Issue 1: Bucket Scope Returns Results, Catalog/Global Don't

### Problem Statement
Searching on a specific bucket returns results, but 'catalog' and 'global' search scopes (which should be supersets) return no results or errors.

### Expected Behavior
- **Bucket scope**: Search within specific bucket (e.g., `s3://quilt-ernest-staging`)
- **Catalog scope**: Search across all buckets in the current catalog stack (superset of bucket)
- **Global scope**: Search across all available resources (superset of catalog)

If bucket search returns 5 results, catalog and global should return **at least** those same 5 results.

### Actual Behavior
From testing with released version (via MCP tools):

```
Bucket scope (s3://quilt-ernest-staging):
  ✅ Success: true
  ✅ Backend: elasticsearch
  ✅ Total results: 5

Catalog scope:
  ⚠️  Success: true (but empty)
  ⚠️  Backend: graphql, s3
  ❌ Total results: 0
  ❌ Elasticsearch error: "403 Forbidden"

Global scope:
  ⚠️  Success: true (but empty)
  ⚠️  Backend: graphql, s3
  ❌ Total results: 0
  ❌ Elasticsearch error: "403 Forbidden"
```

### Root Cause Analysis

#### Code Flow for Different Scopes

**Bucket Scope** ([elasticsearch.py:115-117](../../src/quilt_mcp/search/backends/elasticsearch.py#L115-L117)):
```python
if scope == "bucket" and target:
    # Use bucket-specific search
    results = await self._search_bucket(query, target, filters, limit)
```

This calls `_search_bucket()` which uses:
```python
bucket_obj = self.quilt_service.create_bucket(bucket_uri)
raw_results = bucket_obj.search(es_query, limit=limit)
```

This works because it directly searches the bucket's Elasticsearch index.

**Catalog/Global Scope** ([elasticsearch.py:122-123](../../src/quilt_mcp/search/backends/elasticsearch.py#L122-L123)):
```python
else:
    # Global/catalog search using packages search API
    results = await self._search_global(query, filters, limit)
```

This calls `_search_global()` which:
1. Calls `_execute_catalog_search()`
2. Inside that, calls `build_stack_search_indices()` from [stack_buckets.py](../../src/quilt_mcp/tools/stack_buckets.py)
3. This builds an index pattern like: `"bucket1,bucket1_packages,bucket2,bucket2_packages"`
4. Passes this to the catalog search API

#### Why It Fails

The `build_stack_search_indices()` function:
```python
def build_stack_search_indices(buckets: Optional[List[str]] = None) -> str:
    """Build Elasticsearch index pattern for searching across all stack buckets."""
    if buckets is None:
        buckets = get_stack_buckets()

    if not buckets:
        logger.warning("No buckets found for stack search")
        return ""

    # Build index pattern: for each bucket, include both the main index and packages index
    indices = []
    for bucket in buckets:
        indices.extend([bucket, f"{bucket}_packages"])

    index_pattern = ",".join(indices)
    return index_pattern
```

When this index pattern is passed to the catalog search API, it returns **403 Forbidden**. Possible reasons:

1. **Permission Error**: The user may not have permission to search across multiple indices
2. **Index Doesn't Exist**: Some indices in the pattern may not exist
3. **API Limitation**: The catalog search API might not support cross-bucket searches
4. **Stack Discovery Issue**: `get_stack_buckets()` might be returning buckets that shouldn't be in the pattern

#### The Missing Fallback

In `_search_global()` ([elasticsearch.py:200-208](../../src/quilt_mcp/search/backends/elasticsearch.py#L200-L208)):

```python
async def _search_global(self, query: str, filters: Optional[Dict[str, Any]], limit: int) -> List[SearchResult]:
    """Global search across all stack buckets using the catalog search API."""
    search_response = self._execute_catalog_search(query=query, limit=limit, filters=filters)

    if "error" in search_response:
        raise Exception(search_response["error"])  # ❌ Raises immediately!

    hits = search_response.get("hits", {}).get("hits", [])
    return self._convert_catalog_results(hits)
```

When the 403 error occurs, the code **immediately raises an exception** instead of falling back to searching just the default bucket.

### Solution Design

Add a fallback mechanism in `_search_global()`:

```python
async def _search_global(self, query: str, filters: Optional[Dict[str, Any]], limit: int) -> List[SearchResult]:
    """Global search across all stack buckets using the catalog search API.

    Falls back to searching the default registry bucket if stack-wide search fails.
    """
    search_response = self._execute_catalog_search(query=query, limit=limit, filters=filters)

    if "error" in search_response:
        # Check if this is a permission error (403) or index not found error
        error_msg = search_response["error"]
        is_permission_error = "403" in str(error_msg) or "Forbidden" in str(error_msg)
        is_index_error = "index_not_found" in str(error_msg).lower()

        if is_permission_error or is_index_error:
            # Fall back to searching just the default registry bucket
            try:
                from ...constants import DEFAULT_REGISTRY

                if DEFAULT_REGISTRY:
                    bucket_uri = DEFAULT_REGISTRY
                    # Try bucket-specific search as fallback
                    return await self._search_bucket(query, bucket_uri, filters, limit)
            except Exception:
                # If fallback also fails, raise the original error
                pass

        raise Exception(search_response["error"])

    hits = search_response.get("hits", {}).get("hits", [])
    return self._convert_catalog_results(hits)
```

This ensures that:
1. We try the full stack search first (best case)
2. If we get 403 or index errors, fall back to just the default bucket
3. If fallback works, return those results (semantic correctness)
4. If even fallback fails, raise the original error

---

## Issue 2: GraphQL Shows Available But Errors When Used

### Problem Statement
GraphQL backend shows as available in `backend_status`, but errors when actually used.

### Observed Behavior

From testing:
```
Backend Info (backend_status):
  graphql: {
    "available": true,     # ✅ Shows available
    "status": "available"
  }

When using GraphQL explicitly:
  Bucket scope: ❌ "GraphQL query failed: Error: GraphQL request failed: 'message'"
  Catalog scope: ✅ Works (returns 0 results, but no error)
  Global scope: ✅ Works (returns 0 results, but no error)
```

### Root Cause Analysis

#### Lazy Initialization

The GraphQL backend uses lazy initialization ([graphql.py:37-45](../../src/quilt_mcp/search/backends/graphql.py#L37-L45)):

```python
def __init__(self):
    super().__init__(BackendType.GRAPHQL)
    self._registry_url = None
    self._session = None
    # Do not check GraphQL access during initialization - use lazy initialization

def _initialize(self):
    """Initialize backend by checking GraphQL access.

    This method is called lazily on first use via ensure_initialized().
    Authentication checks are deferred until the backend is actually needed.
    """
    self._check_graphql_access()
```

The initialization is only triggered when `ensure_initialized()` is called, which happens:
1. When `get_search_backend_status()` is called ([backend_status.py:94](../../src/quilt_mcp/search/utils/backend_status.py#L94))
2. When the backend is actually used for search ([graphql.py:141](../../src/quilt_mcp/search/backends/graphql.py#L141))

#### The Cryptic Error Message

The error "GraphQL request failed: 'message'" comes from ([search.py:432-433](../../src/quilt_mcp/tools/search.py#L432-L433)):

```python
except Exception as e:
    return SearchGraphQLError(error=f"GraphQL request failed: {e}")
```

The string representation of some exception is literally `'message'`, which suggests the exception object is not being properly converted to a string, or there's a KeyError for `'message'`.

#### Error Handling Chain

1. GraphQL query is executed via `_execute_graphql_query()` ([graphql.py:464-492](../../src/quilt_mcp/search/backends/graphql.py#L464-L492))
2. This calls `search_graphql()` from tools ([search.py:377-433](../../src/quilt_mcp/tools/search.py#L377-L433))
3. If `search_graphql()` returns `success: false`, it tries to extract error details
4. The error extraction code:

```python
if result.get("errors"):
    for error in result["errors"]:
        error_msg = error.get("message", "Unknown error")  # ⚠️ Assumes dict
        error_path = " -> ".join(error.get("path", []))
        error_location = error.get("locations", [{}])[0]
        location_str = f"line {error_location.get('line', '?')}, col {error_location.get('column', '?')}"

        error_details.append(f"GraphQL Error: {error_msg} (path: {error_path}, location: {location_str})")
```

This assumes `error` is a dict with a `message` key. If the error format is different, this could fail.

#### Scope-Specific Behavior

- **Bucket scope** ([graphql.py:219-264](../../src/quilt_mcp/search/backends/graphql.py#L219-L264)): Uses `objects(bucket:...)` query which might not be supported
- **Catalog/Global scope** ([graphql.py:266-356](../../src/quilt_mcp/search/backends/graphql.py#L266-L356)): Uses `searchPackages` and `searchObjects` which work

The bucket scope query:
```graphql
query SearchBucketObjects($bucket: String!, $filter: ObjectFilterInput, $first: Int!) {
    objects(bucket: $bucket, filter: $filter, first: $first) {
        edges {
            node { key size updated contentType extension ... }
        }
    }
}
```

This might not be available in all GraphQL deployments, causing the error.

### Solution Design

#### Fix 1: Better Error Handling in `_execute_graphql_query`

```python
async def _execute_graphql_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a GraphQL query using the proven search_graphql approach."""
    from ...tools.search import search_graphql

    result = search_graphql(query, variables)

    if not result.get("success"):
        # Unpack detailed error information for better troubleshooting
        error_details = []

        if result.get("error"):
            error_details.append(f"Error: {result['error']}")

        if result.get("errors"):
            # Handle both list and dict error formats
            errors = result["errors"]
            if isinstance(errors, list):
                for error in errors:
                    if isinstance(error, dict):
                        error_msg = error.get("message", str(error))
                        error_path = error.get("path")
                        if error_path:
                            error_details.append(f"GraphQL Error: {error_msg} (path: {' -> '.join(str(p) for p in error_path)})")
                        else:
                            error_details.append(f"GraphQL Error: {error_msg}")
                    else:
                        error_details.append(f"GraphQL Error: {error}")
            else:
                error_details.append(f"GraphQL Errors: {errors}")

        detailed_error = "; ".join(error_details) if error_details else "Unknown GraphQL error"
        raise Exception(f"GraphQL query failed: {detailed_error}")

    return {"data": result.get("data"), "errors": result.get("errors")}
```

#### Fix 2: Graceful Degradation for Bucket Scope

When bucket-specific GraphQL queries fail, fall back to alternative approaches:

```python
async def _search_bucket_objects(
    self, query: str, bucket: str, filters: Optional[Dict[str, Any]], limit: int
) -> List[SearchResult]:
    """Search objects within a specific bucket using GraphQL."""
    try:
        # Try the bucket-specific objects query
        graphql_query = """..."""
        result = await self._execute_graphql_query(graphql_query, variables)
        return self._convert_bucket_objects_results(result, bucket)
    except Exception as e:
        # If bucket-specific query fails, return empty results
        # (Elasticsearch backend will handle bucket search)
        return []
```

#### Fix 3: Status Check Improvements

Ensure `backend_status` accurately reflects actual availability:

1. Test the specific queries that will be used (not just `bucketConfigs`)
2. Mark as "partial" if only some queries work
3. Include capability details (what query types are supported)

---

## Testing Strategy

### Test Case 1: Bucket vs Catalog/Global Parity
```python
# All three should return the same results
bucket_results = search_catalog(query="*", scope="bucket", target="s3://quilt-ernest-staging")
catalog_results = search_catalog(query="*", scope="catalog")
global_results = search_catalog(query="*", scope="global")

assert len(bucket_results) > 0, "Bucket search should return results"
assert len(catalog_results) >= len(bucket_results), "Catalog should be superset of bucket"
assert len(global_results) >= len(catalog_results), "Global should be superset of catalog"
```

### Test Case 2: GraphQL Backend Consistency
```python
# Backend status should match actual availability
status = get_search_backend_status()
graphql_status = status["backends"]["graphql"]

# Try to use GraphQL
try:
    result = search_catalog(query="test", backend="graphql")
    # If status says available, this should work
    if graphql_status["available"]:
        assert result["success"], "GraphQL should work if marked available"
except Exception as e:
    # If it fails, status should NOT say available
    assert not graphql_status["available"], f"GraphQL marked available but failed: {e}"
```

### Test Case 3: Fallback Mechanism
```python
# When stack search fails, should fall back to bucket search
with mock.patch('build_stack_search_indices', return_value="nonexistent_index"):
    result = search_catalog(query="*", scope="global")
    # Should fall back and return bucket results, not error
    assert result["success"], "Should fall back when stack search fails"
    assert len(result["results"]) > 0, "Fallback should return results"
```

---

## Files to Modify

1. **[src/quilt_mcp/search/backends/elasticsearch.py](../../src/quilt_mcp/search/backends/elasticsearch.py)**
   - Modify `_search_global()` to add fallback logic (lines 200-208)

2. **[src/quilt_mcp/search/backends/graphql.py](../../src/quilt_mcp/search/backends/graphql.py)**
   - Improve error handling in `_execute_graphql_query()` (lines 464-492)
   - Add fallback in `_search_bucket_objects()` (lines 219-264)

3. **[tests/](../../tests/)** (create new test file)
   - Add comprehensive tests for scope parity
   - Add tests for backend status consistency
   - Add tests for fallback mechanisms

---

## Impact Assessment

### Critical Issues
- ❌ **Semantic correctness violated**: Supersets returning subsets breaks the mental model
- ❌ **Silent failures**: Errors masked as "no results found"
- ❌ **Status misreporting**: Backend claims availability but fails

### User Impact
- Users cannot trust scope semantics
- Catalog/global search appears broken when bucket search works
- Confusing error messages about GraphQL

### System Impact
- No data corruption risk
- No authentication/security risk
- Affects search functionality only
- Can be fixed without breaking changes
