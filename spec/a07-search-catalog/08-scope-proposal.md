# Search Catalog Scope Redesign Proposal

**Date:** 2025-11-11
**Branch:** search-catalog-fixes
**Status:** Proposal - Not Yet Implemented
**Depends On:** 07-scope-issues.md

---

## Executive Summary

This document proposes a redesigned API for `search_catalog` that separates concerns, eliminates ambiguity, and provides predictable behavior across backends. The proposal includes backward compatibility strategy and incremental migration path.

### Design Goals

1. **Clarity**: Parameter names match what they search
2. **Predictability**: Same parameters return same entity types regardless of backend
3. **Completeness**: All backend capabilities are accessible
4. **Type Safety**: Parameters are validated and well-typed
5. **Backward Compatibility**: Existing code continues to work with deprecation warnings

---

## Proposed API Design

### Option A: Separate Entity Type and Scope (RECOMMENDED)

```python
def search_catalog(
    query: str,
    entity: Literal["objects", "packages", "all"] = "objects",
    scope: Literal["bucket", "catalog"] = "catalog",
    target: Optional[str] = None,
    backend: Literal["auto", "elasticsearch", "graphql"] = "auto",
    limit: int = 50,
    detail_level: Literal["individual", "summary", "auto"] = "auto",
    include_metadata: bool = True,
    include_content_preview: bool = False,
    explain_query: bool = False,
) -> Dict[str, Any]:
    """Search Quilt catalog with explicit control over what and where to search.

    Args:
        query: Search query string
        entity: What to search for:
            - "objects": Search for files/objects
            - "packages": Search for Quilt packages
            - "all": Search both objects and packages
        scope: Where to search:
            - "bucket": Search within specific bucket (requires target)
            - "catalog": Search across entire catalog
        target: Bucket name (when scope="bucket") or None
        backend: Search backend to use (auto-selected if "auto")
        limit: Maximum number of results
        detail_level: Result detail level:
            - "individual": Return individual items (default for Elasticsearch)
            - "summary": Return aggregated statistics (default for GraphQL catalog search)
            - "auto": Let backend choose (recommended)
        include_metadata: Include rich metadata in results
        include_content_preview: Include content previews
        explain_query: Include query execution explanation

    Returns:
        Search results with clear entity type indicators

    Examples:
        # Search for CSV files across all buckets
        search_catalog(query="*.csv", entity="objects", scope="catalog")

        # Search for packages by name
        search_catalog(query="genomics", entity="packages", scope="catalog")

        # Search for files in specific bucket
        search_catalog(query="data", entity="objects", scope="bucket", target="s3://my-bucket")

        # Search everything (objects + packages)
        search_catalog(query="experiment", entity="all", scope="catalog")
    """
```

#### Key Changes from Current API

**1. New `entity` parameter** - Explicitly specifies what to search:

- Replaces implicit entity type selection via scope
- Clear naming: "objects" and "packages" instead of "bucket" and "catalog"
- Supports "all" for combined search

**2. Simplified `scope` parameter** - Only describes where to search:

- "bucket" = within specific bucket (requires target)
- "catalog" = across entire catalog
- Removes "global" (redundant with "catalog")
- Removes "package" (broken and unclear)

**3. Optional `target` parameter** - Type-safe targeting:

- Defaults to DEFAULT_BUCKET when scope = bucket
- Validated based on scope
- Clear error messages when missing or invalid

**4. New `detail_level` parameter** - Controls result format:

- "individual" = list of individual items (files, packages)
- "summary" = aggregated statistics
- "auto" = backend chooses appropriate level (recommended)

**5. Removed ambiguity**:

- No more scope values that mean different things per backend
- No more guessing what type of results you'll get
- No more silent fallbacks

### Option B: Separate Search Functions

```python
def search_objects(
    query: str,
    scope: Literal["bucket", "catalog"] = "catalog",
    bucket: Optional[str] = None,
    backend: Literal["auto", "elasticsearch", "graphql"] = "auto",
    limit: int = 50,
    **kwargs,
) -> ObjectSearchResults:
    """Search for objects (files) in Quilt catalog.

    Args:
        query: Search query string
        scope: "bucket" (specific bucket) or "catalog" (all buckets)
        bucket: Bucket name (required when scope="bucket")
        backend: Search backend to use
        limit: Maximum number of results

    Returns:
        List of matching objects with S3 URIs, sizes, etc.
    """


def search_packages(
    query: str,
    backend: Literal["auto", "elasticsearch", "graphql"] = "auto",
    limit: int = 50,
    **kwargs,
) -> PackageSearchResults:
    """Search for Quilt packages in catalog.

    Args:
        query: Search query string
        backend: Search backend to use
        limit: Maximum number of results

    Returns:
        List of matching packages with names, versions, etc.
    """


def search_catalog_unified(
    query: str,
    scope: Literal["catalog"] = "catalog",
    backend: Literal["auto", "graphql"] = "auto",
    limit: int = 50,
    **kwargs,
) -> UnifiedSearchResults:
    """Search for both objects and packages across catalog.

    Note: This is only supported by GraphQL backend.
    Elasticsearch users should call search_objects() and search_packages() separately.

    Args:
        query: Search query string
        scope: Must be "catalog" (objects+packages catalog-wide only)
        backend: Search backend to use (graphql recommended)
        limit: Maximum number of results

    Returns:
        Combined results with both objects and packages
    """
```

