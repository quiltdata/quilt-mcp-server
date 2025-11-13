# Issue: GraphQL Package Search Returns Object Summaries Instead of Individual Package Results

**Status:** Identified
**Created:** 2025-01-12
**Component:** `search_catalog` tool - GraphQL backend package search
**Severity:** High - Fundamentally incorrect search results

## Problem Statement

When using the GraphQL backend to search for packages, the search returns **summary statistics about bucket objects** instead of **individual package results**. This makes it impossible to:

1. Browse actual packages that match the search query
2. Get package names, hashes, or metadata
3. Navigate to specific packages from search results
4. Distinguish one package from another

### Current Behavior

When searching with `backend="graphql"` and `scope="global"` (or `scope="catalog"`), the results mix:

1. **Object summary** - A single aggregate result about matching bucket objects
2. **Package summary** - A single aggregate result about matching packages

**Example Output:**

```json
{
  "results": [
    {
      "id": "graphql-objects-myquery",
      "type": "object_summary",
      "title": "1,234 objects matching 'myquery'",
      "description": "Found 1,234 objects | Total size: 45.2 GB | Top types: csv: 450, json: 320, parquet: 215",
      "metadata": {
        "total_objects": 1234,
        "search_query": "myquery",
        "stats": { ... },
        "extension_breakdown": [ ... ]
      },
      "backend": "graphql"
    },
    {
      "id": "graphql-packages-myquery",
      "type": "package_summary",
      "title": "89 packages matching 'myquery'",
      "description": "Found 89 packages | Total size: 12.3 GB | Date range: 2023-01-15 to 2024-12-10",
      "metadata": {
        "total_packages": 89,
        "search_query": "myquery",
        "stats": { ... }
      },
      "backend": "graphql"
    }
  ]
}
```

**What's Wrong:**
- Only **2 results total** regardless of how many packages match
- No way to see **which packages** matched
- No package names, hashes, or individual metadata
- Can't navigate to specific packages
- Completely useless for browsing packages

### Expected Behavior

The GraphQL backend should return individual package results, similar to Elasticsearch:

```json
{
  "results": [
    {
      "id": "graphql-package-team/dataset-v1",
      "type": "package",
      "title": "team/dataset-v1",
      "description": "RNA sequencing data from experiment A",
      "package_name": "team/dataset-v1",
      "s3_uri": "quilt+s3://my-bucket#package=team/dataset-v1@abc123",
      "size": 2500000000,
      "last_modified": "2024-11-15T10:30:00Z",
      "metadata": {
        "bucket": "my-bucket",
        "hash": "abc123...",
        "total_entries": 45,
        "comment": "Initial upload"
      },
      "score": 0.92,
      "backend": "graphql"
    },
    {
      "id": "graphql-package-team/dataset-v2",
      "type": "package",
      "title": "team/dataset-v2",
      "description": "Updated RNA sequencing data with QC metrics",
      "package_name": "team/dataset-v2",
      "s3_uri": "quilt+s3://my-bucket#package=team/dataset-v2@def456",
      "size": 2800000000,
      "last_modified": "2024-12-01T14:20:00Z",
      "metadata": {
        "bucket": "my-bucket",
        "hash": "def456...",
        "total_entries": 52,
        "comment": "Added QC metrics"
      },
      "score": 0.88,
      "backend": "graphql"
    }
    // ... up to limit
  ]
}
```

## Root Cause Analysis

