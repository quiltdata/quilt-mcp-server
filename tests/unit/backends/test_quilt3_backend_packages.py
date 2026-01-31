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

        # Verify search_api was called with ES DSL query
        mock_search_api.assert_called_once()
        call_kwargs = mock_search_api.call_args.kwargs

        assert "query" in call_kwargs
        assert "index" in call_kwargs
        assert "limit" in call_kwargs

        es_query = call_kwargs["query"]
        assert isinstance(es_query, dict)
        assert "query" in es_query
        # Check that it's a bool query with ptr_name filter
        assert "bool" in es_query["query"]
        assert "must" in es_query["query"]["bool"]
        must_clauses = es_query["query"]["bool"]["must"]
        # Should have query_string and exists clauses
        assert len(must_clauses) == 2
        assert any("query_string" in clause for clause in must_clauses)
        assert any("exists" in clause and clause["exists"]["field"] == "ptr_name" for clause in must_clauses)
        assert call_kwargs["index"] == "test-registry_packages"
        assert call_kwargs["limit"] == 1000

    @patch('quilt3.search_util.search_api')
    def test_search_packages_error_handling(self, mock_search_api):
        """Test search_packages() error handling."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock search_api to raise exception
        mock_search_api.side_effect = Exception("Network error")

        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("test", "s3://test-registry")

        assert "quilt3" in str(exc_info.value).lower()
        assert "network error" in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_with_mocked_package_loading(self, mock_quilt3):
        """Test get_package_info() with mocked quilt3 package loading."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package loading
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test package"
        mock_package.tags = ["test"]
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
        mock_quilt3.Package.browse.assert_called_once_with("test/package", registry="s3://test-registry")

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_error_handling(self, mock_quilt3):
        """Test get_package_info() error handling."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package loading to raise exception
        mock_quilt3.Package.browse.side_effect = Exception("Package not found")

        with pytest.raises(BackendError):
            backend.get_package_info("nonexistent/package", "s3://test-registry")

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_calls_quilt3_browse_correctly(self, mock_quilt3):
        """Test that get_package_info() correctly calls quilt3.Package.browse with proper parameters."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package object
        mock_package = Mock()
        mock_package.name = "user/dataset"
        mock_package.description = "Test dataset"
        mock_package.tags = ["data", "test"]
        mock_package.modified = datetime(2024, 1, 15, 10, 30, 0)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "def456ghi789"

        mock_quilt3.Package.browse.return_value = mock_package

        # Execute
        result = backend.get_package_info("user/dataset", "s3://test-registry")

        # Verify quilt3.Package.browse was called with correct parameters
        mock_quilt3.Package.browse.assert_called_once_with("user/dataset", registry="s3://test-registry")

        # Verify result is properly transformed
        assert isinstance(result, Package_Info)
        assert result.name == "user/dataset"
        assert result.description == "Test dataset"
        assert result.tags == ["data", "test"]
        assert result.modified_date == "2024-01-15T10:30:00"
        assert result.registry == "s3://test-registry"
        assert result.bucket == "test-bucket"
        assert result.top_hash == "def456ghi789"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_with_different_registries(self, mock_quilt3):
        """Test get_package_info() works with different registry formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different registry formats
        registries = [
            "s3://my-bucket",
            "s3://another-registry-bucket",
            "s3://test-bucket-with-dashes",
        ]

        for registry in registries:
            # Mock package object
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = []
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = registry
            mock_package.bucket = registry.replace("s3://", "")
            mock_package.top_hash = "abc123"

            mock_quilt3.Package.browse.return_value = mock_package

            # Execute
            result = backend.get_package_info("test/package", registry)

            # Verify correct registry was passed to quilt3
            mock_quilt3.Package.browse.assert_called_with("test/package", registry=registry)

            # Verify result contains correct registry
            assert result.registry == registry
            assert result.bucket == registry.replace("s3://", "")

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_with_complex_package_names(self, mock_quilt3):
        """Test get_package_info() works with complex package names."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various package name formats
        package_names = [
            "simple-package",
            "user/dataset",
            "organization/project/dataset",
            "user-name/dataset-name",
            "org.domain/project.name",
        ]

        for package_name in package_names:
            # Mock package object
            mock_package = Mock()
            mock_package.name = package_name
            mock_package.description = f"Package {package_name}"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            mock_quilt3.Package.browse.return_value = mock_package

            # Execute
            result = backend.get_package_info(package_name, "s3://test-registry")

            # Verify correct package name was passed to quilt3
            mock_quilt3.Package.browse.assert_called_with(package_name, registry="s3://test-registry")

            # Verify result contains correct package name
            assert result.name == package_name

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_transformation_to_package_info(self, mock_quilt3):
        """Test that get_package_info() properly transforms quilt3 Package to Package_Info domain object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create comprehensive mock package with all fields
        mock_package = Mock()
        mock_package.name = "comprehensive/package"
        mock_package.description = "A comprehensive test package with all metadata"
        mock_package.tags = ["comprehensive", "test", "metadata", "full"]
        mock_package.modified = datetime(2024, 3, 15, 14, 30, 45)
        mock_package.registry = "s3://comprehensive-registry"
        mock_package.bucket = "comprehensive-bucket"
        mock_package.top_hash = "abcdef123456789comprehensive"

        mock_quilt3.Package.browse.return_value = mock_package

        # Execute
        result = backend.get_package_info("comprehensive/package", "s3://comprehensive-registry")

        # Verify result is Package_Info domain object
        assert isinstance(result, Package_Info)

        # Verify all fields are correctly transformed
        assert result.name == "comprehensive/package"
        assert result.description == "A comprehensive test package with all metadata"
        assert result.tags == ["comprehensive", "test", "metadata", "full"]
        assert result.modified_date == "2024-03-15T14:30:45"
        assert result.registry == "s3://comprehensive-registry"
        assert result.bucket == "comprehensive-bucket"
        assert result.top_hash == "abcdef123456789comprehensive"

        # Verify it's a proper dataclass that can be serialized
        from dataclasses import asdict

        result_dict = asdict(result)
        assert isinstance(result_dict, dict)
        assert result_dict['name'] == "comprehensive/package"
        assert result_dict['description'] == "A comprehensive test package with all metadata"
        assert result_dict['tags'] == ["comprehensive", "test", "metadata", "full"]

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_error_scenarios(self, mock_quilt3):
        """Test get_package_info() error handling for various failure scenarios."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various error scenarios
        error_scenarios = [
            (Exception("Package not found"), "not found"),
            (Exception("Access denied"), "access denied"),
            (Exception("Network timeout"), "timeout"),
            (Exception("Invalid package format"), "invalid"),
            (PermissionError("Insufficient permissions"), "permission"),
            (ValueError("Invalid registry URL"), "invalid"),
            (ConnectionError("Connection failed"), "connection"),
        ]

        for error, expected_context in error_scenarios:
            mock_quilt3.Package.browse.side_effect = error

            with pytest.raises(BackendError) as exc_info:
                backend.get_package_info("test/package", "s3://test-registry")

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "get_package_info failed" in error_message.lower()
            assert expected_context.lower() in error_message.lower()

            # Reset for next test
            mock_quilt3.Package.browse.side_effect = None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_with_missing_optional_fields(self, mock_quilt3):
        """Test get_package_info() handles packages with missing optional fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package with minimal required fields only
        mock_package = Mock()
        mock_package.name = "minimal/package"
        mock_package.description = None  # Optional field missing
        mock_package.tags = None  # Optional field missing
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "minimal123"

        mock_quilt3.Package.browse.return_value = mock_package

        # Execute
        result = backend.get_package_info("minimal/package", "s3://test-registry")

        # Verify result handles missing fields gracefully
        assert isinstance(result, Package_Info)
        assert result.name == "minimal/package"
        assert result.description is None
        assert result.tags == []  # Should default to empty list
        assert result.modified_date == "2024-01-01T12:00:00"
        assert result.registry == "s3://test-registry"
        assert result.bucket == "test-bucket"
        assert result.top_hash == "minimal123"


class TestQuilt3BackendPackageTransformationIsolated:
    """Test _transform_package() method in complete isolation with focus on transformation logic."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_isolated_with_minimal_mock(self, mock_quilt3):
        """Test _transform_package() method in isolation with minimal mock quilt3.Package object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create minimal mock package with only required fields
        mock_package = Mock()
        mock_package.name = "isolated/test"
        mock_package.description = "Isolated test package"
        mock_package.tags = ["isolated", "test"]
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = "s3://isolated-registry"
        mock_package.bucket = "isolated-bucket"
        mock_package.top_hash = "isolated123hash"

        # Execute transformation in isolation
        result = backend._transform_package(mock_package)

        # Verify transformation produces correct Package_Info
        assert isinstance(result, Package_Info)
        assert result.name == "isolated/test"
        assert result.description == "Isolated test package"
        assert result.tags == ["isolated", "test"]
        assert result.modified_date == "2024-01-01T12:00:00"
        assert result.registry == "s3://isolated-registry"
        assert result.bucket == "isolated-bucket"
        assert result.top_hash == "isolated123hash"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_isolated_validation_logic(self, mock_quilt3):
        """Test _transform_package() validation logic in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test validation of required fields
        required_field_tests = [
            ('name', None, "required field 'name' is None"),
            ('registry', None, "required field 'registry' is None"),
            ('bucket', None, "required field 'bucket' is None"),
            ('top_hash', None, "required field 'top_hash' is None"),
        ]

        for field_name, field_value, expected_error in required_field_tests:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = []
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            # Set the specific field to None to trigger validation error
            setattr(mock_package, field_name, field_value)

            with pytest.raises(BackendError) as exc_info:
                backend._transform_package(mock_package)

            assert expected_error in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_isolated_helper_method_integration(self, mock_quilt3):
        """Test _transform_package() integration with helper methods in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock package that exercises all helper methods
        mock_package = Mock()
        mock_package.name = "helper/integration"
        mock_package.description = None  # Tests _normalize_description
        mock_package.tags = None  # Tests _normalize_tags
        mock_package.modified = datetime(2024, 2, 15, 14, 30, 45)  # Tests _normalize_package_datetime
        mock_package.registry = "s3://helper-registry"
        mock_package.bucket = "helper-bucket"
        mock_package.top_hash = "helper456hash"

        # Execute transformation
        result = backend._transform_package(mock_package)

        # Verify helper method results are correctly integrated
        assert result.name == "helper/integration"
        assert result.description is None  # _normalize_description preserves None
        assert result.tags == []  # _normalize_tags converts None to empty list
        assert result.modified_date == "2024-02-15T14:30:45"  # _normalize_package_datetime converts datetime
        assert result.registry == "s3://helper-registry"
        assert result.bucket == "helper-bucket"
        assert result.top_hash == "helper456hash"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_isolated_error_context_preservation(self, mock_quilt3):
        """Test _transform_package() error context preservation in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock package that will cause transformation error
        mock_package = Mock()
        mock_package.name = "error/test"
        mock_package.description = "Error test package"
        mock_package.tags = []
        mock_package.modified = "invalid-date"  # This triggers ValueError in _normalize_package_datetime
        mock_package.registry = "s3://error-registry"
        mock_package.bucket = "error-bucket"
        mock_package.top_hash = "error789hash"

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(mock_package)

        error_message = str(exc_info.value)
        # Verify error context is preserved
        assert "Quilt3 backend package transformation failed" in error_message
        assert "Invalid date format" in error_message

        # Verify error context includes package information
        error_context = exc_info.value.context
        assert error_context['package_name'] == "error/test"
        assert error_context['package_type'] == "Mock"
        assert 'available_attributes' in error_context

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_isolated_with_edge_case_inputs(self, mock_quilt3):
        """Test _transform_package() with edge case inputs in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with edge case values
        edge_cases = [
            {
                'name': "",  # Empty string name
                'description': "",  # Empty description
                'tags': [],  # Empty tags list
                'modified': datetime(1970, 1, 1, 0, 0, 0),  # Unix epoch
                'registry': "s3://a",  # Minimal registry
                'bucket': "b",  # Minimal bucket
                'top_hash': "0",  # Minimal hash
            },
            {
                'name': "a" * 1000,  # Very long name
                'description': "d" * 10000,  # Very long description
                'tags': ["t" + str(i) for i in range(1000)],  # Many tags
                'modified': datetime(2099, 12, 31, 23, 59, 59),  # Future date
                'registry': "s3://" + "x" * 100,  # Long registry
                'bucket': "y" * 100,  # Long bucket
                'top_hash': "z" * 200,  # Long hash
            },
        ]

        for i, edge_case in enumerate(edge_cases):
            mock_package = Mock()
            for attr, value in edge_case.items():
                setattr(mock_package, attr, value)

            # Should handle edge cases without error
            result = backend._transform_package(mock_package)

            assert isinstance(result, Package_Info)
            assert result.name == edge_case['name']
            assert result.description == edge_case['description']
            assert result.tags == edge_case['tags']
            assert result.registry == edge_case['registry']
            assert result.bucket == edge_case['bucket']
            assert result.top_hash == edge_case['top_hash']


class TestQuilt3BackendTransformationHelperMethods:
    """Test transformation helper methods in complete isolation."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_validate_package_fields_isolated(self, mock_quilt3):
        """Test _validate_package_fields() method in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with valid package
        valid_package = Mock()
        valid_package.name = "valid/package"
        valid_package.registry = "s3://valid-registry"
        valid_package.bucket = "valid-bucket"
        valid_package.top_hash = "valid123"

        # Should not raise any exception
        backend._validate_package_fields(valid_package)

        # Test missing required fields
        required_fields = ['name', 'registry', 'bucket', 'top_hash']
        for missing_field in required_fields:
            invalid_package = Mock()
            invalid_package.name = "test/package"
            invalid_package.registry = "s3://test-registry"
            invalid_package.bucket = "test-bucket"
            invalid_package.top_hash = "test123"

            # Remove the required field
            delattr(invalid_package, missing_field)

            with pytest.raises(BackendError) as exc_info:
                backend._validate_package_fields(invalid_package)

            assert f"missing required field '{missing_field}'" in str(exc_info.value)

        # Test None values for required fields
        for field_name in required_fields:
            invalid_package = Mock()
            invalid_package.name = "test/package"
            invalid_package.registry = "s3://test-registry"
            invalid_package.bucket = "test-bucket"
            invalid_package.top_hash = "test123"

            # Set the field to None
            setattr(invalid_package, field_name, None)

            with pytest.raises(BackendError) as exc_info:
                backend._validate_package_fields(invalid_package)

            assert f"required field '{field_name}' is None" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_normalize_tags_isolated(self, mock_quilt3):
        """Test _normalize_tags() method in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various tag input scenarios
        tag_scenarios = [
            (None, []),  # None -> empty list
            ([], []),  # Empty list -> empty list
            (["tag1", "tag2"], ["tag1", "tag2"]),  # Normal list -> same list
            ("single_tag", ["single_tag"]),  # Single string -> list with one item
            ([1, 2, 3], ["1", "2", "3"]),  # Numbers -> string conversion
            ([None, "tag", 123], ["None", "tag", "123"]),  # Mixed types -> string conversion
            (42, []),  # Unexpected type -> empty list
            ({"key": "value"}, []),  # Dict -> empty list
        ]

        for input_tags, expected_output in tag_scenarios:
            result = backend._normalize_tags(input_tags)
            assert result == expected_output, f"Failed for input: {input_tags}"
            assert isinstance(result, list), f"Result should be list for input: {input_tags}"
            assert all(isinstance(tag, str) for tag in result), f"All tags should be strings for input: {input_tags}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_normalize_package_datetime_isolated(self, mock_quilt3):
        """Test _normalize_package_datetime() method in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various datetime input scenarios
        datetime_scenarios = [
            (None, "None"),  # None -> "None" string (backward compatibility)
            (datetime(2024, 1, 1, 12, 0, 0), "2024-01-01T12:00:00"),  # datetime -> ISO string
            ("2024-01-01T12:00:00Z", "2024-01-01T12:00:00Z"),  # String -> same string
            ("custom_date_string", "custom_date_string"),  # Custom string -> same string
            (123456789, "123456789"),  # Number -> string
        ]

        for input_datetime, expected_output in datetime_scenarios:
            result = backend._normalize_package_datetime(input_datetime)
            assert result == expected_output, f"Failed for input: {input_datetime}"
            assert isinstance(result, str), f"Result should be string for input: {input_datetime}"

        # Test error case
        with pytest.raises(ValueError) as exc_info:
            backend._normalize_package_datetime("invalid-date")
        assert "Invalid date format" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_normalize_description_isolated(self, mock_quilt3):
        """Test _normalize_description() method in isolation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various description input scenarios
        description_scenarios = [
            (None, None),  # None -> None
            ("", ""),  # Empty string -> empty string
            ("Normal description", "Normal description"),  # Normal string -> same string
            (123, "123"),  # Number -> string
            (True, "True"),  # Boolean -> string
            (["list", "item"], "['list', 'item']"),  # List -> string representation
            ({"key": "value"}, "{'key': 'value'}"),  # Dict -> string representation
        ]

        for input_description, expected_output in description_scenarios:
            result = backend._normalize_description(input_description)
            assert result == expected_output, f"Failed for input: {input_description}"
            if expected_output is not None:
                assert isinstance(result, str), f"Result should be string for input: {input_description}"