#### Key Changes from Current API

**Pros:**

- Crystal clear what each function does
- Type-safe return values (typed result objects)
- No ambiguous parameters
- Backend capabilities explicit in function availability

**Cons:**

- More API surface to document
- Requires calling multiple functions for "search everything"
- Migration requires changing function names, not just parameters

---

## Comparison of Options

| Aspect | Option A (Single Function) | Option B (Multiple Functions) |
|--------|---------------------------|------------------------------|
| **API Surface** | Smaller (1 function) | Larger (3 functions) |
| **Clarity** | Good (via entity parameter) | Excellent (function names) |
| **Migration** | Easier (parameter changes) | Harder (function name changes) |
| **Type Safety** | Good (with typed dicts) | Excellent (typed result classes) |
| **Backend Abstraction** | Better (hidden from user) | Exposed (some functions backend-specific) |
| **Documentation** | Single docstring | Multiple docstrings |
| **Backward Compat** | Can wrap old API easily | Requires more wrapper logic |

**Recommendation: Option A** - Better balance of clarity, backward compatibility, and API simplicity.

---

## Detailed Design: Option A

### Parameter Validation

```python
def search_catalog(
    query: str,
    entity: Literal["objects", "packages", "all"] = "objects",
    scope: Literal["bucket", "catalog"] = "catalog",
    target: Optional[str] = None,
    backend: Literal["auto", "elasticsearch", "graphql"] = "auto",
    limit: int = 50,
    detail_level: Literal["individual", "summary", "auto"] = "auto",
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

    # Validate entity + backend compatibility
    if entity == "all" and backend == "elasticsearch":
        logger.warning(
            "entity='all' with backend='elasticsearch' will search objects and packages "
            "separately and may return inconsistent result counts. Consider backend='graphql' "
            "for unified search."
        )

    # Validate bucket scope + packages
    if scope == "bucket" and entity == "packages":
        raise ValueError(
            "Cannot search packages within a specific bucket. "
            "Packages are catalog-wide entities. Use scope='catalog' or entity='objects'."
        )
```

### Backend Routing Logic

```python
async def _route_search(
    query: str,
    entity: str,
    scope: str,
    target: Optional[str],
    filters: Dict[str, Any],
    limit: int,
    detail_level: str,
) -> List[SearchResult]:
    """Route search to appropriate backend methods based on entity and scope."""

    # Bucket-scoped object search
    if scope == "bucket" and entity == "objects":
        return await backend.search_objects_in_bucket(
            query=query,
            bucket=target,
            filters=filters,
            limit=limit,
        )

    # Catalog-wide object search
    if scope == "catalog" and entity == "objects":
        if detail_level == "summary" or (detail_level == "auto" and backend_type == "graphql"):
            return await backend.search_objects_catalog_summary(
                query=query,
                filters=filters,
                limit=limit,
            )
        else:
            return await backend.search_objects_catalog_individual(
                query=query,
                filters=filters,
                limit=limit,
            )

    # Catalog-wide package search
    if scope == "catalog" and entity == "packages":
        if detail_level == "summary" or (detail_level == "auto" and backend_type == "graphql"):
            return await backend.search_packages_catalog_summary(
                query=query,
                filters=filters,
                limit=limit,
            )
        else:
            return await backend.search_packages_catalog_individual(
                query=query,
                filters=filters,
                limit=limit,
            )

    # Combined search (objects + packages)
    if scope == "catalog" and entity == "all":
        object_results = await backend.search_objects_catalog(
            query=query,
            filters=filters,
            limit=limit // 2,
            detail_level=detail_level,
        )
        package_results = await backend.search_packages_catalog(
            query=query,
            filters=filters,
            limit=limit // 2,
            detail_level=detail_level,
        )
        return object_results + package_results
```

### Result Format Standardization

```python
@dataclass
class SearchResult:
    """Unified search result with clear type indicators."""

    # Core fields (always present)
    id: str
    type: Literal["object", "package", "object_summary", "package_summary"]
    title: str
    score: float
    backend: str

    # Object-specific fields (when type="object")
    s3_uri: Optional[str] = None
    logical_key: Optional[str] = None
    size: Optional[int] = None
    last_modified: Optional[str] = None
    content_type: Optional[str] = None
    extension: Optional[str] = None

    # Package-specific fields (when type="package")
    package_name: Optional[str] = None
    package_hash: Optional[str] = None
    package_tag: Optional[str] = None

    # Summary fields (when type ends with "_summary")
    total_count: Optional[int] = None
    statistics: Optional[Dict[str, Any]] = None

    # Common metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_object(self) -> bool:
        """Check if this is an object result."""
        return self.type in ("object", "object_summary")

    def is_package(self) -> bool:
        """Check if this is a package result."""
        return self.type in ("package", "package_summary")

    def is_summary(self) -> bool:
        """Check if this is a summary result."""
        return self.type.endswith("_summary")
```

