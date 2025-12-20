# Search Catalog Scope Issues Analysis

**Date:** 2025-11-11
**Branch:** search-catalog-fixes
**Status:** Critical Design Issues Identified

---

## Executive Summary

The `search_catalog` tool has fundamental semantic confusion in its parameter design. The `scope` parameter names don't match what they actually search, and different backends interpret the same scope differently, returning completely different result types. Additionally, result parsing bugs prevent some functionality from working even though the underlying APIs support it.

### Critical Findings

1. **Scope names are misleading**: `scope="bucket"` searches objects, `scope="catalog"` searches packages
2. **Backend inconsistency**: Same scope returns different entity types depending on backend
3. **Hidden capabilities**: Elasticsearch already queries object indices but discards the results
4. **Non-functional features**: `scope="package"` is documented but returns empty results
5. **Redundant parameters**: `scope="global"` and `scope="catalog"` are identical

---

## Current Parameter Design

### Parameters

```python
def search_catalog(
    query: str,
    scope: Literal["global", "catalog", "package", "bucket"] = "bucket",
    target: str = "",  # Required for bucket/package scopes
    backend: Literal["auto", "elasticsearch", "graphql"] = "elasticsearch",
    limit: int = 50,
    ...
) -> Dict[str, Any]:
```

### Documented Behavior

From the docstring:

```python
scope: Search scope - "bucket" (specific bucket, default),
                      "catalog" (current catalog),
                      "package" (specific package),
                      "global" (all)
```

This documentation **does not explain**:
- What entity types each scope returns (objects vs packages)
- That "catalog" and "global" are identical
- That behavior differs between backends
- That "package" scope doesn't work

---

## What Scopes Actually Do

### Current Implementation Matrix

| Scope Value | Target Required? | Elasticsearch Backend | GraphQL Backend | Working? |
|-------------|-----------------|----------------------|-----------------|----------|
| `"bucket"` | Yes (bucket name) | Searches **objects** in bucket | Searches **objects** in bucket | ✅ Yes |
| `"package"` | Yes (package name) | Returns `[]` (not implemented) | Returns `[]` (not implemented) | ❌ No |
| `"catalog"` | No | Searches **packages** catalog-wide | Searches **objects + packages** | ✅ Yes (different results) |
| `"global"` | No | Searches **packages** catalog-wide | Searches **objects + packages** | ✅ Yes (identical to catalog) |

### Code Evidence

**Elasticsearch Backend** (`src/quilt_mcp/search/backends/elasticsearch.py:115-123`):

```python
if scope == "bucket" and target:
    # Use bucket-specific search
    results = await self._search_bucket(query, target, filters, limit)
elif scope == "package" and target:
    # Search within specific package (dedicated package-scoped logic pending)
    results = await self._search_package(query, target, filters, limit)
else:
    # Global/catalog search using packages search API
    results = await self._search_global(query, filters, limit)
```

**GraphQL Backend** (`src/quilt_mcp/search/backends/graphql.py:165-173`):

```python
if scope == "bucket" and target:
    results = await self._search_bucket_objects(query, target, filters, limit)
elif scope == "package" and target:
    results = await self._search_package_contents(query, target, filters, limit)
else:
    # Global/catalog search - search both objects and packages
    object_results = await self._search_objects_global(query, filters, limit // 2)
    package_results = await self._search_packages_global(query, filters, limit // 2)
    results = object_results + package_results
```

---

## Backend Capabilities Analysis

### What Each Backend Can Actually Search

| Search Operation | Elasticsearch | GraphQL | Notes |
|-----------------|---------------|---------|-------|
| **Objects in specific bucket** | ✅ Yes | ✅ Yes | Via `quilt3.Bucket.search()` / GraphQL `objects(bucket:)` |
| **Packages catalog-wide** | ✅ Yes | ✅ Yes | Via catalog search API / GraphQL `searchPackages()` |
| **Objects catalog-wide** | 🐛 Broken | ✅ Yes | ES queries the indices but discards results |
| **Objects + Packages together** | 🐛 Broken | ✅ Yes | ES has the data but can't parse it |

