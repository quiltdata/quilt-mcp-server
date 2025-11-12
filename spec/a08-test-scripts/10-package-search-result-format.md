# Fix: Package Search Result Format

**Status:** Proposed
**Created:** 2025-01-12
**Component:** `search_catalog` tool - Elasticsearch backend package results

## Problem Statement

When searching for packages using `search_catalog`, the results are malformed with critical package information buried in the metadata field instead of being at the top level where it belongs.

### Current Behavior

```json
{
  "id": "mnfst:60066af2bd6dc0103b6c84cf89566885d36642ba195c1b9e42144f0dca6ef7f9",
  "type": "package",
  "title": "Unknown",
  "description": "Object in s3://quilt-ernest-staging",
  "score": 3.913788,
  "backend": "elasticsearch",
  "s3_uri": null,
  "package_name": null,
  "logical_key": "",
  "size": 0,
  "last_modified": "",
  "metadata": {
    "mnfst_hash": "60066af2bd6dc0103b6c84cf89566885d36642ba195c1b9e42144f0dca6ef7f9",
    "mnfst_last_modified": "2023-12-12T00:45:41+00:00",
    "mnfst_message": "{\"bucket\": \"quilt-ernest-staging\", \"package\": \"test/omics-quilt-demo\"}",
    "mnfst_metadata": "{\"META\":\"./tests/outputs/8637245/quilt_metadata.json\",\"REPORT\":\"./tests/outputs/8637245/out/bqsr_rep...\",
    "mnfst_stats": { ... } 2 items,
    "mnfst_workflow": { ... } 3 items
  }
}
```

**Issues:**
1. `title: "Unknown"` instead of the actual package name
2. `description: "Object in s3://quilt-ernest-staging"` generic and unhelpful
3. `package_name: null` when it should be `"test/omics-quilt-demo"`
4. `s3_uri: null` could be constructed as `quilt+s3://...`
5. All useful package information is nested in `metadata` dict
6. `size` and `last_modified` are 0/"" when real values exist in metadata

### Expected Behavior

```json
{
  "id": "mnfst:60066af2bd6dc0103b6c84cf89566885d36642ba195c1b9e42144f0dca6ef7f9",
  "type": "package",
  "title": "test/omics-quilt-demo",
  "description": "Package in quilt-ernest-staging",
  "score": 3.913788,
  "backend": "elasticsearch",
  "s3_uri": "quilt+s3://quilt-ernest-staging#package=test/omics-quilt-demo",
  "package_name": "test/omics-quilt-demo",
  "logical_key": null,
  "size": 292, // from mnfs_stats.total_bytes
  "last_modified": "2023-12-12T00:45:41+00:00",
  "metadata": {
    "hash": "60066af2bd6dc0103b6c84cf89566885d36642ba195c1b9e42144f0dca6ef7f9",
    "message": "{\"bucket\": \"quilt-ernest-staging\", \"package\": \"test/omics-quilt-demo\"}",
    "stats": { ... },
    "workflow": { ... }
  }
}
```

## Root Cause Analysis

The issue is in `elasticsearch.py:_convert_catalog_results()` (lines 381-404):

```python
def _convert_catalog_results(self, raw_results: List[Dict[str, Any]]) -> List[SearchResult]:
    """Convert catalog search results to standard format."""
    results = []

    for hit in raw_results:
        source = hit.get("_source", {})

        # Extract package information
        package_name = source.get("ptr_name", source.get("mnfst_name", ""))  # ❌ This field doesn't exist

        result = SearchResult(
            id=hit.get("_id", ""),
            type="package",
            title=package_name,  # ❌ Empty string becomes "Unknown" via default
            description=f"Quilt package: {package_name}",  # ❌ "Quilt package: "
            package_name=package_name,  # ❌ None
            metadata=source,  # ❌ All raw fields dumped here
            score=hit.get("_score", 0.0),
            backend="elasticsearch",
        )

        results.append(result)

    return results
```

### Problems

1. **Wrong field name**: Looking for `ptr_name`/`mnfst_name` but the actual field is in `mnfst_message` as a JSON string
2. **No parsing of nested JSON**: The `mnfst_message` field contains a JSON object with bucket and package names
3. **No extraction of important fields**: Hash, last_modified, etc. are not extracted from their `mnfst_*` prefixed fields
4. **Raw metadata dumping**: The entire `_source` is dumped into `metadata` instead of being selectively extracted

