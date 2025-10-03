# Search Types Architecture

## Overview

The Quilt MCP server implements two distinct search types to clearly differentiate between searching for packages (collections of files) and objects (individual files). This architecture provides users with precise control over their search operations and ensures they get the most relevant results for their specific needs.

## Search Types

### 1. Package Search (`search_type="packages"`)

**Purpose**: Search for collections/packages of files

**Use Cases**:
- Finding datasets or experiments
- Discovering research projects
- Locating curated data collections
- Browsing organized file groups

**Examples**:
```python
# Search for genomics datasets
search_packages("genomics datasets")

# Find machine learning packages in a specific catalog
search_packages("machine learning packages", scope="catalog")

# Look for datasets in a specific bucket
search_packages("datasets", scope="bucket", target="quilt-sandbox-bucket")
```

**Query Patterns**:
- "genomics datasets"
- "machine learning packages"
- "research projects"
- "curated collections"
- "experimental data"

### 2. Object Search (`search_type="objects"`)

**Purpose**: Search for individual files/objects

**Use Cases**:
- Finding specific file types (CSV, JSON, etc.)
- Locating configuration files
- Searching for documentation
- Finding data files by extension

**Examples**:
```python
# Search for CSV files
search_objects("CSV files")

# Find README files in a specific bucket
search_objects("README files", scope="bucket", target="quilt-sandbox-bucket")

# Look for large Parquet files
search_objects("*.parquet", filters={"size_gt": "100MB"})
```

**Query Patterns**:
- "CSV files"
- "README.md"
- "*.parquet"
- "configuration files"
- "data files"

## Implementation Details

### Auto-Detection Logic

When `search_type="auto"` (default), the system automatically detects the intended search type based on query content:

```python
def _is_file_or_object_query(self, query: str) -> bool:
    """Detect if a query is likely for files/objects vs packages/collections."""
    query_lower = query.lower()
    
    # File extension patterns
    file_extensions = ['.csv', '.json', '.parquet', '.tsv', '.txt', '.md', '.py', '.r', '.ipynb', 
                      '.h5', '.hdf5', '.zarr', '.nc', '.tif', '.tiff', '.png', '.jpg', '.jpeg']
    
    # File-specific keywords
    file_keywords = ['file', 'files', 'object', 'objects', 'data file', 'dataset file', 'readme', 'config']
    
    # Package/collection keywords
    package_keywords = ['package', 'packages', 'dataset', 'datasets', 'collection', 'collections', 
                       'project', 'projects', 'experiment', 'experiments', 'study', 'studies']
    
    # Detection logic...
```

### Search Strategy Selection

The GraphQL backend implements different search strategies based on the search type:

```python
if search_type == "packages":
    # Search only packages using packages() or searchPackages queries
    results = await self._search_packages_global(query, filters, limit, offset)
elif search_type == "objects":
    # Search only objects using objects() or searchObjects queries
    results = await self._search_objects_global(query, filters, limit, offset)
elif search_type == "both":
    # Search both packages and objects, combining results
    package_results = await self._search_packages_global(query, filters, limit // 2, offset // 2)
    object_results = await self._search_objects_global(query, filters, limit // 2, offset // 2)
    results = package_results + object_results
else:  # search_type == "auto"
    # Auto-detect and use appropriate strategy
    is_file_query = self._is_file_or_object_query(query)
    if is_file_query:
        results = await self._search_objects_global(query, filters, limit, offset)
    else:
        results = await self._search_packages_global(query, filters, limit, offset)
```

## API Reference

### Main Search Functions

#### `unified_search()`
The main search function with explicit search type control:

```python
async def unified_search(
    query: str,
    scope: str = "global",
    target: str = "",
    search_type: str = "auto",  # "auto", "packages", "objects", "both"
    backends: Optional[List[str]] = None,
    limit: int = 20,
    offset: int = 0,
    include_metadata: bool = False,
    include_content_preview: bool = False,
    explain_query: bool = False,
    filters: Optional[Dict[str, Any]] = None,
    count_only: bool = False,
) -> Dict[str, Any]:
```