### Response Format

```python
{
    "success": True,
    "query": "*.csv",
    "entity": "objects",
    "scope": "catalog",
    "target": None,
    "results": [
        {
            "id": "s3://bucket1/data.csv",
            "type": "object",
            "title": "data.csv",
            "s3_uri": "s3://bucket1/data.csv",
            "logical_key": "data.csv",
            "size": 1234567,
            "extension": "csv",
            "score": 1.0,
            "backend": "elasticsearch"
        },
        # ... more results
    ],
    "total_results": 42,
    "query_time_ms": 156.3,
    "backend_used": "elasticsearch",
    "detail_level": "individual",
    "analysis": {
        "entity_type": "objects",
        "search_scope": "catalog",
        "query_type": "wildcard",
        "filters_applied": {"file_extensions": ["csv"]}
    }
}
```

---

## Backend Implementation Changes

### Elasticsearch Backend Enhancements

#### 1. Fix Catalog Result Parsing

**Current Bug** (`elasticsearch.py:381-404`):

```python
def _convert_catalog_results(self, raw_results: List[Dict[str, Any]]) -> List[SearchResult]:
    """Convert catalog search results to standard format."""
    for hit in raw_results:
        # Always assumes package - WRONG!
        result = SearchResult(type="package", ...)
```

**Fixed Implementation**:

```python
def _convert_catalog_results(
    self,
    raw_results: List[Dict[str, Any]],
    entity_filter: Optional[str] = None,
) -> List[SearchResult]:
    """Convert catalog search results to standard format.

    Args:
        raw_results: Raw Elasticsearch hits
        entity_filter: Filter results by entity type ("objects", "packages", None for all)
    """
    results = []

    for hit in raw_results:
        source = hit.get("_source", {})
        index_name = hit.get("_index", "")

        # Determine entity type from index name
        is_package_index = index_name.endswith("_packages")

        # Apply entity filter if specified
        if entity_filter == "objects" and is_package_index:
            continue  # Skip packages when filtering for objects
        if entity_filter == "packages" and not is_package_index:
            continue  # Skip objects when filtering for packages

        # Convert based on actual entity type
        if is_package_index:
            result = self._convert_package_hit(hit, source)
        else:
            result = self._convert_object_hit(hit, source)

        results.append(result)

    return results


def _convert_package_hit(self, hit: Dict[str, Any], source: Dict[str, Any]) -> SearchResult:
    """Convert package hit to SearchResult."""
    package_name = source.get("ptr_name", source.get("mnfst_name", ""))

    return SearchResult(
        id=hit.get("_id", ""),
        type="package",
        title=package_name,
        package_name=package_name,
        package_hash=source.get("hash"),
        metadata=source,
        score=hit.get("_score", 0.0),
        backend="elasticsearch",
    )


def _convert_object_hit(self, hit: Dict[str, Any], source: Dict[str, Any]) -> SearchResult:
    """Convert object hit to SearchResult."""
    key = source.get("key", "")
    bucket = self._extract_bucket_from_index(hit.get("_index", ""))

    return SearchResult(
        id=hit.get("_id", ""),
        type="object",
        title=key.split("/")[-1] if key else "Unknown",
        s3_uri=f"s3://{bucket}/{key}" if key else None,
        logical_key=key,
        size=source.get("size", 0),
        last_modified=source.get("last_modified", ""),
        extension=source.get("ext", ""),
        content_type=source.get("content_type", ""),
        metadata=source,
        score=hit.get("_score", 0.0),
        backend="elasticsearch",
    )


def _extract_bucket_from_index(self, index_name: str) -> str:
    """Extract bucket name from Elasticsearch index name.

    Index names are either:
    - "bucket-name" (objects index)
    - "bucket-name_packages" (packages index)
    """
    if index_name.endswith("_packages"):
        return index_name[:-9]  # Remove "_packages" suffix
    return index_name
```

#### 2. Add Entity-Specific Search Methods

```python
async def search_objects_catalog_individual(
    self,
    query: str,
    filters: Optional[Dict[str, Any]],
    limit: int,
) -> List[SearchResult]:
    """Search for individual objects across all catalog buckets.

    This uses the same _search_global infrastructure but filters to only
    return object results (not packages).
    """
    search_response = self._execute_catalog_search(
        query=query,
        limit=limit,
        filters=filters,
    )

    if "error" in search_response:
        raise Exception(search_response["error"])

    hits = search_response.get("hits", {}).get("hits", [])

    # Convert with entity filter for objects only
    return self._convert_catalog_results(hits, entity_filter="objects")


async def search_packages_catalog_individual(
    self,
    query: str,
    filters: Optional[Dict[str, Any]],
    limit: int,
) -> List[SearchResult]:
    """Search for individual packages across catalog.

    This is the same as current _search_global but with explicit filtering.
    """
    search_response = self._execute_catalog_search(
        query=query,
        limit=limit,
        filters=filters,
    )

    if "error" in search_response:
        raise Exception(search_response["error"])

    hits = search_response.get("hits", {}).get("hits", [])

    # Convert with entity filter for packages only
    return self._convert_catalog_results(hits, entity_filter="packages")


async def search_objects_in_bucket(
    self,
    query: str,
    bucket: str,
    filters: Optional[Dict[str, Any]],
    limit: int,
) -> List[SearchResult]:
    """Search for objects within a specific bucket.

    This is a renamed version of current _search_bucket.
    """
    return await self._search_bucket(query, bucket, filters, limit)
```

