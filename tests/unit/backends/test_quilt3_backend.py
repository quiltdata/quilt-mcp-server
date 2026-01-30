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
    
    def test_quilt3_backend_implements_all_abstract_methods(self):
        """Test that Quilt3_Backend implements all required QuiltOps abstract methods."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        from quilt_mcp.ops.quilt_ops import QuiltOps
        
        # Get all abstract methods from QuiltOps
        abstract_methods = {name for name, method in QuiltOps.__dict__.items() 
                          if getattr(method, '__isabstractmethod__', False)}
        
        # Check that Quilt3_Backend implements all abstract methods
        backend_methods = set(dir(Quilt3_Backend))
        
        for method_name in abstract_methods:
            assert method_name in backend_methods, f"Missing implementation of abstract method: {method_name}"
            # Verify the method is callable
            assert callable(getattr(Quilt3_Backend, method_name))
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_quilt3_backend_initialization_with_valid_session(self, mock_quilt3):
        """Test that Quilt3_Backend initializes correctly with a valid session."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        # Mock valid session
        mock_session_config = {
            'registry': 's3://test-registry',
            'credentials': {'access_key': 'test', 'secret_key': 'test'}
        }
        
        # Mock successful session validation
        mock_quilt3.session.get_session_info.return_value = mock_session_config
        
        backend = Quilt3_Backend(mock_session_config)
        assert backend is not None
        assert hasattr(backend, 'session')
        assert backend.session == mock_session_config
        
        # Verify session validation was called
        mock_quilt3.session.get_session_info.assert_called_once()
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_quilt3_backend_initialization_with_empty_session(self, mock_quilt3):
        """Test that Quilt3_Backend raises AuthenticationError with empty session."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        # Test with None
        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend(None)
        assert "session configuration is empty" in str(exc_info.value)
        
        # Test with empty dict
        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend({})
        assert "session configuration is empty" in str(exc_info.value)
        
        # Test with empty string
        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend("")
        assert "session configuration is empty" in str(exc_info.value)
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3', None)
    def test_quilt3_backend_initialization_without_quilt3_library(self):
        """Test that Quilt3_Backend raises AuthenticationError when quilt3 library is not available."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session_config = {'registry': 's3://test-registry'}
        
        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend(mock_session_config)
        
        assert "quilt3 library is not available" in str(exc_info.value)
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_quilt3_backend_session_validation_success(self, mock_quilt3):
        """Test successful session validation with various session configurations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        # Test with minimal valid session
        minimal_session = {'registry': 's3://test-registry'}
        mock_quilt3.session.get_session_info.return_value = minimal_session
        
        backend = Quilt3_Backend(minimal_session)
        assert backend.session == minimal_session
        
        # Test with comprehensive session config
        comprehensive_session = {
            'registry': 's3://test-registry',
            'credentials': {'access_key': 'test', 'secret_key': 'test'},
            'region': 'us-east-1',
            'profile': 'default'
        }
        mock_quilt3.session.get_session_info.return_value = comprehensive_session
        
        backend = Quilt3_Backend(comprehensive_session)
        assert backend.session == comprehensive_session
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_quilt3_backend_session_validation_failure(self, mock_quilt3):
        """Test session validation failure scenarios."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        # Test with session validation exception
        mock_quilt3.session.get_session_info.side_effect = Exception("Invalid credentials")
        
        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend({'invalid': 'config'})
        
        assert "Invalid quilt3 session: Invalid credentials" in str(exc_info.value)
        
        # Test with permission denied
        mock_quilt3.session.get_session_info.side_effect = PermissionError("Access denied")
        
        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend({'registry': 's3://test-registry'})
        
        assert "Invalid quilt3 session: Access denied" in str(exc_info.value)
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_quilt3_backend_session_validation_without_get_session_info(self, mock_quilt3):
        """Test session validation when get_session_info method is not available."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        # Mock quilt3.session without get_session_info method
        mock_session = Mock()
        del mock_session.get_session_info  # Remove the method
        mock_quilt3.session = mock_session
        
        # Should still initialize successfully if session config is provided
        session_config = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(session_config)
        assert backend.session == session_config
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_quilt3_backend_initialization_logging(self, mock_quilt3):
        """Test that initialization success is properly logged."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import logging
        
        # Mock session validation
        mock_session_config = {'registry': 's3://test-registry'}
        mock_quilt3.session.get_session_info.return_value = mock_session_config
        
        # Capture log messages
        with patch('quilt_mcp.backends.quilt3_backend.logger') as mock_logger:
            backend = Quilt3_Backend(mock_session_config)
            
            # Verify success logging
            mock_logger.info.assert_called_with("Quilt3_Backend initialized successfully")
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_quilt3_backend_initialization_preserves_session_config(self, mock_quilt3):
        """Test that initialization preserves the original session configuration."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        original_config = {
            'registry': 's3://test-registry',
            'credentials': {'access_key': 'test', 'secret_key': 'test'},
            'metadata': {'user': 'test_user', 'environment': 'test'}
        }
        
        # Mock successful validation
        mock_quilt3.session.get_session_info.return_value = original_config
        
        backend = Quilt3_Backend(original_config)
        
        # Verify the session config is preserved exactly
        assert backend.session == original_config
        
        # Verify nested structures are preserved
        assert backend.session['credentials']['access_key'] == 'test'
        assert backend.session['metadata']['user'] == 'test_user'


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


class TestQuilt3BackendSessionValidation:
    """Test comprehensive session validation scenarios."""
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_session_validation_with_corrupted_session_data(self, mock_quilt3):
        """Test session validation with corrupted session data."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        # Test with corrupted session data that causes validation to fail
        corrupted_sessions = [
            {'registry': 'invalid-uri-format'},
            {'credentials': 'not-a-dict'},
            {'registry': 's3://test', 'credentials': {'malformed': True}},
            {'registry': None},
            {'registry': ''},
        ]
        
        for corrupted_session in corrupted_sessions:
            mock_quilt3.session.get_session_info.side_effect = ValueError("Corrupted session data")
            
            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(corrupted_session)
            
            assert "Invalid quilt3 session" in str(exc_info.value)
            assert "Corrupted session data" in str(exc_info.value)
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_session_validation_with_expired_credentials(self, mock_quilt3):
        """Test session validation with expired credentials."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        expired_session = {
            'registry': 's3://test-registry',
            'credentials': {'access_key': 'expired', 'secret_key': 'expired'}
        }
        
        # Mock expired credentials error
        mock_quilt3.session.get_session_info.side_effect = Exception("Token has expired")
        
        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend(expired_session)
        
        assert "Invalid quilt3 session" in str(exc_info.value)
        assert "Token has expired" in str(exc_info.value)
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_session_validation_with_network_errors(self, mock_quilt3):
        """Test session validation with network connectivity issues."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import socket
        
        session_config = {'registry': 's3://test-registry'}
        
        # Test various network-related errors
        network_errors = [
            socket.timeout("Connection timeout"),
            ConnectionError("Network unreachable"),
            OSError("Name resolution failed"),
        ]
        
        for network_error in network_errors:
            mock_quilt3.session.get_session_info.side_effect = network_error
            
            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(session_config)
            
            assert "Invalid quilt3 session" in str(exc_info.value)
            assert str(network_error) in str(exc_info.value)
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_session_validation_with_permission_errors(self, mock_quilt3):
        """Test session validation with various permission-related errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        session_config = {'registry': 's3://restricted-registry'}
        
        # Test various permission errors
        permission_errors = [
            PermissionError("Access denied to registry"),
            Exception("Forbidden: Insufficient permissions"),
            Exception("403 Forbidden"),
            Exception("UnauthorizedOperation"),
        ]
        
        for permission_error in permission_errors:
            mock_quilt3.session.get_session_info.side_effect = permission_error
            
            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(session_config)
            
            assert "Invalid quilt3 session" in str(exc_info.value)
            assert str(permission_error) in str(exc_info.value)
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_session_validation_error_message_clarity(self, mock_quilt3):
        """Test that session validation errors provide clear, actionable messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        session_config = {'registry': 's3://test-registry'}
        mock_quilt3.session.get_session_info.side_effect = Exception("Invalid API key")
        
        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend(session_config)
        
        error_message = str(exc_info.value)
        
        # Verify error message contains helpful information
        assert "Invalid quilt3 session" in error_message
        assert "Invalid API key" in error_message
        
        # Should provide context about what went wrong
        assert any(keyword in error_message.lower() for keyword in [
            "session", "authentication", "credentials", "login"
        ])
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_session_validation_with_malformed_registry_urls(self, mock_quilt3):
        """Test session validation with malformed registry URLs."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        malformed_registries = [
            {'registry': 'not-a-url'},
            {'registry': 'http://insecure-registry'},  # Should be s3://
            {'registry': 's3://'},  # Missing bucket name
            {'registry': 's3://bucket/with/path'},  # Invalid format
            {'registry': 'ftp://wrong-protocol'},
        ]
        
        for malformed_config in malformed_registries:
            mock_quilt3.session.get_session_info.side_effect = ValueError("Invalid registry URL")
            
            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(malformed_config)
            
            assert "Invalid quilt3 session" in str(exc_info.value)
            assert "Invalid registry URL" in str(exc_info.value)
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_session_validation_edge_cases(self, mock_quilt3):
        """Test session validation edge cases and boundary conditions."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        # Test with very large session config
        large_session = {
            'registry': 's3://test-registry',
            'metadata': {'key' + str(i): 'value' + str(i) for i in range(1000)}
        }
        mock_quilt3.session.get_session_info.return_value = large_session
        
        # Should handle large configs without issues
        backend = Quilt3_Backend(large_session)
        assert backend.session == large_session
        
        # Test with unicode characters in session
        unicode_session = {
            'registry': 's3://test-registry',
            'user': 'üser_nämé',
            'description': '测试用户'
        }
        mock_quilt3.session.get_session_info.return_value = unicode_session
        
        backend = Quilt3_Backend(unicode_session)
        assert backend.session == unicode_session
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_session_validation_with_timeout_scenarios(self, mock_quilt3):
        """Test session validation with various timeout scenarios."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import socket
        
        session_config = {'registry': 's3://test-registry'}
        
        # Test different timeout scenarios
        timeout_errors = [
            socket.timeout("Connection timed out"),
            TimeoutError("Operation timed out"),
            Exception("Read timeout"),
            Exception("Connection timeout after 30 seconds"),
        ]
        
        for timeout_error in timeout_errors:
            mock_quilt3.session.get_session_info.side_effect = timeout_error
            
            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(session_config)
            
            assert "Invalid quilt3 session" in str(exc_info.value)
            assert any(keyword in str(exc_info.value).lower() for keyword in ["timeout", "timed out"])
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_session_validation_with_ssl_errors(self, mock_quilt3):
        """Test session validation with SSL/TLS related errors."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import ssl
        
        session_config = {'registry': 's3://test-registry'}
        
        # Test SSL-related errors
        ssl_errors = [
            ssl.SSLError("SSL certificate verification failed"),
            ssl.SSLCertVerificationError("Certificate verification failed"),
            Exception("SSL: CERTIFICATE_VERIFY_FAILED"),
            Exception("SSL handshake failed"),
        ]
        
        for ssl_error in ssl_errors:
            mock_quilt3.session.get_session_info.side_effect = ssl_error
            
            with pytest.raises(AuthenticationError) as exc_info:
                Quilt3_Backend(session_config)
            
            assert "Invalid quilt3 session" in str(exc_info.value)
            assert any(keyword in str(exc_info.value).lower() for keyword in ["ssl", "certificate", "handshake"])