## Solution Design

### 1. Parse Package Information

Extract and parse the package information from the Elasticsearch document:

```python
def _extract_package_info(self, source: Dict[str, Any]) -> tuple[str, str, str]:
    """Extract bucket, package name, and hash from catalog search result.

    Returns:
        (bucket, package_name, hash)
    """
    import json

    # Parse the mnfst_message JSON
    message_str = source.get("mnfst_message", "{}")
    try:
        message = json.loads(message_str)
        bucket = message.get("bucket", "")
        package_name = message.get("package", "")
    except (json.JSONDecodeError, AttributeError):
        bucket = ""
        package_name = ""

    # Get the hash
    hash_value = source.get("mnfst_hash", "")

    return bucket, package_name, hash_value
```

### 2. Build Proper Quilt+ URI

Find and reuse existing code from other tools

### 3. Clean Metadata

Only keep relevant metadata fields, removing the `mnfst_` prefix:

```python
def _clean_package_metadata(self, source: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and clean relevant metadata from catalog result.

    Args:
        source: Raw _source dict from Elasticsearch

    Returns:
        Cleaned metadata dict with user-relevant fields
    """
    metadata = {}

    # Extract specific fields, removing mnfst_ prefix
    if "mnfst_hash" in source:
        metadata["hash"] = source["mnfst_hash"]

    if "mnfst_message" in source:
        metadata["message"] = source["mnfst_message"]

    if "mnfst_metadata" in source:
        metadata["package_metadata"] = source["mnfst_metadata"]

    if "mnfst_stats" in source:
        metadata["stats"] = source["mnfst_stats"]

    if "mnfst_workflow" in source:
        metadata["workflow"] = source["mnfst_workflow"]

    if "mnfst_user_meta" in source:
        metadata["user_meta"] = source["mnfst_user_meta"]

    return metadata
```

### 4. Updated Conversion Function

```python
def _convert_catalog_results(self, raw_results: List[Dict[str, Any]]) -> List[SearchResult]:
    """Convert catalog search results to standard format."""
    results = []

    for hit in raw_results:
        source = hit.get("_source", {})

        # Extract package information
        bucket, package_name, hash_value = self._extract_package_info(source)

        # Build Quilt+ URI
        quilt_uri = self._build_quilt_uri(bucket, package_name, hash_value) if package_name else None

        # Get last modified date
        last_modified = source.get("mnfst_last_modified", "")

        # Clean metadata
        clean_metadata = self._clean_package_metadata(source)

        result = SearchResult(
            id=hit.get("_id", ""),
            type="package",
            title=package_name or "Unknown Package",
            description=f"Package in {bucket}" if bucket else "Quilt package",
            s3_uri=quilt_uri,
            package_name=package_name or None,
            logical_key=None,  # Packages don't have logical keys
            size=mnfs_stats.total_bytes,
            last_modified=last_modified,
            metadata=clean_metadata,
            score=hit.get("_score", 0.0),
            backend="elasticsearch",
        )

        results.append(result)

    return results
```

## Implementation Steps

1. **Add helper methods** to `Quilt3ElasticsearchBackend`:
   - [ ] `_extract_package_info(source)`
   - [ ] `_clean_package_metadata(source)`

2. **Update `_convert_catalog_results()`** to use the new helpers

3. **Add tests** in `test_elasticsearch.py`:
   - [ ] Test parsing of `mnfst_message` JSON
   - [ ] Test Quilt+ URI construction
   - [ ] Test metadata cleaning
   - [ ] Test handling of malformed/missing fields
   - [ ] Integration test comparing before/after result format

4. **Update documentation** to reflect the new result structure

## Testing

### Unit Tests

