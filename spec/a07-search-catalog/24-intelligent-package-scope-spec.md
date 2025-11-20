# Intelligent Package Scope Specification

**Date**: 2025-11-15
**Status**: Draft
**Related**: [23-quilt3-search-usage-analysis.md](./23-quilt3-search-usage-analysis.md)

---

## Executive Summary

This spec defines an **intelligent `package` scope** that addresses real user queries like:
- "Find me all CCLE packages containing a csv file"
- "Which packages have RNA-seq data?"
- "Show me packages about 'drug resistance' with Excel files"

The intelligent package scope searches both manifests and entries, but returns **package-centric results** with matched entry information aggregated.

---

## Problem Statement

### Current Limitation

The existing implementation has:
- ✅ `packageEntry` scope - Returns individual files
- ❌ No `package` scope - Can't answer "which packages contain X?"

### User Intent Gap

When users query packages, they typically want:
1. **Package-level results** (not individual files)
2. **Entry-aware filtering** ("packages containing CSV files")
3. **Aggregated information** (how many matching files, which ones)

Example user query:
```
"Find all CCLE packages that contain CSV files"
```

Expected behavior:
- Search both manifests (for "CCLE") and entries (for "csv")
- Group results by package
- Return packages with matched entry details

**NOT expected:**
- Return 1000+ individual CSV files (that's `packageEntry` scope)
- Return only manifest metadata with no entry info (too limited)

---

## Scope Comparison

| Scope | Searches | Returns | Groups By | Use Case |
|-------|----------|---------|-----------|----------|
| `file` | File indices | S3 objects | None | "Find loose CSV files in bucket" |
| `packageEntry` | Package indices (entries only) | Individual files | None | "Find all CSV files in packages" |
| `package` ⭐ NEW | Package indices (manifests + entries) | Packages | Package name | "Find packages containing CSV files" |
| `global` | All indices | Mixed results | None | "Find anything matching query" |

---

## Detailed Specification

### Query Behavior

**Input:**
```python
search(
    query="CCLE AND csv",
    scope="package",
    bucket="my-bucket",
    limit=10
)
```

**Elasticsearch Query Strategy:**

```python
{
    "query": {
        "bool": {
            "must": [
                {"query_string": {"query": "CCLE AND csv"}},
                # Search both manifests AND entries
            ],
            "should": [
                # Boost packages where manifest matches
                {"exists": {"field": "ptr_name", "boost": 2.0}},
                # Also match entries
                {"exists": {"field": "entry_pk"}}
            ]
        }
    },
    "collapse": {
        # Group by package name
        "field": "ptr_name.keyword",
        "inner_hits": {
            "name": "matched_entries",
            "size": 100,  # Get up to 100 matching entries per package
            "_source": ["entry_lk", "entry_pk", "entry_size", "entry_metadata"]
        }
    },
    "size": 10  # Return 10 packages
}
```

### Result Format

**SearchResult schema for package scope:**

```python
SearchResult(
    id="abc123",
    type="package",
    name="CCLE/2024-01-15",  # Package name (ptr_name)
    title="CCLE",  # Display name
    description="Package: CCLE/2024-01-15 (tag: latest) - Contains 15 matched files",
    s3_uri="s3://bucket/.quilt/packages/manifest_hash",
    size=0,  # Manifests don't have size
    last_modified="2024-01-15T10:30:00Z",
    metadata={
        "ptr_name": "CCLE/2024-01-15",
        "ptr_tag": "latest",
        "mnfst_name": "manifest_hash",
        "matched_entries": [
            {
                "entry_lk": "data/expression.csv",
                "entry_pk": "s3://bucket/.../expression.csv",
                "entry_size": 12345678,
                "entry_metadata": {...}
            },
            {
                "entry_lk": "metadata/samples.csv",
                "entry_pk": "s3://bucket/.../samples.csv",
                "entry_size": 45678,
                "entry_metadata": {...}
            }
            # ... up to 100 entries
        ],
        "matched_entry_count": 15,  # Total matched entries
        "showing_entries": 15,  # How many included in result
        "_index": "bucket_packages"
    },
    score=2.45,
    backend="elasticsearch",
    bucket="my-bucket",
    content_type="application/json",
    extension=""
)
```

### Implementation Components

#### 1. PackageScopeHandler

**Location:** `src/quilt_mcp/search/backends/scope_handlers.py`

```python
class PackageScopeHandler(ScopeHandler):
    """Handler for INTELLIGENT package searches.

    Searches both manifests and entries in package indices,
    but groups results by package and includes matched entry details.

    This is different from:
    - PackageEntryScopeHandler: Returns individual files
    - (Future) PackageManifestOnlyHandler: Returns only manifest metadata
    """

    def build_index_pattern(self, buckets: List[str]) -> str:
        """Build index pattern for package indices."""
        if not buckets:
            raise ValueError("Cannot build index pattern: bucket list is empty")
        return ",".join(f"{b}_packages" for b in buckets)

    def build_query_filter(self, base_query: str) -> Dict[str, Any]:
        """Build query that searches both manifests and entries.

        Does NOT filter by document type - we want both!
        But uses field boosts to prefer packages where manifest matches.
        """
        return {
            "bool": {
                "must": [
                    {"query_string": {"query": base_query}}
                ],
                "should": [
                    # Boost if manifest fields match
                    {
                        "bool": {
                            "must": [
                                {"exists": {"field": "ptr_name"}},
                                {"query_string": {
                                    "query": base_query,
                                    "fields": ["ptr_name^2", "ptr_tag"]
                                }}
                            ],
                            "boost": 2.0
                        }
                    },
                    # Also match entries
                    {
                        "bool": {
                            "must": [
                                {"exists": {"field": "entry_pk"}},
                                {"query_string": {
                                    "query": base_query,
                                    "fields": ["entry_lk", "entry_pk"]
                                }}
                            ]
                        }
                    }
                ],
                "minimum_should_match": 1
            }
        }

    def build_collapse_config(self) -> Dict[str, Any]:
        """Build collapse configuration to group by package.

        This is the KEY feature of intelligent package scope:
        - Group results by ptr_name (package name)
        - Include matched entries as inner_hits
        """
        return {
            "field": "ptr_name.keyword",
            "inner_hits": {
                "name": "matched_entries",
                "size": 100,  # Up to 100 matched entries per package
                "_source": [
                    "entry_lk",
                    "entry_pk",
                    "entry_size",
                    "entry_hash",
                    "entry_metadata"
                ]
            }
        }

    def parse_result(self, hit: Dict[str, Any], bucket_name: str) -> Optional[SearchResult]:
        """Parse a package result with matched entries.

        The hit will be a MANIFEST document (because of collapse),
        but will include inner_hits with matched ENTRY documents.
        """
        source = hit.get("_source", {})

        # Must be a manifest document
        ptr_name = source.get("ptr_name", "")
        if not ptr_name:
            logger.error(
                f"Package scope got non-manifest document. "
                f"ID: {hit.get('_id')}, fields: {list(source.keys())}"
            )
            return None

        # Extract manifest fields
        mnfst_name = source.get("mnfst_name", "")
        ptr_tag = source.get("ptr_tag", "")
        last_modified = source.get("ptr_last_modified", "")

        # Extract matched entries from inner_hits
        inner_hits = hit.get("inner_hits", {}).get("matched_entries", {})
        matched_entries_hits = inner_hits.get("hits", {}).get("hits", [])
        matched_entry_count = inner_hits.get("hits", {}).get("total", {})

        # Parse total count (can be int or dict)
        if isinstance(matched_entry_count, dict):
            matched_entry_count = matched_entry_count.get("value", 0)

        # Parse matched entries
        matched_entries = []
        for entry_hit in matched_entries_hits:
            entry_source = entry_hit.get("_source", {})
            if entry_source.get("entry_pk") or entry_source.get("entry_lk"):
                matched_entries.append({
                    "entry_lk": entry_source.get("entry_lk", ""),
                    "entry_pk": entry_source.get("entry_pk", ""),
                    "entry_size": entry_source.get("entry_size", 0),
                    "entry_hash": entry_source.get("entry_hash", {}),
                    "entry_metadata": entry_source.get("entry_metadata", {})
                })

        # Build package name for display
        package_name = ptr_name.split("/")[-1] if "/" in ptr_name else ptr_name

        # Build description
        description_parts = [f"Package: {ptr_name}"]
        if ptr_tag:
            description_parts.append(f"(tag: {ptr_tag})")
        if matched_entry_count > 0:
            description_parts.append(f"- Contains {matched_entry_count} matched file(s)")
        description = " ".join(description_parts)

        # Build S3 URI to manifest
        s3_uri = None
        if bucket_name and mnfst_name:
            s3_uri = f"s3://{bucket_name}/.quilt/packages/{mnfst_name}"

        return SearchResult(
            id=hit.get("_id", ""),
            type="package",
            name=ptr_name,
            title=package_name,
            description=description,
            s3_uri=s3_uri,
            size=0,  # Manifests don't have size
            last_modified=last_modified,
            metadata={
                **source,
                "_index": hit.get("_index", ""),
                "matched_entries": matched_entries,
                "matched_entry_count": matched_entry_count,
                "showing_entries": len(matched_entries),
            },
            score=hit.get("_score", 0.0),
            backend="elasticsearch",
            bucket=bucket_name,
            content_type="application/json",
            extension="",
        )

    def get_expected_result_type(self) -> str:
        return "package"
```

#### 2. Backend Integration

**Location:** `src/quilt_mcp/search/backends/elasticsearch.py`

**Changes needed:**

1. Register the new handler:
```python
self.scope_handlers = {
    "file": FileScopeHandler(),
    "packageEntry": PackageEntryScopeHandler(),
    "package": PackageScopeHandler(),  # ← NEW
    "global": GlobalScopeHandler(),
}
```

2. Add collapse support to search method:
```python
def search(self, query: str, scope: str = "global", ...) -> BackendResponse:
    # ... existing code ...

    # Build base query
    dsl_query = {
        "from": 0,
        "size": limit,
        "query": {"query_string": {"query": escaped_query}},
    }

    # Get scope handler
    handler = self.scope_handlers.get(scope)
    if not handler:
        return BackendResponse(...)

    # NEW: Add query filter if handler provides it
    if hasattr(handler, 'build_query_filter'):
        dsl_query["query"] = handler.build_query_filter(escaped_query)

    # NEW: Add collapse config if handler provides it
    if hasattr(handler, 'build_collapse_config'):
        collapse_config = handler.build_collapse_config()
        if collapse_config:
            dsl_query["collapse"] = collapse_config

    # Execute search...
```

---

## Test Specifications

### Unit Tests

**Location:** `tests/unit/search/test_scope_handlers.py`

```python
class TestPackageScopeHandler:
    """Test the intelligent package scope handler."""

    def test_build_index_pattern(self):
        """Should build pattern for package indices."""
        handler = PackageScopeHandler()
        pattern = handler.build_index_pattern(["bucket1", "bucket2"])
        assert pattern == "bucket1_packages,bucket2_packages"

    def test_build_query_filter(self):
        """Should build query that searches both manifests and entries."""
        handler = PackageScopeHandler()
        query_filter = handler.build_query_filter("CCLE AND csv")

        # Should be a bool query
        assert "bool" in query_filter
        assert "must" in query_filter["bool"]
        assert "should" in query_filter["bool"]

        # Should have base query in must
        assert query_filter["bool"]["must"][0]["query_string"]["query"] == "CCLE AND csv"

        # Should boost manifest matches
        should_clauses = query_filter["bool"]["should"]
        assert len(should_clauses) == 2
        assert any("ptr_name" in str(clause) for clause in should_clauses)
        assert any("entry_pk" in str(clause) for clause in should_clauses)

    def test_build_collapse_config(self):
        """Should build collapse config to group by package."""
        handler = PackageScopeHandler()
        collapse = handler.build_collapse_config()

        assert collapse["field"] == "ptr_name.keyword"
        assert "inner_hits" in collapse
        assert collapse["inner_hits"]["name"] == "matched_entries"
        assert collapse["inner_hits"]["size"] == 100

    def test_parse_manifest_with_entries(self):
        """Should parse manifest document with matched entries."""
        handler = PackageScopeHandler()

        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_score": 2.5,
            "_source": {
                "ptr_name": "CCLE/2024-01-15",
                "ptr_tag": "latest",
                "mnfst_name": "abc123",
                "ptr_last_modified": "2024-01-15T10:00:00Z"
            },
            "inner_hits": {
                "matched_entries": {
                    "hits": {
                        "total": {"value": 2},
                        "hits": [
                            {
                                "_source": {
                                    "entry_lk": "data.csv",
                                    "entry_pk": "s3://bucket/data.csv",
                                    "entry_size": 1234,
                                    "entry_hash": {"type": "SHA256", "value": "abc"}
                                }
                            },
                            {
                                "_source": {
                                    "entry_lk": "meta.csv",
                                    "entry_pk": "s3://bucket/meta.csv",
                                    "entry_size": 567,
                                    "entry_hash": {"type": "SHA256", "value": "def"}
                                }
                            }
                        ]
                    }
                }
            }
        }

        result = handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.type == "package"
        assert result.name == "CCLE/2024-01-15"
        assert result.title == "2024-01-15"
        assert "Contains 2 matched file(s)" in result.description
        assert result.s3_uri == "s3://test-bucket/.quilt/packages/abc123"

        # Check matched entries in metadata
        assert result.metadata["matched_entry_count"] == 2
        assert result.metadata["showing_entries"] == 2
        assert len(result.metadata["matched_entries"]) == 2
        assert result.metadata["matched_entries"][0]["entry_lk"] == "data.csv"
        assert result.metadata["matched_entries"][1]["entry_lk"] == "meta.csv"

    def test_parse_manifest_without_entries(self):
        """Should parse manifest with no matched entries."""
        handler = PackageScopeHandler()

        hit = {
            "_id": "manifest123",
            "_source": {
                "ptr_name": "EmptyPackage/v1",
                "ptr_tag": "latest",
                "mnfst_name": "xyz789"
            },
            "inner_hits": {
                "matched_entries": {
                    "hits": {
                        "total": {"value": 0},
                        "hits": []
                    }
                }
            }
        }

        result = handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.type == "package"
        assert result.metadata["matched_entry_count"] == 0
        assert result.metadata["matched_entries"] == []

    def test_parse_rejects_non_manifest(self):
        """Should reject documents without ptr_name."""
        handler = PackageScopeHandler()

        hit = {
            "_id": "entry123",
            "_source": {
                "entry_pk": "s3://bucket/file.csv",
                "entry_lk": "file.csv"
            }
        }

        result = handler.parse_result(hit, "test-bucket")
        assert result is None

    def test_get_expected_result_type(self):
        """Should return 'package' as expected type."""
        handler = PackageScopeHandler()
        assert handler.get_expected_result_type() == "package"
```

### Integration Tests

**Location:** `tests/integration/test_elasticsearch_package_scope.py`

```python
import pytest
from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend
from quilt_mcp.search.backends.status import ResponseStatus


class TestPackageScopeIntegration:
    """Integration tests for intelligent package scope.

    These tests run against REAL Elasticsearch indices.
    """

    @pytest.fixture
    def backend(self):
        """Create backend instance."""
        return Quilt3ElasticsearchBackend()

    @pytest.fixture
    def default_bucket(self):
        """Default bucket for testing."""
        return "ai2-s2-cord19"

    async def test_package_scope_basic_search(self, backend, default_bucket):
        """Should search packages and return package-centric results."""
        response = await backend.search(
            query="CORD",
            scope="package",
            bucket=default_bucket,
            limit=5
        )

        assert response.status.value == "available"
        assert len(response.results) > 0

        # All results should be packages
        for result in response.results:
            assert result.type == "package"
            assert result.metadata.get("ptr_name")
            assert "matched_entry_count" in result.metadata

    async def test_package_scope_with_file_filter(self, backend, default_bucket):
        """Should find packages containing specific file types."""
        response = await backend.search(
            query="csv",
            scope="package",
            bucket=default_bucket,
            limit=5
        )

        assert response.status.value == "available"

        # Results should include matched entries
        for result in response.results:
            assert result.type == "package"
            matched_entries = result.metadata.get("matched_entries", [])
            # At least some results should have CSV files
            if matched_entries:
                csv_entries = [
                    e for e in matched_entries
                    if e.get("entry_lk", "").endswith(".csv")
                ]
                # If we have entries, at least one should be CSV
                # (or query matched the package name)

    async def test_package_scope_groups_by_package(self, backend, default_bucket):
        """Should return one result per package, not per file."""
        # Search for something that matches multiple files
        response = await backend.search(
            query="data",
            scope="package",
            bucket=default_bucket,
            limit=5
        )

        assert response.status.value == "available"

        # Should get packages, not individual files
        package_names = [r.name for r in response.results]
        # No duplicate package names
        assert len(package_names) == len(set(package_names))

        # Each package should potentially have multiple matched entries
        for result in response.results:
            if result.metadata["matched_entry_count"] > 1:
                # Found a package with multiple matches - good!
                assert len(result.metadata["matched_entries"]) > 1
                return

    async def test_package_scope_vs_packageEntry_scope(self, backend, default_bucket):
        """Package scope should return fewer, grouped results vs packageEntry."""
        query = "csv"

        # Get package results (grouped)
        package_response = await backend.search(
            query=query,
            scope="package",
            bucket=default_bucket,
            limit=10
        )

        # Get entry results (individual files)
        entry_response = await backend.search(
            query=query,
            scope="packageEntry",
            bucket=default_bucket,
            limit=10
        )

        # Both should succeed
        assert package_response.status.value == "available"
        assert entry_response.status.value == "available"

        # Package results are packages
        for result in package_response.results:
            assert result.type == "package"
            assert result.metadata.get("ptr_name")

        # Entry results are files
        for result in entry_response.results:
            assert result.type == "packageEntry"
            assert result.metadata.get("entry_pk") or result.metadata.get("entry_lk")

    async def test_package_scope_matched_entries_structure(self, backend, default_bucket):
        """Should include properly structured matched entry information."""
        response = await backend.search(
            query="*",
            scope="package",
            bucket=default_bucket,
            limit=3
        )

        assert response.status.value == "available"
        assert len(response.results) > 0

        # Check structure of matched entries
        for result in response.results:
            metadata = result.metadata

            # Should have entry count fields
            assert "matched_entry_count" in metadata
            assert "showing_entries" in metadata
            assert isinstance(metadata["matched_entry_count"], int)
            assert isinstance(metadata["showing_entries"], int)

            # If we have entries, check their structure
            if metadata["matched_entries"]:
                for entry in metadata["matched_entries"]:
                    # Each entry should have these fields
                    assert "entry_lk" in entry  # Logical key (path)
                    # May or may not have these, but structure should be consistent
                    assert isinstance(entry, dict)

    async def test_package_scope_empty_results(self, backend, default_bucket):
        """Should handle queries with no results gracefully."""
        response = await backend.search(
            query="xyznonexistentquery12345",
            scope="package",
            bucket=default_bucket,
            limit=10
        )

        # Should succeed but return no results
        assert response.status.value in ["available", "not_found"]
        assert len(response.results) == 0

    async def test_package_scope_complex_query(self, backend, default_bucket):
        """Should handle complex boolean queries."""
        response = await backend.search(
            query="(csv OR json) AND data",
            scope="package",
            bucket=default_bucket,
            limit=5
        )

        # Should execute without error
        assert response.status.value in ["available", "not_found"]

        # If we get results, verify they're packages
        for result in response.results:
            assert result.type == "package"
```

### Test Coverage Requirements

- **Unit tests**: 100% coverage of PackageScopeHandler
- **Integration tests**: All major user scenarios covered
- **Existing tests**: Must continue to pass (no regressions)

---

## Implementation Checklist

### Phase 1: Core Handler Implementation
- [ ] Create `PackageScopeHandler` class in `scope_handlers.py`
- [ ] Implement `build_index_pattern()`
- [ ] Implement `build_query_filter()`
- [ ] Implement `build_collapse_config()`
- [ ] Implement `parse_result()`
- [ ] Implement `get_expected_result_type()`

### Phase 2: Backend Integration
- [ ] Register handler in `elasticsearch.py`
- [ ] Add collapse support to `search()` method
- [ ] Add query filter support to `search()` method
- [ ] Update error handling for new scope

### Phase 3: Unit Tests
- [ ] Test `build_index_pattern()`
- [ ] Test `build_query_filter()`
- [ ] Test `build_collapse_config()`
- [ ] Test `parse_result()` with entries
- [ ] Test `parse_result()` without entries
- [ ] Test `parse_result()` rejection cases
- [ ] Test `get_expected_result_type()`

### Phase 4: Integration Tests
- [ ] Test basic package search
- [ ] Test package search with file filters
- [ ] Test grouping behavior
- [ ] Test vs packageEntry scope comparison
- [ ] Test matched entries structure
- [ ] Test empty results
- [ ] Test complex queries

### Phase 5: Documentation & PR
- [ ] Update README with package scope examples
- [ ] Add docstrings to all new methods
- [ ] Update integration test documentation
- [ ] Create PR with comprehensive description
- [ ] Ensure all CI checks pass

---

## Success Criteria

1. **Functional Requirements**
   - ✅ Package scope returns package-centric results
   - ✅ Results grouped by package name (no duplicates)
   - ✅ Matched entries included in metadata
   - ✅ Works with all query types (simple, boolean, wildcards)

2. **Test Coverage**
   - ✅ 100% unit test coverage for new handler
   - ✅ Integration tests cover all major scenarios
   - ✅ All existing tests continue to pass

3. **Code Quality**
   - ✅ Type hints on all methods
   - ✅ Comprehensive docstrings
   - ✅ Follows existing patterns and conventions
   - ✅ No regressions in other scopes

4. **Documentation**
   - ✅ Clear examples in code comments
   - ✅ Integration test demonstrates usage
   - ✅ README updated with package scope info

---

## Future Enhancements

### Phase 2 (Not in this PR)
- Add `packageManifestOnly` scope for pure manifest searches
- Support aggregation queries (count packages by tag, etc.)
- Add pagination for matched entries (>100 per package)
- Support sorting packages by matched entry count

### Phase 3 (Not in this PR)
- Add faceting support (filter by file type, size, etc.)
- Support nested queries within packages
- Add package version comparison
- Support package dependency searches
