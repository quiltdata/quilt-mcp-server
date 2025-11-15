# Simplified Search API Specification

**Date:** 2025-01-14
**Status:** 📋 Proposed
**Type:** API Design Specification

---

## Executive Summary

This spec defines a **simplified, rational, and testable** search API for Quilt MCP Server. Key improvements:

1. **Scope clarity**: `'global'`, `'package'`, `'object'` (not "bucket")
2. **Target simplicity**: `bucket` parameter (empty = all buckets)
3. **Backend rationality**: Single value `"elasticsearch"` (default when None/"")
4. **Result consistency**: Shared field names across types, distinguished by `type` field

---

## API Design

### Function Signature

```python
def search_catalog(
    query: str,
    scope: Literal["global", "package", "file"] = "file",
    bucket: str = "",
    backend: Literal["elasticsearch"] = "elasticsearch",
    limit: int = 50,
    include_metadata: bool = True,
    include_content_preview: bool = False,
    explain_query: bool = False,
    count_only: bool = False,
) -> Dict[str, Any]:
    """Intelligent unified search across Quilt catalog using Elasticsearch.

    Args:
        query: Natural language search query
        scope: Search scope - "file" (files in bucket), "package" (packages in catalog), "global" (everything)
        bucket: Target S3 bucket (s3://bucket-name or bucket-name). Empty = all buckets.
        backend: Backend to use - "elasticsearch" (only valid option)
        limit: Maximum number of results to return (default: 50)
        include_metadata: Include rich metadata in results (default: True)
        include_content_preview: Include content previews for files (default: False)
        explain_query: Include query execution explanation (default: False)
        count_only: Return aggregated counts only (default: False)

    Returns:
        Unified search results with metadata, explanations, and suggestions
    """
```

---

## Parameters

### 1. `scope` - Search Scope

**Type:** `Literal["global", "package", "file"]`
**Default:** `"file"`

| Scope | Searches | Returns | Use Case |
|-------|----------|---------|----------|
| `"file"` | Files within bucket(s) | File results | "Find CSV files in my data bucket" |
| `"package"` | Packages within catalog | Package results | "Find packages related to genomics" |
| `"global"` | Everything (files + packages) | Mixed results | "Find anything related to experiment_2024" |

**Rationale:**

- `"file"` matches the result `type` field for consistency
- `"package"` is clear and maps to Quilt concepts
- `"global"` is intuitive for cross-cutting searches
- Removed "bucket" and "object" as scope names to avoid confusion

### 2. `bucket` - Target Bucket

**Type:** `str`
**Default:** `""` (empty = all buckets)

**Behavior:**

- When `scope="file"`:
  - **Empty string** → Search across ALL buckets user has access to
  - **"my-bucket"** or **"s3://my-bucket"** → Search only this bucket
- When `scope="package"` or `scope="global"`:
  - **Empty string** → Search entire catalog
  - **"my-bucket"** → Filter results to packages/files in this bucket only

**Examples:**

```python
# Search all buckets for CSV files
search_catalog("CSV files", scope="file", bucket="")

# Search specific bucket
search_catalog("CSV files", scope="file", bucket="s3://my-data-bucket")

# Search all packages
search_catalog("genomics", scope="package", bucket="")

# Search packages in specific bucket
search_catalog("genomics", scope="package", bucket="my-data-bucket")
```

**Rationale:**

- Clear separation between scope (what to search) and bucket (where to search)
- Empty string = natural default for "search everything"
- Supports both bucket-only names and s3:// URIs for flexibility
- Replaces confusing `target` parameter with clearer `bucket` name

### 3. `backend` - Search Backend

**Type:** `Literal["elasticsearch"]`
**Default:** `"elasticsearch"`

**Behavior:**

- Only accepts `"elasticsearch"` as valid value
- Defaults to `"elasticsearch"` when `None` or `""`
- No other backends supported (GraphQL is broken, removed)

**Rationale:**

- Removes pretense of backend selection (only one works)
- Makes testing simpler (no backend switching logic)
- Clearer error messages if backend is down
- Future-proof: can add backends later if needed

---

## Result Types

### Unified Result Structure

All results share these core fields:

```python
{
    "id": str,              # Unique identifier
    "type": str,            # Result type: "file" or "package"
    "name": str,            # Unified identifier (path for files, package ID for packages)
    "title": str,           # Display name
    "description": str,     # Human-readable description
    "score": float,         # Relevance score
    "backend": str,         # Backend that provided this result
    "metadata": dict,       # Additional metadata (type-specific)
}
```

### Type: `"file"` - File/Object Results

**Used when:** `scope="file"` or `scope="global"` (mixed results)

```python
{
    "id": "s3://bucket/path/to/file.csv",
    "type": "file",
    "name": "path/to/file.csv",           # Path within bucket
    "title": "file.csv",                   # Filename for display
    "description": "CSV data file",
    "score": 1.5,
    "backend": "elasticsearch",

    # File-specific fields
    "s3_uri": "s3://bucket/path/to/file.csv",
    "bucket": "my-bucket",                 # Extracted bucket name
    "size": 1024,                          # Bytes
    "last_modified": "2025-01-14T10:00:00Z",
    "content_type": "text/csv",
    "extension": "csv",

    # Optional preview
    "content_preview": "col1,col2\nval1,val2\n...",  # If include_content_preview=True

    "metadata": {
        "user_metadata": {},               # User-defined metadata
        "system_metadata": {}              # System metadata
    }
}
```

### Type: `"package"` - Package Results

**Used when:** `scope="package"` or `scope="global"` (mixed results)

```python
{
    "id": "quilt+s3://bucket#package=namespace/name@abc123",
    "type": "package",
    "name": "namespace/name",              # Package identifier
    "title": "namespace/name",             # Package name for display
    "description": "Quilt package: namespace/name",
    "score": 2.1,
    "backend": "elasticsearch",

    # Package fields (same structure as files, but manifest-focused)
    "s3_uri": "s3://bucket/.quilt/packages/namespace/name/abc123.jsonl",  # Package manifest
    "bucket": "my-bucket",                 # Package registry bucket
    "size": 2048,                          # Manifest file size in bytes
    "last_modified": "2025-01-14T10:00:00Z",  # Last push time
    "content_type": "application/jsonl",   # Manifest is JSONL
    "extension": "jsonl",                  # Manifest extension

    # Optional preview
    "content_preview": '{"logical_key":"file1.csv","physical_keys":...}\n{"logical_key":"file2.csv",...',  # If include_content_preview=True

    "metadata": {
        "hash": "abc123...",               # Package hash
        "version": "latest",               # Version tag
        "author": "user@example.com",
        "created": "2025-01-01T00:00:00Z",
        "num_files": 42,                   # Total files in package
        "total_size": 10485760,            # Total size of all files in package
    }
}
```

---

## Field Design Rationale

### Shared Fields Across Types

These fields have **same name and semantic meaning** for both files and packages:

| Field | Files | Packages | Rationale |
|-------|-------|----------|-----------|
| `name` | Path within bucket | Package identifier | Unified identifier concept |
| `title` | Filename | Package name | Display name concept |
| `s3_uri` | Object URI | Manifest URI | Both are S3 locations |
| `bucket` | Object's bucket | Registry bucket | Both exist in buckets |
| `last_modified` | Object timestamp | Last push time | Both have modification times |
| `metadata` | User/system metadata | Package metadata | Both can have rich metadata |

### Type-Specific Values

All shared fields have **meaningful values** for both types:

| Field | Files | Packages | Rationale |
|-------|-------|----------|-----------|
| `size` | File size in bytes | Package manifest size in bytes | Both are S3 objects with sizes |
| `content_type` | MIME type (e.g., `text/csv`) | `application/jsonl` | Package manifest is JSONL |
| `extension` | File extension (e.g., `csv`) | `jsonl` | Package manifest has extension |
| `content_preview` | File content preview | Package manifest preview (first few entries) | Both can be previewed |

### Distinguishing Results

**Use the `type` field** to determine result type:

```python
for result in search_results:
    if result["type"] == "file":
        # Handle file: result["name"] is path, result["s3_uri"] is full URI
        download_file(result["s3_uri"])
    elif result["type"] == "package":
        # Handle package: result["name"] is package ID
        install_package(result["name"])
```

---

## Usage Examples

### Example 1: Search Files in Specific Bucket

```python
result = search_catalog(
    query="CSV files larger than 1MB",
    scope="file",
    bucket="s3://my-data-bucket",
    limit=20
)

# Returns only file results
for file in result["results"]:
    assert file["type"] == "file"
    print(f"Found: {file['name']} ({file['size']} bytes)")
```