### GraphQL Backend Enhancements

#### 1. Add Individual Result Support for Catalog Search

**Current Issue**: GraphQL catalog search returns only summary statistics, not individual items.

**Solution**: Add option to fetch individual items when detail_level="individual"

```python
async def search_objects_catalog_individual(
    self,
    query: str,
    filters: Optional[Dict[str, Any]],
    limit: int,
) -> List[SearchResult]:
    """Search for individual objects across catalog.

    Note: This may be slower than summary search for large result sets.
    """
    # Use searchObjects but request first page of actual results
    graphql_query = """
    query SearchObjectsWithResults($buckets: [String!], $searchString: String, $filter: ObjectsSearchFilter, $limit: Int!) {
        searchObjects(buckets: $buckets, searchString: $searchString, filter: $filter) {
            ... on ObjectsSearchResultSet {
                total
                firstPage(limit: $limit) {
                    hits {
                        key
                        bucket
                        size
                        modified
                        ext
                        package { name }
                    }
                }
            }
        }
    }
    """

    variables = {
        "buckets": [],  # Empty = search all accessible buckets
        "searchString": query,
        "filter": self._build_objects_filter(filters),
        "limit": limit,
    }

    result = await self._execute_graphql_query(graphql_query, variables)
    return self._convert_objects_individual_results(result)


def _convert_objects_individual_results(self, graphql_result: Dict[str, Any]) -> List[SearchResult]:
    """Convert individual object hits to SearchResult format."""
    data = graphql_result.get("data", {})
    search_result = data.get("searchObjects", {})
    first_page = search_result.get("firstPage", {})
    hits = first_page.get("hits", [])

    results = []
    for hit in hits:
        bucket = hit.get("bucket", "")
        key = hit.get("key", "")

        result = SearchResult(
            id=f"{bucket}/{key}",
            type="object",
            title=key.split("/")[-1] if key else "Unknown",
            s3_uri=f"s3://{bucket}/{key}",
            logical_key=key,
            size=hit.get("size"),
            last_modified=hit.get("modified"),
            extension=hit.get("ext"),
            package_name=hit.get("package", {}).get("name") if hit.get("package") else None,
            metadata={"bucket": bucket},
            score=1.0,  # GraphQL doesn't provide relevance scores
            backend="graphql",
        )
        results.append(result)

    return results
```

#### 2. Consistent Method Naming

```python
# Rename for consistency
async def search_objects_in_bucket(self, ...) -> List[SearchResult]:
    """Previously _search_bucket_objects"""

async def search_objects_catalog_summary(self, ...) -> List[SearchResult]:
    """Previously _search_objects_global"""

async def search_packages_catalog_summary(self, ...) -> List[SearchResult]:
    """Previously _search_packages_global"""
```

---

## Backward Compatibility Strategy

### Phase 1: Deprecation Warnings (v1.x)

Keep old API working but add warnings:

```python
def search_catalog(
    query: str,
    # NEW parameters
    entity: Optional[Literal["objects", "packages", "all"]] = None,
    scope: Literal["bucket", "catalog", "global", "package"] = "catalog",
    target: Optional[str] = None,
    # OLD parameters (deprecated)
    **kwargs,
) -> Dict[str, Any]:
    """Search Quilt catalog.

    DEPRECATION NOTICE:
    - scope="global" is deprecated, use scope="catalog" instead
    - scope="package" is deprecated and non-functional
    - Implicit entity type selection via scope is deprecated, use entity parameter

    Migration guide: https://docs.quilt.com/mcp-server/migration/search-api-v2
    """

    # Detect old-style usage and translate
    if entity is None:
        # Old-style usage - infer entity from scope
        warnings.warn(
            "Implicit entity type selection is deprecated. "
            "Please specify entity='objects' or entity='packages' explicitly. "
            "In a future version, this will raise an error.",
            DeprecationWarning,
            stacklevel=2,
        )

        if scope == "bucket":
            entity = "objects"  # Old behavior
        elif scope == "catalog" or scope == "global":
            # This is the problem case - backend-dependent
            # Default to most common use case
            entity = "packages"
            warnings.warn(
                f"Assuming entity='packages' for scope='{scope}'. "
                "This may not match your expectation if using GraphQL backend. "
                "Please specify entity explicitly.",
                DeprecationWarning,
                stacklevel=2,
            )

    # Handle deprecated scope values
    if scope == "global":
        warnings.warn(
            "scope='global' is deprecated, use scope='catalog' instead",
            DeprecationWarning,
            stacklevel=2,
        )
        scope = "catalog"

    if scope == "package":
        warnings.warn(
            "scope='package' is deprecated and non-functional. "
            "Package-scoped search is not currently supported. "
            "This parameter will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Return empty results to match current behavior
        return {
            "success": False,
            "error": "Package-scoped search is not implemented",
            "query": query,
            "results": [],
        }

    # Continue with new implementation
    return _search_catalog_v2(query, entity, scope, target, **kwargs)
```

