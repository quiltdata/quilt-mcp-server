"""
Tests for Quilt3_Backend implementation.

This module tests the concrete implementation of QuiltOps using the quilt3 library.
All quilt3 library calls are mocked to ensure tests are isolated and fast.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List, Optional

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError
from quilt_mcp.domain.package_info import Package_Info
from quilt_mcp.domain.content_info import Content_Info
from quilt_mcp.domain.bucket_info import Bucket_Info


class TestQuilt3BackendStructure:
    """Test the basic structure and initialization of Quilt3_Backend."""
    
    def test_quilt3_backend_can_be_imported(self):
        """Test that Quilt3_Backend can be imported from the backends module."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        assert Quilt3_Backend is not None
    
    def test_quilt3_backend_implements_quilt_ops(self):
        """Test that Quilt3_Backend implements the QuiltOps interface."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        assert issubclass(Quilt3_Backend, QuiltOps)
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_quilt3_backend_initialization_with_valid_session(self, mock_quilt3):
        """Test that Quilt3_Backend initializes correctly with a valid session."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        # Mock valid session
        mock_session_config = {
            'registry': 's3://test-registry',
            'credentials': {'access_key': 'test', 'secret_key': 'test'}
        }
        
        backend = Quilt3_Backend(mock_session_config)
        assert backend is not None
        assert hasattr(backend, 'session')
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_quilt3_backend_initialization_with_invalid_session(self, mock_quilt3):
        """Test that Quilt3_Backend raises AuthenticationError with invalid session."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        # Mock invalid session
        invalid_session = None
        
        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend(invalid_session)
        
        assert "session" in str(exc_info.value).lower()
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_quilt3_backend_session_validation(self, mock_quilt3):
        """Test that Quilt3_Backend validates session configuration."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        # Mock session validation failure
        mock_quilt3.session.get_session_info.side_effect = Exception("Invalid session")
        
        with pytest.raises(AuthenticationError):
            Quilt3_Backend({'invalid': 'config'})


class TestQuilt3BackendPackageOperations:
    """Test package-related operations in Quilt3_Backend."""
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_search_packages_with_mocked_quilt3_search(self, mock_quilt3):
        """Test search_packages() with mocked quilt3.search() calls."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        # Setup mock
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Mock quilt3.search response
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.description = "Test package"
        mock_package.tags = ["test", "data"]
        mock_package.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"
        
    @patch('quilt3.search_util.search_api')
    def test_search_packages_with_mocked_quilt3_search(self, mock_search_api):
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
                            "top_hash": "abc123"
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
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
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
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_get_package_info_error_handling(self, mock_quilt3):
        """Test get_package_info() error handling."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Mock package loading to raise exception
        mock_quilt3.Package.browse.side_effect = Exception("Package not found")
        
        with pytest.raises(BackendError):
            backend.get_package_info("nonexistent/package", "s3://test-registry")


