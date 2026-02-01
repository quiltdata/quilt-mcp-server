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
        """Test that Quilt3_Backend initializes without parameters (new mode-based approach)."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # New implementation doesn't take session parameters
        # It should initialize successfully when quilt3 is available
        backend = Quilt3_Backend()
        assert backend is not None
        assert hasattr(backend, 'quilt3')

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3', None)
    def test_quilt3_backend_initialization_without_quilt3_library(self):
        """Test that Quilt3_Backend raises AuthenticationError when quilt3 library is not available."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Should raise AuthenticationError when quilt3 is not available
        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend()
        assert "quilt3 library is not available" in str(exc_info.value)

        # Should raise AuthenticationError when quilt3 is not available
        with pytest.raises(AuthenticationError) as exc_info:
            Quilt3_Backend()
        assert "quilt3 library is not available" in str(exc_info.value)

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_quilt3_backend_session_validation_failure(self, mock_quilt3):
        """Test backend initialization with quilt3 available (new mode-based approach)."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # New implementation doesn't validate sessions during initialization
        # It should initialize successfully when quilt3 is available
        backend = Quilt3_Backend()
        assert backend is not None
        assert hasattr(backend, 'quilt3')

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_quilt3_backend_session_validation_without_get_session_info(self, mock_quilt3):
        """Test backend initialization without session validation (new mode-based approach)."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        # Mock quilt3.session without get_session_info method
        mock_session = Mock()
        del mock_session.get_session_info  # Remove the method
        mock_quilt3.session = mock_session

        # Should initialize successfully without session validation
        backend = Quilt3_Backend()
        assert backend is not None
        assert hasattr(backend, 'quilt3')


class TestQuilt3BackendIntegration:
    """Test integration scenarios and complete workflows."""

    @patch('quilt3.search_util.search_api')
    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_error_propagation_through_workflow(self, mock_quilt3, mock_search_api):
        """Test that errors propagate correctly through workflow steps."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        mock_session = {'registry': 's3://test-registry'}
        backend = Quilt3_Backend()

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