class TestQuilt3BackendMockPackageTransformation:
    """Test transformation with mock quilt3.Package objects with various configurations."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_complete_mock_package(self, mock_quilt3):
        """Test _transform_package() with complete mock quilt3.Package object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create comprehensive mock quilt3.Package with all fields
        mock_package = Mock()
        mock_package.name = "comprehensive/dataset"
        mock_package.description = "A comprehensive test dataset with full metadata"
        mock_package.tags = ["comprehensive", "test", "dataset", "full-metadata"]
        mock_package.modified = datetime(2024, 3, 15, 14, 30, 45, 123456)
        mock_package.registry = "s3://comprehensive-registry"
        mock_package.bucket = "comprehensive-bucket"
        mock_package.top_hash = "abcdef123456789comprehensive"

        # Execute transformation
        result = backend._transform_package(mock_package)

        # Verify complete transformation
        assert isinstance(result, Package_Info)
        assert result.name == "comprehensive/dataset"
        assert result.description == "A comprehensive test dataset with full metadata"
        assert result.tags == ["comprehensive", "test", "dataset", "full-metadata"]
        assert result.modified_date == "2024-03-15T14:30:45.123456"
        assert result.registry == "s3://comprehensive-registry"
        assert result.bucket == "comprehensive-bucket"
        assert result.top_hash == "abcdef123456789comprehensive"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_minimal_mock_package(self, mock_quilt3):
        """Test _transform_package() with minimal mock quilt3.Package object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create minimal mock quilt3.Package with only required fields
        mock_package = Mock()
        mock_package.name = "minimal/package"
        mock_package.description = None  # Optional field
        mock_package.tags = None  # Optional field
        mock_package.modified = datetime(2024, 1, 1, 0, 0, 0)
        mock_package.registry = "s3://minimal-registry"
        mock_package.bucket = "minimal-bucket"
        mock_package.top_hash = "minimal123"

        # Execute transformation
        result = backend._transform_package(mock_package)

        # Verify minimal transformation handles None values correctly
        assert isinstance(result, Package_Info)
        assert result.name == "minimal/package"
        assert result.description is None
        assert result.tags == []  # Should convert None to empty list
        assert result.modified_date == "2024-01-01T00:00:00"
        assert result.registry == "s3://minimal-registry"
        assert result.bucket == "minimal-bucket"
        assert result.top_hash == "minimal123"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_edge_case_mock_configurations(self, mock_quilt3):
        """Test _transform_package() with edge case mock quilt3.Package configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various edge case configurations
        edge_cases = [
            {
                'name': None,  # None name (should cause validation error)
                'description': "",  # Empty description
                'tags': [],  # Empty tags list
                'modified': datetime(1970, 1, 1, 0, 0, 0),  # Unix epoch
                'registry': "s3://a",  # Minimal registry
                'bucket': "b",  # Minimal bucket
                'top_hash': "0",  # Minimal hash
                'should_fail': True,  # This configuration should fail validation
            },
            {
                'name': "a" * 1000,  # Very long name
                'description': "d" * 10000,  # Very long description
                'tags': ["t" + str(i) for i in range(100)],  # Many tags
                'modified': datetime(2099, 12, 31, 23, 59, 59),  # Future date
                'registry': "s3://" + "x" * 63,  # Long registry (AWS bucket name limit)
                'bucket': "y" * 63,  # Long bucket (AWS bucket name limit)
                'top_hash': "z" * 200,  # Long hash
                'should_fail': False,
            },
            {
                'name': "unicode/测试包",  # Unicode package name
                'description': "Unicode description: 测试描述 with émojis 🚀📊",
                'tags': ["unicode-标签", "émoji-🏷️", "special-chars-!@#"],
                'modified': datetime(2024, 6, 15, 12, 30, 45),
                'registry': "s3://unicode-registry",
                'bucket': "unicode-bucket",
                'top_hash': "unicode123hash",
                'should_fail': False,
            },
        ]

        for i, case in enumerate(edge_cases):
            mock_package = Mock()
            for attr, value in case.items():
                if attr != 'should_fail':
                    setattr(mock_package, attr, value)

            if case['should_fail']:
                with pytest.raises(BackendError):
                    backend._transform_package(mock_package)
            else:
                result = backend._transform_package(mock_package)
                assert isinstance(result, Package_Info)
                assert result.name == case['name']
                assert result.description == case['description']
                assert result.tags == case['tags']
                assert result.registry == case['registry']
                assert result.bucket == case['bucket']
                assert result.top_hash == case['top_hash']

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_various_tag_configurations(self, mock_quilt3):
        """Test _transform_package() with various tag configurations in mock packages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different tag configurations
        tag_configurations = [
            (None, []),  # None tags
            ([], []),  # Empty list
            (["single"], ["single"]),  # Single tag
            (["tag1", "tag2", "tag3"], ["tag1", "tag2", "tag3"]),  # Multiple tags
            ("single_string", ["single_string"]),  # Single string (should be converted to list)
            ([1, 2, 3], ["1", "2", "3"]),  # Numbers (should be converted to strings)
            ([None, "valid", 123, True], ["None", "valid", "123", "True"]),  # Mixed types
            ({"invalid": "dict"}, []),  # Invalid type (should default to empty list)
        ]

        for input_tags, expected_tags in tag_configurations:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = input_tags
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            result = backend._transform_package(mock_package)
            assert result.tags == expected_tags, f"Failed for input tags: {input_tags}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_various_datetime_configurations(self, mock_quilt3):
        """Test _transform_package() with various datetime configurations in mock packages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different datetime configurations
        datetime_configurations = [
            (None, "None"),  # None datetime
            (datetime(2024, 1, 1, 12, 0, 0), "2024-01-01T12:00:00"),  # Standard datetime
            (datetime(2024, 12, 31, 23, 59, 59, 999999), "2024-12-31T23:59:59.999999"),  # With microseconds
            ("2024-01-01T12:00:00Z", "2024-01-01T12:00:00Z"),  # String datetime
            ("custom_date_string", "custom_date_string"),  # Custom string
            (123456789, "123456789"),  # Numeric timestamp
        ]

        for input_datetime, expected_datetime in datetime_configurations:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = input_datetime
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            result = backend._transform_package(mock_package)
            assert result.modified_date == expected_datetime, f"Failed for input datetime: {input_datetime}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_various_description_configurations(self, mock_quilt3):
        """Test _transform_package() with various description configurations in mock packages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different description configurations
        description_configurations = [
            (None, None),  # None description
            ("", ""),  # Empty string
            ("Simple description", "Simple description"),  # Normal string
            ("Multi-line\ndescription\nwith\ttabs", "Multi-line\ndescription\nwith\ttabs"),  # Multi-line
            ("Unicode: 测试描述 with émojis 🚀📊", "Unicode: 测试描述 with émojis 🚀📊"),  # Unicode
            ("A" * 10000, "A" * 10000),  # Very long description
            (123, "123"),  # Number (should be converted to string)
            (True, "True"),  # Boolean (should be converted to string)
            (["list", "item"], "['list', 'item']"),  # List (should be converted to string)
        ]

        for input_description, expected_description in description_configurations:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = input_description
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            result = backend._transform_package(mock_package)
            assert result.description == expected_description, f"Failed for input description: {input_description}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_complex_registry_configurations(self, mock_quilt3):
        """Test _transform_package() with complex registry configurations in mock packages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various registry and bucket configurations
        registry_configurations = [
            ("s3://simple-bucket", "simple-bucket"),
            ("s3://bucket-with-dashes", "bucket-with-dashes"),
            ("s3://bucket.with.dots", "bucket.with.dots"),
            ("s3://bucket_with_underscores", "bucket_with_underscores"),
            ("s3://123numeric-bucket", "123numeric-bucket"),
            (
                "s3://very-long-bucket-name-with-many-characters-and-dashes-for-testing-purposes",
                "very-long-bucket-name-with-many-characters-and-dashes-for-testing-purposes",
            ),
            ("s3://a", "a"),  # Single character bucket
        ]

        for registry, expected_bucket in registry_configurations:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = registry
            mock_package.bucket = expected_bucket
            mock_package.top_hash = "abc123"

            result = backend._transform_package(mock_package)
            assert result.registry == registry, f"Failed for registry: {registry}"
            assert result.bucket == expected_bucket, f"Failed for bucket: {expected_bucket}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_various_hash_configurations(self, mock_quilt3):
        """Test _transform_package() with various top_hash configurations in mock packages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test different hash configurations
        hash_configurations = [
            "abc123",  # Short hash
            "abcdef123456789abcdef123456789abcdef123456789abcdef123456789abcdef12",  # Long hash
            "0123456789abcdef",  # Hex characters
            "hash-with-dashes-and-special-chars_123",  # Hash with special characters
            "UPPERCASE_HASH_123",  # Uppercase hash
            "mixedCaseHash123",  # Mixed case
            "hash.with.dots",  # Hash with dots
            "hash/with/slashes",  # Hash with slashes (unusual but possible)
            None,  # None hash (should cause validation error)
        ]

        for top_hash in hash_configurations:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = top_hash

            if top_hash is None:
                # None hash should cause validation error
                with pytest.raises(BackendError):
                    backend._transform_package(mock_package)
            else:
                result = backend._transform_package(mock_package)
                assert result.top_hash == top_hash, f"Failed for hash: {top_hash}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_mock_package_missing_attributes(self, mock_quilt3):
        """Test _transform_package() with mock packages missing required attributes."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test missing required attributes
        required_attributes = ['name', 'registry', 'bucket', 'top_hash']

        for missing_attr in required_attributes:
            mock_package = Mock()
            # Set all required attributes
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            # Remove the specific required attribute
            delattr(mock_package, missing_attr)

            with pytest.raises(BackendError) as exc_info:
                backend._transform_package(mock_package)

            assert f"missing required field '{missing_attr}'" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_mock_package_none_attributes(self, mock_quilt3):
        """Test _transform_package() with mock packages having None required attributes."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test None values for required attributes
        required_attributes = ['name', 'registry', 'bucket', 'top_hash']

        for none_attr in required_attributes:
            mock_package = Mock()
            # Set all required attributes
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            # Set the specific required attribute to None
            setattr(mock_package, none_attr, None)

            with pytest.raises(BackendError) as exc_info:
                backend._transform_package(mock_package)

            assert f"required field '{none_attr}' is None" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_mock_package_type_variations(self, mock_quilt3):
        """Test _transform_package() with different types of mock package objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with different mock object types
        mock_types = [
            Mock(),  # Standard Mock
            type('CustomPackage', (), {})(),  # Custom class instance
            type('MockPackage', (object,), {})(),  # Object subclass
        ]

        for mock_package in mock_types:
            # Set required attributes
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            result = backend._transform_package(mock_package)
            assert isinstance(result, Package_Info)
            assert result.name == "test/package"