class TestQuilt3BackendPackageTransformation:
    """Test package transformation methods in isolation."""
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
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
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
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
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_package_error_handling(self, mock_quilt3):
        """Test _transform_package() error handling in transformation logic."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Create mock package that will cause transformation error
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.modified = "invalid-date"  # Invalid date format
        
        with pytest.raises(BackendError):
            backend._transform_package(mock_package)


class TestQuilt3BackendContentOperations:
    """Test content browsing and URL generation operations."""
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_browse_content_with_mocked_package_browsing(self, mock_quilt3):
        """Test browse_content() with mocked quilt3 package browsing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Mock package and content
        mock_package = Mock()
        mock_entry = Mock()
        mock_entry.name = "data.csv"
        mock_entry.size = 1024
        mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry.is_dir = False
        
        mock_package.__iter__ = Mock(return_value=iter([mock_entry]))
        mock_quilt3.Package.browse.return_value = mock_package
        
        # Execute
        result = backend.browse_content("test/package", "s3://test-registry", "")
        
        # Verify
        assert len(result) == 1
        assert isinstance(result[0], Content_Info)
        assert result[0].path == "data.csv"
        assert result[0].size == 1024
        assert result[0].type == "file"
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_browse_content_directory_vs_file_detection(self, mock_quilt3):
        """Test browse_content() correctly detects directories vs files."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Mock directory and file entries
        mock_dir = Mock()
        mock_dir.name = "folder/"
        mock_dir.is_dir = True
        mock_dir.size = None
        
        mock_file = Mock()
        mock_file.name = "file.txt"
        mock_file.is_dir = False
        mock_file.size = 512
        
        mock_package = Mock()
        mock_package.__iter__ = Mock(return_value=iter([mock_dir, mock_file]))
        mock_quilt3.Package.browse.return_value = mock_package
        
        # Execute
        result = backend.browse_content("test/package", "s3://test-registry", "")
        
        # Verify
        assert len(result) == 2
        dir_result = next(r for r in result if r.path == "folder/")
        file_result = next(r for r in result if r.path == "file.txt")
        
        assert dir_result.type == "directory"
        assert dir_result.size is None
        assert file_result.type == "file"
        assert file_result.size == 512
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_get_content_url_with_mocked_url_generation(self, mock_quilt3):
        """Test get_content_url() with mocked quilt3 URL generation."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Mock URL generation
        expected_url = "https://s3.amazonaws.com/test-bucket/test-package/data.csv?signature=abc123"
        mock_package = Mock()
        mock_package.get_url.return_value = expected_url
        mock_quilt3.Package.browse.return_value = mock_package
        
        # Execute
        result = backend.get_content_url("test/package", "s3://test-registry", "data.csv")
        
        # Verify
        assert result == expected_url
        mock_package.get_url.assert_called_once_with("data.csv")


