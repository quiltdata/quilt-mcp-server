# Search Catalog Simplified API - v0.9.0 Breaking Change

**Date:** 2025-01-11
**Branch:** search-catalog-fixes
**Status:** Implementation Spec
**Version:** 0.9.0 (Breaking Change)

---

## Executive Summary

**This is a BREAKING CHANGE for v0.9.0. No backward compatibility.**

Simple, clear API that matches what the backends actually do:

```python
def search_catalog(
    query: str,
    scope: Literal["global", "packages", "bucket"] = "global",
    target: Optional[str] = None,
    limit: int = 50,
    count_only: bool = False,
    include_metadata: bool = True,
    explain_query: bool = False,
) -> Dict[str, Any]:
    """Search Quilt catalog.

    Scope determines what gets searched:
    - "global": All buckets, all entities (objects + packages)
    - "packages": Packages only (across all accessible buckets)
    - "bucket": Specific bucket (objects + packages, requires target)

    Backend is automatically selected (GraphQL preferred, Elasticsearch fallback).

    Args:
        query: Search query string
        scope: Search scope (global, packages, bucket)
        target: Target bucket for scope="bucket"
        limit: Maximum results to return
        count_only: Return count only (no results)
        include_metadata: Include metadata in results (default True)
        explain_query: Include query explanation in response (default False)
    """
```

**That's it.** Three simple scopes, clear behavior, no confusion.

---

## Scope Behavior (Simple Truth)

### `scope="global"` (Default)

- **Searches**: All accessible buckets
- **Returns**: Both objects AND packages
- **Use**: "Find anything matching X across everything"
- **Backend**: GraphQL (if available), else Elasticsearch with stack indices

### `scope="packages"`

- **Searches**: All accessible buckets
- **Returns**: Packages only
- **Use**: "Find packages by name/metadata"
- **Backend**: Elasticsearch `*_packages` indices or GraphQL searchPackages

### `scope="bucket"`

- **Searches**: Specific bucket (requires `target`)
- **Returns**: Objects AND packages in that bucket
- **Use**: "Find files/packages in bucket X"
- **Backend**: Elasticsearch `{bucket},{bucket}_packages` indices

---

## Backend Selection (Cached with Auto-Reset on Failure)

```python
# Backend cached, reset automatically on any failure
_BACKEND: Optional[SearchBackend] = None

def _select_backend() -> SearchBackend:
    """Select backend based on availability."""

    # Try GraphQL first (Enterprise only)
    if GraphQLBackend().verify_works():
        return GraphQLBackend()

    # Fallback to Elasticsearch
    if ElasticsearchBackend().verify_works():
        return ElasticsearchBackend()

    raise BackendUnavailableError("No search backend available")

def get_backend() -> SearchBackend:
    """Get cached backend (or select if not cached)."""
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = _select_backend()
    return _BACKEND

def reset_backend():
    """Reset backend cache (forces re-selection next time)."""
    global _BACKEND
    _BACKEND = None

async def search_with_retry(
    query: str,
    scope: str,
    target: Optional[str],
    limit: int,
    count_only: bool,
    include_metadata: bool,
    explain_query: bool,
):
    """Execute search with automatic backend reset on failure."""
    try:
        backend = get_backend()
        return await backend.search(query, scope, target, limit, count_only, include_metadata, explain_query)
    except Exception as e:
        # Reset backend and retry once
        reset_backend()
        try:
            backend = get_backend()
            return await backend.search(query, scope, target, limit, count_only, include_metadata, explain_query)
        except Exception:
            # Re-raise original error if retry fails
            raise e
```

**Key points:**

- Backend cached for performance (not re-selected per-query)
- **Automatically reset on any search failure**
- Retry once with fresh backend after reset
- GraphQL preferred (if available and working)
- Elasticsearch fallback
- Users don't specify backend
- Handles auth changes, catalog switches, deployment changes automatically

---

## Implementation

### Parameter Validation

```python
def search_catalog(
    query: str,
    scope: Literal["global", "packages", "bucket"] = "global",
    target: Optional[str] = None,
    limit: int = 50,
    count_only: bool = False,
    include_metadata: bool = True,
    explain_query: bool = False,
) -> Dict[str, Any]:

    # Validate target for bucket scope
    if scope == "bucket" and target is None:
        target = constants.DEFAULT_BUCKET

    # That's it. Simple.
    backend = get_backend()
    return backend.search(query, scope, target, limit, count_only, include_metadata, explain_query)
```

### Backend Interface

```python
class SearchBackend(ABC):
    """Base search backend interface."""

    @abstractmethod
    def verify_works(self) -> bool:
        """Test if backend is available and functional."""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        scope: str,
        target: Optional[str],
        limit: int,
        count_only: bool,
        include_metadata: bool,
        explain_query: bool,
    ) -> BackendResponse:
        """Execute search query."""
        pass
```

### Elasticsearch Implementation

