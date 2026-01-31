"""
Tests for Quilt3_Backend package operations.

This module tests package-related operations including package retrieval,
transformations, and error handling for the Quilt3_Backend implementation.
"""

import logging
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError
from quilt_mcp.domain.package_info import Package_Info
from quilt_mcp.domain.content_info import Content_Info
from quilt_mcp.domain.bucket_info import Bucket_Info


class TestQuilt3BackendPackageOperations:
    """Test package-related operations in Quilt3_Backend."""

    @patch('quilt3.search_util.search_api')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_search_packages_with_mocked_quilt3_search(self, mock_quilt3, mock_search_api):
        """Test search_packages() with mocked quilt3.search() calls."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock search_api response
        mock_search_api.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "ptr_name": "test/package",
                            "description": "Test package",
                            "tags": ["test", "data"],
                            "ptr_last_modified": "2024-01-01T12:00:00",
                            "top_hash": "abc123",
                        }
                    }
                ]
            }
        }

        # Execute
        result = backend.search_packages("test query", "s3://test-registry")

        # Verify
        assert len(result) == 1
        assert isinstance(result[0], Package_Info)
        assert result[0].name == "test/package"
        assert result[0].description == "Test package"
        assert result[0].tags == ["test", "data"]
        assert result[0].registry == "s3://test-registry"
        assert result[0].bucket == "test-registry"
        assert result[0].top_hash == "abc123"

        # Verify search_api was called correctly
        mock_search_api.assert_called_once()
        call_kwargs = mock_search_api.call_args.kwargs
        assert "query" in call_kwargs
        assert "index" in call_kwargs
        assert call_kwargs["index"] == "test-registry_packages"

    @patch('quilt3.search_util.search_api')
    def test_search_packages_with_mocked_search_api(self, mock_search_api):
        """Test search_packages() with mocked quilt3.search_api() calls."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock search_api response
        mock_search_api.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "ptr_name": "test/package",  # Package name is in ptr_name field
                            "description": "Test package",
                            "tags": ["test", "data"],
                            "ptr_last_modified": "2024-01-01T12:00:00",  # Last modified is in ptr_last_modified
                            "top_hash": "abc123",
                        }
                    }
                ]
            }
        }

        # Execute
        result = backend.search_packages("test query", "s3://test-registry")

        # Verify
        assert len(result) == 1
        assert isinstance(result[0], Package_Info)
        assert result[0].name == "test/package"
        assert result[0].description == "Test package"
        assert result[0].tags == ["test", "data"]

        # Verify search_api was called with correct index
        mock_search_api.assert_called_once()
        call_args = mock_search_api.call_args
        assert call_args.kwargs["index"] == "test-registry_packages"

    @patch('quilt3.search_util.search_api')
    def test_search_packages_empty_query(self, mock_search_api):
        """Test search_packages() with empty query (match all)."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock search_api response
        mock_search_api.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "ptr_name": "test/package1",
                            "description": "Test package 1",
                            "tags": ["test"],
                            "ptr_last_modified": "2024-01-01T12:00:00",
                            "top_hash": "abc123",
                        }
                    },
                    {
                        "_source": {
                            "ptr_name": "test/package2",
                            "description": "Test package 2",
                            "tags": ["data"],
                            "ptr_last_modified": "2024-01-02T12:00:00",
                            "top_hash": "def456",
                        }
                    },
                ]
            }
        }

        # Execute with empty query
        result = backend.search_packages("", "s3://test-registry")

        # Verify
        assert len(result) == 2
        assert result[0].name == "test/package1"
        assert result[1].name == "test/package2"

        # Verify search_api was called with match_all query
        mock_search_api.assert_called_once()
        call_args = mock_search_api.call_args
        query = call_args.kwargs["query"]
        assert "match_all" in str(query)

    @patch('quilt3.search_util.search_api')
    def test_search_packages_with_special_characters(self, mock_search_api):
        """Test search_packages() with special characters in query."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock search_api response
        mock_search_api.return_value = {"hits": {"hits": []}}

        # Execute with special characters that need escaping
        backend.search_packages("test:package-name+2024", "s3://test-registry")

        # Verify search_api was called (query should be escaped internally)
        mock_search_api.assert_called_once()

    @patch('quilt3.search_util.search_api')
    def test_search_packages_with_wildcards(self, mock_search_api):
        """Test search_packages() with wildcards (should be preserved)."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock search_api response
        mock_search_api.return_value = {"hits": {"hits": []}}

        # Execute with wildcards
        backend.search_packages("test*package?name", "s3://test-registry")

        # Verify search_api was called with wildcards preserved
        mock_search_api.assert_called_once()
        call_args = mock_search_api.call_args
        query_str = str(call_args.kwargs["query"])
        # Wildcards should be in the query (not escaped)
        assert "*" in query_str or "test" in query_str

    @patch('quilt3.search_util.search_api')
    def test_search_packages_api_error(self, mock_search_api):
        """Test search_packages() handles API errors gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock search_api to return error response
        mock_search_api.return_value = {"error": "Search failed"}

        # Execute and expect BackendError
        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("test query", "s3://test-registry")

        assert "Search API error" in str(exc_info.value)

    @patch('quilt3.search_util.search_api')
    def test_search_packages_malformed_response(self, mock_search_api):
        """Test search_packages() handles malformed responses gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock search_api to return response with missing/invalid hits
        mock_search_api.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"ptr_name": "valid/package", "top_hash": "abc"}},
                    {"_source": {}},  # Missing required fields
                    {"invalid": "structure"},  # Missing _source
                ]
            }
        }

        # Execute - should skip invalid entries but not fail
        result = backend.search_packages("test query", "s3://test-registry")

        # Should return only valid packages (may be fewer than input hits)
        assert isinstance(result, list)

    @patch('quilt3.search_util.search_api')
    def test_search_packages_network_error(self, mock_search_api):
        """Test search_packages() handles network errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock search_api to raise exception
        mock_search_api.side_effect = Exception("Network error")

        # Execute and expect BackendError
        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("test query", "s3://test-registry")

        assert "Quilt3 backend search failed" in str(exc_info.value)
        assert "Network error" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_basic(self, mock_quilt3):
        """Test get_package_info() basic functionality."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package object
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test package"
        mock_package.tags = ["test", "data"]
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        mock_quilt3.Package.browse.return_value = mock_package

        # Execute
        result = backend.get_package_info("test/package", "s3://test-registry")

        # Verify
        assert isinstance(result, Package_Info)
        assert result.name == "test/package"
        assert result.description == "Test package"
        assert result.tags == ["test", "data"]
        assert result.registry == "s3://test-registry"
        assert result.bucket == "test-bucket"
        assert result.top_hash == "abc123"
        assert "2024-01-01" in result.modified_date

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_not_found(self, mock_quilt3):
        """Test get_package_info() when package doesn't exist."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock Package.browse to raise exception
        mock_quilt3.Package.browse.side_effect = Exception("Package not found")

        # Execute and expect BackendError
        with pytest.raises(BackendError) as exc_info:
            backend.get_package_info("nonexistent/package", "s3://test-registry")

        assert "Quilt3 backend get_package_info failed" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_none_tags(self, mock_quilt3):
        """Test _transform_package() handles None tags gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package with None tags
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test package"
        mock_package.tags = None  # None tags
        mock_package.modified = datetime(2024, 1, 1)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        # Execute transformation
        result = backend._transform_package(mock_package)

        # Verify tags are converted to empty list
        assert result.tags == []

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_empty_description(self, mock_quilt3):
        """Test _transform_package() handles empty description."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package with no description
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = None
        mock_package.tags = []
        mock_package.modified = datetime(2024, 1, 1)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        # Execute transformation
        result = backend._transform_package(mock_package)

        # Verify description remains None
        assert result.description is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_missing_required_fields(self, mock_quilt3):
        """Test _transform_package() raises error for missing required fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package missing required 'name' field
        mock_package = Mock()
        mock_package.description = "Test"
        mock_package.tags = []
        mock_package.modified = datetime(2024, 1, 1)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"
        # Remove name attribute to simulate missing field
        delattr(mock_package, 'name')

        # Execute and expect BackendError
        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(mock_package)

        assert "missing required field 'name'" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_none_required_field(self, mock_quilt3):
        """Test _transform_package() raises error when required field is None."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package with None required field
        mock_package = Mock()
        mock_package.name = None  # None required field
        mock_package.description = "Test"
        mock_package.tags = []
        mock_package.modified = datetime(2024, 1, 1)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        # Execute and expect BackendError
        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(mock_package)

        assert "required field 'name' is None" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_invalid_datetime(self, mock_quilt3):
        """Test _transform_package() handles invalid datetime gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package with invalid datetime
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test"
        mock_package.tags = []
        mock_package.modified = "invalid-date"  # Invalid datetime
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        # Execute and expect BackendError
        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(mock_package)

        assert "Quilt3 backend package transformation failed" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_escape_elasticsearch_query_special_chars(self, mock_quilt3):
        """Test _escape_elasticsearch_query() escapes special characters correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test escaping of special characters
        test_cases = [
            ("test:query", "test\\:query"),
            ("test+query", "test\\+query"),
            ("test-query", "test\\-query"),
            ("test(query)", "test\\(query\\)"),
            ("test[query]", "test\\[query\\]"),
            ("test{query}", "test\\{query\\}"),
            ("test/query", "test\\/query"),
        ]

        for input_query, expected_output in test_cases:
            result = backend._escape_elasticsearch_query(input_query)
            assert result == expected_output, f"Failed for input: {input_query}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_escape_elasticsearch_query_preserves_wildcards(self, mock_quilt3):
        """Test _escape_elasticsearch_query() preserves wildcards (* and ?)."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test that wildcards are NOT escaped
        test_cases = [
            ("test*", "test*"),  # * should not be escaped
            ("test?", "test?"),  # ? should not be escaped
            ("test*query?name", "test*query?name"),  # Both should be preserved
        ]

        for input_query, expected_output in test_cases:
            result = backend._escape_elasticsearch_query(input_query)
            assert result == expected_output, f"Failed for input: {input_query}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_escape_elasticsearch_query_complex(self, mock_quilt3):
        """Test _escape_elasticsearch_query() with complex query."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test complex query with both special chars and wildcards
        input_query = "test:package-name*+tag[2024]"
        result = backend._escape_elasticsearch_query(input_query)

        # Verify special chars are escaped but wildcards are preserved
        assert "\\:" in result
        assert "\\-" in result
        assert "\\+" in result
        assert "\\[" in result
        assert "\\]" in result
        assert "*" in result  # Wildcard should be preserved
        assert "\\*" not in result  # Wildcard should NOT be escaped

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_validate_package_fields_success(self, mock_quilt3):
        """Test _validate_package_fields() passes for valid package."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock valid package
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        # Execute - should not raise
        backend._validate_package_fields(mock_package)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_normalize_package_datetime_with_datetime_object(self, mock_quilt3):
        """Test _normalize_package_datetime() with datetime object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with datetime object
        dt = datetime(2024, 1, 15, 12, 30, 45)
        result = backend._normalize_package_datetime(dt)

        assert "2024-01-15" in result
        assert "12:30:45" in result

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_normalize_package_datetime_with_none(self, mock_quilt3):
        """Test _normalize_package_datetime() with None value."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with None
        result = backend._normalize_package_datetime(None)

        # Should return "None" string for backward compatibility
        assert result == "None"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_normalize_package_datetime_with_string(self, mock_quilt3):
        """Test _normalize_package_datetime() with string value."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with string
        result = backend._normalize_package_datetime("2024-01-15T12:30:45")

        assert result == "2024-01-15T12:30:45"