class TestQuilt3BackendContentTransformation:
    """Test content transformation methods in isolation."""
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_content_with_complete_entry(self, mock_quilt3):
        """Test _transform_content() method with complete quilt3 content object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Create mock content entry
        mock_entry = Mock()
        mock_entry.name = "data/file.csv"
        mock_entry.size = 2048
        mock_entry.modified = datetime(2024, 1, 1, 12, 0, 0)
        mock_entry.is_dir = False
        
        # Execute transformation
        result = backend._transform_content(mock_entry)
        
        # Verify
        assert isinstance(result, Content_Info)
        assert result.path == "data/file.csv"
        assert result.size == 2048
        assert result.type == "file"
        assert result.modified_date == "2024-01-01T12:00:00"
        assert result.download_url is None  # URL not provided in transformation
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_content_with_missing_fields(self, mock_quilt3):
        """Test _transform_content() handles missing/null fields in quilt3 objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Create mock content entry with missing fields
        mock_entry = Mock()
        mock_entry.name = "folder/"
        mock_entry.size = None
        mock_entry.modified = None
        mock_entry.is_dir = True
        
        # Execute transformation
        result = backend._transform_content(mock_entry)
        
        # Verify
        assert result.path == "folder/"
        assert result.size is None
        assert result.type == "directory"
        assert result.modified_date is None
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_content_error_handling(self, mock_quilt3):
        """Test _transform_content() error handling in transformation logic."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Create mock entry that will cause transformation error
        mock_entry = Mock()
        mock_entry.name = None  # Invalid name
        
        with pytest.raises(BackendError):
            backend._transform_content(mock_entry)


class TestQuilt3BackendBucketOperations:
    """Test bucket listing operations."""
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_with_mocked_quilt3_calls(self, mock_quilt3):
        """Test list_buckets() with mocked quilt3 calls."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Mock bucket listing response
        mock_bucket_data = {
            'test-bucket-1': {
                'region': 'us-east-1',
                'access_level': 'read-write',
                'created_date': '2024-01-01T00:00:00Z'
            },
            'test-bucket-2': {
                'region': 'us-west-2',
                'access_level': 'read-only',
                'created_date': '2024-01-02T00:00:00Z'
            }
        }
        
        mock_quilt3.list_buckets.return_value = mock_bucket_data
        
        # Execute
        result = backend.list_buckets()
        
        # Verify
        assert len(result) == 2
        assert all(isinstance(bucket, Bucket_Info) for bucket in result)
        
        bucket1 = next(b for b in result if b.name == 'test-bucket-1')
        assert bucket1.region == 'us-east-1'
        assert bucket1.access_level == 'read-write'
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_list_buckets_bucket_metadata_extraction(self, mock_quilt3):
        """Test list_buckets() bucket metadata extraction."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Mock minimal bucket data
        mock_bucket_data = {
            'minimal-bucket': {
                'region': 'eu-west-1',
                'access_level': 'admin'
            }
        }
        
        mock_quilt3.list_buckets.return_value = mock_bucket_data
        
        # Execute
        result = backend.list_buckets()
        
        # Verify
        assert len(result) == 1
        bucket = result[0]
        assert bucket.name == 'minimal-bucket'
        assert bucket.region == 'eu-west-1'
        assert bucket.access_level == 'admin'
        assert bucket.created_date is None  # Not provided


class TestQuilt3BackendBucketTransformation:
    """Test bucket transformation methods in isolation."""
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_complete_data(self, mock_quilt3):
        """Test _transform_bucket() method with complete quilt3 bucket object."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Create complete bucket data
        bucket_name = "test-bucket"
        bucket_data = {
            'region': 'us-east-1',
            'access_level': 'read-write',
            'created_date': '2024-01-01T00:00:00Z'
        }
        
        # Execute transformation
        result = backend._transform_bucket(bucket_name, bucket_data)
        
        # Verify
        assert isinstance(result, Bucket_Info)
        assert result.name == "test-bucket"
        assert result.region == "us-east-1"
        assert result.access_level == "read-write"
        assert result.created_date == "2024-01-01T00:00:00Z"
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_with_missing_fields(self, mock_quilt3):
        """Test _transform_bucket() handles missing/null fields in quilt3 objects."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Create minimal bucket data
        bucket_name = "minimal-bucket"
        bucket_data = {
            'region': 'us-west-2',
            'access_level': 'read-only'
            # created_date missing
        }
        
        # Execute transformation
        result = backend._transform_bucket(bucket_name, bucket_data)
        
        # Verify
        assert result.name == "minimal-bucket"
        assert result.region == "us-west-2"
        assert result.access_level == "read-only"
        assert result.created_date is None
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_transform_bucket_error_handling(self, mock_quilt3):
        """Test _transform_bucket() error handling in transformation logic."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Create invalid bucket data
        bucket_name = None  # Invalid name
        bucket_data = {'region': 'us-east-1'}
        
        with pytest.raises(BackendError):
            backend._transform_bucket(bucket_name, bucket_data)