class TestQuilt3BackendAdvancedErrorHandling:
    """Test advanced error handling scenarios and edge cases."""
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_error_handling_with_nested_exceptions(self, mock_quilt3):
        """Test error handling with nested exception chains."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Create nested exception
        root_cause = ValueError("Invalid parameter")
        wrapper_exception = Exception("Operation failed")
        wrapper_exception.__cause__ = root_cause
        
        # Mock the search_api directly since that's what the backend uses
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = wrapper_exception
            
            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test", "s3://test-registry")
            
            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "search failed" in error_message.lower()
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_error_handling_with_unicode_error_messages(self, mock_quilt3):
        """Test error handling with unicode characters in error messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test with unicode error message
        unicode_error = Exception("错误: 无法连接到服务器")
        
        # Mock the search_api directly since that's what the backend uses
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = unicode_error
            
            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test", "s3://test-registry")
            
            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "search failed" in error_message.lower()
            # The unicode characters should be preserved in the error message
            assert "错误" in error_message
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_error_propagation_preserves_original_context(self, mock_quilt3):
        """Test that error propagation preserves original error context."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test with detailed error context
        detailed_error = Exception("HTTP 404: Package 'test/package' not found in registry 's3://test-registry'")
        mock_quilt3.Package.browse.side_effect = detailed_error
        
        with pytest.raises(BackendError) as exc_info:
            backend.get_package_info("test/package", "s3://test-registry")
        
        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "404" in error_message
        assert "test/package" in error_message
        assert "s3://test-registry" in error_message
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_error_handling_with_empty_error_messages(self, mock_quilt3):
        """Test error handling when underlying errors have empty messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test with empty error message
        empty_error = Exception("")
        mock_quilt3.search.side_effect = empty_error
        
        with pytest.raises(BackendError) as exc_info:
            backend.search_packages("test", "registry")
        
        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "backend" in error_message.lower()
        # Should still provide meaningful context even with empty underlying message
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_error_handling_with_very_long_error_messages(self, mock_quilt3):
        """Test error handling with very long error messages."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Create very long error message
        long_message = "Error: " + "A" * 10000 + " - operation failed"
        long_error = Exception(long_message)
        
        # Mock the search_api directly since that's what the backend uses
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = long_error
            
            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test", "s3://test-registry")
            
            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "search failed" in error_message.lower()
            # Should handle long messages without truncation issues
            # The original long message should be preserved in the error
            assert len(error_message) > 100  # Should preserve substantial portion of the long message
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_concurrent_error_handling(self, mock_quilt3):
        """Test error handling in concurrent operation scenarios."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import threading
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Mock different errors for concurrent calls
        errors = [
            Exception("Error 1"),
            Exception("Error 2"),
            Exception("Error 3"),
        ]
        
        mock_quilt3.search.side_effect = errors
        
        results = []
        
        def call_backend():
            try:
                backend.search_packages("test", "registry")
            except BackendError as e:
                results.append(str(e))
        
        # Create multiple threads
        threads = [threading.Thread(target=call_backend) for _ in range(3)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all errors were handled properly
        assert len(results) == 3
        for result in results:
            assert "quilt3" in result.lower()


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
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_authentication_error_scenarios_during_operations(self, mock_quilt3):
        """Test authentication-related errors during backend operations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test various authentication errors during operations
        auth_errors = [
            Exception("401 Unauthorized"),
            Exception("403 Forbidden"),
            Exception("Invalid credentials"),
            Exception("Session expired"),
            Exception("Access token invalid"),
        ]
        
        for auth_error in auth_errors:
            # Mock the search_api directly since that's what the backend uses
            with patch('quilt3.search_util.search_api') as mock_search_api:
                mock_search_api.side_effect = auth_error
                
                with pytest.raises(BackendError) as exc_info:
                    backend.search_packages("test", "s3://test-registry")
                
                error_message = str(exc_info.value)
                assert "quilt3" in error_message.lower()
                assert "search failed" in error_message.lower()
                # Should preserve the original authentication error context
                original_message = str(auth_error).lower()
                if "unauthorized" in original_message or "forbidden" in original_message:
                    assert any(keyword in error_message.lower() for keyword in ["unauthorized", "forbidden"])
                elif "credentials" in original_message or "session" in original_message or "token" in original_message:
                    assert any(keyword in error_message.lower() for keyword in ["credentials", "session", "token"])
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_network_error_scenarios_during_operations(self, mock_quilt3):
        """Test network-related errors during backend operations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        import socket
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test various network errors
        network_errors = [
            socket.timeout("Connection timeout"),
            ConnectionError("Network unreachable"),
            Exception("DNS resolution failed"),
            Exception("Connection refused"),
            Exception("Network is unreachable"),
        ]
        
        for network_error in network_errors:
            mock_quilt3.Package.browse.side_effect = network_error
            
            with pytest.raises(BackendError) as exc_info:
                backend.get_package_info("test/package", "registry")
            
            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert any(keyword in error_message.lower() for keyword in [
                "timeout", "connection", "network", "dns", "unreachable"
            ])
            
            mock_quilt3.Package.browse.side_effect = None  # Reset
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_data_validation_error_scenarios(self, mock_quilt3):
        """Test data validation errors during backend operations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test various data validation errors
        validation_errors = [
            ValueError("Invalid package name format"),
            Exception("Malformed registry URL"),
            Exception("Invalid path specification"),
            Exception("Package hash mismatch"),
            Exception("Corrupted package metadata"),
        ]
        
        for validation_error in validation_errors:
            mock_quilt3.list_buckets.side_effect = validation_error
            
            with pytest.raises(BackendError) as exc_info:
                backend.list_buckets()
            
            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert any(keyword in error_message.lower() for keyword in [
                "invalid", "malformed", "mismatch", "corrupted", "format"
            ])
            
            mock_quilt3.list_buckets.side_effect = None  # Reset
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_resource_exhaustion_error_scenarios(self, mock_quilt3):
        """Test resource exhaustion errors during backend operations."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test various resource exhaustion errors
        resource_errors = [
            MemoryError("Out of memory"),
            Exception("Rate limit exceeded"),
            Exception("Quota exceeded"),
            Exception("Too many requests"),
            Exception("Service unavailable"),
        ]
        
        for resource_error in resource_errors:
            # Mock the search_api directly since that's what the backend uses
            with patch('quilt3.search_util.search_api') as mock_search_api:
                mock_search_api.side_effect = resource_error
                
                with pytest.raises(BackendError) as exc_info:
                    backend.search_packages("test", "s3://test-registry")
                
                error_message = str(exc_info.value)
                assert "quilt3" in error_message.lower()
                assert "search failed" in error_message.lower()
                # Should preserve the original resource error context
                original_message = str(resource_error).lower()
                if "memory" in original_message:
                    assert "memory" in error_message.lower()
                elif any(keyword in original_message for keyword in ["rate", "quota", "requests", "unavailable"]):
                    assert any(keyword in error_message.lower() for keyword in ["rate", "quota", "requests", "unavailable"])
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_error_context_preservation(self, mock_quilt3):
        """Test that error context is preserved through the backend layer."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test with detailed error context
        detailed_errors = [
            Exception("HTTP 404: Package 'user/dataset' not found in registry 's3://my-registry'"),
            Exception("S3 Error: Access denied for bucket 'restricted-bucket' (Code: AccessDenied)"),
            Exception("Elasticsearch timeout: Query took longer than 30 seconds to complete"),
        ]
        
        operations = [
            (lambda: backend.get_package_info("user/dataset", "s3://my-registry"), mock_quilt3.Package.browse),
            (lambda: backend.list_buckets(), mock_quilt3.list_buckets),
        ]
        
        # Test the first two operations with their respective detailed errors
        for (operation, mock_method), detailed_error in zip(operations, detailed_errors[:2]):
            mock_method.side_effect = detailed_error
            
            with pytest.raises(BackendError) as exc_info:
                operation()
            
            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            # Should preserve specific details from original error
            if "404" in str(detailed_error):
                assert "404" in error_message
                assert "user/dataset" in error_message
            elif "AccessDenied" in str(detailed_error):
                assert "access denied" in error_message.lower()
                assert "restricted-bucket" in error_message
            
            mock_method.side_effect = None  # Reset
        
        # Test search operation with timeout error using search_api
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = detailed_errors[2]  # Timeout error
            
            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test", "s3://test-registry")
            
            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "search failed" in error_message.lower()
            assert "timeout" in error_message.lower()
            assert "30 seconds" in error_message
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_error_message_backend_identification(self, mock_quilt3):
        """Test that all error messages clearly identify the backend type."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test all operations include backend identification in errors
        operations_and_mocks = [
            (lambda: backend.search_packages("test", "registry"), mock_quilt3.search),
            (lambda: backend.get_package_info("pkg", "registry"), mock_quilt3.Package.browse),
            (lambda: backend.browse_content("pkg", "registry"), mock_quilt3.Package.browse),
            (lambda: backend.get_content_url("pkg", "registry", "path"), mock_quilt3.Package.browse),
            (lambda: backend.list_buckets(), mock_quilt3.list_buckets),
        ]
        
        for operation, mock_method in operations_and_mocks:
            mock_method.side_effect = Exception("Generic error")
            
            with pytest.raises(BackendError) as exc_info:
                operation()
            
            error_message = str(exc_info.value)
            # Should clearly identify this as a quilt3 backend error
            assert "quilt3" in error_message.lower()
            assert "backend" in error_message.lower()
            
            mock_method.side_effect = None  # Reset
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_error_handling_with_transformation_failures(self, mock_quilt3):
        """Test error handling when data transformation fails."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Mock successful quilt3 call but create object that will fail transformation
        mock_package = Mock()
        mock_package.name = "test/package"
        mock_package.modified = "invalid-date"  # This triggers the special error case in _transform_package
        mock_package.description = "Test package"
        mock_package.tags = []
        mock_package.registry = "s3://test-registry"
        mock_package.bucket = "test-bucket"
        mock_package.top_hash = "abc123"
        
        mock_quilt3.Package.browse.return_value = mock_package
        
        with pytest.raises(BackendError) as exc_info:
            backend.get_package_info("test/package", "s3://test-registry")
        
        error_message = str(exc_info.value)
        assert "quilt3" in error_message.lower()
        assert "get_package_info failed" in error_message.lower()
        # Should indicate this was a transformation/processing error
        assert any(keyword in error_message.lower() for keyword in [
            "transformation failed", "invalid date", "invalid"
        ])
    
    @patch('quilt_mcp.backends.quilt3_backend.quilt3')
    def test_error_propagation_from_quilt3_library(self, mock_quilt3):
        """Test proper error propagation from quilt3 library calls."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
        
        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend(mock_session)
        
        # Test that specific quilt3 errors are properly wrapped
        quilt3_specific_errors = [
            Exception("QuiltException: Package validation failed"),
            Exception("S3NoCredentialsError: No AWS credentials found"),
            Exception("PackageException: Invalid package structure"),
            Exception("RegistryException: Registry not accessible"),
        ]
        
        operations = [
            (lambda: backend.get_package_info("pkg", "s3://test-registry"), mock_quilt3.Package.browse),
            (lambda: backend.browse_content("pkg", "s3://test-registry"), mock_quilt3.Package.browse),
            (lambda: backend.list_buckets(), mock_quilt3.list_buckets),
        ]
        
        # Test the first three operations with their respective errors
        for (operation, mock_method), quilt3_error in zip(operations, quilt3_specific_errors[:3]):
            mock_method.side_effect = quilt3_error
            
            with pytest.raises(BackendError) as exc_info:
                operation()
            
            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            # Should preserve the original quilt3 error details
            original_message = str(quilt3_error).lower()
            if "validation" in original_message:
                assert "validation" in error_message.lower()
            elif "credentials" in original_message:
                assert "credentials" in error_message.lower()
            elif "package" in original_message:
                assert "package" in error_message.lower()
            
            mock_method.side_effect = None  # Reset
        
        # Test search operation with registry error using search_api
        with patch('quilt3.search_util.search_api') as mock_search_api:
            mock_search_api.side_effect = quilt3_specific_errors[3]  # Registry error
            
            with pytest.raises(BackendError) as exc_info:
                backend.search_packages("test", "s3://test-registry")
            
            error_message = str(exc_info.value)
            assert "quilt3" in error_message.lower()
            assert "search failed" in error_message.lower()
            assert "registry" in error_message.lower()


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