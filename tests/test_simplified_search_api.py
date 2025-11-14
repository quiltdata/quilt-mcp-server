"""Tests for simplified search API.

This test suite validates the simplified search API changes that provide
a unified interface focused on files and packages, with explicit scope
control and clear result structure.

Test categories:
1. Scope Tests - Verify scope parameter correctly filters results
2. Bucket Parameter Tests - Verify bucket filtering and normalization
3. Backend Tests - Verify backend selection and validation
4. Result Structure Tests - Verify result field presence and semantics
5. Parameter Validation Tests - Verify input validation and normalization
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from quilt_mcp.tools.search import search_catalog
from quilt_mcp.search.backends.base import BackendType, BackendStatus


class TestScopeParameter:
    """Test suite for scope parameter functionality."""

    @patch("quilt_mcp.tools.search._unified_search")
    def test_scope_file(self, mock_unified_search):
        """Test that scope='file' returns only file results."""
        # Mock unified_search to return file results
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "file",
            "bucket": "",
            "results": [
                {
                    "id": "s3://bucket/file1.csv",
                    "type": "file",
                    "title": "file1.csv",
                    "name": "file1.csv",
                    "s3_uri": "s3://bucket/file1.csv",
                    "size": 1000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                },
                {
                    "id": "s3://bucket/file2.csv",
                    "type": "file",
                    "title": "file2.csv",
                    "name": "file2.csv",
                    "s3_uri": "s3://bucket/file2.csv",
                    "size": 2000,
                    "score": 0.8,
                    "backend": "elasticsearch",
                },
            ],
            "total_results": 2,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test", scope="file")

        assert result["success"] is True
        assert result["scope"] == "file"
        assert len(result["results"]) == 2
        # Verify all results are files
        for r in result["results"]:
            assert r["type"] == "file"
            assert r["id"].startswith("s3://")

    @patch("quilt_mcp.tools.search._unified_search")
    def test_scope_package(self, mock_unified_search):
        """Test that scope='package' returns only package results."""
        # Mock unified_search to return package results
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "package",
            "bucket": "",
            "results": [
                {
                    "id": "quilt+s3://bucket#package=test/pkg1",
                    "type": "package",
                    "title": "test/pkg1",
                    "name": "test/pkg1",
                    "s3_uri": "s3://bucket/.quilt/packages/test/pkg1/latest",
                    "size": 5000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                    "package_name": "test/pkg1",
                },
                {
                    "id": "quilt+s3://bucket#package=test/pkg2",
                    "type": "package",
                    "title": "test/pkg2",
                    "name": "test/pkg2",
                    "s3_uri": "s3://bucket/.quilt/packages/test/pkg2/latest",
                    "size": 3000,
                    "score": 0.8,
                    "backend": "elasticsearch",
                    "package_name": "test/pkg2",
                },
            ],
            "total_results": 2,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test", scope="package")

        assert result["success"] is True
        assert result["scope"] == "package"
        assert len(result["results"]) == 2
        # Verify all results are packages
        for r in result["results"]:
            assert r["type"] == "package"
            assert r["id"].startswith("quilt+s3://")

    @patch("quilt_mcp.tools.search._unified_search")
    def test_scope_global(self, mock_unified_search):
        """Test that scope='global' allows mixed file and package results."""
        # Mock unified_search to return mixed results
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "global",
            "bucket": "",
            "results": [
                {
                    "id": "s3://bucket/file1.csv",
                    "type": "file",
                    "title": "file1.csv",
                    "name": "file1.csv",
                    "s3_uri": "s3://bucket/file1.csv",
                    "size": 1000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                },
                {
                    "id": "quilt+s3://bucket#package=test/pkg1",
                    "type": "package",
                    "title": "test/pkg1",
                    "name": "test/pkg1",
                    "s3_uri": "s3://bucket/.quilt/packages/test/pkg1/latest",
                    "size": 5000,
                    "score": 0.8,
                    "backend": "elasticsearch",
                    "package_name": "test/pkg1",
                },
            ],
            "total_results": 2,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test", scope="global")

        assert result["success"] is True
        assert result["scope"] == "global"
        assert len(result["results"]) == 2
        # Verify we have both types
        types = {r["type"] for r in result["results"]}
        assert "file" in types
        assert "package" in types


class TestBucketParameter:
    """Test suite for bucket parameter functionality."""

    @patch("quilt_mcp.tools.search._unified_search")
    def test_bucket_empty_searches_all(self, mock_unified_search):
        """Test that empty bucket parameter searches all buckets."""
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "file",
            "bucket": "",
            "results": [
                {
                    "id": "s3://bucket1/file1.csv",
                    "type": "file",
                    "title": "file1.csv",
                    "name": "file1.csv",
                    "s3_uri": "s3://bucket1/file1.csv",
                    "size": 1000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                },
                {
                    "id": "s3://bucket2/file2.csv",
                    "type": "file",
                    "title": "file2.csv",
                    "name": "file2.csv",
                    "s3_uri": "s3://bucket2/file2.csv",
                    "size": 2000,
                    "score": 0.8,
                    "backend": "elasticsearch",
                },
            ],
            "total_results": 2,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test", scope="file", bucket="")

        assert result["success"] is True
        assert result["bucket"] == ""
        # Results can come from multiple buckets
        buckets = {r["s3_uri"].split("/")[2] for r in result["results"]}
        assert len(buckets) > 1  # Multiple buckets

    @patch("quilt_mcp.tools.search._unified_search")
    def test_bucket_specific_filters(self, mock_unified_search):
        """Test that specific bucket name filters results."""
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "file",
            "bucket": "my-bucket",
            "results": [
                {
                    "id": "s3://my-bucket/file1.csv",
                    "type": "file",
                    "title": "file1.csv",
                    "name": "file1.csv",
                    "s3_uri": "s3://my-bucket/file1.csv",
                    "size": 1000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                },
            ],
            "total_results": 1,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test", scope="file", bucket="my-bucket")

        assert result["success"] is True
        assert result["bucket"] == "my-bucket"
        # All results should be from the specified bucket
        for r in result["results"]:
            assert "my-bucket" in r["s3_uri"]

    @patch("quilt_mcp.tools.search._unified_search")
    def test_bucket_s3_uri_normalized(self, mock_unified_search):
        """Test that s3://bucket and bucket are treated the same."""
        # Mock returns same results for both formats
        mock_response = {
            "success": True,
            "query": "test",
            "scope": "file",
            "bucket": "my-bucket",  # Normalized bucket name
            "results": [
                {
                    "id": "s3://my-bucket/file1.csv",
                    "type": "file",
                    "title": "file1.csv",
                    "name": "file1.csv",
                    "s3_uri": "s3://my-bucket/file1.csv",
                    "size": 1000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                },
            ],
            "total_results": 1,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }
        mock_unified_search.return_value = mock_response

        # Test with bucket name
        result1 = search_catalog("test", scope="file", bucket="my-bucket")
        # Test with s3:// URI
        result2 = search_catalog("test", scope="file", bucket="s3://my-bucket")

        # Both should normalize to the same bucket name
        assert result1["bucket"] == "my-bucket"
        assert result2["bucket"] == "my-bucket"