### Example 2: Search Packages Globally

```python
result = search_catalog(
    query="genomics experiment",
    scope="package",
    bucket="",  # All buckets
    limit=10
)

# Returns only package results
for pkg in result["results"]:
    assert pkg["type"] == "package"
    print(f"Package: {pkg['name']} - {pkg['description']}")
```

### Example 3: Global Search (Mixed Results)

```python
result = search_catalog(
    query="RNA-seq data 2024",
    scope="global",
    bucket="",
    limit=50
)

# Returns mixed results
files = [r for r in result["results"] if r["type"] == "file"]
packages = [r for r in result["results"] if r["type"] == "package"]

print(f"Found {len(files)} files and {len(packages)} packages")
```

### Example 4: Count-Only Query

```python
result = search_catalog(
    query="parquet files",
    scope="file",
    bucket="my-bucket",
    count_only=True
)

print(f"Total results: {result['total_results']}")
print(f"Query time: {result['query_time_ms']}ms")
# result["results"] is empty (count_only=True)
```

---

## Response Structure

### Success Response

```python
{
    "success": True,
    "query": "CSV files",
    "scope": "file",
    "bucket": "my-bucket",
    "backend_used": "elasticsearch",

    "results": [
        {
            "id": "...",
            "type": "file",
            "name": "...",
            # ... full result object
        },
        # ... more results
    ],

    "total_results": 42,
    "query_time_ms": 123.45,

    # Optional fields
    "analysis": {
        "detected_filters": ["extension:csv"],
        "query_complexity": "simple"
    },

    "backend_status": {
        "elasticsearch": "healthy"
    },

    "backend_info": {
        "elasticsearch": {
            "endpoint": "https://...",
            "index": "objects"
        }
    },

    "explanation": {
        # Included when explain_query=True
        "query_analysis": {...},
        "backend_selection": {...},
        "execution_plan": {...}
    }
}
```

### Error Response

```python
{
    "success": False,
    "error": "Search backend unavailable: Connection timeout",
    "query": "CSV files",
    "scope": "file",
    "bucket": "my-bucket",
    "backend_used": "elasticsearch",
    "backend_status": {
        "elasticsearch": "unhealthy"
    }
}
```

---

## Validation Rules

### Parameter Validation

```python
# scope validation
assert scope in ["global", "package", "file"], \
    f"Invalid scope: {scope}. Must be 'global', 'package', or 'file'"

# backend validation
if backend is None or backend == "":
    backend = "elasticsearch"
assert backend == "elasticsearch", \
    f"Invalid backend: {backend}. Only 'elasticsearch' is supported"

# bucket normalization
if bucket.startswith("s3://"):
    bucket = bucket[5:].split("/")[0]  # Extract bucket name from URI

# limit validation
assert 1 <= limit <= 1000, \
    f"Invalid limit: {limit}. Must be between 1 and 1000"
```

### Result Validation

```python
# All results must have required fields
required_fields = {"id", "type", "name", "title", "score", "backend"}
for result in results:
    assert required_fields.issubset(result.keys()), \
        f"Result missing required fields: {required_fields - result.keys()}"

# Type field must be valid
assert result["type"] in ["file", "package"], \
    f"Invalid result type: {result['type']}"

# All results must have s3_uri
assert "s3_uri" in result and result["s3_uri"], \
    f"{result['type']} result missing s3_uri"
assert result["s3_uri"].startswith("s3://"), \
    f"Invalid s3_uri: {result['s3_uri']}"

# All results must have size, content_type, extension
assert "size" in result and isinstance(result["size"], int), \
    f"{result['type']} result missing or invalid size"
assert "content_type" in result and result["content_type"], \
    f"{result['type']} result missing content_type"
assert "extension" in result and result["extension"], \
    f"{result['type']} result missing extension"
```

---

## Migration from Current API

### Parameter Changes

| Old Parameter | New Parameter | Change |
|---------------|---------------|--------|
| `scope: "bucket"` | `scope: "file"` | Renamed for clarity and consistency |
| `target: str` | `bucket: str` | Renamed, simplified |
| `backend: Optional[Literal["elasticsearch", "graphql"]]` | `backend: Literal["elasticsearch"]` | Removed broken option |