### Phase 2: Error on Old Usage (v2.0)

```python
def search_catalog(
    query: str,
    entity: Literal["objects", "packages", "all"],  # Now required
    scope: Literal["bucket", "catalog"] = "catalog",  # Removed global, package
    target: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Search Quilt catalog.

    BREAKING CHANGE in v2.0:
    - entity parameter is now required
    - scope values 'global' and 'package' have been removed

    Migration guide: https://docs.quilt.com/mcp-server/migration/search-api-v2
    """

    # entity is required now - type checker enforces this
    # scope only accepts valid values - type checker enforces this

    return _search_catalog_v2(query, entity, scope, target, **kwargs)
```

### Migration Helper Function

Provide a helper to ease migration:

```python
def migrate_search_call(
    query: str,
    old_scope: str,
    old_target: Optional[str] = None,
    old_backend: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper function to migrate old search_catalog calls to new API.

    Usage:
        # Old code:
        result = search_catalog(query="*.csv", scope="bucket", target="s3://my-bucket")

        # Migration helper (temporary):
        result = migrate_search_call(query="*.csv", old_scope="bucket", old_target="s3://my-bucket")

        # New code (recommended):
        result = search_catalog(query="*.csv", entity="objects", scope="bucket", target="s3://my-bucket")

    Returns:
        Mapping of old parameters to new parameters with explanation
    """

    mapping = {
        "bucket": {
            "entity": "objects",
            "scope": "bucket",
            "explanation": "Bucket scope searches for objects in a specific bucket",
        },
        "catalog": {
            "entity": "packages",  # Most common use case
            "scope": "catalog",
            "explanation": "Catalog scope typically searches for packages. Use entity='objects' to search objects across all buckets.",
        },
        "global": {
            "entity": "packages",
            "scope": "catalog",
            "explanation": "'global' is now 'catalog'. Use entity='objects' or entity='all' for different search types.",
        },
        "package": {
            "entity": None,
            "scope": None,
            "explanation": "Package-scoped search is not implemented. This was never functional.",
        },
    }

    migration = mapping.get(old_scope, {})

    return {
        "old_call": {
            "scope": old_scope,
            "target": old_target,
            "backend": old_backend,
        },
        "new_call": {
            "entity": migration.get("entity"),
            "scope": migration.get("scope"),
            "target": old_target,
            "backend": old_backend or "auto",
        },
        "explanation": migration.get("explanation", "Unknown scope value"),
        "example": f"search_catalog(query='{query}', entity='{migration.get('entity')}', scope='{migration.get('scope')}', target='{old_target}')",
    }
```

---

## Implementation Plan

### Phase 1: Internal Refactoring (Week 1)

**Goal**: Fix Elasticsearch bug and add new backend methods without changing public API

1. **Fix Elasticsearch `_convert_catalog_results()`**
   - Add entity type detection from index name
   - Split into `_convert_package_hit()` and `_convert_object_hit()`
   - Add `entity_filter` parameter
   - Add tests verifying object results are parsed correctly

2. **Add new backend methods**
   - `search_objects_in_bucket()` (wrapper for existing `_search_bucket`)
   - `search_objects_catalog_individual()` (new, with entity filtering)
   - `search_packages_catalog_individual()` (existing `_search_global` with filtering)
   - Keep old methods working as wrappers

3. **Add GraphQL individual result support**
   - Implement `search_objects_catalog_individual()`
   - Implement `search_packages_catalog_individual()`
   - Modify GraphQL queries to support firstPage results

4. **Update tests**
   - Add tests for object results from catalog search
   - Add tests for entity filtering
   - Add tests for GraphQL individual results

**Deliverables**:

- ✅ Elasticsearch returns objects from catalog search
- ✅ Both backends support individual and summary results
- ✅ All tests pass
- ⚠️ Public API unchanged (no breaking changes yet)

### Phase 2: New API with Deprecation (Week 2)

**Goal**: Launch new API while keeping old API working with warnings

1. **Add new parameters to `search_catalog()`**
   - Add `entity` parameter (optional for now)
   - Add `detail_level` parameter
   - Keep old `scope` values but deprecate "global" and "package"

2. **Add parameter validation**
   - Validate `target` requirement based on scope
   - Validate entity + scope combinations
   - Add helpful error messages

3. **Add deprecation warnings**
   - Warn when `entity` is not specified
   - Warn when using `scope="global"`
   - Warn when using `scope="package"`
   - Include migration guidance in warnings

4. **Update routing logic**
   - Route based on `entity` + `scope` combination
   - Fall back to old behavior when `entity` not specified
   - Maintain backward compatibility

5. **Update documentation**
   - Document new parameters with examples
   - Add migration guide
   - Mark old usage patterns as deprecated

