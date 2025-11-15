# 06: Remove `filters` Parameter from `search_catalog`

## Problem

The `search_catalog` tool has a `filters` parameter that is:

1. **Redundant** - Natural language query parsing already extracts filters via regex
2. **Poor UX** - LLM agents struggle to construct valid nested dicts
3. **Type-unsafe** - MCP Inspector sends `""` (empty string) instead of `None`, causing runtime errors
4. **Undiscoverable** - Valid keys/values are not documented or validated
5. **Not LLM-friendly** - Requires explicit dict construction when query parsing already handles it

### Current Behavior

**Code:** [src/quilt_mcp/tools/search.py:78-84](src/quilt_mcp/tools/search.py#L78-L84)
```python
filters: Annotated[
    Optional[Dict[str, Any]],
    Field(
        default=None,
        description='Additional filters as dict - e.g., {"file_extensions": ["csv"], "size_gt": "100MB"}',
    ),
] = None,
```

**Problem:** When MCP Inspector sends `filters=""`, Python receives an empty string instead of `None`/dict, breaking type checking.

### Why It's Redundant

The query parser already extracts filters from natural language:

**Query:** `"CSV files larger than 100MB created after 2023-01-01"`

**Auto-extracted filters:**
```python
{
    "file_extensions": ["csv"],
    "size_min": 104857600,  # 100MB in bytes
    "created_after": "2023-01-01"
}
```

**Evidence:** [src/quilt_mcp/search/core/query_parser.py:162-176](src/quilt_mcp/search/core/query_parser.py#L162-L176)
```python
# Extract filters and parameters
keywords = self._extract_keywords(query_lower)
file_extensions = self._extract_file_extensions(query_lower)  # Regex
size_filters = self._extract_size_filters(query_lower)        # Regex
date_filters = self._extract_date_filters(query_lower)        # Regex

# Build filters dictionary
filters = {}
if file_extensions:
    filters["file_extensions"] = file_extensions
if size_filters:
    filters.update(size_filters)
if date_filters:
    filters.update(date_filters)
```

The explicit `filters` parameter **duplicates** what the query parser already provides.

## Solution

**Remove the `filters` parameter entirely** and rely on the natural language query parser.

### Why This Works

1. **Query parsing is comprehensive** - Handles file extensions, size ranges, date filters via regex patterns
2. **More intuitive for LLMs** - "Find CSV files larger than 100MB" vs constructing `{"file_extensions": ["csv"], "size_min": 104857600}`
3. **Type-safe** - No risk of empty strings or invalid dict structures
4. **Simpler API** - One less parameter to document/validate

### Migration Path

**Before:**
```python
search_catalog(
    query="genomics data",
    filters={"file_extensions": ["csv"], "size_min": 104857600}
)
```

**After:**
```python
search_catalog(
    query="CSV genomics data larger than 100MB"
)
```

## Implementation Plan

### 1. Remove `filters` Parameter

**File:** `src/quilt_mcp/tools/search.py`

**Changes:**
```python
def search_catalog(
    query: Annotated[str, Field(...)],
    scope: Annotated[str, Field(default="global")] = "global",
    target: Annotated[str, Field(default="")] = "",
    backend: Annotated[str, Field(default="auto")] = "auto",
    limit: Annotated[int, Field(default=50)] = 50,
    include_metadata: Annotated[bool, Field(default=True)] = True,
    include_content_preview: Annotated[bool, Field(default=False)] = False,
    explain_query: Annotated[bool, Field(default=False)] = False,
    # REMOVED: filters parameter
    count_only: Annotated[bool, Field(default=False)] = False,
) -> Dict[str, Any]:
```

**Remove `filters` from:**
- Function signature [line 78-84]
- Docstring [line 110]
- Example usage [line 120]
- Function call to `_unified_search()` [lines 160, 177]

### 2. Update Internal Implementation

**File:** `src/quilt_mcp/search/tools/unified_search.py`

**Changes:**
```python
async def unified_search(
    query: str,
    scope: str = "global",
    target: str = "",
    backend: Optional[str] = None,
    limit: int = 50,
    include_metadata: bool = True,
    include_content_preview: bool = False,
    explain_query: bool = False,
    # REMOVED: filters parameter
    count_only: bool = False,
) -> Dict[str, Any]:
```

**Remove filter merging logic** [lines 72-75]:
```python
# DELETE THIS:
# Merge filters from query analysis and explicit filters
combined_filters = {**analysis.filters}
if filters:
    combined_filters.update(filters)
```

**Replace with:**
```python
# Use only query-extracted filters
combined_filters = analysis.filters
```

### 3. Update UnifiedSearchEngine.search()

**File:** `src/quilt_mcp/search/tools/unified_search.py`

**Changes:**
```python
async def search(
    self,
    query: str,
    scope: str = "global",
    target: str = "",
    backend: Optional[str] = None,
    limit: int = 50,
    include_metadata: bool = True,
    include_content_preview: bool = False,
    explain_query: bool = False,
    # REMOVED: filters parameter
) -> Dict[str, Any]:
```

### 4. Update Tests

**Files to update:**
- `tests/integration/test_search_integration.py`
- `tests/unit/test_search_tools.py`
- Any tests using `filters={...}` parameter

**Change pattern:**
```python
# Before
result = search_catalog(
    query="data",
    filters={"file_extensions": ["csv"]}
)

# After
result = search_catalog(
    query="CSV data"
)
```

### 5. Update Documentation

**Files to update:**
- `README.md` - Remove `filters` from examples
- `docs/mcp-tools.md` - Remove `filters` documentation
- `docs/SEARCH.md` - Update search examples
- Tool descriptions in `search.py` docstrings

**Emphasize natural language capabilities:**
```markdown
## Search Examples

# File type filtering
search_catalog("CSV files in genomics packages")

# Size filtering
search_catalog("files larger than 100MB")

# Date filtering
search_catalog("packages created in the last 30 days")

# Combined filters
search_catalog("CSV files larger than 100MB created after 2023-01-01")
```

## Testing Strategy

### Unit Tests
- Verify `filters` parameter is removed from signature
- Test that query parsing still extracts filters correctly
- Ensure no regression in filter application logic

### Integration Tests
- Test natural language queries with various filter combinations
- Verify file extension filtering works via query parsing
- Test size and date filter extraction from queries

### Regression Tests
- Ensure existing search functionality remains intact
- Verify backend selection logic unchanged
- Test result aggregation and deduplication

## Benefits

1. **Simpler API** - One less parameter to document/explain
2. **Better UX** - Natural language is more intuitive than dict construction
3. **Type-safe** - No risk of invalid input types from MCP clients
4. **Cleaner code** - Removes filter merging logic
5. **More discoverable** - Query patterns documented in parser

## Affected Files

### Core Implementation
- `src/quilt_mcp/tools/search.py` - Remove parameter, update docstrings
- `src/quilt_mcp/search/tools/unified_search.py` - Remove parameter, simplify logic
- `src/quilt_mcp/search/tools/unified_search.py` - Remove from UnifiedSearchEngine

### Tests
- `tests/integration/test_search_integration.py` - Update test calls
- `tests/unit/test_search_tools.py` - Update test calls
- `tests/e2e/test_mcp_integration.py` - Update search examples

### Documentation
- `README.md` - Update search examples
- `docs/mcp-tools.md` - Remove filters documentation
- `docs/SEARCH.md` - Emphasize natural language capabilities

## Breaking Changes

**Yes** - This is a breaking change for clients using `filters={}` parameter.

**Migration:**
```python
# Old way (will break)
search_catalog(query="data", filters={"file_extensions": ["csv"]})

# New way
search_catalog(query="CSV data")
```

## Rollout Plan

1. ✅ Create spec (this document)
2. ✅ Update code to remove `filters` parameter
3. ✅ Update all tests to use natural language queries
4. ✅ Update documentation with natural language examples
5. ✅ Add migration guide to CHANGELOG
6. ✅ Bump minor version (breaking change)

## Status: COMPLETED

The `filters` parameter has been successfully removed from `search_catalog()`. All documentation has been updated to emphasize natural language query capabilities.

## Notes

- Query parser uses regex patterns (not LLM) - see [query_parser.py:64-141](src/quilt_mcp/search/core/query_parser.py#L64-L141)
- Parser is comprehensive: handles extensions, sizes, dates, keywords
- This makes the API more "AI-native" by preferring natural language over structured dicts
