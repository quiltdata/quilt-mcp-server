# Search Explain Action

The `explain` action for the `search` tool provides detailed analysis of how search queries are interpreted and processed by the search engine.

## Overview

The `explain` action helps users understand:
- How their query is classified (file search, package discovery, etc.)
- What keywords and filters are extracted
- Which backends will be used for the search
- What search strategy will be employed
- Recommendations for improving the query

## Usage

### Basic Usage

```python
from quilt_mcp.tools.search import search

# Explain a simple query
result = await search(
    action="explain",
    params={"query": "CSV files"}
)
```

### Via MCP Tool

```python
# Call through MCP
result = await search(action="explain", params={
    "query": "CSV files larger than 100MB"
})
```

## Response Format

The `explain` action returns a detailed analysis:

```python
{
    "success": True,
    "query": "CSV files larger than 100MB",
    "analysis": {
        "query_type": "analytical_search",
        "query_type_description": "Analytical query (size, count, aggregations)",
        "scope": "global",
        "keywords": ["csv", "larger", "100mb"],
        "file_extensions": ["csv"],
        "filters": {
            "file_extensions": ["csv"],
            "size_filters": {
                "size_min": 104857600
            },
            "date_filters": {}
        },
        "suggested_backends": ["elasticsearch", "graphql", "s3"],
        "confidence": 0.8
    },
    "execution_plan": {
        "backends": ["elasticsearch", "graphql", "s3"],
        "search_strategy": "Search for individual files/objects matching the criteria with extensions: csv and size constraints",
        "expected_result_types": ["aggregated_results", "statistics"]
    },
    "recommendations": [
        "Consider narrowing the search scope to a specific catalog or bucket for faster results"
    ]
}
```

## Examples

### Example 1: File Search with Size Filter

```python
result = await search(
    action="explain",
    params={"query": "CSV files larger than 100MB"}
)

# Analysis will show:
# - Query type: analytical_search
# - File extensions: ["csv"]
# - Size filter: size_min = 104857600 bytes
# - Recommended backends: elasticsearch, graphql, s3
```

### Example 2: Package Discovery

```python
result = await search(
    action="explain",
    params={"query": "genomics packages created in 2024"}
)

# Analysis will show:
# - Query type: package_discovery
# - Keywords: ["genomics", "created", "2024"]
# - Date filters: created_after = "2024-01-01", created_before = "2024-12-31"
# - Expected results: packages, collections
```

### Example 3: Wildcard Pattern

```python
result = await search(
    action="explain",
    params={"query": "*.parquet"}
)

# Analysis will show:
# - Query type: file_search
# - File extensions: ["parquet"]
# - Recommendations: Consider narrowing scope, add more filters
```

## Query Types

The explain action classifies queries into these types:

1. **file_search** - Searching for individual files/objects
   - Examples: "CSV files", "README.md", "*.json"

2. **package_discovery** - Discovering packages/collections
   - Examples: "genomics packages", "machine learning datasets"

3. **content_search** - Searching within file contents
   - Examples: "files containing 'RNA-seq'", "text search for cancer"

4. **metadata_search** - Searching based on metadata
   - Examples: "packages created by John", "files with tag genomics"

5. **analytical_search** - Analytical queries with aggregations
   - Examples: "largest files", "files bigger than 10GB", "count of CSV files"

6. **cross_catalog** - Searches across multiple catalogs
   - Examples: "compare datasets across catalogs"

## Confidence Score

The confidence score (0.0 to 1.0) indicates how well the query parser understood the query:

- **0.9-1.0**: High confidence - query is clear and specific
- **0.7-0.8**: Good confidence - query is reasonably clear
- **0.5-0.6**: Medium confidence - query may be ambiguous
- **< 0.5**: Low confidence - consider adding more specific terms

## Use Cases

1. **Query Debugging** - Understand why a query returns unexpected results
2. **Query Optimization** - Get recommendations for improving search performance
3. **Learning Tool** - Understand how the search engine interprets different queries
4. **API Development** - Build search UIs with query preview/explanation

## Integration with Issue #206

This feature resolves [GitHub Issue #206](https://github.com/quiltdata/quilt-mcp-server/issues/206) by implementing the `explain` action that was previously listed in the docstring but not implemented.

The implementation:
- ✅ Returns structured query analysis
- ✅ Provides execution plan details
- ✅ Offers recommendations for improvement
- ✅ Integrates with existing query parser
- ✅ Available in discovery mode
- ✅ Callable by clients

## Testing

See `tests/unit/test_search_stateless.py` for comprehensive test coverage:

```python
# Test basic functionality
result = await search.search(
    action="explain",
    params={"query": "CSV files larger than 100MB"}
)
assert result["success"] is True
assert "csv" in result["analysis"]["file_extensions"]

# Test error handling
result = await search.search(
    action="explain",
    params={}  # Missing query
)
assert result["success"] is False
assert "query" in result["error"].lower()
```

## Related Documentation

- [Search Tools Overview](./TOOLS.md#search)
- [Query Parser](../../src/quilt_mcp/search/core/query_parser.py)
- [Issue #206](https://github.com/quiltdata/quilt-mcp-server/issues/206)