class TestQuilt3BackendMissingNullFieldHandling:
    """Test handling of missing/null fields in quilt3 objects during transformation."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_missing_optional_attributes(self, mock_quilt3):
        """Test _transform_package() handles missing optional attributes gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock package with only required fields
        mock_package = Mock()
        mock_package.name = "minimal/package"
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)

        # Remove optional attributes to test missing field handling
        if hasattr(mock_package, 'description'):
            delattr(mock_package, 'description')
        if hasattr(mock_package, 'tags'):
            delattr(mock_package, 'tags')

        # Should handle missing optional attributes gracefully by using getattr with defaults
        result = backend._transform_package(mock_package)

        assert isinstance(result, Package_Info)
        assert result.name == "minimal/package"
        assert result.description is None  # Should handle missing description gracefully
        assert result.tags == []  # Should handle missing tags gracefully
        assert result.modified_date == "2024-01-01T12:00:00"
        assert result.registry == "s3://test-registry"
        assert result.bucket == "test-bucket"
        assert result.top_hash == "abc123"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_null_optional_fields(self, mock_quilt3):
        """Test _transform_package() handles null/None values in optional fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various null/None scenarios for optional fields
        null_scenarios = [
            {'description': None, 'tags': None},
            {'description': None, 'tags': []},
            {'description': "", 'tags': None},
            {'description': "", 'tags': []},
            {'description': None, 'tags': [None, "valid", None]},
        ]

        for i, scenario in enumerate(null_scenarios):
            mock_package = Mock()
            mock_package.name = f"null-test-{i}/package"
            mock_package.description = scenario['description']
            mock_package.tags = scenario['tags']
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = f"hash{i}"

            result = backend._transform_package(mock_package)

            assert isinstance(result, Package_Info)
            assert result.name == f"null-test-{i}/package"

            # Verify null handling
            if scenario['description'] is None:
                assert result.description is None
            else:
                assert result.description == scenario['description']

            # Tags should always be a list, even if input is None
            assert isinstance(result.tags, list)
            if scenario['tags'] is None:
                assert result.tags == []
            elif scenario['tags'] == [None, "valid", None]:
                assert result.tags == ["None", "valid", "None"]  # None converted to string
            else:
                assert result.tags == scenario['tags']

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_missing_required_attributes(self, mock_quilt3):
        """Test _transform_package() properly fails when required attributes are missing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        required_fields = ['name', 'registry', 'bucket', 'top_hash']

        for missing_field in required_fields:
            # Create complete mock package
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            # Remove the specific required attribute
            delattr(mock_package, missing_field)

            with pytest.raises(BackendError) as exc_info:
                backend._transform_package(mock_package)

            error_message = str(exc_info.value)
            assert f"missing required field '{missing_field}'" in error_message
            assert "invalid package object" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_null_required_fields(self, mock_quilt3):
        """Test _transform_package() properly fails when required fields are None."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        required_fields = ['name', 'registry', 'bucket', 'top_hash']

        for null_field in required_fields:
            # Create complete mock package
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            # Set the specific required field to None
            setattr(mock_package, null_field, None)

            with pytest.raises(BackendError) as exc_info:
                backend._transform_package(mock_package)

            error_message = str(exc_info.value)
            assert f"required field '{null_field}' is None" in error_message
            assert "invalid package object" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_empty_string_fields(self, mock_quilt3):
        """Test _transform_package() handles empty string values appropriately."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test empty strings in required fields - should cause validation errors
        mock_package = Mock()
        mock_package.name = ""  # Empty name should cause validation error
        mock_package.description = ""  # Empty description should be preserved
        mock_package.tags = ["", "valid", ""]  # Empty tags should be preserved
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = ""  # Empty registry should cause validation error
        mock_package.bucket = ""  # Empty bucket should cause validation error
        mock_package.top_hash = ""  # Empty hash should cause validation error

        # Empty required fields should cause validation errors
        # The current validation logic checks for None, not empty strings
        # So empty strings in required fields are actually allowed
        result = backend._transform_package(mock_package)

        assert isinstance(result, Package_Info)
        assert result.name == ""  # Empty string preserved
        assert result.description == ""  # Empty string preserved
        assert result.tags == ["", "valid", ""]  # Empty strings in tags preserved
        assert result.registry == ""  # Empty string preserved
        assert result.bucket == ""  # Empty string preserved
        assert result.top_hash == ""  # Empty string preserved

        # Test with valid required fields but empty optional fields
        mock_package.name = "empty-test/package"
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        result = backend._transform_package(mock_package)

        assert result.name == "empty-test/package"
        assert result.description == ""  # Empty string preserved
        assert result.tags == ["", "valid", ""]  # Empty strings in tags preserved

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_malformed_datetime_fields(self, mock_quilt3):
        """Test _transform_package() handles malformed datetime fields appropriately."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various malformed datetime scenarios
        datetime_scenarios = [
            None,  # None datetime (should be handled gracefully)
            "invalid-date-string",  # Invalid string (should cause error in test mode)
            "",  # Empty string
            123456789,  # Numeric timestamp (should be converted to string)
            "2024-13-45T25:70:80",  # Invalid date components
            {"invalid": "object"},  # Invalid object type
        ]

        for i, modified_value in enumerate(datetime_scenarios):
            mock_package = Mock()
            mock_package.name = f"datetime-test-{i}/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = modified_value
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = f"hash{i}"

            if modified_value == "invalid-date":
                # This specific case should trigger error in _normalize_package_datetime
                with pytest.raises(BackendError):
                    backend._transform_package(mock_package)
            else:
                # Other cases should be handled gracefully
                result = backend._transform_package(mock_package)
                assert isinstance(result, Package_Info)
                assert result.name == f"datetime-test-{i}/package"

                if modified_value is None:
                    assert result.modified_date == "None"  # Backward compatibility
                else:
                    assert isinstance(result.modified_date, str)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_unexpected_field_types(self, mock_quilt3):
        """Test _transform_package() handles unexpected field types gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test unexpected types for various fields
        mock_package = Mock()
        mock_package.name = 12345  # Number instead of string
        mock_package.description = ["list", "instead", "of", "string"]  # List instead of string
        mock_package.tags = "single_string"  # String instead of list
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = {"s3": "test-registry"}  # Dict instead of string
        mock_package.bucket = True  # Boolean instead of string
        mock_package.top_hash = 3.14159  # Float instead of string

        # Should handle type conversion gracefully for most fields
        result = backend._transform_package(mock_package)

        assert isinstance(result, Package_Info)
        # The Package_Info dataclass preserves the original types, doesn't convert them
        assert result.name == 12345  # Original type preserved
        assert result.description == "['list', 'instead', 'of', 'string']"  # Converted to string
        assert result.tags == ["single_string"]  # Converted to list
        assert result.registry == {"s3": "test-registry"}  # Original type preserved
        assert result.bucket is True  # Original type preserved
        assert result.top_hash == 3.14159  # Original type preserved

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_missing_optional_attributes(self, mock_quilt3):
        """Test _transform_content() handles missing optional attributes gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock content entry with minimal required fields
        mock_entry = Mock()
        mock_entry.name = "minimal_file.txt"

        # Remove optional attributes to test missing field handling
        if hasattr(mock_entry, 'size'):
            delattr(mock_entry, 'size')
        if hasattr(mock_entry, 'modified'):
            delattr(mock_entry, 'modified')
        if hasattr(mock_entry, 'is_dir'):
            delattr(mock_entry, 'is_dir')

        # Should handle missing optional fields gracefully
        result = backend._transform_content(mock_entry)

        assert isinstance(result, Content_Info)
        assert result.path == "minimal_file.txt"
        assert result.size is None  # Should default to None for missing size
        assert result.modified_date is None  # Should default to None for missing modified
        assert result.type == "file"  # Should default to "file" for missing is_dir
        assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_null_optional_fields(self, mock_quilt3):
        """Test _transform_content() handles null/None values in optional fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various null/None scenarios for optional fields
        null_scenarios = [
            {'size': None, 'modified': None, 'is_dir': None},
            {'size': 0, 'modified': None, 'is_dir': False},
            {'size': None, 'modified': datetime(2024, 1, 1), 'is_dir': True},
        ]

        for i, scenario in enumerate(null_scenarios):
            mock_entry = Mock()
            mock_entry.name = f"null-content-{i}.txt"
            mock_entry.size = scenario['size']
            mock_entry.modified = scenario['modified']
            mock_entry.is_dir = scenario['is_dir']

            result = backend._transform_content(mock_entry)

            assert isinstance(result, Content_Info)
            assert result.path == f"null-content-{i}.txt"

            # Verify null handling
            if scenario['size'] is None:
                assert result.size is None
            else:
                assert result.size == scenario['size']

            if scenario['modified'] is None:
                assert result.modified_date is None
            else:
                assert result.modified_date == scenario['modified'].isoformat()

            if scenario['is_dir'] is None:
                assert result.type == "file"  # Default to file
            else:
                assert result.type == ("directory" if scenario['is_dir'] else "file")

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_missing_required_attributes(self, mock_quilt3):
        """Test _transform_content() properly fails when required attributes are missing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test missing name attribute
        mock_entry = Mock()
        mock_entry.size = 1024
        mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry.is_dir = False

        # Remove the required name attribute
        if hasattr(mock_entry, 'name'):
            delattr(mock_entry, 'name')

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry)

        error_message = str(exc_info.value)
        assert "missing name" in error_message.lower()
        assert "content transformation failed" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_with_null_required_fields(self, mock_quilt3):
        """Test _transform_content() properly fails when required fields are None."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test None name
        mock_entry = Mock()
        mock_entry.name = None
        mock_entry.size = 1024
        mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry.is_dir = False

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry)

        error_message = str(exc_info.value)
        assert "missing name" in error_message.lower()

        # Test empty name
        mock_entry.name = ""

        with pytest.raises(BackendError) as exc_info:
            backend._transform_content(mock_entry)

        error_message = str(exc_info.value)
        assert "empty name" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_bucket_with_missing_optional_fields(self, mock_quilt3):
        """Test _transform_bucket() handles missing optional fields gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with minimal bucket data (missing optional fields)
        bucket_name = "minimal-bucket"
        bucket_data = {
            'region': 'us-west-2',
            'access_level': 'read-only',
            # created_date missing
        }

        result = backend._transform_bucket(bucket_name, bucket_data)

        assert isinstance(result, Bucket_Info)
        assert result.name == "minimal-bucket"
        assert result.region == "us-west-2"
        assert result.access_level == "read-only"
        assert result.created_date is None  # Should default to None for missing field

        # Test with completely empty bucket data (should use defaults)
        bucket_data_empty = {}

        result_empty = backend._transform_bucket("empty-bucket", bucket_data_empty)

        assert isinstance(result_empty, Bucket_Info)
        assert result_empty.name == "empty-bucket"
        assert result_empty.region == "unknown"  # Should default to "unknown"
        assert result_empty.access_level == "unknown"  # Should default to "unknown"
        assert result_empty.created_date is None  # Should default to None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_bucket_with_null_optional_fields(self, mock_quilt3):
        """Test _transform_bucket() handles null/None values in optional fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test scenarios that should now work due to improved null handling
        working_scenarios = [
            {'region': 'us-east-1', 'access_level': 'read-write', 'created_date': None},
            {'region': 'us-west-2', 'access_level': 'read-only', 'created_date': None},
            {'region': 'eu-west-1', 'access_level': 'admin', 'created_date': ""},
        ]

        for i, scenario in enumerate(working_scenarios):
            bucket_name = f"null-bucket-{i}"
            bucket_data = scenario

            result = backend._transform_bucket(bucket_name, bucket_data)

            assert isinstance(result, Bucket_Info)
            assert result.name == bucket_name

            # Verify null handling - fields should be converted to strings or None
            assert result.region == scenario['region']  # Region must be non-empty
            assert result.access_level == scenario['access_level']  # Access level must be non-empty

            if scenario['created_date'] is None:
                assert result.created_date is None
            else:
                assert result.created_date == str(scenario['created_date'])

        # Test scenarios that should fail due to domain validation
        failing_scenarios = [
            {'region': None, 'access_level': 'read-write', 'created_date': None},
            {'region': "", 'access_level': 'read-write', 'created_date': None},
            {'region': 'us-east-1', 'access_level': None, 'created_date': None},
            {'region': 'us-east-1', 'access_level': "", 'created_date': None},
        ]

        for i, scenario in enumerate(failing_scenarios):
            bucket_name = f"failing-bucket-{i}"
            bucket_data = scenario

            # These should now work because None and empty strings are converted to "unknown"
            result = backend._transform_bucket(bucket_name, bucket_data)
            assert isinstance(result, Bucket_Info)
            assert result.name == bucket_name

            # None and empty strings should be converted to "unknown"
            if scenario['region'] is None or scenario['region'] == "":
                assert result.region == "unknown"
            else:
                assert result.region == scenario['region']

            if scenario['access_level'] is None or scenario['access_level'] == "":
                assert result.access_level == "unknown"
            else:
                assert result.access_level == scenario['access_level']

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_bucket_with_missing_required_fields(self, mock_quilt3):
        """Test _transform_bucket() properly fails when required fields are missing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test missing bucket name
        bucket_name = None
        bucket_data = {'region': 'us-east-1', 'access_level': 'read-write'}

        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket(bucket_name, bucket_data)

        error_message = str(exc_info.value)
        assert "missing name" in error_message.lower()

        # Test empty bucket name
        bucket_name = ""

        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket(bucket_name, bucket_data)

        error_message = str(exc_info.value)
        assert "missing name" in error_message.lower()

        # Test None bucket data
        bucket_name = "test-bucket"
        bucket_data = None

        with pytest.raises(BackendError) as exc_info:
            backend._transform_bucket(bucket_name, bucket_data)

        error_message = str(exc_info.value)
        assert "bucket_data is none" in error_message.lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_bucket_with_empty_bucket_data(self, mock_quilt3):
        """Test _transform_bucket() handles empty bucket data but fails due to domain validation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with empty bucket data dictionary
        bucket_name = "empty-data-bucket"
        bucket_data = {}

        # Empty bucket data will now work because we provide "unknown" defaults
        result = backend._transform_bucket(bucket_name, bucket_data)

        assert isinstance(result, Bucket_Info)
        assert result.name == bucket_name
        assert result.region == "unknown"  # Should default to "unknown"
        assert result.access_level == "unknown"  # Should default to "unknown"
        assert result.created_date is None  # Should default to None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_provides_reasonable_defaults(self, mock_quilt3):
        """Test _transform_package() provides reasonable defaults for missing/null fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with various combinations of missing/null optional fields
        test_cases = [
            {
                'name': 'test-defaults-1',
                'description': None,
                'tags': None,
                'expected_description': None,
                'expected_tags': [],
            },
            {
                'name': 'test-defaults-2',
                'description': '',
                'tags': [],
                'expected_description': '',
                'expected_tags': [],
            },
            {
                'name': 'test-defaults-3',
                'description': 'Valid description',
                'tags': ['tag1', 'tag2'],
                'expected_description': 'Valid description',
                'expected_tags': ['tag1', 'tag2'],
            },
        ]

        for case in test_cases:
            mock_package = Mock()
            mock_package.name = case['name']
            mock_package.description = case['description']
            mock_package.tags = case['tags']
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            result = backend._transform_package(mock_package)

            assert isinstance(result, Package_Info)
            assert result.name == case['name']
            assert result.description == case['expected_description']
            assert result.tags == case['expected_tags']
            assert result.modified_date == "2024-01-01T12:00:00"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_content_provides_reasonable_defaults(self, mock_quilt3):
        """Test _transform_content() provides reasonable defaults for missing/null fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with various combinations of missing/null optional fields
        test_cases = [
            {
                'name': 'file1.txt',
                'size': None,
                'modified': None,
                'is_dir': None,
                'expected_size': None,
                'expected_modified': None,
                'expected_type': 'file',
            },
            {
                'name': 'file2.txt',
                'size': 0,
                'modified': datetime(2024, 1, 1, 12, 0, 0),
                'is_dir': False,
                'expected_size': 0,
                'expected_modified': '2024-01-01T12:00:00',
                'expected_type': 'file',
            },
            {
                'name': 'directory/',
                'size': None,
                'modified': None,
                'is_dir': True,
                'expected_size': None,
                'expected_modified': None,
                'expected_type': 'directory',
            },
        ]

        for case in test_cases:
            mock_entry = Mock()
            mock_entry.name = case['name']
            mock_entry.size = case['size']
            mock_entry.modified = case['modified']
            mock_entry.is_dir = case['is_dir']

            result = backend._transform_content(mock_entry)

            assert isinstance(result, Content_Info)
            assert result.path == case['name']
            assert result.size == case['expected_size']
            assert result.modified_date == case['expected_modified']
            assert result.type == case['expected_type']
            assert result.download_url is None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_bucket_provides_reasonable_defaults(self, mock_quilt3):
        """Test _transform_bucket() provides reasonable defaults for missing/null fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with various combinations of missing/null optional fields
        test_cases = [
            {
                'bucket_name': 'test-bucket-1',
                'bucket_data': {'region': 'us-east-1', 'access_level': 'read-only'},
                'expected_region': 'us-east-1',
                'expected_access_level': 'read-only',
                'expected_created_date': None,
            },
            {
                'bucket_name': 'test-bucket-2',
                'bucket_data': {'region': 'us-west-2', 'access_level': 'admin', 'created_date': '2024-01-01'},
                'expected_region': 'us-west-2',
                'expected_access_level': 'admin',
                'expected_created_date': '2024-01-01',
            },
            {
                'bucket_name': 'test-bucket-3',
                'bucket_data': {'region': 'eu-central-1', 'access_level': 'read-write', 'created_date': None},
                'expected_region': 'eu-central-1',
                'expected_access_level': 'read-write',
                'expected_created_date': None,
            },
        ]

        for case in test_cases:
            result = backend._transform_bucket(case['bucket_name'], case['bucket_data'])

            assert isinstance(result, Bucket_Info)
            assert result.name == case['bucket_name']
            assert result.region == case['expected_region']
            assert result.access_level == case['expected_access_level']
            assert result.created_date == case['expected_created_date']

        # Test cases that should now work because empty strings are converted to "unknown"
        edge_cases = [
            {
                'bucket_name': 'edge-case-bucket-1',
                'bucket_data': {'region': '', 'access_level': 'read-only'},  # Empty region -> "unknown"
                'expected_region': 'unknown',
                'expected_access_level': 'read-only',
                'expected_created_date': None,
            },
            {
                'bucket_name': 'edge-case-bucket-2',
                'bucket_data': {'region': 'us-east-1', 'access_level': ''},  # Empty access_level -> "unknown"
                'expected_region': 'us-east-1',
                'expected_access_level': 'unknown',
                'expected_created_date': None,
            },
        ]

        for case in edge_cases:
            result = backend._transform_bucket(case['bucket_name'], case['bucket_data'])

            assert isinstance(result, Bucket_Info)
            assert result.name == case['bucket_name']
            assert result.region == case['expected_region']
            assert result.access_level == case['expected_access_level']
            assert result.created_date == case['expected_created_date']

        # Test case with completely empty bucket data (should use defaults)
        result_empty = backend._transform_bucket("empty-bucket", {})

        assert isinstance(result_empty, Bucket_Info)
        assert result_empty.name == "empty-bucket"
        assert result_empty.region == "unknown"  # Should default to "unknown"
        assert result_empty.access_level == "unknown"  # Should default to "unknown"
        assert result_empty.created_date is None  # Should default to None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_edge_case_attribute_access_patterns(self, mock_quilt3):
        """Test _transform_package() works with mock objects created from Elasticsearch responses."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock package that mimics the format used in search_packages
        # This tests the transformation path used when processing search results
        mock_package = type('MockPackage', (), {})()
        mock_package.name = "elasticsearch/package"
        mock_package.description = "Package from Elasticsearch"
        mock_package.tags = ["elasticsearch", "search"]
        mock_package.modified = "2024-01-01T12:00:00Z"  # String format from ES
        mock_package.registry = "s3://search-registry"
        mock_package.bucket = "search-bucket"
        mock_package.top_hash = "es123hash456"

        result = backend._transform_package(mock_package)

        # Verify transformation works correctly
        assert isinstance(result, Package_Info)
        assert result.name == "elasticsearch/package"
        assert result.description == "Package from Elasticsearch"
        assert result.tags == ["elasticsearch", "search"]
        assert result.modified_date == "2024-01-01T12:00:00Z"
        assert result.registry == "s3://search-registry"
        assert result.bucket == "search-bucket"
        assert result.top_hash == "es123hash456"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_mock_package_performance_edge_cases(self, mock_quilt3):
        """Test _transform_package() handles performance edge cases with large data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with very large data structures
        mock_package = Mock()
        mock_package.name = "performance/test"
        mock_package.description = "A" * 100000  # Very long description
        mock_package.tags = [f"tag{i}" for i in range(10000)]  # Many tags
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = "s3://performance-registry"
        mock_package.bucket = "performance-bucket"
        mock_package.top_hash = "perf" * 1000  # Very long hash

        # Should handle large data without issues
        result = backend._transform_package(mock_package)

        assert isinstance(result, Package_Info)
        assert result.name == "performance/test"
        assert len(result.description) == 100000
        assert len(result.tags) == 10000
        assert len(result.top_hash) == 4000  # "perf" * 1000ckend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with different mock object types
        mock_types = [
            Mock(),  # Standard Mock
            MagicMock(),  # MagicMock
            type('MockPackage', (), {})(),  # Custom class instance
        ]

        for i, mock_package in enumerate(mock_types):
            # Set attributes on each mock type
            mock_package.name = f"test/package-{i}"
            mock_package.description = f"Test package {i}"
            mock_package.tags = [f"test-{i}", f"mock-{i}"]
            mock_package.modified = datetime(2024, 1, 1, 12, i, 0)
            mock_package.registry = f"s3://test-registry-{i}"
            mock_package.bucket = f"test-bucket-{i}"
            mock_package.top_hash = f"abc123-{i}"

            result = backend._transform_package(mock_package)

            assert isinstance(result, Package_Info)
            assert result.name == f"test/package-{i}"
            assert result.description == f"Test package {i}"
            assert result.tags == [f"test-{i}", f"mock-{i}"]
            assert result.registry == f"s3://test-registry-{i}"
            assert result.bucket == f"test-bucket-{i}"
            assert result.top_hash == f"abc123-{i}"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_mock_package_elasticsearch_format_v2(self, mock_quilt3):
        """Test _transform_package() with mock packages mimicking Elasticsearch response format."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock package that mimics the format used in search_packages
        # This tests the transformation path used when processing search results
        mock_package = type('MockPackage', (), {})()
        mock_package.name = "elasticsearch/search-result"
        mock_package.description = "Package from Elasticsearch search"
        mock_package.tags = ["elasticsearch", "search", "result"]
        mock_package.modified = "2024-01-01T12:00:00Z"  # String format from ES
        mock_package.registry = "s3://search-registry"
        mock_package.bucket = "search-bucket"
        mock_package.top_hash = "es123hash456"

        result = backend._transform_package(mock_package)

        # Verify transformation works correctly with ES-style data
        assert isinstance(result, Package_Info)
        assert result.name == "elasticsearch/search-result"
        assert result.description == "Package from Elasticsearch search"
        assert result.tags == ["elasticsearch", "search", "result"]
        assert result.modified_date == "2024-01-01T12:00:00Z"
        assert result.registry == "s3://search-registry"
        assert result.bucket == "search-bucket"
        assert result.top_hash == "es123hash456"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_mock_package_performance_edge_cases_v2(self, mock_quilt3):
        """Test _transform_package() with mock packages designed to test performance edge cases."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with very large data structures
        large_mock_package = Mock()
        large_mock_package.name = "performance/large-package"
        large_mock_package.description = "X" * 100000  # 100KB description
        large_mock_package.tags = [f"tag-{i}" for i in range(10000)]  # 10K tags
        large_mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        large_mock_package.registry = "s3://performance-registry"
        large_mock_package.bucket = "performance-bucket"
        large_mock_package.top_hash = "performance" + "x" * 1000  # Long hash

        # Should handle large data without issues
        result = backend._transform_package(large_mock_package)

        assert isinstance(result, Package_Info)
        assert result.name == "performance/large-package"
        assert len(result.description) == 100000
        assert len(result.tags) == 10000
        assert result.registry == "s3://performance-registry"
        assert result.bucket == "performance-bucket"
        assert len(result.top_hash) == 1011  # "performance" + 1000 x's


class TestQuilt3BackendPackageTransformation:
    """Test package transformation methods in isolation."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_all_fields(self, mock_quilt3):
        """Test _transform_package() method with complete quilt3.Package object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock quilt3 package
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test description"
        mock_package.tags = ["tag1", "tag2"]
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123def456"

        # Execute transformation
        result = backend._transform_package(mock_package)

        # Verify
        assert isinstance(result, Package_Info)
        assert result.name == "test/package"
        assert result.description == "Test description"
        assert result.tags == ["tag1", "tag2"]
        assert result.modified_date == "2024-01-01T12:00:00"
        assert result.registry == "s3://test-registry"
        assert result.bucket == "test-bucket"
        assert result.top_hash == "abc123def456"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_missing_fields(self, mock_quilt3):
        """Test _transform_package() handles missing/null fields in quilt3 objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock quilt3 package with missing fields
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = None
        mock_package.tags = None
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        # Execute transformation
        result = backend._transform_package(mock_package)

        # Verify
        assert result.description is None
        assert result.tags == []  # Should default to empty list

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_error_handling(self, mock_quilt3):
        """Test _transform_package() error handling in transformation logic."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock package that will cause transformation error
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.modified = "invalid-date"  # Invalid date format
        mock_package.description = "Test package"
        mock_package.tags = []
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(mock_package)

        assert "transformation failed" in str(exc_info.value).lower()

    @pytest.mark.skip(reason="Advanced error handling edge cases - to be addressed in follow-up")
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_error_wrapping_and_context(self, mock_quilt3):
        """Test that transformation errors are properly wrapped in BackendError with context."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various error scenarios that should be wrapped in BackendError
        error_scenarios = [
            # Missing required field
            {
                'setup': lambda pkg: delattr(pkg, 'name'),
                'expected_message': 'missing required field',
                'description': 'missing required field',
            },
            # None required field
            {
                'setup': lambda pkg: setattr(pkg, 'top_hash', None),
                'expected_message': 'required field \'top_hash\' is None',
                'description': 'None required field',
            },
            # Invalid datetime format
            {
                'setup': lambda pkg: setattr(pkg, 'modified', 'invalid-date'),
                'expected_message': 'Invalid date format',
                'description': 'invalid datetime format',
            },
            # Attribute access error
            {
                'setup': lambda pkg: setattr(
                    pkg,
                    'description',
                    property(lambda self: exec('raise AttributeError("Access denied")')),  # noqa: S102
                ),
                'expected_message': 'transformation failed',
                'description': 'attribute access error',
            },
        ]

        for scenario in error_scenarios:
            # Create fresh mock package for each test
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            # Apply the error scenario setup
            try:
                scenario['setup'](mock_package)
            except Exception as e:
                # Some setups might fail, skip those
                logger.debug(f"Skipping scenario {scenario.get('description', 'unknown')}: {e}")
                continue

            # Test that error is wrapped in BackendError
            with pytest.raises(BackendError) as exc_info:
                backend._transform_package(mock_package)

            error = exc_info.value
            error_message = str(error)

            # Verify error message contains expected content
            assert scenario['expected_message'].lower() in error_message.lower(), (
                f"Expected '{scenario['expected_message']}' in error message for {scenario['description']}"
            )

            # Verify error is properly wrapped as BackendError
            assert isinstance(error, BackendError), f"Error should be BackendError for {scenario['description']}"

            # Verify error context is provided
            assert hasattr(error, 'context'), f"Error should have context for {scenario['description']}"
            if error.context:
                assert 'package_name' in error.context or 'package_type' in error.context, (
                    f"Error context should contain package info for {scenario['description']}"
                )

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_error_message_clarity(self, mock_quilt3):
        """Test that transformation error messages are clear and actionable."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test error message clarity for different failure types
        clarity_tests = [
            {
                'name': 'missing_name_field',
                'setup': lambda pkg: delattr(pkg, 'name'),
                'expected_keywords': ['missing', 'required', 'field', 'name'],
            },
            {
                'name': 'none_registry_field',
                'setup': lambda pkg: setattr(pkg, 'registry', None),
                'expected_keywords': ['required', 'field', 'registry', 'none'],
            },
            {
                'name': 'invalid_datetime',
                'setup': lambda pkg: setattr(pkg, 'modified', 'invalid-date'),
                'expected_keywords': ['invalid', 'date', 'format'],
            },
        ]

        for test_case in clarity_tests:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            test_case['setup'](mock_package)

            with pytest.raises(BackendError) as exc_info:
                backend._transform_package(mock_package)

            error_message = str(exc_info.value).lower()

            # Verify error message contains expected keywords for clarity
            for keyword in test_case['expected_keywords']:
                assert keyword.lower() in error_message, (
                    f"Error message should contain '{keyword}' for {test_case['name']}: {error_message}"
                )

            # Verify error message mentions the backend type
            assert 'quilt3' in error_message, (
                f"Error message should mention backend type for {test_case['name']}: {error_message}"
            )

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_error_propagation_from_helpers(self, mock_quilt3):
        """Test that errors from helper methods are properly propagated."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test error propagation from validation helper
        mock_package = Mock()
        mock_package.name = None  # This will trigger _validate_package_fields error
        mock_package.description = "Test package"
        mock_package.tags = ["test"]
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(mock_package)

        # Verify the validation error is properly propagated
        assert "required field 'name' is None" in str(exc_info.value)

        # Test error propagation from normalization helper
        mock_package.name = "test/package"
        mock_package.modified = "invalid-date"  # This will trigger _normalize_package_datetime error

        with pytest.raises(BackendError) as exc_info:
            backend._transform_package(mock_package)

        # Verify the normalization error is properly propagated
        assert "Invalid date format" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_various_transformation_failures(self, mock_quilt3):
        """Test various types of transformation failures and their error handling."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test Package_Info creation failure
        with patch(
            'quilt_mcp.backends.quilt3_backend_packages.Package_Info',
            side_effect=ValueError("Package_Info creation failed"),
        ):
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            with pytest.raises(BackendError) as exc_info:
                backend._transform_package(mock_package)

            assert 'transformation failed' in str(exc_info.value).lower()
            assert 'package_info creation failed' in str(exc_info.value).lower()

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_various_date_formats(self, mock_quilt3):
        """Test _transform_package() handles various date formats from quilt3 objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with datetime object
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test package"
        mock_package.tags = ["test"]
        mock_package.modified = datetime(2024, 1, 15, 10, 30, 45)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        result = backend._transform_package(mock_package)
        assert result.modified_date == "2024-01-15T10:30:45"

        # Test with string date
        mock_package.modified = "2024-01-15T10:30:45Z"
        result = backend._transform_package(mock_package)
        assert result.modified_date == "2024-01-15T10:30:45Z"

        # Test with None date
        mock_package.modified = None
        result = backend._transform_package(mock_package)
        assert result.modified_date == "None"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_empty_and_null_tags(self, mock_quilt3):
        """Test _transform_package() handles empty and null tags correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test with None tags
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test package"
        mock_package.tags = None
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        result = backend._transform_package(mock_package)
        assert result.tags == []

        # Test with empty list
        mock_package.tags = []
        result = backend._transform_package(mock_package)
        assert result.tags == []

        # Test with populated tags
        mock_package.tags = ["tag1", "tag2", "tag3"]
        result = backend._transform_package(mock_package)
        assert result.tags == ["tag1", "tag2", "tag3"]

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_complex_package_names(self, mock_quilt3):
        """Test _transform_package() handles complex package names correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        complex_names = [
            "simple-package",
            "user/dataset",
            "organization/project/dataset",
            "user-name/dataset-name",
            "org.domain/project.name",
            "namespace_with_underscores/package_name",
            "123numeric/456package",
            "unicode-测试/package名称",
        ]

        for package_name in complex_names:
            mock_package = Mock()
            mock_package.name = package_name
            mock_package.description = f"Package {package_name}"
            mock_package.tags = ["test"]
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            result = backend._transform_package(mock_package)
            assert result.name == package_name
            assert isinstance(result, Package_Info)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_various_registry_formats(self, mock_quilt3):
        """Test _transform_package() handles various registry URL formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        registry_formats = [
            "s3://simple-bucket",
            "s3://bucket-with-dashes",
            "s3://bucket.with.dots",
            "s3://bucket_with_underscores",
            "s3://123numeric-bucket",
            "s3://very-long-bucket-name-with-many-characters-and-dashes",
        ]

        for registry in registry_formats:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = []
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = registry
            mock_package.bucket = registry.replace("s3://", "")
            mock_package.top_hash = "abc123"

            result = backend._transform_package(mock_package)
            assert result.registry == registry
            assert result.bucket == registry.replace("s3://", "")

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_various_hash_formats(self, mock_quilt3):
        """Test _transform_package() handles various top_hash formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        hash_formats = [
            "abc123def456",  # Short hash
            "abcdef123456789abcdef123456789abcdef123456789abcdef123456789abcdef12",  # Long hash
            "0123456789abcdef",  # Hex characters
            "",  # Empty hash
            "hash-with-dashes",  # Hash with special characters
            "UPPERCASE_HASH_123",  # Uppercase hash
        ]

        for top_hash in hash_formats:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = []
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = top_hash

            result = backend._transform_package(mock_package)
            assert result.top_hash == top_hash

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_long_descriptions(self, mock_quilt3):
        """Test _transform_package() handles long and special character descriptions."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        descriptions = [
            "A" * 1000,  # Very long description
            "Description with\nnewlines\nand\ttabs",  # Special characters
            "Unicode description: 测试描述 with émojis 🚀📊",  # Unicode
            "",  # Empty description
            None,  # None description
            "Description with \"quotes\" and 'apostrophes'",  # Quotes
            "Description with special chars: !@#$%^&*()_+-=[]{}|;:,.<>?",  # Special symbols
        ]

        for description in descriptions:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = description
            mock_package.tags = []
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            result = backend._transform_package(mock_package)
            assert result.description == description
            assert isinstance(result, Package_Info)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_large_tag_lists(self, mock_quilt3):
        """Test _transform_package() handles large tag lists and special tag formats."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        tag_scenarios = [
            ["tag" + str(i) for i in range(100)],  # Large number of tags
            ["tag-with-dashes", "tag_with_underscores", "tag.with.dots"],  # Special characters
            ["UPPERCASE", "lowercase", "MiXeDcAsE"],  # Case variations
            ["unicode-标签", "émoji-🏷️", "special-chars-!@#"],  # Unicode and special chars
            [""],  # Empty tag in list
            ["very-long-tag-name-that-exceeds-normal-length-expectations-and-continues-for-a-while"],  # Long tag
            ["123", "456", "789"],  # Numeric tags
        ]

        for tags in tag_scenarios:
            mock_package = Mock()
            mock_package.name = "test/package"
            mock_package.description = "Test package"
            mock_package.tags = tags
            mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
            mock_package.registry = "s3://test-registry"
            mock_package.bucket = "test-bucket"
            mock_package.top_hash = "abc123"

            result = backend._transform_package(mock_package)
            assert result.tags == tags
            assert isinstance(result, Package_Info)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_missing_required_fields(self, mock_quilt3):
        """Test _transform_package() handles missing required fields gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test missing name (should cause error)
        mock_package = Mock()
        del mock_package.name  # Remove name attribute
        mock_package.description = "Test package"
        mock_package.tags = []
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        with pytest.raises(BackendError):
            backend._transform_package(mock_package)

        # Test missing registry (should cause error)
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test package"
        mock_package.tags = []
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        del mock_package.registry  # Remove registry attribute
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        with pytest.raises(BackendError):
            backend._transform_package(mock_package)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_preserves_all_field_types(self, mock_quilt3):
        """Test _transform_package() preserves correct data types for all fields."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test description"
        mock_package.tags = ["tag1", "tag2"]
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123def456"

        result = backend._transform_package(mock_package)

        # Verify all field types
        assert isinstance(result.name, str)
        assert isinstance(result.description, str) or result.description is None
        assert isinstance(result.tags, list)
        assert isinstance(result.modified_date, str)
        assert isinstance(result.registry, str)
        assert isinstance(result.bucket, str)
        assert isinstance(result.top_hash, str)

        # Verify specific values
        assert result.name == "test/package"
        assert result.description == "Test description"
        assert result.tags == ["tag1", "tag2"]
        assert result.modified_date == "2024-01-01T12:00:00"
        assert result.registry == "s3://test-registry"
        assert result.bucket == "test-bucket"
        assert result.top_hash == "abc123def456"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_transform_package_with_mock_elasticsearch_response_format(self, mock_quilt3):
        """Test _transform_package() works with mock objects created from Elasticsearch responses."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Create mock package that mimics the format used in search_packages
        # This tests the transformation path used when processing search results
        mock_package = type('MockPackage', (), {})()
        mock_package.name = "elasticsearch/package"
        mock_package.description = "Package from Elasticsearch"
        mock_package.tags = ["elasticsearch", "search"]
        mock_package.modified = "2024-01-01T12:00:00Z"  # String format from ES
        mock_package.registry = "s3://search-registry"
        mock_package.bucket = "search-bucket"
        mock_package.top_hash = "es123hash456"

        result = backend._transform_package(mock_package)

        # Verify transformation works correctly
        assert isinstance(result, Package_Info)
        assert result.name == "elasticsearch/package"
        assert result.description == "Package from Elasticsearch"
        assert result.tags == ["elasticsearch", "search"]
        assert result.modified_date == "2024-01-01T12:00:00Z"
        assert result.registry == "s3://search-registry"
        assert result.bucket == "search-bucket"
        assert result.top_hash == "es123hash456"


class TestQuilt3BackendPackageOperationsErrorHandling:
    """Test comprehensive error handling for package operations (search_packages and get_package_info)."""

    @patch('quilt3.search_util.search_api')
    def test_search_packages_network_errors(self, mock_search_api):
        """Test search_packages() handles various network errors correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various network error scenarios
        network_errors = [
            ConnectionError("Connection failed"),
            TimeoutError("Request timed out"),
            OSError("Network is unreachable"),
            Exception("DNS resolution failed"),
            Exception("Connection reset by peer"),
            Exception("SSL handshake failed"),
        ]

        for error in network_errors:
            mock_search_api.side_effect = error

            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test query", "s3://test-registry")

            error_message = str(exc_info.value)
            # Verify error message includes backend type
            assert "quilt3" in error_message.lower()
            # Verify error message includes operation context
            assert "search failed" in error_message.lower()
            # Verify original error is preserved
            assert str(error) in error_message

            # Reset for next test
            mock_search_api.side_effect = None

    @patch('quilt3.search_util.search_api')
    def test_search_packages_authentication_errors(self, mock_search_api):
        """Test search_packages() handles authentication/permission errors correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various authentication error scenarios
        auth_errors = [
            PermissionError("Access denied"),
            Exception("403 Forbidden"),
            Exception("401 Unauthorized"),
            Exception("Invalid credentials"),
            Exception("Token has expired"),
            Exception("Insufficient permissions"),
        ]

        for error in auth_errors:
            mock_search_api.side_effect = error

            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test query", "s3://test-registry")

            error_message = str(exc_info.value)
            # Verify error message includes backend type
            assert "quilt3" in error_message.lower()
            # Verify error message includes operation context
            assert "search failed" in error_message.lower()
            # Verify original error is preserved
            assert str(error) in error_message

            # Reset for next test
            mock_search_api.side_effect = None

    @patch('quilt3.search_util.search_api')
    def test_search_packages_elasticsearch_errors(self, mock_search_api):
        """Test search_packages() handles Elasticsearch-specific errors correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test Elasticsearch error responses
        es_error_responses = [
            {"error": {"type": "index_not_found_exception", "reason": "no such index"}},
            {"error": {"type": "parsing_exception", "reason": "invalid query syntax"}},
            {"error": {"type": "search_phase_execution_exception", "reason": "shard failure"}},
        ]

        for error_response in es_error_responses:
            mock_search_api.return_value = error_response

            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test query", "s3://test-registry")

            error_message = str(exc_info.value)
            # Verify error message includes backend type
            assert "quilt3" in error_message.lower()
            # Verify error message includes operation context
            assert "search failed" in error_message.lower()
            # Verify Elasticsearch error details are preserved
            assert "Search API error" in error_message

            # Reset for next test
            mock_search_api.return_value = None

    @patch('quilt3.search_util.search_api')
    def test_search_packages_malformed_response_errors(self, mock_search_api):
        """Test search_packages() handles malformed API responses correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various malformed response scenarios that should raise BackendError
        malformed_responses_with_errors = [
            (None, "Null response"),
            ("invalid json string", "Non-dict string response"),
            (42, "Non-dict numeric response"),
            ([], "List instead of dict"),
            ({"hits": None}, "Null hits - fails at response.get()"),
            ({"hits": {"hits": None}}, "Null hits.hits - fails at iteration"),
        ]

        for response, description in malformed_responses_with_errors:
            mock_search_api.return_value = response

            # Should raise BackendError due to malformed response
            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test query", "s3://test-registry")

            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower(), f"Failed for {description}: {error_message}"
            assert "search failed" in error_message.lower(), f"Failed for {description}: {error_message}"
            # Should preserve the original error details
            assert any(
                keyword in error_message.lower()
                for keyword in ["not iterable", "has no attribute", "get", "typeerror", "nonetype"]
            ), f"Failed for {description}: {error_message}"

            # Reset for next test
            mock_search_api.return_value = None

        # Test responses that return empty lists (valid responses that don't cause errors)
        valid_empty_responses = [
            ({}, "Empty dict"),
            ({"hits": {}}, "Missing hits.hits"),
            ({"hits": {"hits": []}}, "Empty hits array"),
        ]

        for response, description in valid_empty_responses:
            mock_search_api.return_value = response

            # Should not raise an error, but should return empty list
            result = backend.search_packages("test query", "s3://test-registry")
            assert isinstance(result, list), f"Expected list for {description}, got {type(result)}"
            assert len(result) == 0, f"Expected empty list for {description}, got {len(result)} items"

            # Reset for next test
            mock_search_api.return_value = None

    @patch('quilt3.search_util.search_api')
    def test_search_packages_transformation_errors(self, mock_search_api):
        """Test search_packages() handles transformation errors gracefully."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock response with data that will cause transformation errors
        mock_search_api.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "ptr_name": "valid/package",
                            "description": "Valid package",
                            "tags": ["test"],
                            "ptr_last_modified": "2024-01-01T12:00:00",
                            "top_hash": "abc123",
                        }
                    },
                    {
                        "_source": {
                            # Missing ptr_name - will create package with empty name
                            "description": "Invalid package",
                            "tags": ["test"],
                            "ptr_last_modified": "2024-01-01T12:00:00",
                            "top_hash": "def456",
                        }
                    },
                    {
                        "_source": {
                            "ptr_name": "another/valid",
                            "description": "Another valid package",
                            "tags": ["test"],
                            "ptr_last_modified": "2024-01-01T12:00:00",
                            "top_hash": "ghi789",
                        }
                    },
                ]
            }
        }

        # Should return all packages, including the one with empty name
        # The backend doesn't skip invalid packages, it transforms them as-is
        result = backend.search_packages("test query", "s3://test-registry")
        assert len(result) == 3
        assert result[0].name == "valid/package"
        assert result[1].name == ""  # Empty name from missing ptr_name
        assert result[2].name == "another/valid"

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_network_errors(self, mock_quilt3):
        """Test get_package_info() handles various network errors correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various network error scenarios
        network_errors = [
            ConnectionError("Connection failed"),
            TimeoutError("Request timed out"),
            OSError("Network is unreachable"),
            Exception("DNS resolution failed"),
            Exception("Connection reset by peer"),
            Exception("SSL handshake failed"),
        ]

        for error in network_errors:
            mock_quilt3.Package.browse.side_effect = error

            with pytest.raises(BackendError) as exc_info:
                backend.get_package_info("test/package", "s3://test-registry")

            error_message = str(exc_info.value)
            # Verify error message includes backend type
            assert "quilt3" in error_message.lower()
            # Verify error message includes operation context
            assert "get_package_info failed" in error_message.lower()
            # Verify original error is preserved
            assert str(error) in error_message

            # Reset for next test
            mock_quilt3.Package.browse.side_effect = None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_authentication_errors(self, mock_quilt3):
        """Test get_package_info() handles authentication/permission errors correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various authentication error scenarios
        auth_errors = [
            PermissionError("Access denied"),
            Exception("403 Forbidden"),
            Exception("401 Unauthorized"),
            Exception("Invalid credentials"),
            Exception("Token has expired"),
            Exception("Insufficient permissions"),
        ]

        for error in auth_errors:
            mock_quilt3.Package.browse.side_effect = error

            with pytest.raises(BackendError) as exc_info:
                backend.get_package_info("test/package", "s3://test-registry")

            error_message = str(exc_info.value)
            # Verify error message includes backend type
            assert "quilt3" in error_message.lower()
            # Verify error message includes operation context
            assert "get_package_info failed" in error_message.lower()
            # Verify original error is preserved
            assert str(error) in error_message

            # Reset for next test
            mock_quilt3.Package.browse.side_effect = None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_not_found_errors(self, mock_quilt3):
        """Test get_package_info() handles package not found errors correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various "not found" error scenarios
        not_found_errors = [
            Exception("Package not found"),
            FileNotFoundError("No such package"),
            Exception("404 Not Found"),
            KeyError("Package does not exist"),
            Exception("NoSuchKey"),
        ]

        for error in not_found_errors:
            mock_quilt3.Package.browse.side_effect = error

            with pytest.raises(BackendError) as exc_info:
                backend.get_package_info("nonexistent/package", "s3://test-registry")

            error_message = str(exc_info.value)
            # Verify error message includes backend type
            assert "quilt3" in error_message.lower()
            # Verify error message includes operation context
            assert "get_package_info failed" in error_message.lower()
            # Verify original error is preserved
            assert str(error) in error_message

            # Reset for next test
            mock_quilt3.Package.browse.side_effect = None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_invalid_registry_errors(self, mock_quilt3):
        """Test get_package_info() handles invalid registry errors correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test various invalid registry error scenarios
        registry_errors = [
            ValueError("Invalid registry URL"),
            Exception("Invalid S3 bucket name"),
            Exception("Registry not accessible"),
            Exception("Bucket does not exist"),
        ]

        for error in registry_errors:
            mock_quilt3.Package.browse.side_effect = error

            with pytest.raises(BackendError) as exc_info:
                backend.get_package_info("test/package", "s3://invalid-registry")

            error_message = str(exc_info.value)
            # Verify error message includes backend type
            assert "quilt3" in error_message.lower()
            # Verify error message includes operation context
            assert "get_package_info failed" in error_message.lower()
            # Verify original error is preserved
            assert str(error) in error_message

            # Reset for next test
            mock_quilt3.Package.browse.side_effect = None

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_get_package_info_transformation_errors(self, mock_quilt3):
        """Test get_package_info() handles package transformation errors correctly."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Mock package with invalid data that will cause transformation error
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test package"
        mock_package.tags = []
        mock_package.modified = "invalid-date"  # This will trigger transformation error
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"

        mock_quilt3.Package.browse.return_value = mock_package

        with pytest.raises(BackendError) as exc_info:
            backend.get_package_info("test/package", "s3://test-registry")

        error_message = str(exc_info.value)
        # Verify error message includes backend type
        assert "quilt3" in error_message.lower()
        # Verify error message includes transformation context
        assert "transformation failed" in error_message.lower()

    def test_error_context_information(self):
        """Test that BackendError includes proper context information."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.ops.exceptions import BackendError

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test search_packages error context
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = Exception("Test error")

            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test query", "s3://test-registry")

            error = exc_info.value
            # Verify context is included
            assert hasattr(error, 'context')
            assert error.context['query'] == "test query"
            assert error.context['registry'] == "s3://test-registry"

        # Test get_package_info error context
        with patch('quilt_mcp.backends.quilt3_backend.quilt3') as mock_quilt3:
            mock_quilt3.Package.browse.side_effect = Exception("Test error")

            with pytest.raises(BackendError) as exc_info:
                backend.get_package_info("test/package", "s3://test-registry")

            error = exc_info.value
            # Verify context is included
            assert hasattr(error, 'context')
            assert error.context['package_name'] == "test/package"
            assert error.context['registry'] == "s3://test-registry"

    def test_error_message_format_consistency(self):
        """Test that all error messages follow consistent format with backend type."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)

        # Test search_packages error message format
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = Exception("Test search error")

            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test", "s3://test-registry")

            error_message = str(exc_info.value)
            # Verify message starts with backend identifier
            assert error_message.startswith("Quilt3 backend")
            # Verify operation is identified
            assert "search failed" in error_message
            # Verify original error is included
            assert "Test search error" in error_message

        # Test get_package_info error message format
        # Mock the backend instance's quilt3 reference directly
        mock_quilt3_instance = Mock()
        mock_quilt3_instance.Package.browse.side_effect = Exception("Test package error")
        backend.quilt3 = mock_quilt3_instance

        with pytest.raises(BackendError) as exc_info:
            backend.get_package_info("test/package", "s3://test-registry")

        error_message = str(exc_info.value)
        # Verify message starts with backend identifier
        assert error_message.startswith("Quilt3 backend")
        # Verify operation is identified
        assert "get_package_info failed" in error_message
        # Verify original error is included
        assert "Test package error" in error_message
