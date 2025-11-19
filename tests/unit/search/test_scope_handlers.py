"""Unit tests for scope handlers - Strategy Pattern.

These tests verify the scope handler implementations:
- FileScopeHandler: Searches file/object indices
- PackageEntryScopeHandler: Searches package entry indices
- PackageScopeHandler: Intelligent package search with entry aggregation
- GlobalScopeHandler: Searches both file and package indices
"""

from __future__ import annotations

import pytest

from quilt_mcp.search.backends.scope_handlers import (
    FileScopeHandler,
    PackageEntryScopeHandler,
    PackageScopeHandler,
    GlobalScopeHandler,
)


class TestFileScopeHandler:
    """Test file scope handler."""

    def setup_method(self):
        """Setup handler for each test."""
        self.handler = FileScopeHandler()

    def test_build_index_pattern(self):
        """Should build pattern for file indices only."""
        pattern = self.handler.build_index_pattern(["bucket1", "bucket2"])
        assert pattern == "bucket1,bucket2"

    def test_build_index_pattern_single_bucket(self):
        """Should handle single bucket."""
        pattern = self.handler.build_index_pattern(["mybucket"])
        assert pattern == "mybucket"

    def test_build_index_pattern_empty_raises(self):
        """Should raise ValueError for empty bucket list."""
        with pytest.raises(ValueError, match="bucket list is empty"):
            self.handler.build_index_pattern([])

    def test_parse_file_result(self):
        """Should parse file result from Elasticsearch hit."""
        hit = {
            "_id": "file123",
            "_index": "test-bucket",
            "_score": 1.5,
            "_source": {
                "key": "data/experiment.csv",
                "size": 12345,
                "last_modified": "2024-01-15T10:00:00Z",
                "content_type": "text/csv",
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.type == "file"
        assert result.name == "data/experiment.csv"
        assert result.title == "experiment.csv"
        assert result.s3_uri == "s3://test-bucket/data/experiment.csv"
        assert result.size == 12345
        assert result.content_type == "text/csv"
        assert result.extension == "csv"
        assert result.bucket == "test-bucket"
        assert result.score == 1.5

    def test_get_expected_result_type(self):
        """Should return 'file' as expected type."""
        assert self.handler.get_expected_result_type() == "file"


class TestPackageEntryScopeHandler:
    """Test package entry scope handler."""

    def setup_method(self):
        """Setup handler for each test."""
        self.handler = PackageEntryScopeHandler()

    def test_build_index_pattern(self):
        """Should build pattern for package indices only."""
        pattern = self.handler.build_index_pattern(["bucket1", "bucket2"])
        assert pattern == "bucket1_packages,bucket2_packages"

    def test_build_index_pattern_single_bucket(self):
        """Should handle single bucket."""
        pattern = self.handler.build_index_pattern(["mybucket"])
        assert pattern == "mybucket_packages"

    def test_build_index_pattern_empty_raises(self):
        """Should raise ValueError for empty bucket list."""
        with pytest.raises(ValueError, match="bucket list is empty"):
            self.handler.build_index_pattern([])

    def test_parse_entry_result(self):
        """Should parse package entry result from Elasticsearch hit."""
        hit = {
            "_id": "entry123",
            "_index": "test-bucket_packages",
            "_score": 2.5,
            "_source": {
                "entry_pk": "CCLE/2024-01-15@abc123",
                "entry_lk": "data/expression.csv",
                "entry_size": 5000000,
                "entry_hash": {"type": "SHA256", "value": "abc123"},
                "entry_metadata": {"last_modified": "2024-01-15T10:00:00Z"},
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.type == "packageEntry"
        assert result.name == "data/expression.csv"
        assert result.title == "expression.csv"
        assert result.description == "Package entry: CCLE/2024-01-15"
        assert result.s3_uri == "s3://test-bucket/data/expression.csv"
        assert result.size == 5000000
        assert result.extension == "csv"
        assert result.metadata["package_name"] == "CCLE/2024-01-15"

    def test_parse_rejects_manifest_documents(self):
        """Should reject manifest documents (ptr_name present)."""
        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_source": {
                "ptr_name": "CCLE/2024-01-15",
                "mnfst_name": "abc123",
                "ptr_tag": "latest",
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")
        assert result is None

    def test_get_expected_result_type(self):
        """Should return 'packageEntry' as expected type."""
        assert self.handler.get_expected_result_type() == "packageEntry"


class TestPackageScopeHandler:
    """Test the simplified package scope handler.

    This handler searches ONLY manifest documents and returns simple package
    information without entry aggregation. This avoids the need for
    ptr_name.keyword field mapping in Elasticsearch.
    """

    def setup_method(self):
        """Setup handler for each test."""
        self.handler = PackageScopeHandler()

    def test_build_index_pattern(self):
        """Should build pattern for package indices."""
        pattern = self.handler.build_index_pattern(["bucket1", "bucket2"])
        assert pattern == "bucket1_packages,bucket2_packages"

    def test_build_index_pattern_single_bucket(self):
        """Should handle single bucket."""
        pattern = self.handler.build_index_pattern(["mybucket"])
        assert pattern == "mybucket_packages"

    def test_build_index_pattern_empty_raises(self):
        """Should raise ValueError for empty bucket list."""
        with pytest.raises(ValueError, match="bucket list is empty"):
            self.handler.build_index_pattern([])

    def test_build_query_filter(self):
        """Should build query that searches only manifest documents."""
        query_filter = self.handler.build_query_filter("CCLE AND csv")

        # Should be a bool query
        assert "bool" in query_filter
        assert "must" in query_filter["bool"]

        # Should have two must clauses: exists check and query
        must_clauses = query_filter["bool"]["must"]
        assert len(must_clauses) == 2

        # First must clause: check for ptr_name field (manifest documents only)
        assert must_clauses[0] == {"exists": {"field": "ptr_name"}}

        # Second must clause: simple query string without field specification
        # (searches all fields by default)
        query_clause = must_clauses[1]
        assert "query_string" in query_clause
        assert query_clause["query_string"]["query"] == "CCLE AND csv"
        # Simplified version doesn't specify fields (searches all by default)
        assert "fields" not in query_clause["query_string"]

    def test_build_query_filter_preserves_wildcards(self):
        """Should preserve wildcard syntax in query."""
        query_filter = self.handler.build_query_filter("CCLE* AND *.csv")

        # Verify wildcards are preserved in query string
        query_clause = query_filter["bool"]["must"][1]  # Second must clause is the query
        base_query = query_clause["query_string"]["query"]
        assert "CCLE*" in base_query
        assert "*.csv" in base_query

    def test_build_query_filter_handles_boolean_operators(self):
        """Should handle complex boolean queries."""
        query_filter = self.handler.build_query_filter("(csv OR json) AND data NOT test")

        # Query should be in the second must clause
        query_clause = query_filter["bool"]["must"][1]
        base_query = query_clause["query_string"]["query"]
        assert "(csv OR json) AND data NOT test" == base_query

    def test_build_collapse_config(self):
        """Should return None (no collapse needed for manifest-only search)."""
        collapse = self.handler.build_collapse_config()

        # Simplified version doesn't use collapse since we only search manifests
        # (which are naturally unique per package)
        assert collapse is None

    def test_parse_manifest_basic(self):
        """Should parse manifest document (simplified version without inner_hits)."""
        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_score": 2.5,
            "_source": {
                "ptr_name": "CCLE/2024-01-15",
                "ptr_tag": "latest",
                "mnfst_name": "abc123",
                "ptr_last_modified": "2024-01-15T10:00:00Z",
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        # Verify basic package info
        assert result is not None
        assert result.type == "package"
        assert result.name == "CCLE/2024-01-15"
        assert result.title == "2024-01-15"
        assert "Package: CCLE/2024-01-15" in result.description
        assert "(tag: latest)" in result.description
        assert result.s3_uri == "s3://test-bucket/CCLE/2024-01-15"
        assert result.size == 0  # Manifests don't have size
        assert result.last_modified == "2024-01-15T10:00:00Z"

        # Verify metadata includes source fields
        metadata = result.metadata
        assert metadata["ptr_name"] == "CCLE/2024-01-15"
        assert metadata["ptr_tag"] == "latest"
        assert metadata["mnfst_name"] == "abc123"
        # Simplified version doesn't include matched_entry_count or matched_entries

    def test_parse_manifest_without_tag(self):
        """Should parse manifest without tag field."""
        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_score": 1.0,
            "_source": {
                "ptr_name": "EmptyPackage/v1",
                "mnfst_name": "xyz789",
                "ptr_last_modified": "2024-01-10T10:00:00Z",
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.type == "package"
        assert result.name == "EmptyPackage/v1"
        # Description should not mention tag when it's not present
        assert "(tag:" not in result.description
        assert "Package: EmptyPackage/v1" in result.description

    def test_parse_rejects_non_manifest(self):
        """Should reject documents without ptr_name."""
        hit = {
            "_id": "entry123",
            "_index": "test-bucket_packages",
            "_source": {
                "entry_pk": "s3://bucket/file.csv",
                "entry_lk": "file.csv",
                "entry_size": 1000,
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")
        assert result is None

    def test_parse_manifest_extracts_package_name_correctly(self):
        """Should extract package name correctly from ptr_name."""
        test_cases = [
            ("simple", "simple"),
            ("namespace/package", "package"),
            ("org/namespace/package", "package"),
            ("deeply/nested/path/to/package", "package"),
        ]

        for ptr_name, expected_title in test_cases:
            hit = {
                "_id": "manifest123",
                "_index": "test-bucket_packages",
                "_score": 1.0,
                "_source": {
                    "ptr_name": ptr_name,
                    "mnfst_name": "abc123",
                },
            }

            result = self.handler.parse_result(hit, "test-bucket")
            assert result is not None
            assert result.title == expected_title, f"Failed for ptr_name: {ptr_name}"

    def test_parse_manifest_constructs_s3_uri_correctly(self):
        """Should construct S3 URI using ptr_name format (simplified version)."""
        hit = {
            "_id": "manifest123",
            "_index": "my-bucket_packages",
            "_score": 1.0,
            "_source": {
                "ptr_name": "MyPackage/v1",
                "mnfst_name": "manifest_hash_123",
            },
        }

        result = self.handler.parse_result(hit, "my-bucket")

        assert result is not None
        # Simplified version uses ptr_name format, not manifest hash format
        assert result.s3_uri == "s3://my-bucket/MyPackage/v1"

    def test_parse_manifest_without_mnfst_name(self):
        """Should handle manifest without mnfst_name gracefully."""
        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_score": 1.0,
            "_source": {
                "ptr_name": "TestPackage/v1",
                # No mnfst_name field
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.type == "package"
        assert result.name == "TestPackage/v1"
        # Simplified version still constructs URI using ptr_name
        assert result.s3_uri == "s3://test-bucket/TestPackage/v1"

    def test_parse_manifest_includes_metadata(self):
        """Should include all source fields in metadata."""
        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_score": 1.0,
            "_source": {
                "ptr_name": "TestPackage/v1",
                "ptr_tag": "latest",
                "mnfst_name": "abc123",
                "ptr_last_modified": "2024-01-15T10:00:00Z",
                "custom_field": "custom_value",
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        # Should include all original source fields
        assert result.metadata["ptr_name"] == "TestPackage/v1"
        assert result.metadata["ptr_tag"] == "latest"
        assert result.metadata["mnfst_name"] == "abc123"
        assert result.metadata["custom_field"] == "custom_value"
        # Should include index name
        assert result.metadata["_index"] == "test-bucket_packages"

    def test_get_expected_result_type(self):
        """Should return 'package' as expected type."""
        assert self.handler.get_expected_result_type() == "package"


class TestGlobalScopeHandler:
    """Test global scope handler."""

    def setup_method(self):
        """Setup handler for each test."""
        self.handler = GlobalScopeHandler()

    def test_build_index_pattern(self):
        """Should build pattern for both file and package indices."""
        pattern = self.handler.build_index_pattern(["bucket1", "bucket2"])
        assert pattern == "bucket1,bucket2,bucket1_packages,bucket2_packages"

    def test_build_index_pattern_single_bucket(self):
        """Should handle single bucket."""
        pattern = self.handler.build_index_pattern(["mybucket"])
        assert pattern == "mybucket,mybucket_packages"

    def test_build_index_pattern_empty_raises(self):
        """Should raise ValueError for empty bucket list."""
        with pytest.raises(ValueError, match="bucket list is empty"):
            self.handler.build_index_pattern([])

    def test_parse_file_result(self):
        """Should parse file result (no _packages suffix)."""
        hit = {
            "_id": "file123",
            "_index": "test-bucket",
            "_score": 1.5,
            "_source": {
                "key": "data/file.csv",
                "size": 1000,
                "last_modified": "2024-01-15T10:00:00Z",
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.type == "file"
        assert result.name == "data/file.csv"

    def test_parse_package_result(self):
        """Should parse package entry result (_packages suffix)."""
        hit = {
            "_id": "entry123",
            "_index": "test-bucket_packages",
            "_score": 2.5,
            "_source": {
                "entry_pk": "Package/v1@abc123",
                "entry_lk": "data/file.csv",
                "entry_size": 2000,
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.type == "packageEntry"
        assert result.name == "data/file.csv"

    def test_get_expected_result_type(self):
        """Should return 'mixed' as expected type."""
        assert self.handler.get_expected_result_type() == "mixed"