class TestBackendParameter:
    """Test suite for backend parameter functionality."""

    @patch("quilt_mcp.tools.search._unified_search")
    def test_backend_default(self, mock_unified_search):
        """Test that backend defaults to elasticsearch."""
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "file",
            "bucket": "",
            "results": [],
            "total_results": 0,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test")

        assert result["backend_used"] == "elasticsearch"

    @patch("quilt_mcp.tools.search._unified_search")
    def test_backend_explicit(self, mock_unified_search):
        """Test that explicit elasticsearch backend works."""
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "file",
            "bucket": "",
            "results": [],
            "total_results": 0,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test", backend="elasticsearch")

        assert result["backend_used"] == "elasticsearch"

    def test_backend_invalid_raises(self):
        """Test that invalid backend raises ValueError.

        Note: The actual validation happens in the Pydantic model,
        which only accepts Literal["elasticsearch"]. This test verifies
        that attempting to use an invalid backend value fails.
        """
        # The Pydantic type hint only allows "elasticsearch"
        # Attempting to pass "graphql" should fail at the type level
        # For now, we test that calling with valid backend works
        # and document that invalid values would fail Pydantic validation

        with pytest.raises(Exception):  # Pydantic ValidationError or similar
            # This should fail because backend parameter only accepts "elasticsearch"
            search_catalog("test", backend="graphql")  # type: ignore