### Elasticsearch Hidden Capability

**Discovery**: Elasticsearch **already queries object indices** across all buckets, but result parsing throws away object results.

**Evidence** (`src/quilt_mcp/tools/stack_buckets.py:131-138`):

```python
def build_stack_search_indices(buckets: Optional[List[str]] = None) -> str:
    """Build Elasticsearch index pattern for searching across all stack buckets."""
    # ...
    indices = []
    for bucket in buckets:
        indices.extend([bucket, f"{bucket}_packages"])  # ← Includes BOTH

    index_pattern = ",".join(indices)
    return index_pattern
```

This returns: `"bucket1,bucket1_packages,bucket2,bucket2_packages"`

The search API queries **all these indices**, returning both objects and packages.

**The Bug** (`src/quilt_mcp/search/backends/elasticsearch.py:381-404`):

```python
def _convert_catalog_results(self, raw_results: List[Dict[str, Any]]) -> List[SearchResult]:
    """Convert catalog search results to standard format."""
    results = []

    for hit in raw_results:
        source = hit.get("_source", {})

        # Extract package information
        package_name = source.get("ptr_name", source.get("mnfst_name", ""))

        result = SearchResult(
            id=hit.get("_id", ""),
            type="package",  # ← ALWAYS assumes package
            title=package_name,
            description=f"Quilt package: {package_name}",
            package_name=package_name,
            metadata=source,
            score=hit.get("_score", 0.0),
            backend="elasticsearch",
        )

        results.append(result)

    return results
```

**Problem**:
- This method assumes ALL results are packages
- It extracts `ptr_name`/`mnfst_name` (package-specific fields)
- Object results get malformed into "packages" with empty names
- Object data is effectively discarded

**Solution**: Check `hit.get("_index")` to determine if result is from `bucket_packages` index or object index, and route to appropriate converter.

---

## Semantic Confusion

### Issue 1: Scope Names Don't Match Entity Types

**What users think:**
- `scope="bucket"` → searches a bucket (all contents)
- `scope="catalog"` → searches the catalog (all contents)

**What actually happens:**
- `scope="bucket"` → searches **objects** in a bucket
- `scope="catalog"` → searches **packages** in catalog (ES) or **objects+packages** (GraphQL)

**The real semantic dimensions:**

```
Dimension 1: WHAT to search (entity type)
  - objects
  - packages
  - both

Dimension 2: WHERE to search (scope)
  - specific bucket
  - catalog-wide

Dimension 3: HOW to search (backend)
  - elasticsearch
  - graphql
```

Current API conflates all three dimensions into ambiguous parameter combinations.

### Issue 2: Backend Selection Changes Result Types

**Scenario**: User runs same query with different backends

```python
# With Elasticsearch backend
search_catalog(query="data.csv", scope="catalog", backend="elasticsearch")
# Returns: Package results only

# With GraphQL backend
search_catalog(query="data.csv", scope="catalog", backend="graphql")
# Returns: Object results + Package results
```

**Impact**: Same API call returns fundamentally different entity types depending on backend. This violates principle of least surprise and makes results unpredictable.

### Issue 3: Redundant Scope Values

**Code Evidence** (`elasticsearch.py:121-123`, `graphql.py:169-173`):

Both backends treat `scope="global"` and `scope="catalog"` identically - they fall through to the same `else` clause.

**Impact**:
- API surface is unnecessarily large
- Users must guess difference between "global" and "catalog"
- Documentation can't meaningfully distinguish them
- No functionality benefits from having both

### Issue 4: Target Parameter Overloading

**Current behavior:**