The issue is in [graphql.py:277-366](../../../src/quilt_mcp/search/backends/graphql.py#L277-L366):

### 1. Query Only Returns Aggregate Statistics

```python
async def _search_packages_global(
    self, query: str, filters: Optional[Dict[str, Any]], limit: int
) -> List[SearchResult]:
    """Search packages globally using Enterprise GraphQL searchPackages."""
    graphql_query = """
    query SearchPackages($searchString: String!) {
        searchPackages(buckets: [], searchString: $searchString) {
            ... on PackagesSearchResultSet {
                total          # ❌ Only aggregate count
                stats {        # ❌ Only aggregate stats
                    modified { min max }
                    size { min max sum }
                }
            }
            ... on EmptySearchResultSet {
                _
            }
        }
    }
    """
```

**Problem:** The GraphQL query doesn't request the `firstPage` field that contains actual package hits!

### 2. Converting Stats to Single Summary Result

```python
if total > 0:
    # Create meaningful result with statistics from GraphQL
    return [
        SearchResult(
            id=f"graphql-packages-{query}",      # ❌ Single summary result
            type="package_summary",              # ❌ Not "package"
            title=f"{total} packages matching '{query}'",  # ❌ Generic title
            description=" | ".join(description_parts),     # ❌ Just stats
            metadata={
                "total_packages": total,  # ❌ No individual package info
                "search_query": query,
                "stats": stats,
            },
            backend="graphql",
        )
    ]
```

**Problem:** Returns a single summary instead of iterating through individual package hits.

### 3. Comment Reveals the Truth

Line 281 has a telling comment:

```python
# Use working searchPackages query (total only - firstPage has server errors)
```

**The Real Issue:** The `firstPage` field was **intentionally disabled** due to server errors!

### 4. Comparison with Object Search

The object search has the **exact same problem** in [graphql.py:759-810](../../../src/quilt_mcp/search/backends/graphql.py#L759-L810):

```python
def _convert_objects_search_results(self, graphql_result: Dict[str, Any], query: str):
    search_objects = data.get("searchObjects", {})

    if search_objects.get("total") is not None:
        total = search_objects["total"]
        stats = search_objects.get("stats", {})

        # ❌ Returns single summary instead of individual objects
        return [
            SearchResult(
                id=f"graphql-objects-{query}",
                type="object_summary",  # ❌ Summary type
                title=f"{total} objects matching '{query}'",
                ...
            )
        ]
```

## What the Correct GraphQL Query Should Be

Based on the Enterprise schema, the correct query should request `firstPage` with `hits`:

```graphql
query SearchPackages($searchString: String!, $first: Int!) {
    searchPackages(buckets: [], searchString: $searchString) {
        ... on PackagesSearchResultSet {
            total
            stats {
                modified { min max }
                size { min max sum }
            }
            firstPage(first: $first) {
                hits {
                    id
                    name
                    bucket
                    hash
                    pointer
                    size
                    modified
                    totalEntriesCount
                    comment
                    workflow {
                        id
                        config
                    }
                    meta
                }
                cursor
            }
        }
        ... on EmptySearchResultSet {
            _
        }
    }
}
```

## Why This Wasn't Noticed Earlier

1. **Backend defaults to Elasticsearch** - The default backend is `"elasticsearch"`, not `"graphql"`
2. **Tests use mocks** - Unit tests mock GraphQL responses, hiding the real behavior
3. **Integration tests skip GraphQL** - Most integration tests use Elasticsearch or S3 backends
4. **Server errors mentioned** - The comment about "firstPage has server errors" suggests this was a known workaround

## Impact Assessment

### Current State

| Backend | Package Search Works? | Returns Individual Results? |
|---------|----------------------|----------------------------|
| Elasticsearch | ✅ Yes | ✅ Yes |
| GraphQL | ❌ No | ❌ No (only summaries) |
| S3 | N/A (not applicable) | N/A |

### Affected Use Cases

1. **Package browsing** - Users can't see which packages match their search
2. **Package discovery** - Can't explore package names or metadata
3. **Catalog navigation** - Can't click through to specific packages
4. **Backend comparison** - GraphQL backend appears broken vs. Elasticsearch
5. **Enterprise installations** - Sites that prefer GraphQL over Elasticsearch are stuck

### Why This Is Severe

- **Fundamentally broken** - Package search is a core feature
- **Silent failure** - Returns results (summaries) but wrong type
- **No workaround** - Can't use GraphQL backend for package search at all
- **Bad user experience** - "Found 89 packages" with no way to see them

## Solution Design

### Option 1: Fix GraphQL Query (Preferred)

**If server-side `firstPage` errors are resolved:**

1. Update the GraphQL query to request `firstPage` with `hits`
2. Implement proper pagination with cursors
3. Convert individual hits to `SearchResult` objects
4. Handle both aggregate stats AND individual results

**Implementation:**

```python
async def _search_packages_global(
    self, query: str, filters: Optional[Dict[str, Any]], limit: int
) -> List[SearchResult]:
    """Search packages globally using Enterprise GraphQL searchPackages."""
    graphql_query = """
    query SearchPackages($searchString: String!, $first: Int!) {
        searchPackages(buckets: [], searchString: $searchString) {
            ... on PackagesSearchResultSet {
                total
                stats { ... }
                firstPage(first: $first) {
                    hits {
                        id name bucket hash pointer size modified
                        totalEntriesCount comment workflow { id config } meta
                    }
                    cursor
                }
            }
            ... on EmptySearchResultSet { _ }
        }
    }
    """

    variables = {"searchString": query, "first": limit}
    result = await self._execute_graphql_query(graphql_query, variables)

    # Convert individual hits, not just stats
    return self._convert_catalog_search_results(result)


def _convert_catalog_search_results(self, graphql_result: Dict[str, Any]) -> List[SearchResult]:
    """Convert searchPackages GraphQL results to standard format."""
    results = []

    data = graphql_result.get("data", {})
    search_packages = data.get("searchPackages", {})

    if search_packages.get("total") is not None:
        first_page = search_packages.get("firstPage", {})
        hits = first_page.get("hits", [])

        for hit in hits:
            # Extract package metadata
            bucket = hit.get("bucket", "")
            package_name = hit.get("name", "")
            hash_value = hit.get("hash", "")

            # Build Quilt+ URI
            quilt_uri = f"quilt+s3://{bucket}#package={package_name}"
            if hash_value:
                quilt_uri += f"@{hash_value[:8]}"

            result = SearchResult(
                id=hit.get("id", f"graphql-package-{package_name}"),
                type="package",
                title=package_name,
                description=hit.get("comment") or f"Package in {bucket}",
                s3_uri=quilt_uri,
                package_name=package_name,
                logical_key=None,
                size=hit.get("size"),
                last_modified=hit.get("modified"),
                metadata={
                    "bucket": bucket,
                    "hash": hash_value,
                    "pointer": hit.get("pointer"),
                    "total_entries": hit.get("totalEntriesCount"),
                    "comment": hit.get("comment"),
                    "workflow": hit.get("workflow"),
                    "user_meta": hit.get("meta"),
                },
                score=hit.get("score", 1.0),
                backend="graphql",
            )

            results.append(result)

    return results
```

### Option 2: Disable GraphQL for Package Search

**If server-side issues persist:**

1. Make GraphQL backend return empty results for package search
2. Add clear error message explaining limitation
3. Force fallback to Elasticsearch for package queries
4. Document GraphQL limitations

**Implementation:**

```python
async def _search_packages_global(
    self, query: str, filters: Optional[Dict[str, Any]], limit: int
) -> List[SearchResult]:
    """Search packages globally - NOT SUPPORTED in GraphQL backend.

    The Enterprise GraphQL searchPackages.firstPage field has server errors
    that prevent retrieving individual package hits. Package search will
    automatically fall back to Elasticsearch backend.
    """
    # Return empty results so unified search tries other backends
    return []
```

### Option 3: Hybrid Approach

**Best of both worlds:**

1. Use GraphQL for aggregate stats (fast)
2. Fall back to Elasticsearch for individual results (reliable)
3. Combine both for rich metadata

## Recommended Solution

**Option 1** if server issues are fixable (probably worth investigating)
**Option 2** if server issues are architectural (document and move on)

### Investigation Steps

1. **Test `firstPage` query directly**
   - Use `test-mcp` script to execute the full query with `firstPage`
   - Check what error the server returns
   - Determine if it's a client issue or server issue

2. **Check Enterprise schema version**
   - Verify schema supports `firstPage` field
   - Check if field requires special permissions
   - Look for deprecation notices

3. **Review GraphQL server logs**
   - Check Enterprise backend logs for errors
   - Look for query complexity limits
   - Check for field resolver errors

## Testing Plan

### Unit Tests

```python
def test_search_packages_returns_individual_results():
    """GraphQL package search should return individual packages, not summaries."""
    backend = EnterpriseGraphQLBackend()

    response = await backend.search("myquery", scope="global", limit=10)

    assert len(response.results) > 2  # More than just 2 summaries

    # Check first result is an actual package
    pkg = response.results[0]
    assert pkg.type == "package"  # Not "package_summary"
    assert pkg.package_name is not None
    assert pkg.s3_uri is not None
    assert pkg.s3_uri.startswith("quilt+s3://")


def test_search_packages_with_firstpage():
    """Test GraphQL query with firstPage field works."""
    backend = EnterpriseGraphQLBackend()

    query = """
    query SearchPackages($searchString: String!, $first: Int!) {
        searchPackages(buckets: [], searchString: $searchString) {
            ... on PackagesSearchResultSet {
                firstPage(first: $first) {
                    hits { id name bucket hash }
                }
            }
        }
    }
    """

    variables = {"searchString": "test", "first": 5}
    result = await backend._execute_graphql_query(query, variables)

    # Should not have errors
    assert result.get("errors") is None or len(result["errors"]) == 0

    # Should have hits
    hits = result["data"]["searchPackages"]["firstPage"]["hits"]
    assert len(hits) > 0
    assert all("name" in hit for hit in hits)
```

### Integration Test

```python
async def test_graphql_package_search_end_to_end():
    """End-to-end test of GraphQL package search."""
    from quilt_mcp.tools.search import search_catalog

    # Search with GraphQL backend explicitly
    result = search_catalog(
        query="test",
        scope="global",
        backend="graphql",
        limit=10
    )

    assert result["status"] == "success"
    results = result["results"]

    # Should have multiple package results
    package_results = [r for r in results if r["type"] == "package"]
    assert len(package_results) > 0

    # Check package fields are populated
    pkg = package_results[0]
    assert pkg["title"] != "Unknown"
    assert pkg["package_name"] is not None
    assert "packages matching" not in pkg["title"]  # Not a summary
```

## Acceptance Criteria

- [ ] GraphQL package search returns individual packages, not summaries
- [ ] Each result has proper `type="package"` (not `"package_summary"`)
- [ ] Package names are in `title` and `package_name` fields
- [ ] Quilt+ URIs are properly constructed in `s3_uri`
- [ ] Pagination works with cursor-based navigation
- [ ] Results are comparable to Elasticsearch backend
- [ ] Unit tests verify correct result format
- [ ] Integration tests confirm end-to-end functionality
- [ ] Documentation explains GraphQL capabilities and limitations

## Related Issues

- `10-package-search-result-format.md` - Similar issue with Elasticsearch backend (different root cause)
- GraphQL schema `searchPackages` field definition
- Enterprise GraphQL server `firstPage` errors

## References

- [graphql.py:277-366](../../../src/quilt_mcp/search/backends/graphql.py#L277-L366) - Current implementation
- Enterprise GraphQL schema `SearchHitPackage` type
- `SearchResult` dataclass in [base.py](../../../src/quilt_mcp/search/backends/base.py)
- Elasticsearch backend package search for comparison
