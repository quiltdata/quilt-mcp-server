# Search Catalog Scope Fixes

**Date:** 2025-01-11
**Branch:** search-catalog-fixes
**Status:** Correction to 08-scope-proposal.md
**Replaces:** Lines 249-254 and backend selection logic in 08-scope-proposal.md

---

## Issue 1: Incorrect Validation - Bucket-Scoped Package Search IS Supported

### Problem

The spec at [08-scope-proposal.md:249-254](08-scope-proposal.md#L249-L254) incorrectly rejects `scope="bucket"` + `entity="packages"`:

```python
# INCORRECT validation in 08-scope-proposal.md
if scope == "bucket" and entity == "packages":
    raise ValueError(
        "Cannot search packages within a specific bucket. "
        "Packages are catalog-wide entities. Use scope='catalog' or entity='objects'."
    )
```

### Evidence: Bucket-Scoped Package Search DOES Work

Looking at `quilt3.Bucket.search()` implementation ([quilt3/bucket.py:60](https://github.com/quiltdata/quilt/blob/main/api/python/quilt3/bucket.py#L60)):

```python
def search(self, query: T.Union[str, dict], limit: int = 10) -> T.List[dict]:
    """Execute a search against the configured search endpoint."""
    return search_api(
        query,
        index=f"{self._pk.bucket},{self._pk.bucket}_packages",  # ← Searches BOTH indices!
        limit=limit
    )["hits"]["hits"]
```

**Key insight**: `quilt3.Bucket.search()` searches **TWO** Elasticsearch indices:

1. `{bucket}` - object metadata index
2. `{bucket}_packages` - **package metadata index for that bucket**

### Elasticsearch Index Architecture

Each bucket in a Quilt stack has **two** Elasticsearch indices:

```
bucket-name           → S3 object metadata (files)
bucket-name_packages  → Package metadata (packages in this bucket)
```

This is confirmed in:

- [stack_buckets.py:134](../../src/quilt_mcp/tools/stack_buckets.py#L134): `indices.extend([bucket, f"{bucket}_packages"])`
- [elasticsearch.py:60](../../src/quilt_mcp/search/backends/elasticsearch.py#L60): Bucket.search() searches both indices

### Correct Behavior

**Bucket-scoped package search IS valid** and should be allowed:

```python
# CORRECT: Allow bucket-scoped package search
if scope == "bucket" and entity == "packages":
    # Search the {bucket}_packages index
    # This is supported by Elasticsearch backend
    pass
```

### Why This Matters

Valid use cases that were incorrectly rejected:

- "Show me all packages in bucket X"
- "Find packages matching query in specific bucket"
- Per-bucket package management and discovery

### Corrected Validation

```python
def search_catalog(
    query: str,
    entity: Literal["objects", "packages", "all"] = "objects",
    scope: Literal["bucket", "catalog"] = "catalog",
    target: Optional[str] = None,
    backend: str = "auto",  # NOT a user choice! See Issue 2
    limit: int = 50,
    **kwargs,
) -> Dict[str, Any]:
    # Validate target requirement
    if scope == "bucket" and target is None:
        raise ValueError(
            "target (bucket name) is required when scope='bucket'. "
            "Example: target='s3://my-bucket' or target='my-bucket'"
        )

    if scope == "catalog" and target is not None:
        logger.warning(
            f"target='{target}' is ignored when scope='catalog'. "
            "Catalog search spans all accessible buckets."
        )

    # REMOVED: Incorrect validation that rejected bucket + packages
    # Bucket-scoped package search IS supported via {bucket}_packages index

    # Entity + backend compatibility warning
    if entity == "all" and backend == "elasticsearch":
        logger.warning(
            "entity='all' with backend='elasticsearch' searches objects and packages "
            "separately. Results will be combined but may have inconsistent counts."
        )
```

---

## Issue 2: Backend Selection is NOT a Dynamic Choice

### Problem

The spec treats `backend` as a user-selectable parameter with runtime choices:

```python
# WRONG: Backend is NOT a dynamic runtime choice
backend: Literal["auto", "elasticsearch", "graphql"] = "auto"
```

This is incorrect. Backend selection is **static** based on what's available in the environment.

### Correct Backend Selection Logic

```python
# Backend selection happens ONCE at initialization, NOT per-query
def _select_backend() -> SearchBackend:
    """Select backend based on availability (static, not dynamic)."""

    # Try GraphQL first (if available in Enterprise)
    try:
        graphql_backend = GraphQLSearchBackend()
        if graphql_backend.verify_works():  # MUST verify it actually works
            logger.info("Using GraphQL backend (Enterprise)")
            return graphql_backend
    except Exception as e:
        logger.debug(f"GraphQL backend not available: {e}")

    # Fallback to Elasticsearch (always available if authenticated)
    try:
        es_backend = ElasticsearchBackend()
        if es_backend.verify_works():
            logger.info("Using Elasticsearch backend")
            return es_backend
    except Exception as e:
        logger.error(f"Elasticsearch backend not available: {e}")

    # No working backend
    raise BackendUnavailableError(
        "No search backend available. "
        "Ensure you are authenticated (quilt3.login()) and have search permissions."
    )

# Backend is selected once and reused
_BACKEND: Optional[SearchBackend] = None

def get_backend() -> SearchBackend:
    """Get the search backend (singleton pattern)."""
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = _select_backend()
    return _BACKEND
```

### Why Backend is NOT a User Choice

1. **Availability**: GraphQL is only present in Enterprise deployments
2. **Verification**: Must actually test that GraphQL works (not just check if module exists)
3. **Consistency**: All searches in a session should use the same backend
4. **Simplicity**: Users shouldn't need to understand backend differences

### Corrected API Signature

```python
def search_catalog(
    query: str,
    entity: Literal["objects", "packages", "all"] = "objects",
    scope: Literal["bucket", "catalog"] = "catalog",
    target: Optional[str] = None,
    limit: int = 50,
    detail_level: Literal["individual", "summary", "auto"] = "auto",
    include_metadata: bool = True,
    include_content_preview: bool = False,
    explain_query: bool = False,
    count_only: bool = False,
) -> Dict[str, Any]:
    """Search Quilt catalog.

    Backend is automatically selected based on availability:
    - GraphQL (if available and verified to work in Enterprise)
    - Elasticsearch (fallback, always available)

    Users do NOT specify backend - it's determined by environment.
    """
    backend = get_backend()  # NOT a parameter!

    return backend.search(
        query=query,
        entity=entity,
        scope=scope,
        target=target,
        limit=limit,
        detail_level=detail_level,
    )
```

### Backend Verification Protocol

Backend availability must be **verified**, not assumed:

```python
class SearchBackend(ABC):
    """Base class for search backends."""

    @abstractmethod
    def verify_works(self) -> bool:
        """Verify backend is available and functional.

        This MUST actually test backend functionality, not just check imports.

        Returns:
            True if backend is ready to use
        """
        pass

class GraphQLSearchBackend(SearchBackend):
    """GraphQL search backend (Enterprise only)."""

    def verify_works(self) -> bool:
        """Verify GraphQL endpoint is accessible and responding."""
        try:
            # 1. Check session is available
            if not self.quilt_service.has_session_support():
                return False

            # 2. Get registry URL
            registry_url = self.quilt_service.get_registry_url()
            if not registry_url:
                return False

            # 3. Actually test GraphQL with a simple query
            test_query = {"query": "{ __typename }"}
            session = self.quilt_service.get_session()
            graphql_url = urljoin(registry_url.rstrip("/") + "/", "graphql")

            response = session.post(graphql_url, json=test_query, timeout=5)

            # 4. Must get 200 with valid JSON response
            if response.status_code != 200:
                return False

            data = response.json()
            return "data" in data and "__typename" in data["data"]

        except Exception as e:
            logger.debug(f"GraphQL verification failed: {e}")
            return False

class ElasticsearchBackend(SearchBackend):
    """Elasticsearch search backend (standard)."""

    def verify_works(self) -> bool:
        """Verify Elasticsearch search API is accessible."""
        try:
            # 1. Check authentication
            if not self.quilt_service.is_authenticated():
                return False

            # 2. Try to get search API
            search_api = self.quilt_service.get_search_api()

            # 3. Test with simple query
            test_result = search_api(
                query={"query": {"match_all": {}}, "size": 0},
                index="*",
                limit=0
            )

            # 4. Must get valid response
            return "hits" in test_result

        except Exception as e:
            logger.debug(f"Elasticsearch verification failed: {e}")
            return False
```

### Impact on Unified Search Implementation

The current `unified_search.py` implementation already partially follows this pattern but needs correction:

```python
# Current (PARTIALLY CORRECT)
class UnifiedSearch:
    def __init__(self):
        self.backends = [
            Quilt3ElasticsearchBackend(),
            GraphQLSearchBackend(),
        ]

    async def search(self, ...):
        # Tries each backend until one works
        for backend in self.backends:
            try:
                return await backend.search(...)
            except:
                continue

# Should be (FULLY CORRECT)
class UnifiedSearch:
    def __init__(self):
        self._backend: Optional[SearchBackend] = None
        self._select_backend()

    def _select_backend(self):
        """Select backend once at initialization."""
        # Try GraphQL first (if Enterprise)
        graphql = GraphQLSearchBackend()
        if graphql.verify_works():
            self._backend = graphql
            logger.info("Using GraphQL backend")
            return

        # Fallback to Elasticsearch
        es = ElasticsearchBackend()
        if es.verify_works():
            self._backend = es
            logger.info("Using Elasticsearch backend")
            return

        raise BackendUnavailableError("No working search backend found")

    async def search(self, ...):
        """Use the selected backend (no fallback per-query)."""
        if self._backend is None:
            raise BackendUnavailableError("Backend not initialized")

        return await self._backend.search(...)
```

---

## Summary of Changes Required

### 1. Remove Incorrect Validation

**File**: `spec/a07-search-catalog/08-scope-proposal.md:249-254`

**Action**: DELETE lines that reject `scope="bucket"` + `entity="packages"`

**Reason**: Bucket-scoped package search IS supported via `{bucket}_packages` index

### 2. Remove Backend Parameter from User API

**Files**:

- `spec/a07-search-catalog/08-scope-proposal.md` (multiple locations)
- `src/quilt_mcp/tools/search.py`

**Action**: Remove `backend` parameter from public API signature

**Reason**: Backend selection is static, not dynamic

### 3. Implement Backend Verification

**File**: `src/quilt_mcp/search/backends/base.py`

**Action**: Add `verify_works()` abstract method

**File**: `src/quilt_mcp/search/backends/elasticsearch.py`, `graphql.py`

**Action**: Implement `verify_works()` with actual backend testing

### 4. Implement Static Backend Selection

**File**: `src/quilt_mcp/search/tools/unified_search.py`

**Action**: Select backend once at initialization, not per-query

**File**: `src/quilt_mcp/tools/search.py`

**Action**: Use singleton backend instance

---

## Migration Impact

### Breaking Changes

1. **Removed validation**: `scope="bucket"` + `entity="packages"` now allowed
   - **Impact**: Previously rejected calls will now work
   - **Risk**: Low (this makes API more permissive)

2. **Removed `backend` parameter**: Users can no longer specify backend
   - **Impact**: Calls with explicit `backend` parameter will error
   - **Mitigation**: Add deprecation warning first, then remove in v2.0

### Migration Path

```python
# OLD (will be deprecated)
search_catalog(query="test", scope="bucket", entity="packages", backend="elasticsearch")

# NEW (correct)
search_catalog(query="test", scope="bucket", entity="packages")
# Backend is automatically selected based on what's available
```

---

## Testing Requirements

### 1. Bucket-Scoped Package Search

```python
def test_bucket_scoped_package_search():
    """Verify bucket + packages combination works."""
    result = search_catalog(
        query="*",
        entity="packages",
        scope="bucket",
        target="s3://test-bucket",
    )

    assert result["success"] is True
    assert all(r["type"] == "package" for r in result["results"])
    # All packages should be from the target bucket
```

### 2. Backend Verification

```python
def test_graphql_verification():
    """Verify GraphQL backend correctly identifies availability."""
    backend = GraphQLSearchBackend()

    # Should actually test GraphQL endpoint
    is_available = backend.verify_works()

    if is_available:
        # If available, must actually work
        result = backend.search(query="*", entity="packages", scope="catalog", limit=1)
        assert result is not None

def test_backend_selection_priority():
    """Verify GraphQL is preferred over Elasticsearch when available."""
    search = UnifiedSearch()

    # If GraphQL works, it should be selected
    if GraphQLSearchBackend().verify_works():
        assert isinstance(search._backend, GraphQLSearchBackend)
    else:
        assert isinstance(search._backend, ElasticsearchBackend)
```

### 3. Backend Stability

```python
def test_backend_doesnt_change_per_query():
    """Verify backend selection is stable across queries."""
    search = UnifiedSearch()

    backend1 = search._backend
    search.search(query="test1", entity="packages", scope="catalog")
    backend2 = search._backend

    assert backend1 is backend2  # Same instance
```

---

## Documentation Updates Required

### 1. User-Facing Docs

**Remove all references to `backend` parameter** from user documentation.

Replace:

```markdown
### `backend` (optional)
Choose search backend:
- `"auto"` (default): Automatically select
- `"elasticsearch"`: Use Elasticsearch
- `"graphql"`: Use GraphQL
```

With:

```markdown
### Backend Selection (Automatic)

The search backend is automatically selected based on your Quilt deployment:

- **GraphQL**: Used automatically in Enterprise deployments (preferred)
- **Elasticsearch**: Used in all other deployments (fallback)

You do not need to (and cannot) specify which backend to use.
```

### 2. Architecture Docs

Add section explaining backend selection logic:

```markdown
## Search Backend Architecture

### Backend Selection

Backend selection happens **once** when the search system initializes:

1. **Try GraphQL** (Enterprise only)
   - Check if GraphQL endpoint exists
   - Verify it responds to test query
   - Use if available and working

2. **Fallback to Elasticsearch** (standard)
   - Check if user is authenticated
   - Verify search API is accessible
   - Use as fallback

3. **Error if neither works**
   - Report authentication or permission issues
   - Guide user to resolve access problems

### Why Not Dynamic?

Backend is NOT selected per-query because:

- **Consistency**: All searches in a session should behave the same
- **Performance**: Avoid overhead of checking backend every query
- **Simplicity**: Users don't need to understand backend differences
- **Correctness**: Prevent fallback behavior that masks deployment issues
```

---

**End of Document**