6. **Add `migrate_search_call()` helper**
   - Provide migration assistant function
   - Help users convert old calls to new format

**Deliverables**:

- ✅ New API available and working
- ✅ Old API still works with warnings
- ✅ Migration guide published
- ✅ All tests pass (old and new style)

### Phase 3: Enforce New API (v2.0, Week 3+)

**Goal**: Make `entity` parameter required, remove deprecated scope values

1. **Make `entity` parameter required**
   - Remove default value
   - Update type hints
   - Raise errors on old-style calls

2. **Remove deprecated scope values**
   - Remove "global" from Literal type
   - Remove "package" from Literal type
   - Update validation logic

3. **Remove fallback logic**
   - Remove old-style parameter inference
   - Simplify routing logic
   - Remove deprecation warnings (now errors)

4. **Clean up internal methods**
   - Remove wrapper methods that maintained old API
   - Consolidate duplicate logic
   - Optimize performance

5. **Update all documentation**
   - Remove references to old API
   - Update all examples to new style
   - Archive migration guide (still accessible)

**Deliverables**:

- ✅ Clean, unambiguous API
- ✅ No deprecated code paths
- ✅ Simplified implementation
- ⚠️ Breaking change (major version bump to v2.0)

---

## Testing Strategy

### Unit Tests

```python
class TestSearchCatalogNewAPI:
    """Test new API with entity parameter."""

    def test_search_objects_in_bucket(self):
        """Test entity='objects' scope='bucket'."""
        result = search_catalog(
            query="*.csv",
            entity="objects",
            scope="bucket",
            target="s3://test-bucket",
        )

        assert result["success"] is True
        assert all(r["type"] == "object" for r in result["results"])
        assert all("s3_uri" in r for r in result["results"])

    def test_search_packages_catalog(self):
        """Test entity='packages' scope='catalog'."""
        result = search_catalog(
            query="genomics",
            entity="packages",
            scope="catalog",
        )

        assert result["success"] is True
        assert all(r["type"] in ("package", "package_summary") for r in result["results"])
        assert all("package_name" in r for r in result["results"])

    def test_search_objects_catalog_elasticsearch(self):
        """Test entity='objects' scope='catalog' with Elasticsearch."""
        result = search_catalog(
            query="*.csv",
            entity="objects",
            scope="catalog",
            backend="elasticsearch",
        )

        assert result["success"] is True
        # This should now work (was broken before)
        assert any(r["type"] == "object" for r in result["results"])

    def test_search_all_catalog(self):
        """Test entity='all' scope='catalog'."""
        result = search_catalog(
            query="data",
            entity="all",
            scope="catalog",
        )

        assert result["success"] is True
        # Should have both objects and packages
        types = {r["type"] for r in result["results"]}
        assert len(types) > 1  # Multiple types present

    def test_validation_bucket_requires_target(self):
        """Test that scope='bucket' requires target."""
        with pytest.raises(ValueError, match="target.*required"):
            search_catalog(
                query="*.csv",
                entity="objects",
                scope="bucket",
                target=None,
            )

    def test_validation_cannot_search_packages_in_bucket(self):
        """Test that entity='packages' scope='bucket' is invalid."""
        with pytest.raises(ValueError, match="Cannot search packages within"):
            search_catalog(
                query="test",
                entity="packages",
                scope="bucket",
                target="s3://test-bucket",
            )


class TestSearchCatalogBackwardCompatibility:
    """Test old API still works with deprecation warnings."""

    def test_old_bucket_scope(self):
        """Test old scope='bucket' without entity parameter."""
        with pytest.warns(DeprecationWarning, match="entity.*deprecated"):
            result = search_catalog(
                query="*.csv",
                scope="bucket",
                target="s3://test-bucket",
            )

        assert result["success"] is True
        # Should infer entity='objects'
        assert all(r["type"] == "object" for r in result["results"])

    def test_old_global_scope(self):
        """Test old scope='global' gets converted to scope='catalog'."""
        with pytest.warns(DeprecationWarning, match="global.*deprecated"):
            result = search_catalog(
                query="genomics",
                scope="global",
            )

        assert result["success"] is True
        # Should work as catalog search

    def test_old_package_scope(self):
        """Test old scope='package' returns error."""
        with pytest.warns(DeprecationWarning, match="package.*deprecated"):
            result = search_catalog(
                query="*.csv",
                scope="package",
                target="user/dataset",
            )

        assert result["success"] is False
        assert "not implemented" in result["error"].lower()


class TestElasticsearchObjectParsing:
    """Test Elasticsearch correctly parses object results from catalog search."""

    def test_parses_object_hits(self):
        """Test that object hits are correctly converted."""
        backend = Quilt3ElasticsearchBackend()

        raw_hits = [
            {
                "_index": "test-bucket",  # Object index
                "_id": "obj1",
                "_score": 1.0,
                "_source": {
                    "key": "data/file.csv",
                    "size": 1234,
                    "last_modified": "2024-01-01",
                    "ext": "csv",
                }
            }
        ]

        results = backend._convert_catalog_results(raw_hits, entity_filter="objects")

        assert len(results) == 1
        assert results[0].type == "object"
        assert results[0].s3_uri == "s3://test-bucket/data/file.csv"
        assert results[0].size == 1234

    def test_filters_by_entity_type(self):
        """Test entity filtering works correctly."""
        backend = Quilt3ElasticsearchBackend()

        raw_hits = [
            {"_index": "test-bucket", "_source": {"key": "file.csv"}},  # Object
            {"_index": "test-bucket_packages", "_source": {"ptr_name": "pkg"}},  # Package
        ]

        # Filter for objects only
        object_results = backend._convert_catalog_results(raw_hits, entity_filter="objects")
        assert len(object_results) == 1
        assert object_results[0].type == "object"

        # Filter for packages only
        package_results = backend._convert_catalog_results(raw_hits, entity_filter="packages")
        assert len(package_results) == 1
        assert package_results[0].type == "package"

        # No filter - get both
        all_results = backend._convert_catalog_results(raw_hits, entity_filter=None)
        assert len(all_results) == 2
```