```python
# Required for bucket scope
search_catalog(query="*.csv", scope="bucket", target="s3://my-bucket")

# Required for package scope
search_catalog(query="file.csv", scope="package", target="user/dataset")

# Ignored for catalog/global scopes
search_catalog(query="*.csv", scope="catalog", target="anything")  # target ignored

# Auto-filled from DEFAULT_BUCKET when empty
search_catalog(query="*.csv", scope="bucket", target="")  # Uses DEFAULT_BUCKET
```

**Issues:**
- Same parameter means different things (bucket URI vs package name)
- No type safety or validation
- Silent behavior when target is ignored
- Magic DEFAULT_BUCKET fallback is implicit

---

## Non-Functional Features

### Package Scope Returns Empty Results

**Both backends** (`elasticsearch.py:189-198`, `graphql.py:435-445`):

```python
async def _search_package(...) -> List[SearchResult]:
    """Search within a specific package."""
    # TODO: implement package-scoped search directly via search API if needed
    return []
```

**Impact:**
- `scope="package"` is documented in the API
- Users can call it without errors
- Always returns zero results
- No indication that feature is unimplemented
- Wastes user time debugging why their query returns nothing

**Example of silent failure:**

```python
# User tries to search within a package
result = search_catalog(
    query="*.csv",
    scope="package",
    target="genomics/experiment-2024",
)

# Returns: {"success": True, "results": [], "total_results": 0}
# No error, no warning, just empty results
```

---

## Result Type Inconsistencies

### Elasticsearch Backend Result Types

**Bucket scope** (`_convert_bucket_results`, lines 344-379):
```python
result = SearchResult(
    type="file",  # or "package" if from _packages index
    s3_uri=f"s3://{bucket}/{key}",
    logical_key=key,
    size=size,
    last_modified=last_modified,
    ...
)
```

**Catalog scope** (`_convert_catalog_results`, lines 381-404):
```python
result = SearchResult(
    type="package",  # ALWAYS package
    package_name=package_name,
    ...
)
```

### GraphQL Backend Result Types

**Bucket scope** (`_convert_bucket_objects_results`, lines 528-569):
```python
result = SearchResult(
    type="file",
    s3_uri=f"s3://{bucket}/{node.get('key', '')}",
    logical_key=node.get("key"),
    ...
)
```

**Catalog scope - Objects** (`_convert_objects_search_results`, lines 759-810):
```python
result = SearchResult(
    type="object_summary",  # Summary, not individual objects
    title=f"{total} objects matching '{query}'",
    metadata={"total_objects": total, "stats": stats, ...},
    ...
)
```

**Catalog scope - Packages** (`_convert_catalog_search_results`, lines 719-757):
```python
result = SearchResult(
    type="package_summary",  # Summary, not individual packages
    title=f"{total} packages matching '{query}'",
    metadata={"total_packages": total, "stats": stats, ...},
    ...
)
```

### Issue: Inconsistent Summary vs Individual Results

**Elasticsearch**: Returns individual objects/packages with full details

**GraphQL catalog search**: Returns summary statistics, not individual items

```python
# Elasticsearch result
{
    "type": "package",
    "title": "genomics/experiment-2024",
    "package_name": "genomics/experiment-2024",
    "size": 1234567,
    ...
}

# GraphQL result
{
    "type": "package_summary",
    "title": "150 packages matching 'genomics'",
    "metadata": {
        "total_packages": 150,
        "size_sum_bytes": 999999999,
        ...
    }
}
```

**Impact**: Users can't use GraphQL results for item-level operations (download, inspect specific package) because they only get aggregated statistics.

---

## API Surface Analysis

### What Works

✅ **Bucket-scoped object search** (both backends)
```python
search_catalog(query="*.csv", scope="bucket", target="s3://my-bucket")
# Returns: List of CSV files in that bucket
```

✅ **Catalog-wide package search** (Elasticsearch)
```python
search_catalog(query="genomics", scope="catalog", backend="elasticsearch")
# Returns: List of packages matching "genomics"
```

