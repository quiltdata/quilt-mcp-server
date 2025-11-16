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
    """Test the intelligent package scope handler.

    This handler searches both manifests and entries but returns package-centric
    results with matched entry information aggregated.
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
        """Should build query that searches both manifests and entries."""
        query_filter = self.handler.build_query_filter("CCLE AND csv")

        # Should be a bool query
        assert "bool" in query_filter
        assert "must" in query_filter["bool"]
        assert "should" in query_filter["bool"]
        assert "minimum_should_match" in query_filter["bool"]

        # Should have base query in must
        must_clauses = query_filter["bool"]["must"]
        assert len(must_clauses) == 1
        assert must_clauses[0]["query_string"]["query"] == "CCLE AND csv"

        # Should have manifest and entry boosting in should clauses
        should_clauses = query_filter["bool"]["should"]
        assert len(should_clauses) == 2

        # Check manifest boost clause
        manifest_clause = should_clauses[0]
        assert "bool" in manifest_clause
        # Boost is inside the bool clause
        assert "boost" in manifest_clause["bool"]
        assert manifest_clause["bool"]["boost"] == 2.0
        # Verify it checks for ptr_name field
        manifest_must = manifest_clause["bool"]["must"]
        assert any(
            "ptr_name" in str(clause) for clause in manifest_must
        ), "Should check for ptr_name field"

        # Check entry clause
        entry_clause = should_clauses[1]
        assert "bool" in entry_clause
        entry_must = entry_clause["bool"]["must"]
        assert any(
            "entry_pk" in str(clause) for clause in entry_must
        ), "Should check for entry_pk field"

        # Should require at least one should clause to match
        assert query_filter["bool"]["minimum_should_match"] == 1

    def test_build_query_filter_preserves_wildcards(self):
        """Should preserve wildcard syntax in query."""
        query_filter = self.handler.build_query_filter("CCLE* AND *.csv")

        # Verify wildcards are preserved in base query
        base_query = query_filter["bool"]["must"][0]["query_string"]["query"]
        assert "CCLE*" in base_query
        assert "*.csv" in base_query

        # Verify wildcards are preserved in field queries
        should_clauses = query_filter["bool"]["should"]
        manifest_query = should_clauses[0]["bool"]["must"][1]["query_string"]["query"]
        entry_query = should_clauses[1]["bool"]["must"][1]["query_string"]["query"]
        assert "CCLE*" in manifest_query or "CCLE*" in entry_query
        assert "*.csv" in manifest_query or "*.csv" in entry_query

    def test_build_query_filter_handles_boolean_operators(self):
        """Should handle complex boolean queries."""
        query_filter = self.handler.build_query_filter("(csv OR json) AND data NOT test")

        base_query = query_filter["bool"]["must"][0]["query_string"]["query"]
        assert "(csv OR json) AND data NOT test" == base_query

    def test_build_collapse_config(self):
        """Should build collapse config to group by package."""
        collapse = self.handler.build_collapse_config()

        # Should collapse on ptr_name.keyword
        assert collapse["field"] == "ptr_name.keyword"

        # Should include inner_hits configuration
        assert "inner_hits" in collapse
        inner_hits = collapse["inner_hits"]
        assert inner_hits["name"] == "matched_entries"
        assert inner_hits["size"] == 100

        # Should request entry fields in inner_hits
        source_fields = inner_hits["_source"]
        assert "entry_lk" in source_fields
        assert "entry_pk" in source_fields
        assert "entry_size" in source_fields
        assert "entry_hash" in source_fields
        assert "entry_metadata" in source_fields

    def test_parse_manifest_with_entries(self):
        """Should parse manifest document with matched entries."""
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
            "inner_hits": {
                "matched_entries": {
                    "hits": {
                        "total": {"value": 2},
                        "hits": [
                            {
                                "_source": {
                                    "entry_lk": "data/expression.csv",
                                    "entry_pk": "s3://bucket/data/expression.csv",
                                    "entry_size": 1234,
                                    "entry_hash": {"type": "SHA256", "value": "abc"},
                                    "entry_metadata": {"format": "csv"},
                                }
                            },
                            {
                                "_source": {
                                    "entry_lk": "metadata/samples.csv",
                                    "entry_pk": "s3://bucket/metadata/samples.csv",
                                    "entry_size": 567,
                                    "entry_hash": {"type": "SHA256", "value": "def"},
                                    "entry_metadata": {"format": "csv"},
                                }
                            },
                        ],
                    }
                }
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
        assert "Contains 2 matched file(s)" in result.description
        assert result.s3_uri == "s3://test-bucket/.quilt/packages/abc123"
        assert result.size == 0  # Manifests don't have size
        assert result.last_modified == "2024-01-15T10:00:00Z"

        # Verify matched entries in metadata
        metadata = result.metadata
        assert metadata["matched_entry_count"] == 2
        assert metadata["showing_entries"] == 2
        assert len(metadata["matched_entries"]) == 2

        # Verify first entry
        entry1 = metadata["matched_entries"][0]
        assert entry1["entry_lk"] == "data/expression.csv"
        assert entry1["entry_pk"] == "s3://bucket/data/expression.csv"
        assert entry1["entry_size"] == 1234
        assert entry1["entry_hash"] == {"type": "SHA256", "value": "abc"}
        assert entry1["entry_metadata"] == {"format": "csv"}

        # Verify second entry
        entry2 = metadata["matched_entries"][1]
        assert entry2["entry_lk"] == "metadata/samples.csv"
        assert entry2["entry_pk"] == "s3://bucket/metadata/samples.csv"
        assert entry2["entry_size"] == 567

    def test_parse_manifest_without_entries(self):
        """Should parse manifest with no matched entries."""
        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_score": 1.0,
            "_source": {
                "ptr_name": "EmptyPackage/v1",
                "ptr_tag": "latest",
                "mnfst_name": "xyz789",
                "ptr_last_modified": "2024-01-10T10:00:00Z",
            },
            "inner_hits": {
                "matched_entries": {"hits": {"total": {"value": 0}, "hits": []}}
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.type == "package"
        assert result.name == "EmptyPackage/v1"
        assert result.metadata["matched_entry_count"] == 0
        assert result.metadata["showing_entries"] == 0
        assert result.metadata["matched_entries"] == []
        # Description should not mention matched files when count is 0
        assert "Contains 0 matched file(s)" not in result.description

    def test_parse_manifest_with_entries_total_as_int(self):
        """Should handle total count as integer (older ES versions)."""
        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_score": 2.5,
            "_source": {
                "ptr_name": "TestPackage/v1",
                "mnfst_name": "abc123",
            },
            "inner_hits": {
                "matched_entries": {
                    "hits": {
                        "total": 3,  # Integer instead of dict
                        "hits": [
                            {
                                "_source": {
                                    "entry_lk": "file1.csv",
                                    "entry_pk": "s3://bucket/file1.csv",
                                    "entry_size": 100,
                                    "entry_hash": {},
                                    "entry_metadata": {},
                                }
                            }
                        ],
                    }
                }
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.metadata["matched_entry_count"] == 3
        assert result.metadata["showing_entries"] == 1
        assert "Contains 3 matched file(s)" in result.description

    def test_parse_manifest_with_partial_entries(self):
        """Should handle entries with missing optional fields."""
        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_score": 1.5,
            "_source": {
                "ptr_name": "PartialPackage/v1",
                "mnfst_name": "abc123",
            },
            "inner_hits": {
                "matched_entries": {
                    "hits": {
                        "total": {"value": 1},
                        "hits": [
                            {
                                "_source": {
                                    "entry_lk": "data.csv",
                                    "entry_pk": "s3://bucket/data.csv",
                                    # Missing entry_size, entry_hash, entry_metadata
                                }
                            }
                        ],
                    }
                }
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        entry = result.metadata["matched_entries"][0]
        assert entry["entry_lk"] == "data.csv"
        assert entry["entry_pk"] == "s3://bucket/data.csv"
        assert entry["entry_size"] == 0  # Default value
        assert entry["entry_hash"] == {}  # Default value
        assert entry["entry_metadata"] == {}  # Default value

    def test_parse_manifest_filters_invalid_entries(self):
        """Should filter out entries without entry_pk or entry_lk."""
        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_score": 1.5,
            "_source": {
                "ptr_name": "TestPackage/v1",
                "mnfst_name": "abc123",
            },
            "inner_hits": {
                "matched_entries": {
                    "hits": {
                        "total": {"value": 3},
                        "hits": [
                            {
                                "_source": {
                                    "entry_lk": "valid1.csv",
                                    "entry_pk": "s3://bucket/valid1.csv",
                                    "entry_size": 100,
                                    "entry_hash": {},
                                    "entry_metadata": {},
                                }
                            },
                            {
                                "_source": {
                                    # Missing both entry_pk and entry_lk
                                    "some_other_field": "invalid"
                                }
                            },
                            {
                                "_source": {
                                    "entry_lk": "valid2.csv",
                                    "entry_pk": "s3://bucket/valid2.csv",
                                    "entry_size": 200,
                                    "entry_hash": {},
                                    "entry_metadata": {},
                                }
                            },
                        ],
                    }
                }
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        # Total count should be 3 (from ES response)
        assert result.metadata["matched_entry_count"] == 3
        # But showing_entries should be 2 (only valid entries)
        assert result.metadata["showing_entries"] == 2
        assert len(result.metadata["matched_entries"]) == 2
        assert result.metadata["matched_entries"][0]["entry_lk"] == "valid1.csv"
        assert result.metadata["matched_entries"][1]["entry_lk"] == "valid2.csv"

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
                "inner_hits": {
                    "matched_entries": {"hits": {"total": {"value": 0}, "hits": []}}
                },
            }

            result = self.handler.parse_result(hit, "test-bucket")
            assert result is not None
            assert result.title == expected_title, f"Failed for ptr_name: {ptr_name}"

    def test_parse_manifest_with_missing_inner_hits(self):
        """Should handle manifest with no inner_hits gracefully."""
        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_score": 1.0,
            "_source": {
                "ptr_name": "TestPackage/v1",
                "mnfst_name": "abc123",
            },
            # No inner_hits at all
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.type == "package"
        assert result.metadata["matched_entry_count"] == 0
        assert result.metadata["matched_entries"] == []

    def test_parse_manifest_constructs_s3_uri_correctly(self):
        """Should construct correct S3 URI for package manifest."""
        hit = {
            "_id": "manifest123",
            "_index": "my-bucket_packages",
            "_score": 1.0,
            "_source": {
                "ptr_name": "MyPackage/v1",
                "mnfst_name": "manifest_hash_123",
            },
            "inner_hits": {
                "matched_entries": {"hits": {"total": {"value": 0}, "hits": []}}
            },
        }

        result = self.handler.parse_result(hit, "my-bucket")

        assert result is not None
        assert result.s3_uri == "s3://my-bucket/.quilt/packages/manifest_hash_123"

    def test_parse_manifest_without_mnfst_name(self):
        """Should handle manifest without mnfst_name (s3_uri will be None)."""
        hit = {
            "_id": "manifest123",
            "_index": "test-bucket_packages",
            "_score": 1.0,
            "_source": {
                "ptr_name": "TestPackage/v1",
                # No mnfst_name field
            },
            "inner_hits": {
                "matched_entries": {"hits": {"total": {"value": 0}, "hits": []}}
            },
        }

        result = self.handler.parse_result(hit, "test-bucket")

        assert result is not None
        assert result.type == "package"
        assert result.name == "TestPackage/v1"
        assert result.s3_uri is None  # No URI without mnfst_name

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
            "inner_hits": {
                "matched_entries": {"hits": {"total": {"value": 0}, "hits": []}}
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