### Backward Compatibility

**Breaking changes:**

1. `scope="bucket"` → `scope="file"` (rename required)
2. `target` parameter → `bucket` parameter (rename required)
3. `backend="graphql"` → No longer supported (error raised)
4. Package `id` format → Changed to `quilt+s3://` URI format (parallels `s3://` for files)

**Migration path:**

```python
# Before
search_catalog(query="...", scope="bucket", target="s3://my-bucket", backend="elasticsearch")

# After
search_catalog(query="...", scope="file", bucket="s3://my-bucket", backend="elasticsearch")
```

**Migration script:**

```python
def migrate_search_call(old_params: dict) -> dict:
    """Migrate old API calls to new API."""
    new_params = old_params.copy()

    # Rename scope
    if new_params.get("scope") == "bucket":
        new_params["scope"] = "file"

    # Rename target to bucket
    if "target" in new_params:
        new_params["bucket"] = new_params.pop("target")

    # Remove graphql backend
    if new_params.get("backend") == "graphql":
        new_params["backend"] = "elasticsearch"
        print("Warning: graphql backend no longer supported, using elasticsearch")

    return new_params
```

---

## Testing Strategy

### Unit Tests

```python
# Test scope values
def test_scope_file():
    result = search_catalog("test", scope="file")
    assert all(r["type"] == "file" for r in result["results"])

def test_scope_package():
    result = search_catalog("test", scope="package")
    assert all(r["type"] == "package" for r in result["results"])

def test_scope_global():
    result = search_catalog("test", scope="global")
    types = {r["type"] for r in result["results"]}
    assert types.issubset({"file", "package"})

# Test bucket parameter
def test_bucket_empty_searches_all():
    result = search_catalog("test", scope="file", bucket="")
    # Should search all accessible buckets

def test_bucket_specific_filters():
    result = search_catalog("test", scope="file", bucket="my-bucket")
    assert all("my-bucket" in r["s3_uri"] for r in result["results"])

def test_bucket_s3_uri_normalized():
    result1 = search_catalog("test", scope="file", bucket="my-bucket")
    result2 = search_catalog("test", scope="file", bucket="s3://my-bucket")
    assert result1 == result2  # Same results regardless of format

# Test backend parameter
def test_backend_default():
    result = search_catalog("test")
    assert result["backend_used"] == "elasticsearch"

def test_backend_explicit():
    result = search_catalog("test", backend="elasticsearch")
    assert result["backend_used"] == "elasticsearch"

def test_backend_invalid_raises():
    with pytest.raises(ValueError, match="Only 'elasticsearch' is supported"):
        search_catalog("test", backend="graphql")

# Test result structure
def test_file_result_structure():
    result = search_catalog("test.csv", scope="file")
    file = result["results"][0]
    assert file["type"] == "file"
    assert all(field in file for field in ["id", "name", "title", "s3_uri", "size"])
    assert file["id"].startswith("s3://")  # File ID is s3:// URI

def test_package_result_structure():
    result = search_catalog("test", scope="package")
    pkg = result["results"][0]
    assert pkg["type"] == "package"
    # Packages have same fields as files (manifest-focused)
    assert all(field in pkg for field in ["id", "name", "title", "s3_uri", "size"])
    assert pkg["id"].startswith("quilt+s3://")  # Package ID is quilt+s3:// URI
    assert pkg["content_type"] == "application/jsonl"
    assert pkg["extension"] == "jsonl"
    assert pkg["size"] > 0  # Manifest has a size
    # Total package size is in metadata
    assert "total_size" in pkg["metadata"]
```

### Integration Tests

```python
def test_end_to_end_file_search():
    """Test searching files in a real bucket."""
    result = search_catalog(
        query="*.csv",
        scope="file",
        bucket="test-bucket",
        limit=10
    )
    assert result["success"]
    assert len(result["results"]) > 0
    assert all(r["type"] == "file" for r in result["results"])
    assert all(r["extension"] == "csv" for r in result["results"])
    assert all(r["id"].startswith("s3://") for r in result["results"])

def test_end_to_end_package_search():
    """Test searching packages in catalog."""
    result = search_catalog(
        query="test",
        scope="package",
        bucket="",
        limit=10
    )
    assert result["success"]
    assert all(r["type"] == "package" for r in result["results"])
    assert all(r["id"].startswith("quilt+s3://") for r in result["results"])

def test_end_to_end_global_search():
    """Test global search with mixed results."""
    result = search_catalog(
        query="genomics",
        scope="global",
        bucket="",
        limit=50
    )
    assert result["success"]
    types = {r["type"] for r in result["results"]}
    assert "file" in types or "package" in types  # At least one type
```

