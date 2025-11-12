# Fix: Implement `_search_packages()` for Package-Only Search

**Date:** 2025-01-12
**Issue:** `scope="package"` returns 'file' results instead of 'package' results
**Root Cause:** `_search_packages()` is a stub that returns `[]`, causing fallthrough to `_search_global()`

---

## Problem

Currently `_search_packages()` does nothing:

```python
async def _search_package(
    self,
    query: str,
    package_name: str,
    filters: Optional[Dict[str, Any]],
    limit: int,
) -> List[SearchResult]:
    """Search within a specific package."""
    # TODO: implement package-scoped search directly via search API if needed
    return []  # ← STUB!
```

When `scope="package"` is used:
- **WITH target:** Calls `_search_package()` → returns `[]` (empty)
- **WITHOUT target:** Falls through to `_search_global()` → searches BOTH object and package indices → returns mixed/wrong results

---

## Solution: Implement `_search_packages()` Properly

Rename and implement the method to handle BOTH use cases:
1. **Catalog-wide package search** (no target) - search all packages across catalog
2. **Specific package search** (with target) - search within one package

### Method Signature

```python
async def _search_packages(
    self,
    query: str,
    package_name: str = "",  # Empty = catalog-wide, specified = specific package
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 50,
) -> List[SearchResult]:
    """Search packages across catalog or within specific package.

    Args:
        query: Search query
        package_name: Optional package name. If empty, searches all packages.
                     If specified, searches within that package only.
        filters: Optional filters
        limit: Max results

    Returns:
        List of package search results
    """
```

### Implementation Logic

```python
async def _search_packages(
    self,
    query: str,
    package_name: str = "",
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 50,
) -> List[SearchResult]:
    """Search packages across catalog or within specific package."""

    if package_name:
        # Search within specific package
        # Use package-specific index: {bucket}_packages with package name filter
        search_response = self._execute_catalog_search(
            query=query,
            limit=limit,
            filters={**(filters or {}), "package_name": package_name},
            packages_only=True
        )
    else:
        # Catalog-wide package search
        # Use all *_packages indices
        search_response = self._execute_catalog_search(
            query=query,
            limit=limit,
            filters=filters,
            packages_only=True  # Only search *_packages indices
        )

    if "error" in search_response:
        # Fallback logic if needed
        raise Exception(search_response["error"])

    hits = search_response.get("hits", {}).get("hits", [])
    return self._convert_catalog_results(hits)
```

### Update Router in `search()` Method

```python
async def search(
    self,
    query: str,
    scope: str = "global",
    target: str = "",
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 50,
) -> BackendResponse:
    """Execute search using quilt3.Bucket.search() or packages search API."""
    # ... initialization ...

    try:
        if scope == "bucket" and target:
            # Search objects in specific bucket
            results = await self._search_bucket(query, target, filters, limit)
        elif scope == "package":
            # Search packages (catalog-wide OR specific package)
            results = await self._search_packages(query, target, filters, limit)
        else:
            # Global search (all entities: objects + packages)
            results = await self._search_global(query, filters, limit)
```

### Add `packages_only` Parameter to `build_stack_search_indices()`

```python
def build_stack_search_indices(
    buckets: Optional[List[str]] = None,
    packages_only: bool = False
) -> str:
    """Build Elasticsearch index pattern.

    Args:
        buckets: List of bucket names
        packages_only: If True, only include *_packages indices

    Returns:
        Comma-separated index pattern
        - packages_only=False: "bucket1,bucket1_packages,bucket2,bucket2_packages"
        - packages_only=True:  "bucket1_packages,bucket2_packages"
    """
    if buckets is None:
        buckets = get_stack_buckets()

    if not buckets:
        return ""

    indices = []
    for bucket in buckets:
        if packages_only:
            indices.append(f"{bucket}_packages")
        else:
            indices.extend([bucket, f"{bucket}_packages"])

    return ",".join(indices)
```

### Update `_execute_catalog_search()` to Support `packages_only`

```python
def _execute_catalog_search(
    self,
    query: Union[str, Dict[str, Any]],
    limit: int,
    *,
    filters: Optional[Dict[str, Any]] = None,
    from_: int = 0,
    packages_only: bool = False,
) -> Dict[str, Any]:
    """Execute catalog search query.

    Args:
        packages_only: If True, only search *_packages indices
    """
    # ... query building ...

    index_name = build_stack_search_indices(packages_only=packages_only)

    # ... rest of method ...
```

---

## Result

### Before (Broken)
```python
search_catalog(query="test", scope="package")
# → Falls through to _search_global()
# → Searches "bucket1,bucket1_packages,bucket2,bucket2_packages"
# → Returns mixed file/package results (BUG)
```

### After (Fixed)
```python
search_catalog(query="test", scope="package")
# → Calls _search_packages(query="test", package_name="")
# → Searches "bucket1_packages,bucket2_packages" ONLY
# → Returns package results only (CORRECT)

search_catalog(query="README", scope="package", target="user/dataset")
# → Calls _search_packages(query="README", package_name="user/dataset")
# → Searches within specific package
# → Returns files within that package (CORRECT)
```

---

## Files to Modify

1. `src/quilt_mcp/search/backends/elasticsearch.py`
   - Rename `_search_package()` → `_search_packages()`
   - Implement catalog-wide and specific package search
   - Update `search()` router to call `_search_packages()` for `scope="package"`

2. `src/quilt_mcp/tools/stack_buckets.py`
   - Add `packages_only` parameter to `build_stack_search_indices()`

3. `src/quilt_mcp/search/backends/elasticsearch.py`
   - Add `packages_only` parameter to `_execute_catalog_search()`

---

## Test Cases

```python
# Test 1: Catalog-wide package search
result = search_catalog(query="*", scope="package", limit=10)
assert all(r["type"] == "package" for r in result["results"])

# Test 2: Specific package search
result = search_catalog(query="README", scope="package", target="user/dataset", limit=10)
assert result["success"]

# Test 3: Index pattern generation
indices = build_stack_search_indices(["bucket1", "bucket2"], packages_only=True)
assert indices == "bucket1_packages,bucket2_packages"
```

---

## Summary

**Change:** Implement `_search_packages()` to handle both catalog-wide and specific package search using `packages_only=True` flag.

**Result:** `scope="package"` now correctly searches packages only, not mixed object/package indices.