class TestQuilt3BackendErrorHandling:
    """Test comprehensive error handling across all operations."""
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_backend_operation_error_handling(self, mock_quilt3):
        """Test that backend operations are wrapped with error handling."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test each operation raises BackendError on quilt3 exceptions
        operations = [
            (lambda: backend.search_packages("test", "registry"), mock_quilt3.search),
            (lambda: backend.get_package_info("pkg", "registry"), mock_quilt3.Package.browse),
            (lambda: backend.browse_content("pkg", "registry"), mock_quilt3.Package.browse),
            (lambda: backend.get_content_url("pkg", "registry", "path"), mock_quilt3.Package.browse),
            (lambda: backend.list_buckets(), mock_quilt3.list_buckets),
        ]
        
        for operation, mock_method in operations:
            mock_method.side_effect = Exception("Quilt3 error")
            
            with pytest.raises(BackendError) as exc_info:
                operation()
            
            assert "quilt3" in str(exc_info.value).lower()
            mock_method.side_effect = None  # Reset for next test
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_error_messages_include_backend_type(self, mock_quilt3):
        """Test that error messages include backend type for debugging."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        mock_quilt3.search.side_effect = Exception("Network timeout")
        
        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("test", "registry")
        
        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "backend" in error_message.lower()
    
    @patch('quilt3.search_util.search_api')
    def test_backend_specific_error_transformation(self, mock_search_api):
        """Test that backend-specific errors are transformed to domain errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test authentication-related errors
        mock_search_api.side_effect = Exception("Access denied")
        
        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("test", "registry")
        
        # Should be wrapped as BackendError, not AuthenticationError
        # (AuthenticationError is for session validation only)
        assert isinstance(exc_info.value, BackendError)
        assert "access denied" in str(exc_info.value).lower()


class TestQuilt3BackendIntegration:
    """Test integration scenarios and complete workflows."""
    
    @patch('quilt3.search_util.search_api')
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_complete_package_workflow(self, mock_quilt3, mock_search_api):
        """Test complete workflow: search -> get_info -> browse_content -> get_url."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
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
                            "tags": ["test"],
                            "ptr_last_modified": "2024-01-01T00:00:00",  # Last modified is in ptr_last_modified
                            "top_hash": "abc123"
                        }
                    }
                ]
            }
        }
        
        # Mock package info - create a separate mock for get_package_info
        mock_info_package = Mock()
        mock_info_package.name = "test/package"
        mock_info_package.description = "Detailed description"
        mock_info_package.tags = ["test", "detailed"]
        mock_info_package.modified = datetime(2024, 1, 1)
        mock_info_package.registry = "s3://test-registry"
        mock_info_package.bucket = "test-bucket"
        mock_info_package.top_hash = "abc123"
        
        # Mock content browsing
        mock_content_entry = Mock()
        mock_content_entry.name = "data.csv"
        mock_content_entry.size = 1024
        mock_content_entry.modified = datetime(2024, 1, 1)
        mock_content_entry.is_dir = False
        
        mock_browse_package = Mock()
        mock_browse_package.__iter__ = Mock(return_value=iter([mock_content_entry]))
        mock_browse_package.get_url.return_value = "https://example.com/data.csv"
        
        # Configure mocks for different calls
        # First call to Package.browse returns info package, second returns browse package
        mock_quilt3.Package.browse.side_effect = [mock_info_package, mock_browse_package, mock_browse_package]
        
        # Execute complete workflow
        search_results = backend.search_packages("test", "s3://test-registry")
        package_info = backend.get_package_info("test/package", "s3://test-registry")
        content_list = backend.browse_content("test/package", "s3://test-registry")
        content_url = backend.get_content_url("test/package", "s3://test-registry", "data.csv")
        
        # Verify workflow results
        assert len(search_results) == 1
        assert search_results[0].name == "test/package"
        
        assert package_info.name == "test/package"
        
        assert len(content_list) == 1
        assert content_list[0].path == "data.csv"
        
        assert content_url == "https://example.com/data.csv"
    
    @patch('quilt3.search_util.search_api')
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_error_propagation_through_workflow(self, mock_quilt3, mock_search_api):
        """Test that errors propagate correctly through workflow steps."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test error in each step
        mock_search_api.side_effect = Exception("Search failed")
        
        with pytest.raises(BackendError):
            backend.search_packages("test", "registry")
        
        # Reset and test next step
        mock_search_api.side_effect = None
        mock_quilt3.Package.browse.side_effect = Exception("Browse failed")
        
        with pytest.raises(BackendError):
            backend.get_package_info("test/package", "registry")
        
        with pytest.raises(BackendError):
            backend.browse_content("test/package", "registry")
        
        with pytest.raises(BackendError):
            backend.get_content_url("test/package", "registry", "path")