✅ **Catalog-wide aggregated search** (GraphQL)
```python
search_catalog(query="genomics", scope="catalog", backend="graphql")
# Returns: Summary statistics for matching objects and packages
```

### What's Broken

❌ **Package-scoped search** (both backends)
```python
search_catalog(query="*.csv", scope="package", target="user/dataset")
# Returns: [] (always empty)
```

❌ **Catalog-wide object search** (Elasticsearch)
```python
search_catalog(query="*.csv", scope="catalog", backend="elasticsearch")
# Returns: Only packages, even though objects are in the index
```

❌ **Catalog-wide individual results** (GraphQL)
```python
search_catalog(query="data.csv", scope="catalog", backend="graphql")
# Returns: Summary statistics, not individual files
```

### What's Confusing

⚠️ **Same scope, different result types**
```python
# Elasticsearch: returns individual packages
search_catalog(query="genomics", scope="catalog", backend="elasticsearch")

# GraphQL: returns summary statistics
search_catalog(query="genomics", scope="catalog", backend="graphql")
```

⚠️ **Redundant scope values**
```python
# These are identical
search_catalog(query="data", scope="global")
search_catalog(query="data", scope="catalog")
```

⚠️ **Implicit fallback behavior**
```python
# target="" triggers DEFAULT_BUCKET fallback
search_catalog(query="*.csv", scope="bucket", target="")
# Silently searches DEFAULT_BUCKET instead of erroring
```

---

## Root Causes

### 1. Conflated Concerns in Parameter Design

The `scope` parameter conflates three independent concepts:

```
scope="bucket" means:
  - Entity type: objects
  - Search scope: specific bucket
  - Result detail: individual items

scope="catalog" means:
  - Entity type: packages (ES) or objects+packages (GraphQL)
  - Search scope: catalog-wide
  - Result detail: individual (ES) or summary (GraphQL)
```

### 2. Backend Abstraction Leaks Implementation Details

The unified API exposes backend-specific behaviors:
- Elasticsearch can search individual items
- GraphQL searches return aggregated statistics
- User must know backend capabilities to predict result format

### 3. Missing Entity Type Dimension

The real user intent has two orthogonal dimensions:

```
What to search:
  - objects
  - packages
  - both

Where to search:
  - specific bucket/package
  - catalog-wide
```

Current API forces users to specify backend to control "what" dimension.

### 4. Incomplete Implementation Exposed as API Surface

`scope="package"` is documented and callable but non-functional. Should either:
- Be implemented
- Be removed from API
- Return error indicating not implemented

### 5. Result Parsing Bug Hidden by Design

Elasticsearch already queries object indices but result parser assumes packages. This bug is hidden because:
- No tests verify object results from catalog search
- Documentation doesn't promise object results
- Users don't know to expect object results

---

## Impact Assessment

### User Experience Impact

**High Severity:**
- Users cannot reliably search for objects across multiple buckets
- Same query returns different entity types depending on backend selection
- `scope="package"` silently fails without indication

**Medium Severity:**
- Scope parameter names don't match what they search
- Cannot get individual items from GraphQL catalog search
- Must understand backend differences to use API effectively

**Low Severity:**
- Redundant scope values (`global` vs `catalog`)
- Target parameter overloading requires reading docs carefully

### Code Maintainability Impact

**Current Technical Debt:**
- Backend abstraction doesn't truly abstract - callers must know implementation
- Result converters have different assumptions about data structure
- Missing entity type dimension makes future enhancements difficult
- Elasticsearch result parsing bug indicates insufficient test coverage

### API Evolution Impact

**Blocked Future Enhancements:**
- Can't add "search objects catalog-wide" without breaking changes
- Can't add "search objects + packages" for Elasticsearch without changing behavior
- Can't distinguish individual vs summary results in type system
- Can't deprecate `scope="global"` without removing documented feature

---

## Summary of Issues

### Critical Issues