```python
class ElasticsearchBackend(SearchBackend):

    async def search(
        self,
        query: str,
        scope: str,
        target: Optional[str],
        limit: int,
        count_only: bool,
        include_metadata: bool,
        explain_query: bool,
    ):
        if scope == "bucket":
            # Search bucket objects + packages
            return await self._search_bucket(query, target, limit, include_metadata)

        elif scope == "packages":
            # Search packages only
            return await self._search_packages(query, limit, include_metadata)

        else:  # scope == "global"
            # Search all buckets, all entities
            return await self._search_global(query, limit, include_metadata)

    async def _search_bucket(self, query: str, bucket: str, limit: int):
        """Search specific bucket (objects + packages)."""
        # Uses: index="{bucket},{bucket}_packages"
        ...

    async def _search_packages(self, query: str, limit: int):
        """Search packages only."""
        # Uses: index="*_packages"
        ...

    async def _search_global(self, query: str, limit: int):
        """Search all buckets, all entities."""
        # Uses: index=build_stack_search_indices()
        # Returns: objects + packages from all accessible buckets
        ...
```

### GraphQL Implementation

```python
class GraphQLBackend(SearchBackend):

    async def search(
        self,
        query: str,
        scope: str,
        target: Optional[str],
        limit: int,
        count_only: bool,
        include_metadata: bool,
        explain_query: bool,
    ):
        if scope == "bucket":
            # Search bucket objects via GraphQL
            return await self._search_bucket_objects(query, target, limit, include_metadata)

        elif scope == "packages":
            # Search packages via searchPackages
            return await self._search_packages(query, limit, include_metadata)

        else:  # scope == "global"
            # Search both objects and packages
            objects = await self._search_objects_global(query, limit // 2, include_metadata)
            packages = await self._search_packages(query, limit // 2, include_metadata)
            return self._combine_results(objects, packages)
```

---

## Result Format

Simple, consistent result structure:

```python
{
    "success": True,
    "query": "*.csv",
    "scope": "global",
    "results": [
        {
            "type": "object",  # or "package"
            "title": "data.csv",
            "s3_uri": "s3://bucket/data.csv",  # objects only
            "package_name": "user/dataset",     # packages only
            "score": 1.0,
            "metadata": {...}  # Only if include_metadata=True
        },
        ...
    ],
    "total": 42,
    "query_time_ms": 156.3,
    "backend": "elasticsearch",  # or "graphql"
    "explanation": {...}  # Only if explain_query=True
}
```

### Context Management Parameters

**`include_metadata` (default: True)**

- Controls whether rich metadata is included in result objects
- Set to `False` for lightweight responses when you only need basic info (title, URI)
- Useful for context management when you want to minimize token usage
- Example: List of files vs. detailed file information

**`explain_query` (default: False)**

- When `True`, includes query execution details in response
- Shows backend selection reasoning, index selection, query parsing
- Useful for debugging and understanding how searches work
- Adds `explanation` field to response with execution details

---

## Examples

### Global Search (Everything)

```python
# Find anything matching "genomics"
result = search_catalog(
    query="genomics",
    scope="global"
)
# Returns: objects + packages from all buckets
```

### Package Search (Packages Only)

```python
# Find packages by name
result = search_catalog(
    query="user/dataset",
    scope="packages"
)
# Returns: packages only
```

### Bucket Search (Files in Specific Bucket)

```python
# Find CSV files in bucket
result = search_catalog(
    query="*.csv",
    scope="bucket",
    target="s3://my-bucket"
)
# Returns: objects + packages in that bucket
```

### Count Only (Fast)

```python
# Get count without fetching results
result = search_catalog(
    query="*.csv",
    scope="global",
    count_only=True
)
# Returns: {"total": 1234, "results": []}
```

### Context Management Examples

```python
# Lightweight search (minimal tokens)
result = search_catalog(
    query="*.csv",
    scope="global",
    include_metadata=False  # Just titles and URIs
)
# Returns: Minimal results without full metadata

# Debug query execution
result = search_catalog(
    query="complex query",
    scope="global",
    explain_query=True  # Include execution details
)
# Returns: Results + explanation of backend selection and query processing
```

---

## Migration from Old API

**This is v0.9.0 - BREAKING CHANGE. Update ALL TESTS.**

### Old → New

```python
# OLD (v0.8.x) - REMOVE ALL entity/detail_level/backend parameters
search_catalog(
    query="test",
    entity="packages",
    scope="catalog",
    backend="elasticsearch",
    detail_level="individual"
)

# NEW (v0.9.0) - Simple
search_catalog(
    query="test",
    scope="packages"  # Searches packages only
)
```

```python
# OLD - Complex entity + scope combinations
search_catalog(query="*.csv", entity="objects", scope="bucket", target="s3://bucket")

# NEW - Just scope + target
search_catalog(query="*.csv", scope="bucket", target="s3://bucket")
```

```python
# OLD - entity="all" for everything
search_catalog(query="test", entity="all", scope="catalog")

# NEW - scope="global" for everything
search_catalog(query="test", scope="global")
```

