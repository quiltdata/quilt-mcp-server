# Current Scope and Bucket Semantics in search_catalog

**Status:** Active Specification
**Date:** 2025-11-15
**Version:** 0.9.1
**Related Code:**
- `/src/quilt_mcp/tools/search.py` (lines 26-128)
- `/src/quilt_mcp/search/backends/elasticsearch.py` (lines 202-266)
- `/src/quilt_mcp/search/tools/unified_search.py` (lines 32-179)

---

## Overview

The `search_catalog` tool uses two key parameters to control search scope:
1. **`scope`**: Determines WHAT to search (files, packages, or both)
2. **`bucket`**: Determines WHERE to search (specific bucket or all accessible buckets)

These parameters work together to build Elasticsearch index patterns that target the appropriate data.

---

## Parameter: `scope`

### Type and Valid Values
```python
scope: Literal["global", "package", "file"] = "file"
```

### Semantic Meaning

| Value | Meaning | Searches |
|-------|---------|----------|
| `"file"` | **File-level search** (default) | Object indices only: `{bucket_name}` |
| `"package"` | **Package-level search** | Package indices only: `{bucket_name}_packages` |
| `"global"` | **Universal search** | Both file AND package indices: `{bucket_name},{bucket_name}_packages` |

### Implementation Details

The scope directly controls which Elasticsearch indices are queried:
- **File scope**: Searches object indices (files stored in S3 buckets)
- **Package scope**: Searches package indices (Quilt package metadata)
- **Global scope**: Searches both object and package indices simultaneously

---

## Parameter: `bucket`

### Type and Valid Values
```python
bucket: str = ""
```

### Semantic Meaning

| Value | Meaning | Behavior |
|-------|---------|----------|
| `""` (empty string) | **All accessible buckets** | Enumerates ALL buckets from catalog and builds explicit comma-separated index pattern |
| `"mybucket"` | **Specific bucket** | Targets only `mybucket` indices |
| `"s3://mybucket"` | **S3 URI format** | Normalized to `mybucket`, then targets that bucket |

### Implementation Details

#### Empty Bucket (`bucket=""`)
When `bucket` is empty, the backend:
1. Calls `_get_available_buckets()` to fetch ALL bucket names from catalog via GraphQL
2. Prioritizes buckets using `_prioritize_buckets()` to put default bucket first
3. Builds explicit comma-separated index patterns (wildcard patterns like `*` are rejected by Quilt API)

**Example with 3 buckets (`default-bucket`, `bucket1`, `bucket2`):**
- `scope="file", bucket=""` → `"default-bucket,bucket1,bucket2"`
- `scope="package", bucket=""` → `"default-bucket_packages,bucket1_packages,bucket2_packages"`
- `scope="global", bucket=""` → `"default-bucket,default-bucket_packages,bucket1,bucket1_packages,bucket2,bucket2_packages"`

#### Specific Bucket (`bucket="mybucket"`)
When `bucket` is specified:
1. Bucket name is normalized (removes `s3://` prefix, trailing slashes)
2. Simple index patterns are built for that bucket only

**Example:**
- `scope="file", bucket="mybucket"` → `"mybucket"`
- `scope="package", bucket="mybucket"` → `"mybucket_packages"`
- `scope="global", bucket="mybucket"` → `"mybucket,mybucket_packages"`

---

## Scope × Bucket Combinations

### Matrix of Valid Combinations

| scope | bucket | Result Index Pattern | Use Case |
|-------|--------|---------------------|----------|
| `"file"` | `""` | `"bucket1,bucket2,..."` (all object indices) | Search all files across all buckets |
| `"file"` | `"mybucket"` | `"mybucket"` | Search files in specific bucket |
| `"package"` | `""` | `"bucket1_packages,bucket2_packages,..."` | Search all packages across all buckets |
| `"package"` | `"mybucket"` | `"mybucket_packages"` | Search packages in specific bucket |
| `"global"` | `""` | `"bucket1,bucket1_packages,..."` (all indices) | Search everything everywhere |
| `"global"` | `"mybucket"` | `"mybucket,mybucket_packages"` | Search files AND packages in specific bucket |

### All Combinations Are Valid
There are **NO invalid combinations** - every `scope` value works with every `bucket` value (empty or specified).

---

## Bucket Prioritization

### Default Bucket Priority
When searching all buckets (`bucket=""`), the backend prioritizes the user's default bucket:
1. Reads `QUILT_DEFAULT_BUCKET` environment variable
2. Normalizes to bucket name (removes `s3://` prefix)
3. Moves default bucket to front of list if present
4. Returns prioritized list: `[default_bucket, other_bucket1, other_bucket2, ...]`

### Why Prioritization Matters
- Elasticsearch may limit the number of indices searched
- Default bucket likely contains most relevant data for user
- Ensures best results appear even if search hits index limits

---

## Elasticsearch Index Limits and Retry Logic