### Integration Tests

```python
class TestSearchCatalogIntegration:
    """Integration tests with real backend."""

    @pytest.mark.integration
    def test_catalog_objects_elasticsearch(self):
        """Test searching objects across catalog with Elasticsearch."""
        result = search_catalog(
            query="ext:csv",
            entity="objects",
            scope="catalog",
            backend="elasticsearch",
            limit=10,
        )

        assert result["success"] is True
        assert result["backend_used"] == "elasticsearch"

        # All results should be objects
        for r in result["results"]:
            assert r["type"] == "object"
            assert "s3_uri" in r
            assert r["s3_uri"].endswith(".csv")

    @pytest.mark.integration
    def test_catalog_packages_elasticsearch(self):
        """Test searching packages across catalog with Elasticsearch."""
        result = search_catalog(
            query="*",
            entity="packages",
            scope="catalog",
            backend="elasticsearch",
            limit=10,
        )

        assert result["success"] is True

        # All results should be packages
        for r in result["results"]:
            assert r["type"] == "package"
            assert "package_name" in r

    @pytest.mark.integration
    def test_catalog_all_graphql(self):
        """Test searching everything with GraphQL."""
        result = search_catalog(
            query="test",
            entity="all",
            scope="catalog",
            backend="graphql",
            limit=20,
        )

        assert result["success"] is True

        # Should have results (summary or individual)
        assert len(result["results"]) > 0
```

---

## Documentation Updates

### User-Facing Documentation

#### Quick Start Examples

```markdown
## Searching Quilt Catalog

### Search for Files

```python
# Search for CSV files across all buckets
result = search_catalog(
    query="*.csv",
    entity="objects",
    scope="catalog"
)

# Search for files in specific bucket
result = search_catalog(
    query="data",
    entity="objects",
    scope="bucket",
    target="s3://my-bucket"
)
```

### Search for Packages

```python
# Search for packages by name
result = search_catalog(
    query="genomics",
    entity="packages",
    scope="catalog"
)

# Get individual package details (Elasticsearch)
result = search_catalog(
    query="genomics",
    entity="packages",
    scope="catalog",
    backend="elasticsearch",
    detail_level="individual"
)
```

### Search Everything

```python
# Search both objects and packages
result = search_catalog(
    query="experiment",
    entity="all",
    scope="catalog"
)
```

```

#### Parameter Reference

```markdown
## Parameters

### `entity` (required)
What type of items to search for:
- `"objects"`: Search for files/objects in S3 buckets
- `"packages"`: Search for Quilt packages
- `"all"`: Search both objects and packages

### `scope` (required)
Where to search:
- `"bucket"`: Search within a specific bucket (requires `target`)
- `"catalog"`: Search across entire catalog

### `target` (optional)
Target bucket when `scope="bucket"`:
- Required when `scope="bucket"`
- Ignored when `scope="catalog"`
- Format: `"s3://bucket-name"` or `"bucket-name"`

### `backend` (optional)
Search backend to use:
- `"auto"` (default): Automatically select best backend
- `"elasticsearch"`: Use Elasticsearch (faster, individual results)
- `"graphql"`: Use GraphQL (richer metadata, may return summaries)

### `detail_level` (optional)
Level of detail in results:
- `"auto"` (default): Backend chooses appropriate level
- `"individual"`: Return individual items
- `"summary"`: Return aggregated statistics

**Note**: Not all backends support all detail levels. Elasticsearch always returns individual results. GraphQL catalog searches default to summaries but can return individual results with `detail_level="individual"`.
```

#### Migration Guide

```markdown
## Migrating from Old API

### What Changed

The `search_catalog` API has been redesigned to be clearer and more predictable:

**Old API (deprecated)**:
```python
# Ambiguous - searches packages or objects depending on backend
search_catalog(query="data", scope="catalog")

# Unclear - what does "bucket" scope mean?
search_catalog(query="*.csv", scope="bucket", target="s3://my-bucket")
```

**New API**:

```python
# Explicit - always searches packages
search_catalog(query="data", entity="packages", scope="catalog")