### Kept Parameters

- ✅ `query` - Required
- ✅ `scope` - Optional (default "global")
- ✅ `target` - Optional (defaults to DEFAULT_BUCKET when scope="bucket")
- ✅ `limit` - Optional (default 50)
- ✅ `count_only` - Optional (default False)
- ✅ `include_metadata` - Optional (default True) - Include metadata in results
- ✅ `explain_query` - Optional (default False) - Include query explanation

---

## Testing

### Basic Functionality

```python
def test_global_search():
    """Test global search returns objects + packages."""
    result = search_catalog(query="*", scope="global", limit=10)

    assert result["success"] is True
    assert result["scope"] == "global"
    types = {r["type"] for r in result["results"]}
    # Should have both objects and packages (if any exist)

def test_packages_search():
    """Test packages search returns packages."""
    result = search_catalog(query="*", scope="packages", limit=10)

    assert result["success"] is True
    assert all(r["type"] == "package" for r in result["results"])

def test_bucket_search():
    """Test bucket search returns objects + packages in bucket."""
    result = search_catalog(
        query="*",
        scope="bucket",
        target="s3://test-bucket",
        limit=10
    )

    assert result["success"] is True
    assert result["scope"] == "bucket"

def test_bucket_requires_target():
    """Test bucket scope requires target parameter."""
    with pytest.raises(ValueError, match="target.*required"):
        search_catalog(query="*", scope="bucket")

def test_count_only():
    """Test count_only returns total without results."""
    result = search_catalog(query="*", scope="global", count_only=True)

    assert "total" in result
    assert len(result["results"]) == 0
```

### Backend Selection and Retry

```python
def test_backend_cached():
    """Test backend is cached, not re-selected per-query."""
    backend1 = get_backend()
    search_catalog(query="test1")
    backend2 = get_backend()

    assert backend1 is backend2  # Same instance (cached)

def test_backend_reset():
    """Test reset_backend clears cache."""
    backend1 = get_backend()
    reset_backend()
    backend2 = get_backend()

    # Should be different instance (re-selected)
    assert backend1 is not backend2

def test_search_retry_on_failure():
    """Test search automatically resets backend and retries on failure."""
    # First call fails, retry succeeds
    mock_backend = Mock()
    mock_backend.search.side_effect = [
        Exception("Auth error"),  # First attempt fails
        {"success": True, "results": []}  # Retry succeeds
    ]

    with patch('get_backend', side_effect=[mock_backend, mock_backend]):
        result = await search_with_retry("test", "global", None, 10, False)

    assert result["success"] is True
    assert mock_backend.search.call_count == 2  # Called twice (original + retry)

def test_search_retry_reraises_on_second_failure():
    """Test search re-raises original error if retry also fails."""
    mock_backend = Mock()
    original_error = Exception("Auth error")
    mock_backend.search.side_effect = [
        original_error,  # First attempt fails
        Exception("Still broken")  # Retry also fails
    ]

    with patch('get_backend', side_effect=[mock_backend, mock_backend]):
        with pytest.raises(Exception, match="Auth error"):
            await search_with_retry("test", "global", None, 10, False)

def test_graphql_preferred():
    """Test GraphQL is used when available."""
    reset_backend()  # Clear cache
    if GraphQLBackend().verify_works():
        backend = get_backend()
        assert isinstance(backend, GraphQLBackend)
    else:
        backend = get_backend()
        assert isinstance(backend, ElasticsearchBackend)
```

---

## Documentation

### Quick Start

```markdown
# Search Quilt Catalog

## Basic Usage

```python
from quilt_mcp.tools.search import search_catalog

# Search everything
results = search_catalog(query="genomics")

# Search packages
results = search_catalog(query="user/dataset", scope="packages")

# Search specific bucket
results = search_catalog(
    query="*.csv",
    scope="bucket",
    target="s3://my-bucket"
)
```

## Scope Parameter

- **`global`** (default): Search all buckets, return objects + packages
- **`packages`**: Search packages only (all accessible buckets)
- **`bucket`**: Search specific bucket (requires `target`)

## Backend

Backend is automatically selected:

- **GraphQL** (if available in Enterprise)
- **Elasticsearch** (fallback)

You don't choose the backend - it's automatic.

```


## Breaking Changes Summary

**Version: 0.9.0**

### Removed
- `entity` parameter (scope determines what's searched)
- `backend` parameter (automatic selection)
- `detail_level` parameter (not needed)
- `include_content_preview` parameter (not implemented)

### Changed
- `scope="package"` → Removed (was broken)
- `scope="catalog"` → Renamed to `scope="packages"` (clearer)
- `scope` values: now "global", "packages", "bucket" only
- Backend selection now static (once per session)

### Added
- `count_only` parameter (efficient count queries)
- Automatic backend selection with verification

### Migration
```python
# OLD
search_catalog(query="test", entity="packages", scope="catalog", backend="elasticsearch")

# NEW
search_catalog(query="test", scope="packages")
```

---

**End of Document**
