"""
Tests for Quilt3_Backend core structure and integration.

This module tests the basic structure, initialization, and integration scenarios
of the Quilt3_Backend implementation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from typing import List, Optional

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError
from quilt_mcp.domain.package_info import Package_Info
from quilt_mcp.domain.content_info import Content_Info
from quilt_mcp.domain.bucket_info import Bucket_Info


class TestQuilt3BackendStructure:
    """Test the basic structure and initialization of Quilt3_Backend."""

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
        abstract_methods = {
            name for name, method in QuiltOps.__dict__.items() if getattr(method, '__isabstractmethod__', False)
        }

        # Check that Quilt3_Backend implements all abstract methods
        backend_methods = set(dir(Quilt3_Backend))

        for method_name in abstract_methods:
            assert method_name in backend_methods, f"Missing implementation of abstract method: {method_name}"
            # Verify the method is callable
            assert callable(getattr(Quilt3_Backend, method_name))

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
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

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3', None)
    def test_quilt3_backend_initialization_without_quilt3_library(self):
        """Test that Quilt3_Backend raises AuthenticationError when quilt3 library is not available."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session_config = {'registry': 's3://test-registry'}

        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend(mock_session_config)

        assert "quilt3 library is not available" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
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

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
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



class TestQuilt3BackendIntegration:
    """Test integration scenarios and complete workflows."""

    @patch('quilt3.search_util.search_api')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
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
                            "top_hash": "abc123",
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
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
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
