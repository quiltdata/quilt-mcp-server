# Quilt3 Search Usage Analysis: Are We Doing It Right?

**Date**: 2025-11-15
**Questions Addressed**:
1. Are we making proper use of `quilt3.search()` API?
2. Can we support both Package (manifest) and PackageEntry scopes?

---

## Question A: Are We Using quilt3.search() Properly?

### What quilt3.search() Actually Does

**Function signature:**
```python
def search(query: Union[str, dict], limit: int = 10) -> List[dict]
```

**Implementation** (from quilt3 source):
```python
def search(query: Union[str, dict], limit: int = 10) -> List[dict]:
    """Execute a search against the configured search endpoint."""
    raw_results = search_api(query, '_all', limit)  # ← searches ALL indices
    return raw_results['hits']['hits']
```

**The search_api function** (from quilt3.api):
```python
def search_api(query: Union[str, dict], index: str, limit: int = 10):
    """Send a query to the search API"""
    if isinstance(query, dict):
        # DSL query (our use case)
        params = dict(
            index=index,
            action="freeform",
            body=json.dumps(query),
            size=limit
        )
    else:
        # Simple string query
        params = dict(
            index=index,
            action="search",
            query=query,
            size=limit
        )
    response = session.get(f"{registry_url}/api/search", params=params)
    return response.json()
```

### How We're Using It

**Our implementation** (QuiltService.get_search_api()):
```python
def get_search_api(self):
    """Get the search API function that supports index parameter."""
    def search_api(query: Union[str, dict], index: str, limit: int = 10):
        # Same implementation as quilt3's search_api
        # But we expose the 'index' parameter!
        ...
    return search_api
```

**Our usage** (Quilt3ElasticsearchBackend):
```python
search_api = self.quilt_service.get_search_api()

# We specify EXACT indices
response = search_api(
    query=dsl_query,
    index="bucket-name_packages",  # ← Specific index, not '_all'
    limit=limit
)
```

### Verdict: ✅ YES - We're Using It Correctly (and Better)

**What we do RIGHT:**

1. **We expose the `index` parameter** that `quilt3.search()` hides
   - `quilt3.search()` always searches `'_all'` indices
   - Our `search_api()` lets us specify exact indices
   - This is MORE powerful and MORE efficient

2. **We use DSL queries** for precise control
   ```python
   # Our query structure
   {
       "from": 0,
       "size": limit,
       "query": {
           "query_string": {"query": escaped_query}
       }
   }
   ```

3. **We build index patterns dynamically** based on scope
   - File scope: `"bucket1,bucket2"`
   - Package scope: `"bucket1_packages,bucket2_packages"`
   - Global scope: `"bucket1,bucket2,bucket1_packages,bucket2_packages"`

4. **We handle authentication properly**
   - Use the same session as quilt3
   - Respect registry URL configuration
   - Handle auth errors gracefully

**Comparison:**

| Feature | quilt3.search() | Our Implementation |
|---------|----------------|-------------------|
| Index control | ❌ Always `'_all'` | ✅ Specify exact indices |
| Scope-based search | ❌ No | ✅ file/packageEntry/global |
| Result parsing | ❌ Raw ES hits | ✅ Typed SearchResult objects |
| Error handling | ❌ Raises exceptions | ✅ Returns BackendResponse with status |
| Bucket filtering | ❌ No | ✅ Search specific buckets |
| Multi-bucket 403 retry | ❌ No | ✅ Automatic fallback to fewer buckets |

---

## Question B: Can We Support Both Package and PackageEntry Scopes?

### Document Types in Package Indices

Package indices (`bucket_packages`) contain **TWO types of documents**:

#### 1. Manifest Documents (Package Metadata)

**Fields:**
- `ptr_name`: Package name (e.g., `"CORD-19/2020-09-21"`)
- `ptr_tag`: Tag name (e.g., `"latest"`)
- `ptr_last_modified`: When the package was last modified
- `mnfst_name`: Manifest file name

**Purpose:** Represent package versions/tags

**Example:**
```json
{
  "_source": {
    "ptr_last_modified": "2020-09-21T21:06:58+00:00",
    "ptr_name": "CORD-19/2020-09-21",
    "ptr_tag": "latest"
  }
}
```

#### 2. Entry Documents (Package Contents)

**Fields:**
- `entry_pk`: Entry physical key (S3 URI with package version)
- `entry_lk`: Entry logical key (file path within package)
- `entry_size`: File size in bytes
- `entry_hash`: File hash (SHA256)
- `entry_metadata`: File metadata (last_modified, etc.)
- `entry_pk_parsed.s3`: Parsed S3 location

**Purpose:** Represent individual files within packages

**Example:**
```json
{
  "_source": {
    "entry_pk": "s3://ai2-semanticscholar-cord-19/2020-10-25/CORD19.ipynb",
    "entry_lk": "CORD19.ipynb",
    "entry_size": 467106,
    "entry_hash": {
      "type": "SHA256",
      "value": "d88b5c62414f3ef8f7decf10cad41686846017d5ea86fba2f714a26fa42ba901"
    }
  }
}
```

### How to Distinguish Between Them