---

## Benefits of This Design

### 1. Clearer Semantics

**Old API:**

- `scope="bucket"` + `target="s3://bucket"` → Confusing overlap
- What's the difference between scope and target?

**New API:**

- `scope="file"` → What to search (files)
- `bucket="my-bucket"` → Where to search (which bucket)
- Clear separation of concerns

### 2. Simpler Logic

**Old API:**

```python
if scope == "bucket" and target:
    # Search specific bucket
elif scope == "bucket" and not target:
    # Search default bucket from env var
elif scope == "package" and target:
    # Search specific package
elif scope == "package" and not target:
    # Search all packages
```

**New API:**

```python
if scope == "file":
    if bucket:
        # Search specific bucket
    else:
        # Search all buckets
elif scope == "package":
    if bucket:
        # Filter packages to bucket
    else:
        # Search all packages
```

### 3. Better Testability

- Each parameter has clear, testable behavior
- Fewer edge cases and special handling
- Easier to mock and validate
- Clear assertion patterns

### 4. Future-Proof

- Can add backends later without breaking changes
- Scope can expand (e.g., `"user"`, `"tag"`) without confusion
- Result structure supports new types easily
- Extensible metadata fields

---

## API Reference Summary

### Signatures

```python
# Main search function
def search_catalog(
    query: str,
    scope: Literal["global", "package", "file"] = "file",
    bucket: str = "",
    backend: Literal["elasticsearch"] = "elasticsearch",
    limit: int = 50,
    include_metadata: bool = True,
    include_content_preview: bool = False,
    explain_query: bool = False,
    count_only: bool = False,
) -> Dict[str, Any]: ...

# Helper functions (updated for consistency)
def search_suggest(
    partial_query: str,
    context: str = "",
    suggestion_types: Optional[List[str]] = None,
    limit: int = 10,
) -> Dict[str, Any]: ...

def search_explain(
    query: str,
    scope: Literal["global", "package", "file"] = "global",
    bucket: str = "",
) -> SearchExplainSuccess | SearchExplainError: ...

def search_graphql(
    query: str,
    variables: Optional[Dict] = None,
) -> SearchGraphQLSuccess | SearchGraphQLError: ...

def search_objects_graphql(
    bucket: str,
    object_filter: Optional[Dict] = None,
    first: int = 100,
    after: str = "",
) -> Dict[str, Any]: ...
```

---

## Open Questions

### 1. Should `bucket` support glob patterns?

```python
# Future possibility?
search_catalog("test", scope="file", bucket="data-*")  # Search all buckets starting with "data-"
```

**Decision:** No, not in initial implementation. Keep it simple.

### 2. Should we add `package` filter for file search?

```python
# Search files within a specific package?
search_catalog("CSV", scope="file", bucket="my-bucket", package="user/dataset")
```

**Decision:** No, packages are already scoped to buckets. Use `scope="package"` instead.

### 3. Should `scope="global"` search across catalogs?

**Current:** Global searches within current authenticated catalog
**Future:** Could support multi-catalog federation

**Decision:** Keep current behavior. Multi-catalog is out of scope.

---

## Conclusion

This specification defines a **simplified, rational, and testable** search API that:

1. ✅ Uses clear scope names that match result types (`file`, `package`, `global`)
2. ✅ Separates "what to search" (scope) from "where to search" (bucket)
3. ✅ Removes pretense of backend selection (only elasticsearch works)
4. ✅ Provides consistent result structure across types (all fields have meaningful values)
5. ✅ Uses parallel URI schemes for IDs (`s3://` for files, `quilt+s3://` for packages)
6. ✅ Enables easy testing and validation
7. ✅ Supports future extensibility

**Next Steps:**

1. Review and approve this spec
2. Implement parameter changes in `search.py`
3. Update result processing to ensure consistency
4. Write comprehensive tests
5. Update documentation and examples

---

**Status:** 📋 **Awaiting Review**
**Feedback:** Please review and approve before implementation