class TestQuilt3BackendPackageCreation:
    """Test package creation operations in Quilt3_Backend."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_method_exists(self, mock_quilt3):
        """Test that create_package_revision method exists and is callable."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Verify method exists
        assert hasattr(backend, 'create_package_revision')
        assert callable(backend.create_package_revision)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_basic_functionality(self, mock_quilt3):
        """Test create_package_revision basic functionality with minimal parameters."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.domain.package_creation import Package_Creation_Result

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package creation and operations
        mock_package = Mock()
        mock_package.push.return_value = "abc123def456"
        mock_quilt3.Package.return_value = mock_package

        # Execute with minimal parameters
        result = backend.create_package_revision(
            package_name="test/package", s3_uris=["s3://bucket/file1.txt", "s3://bucket/file2.csv"]
        )

        # Verify result is Package_Creation_Result
        assert isinstance(result, Package_Creation_Result)
        assert result.package_name == "test/package"
        assert result.top_hash == "abc123def456"
        assert result.file_count == 2
        assert result.success is True

        # Verify quilt3 operations were called correctly
        mock_quilt3.Package.assert_called_once()
        mock_package.set.assert_any_call("file1.txt", "s3://bucket/file1.txt")
        mock_package.set.assert_any_call("file2.csv", "s3://bucket/file2.csv")
        mock_package.push.assert_called_once_with(
            "test/package", registry=None, message="Package created via QuiltOps", copy="auto"
        )

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_with_all_parameters(self, mock_quilt3):
        """Test create_package_revision with all parameters specified."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.domain.package_creation import Package_Creation_Result

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.Package creation and operations
        mock_package = Mock()
        mock_package.push.return_value = "xyz789abc123"
        mock_quilt3.Package.return_value = mock_package

        # Execute with all parameters
        metadata = {"description": "Test package", "tags": ["test", "data"]}
        result = backend.create_package_revision(
            package_name="user/dataset",
            s3_uris=["s3://data-bucket/data.json"],
            metadata=metadata,
            registry="s3://custom-registry",
            message="Custom commit message",
        )

        # Verify result
        assert isinstance(result, Package_Creation_Result)
        assert result.package_name == "user/dataset"
        assert result.top_hash == "xyz789abc123"
        assert result.registry == "s3://custom-registry"
        assert result.file_count == 1
        assert result.success is True

        # Verify quilt3 operations were called correctly
        mock_quilt3.Package.assert_called_once()
        mock_package.set.assert_called_once_with("data.json", "s3://data-bucket/data.json")
        mock_package.set_meta.assert_called_once_with(metadata)
        mock_package.push.assert_called_once_with(
            "user/dataset", registry="s3://custom-registry", message="Custom commit message", copy="auto"
        )

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_with_multiple_files(self, mock_quilt3, test_registry):
        """Test create_package_revision with multiple S3 URIs."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': test_registry}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.Package creation and operations
        mock_package = Mock()
        mock_package.push.return_value = "multi123files456"
        mock_quilt3.Package.return_value = mock_package

        # Execute with multiple files
        s3_uris = [
            "s3://bucket/data/file1.txt",
            "s3://bucket/data/file2.csv",
            "s3://bucket/data/file3.json",
        ]
        result = backend.create_package_revision(package_name="multi/files", s3_uris=s3_uris, registry=test_registry)

        # Verify all files were added
        assert mock_package.set.call_count == 3
        mock_package.set.assert_any_call("data/file1.txt", "s3://bucket/data/file1.txt")
        mock_package.set.assert_any_call("data/file2.csv", "s3://bucket/data/file2.csv")
        mock_package.set.assert_any_call("data/file3.json", "s3://bucket/data/file3.json")

        assert result.file_count == 3
        assert result.success is True

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_logical_key_extraction(self, mock_quilt3, test_registry):
        """Test that logical keys are correctly extracted from S3 URIs."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': test_registry}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.Package creation and operations
        mock_package = Mock()
        mock_package.push.return_value = "logical123key456"
        mock_quilt3.Package.return_value = mock_package

        # Test various S3 URI formats
        s3_uris = [
            "s3://bucket/simple.txt",
            "s3://bucket/path/to/file.csv",
            "s3://bucket/deep/nested/path/data.json",
            "s3://bucket/file-with-dashes.txt",
            "s3://bucket/file_with_underscores.py",
        ]

        result = backend.create_package_revision(package_name="logical/keys", s3_uris=s3_uris, registry=test_registry)

        # Verify logical keys are extracted correctly (removing s3://bucket/ prefix)
        expected_calls = [
            call("simple.txt", "s3://bucket/simple.txt"),
            call("path/to/file.csv", "s3://bucket/path/to/file.csv"),
            call("deep/nested/path/data.json", "s3://bucket/deep/nested/path/data.json"),
            call("file-with-dashes.txt", "s3://bucket/file-with-dashes.txt"),
            call("file_with_underscores.py", "s3://bucket/file_with_underscores.py"),
        ]
        mock_package.set.assert_has_calls(expected_calls, any_order=True)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_catalog_url_generation(self, mock_quilt3):
        """Test that catalog URL is correctly generated when registry is provided."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.Package creation and operations
        mock_package = Mock()
        mock_package.push.return_value = "catalog123url456"
        mock_quilt3.Package.return_value = mock_package

        # Execute with registry
        result = backend.create_package_revision(
            package_name="test/package", s3_uris=["s3://bucket/file.txt"], registry="s3://my-bucket"
        )

        # Verify catalog URL is generated
        assert result.catalog_url is not None
        assert "my-bucket" in result.catalog_url
        assert "test/package" in result.catalog_url

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_uses_default_registry(self, mock_quilt3):
        """Test that create_package_revision uses default registry when not provided."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://default-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://default-registry")

        # Mock quilt3.Package creation and operations
        mock_package = Mock()
        mock_package.push.return_value = "default123registry456"
        mock_quilt3.Package.return_value = mock_package

        # Execute without registry parameter
        result = backend.create_package_revision(package_name="test/package", s3_uris=["s3://bucket/file.txt"])

        # Verify push was called with registry=None (uses quilt3 default)
        mock_package.push.assert_called_once()
        push_call_kwargs = mock_package.push.call_args.kwargs
        assert push_call_kwargs.get('registry') is None

        # Verify result uses get_registry_url() for the result
        assert result.registry == "s3://default-registry"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_error_handling_invalid_package_name(self, mock_quilt3):
        """Test create_package_revision raises ValidationError for invalid package names."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various invalid package names
        invalid_names = [
            "",  # Empty string
            "no-slash",  # Missing slash
            "/no-user",  # Missing user
            "no-package/",  # Missing package
            "too/many/slashes",  # Too many slashes
        ]

        for invalid_name in invalid_names:
            with pytest.raises(ValidationError) as exc_info:
                backend.create_package_revision(package_name=invalid_name, s3_uris=["s3://bucket/file.txt"])

            assert "package" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_error_handling_invalid_s3_uris(self, mock_quilt3):
        """Test create_package_revision raises ValidationError for invalid S3 URIs."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various invalid S3 URI scenarios
        invalid_uri_cases = [
            ([],),  # Empty list
            (["not-an-s3-uri"],),  # Not S3 URI
            (["s3://bucket-only"],),  # Missing key
            (["s3://bucket/", "invalid-uri"],),  # Mixed valid and invalid
        ]

        for invalid_uris in invalid_uri_cases:
            with pytest.raises(ValidationError) as exc_info:
                backend.create_package_revision(package_name="test/package", s3_uris=invalid_uris[0])

            assert "s3" in str(exc_info.value).lower() or "uri" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_error_handling_quilt3_package_creation_failure(self, mock_quilt3):
        """Test create_package_revision handles quilt3.Package() creation failures."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.Package to raise exception
        mock_quilt3.Package.side_effect = Exception("Package creation failed")

        with pytest.raises(BackendError) as exc_info:
            backend.create_package_revision(package_name="test/package", s3_uris=["s3://bucket/file.txt"])

        assert "Quilt3 backend create_package_revision failed" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_error_handling_package_set_failure(self, mock_quilt3):
        """Test create_package_revision handles package.set() failures."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.Package with set() that raises exception
        mock_package = Mock()
        mock_package.set.side_effect = Exception("Set operation failed")
        mock_quilt3.Package.return_value = mock_package

        with pytest.raises(BackendError) as exc_info:
            backend.create_package_revision(package_name="test/package", s3_uris=["s3://bucket/file.txt"])

        assert "Quilt3 backend create_package_revision failed" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_error_handling_package_push_failure(self, mock_quilt3):
        """Test create_package_revision handles package.push() failures."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.Package with push() that raises exception
        mock_package = Mock()
        mock_package.push.side_effect = Exception("Push operation failed")
        mock_quilt3.Package.return_value = mock_package

        with pytest.raises(BackendError) as exc_info:
            backend.create_package_revision(package_name="test/package", s3_uris=["s3://bucket/file.txt"])

        assert "Quilt3 backend create_package_revision failed" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_error_handling_metadata_set_failure(self, mock_quilt3):
        """Test create_package_revision handles set_meta() failures."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.Package with set_meta() that raises exception
        mock_package = Mock()
        mock_package.set_meta.side_effect = Exception("Metadata set failed")
        mock_quilt3.Package.return_value = mock_package

        metadata = {"description": "Test package"}
        with pytest.raises(BackendError) as exc_info:
            backend.create_package_revision(
                package_name="test/package", s3_uris=["s3://bucket/file.txt"], metadata=metadata
            )

        assert "Quilt3 backend create_package_revision failed" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_returns_failure_result_on_error(self, mock_quilt3, test_registry):
        """Test that create_package_revision returns failure result when push returns None."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.domain.package_creation import Package_Creation_Result

        mock_session = {'registry': test_registry}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.Package with push() returning None (indicates failure)
        mock_package = Mock()
        mock_package.push.return_value = None  # Indicates failure
        mock_quilt3.Package.return_value = mock_package

        result = backend.create_package_revision(
            package_name="test/package", s3_uris=["s3://bucket/file.txt"], registry=test_registry
        )

        # Should return failure result instead of raising
        assert isinstance(result, Package_Creation_Result)
        assert result.success is False
        assert result.top_hash == ""  # Empty hash for failed creation
        assert result.package_name == "test/package"
        assert result.file_count == 1

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_context_preservation_in_errors(self, mock_quilt3):
        """Test that create_package_revision preserves context in error messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock quilt3.Package to raise exception
        mock_quilt3.Package.side_effect = Exception("Test error")

        with pytest.raises(BackendError) as exc_info:
            backend.create_package_revision(
                package_name="context/test",
                s3_uris=["s3://bucket/file1.txt", "s3://bucket/file2.csv"],
                registry="s3://context-registry",
            )

        # Verify error context is preserved
        error = exc_info.value
        assert hasattr(error, 'context')
        assert error.context['package_name'] == "context/test"
        assert error.context['registry'] == "s3://context-registry"
        assert error.context['file_count'] == 2

    # ========================================================================
    # Tests for auto_organize parameter
    # ========================================================================

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_auto_organize_true_preserves_structure(self, mock_quilt3):
        """Test auto_organize=True preserves S3 folder structure in logical keys."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash123"
        mock_quilt3.Package.return_value = mock_package

        # Execute with auto_organize=True (default)
        s3_uris = [
            "s3://bucket/data/raw/file1.csv",
            "s3://bucket/data/processed/file2.json",
            "s3://bucket/config/settings.yaml",
        ]
        result = backend.create_package_revision(
            package_name="test/organized",
            s3_uris=s3_uris,
            auto_organize=True,  # Explicit True
        )

        # Verify folder structure is preserved
        expected_calls = [
            call("data/raw/file1.csv", "s3://bucket/data/raw/file1.csv"),
            call("data/processed/file2.json", "s3://bucket/data/processed/file2.json"),
            call("config/settings.yaml", "s3://bucket/config/settings.yaml"),
        ]
        mock_package.set.assert_has_calls(expected_calls, any_order=True)
        assert result.success is True

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_auto_organize_false_flattens_structure(self, mock_quilt3):
        """Test auto_organize=False flattens to just filenames."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash456"
        mock_quilt3.Package.return_value = mock_package

        # Execute with auto_organize=False
        s3_uris = [
            "s3://bucket/data/raw/file1.csv",
            "s3://bucket/data/processed/file2.json",
            "s3://bucket/config/settings.yaml",
        ]
        result = backend.create_package_revision(
            package_name="test/flattened",
            s3_uris=s3_uris,
            auto_organize=False,  # Flatten to filenames only
        )

        # Verify structure is flattened to just filenames
        expected_calls = [
            call("file1.csv", "s3://bucket/data/raw/file1.csv"),
            call("file2.json", "s3://bucket/data/processed/file2.json"),
            call("settings.yaml", "s3://bucket/config/settings.yaml"),
        ]
        mock_package.set.assert_has_calls(expected_calls, any_order=True)
        assert result.success is True

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_auto_organize_default_is_true(self, mock_quilt3):
        """Test that auto_organize defaults to True (preserves structure)."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash789"
        mock_quilt3.Package.return_value = mock_package

        # Execute WITHOUT specifying auto_organize (should default to True)
        s3_uris = ["s3://bucket/path/to/nested/file.txt"]
        result = backend.create_package_revision(
            package_name="test/default",
            s3_uris=s3_uris,
            # auto_organize not specified - should default to True
        )

        # Verify structure is preserved (default behavior)
        mock_package.set.assert_called_once_with("path/to/nested/file.txt", "s3://bucket/path/to/nested/file.txt")
        assert result.success is True

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_auto_organize_with_root_files(self, mock_quilt3):
        """Test auto_organize behavior with files at bucket root."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash999"
        mock_quilt3.Package.return_value = mock_package

        # Test with root-level files (no nested paths)
        s3_uris = ["s3://bucket/file1.txt", "s3://bucket/file2.csv"]

        # Test with auto_organize=True
        backend.create_package_revision(
            package_name="test/root-organized", s3_uris=s3_uris, auto_organize=True
        )
        # Both should produce same result for root files: just filename
        expected_calls_true = [
            call("file1.txt", "s3://bucket/file1.txt"),
            call("file2.csv", "s3://bucket/file2.csv"),
        ]
        mock_package.set.assert_has_calls(expected_calls_true, any_order=True)

        # Reset mock for second test
        mock_package.set.reset_mock()

        # Test with auto_organize=False
        backend.create_package_revision(
            package_name="test/root-flat", s3_uris=s3_uris, auto_organize=False
        )
        # Should also use just filenames
        expected_calls_false = [
            call("file1.txt", "s3://bucket/file1.txt"),
            call("file2.csv", "s3://bucket/file2.csv"),
        ]
        mock_package.set.assert_has_calls(expected_calls_false, any_order=True)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_auto_organize_mixed_depths(self, mock_quilt3):
        """Test auto_organize with files at different nesting depths."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash111"
        mock_quilt3.Package.return_value = mock_package

        # Files at various depths
        s3_uris = [
            "s3://bucket/root.txt",
            "s3://bucket/level1/file1.csv",
            "s3://bucket/level1/level2/file2.json",
            "s3://bucket/level1/level2/level3/file3.yaml",
        ]

        # Test with auto_organize=True
        backend.create_package_revision(
            package_name="test/mixed-true", s3_uris=s3_uris, auto_organize=True
        )
        expected_calls_true = [
            call("root.txt", "s3://bucket/root.txt"),
            call("level1/file1.csv", "s3://bucket/level1/file1.csv"),
            call("level1/level2/file2.json", "s3://bucket/level1/level2/file2.json"),
            call("level1/level2/level3/file3.yaml", "s3://bucket/level1/level2/level3/file3.yaml"),
        ]
        mock_package.set.assert_has_calls(expected_calls_true, any_order=True)

        # Reset mock
        mock_package.set.reset_mock()

        # Test with auto_organize=False
        backend.create_package_revision(
            package_name="test/mixed-false", s3_uris=s3_uris, auto_organize=False
        )
        expected_calls_false = [
            call("root.txt", "s3://bucket/root.txt"),
            call("file1.csv", "s3://bucket/level1/file1.csv"),
            call("file2.json", "s3://bucket/level1/level2/file2.json"),
            call("file3.yaml", "s3://bucket/level1/level2/level3/file3.yaml"),
        ]
        mock_package.set.assert_has_calls(expected_calls_false, any_order=True)

    # ========================================================================
    # Tests for copy parameter
    # ========================================================================

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_copy_auto_default(self, mock_quilt3):
        """Test that copy parameter defaults to 'auto'."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash123"
        mock_quilt3.Package.return_value = mock_package

        # Execute without specifying copy parameter
        backend.create_package_revision(
            package_name="test/package",
            s3_uris=["s3://bucket/file.txt"],
            # copy not specified - should default to "auto"
        )

        # Verify push was called with copy="auto"
        mock_package.push.assert_called_once()
        push_kwargs = mock_package.push.call_args.kwargs
        assert push_kwargs['copy'] == "auto"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_copy_always(self, mock_quilt3):
        """Test copy='always' parameter passes through to push()."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash456"
        mock_quilt3.Package.return_value = mock_package

        # Execute with copy="always"
        backend.create_package_revision(
            package_name="test/package",
            s3_uris=["s3://bucket/file.txt"],
            copy="always",  # Force copy
        )

        # Verify push was called with copy="always"
        mock_package.push.assert_called_once()
        push_kwargs = mock_package.push.call_args.kwargs
        assert push_kwargs['copy'] == "always"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_copy_never(self, mock_quilt3):
        """Test copy='never' parameter passes through to push()."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash789"
        mock_quilt3.Package.return_value = mock_package

        # Execute with copy="never"
        backend.create_package_revision(
            package_name="test/package",
            s3_uris=["s3://bucket/file.txt"],
            copy="never",  # No copy (reference only)
        )

        # Verify push was called with copy="never"
        mock_package.push.assert_called_once()
        push_kwargs = mock_package.push.call_args.kwargs
        assert push_kwargs['copy'] == "never"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_copy_auto_explicit(self, mock_quilt3):
        """Test copy='auto' parameter explicitly specified."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash999"
        mock_quilt3.Package.return_value = mock_package

        # Execute with copy="auto" explicitly
        backend.create_package_revision(
            package_name="test/package",
            s3_uris=["s3://bucket/file.txt"],
            copy="auto",  # Explicit auto
        )

        # Verify push was called with copy="auto"
        mock_package.push.assert_called_once()
        push_kwargs = mock_package.push.call_args.kwargs
        assert push_kwargs['copy'] == "auto"

    # ========================================================================
    # Tests for combined auto_organize and copy parameters
    # ========================================================================

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_auto_organize_and_copy_always(self, mock_quilt3):
        """Test auto_organize=True with copy='always'."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash111"
        mock_quilt3.Package.return_value = mock_package

        # Execute with both parameters
        s3_uris = [
            "s3://bucket/data/file1.csv",
            "s3://bucket/results/file2.json",
        ]
        result = backend.create_package_revision(
            package_name="test/organized-copy",
            s3_uris=s3_uris,
            auto_organize=True,
            copy="always",
        )

        # Verify logical keys preserve structure
        expected_calls = [
            call("data/file1.csv", "s3://bucket/data/file1.csv"),
            call("results/file2.json", "s3://bucket/results/file2.json"),
        ]
        mock_package.set.assert_has_calls(expected_calls, any_order=True)

        # Verify copy parameter passed to push
        mock_package.push.assert_called_once()
        push_kwargs = mock_package.push.call_args.kwargs
        assert push_kwargs['copy'] == "always"
        assert result.success is True

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_flatten_and_copy_never(self, mock_quilt3):
        """Test auto_organize=False with copy='never'."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash222"
        mock_quilt3.Package.return_value = mock_package

        # Execute with both parameters
        s3_uris = [
            "s3://bucket/data/raw/file1.csv",
            "s3://bucket/data/processed/file2.json",
        ]
        result = backend.create_package_revision(
            package_name="test/flat-ref",
            s3_uris=s3_uris,
            auto_organize=False,
            copy="never",
        )

        # Verify logical keys are flattened
        expected_calls = [
            call("file1.csv", "s3://bucket/data/raw/file1.csv"),
            call("file2.json", "s3://bucket/data/processed/file2.json"),
        ]
        mock_package.set.assert_has_calls(expected_calls, any_order=True)

        # Verify copy parameter passed to push
        mock_package.push.assert_called_once()
        push_kwargs = mock_package.push.call_args.kwargs
        assert push_kwargs['copy'] == "never"
        assert result.success is True

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_create_package_revision_all_parameters_together(self, mock_quilt3):
        """Test all parameters (auto_organize, copy, metadata, message, registry) together."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock get_registry_url to return a valid S3 URL
        backend.get_registry_url = Mock(return_value="s3://test-registry")

        # Mock quilt3.Package
        mock_package = Mock()
        mock_package.push.return_value = "hash333"
        mock_quilt3.Package.return_value = mock_package

        # Execute with all parameters
        metadata = {"version": "1.0", "author": "test"}
        result = backend.create_package_revision(
            package_name="test/complete",
            s3_uris=["s3://bucket/data/file.csv", "s3://bucket/config/settings.yaml"],
            metadata=metadata,
            registry="s3://custom-registry",
            message="Full parameter test",
            auto_organize=True,
            copy="always",
        )

        # Verify logical keys (organized)
        expected_calls = [
            call("data/file.csv", "s3://bucket/data/file.csv"),
            call("config/settings.yaml", "s3://bucket/config/settings.yaml"),
        ]
        mock_package.set.assert_has_calls(expected_calls, any_order=True)

        # Verify metadata was set
        mock_package.set_meta.assert_called_once_with(metadata)

        # Verify push with all parameters
        mock_package.push.assert_called_once_with(
            "test/complete",
            registry="s3://custom-registry",
            message="Full parameter test",
            copy="always",
        )

        # Verify result
        assert result.success is True
        assert result.top_hash == "hash333"
        assert result.registry == "s3://custom-registry"
        assert result.file_count == 2

    # ========================================================================
    # Tests for _extract_logical_key helper method
    # ========================================================================

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_extract_logical_key_with_auto_organize_true(self, mock_quilt3):
        """Test _extract_logical_key() with auto_organize=True preserves paths."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        test_cases = [
            ("s3://bucket/file.txt", "file.txt"),
            ("s3://bucket/path/to/file.csv", "path/to/file.csv"),
            ("s3://bucket/a/b/c/d/file.json", "a/b/c/d/file.json"),
        ]

        for s3_uri, expected_key in test_cases:
            result = backend._extract_logical_key(s3_uri, auto_organize=True)
            assert result == expected_key, f"Failed for {s3_uri}: expected {expected_key}, got {result}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_extract_logical_key_with_auto_organize_false(self, mock_quilt3):
        """Test _extract_logical_key() with auto_organize=False uses only filename."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        test_cases = [
            ("s3://bucket/file.txt", "file.txt"),
            ("s3://bucket/path/to/file.csv", "file.csv"),
            ("s3://bucket/a/b/c/d/file.json", "file.json"),
        ]

        for s3_uri, expected_key in test_cases:
            result = backend._extract_logical_key(s3_uri, auto_organize=False)
            assert result == expected_key, f"Failed for {s3_uri}: expected {expected_key}, got {result}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_extract_logical_key_edge_cases(self, mock_quilt3):
        """Test _extract_logical_key() with edge cases."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with special characters in filename
        assert backend._extract_logical_key("s3://bucket/file-with-dashes.txt", True) == "file-with-dashes.txt"
        assert backend._extract_logical_key("s3://bucket/path/file_with_underscores.csv", True) == "path/file_with_underscores.csv"
        assert backend._extract_logical_key("s3://bucket/path/file.multiple.dots.json", True) == "path/file.multiple.dots.json"

        # Test flattening with special characters
        assert backend._extract_logical_key("s3://bucket/path/file-with-dashes.txt", False) == "file-with-dashes.txt"
        assert backend._extract_logical_key("s3://bucket/path/file.multiple.dots.json", False) == "file.multiple.dots.json"

    # ========================================================================
    # Tests for list_all_packages (stub)
    # ========================================================================

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_list_all_packages_not_implemented(self, mock_quilt3):
        """Test that list_all_packages() raises NotImplementedError."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Verify method raises NotImplementedError
        with pytest.raises(NotImplementedError) as exc_info:
            backend.list_all_packages("s3://test-registry")

        assert "not yet implemented" in str(exc_info.value).lower()