1. **Backend behavioral inconsistency**: Same `scope="catalog"` returns packages (ES) vs objects+packages (GraphQL)
2. **Hidden Elasticsearch capability**: Already queries object indices but discards results
3. **Non-functional package scope**: Documented but returns empty results always

### Design Issues

4. **Scope names misleading**: "bucket" searches objects, "catalog" searches packages
5. **Redundant scope values**: "global" and "catalog" are identical
6. **Missing entity type dimension**: Cannot explicitly request objects vs packages
7. **Target parameter overloading**: Means bucket URI or package name depending on scope
8. **Result format inconsistency**: Individual items (ES) vs summaries (GraphQL)

### Implementation Issues

9. **Result parser bug**: `_convert_catalog_results()` assumes all results are packages
10. **Implicit DEFAULT_BUCKET fallback**: Silent behavior when target is empty
11. **No validation**: Can pass package name to bucket scope without error

---

## Next Steps

This document identifies the issues. See separate documents for:
- **07-fix-scopes.md**: Proposed API redesign and migration path
- **07-scope-tests.md**: Test coverage plan for scope functionality
- **07-scope-migration.md**: Step-by-step migration guide

---

## Appendices

### Appendix A: Code Reference Index

**Scope routing logic:**
- Elasticsearch: `src/quilt_mcp/search/backends/elasticsearch.py:115-123`
- GraphQL: `src/quilt_mcp/search/backends/graphql.py:165-173`

**Result converters:**
- ES bucket results: `elasticsearch.py:344-379`
- ES catalog results: `elasticsearch.py:381-404` (buggy)
- GraphQL bucket results: `graphql.py:528-569`
- GraphQL object summary: `graphql.py:759-810`
- GraphQL package summary: `graphql.py:719-757`

**Stack search infrastructure:**
- Index building: `src/quilt_mcp/tools/stack_buckets.py:115-138`
- Bucket discovery: `stack_buckets.py:12-51`

**Non-functional implementations:**
- ES package search: `elasticsearch.py:189-198`
- GraphQL package search: `graphql.py:435-445`

### Appendix B: Real-World Usage Scenarios

**Scenario 1: Finding CSV files across all buckets**

```python
# What user wants
search_catalog(query="*.csv", entity="objects", scope="catalog")

# What they actually have to do
search_catalog(query="*.csv", scope="catalog", backend="graphql")
# But this returns summary stats, not individual files
```

**Scenario 2: Searching for packages by name**

```python
# What user wants
search_catalog(query="genomics", entity="packages", scope="catalog")

# What they actually have to do
search_catalog(query="genomics", scope="catalog", backend="elasticsearch")
# And they must know GraphQL returns summaries, not individual packages
```

**Scenario 3: Finding files in specific package**

```python
# What user wants
search_catalog(query="*.csv", scope="package", target="genomics/exp-2024")

# What happens
# Returns: []
# No error, no indication feature doesn't work
```

### Appendix C: Backend Capability Matrix

| Capability | Elasticsearch | GraphQL | Notes |
|------------|--------------|---------|-------|
| Search objects in bucket | ✅ Individual items | ✅ Individual items | Both work |
| Search objects catalog-wide | 🐛 Queries but drops | ✅ Summary stats | ES has bug |
| Search packages catalog-wide | ✅ Individual items | ✅ Summary stats | Different detail levels |
| Search objects + packages | 🐛 Could work | ✅ Summary stats | ES needs fix |
| Search within package | ❌ Not implemented | ❌ Not implemented | Both broken |
| Return individual items | ✅ Yes | ⚠️ Bucket only | GraphQL aggregates catalog |
| Return summary stats | ❌ No | ✅ Catalog only | ES always individual |
| Filter by file extension | ✅ Yes | ✅ Yes | Both work |
| Filter by size | ✅ Yes | ✅ Yes | Both work |
| Filter by date | ✅ Yes | ✅ Yes | Both work |

---

**End of Document**