```python
def test_extract_package_info():
    """Test parsing of package info from catalog results."""
    backend = Quilt3ElasticsearchBackend()

    source = {
        "mnfst_hash": "60066af2bd6dc0103b6c84cf89566885d36642ba195c1b9e42144f0dca6ef7f9",
        "mnfst_message": '{"bucket": "quilt-ernest-staging", "package": "test/omics-quilt-demo"}'
    }

    bucket, package_name, hash_value = backend._extract_package_info(source)

    assert bucket == "quilt-ernest-staging"
    assert package_name == "test/omics-quilt-demo"
    assert hash_value == "60066af2bd6dc0103b6c84cf89566885d36642ba195c1b9e42144f0dca6ef7f9"

def test_build_quilt_uri():
    """Test Quilt+ URI construction."""
    backend = Quilt3ElasticsearchBackend()

    uri = backend._build_quilt_uri(
        "quilt-ernest-staging",
        "test/omics-quilt-demo",
        "60066af2bd6dc0103b6c84cf89566885d36642ba195c1b9e42144f0dca6ef7f9"
    )

    assert uri == "quilt+s3://quilt-ernest-staging#package=test/omics-quilt-demo@60066af2"

def test_clean_package_metadata():
    """Test metadata cleaning."""
    backend = Quilt3ElasticsearchBackend()

    source = {
        "mnfst_hash": "60066af2",
        "mnfst_message": '{"bucket": "test"}',
        "mnfst_stats": {"count": 100},
        "mnfst_workflow": {"steps": []},
        "mnfst_extra_field": "ignored"  # Should be filtered out
    }

    metadata = backend._clean_package_metadata(source)

    assert metadata["hash"] == "60066af2"
    assert metadata["message"] == '{"bucket": "test"}'
    assert metadata["stats"] == {"count": 100}
    assert metadata["workflow"] == {"steps": []}
    assert "mnfst_extra_field" not in metadata
    assert "extra_field" not in metadata
```

### Integration Test

```python
async def test_catalog_search_package_format():
    """Test that catalog search returns properly formatted package results."""
    service = QuiltService()
    backend = Quilt3ElasticsearchBackend(service)

    # Search for packages
    response = await backend.search("*", scope="global", limit=10)

    assert response.status == BackendStatus.AVAILABLE
    assert len(response.results) > 0

    # Check first package result
    pkg = response.results[0]
    assert pkg.type == "package"
    assert pkg.title != "Unknown"
    assert pkg.package_name is not None
    assert pkg.package_name in pkg.title
    assert pkg.s3_uri is not None
    assert pkg.s3_uri.startswith("quilt+s3://")
    assert "package=" in pkg.s3_uri

    # Check metadata is cleaned
    assert "mnfst_hash" not in pkg.metadata
    assert "hash" in pkg.metadata or len(pkg.metadata) == 0
```

## Impact Assessment

### Affected Components

- **Primary:** `src/quilt_mcp/search/backends/elasticsearch.py`
- **Tests:** `tests/search/backends/test_elasticsearch.py`
- **Documentation:** Search API documentation

### Backward Compatibility

This is a **breaking change** to the search result format. However:

1. The `SearchResult` dataclass schema doesn't change
2. Only the values populated in the fields change
3. The raw data is still available via the Elasticsearch API directly if needed
4. This is an internal MCP server, so external API compatibility is not a concern

### Migration Path

For any code depending on the old format:

```python
# Old code that looked in metadata
package_name = result.metadata.get("mnfst_message", "")
# Parse JSON, etc...

# New code uses top-level field
package_name = result.package_name
```

## Future Enhancements

1. **Package size calculation**: Aggregate size from package contents
2. **Version information**: Extract and expose version tags
3. **Rich descriptions**: Parse package metadata for user-provided descriptions
4. **Thumbnail support**: Extract and link to package thumbnails
5. **Author information**: Extract and expose package authors from metadata

## References

- Elasticsearch package manifest schema
- Quilt+ URI specification
- `SearchResult` dataclass in `base.py`
- Existing `_convert_bucket_results()` implementation for comparison

## Acceptance Criteria

- [ ] Package search results have correct `title` (package name)
- [ ] Package search results have correct `package_name` field
- [ ] Package search results have valid Quilt+ URI in `s3_uri`
- [ ] Package search results have cleaned metadata (no `mnfst_` prefixes)
- [ ] Package search results have correct `last_modified` timestamp
- [ ] All unit tests pass
- [ ] Integration test confirms format improvement
- [ ] No regression in bucket search results

## NOTES

1. package search with '/' causes errors
2. grapqhl package search returns bucket search