# Clear - searches objects in bucket
search_catalog(query="*.csv", entity="objects", scope="bucket", target="s3://my-bucket")
```

### Migration Steps

1. **Add `entity` parameter** to all `search_catalog()` calls

   Before:

   ```python
   result = search_catalog(query="data", scope="catalog")
   ```

   After:

   ```python
   result = search_catalog(query="data", entity="packages", scope="catalog")
   ```

2. **Replace `scope="global"` with `scope="catalog"`**

   Before:

   ```python
   result = search_catalog(query="data", scope="global")
   ```

   After:

   ```python
   result = search_catalog(query="data", entity="packages", scope="catalog")
   ```

3. **Remove `scope="package"` calls** (never worked)

   Before:

   ```python
   result = search_catalog(query="*.csv", scope="package", target="user/dataset")
   ```

   After:

   ```python
   # Package-scoped search is not supported
   # Instead, search catalog and filter by package name
   result = search_catalog(query="*.csv", entity="objects", scope="catalog")
   filtered = [r for r in result["results"] if r.get("package_name") == "user/dataset"]
   ```

### Scope Mapping Table

| Old API | New API | Notes |
|---------|---------|-------|
| `scope="bucket"` | `entity="objects", scope="bucket"` | Now explicit that you're searching objects |
| `scope="catalog"` | `entity="packages", scope="catalog"` | Default to packages (most common) |
| `scope="global"` | `entity="packages", scope="catalog"` | "global" removed, use "catalog" |
| `scope="package"` | Not supported | This never worked, remove it |

### Testing Your Migration

Use the migration helper to validate your changes:

```python
from quilt_mcp.tools.search import migrate_search_call

# Check how your old call should be updated
migration = migrate_search_call(
    query="*.csv",
    old_scope="bucket",
    old_target="s3://my-bucket"
)

print(migration["explanation"])
print(migration["example"])
```

```

---

## Success Criteria

### Functional Requirements

✅ **Clarity**: Users can predict what entity types they'll get from parameter choices
✅ **Consistency**: Same parameters return same entity types regardless of backend
✅ **Completeness**: All backend capabilities are accessible through API
✅ **Validation**: Invalid parameter combinations produce clear error messages
✅ **Backward Compatibility**: Existing code continues to work with deprecation warnings

### Technical Requirements

✅ **Elasticsearch Returns Objects**: Catalog search with `entity="objects"` returns object results
✅ **GraphQL Returns Individuals**: Catalog search with `detail_level="individual"` returns individual items
✅ **Type Safety**: All parameters are properly typed and validated
✅ **Documentation**: All usage patterns are documented with examples
✅ **Tests**: 100% coverage of new parameter combinations

### User Experience Requirements

✅ **Migration Path**: Clear migration guide with examples
✅ **Helpful Errors**: Validation errors explain what's wrong and how to fix it
✅ **Deprecation Warnings**: Old API usage produces warnings with migration guidance
✅ **Discovery**: API is self-documenting through parameter names and docstrings

---

## Appendices

### Appendix A: Alternative Rejected Designs

#### Option C: Separate Scope Types

```python
def search_catalog(
    query: str,
    scope: Union[BucketScope, CatalogScope],
    ...
)

@dataclass
class BucketScope:
    bucket: str
    entity: Literal["objects"] = "objects"

@dataclass
class CatalogScope:
    entity: Literal["objects", "packages", "all"] = "packages"
```

**Rejected because**: Too complex for MCP tool usage, harder to serialize over JSON

#### Option D: Query String Syntax

```python
# Entity type in query string
search_catalog(query="type:objects *.csv", scope="catalog")
search_catalog(query="type:packages genomics", scope="catalog")
```

**Rejected because**: Mixes query syntax with API parameters, harder to validate, less discoverable

### Appendix B: Performance Considerations

**Elasticsearch Performance**:

- Adding entity filtering adds minimal overhead (index name check)
- Catalog search already queries all indices, so no additional I/O
- Individual object results may return more data than package results (larger documents)

**GraphQL Performance**:

- Individual results require fetching firstPage which is more expensive than stats-only
- Summary results are faster but less detailed
- `detail_level="auto"` lets backend optimize

**Recommendations**:

- Use `detail_level="summary"` for quick counts/statistics
- Use `detail_level="individual"` when you need to act on specific items
- Use `backend="elasticsearch"` for guaranteed individual results

### Appendix C: Future Enhancements

**Possible Future Additions**:

1. **Package-scoped object search**

   ```python
   search_catalog(
       query="*.csv",
       entity="objects",
       scope="package",
       target="genomics/experiment-2024"
   )
   ```

2. **Multi-bucket search**

   ```python
   search_catalog(
       query="*.csv",
       entity="objects",
       scope="buckets",
       target=["s3://bucket1", "s3://bucket2"]
   )
   ```

3. **Streaming results**

   ```python
   async for result in search_catalog_stream(query="*", entity="objects"):
       process(result)
   ```

4. **Saved searches**

   ```python
   save_search(name="daily-csvs", query="*.csv", entity="objects")
   run_saved_search(name="daily-csvs")
   ```

---

**End of Document**