**Filter by field existence:**

```python
# Search for MANIFESTS only (Package scope)
manifest_query = {
    'query': {
        'bool': {
            'must': [
                {'query_string': {'query': user_query}},
                {'exists': {'field': 'ptr_name'}}  # ← Manifests have this
            ]
        }
    }
}

# Search for ENTRIES only (PackageEntry scope)
entry_query = {
    'query': {
        'bool': {
            'must': [
                {'query_string': {'query': user_query}},
                {'exists': {'field': 'entry_pk'}}  # ← Entries have this
            ]
        }
    }
}
```

### Current Implementation Status

**What we have NOW:**

1. **PackageEntryScopeHandler** - ✅ IMPLEMENTED
   - Searches package indices
   - Parses ONLY entry documents
   - **Rejects manifests** (returns None)
   - Type: `"packageEntry"`

2. **PackageManifestScopeHandler** - ❌ NOT IMPLEMENTED
   - Would search package indices
   - Would parse ONLY manifest documents
   - Would reject entries
   - Type: `"package"`

### Verdict: ✅ YES - We Can Support Both Scopes

**Implementation approach:**

#### Option 1: Query-Level Filtering (RECOMMENDED)

Add filters to the DSL query based on scope:

```python
# In Quilt3ElasticsearchBackend.search()
if scope == "packageEntry":
    # Add entry_pk existence filter
    dsl_query["query"] = {
        "bool": {
            "must": [
                {"query_string": {"query": escaped_query}},
                {"exists": {"field": "entry_pk"}}  # Only entries
            ]
        }
    }
elif scope == "package":
    # Add ptr_name existence filter
    dsl_query["query"] = {
        "bool": {
            "must": [
                {"query_string": {"query": escaped_query}},
                {"exists": {"field": "ptr_name"}}  # Only manifests
            ]
        }
    }
```

**Pros:**
- ✅ Elasticsearch filters at query time (fast)
- ✅ Reduces network traffic (fewer documents returned)
- ✅ No need to filter in Python
- ✅ More efficient

**Cons:**
- Slightly more complex query building

#### Option 2: Parse-Level Filtering (CURRENT APPROACH)

Keep current approach where handlers return None for wrong document types:

```python
class PackageEntryScopeHandler:
    def parse_result(self, hit, bucket_name):
        source = hit.get("_source", {})

        # Reject manifests
        if source.get("ptr_name") or source.get("mnfst_name"):
            return None  # Filtered out

        # Only parse entries
        if not (source.get("entry_pk") or source.get("entry_lk")):
            return None  # Not an entry

        return SearchResult(...)  # Parse entry
```

**Pros:**
- ✅ Simple query building
- ✅ Flexible filtering logic
- ✅ Can add complex validation

**Cons:**
- ❌ Elasticsearch returns documents we discard (waste)
- ❌ Network overhead for unwanted documents
- ❌ May hit limit without getting enough valid results

### Recommended Implementation

**Use BOTH approaches together:**

1. **Query-level filtering** for document type (entry vs manifest)
2. **Parse-level validation** for quality/correctness

```python
# Query: Get only the right document type
dsl_query = {
    "query": {
        "bool": {
            "must": [
                {"query_string": {"query": escaped_query}},
                {"exists": {"field": "entry_pk" if scope == "packageEntry" else "ptr_name"}}
            ]
        }
    }
}

# Parse: Validate the document is actually valid
result = handler.parse_result(hit, bucket_name)
if result is None:  # Invalid/malformed document
    continue  # Skip it
```

---

## Implementation Plan: Adding Package (Manifest) Scope

### 1. Add PackageManifestScopeHandler

```python
class PackageManifestScopeHandler(ScopeHandler):
    """Handler for package MANIFEST searches ONLY.

    Searches for package versions/tags (ptr_name, mnfst_name).
    Entry documents are filtered out.
    """

    def build_index_pattern(self, buckets: List[str]) -> str:
        """Build index pattern for package indices."""
        if not buckets:
            raise ValueError("Cannot build index pattern: bucket list is empty")
        return ",".join(f"{b}_packages" for b in buckets)

    def parse_result(self, hit: Dict[str, Any], bucket_name: str) -> Optional[SearchResult]:
        """Parse a package MANIFEST result.

        CRITICAL: Only parses manifest documents (ptr_name, mnfst_name).
        Entry documents are REJECTED and return None.
        """
        source = hit.get("_source", {})

        # Get manifest fields
        ptr_name = source.get("ptr_name", "")
        mnfst_name = source.get("mnfst_name", "")
        ptr_tag = source.get("ptr_tag", "")
        last_modified = source.get("ptr_last_modified", "")

        # VALIDATION: Must be a manifest document
        if not ptr_name and not mnfst_name:
            # This is likely an entry document - reject it
            if source.get("entry_pk") or source.get("entry_lk"):
                logger.debug(
                    f"Skipping entry document in package scope. "
                    f"Document ID: {hit.get('_id', 'unknown')}"
                )
            else:
                logger.error(
                    f"PACKAGE MANIFEST VALIDATION FAILED: Document missing manifest fields. "
                    f"Document ID: {hit.get('_id', 'unknown')}, "
                    f"Available fields: {list(source.keys())[:10]}"
                )
            return None

        # Extract package name (before the slash if present)
        package_name = ptr_name or mnfst_name

        # Construct S3 URI to the package manifest
        s3_uri = None
        if bucket_name and mnfst_name:
            # Manifests are stored in .quilt/packages/
            s3_uri = f"s3://{bucket_name}/.quilt/packages/{mnfst_name}"

        return SearchResult(
            id=hit.get("_id", ""),
            type="package",  # Different from "packageEntry"
            name=ptr_name or mnfst_name,
            title=package_name.split("/")[-1] if "/" in package_name else package_name,
            description=f"Package: {package_name}" + (f" (tag: {ptr_tag})" if ptr_tag else ""),
            s3_uri=s3_uri,
            size=0,  # Manifests don't have size
            last_modified=last_modified,
            metadata={
                **source,
                "_index": hit.get("_index", ""),
                "package_name": package_name,
                "tag": ptr_tag,
            },
            score=hit.get("_score", 0.0),
            backend="elasticsearch",
            bucket=bucket_name,
            content_type="application/json",  # Manifests are JSON
            extension="",
        )

    def get_expected_result_type(self) -> str:
        return "package"
```