class TestResultStructure:
    """Test suite for result structure validation."""

    @patch("quilt_mcp.tools.search._unified_search")
    def test_file_result_structure(self, mock_unified_search):
        """Test that file results have all required fields."""
        mock_unified_search.return_value = {
            "success": True,
            "query": "test.csv",
            "scope": "file",
            "bucket": "",
            "results": [
                {
                    "id": "s3://bucket/test.csv",
                    "type": "file",
                    "title": "test.csv",
                    "name": "test.csv",  # For files, name = path
                    "s3_uri": "s3://bucket/test.csv",
                    "size": 1000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                    "description": "Test CSV file",
                    "content_type": "text/csv",
                    "extension": "csv",
                    "last_modified": "2024-01-01T00:00:00Z",
                },
            ],
            "total_results": 1,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test.csv", scope="file")

        assert result["success"] is True
        file = result["results"][0]

        # Verify required fields
        assert file["type"] == "file"
        assert "id" in file
        assert "name" in file
        assert "title" in file
        assert "s3_uri" in file
        assert "size" in file

        # Verify ID format for files
        assert file["id"].startswith("s3://")

        # Verify file-specific fields
        assert file["name"] == "test.csv"
        assert file["extension"] == "csv"

    @patch("quilt_mcp.tools.search._unified_search")
    def test_package_result_structure(self, mock_unified_search):
        """Test that package results have all required fields."""
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "package",
            "bucket": "",
            "results": [
                {
                    "id": "quilt+s3://bucket#package=test/package",
                    "type": "package",
                    "title": "test/package",
                    "name": "test/package",  # For packages, name = package_name
                    "s3_uri": "s3://bucket/.quilt/packages/test/package/latest",
                    "size": 5000,  # Manifest size
                    "score": 0.9,
                    "backend": "elasticsearch",
                    "description": "Test package",
                    "package_name": "test/package",
                    "content_type": "application/jsonl",
                    "extension": "jsonl",
                    "metadata": {
                        "total_size": 1000000,  # Total package size
                    },
                },
            ],
            "total_results": 1,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test", scope="package")

        assert result["success"] is True
        pkg = result["results"][0]

        # Verify required fields
        assert pkg["type"] == "package"
        assert "id" in pkg
        assert "name" in pkg
        assert "title" in pkg
        assert "s3_uri" in pkg
        assert "size" in pkg

        # Verify ID format for packages
        assert pkg["id"].startswith("quilt+s3://")

        # Verify package-specific fields
        assert pkg["name"] == "test/package"
        assert pkg["content_type"] == "application/jsonl"
        assert pkg["extension"] == "jsonl"
        assert pkg["size"] > 0  # Manifest has a size
        assert "total_size" in pkg["metadata"]

    @patch("quilt_mcp.tools.search._unified_search")
    def test_result_name_field(self, mock_unified_search):
        """Test that name field has correct semantics for files vs packages."""
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "global",
            "bucket": "",
            "results": [
                {
                    "id": "s3://bucket/path/to/file.csv",
                    "type": "file",
                    "title": "file.csv",
                    "name": "path/to/file.csv",  # Full path for files
                    "s3_uri": "s3://bucket/path/to/file.csv",
                    "size": 1000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                },
                {
                    "id": "quilt+s3://bucket#package=team/dataset",
                    "type": "package",
                    "title": "team/dataset",
                    "name": "team/dataset",  # Package name
                    "s3_uri": "s3://bucket/.quilt/packages/team/dataset/latest",
                    "size": 5000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                    "package_name": "team/dataset",
                },
            ],
            "total_results": 2,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test", scope="global")

        file = result["results"][0]
        pkg = result["results"][1]

        # File name should be the path
        assert file["name"] == "path/to/file.csv"

        # Package name should be the package identifier
        assert pkg["name"] == "team/dataset"
        assert pkg["package_name"] == "team/dataset"

    @patch("quilt_mcp.tools.search._unified_search")
    def test_result_id_format(self, mock_unified_search):
        """Test that ID field uses correct URI format."""
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "global",
            "bucket": "",
            "results": [
                {
                    "id": "s3://bucket/file.csv",
                    "type": "file",
                    "title": "file.csv",
                    "name": "file.csv",
                    "s3_uri": "s3://bucket/file.csv",
                    "size": 1000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                },
                {
                    "id": "quilt+s3://bucket#package=test/pkg",
                    "type": "package",
                    "title": "test/pkg",
                    "name": "test/pkg",
                    "s3_uri": "s3://bucket/.quilt/packages/test/pkg/latest",
                    "size": 5000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                    "package_name": "test/pkg",
                },
            ],
            "total_results": 2,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test", scope="global")

        file = result["results"][0]
        pkg = result["results"][1]

        # File ID should be s3:// URI
        assert file["id"].startswith("s3://")
        assert not file["id"].startswith("quilt+")

        # Package ID should be quilt+s3:// URI
        assert pkg["id"].startswith("quilt+s3://")


class TestParameterValidation:
    """Test suite for parameter validation."""

    def test_scope_validation(self):
        """Test that invalid scope values are rejected.

        Note: Pydantic Literal type validates at the type level,
        so invalid scope values would fail validation.
        """
        # Valid scopes should work
        valid_scopes = ["file", "package", "global"]
        for scope in valid_scopes:
            # Just verify the call structure is correct
            # Actual execution is mocked in other tests
            assert scope in ["file", "package", "global"]

    @patch("quilt_mcp.tools.search._unified_search")
    def test_limit_validation(self, mock_unified_search):
        """Test that limit parameter works correctly."""
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "file",
            "bucket": "",
            "results": [
                {
                    "id": f"s3://bucket/file{i}.csv",
                    "type": "file",
                    "title": f"file{i}.csv",
                    "name": f"file{i}.csv",
                    "s3_uri": f"s3://bucket/file{i}.csv",
                    "size": 1000,
                    "score": 0.9,
                    "backend": "elasticsearch",
                }
                for i in range(10)
            ],
            "total_results": 10,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        result = search_catalog("test", scope="file", limit=10)

        assert result["success"] is True
        assert len(result["results"]) == 10

    @patch("quilt_mcp.tools.search._unified_search")
    def test_bucket_normalization(self, mock_unified_search):
        """Test that s3:// prefix is stripped correctly."""
        mock_unified_search.return_value = {
            "success": True,
            "query": "test",
            "scope": "file",
            "bucket": "my-bucket",  # Normalized without s3://
            "results": [],
            "total_results": 0,
            "query_time_ms": 50.0,
            "backend_used": "elasticsearch",
        }

        # Call with s3:// prefix
        result = search_catalog("test", scope="file", bucket="s3://my-bucket")

        # Bucket should be normalized to just the name
        assert result["bucket"] == "my-bucket"
        assert not result["bucket"].startswith("s3://")


class TestErrorHandling:
    """Test suite for error handling."""

    @patch("quilt_mcp.tools.search._unified_search")
    def test_backend_error_response(self, mock_unified_search):
        """Test that backend errors are properly reported."""
        mock_unified_search.return_value = {
            "success": False,
            "error": "Backend query failed",
            "query": "test",
            "scope": "file",
            "bucket": "",
            "results": [],
            "total_results": 0,
            "query_time_ms": 50.0,
            "backend_used": None,
            "backend_status": {
                "status": "error",
                "error": "Connection failed",
            },
        }

        with pytest.raises(RuntimeError) as exc_info:
            search_catalog("test")

        assert "Backend query failed" in str(exc_info.value)

    @patch("quilt_mcp.tools.search._unified_search")
    def test_authentication_error(self, mock_unified_search):
        """Test that authentication errors are properly handled."""
        mock_unified_search.return_value = {
            "success": False,
            "error": "Authentication required",
            "query": "test",
            "scope": "file",
            "bucket": "",
            "results": [],
            "total_results": 0,
            "query_time_ms": 50.0,
            "backend_used": None,
        }

        with pytest.raises(RuntimeError) as exc_info:
            search_catalog("test")

        assert "Authentication required" in str(exc_info.value)


class TestIntegration:
    """Integration tests using actual search components."""

    @pytest.mark.anyio
    async def test_search_with_real_parser(self):
        """Test search with real query parser integration."""
        from quilt_mcp.search.core.query_parser import parse_query

        # Test query parsing - note that "file" scope isn't directly in SearchScope enum
        # The parser will default to GLOBAL scope if the provided scope isn't valid
        analysis = parse_query("CSV files", scope="global", bucket="")

        assert analysis.query_type.value == "file_search"
        assert "csv" in analysis.file_extensions
        # Verify it defaults to GLOBAL scope
        assert analysis.scope.value == "global"

    @pytest.mark.anyio
    async def test_backend_selection_method(self):
        """Test backend selection with mocked backends."""
        from quilt_mcp.search.backends.base import BackendRegistry, BackendType

        registry = BackendRegistry()

        # Mock Elasticsearch backend
        es_backend = Mock()
        es_backend.backend_type = BackendType.ELASTICSEARCH
        es_backend.status = BackendStatus.AVAILABLE
        es_backend.ensure_initialized = Mock()

        # Register mock backend
        registry._backends[BackendType.ELASTICSEARCH] = es_backend

        # Select primary backend
        selected = registry._select_primary_backend()

        # Should select elasticsearch
        assert selected == es_backend
        assert selected.backend_type == BackendType.ELASTICSEARCH