#### `search_packages()`
Convenience function for package-only searches:

```python
async def search_packages(
    query: str,
    scope: str = "global",
    target: str = "",
    backends: Optional[List[str]] = None,
    limit: int = 20,
    offset: int = 0,
    include_metadata: bool = False,
    explain_query: bool = False,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
```

#### `search_objects()`
Convenience function for object-only searches:

```python
async def search_objects(
    query: str,
    scope: str = "global",
    target: str = "",
    backends: Optional[List[str]] = None,
    limit: int = 20,
    offset: int = 0,
    include_metadata: bool = False,
    explain_query: bool = False,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
```

### MCP Tool Actions

The search tool exposes these actions:

- `unified_search` - Main search with explicit type control
- `search_packages` - Package-only search
- `search_objects` - Object-only search
- `discover` - Search capabilities discovery
- `suggest` - Search suggestions

## Response Format

All search functions return a consistent response format:

```json
{
    "success": true,
    "query": "CSV files",
    "scope": "global",
    "target": "",
    "search_type": "objects",
    "results": [...],
    "total_results": 15,
    "limit": 20,
    "offset": 0,
    "has_more": false,
    "next_offset": null,
    "query_time_ms": 245.6,
    "backend": "graphql",
    "analysis": {
        "query_type": "file_search",
        "confidence": 0.95,
        "keywords": ["csv", "files"],
        "file_extensions": ["csv"],
        "filters_applied": {}
    }
}
```

## Pagination Support

All search functions support pagination through `limit` and `offset` parameters:

```python
# Get first page
results = search_objects("CSV files", limit=20, offset=0)

# Get second page
results = search_objects("CSV files", limit=20, offset=20)

# Get third page
results = search_objects("CSV files", limit=20, offset=40)
```

The response includes pagination metadata:
- `has_more`: Boolean indicating if more results are available
- `next_offset`: Suggested offset for the next page (null if no more results)
- `limit`: Number of results requested
- `offset`: Starting position of current page

## Best Practices

### When to Use Package Search
- Looking for complete datasets or experiments
- Browsing organized collections
- Finding research projects
- Discovering curated data

### When to Use Object Search
- Finding specific file types
- Locating configuration or documentation files
- Searching by file extension
- Finding individual data files

### When to Use Auto-Detection
- General searches where the intent is unclear
- Mixed queries that might return both packages and objects
- When you want the system to make the best guess

### When to Use Both
- Comprehensive searches across all content types
- When you want to see both packages and individual files
- Exploratory searches

## Migration Guide

### From Legacy Search

If you were using the old unified search without explicit types:

```python
# Old way (still works)
unified_search("CSV files")

# New explicit way
search_objects("CSV files")
# or
unified_search("CSV files", search_type="objects")
```

### Frontend Integration

Frontend applications should use the appropriate search type based on user intent:

```javascript
// Package search for dataset discovery
const packages = await mcpClient.callTool('search', 'search_packages', {
    query: 'genomics datasets',
    scope: 'global'
});

// Object search for file finding
const files = await mcpClient.callTool('search', 'search_objects', {
    query: 'CSV files',
    scope: 'bucket',
    target: 'quilt-sandbox-bucket'
});
```

## Performance Considerations

- **Package searches** are typically faster as they query fewer entities
- **Object searches** may be slower for large buckets with many files
- **Auto-detection** adds minimal overhead but provides better user experience
- **Pagination** is essential for large result sets to prevent timeouts

## Future Enhancements

- **Hybrid search**: Combine package and object results with intelligent ranking
- **Search suggestions**: Provide type-specific suggestions based on search history
- **Advanced filtering**: Type-specific filters (e.g., package metadata vs file properties)
- **Search analytics**: Track search patterns to improve auto-detection accuracy