### 403 Error Handling
When searching all buckets with many indices, Elasticsearch may return 403 "too many indices" errors.

**Retry Strategy (implemented in elasticsearch.py lines 333-379):**
1. Try full index pattern first
2. If 403 error AND multi-bucket search AND `bucket=""`:
   - Retry with progressively fewer buckets: [50, 40, 30, 20, 10]
   - Keep default bucket first (prioritization)
   - Stop at first successful response
3. If all retries fail, raise original error

**Example:**
```python
# Initial attempt with 84 buckets (168 indices for global scope)
index_pattern = "bucket1,bucket1_packages,bucket2,bucket2_packages,..."  # 168 indices

# Retry 1: 403 error → retry with 50 buckets (100 indices)
# Retry 2: 403 error → retry with 40 buckets (80 indices)
# Retry 3: Success! ✅
```

---

## Examples from Documentation

### File-Level Search Examples
```python
# Search all CSV files across all buckets
search_catalog("CSV files", scope="file", bucket="")

# Search CSV files in specific bucket
search_catalog("CSV files", scope="file", bucket="my-bucket")

# Search large files in specific bucket
search_catalog("files larger than 100MB", scope="file", bucket="s3://my-bucket")
```

### Package-Level Search Examples
```python
# Search all packages across all buckets
search_catalog("genomics packages", scope="package", bucket="")

# Search packages in specific bucket
search_catalog("packages created last month", scope="package", bucket="my-bucket")
```

### Global Search Examples
```python
# Search everything everywhere
search_catalog("README files", scope="global", bucket="")

# Search files AND packages in specific bucket
search_catalog("data", scope="global", bucket="my-bucket")
```

---

## Key Behavioral Notes

### 1. No Wildcard Patterns
The Quilt catalog API **rejects** wildcard patterns like:
- `"*"` (all indices)
- `"*_packages"` (all package indices)
- `"_all"` (special Elasticsearch pattern)

**Solution:** Explicit enumeration of bucket names from catalog via GraphQL.

### 2. Bucket Normalization
All bucket inputs are normalized:
- `"s3://mybucket"` → `"mybucket"`
- `"s3://mybucket/"` → `"mybucket"`
- `"mybucket/"` → `"mybucket"`

### 3. Empty Pattern = Error
If `_get_available_buckets()` returns empty list (no buckets available):
- Backend returns empty pattern `""`
- Search will fail with error

### 4. Default Backend
If `backend` parameter is not specified or empty, defaults to `"elasticsearch"` (only valid option).

---

## Code References

### Index Pattern Construction
**File:** `/src/quilt_mcp/search/backends/elasticsearch.py`
**Method:** `_build_index_pattern(scope: str, bucket: str) -> str`
**Lines:** 202-266

Key logic:
```python
def _build_index_pattern(self, scope: str, bucket: str) -> str:
    # Normalize bucket
    if bucket:
        bucket_name = bucket.replace("s3://", "").rstrip("/").split("/")[0]
    else:
        bucket_name = ""

    # Specific bucket - simple pattern
    if bucket_name:
        if scope == "file":
            return bucket_name
        elif scope == "package":
            return f"{bucket_name}_packages"
        else:  # global
            return f"{bucket_name},{bucket_name}_packages"

    # All buckets - enumerate and prioritize
    available_buckets = self._get_available_buckets()
    prioritized_buckets = self._prioritize_buckets(available_buckets)

    # Build explicit patterns
    if scope == "file":
        return ",".join(prioritized_buckets)
    elif scope == "package":
        return ",".join(f"{b}_packages" for b in prioritized_buckets)
    else:  # global
        file_indices = prioritized_buckets
        package_indices = [f"{b}_packages" for b in prioritized_buckets]
        return ",".join(file_indices + package_indices)
```

### Tool Interface
**File:** `/src/quilt_mcp/tools/search.py`
**Function:** `search_catalog(...)`
**Lines:** 26-128

Key parameter definitions:
```python
def search_catalog(
    query: str,
    scope: Literal["global", "package", "file"] = "file",
    bucket: str = "",
    backend: Literal["elasticsearch"] = "elasticsearch",
    limit: int = 50,
    include_metadata: bool = True,
    explain_query: bool = False,
    count_only: bool = False,
) -> Dict[str, Any]:
```

---

## Summary

The `scope` and `bucket` parameters work together to provide flexible, powerful search capabilities:

1. **`scope`** controls WHAT to search (files, packages, or both)
2. **`bucket`** controls WHERE to search (specific bucket or all accessible buckets)
3. All combinations are valid and produce predictable index patterns
4. Empty `bucket=""` triggers enumeration of ALL buckets with prioritization
5. Retry logic handles Elasticsearch index limits gracefully
6. Default bucket is prioritized to ensure most relevant results appear first

This design provides both simplicity (default `scope="file"` with `bucket=""`) and power (explicit control over scope and bucket targeting).