### 2. Register the Handler

```python
class Quilt3ElasticsearchBackend(SearchBackend):
    def __init__(self, quilt_service: Optional[QuiltService] = None):
        # ...
        self.scope_handlers = {
            "file": FileScopeHandler(),
            "packageEntry": PackageEntryScopeHandler(),
            "package": PackageManifestScopeHandler(),  # ← New!
            "global": GlobalScopeHandler(),
        }
```

### 3. Add Query-Level Filtering

```python
def search(self, query: str, scope: str = "global", ...):
    # Build base query
    dsl_query = {
        "from": 0,
        "size": limit,
        "query": {"query_string": {"query": escaped_query}},
    }

    # Add scope-specific filters
    if scope == "packageEntry":
        # Only return entry documents
        dsl_query["query"] = {
            "bool": {
                "must": [
                    {"query_string": {"query": escaped_query}},
                    {"exists": {"field": "entry_pk"}}
                ]
            }
        }
    elif scope == "package":
        # Only return manifest documents
        dsl_query["query"] = {
            "bool": {
                "must": [
                    {"query_string": {"query": escaped_query}},
                    {"exists": {"field": "ptr_name"}}
                ]
            }
        }

    # Execute search...
```

### 4. Update build_index_pattern_for_scope

```python
def build_index_pattern_for_scope(self, scope: str, buckets: List[str]) -> str:
    """Build index pattern for given scope and buckets."""
    handler = self.scope_handlers.get(scope)
    if not handler:
        raise ValueError(
            f"Invalid scope: {scope}. "
            f"Must be one of: {', '.join(self.scope_handlers.keys())}"
        )
    return handler.build_index_pattern(buckets)
```

### 5. Update Tests

Add integration tests for package manifest scope:

```python
async def test_package_manifest_handler_parses_real_documents(self, backend, default_bucket):
    """Test PackageManifestScopeHandler parses actual manifest documents ONLY."""
    response = await backend.search(
        query="*",
        scope="package",  # New scope!
        bucket=default_bucket,
        limit=20
    )

    assert response.status.value == "available"
    assert len(response.results) > 0, "No package manifests found"

    # ALL results must be MANIFEST documents
    for result in response.results:
        source = result.metadata

        # MUST have manifest fields
        assert "ptr_name" in source or "mnfst_name" in source

        # MUST NOT have entry fields
        assert "entry_pk" not in source and "entry_lk" not in source
```

---

## Summary

### Question A: Are we using quilt3.search() properly?

**Answer: ✅ YES - We're actually doing BETTER than quilt3.search()**

- We expose index control that quilt3 hides
- We support scope-based searching
- We provide typed results and error handling
- We handle multi-bucket 403 errors gracefully

### Question B: Can we support both Package and PackageEntry scopes?

**Answer: ✅ YES - Absolutely possible and straightforward**

**Current state:**
- ✅ `packageEntry` scope - Searches entry documents (files in packages)
- ❌ `package` scope - Not implemented yet (would search manifest documents)

**To add Package scope:**
1. Create `PackageManifestScopeHandler` (25 lines of code)
2. Register it in `scope_handlers` dict (1 line)
3. Add query-level filtering with `exists: {field: "ptr_name"}` (5 lines)
4. Add integration tests (20 lines)

**Total effort: ~1 hour of work**

---

## Files That Would Change

1. **src/quilt_mcp/search/backends/scope_handlers.py**
   - Add `PackageManifestScopeHandler` class

2. **src/quilt_mcp/search/backends/elasticsearch.py**
   - Register new handler in `scope_handlers` dict
   - Add query-level filtering for `package` vs `packageEntry`

3. **tests/integration/test_elasticsearch_index_discovery.py**
   - Add `test_package_manifest_handler_parses_real_documents()`
   - Add tests for package scope in other test classes

4. **spec/a07-search-catalog/23-quilt3-search-usage-analysis.md**
   - This document
