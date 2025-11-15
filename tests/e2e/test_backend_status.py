"""Tests for Phase 4: Backend Status Integration.

This module tests the get_search_backend_status() helper function and its
integration into catalog_info and search_catalog responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from quilt_mcp.search.utils.backend_status import (
    get_search_backend_status,
    get_backend_capabilities,
)
from quilt_mcp.search.backends.base import BackendType, BackendStatus


class TestBackendCapabilities:
    """Test backend capability detection."""

    def test_elasticsearch_capabilities(self):
        """Test that Elasticsearch capabilities are correctly defined."""
        capabilities = get_backend_capabilities(BackendType.ELASTICSEARCH)
        assert "metadata_search" in capabilities
        assert "content_search" in capabilities
        assert "package_search" in capabilities
        assert "object_search" in capabilities
        assert "natural_language_query" in capabilities



class TestBackendStatusHelper:
    """Test the get_search_backend_status() helper function."""

    def test_backend_status_structure(self):
        """Test that backend status returns the correct structure."""
        status = get_search_backend_status()

        # Check required top-level fields
        assert "available" in status
        assert "backend" in status
        assert "capabilities" in status
        assert "status" in status
        assert "backends" in status

        # Check that status is boolean
        assert isinstance(status["available"], bool)

        # Check that backends dict has expected structure
        assert "elasticsearch" in status["backends"]

        # Each backend should have these fields
        for backend_name in ["elasticsearch"]:
            backend_info = status["backends"][backend_name]
            assert "available" in backend_info
            assert "status" in backend_info
            assert "capabilities" in backend_info
            assert isinstance(backend_info["available"], bool)
            assert isinstance(backend_info["capabilities"], list)

    def test_backend_status_when_available(self):
        """Test backend status when a backend is available."""
        with patch("quilt_mcp.search.tools.unified_search.UnifiedSearchEngine") as mock_engine:
            # Create mock backend that is available
            mock_backend = Mock()
            mock_backend.backend_type = BackendType.ELASTICSEARCH
            mock_backend.status = BackendStatus.AVAILABLE
            mock_backend.last_error = None
            mock_backend.ensure_initialized = Mock()

            # Setup registry mock
            mock_registry = Mock()
            mock_registry._select_primary_backend.return_value = mock_backend
            mock_registry.get_backend.return_value = mock_backend

            # Setup engine mock
            mock_engine_instance = Mock()
            mock_engine_instance.registry = mock_registry
            mock_engine.return_value = mock_engine_instance

            status = get_search_backend_status()

            assert status["available"] is True
            assert status["backend"] == "elasticsearch"
            assert status["status"] == "ready"
            assert len(status["capabilities"]) > 0

    def test_backend_status_when_unavailable(self):
        """Test backend status when no backends are available."""
        with patch("quilt_mcp.search.tools.unified_search.UnifiedSearchEngine") as mock_engine:
            # Create mock backend that is unavailable
            mock_backend = Mock()
            mock_backend.backend_type = BackendType.ELASTICSEARCH
            mock_backend.status = BackendStatus.UNAVAILABLE
            mock_backend.last_error = "Not authenticated"
            mock_backend.ensure_initialized = Mock()

            # Setup registry mock
            mock_registry = Mock()
            mock_registry._select_primary_backend.return_value = None
            mock_registry.get_backend.return_value = mock_backend

            # Setup engine mock
            mock_engine_instance = Mock()
            mock_engine_instance.registry = mock_registry
            mock_engine.return_value = mock_engine_instance

            status = get_search_backend_status()

            assert status["available"] is False
            assert status["backend"] is None
            assert status["status"] in ["authentication_required", "unavailable"]

    def test_backend_status_error_handling(self):
        """Test that backend status handles errors gracefully."""
        with patch("quilt_mcp.search.tools.unified_search.UnifiedSearchEngine") as mock_engine:
            # Make UnifiedSearchEngine raise an exception
            mock_engine.side_effect = Exception("Test error")

            status = get_search_backend_status()

            # Should still return a valid structure
            assert "available" in status
            assert status["available"] is False
            assert status["status"] == "error"
            assert "error" in status
            assert "backends" in status


class TestCatalogInfoIntegration:
    """Test backend status integration into catalog_info."""

    @patch("quilt_mcp.services.auth_metadata._get_catalog_info")
    @patch("quilt_mcp.search.utils.get_search_backend_status")
    def test_catalog_info_includes_backend_status(self, mock_backend_status, mock_catalog_info):
        """Test that catalog_info includes backend status."""
        from quilt_mcp.services.auth_metadata import catalog_info

        # Mock catalog info
        mock_catalog_info.return_value = {
            "catalog_name": "test-catalog",
            "is_authenticated": True,
            "logged_in_url": "https://test-catalog.com",
            "navigator_url": None,
            "registry_url": None,
            "region": "us-east-1",
            "tabulator_data_catalog": None,
        }

        # Mock backend status
        mock_backend_status.return_value = {
            "available": True,
            "backend": "elasticsearch",
            "capabilities": ["metadata_search", "content_search"],
            "status": "ready",
        }

        result = catalog_info()

        assert "search_backend_status" in result
        assert result["search_backend_status"]["available"] is True
        assert result["search_backend_status"]["backend"] == "elasticsearch"

    @patch("quilt_mcp.services.auth_metadata._get_catalog_info")
    @patch("quilt_mcp.search.utils.get_search_backend_status")
    def test_catalog_info_handles_backend_status_errors(self, mock_backend_status, mock_catalog_info):
        """Test that catalog_info handles backend status errors gracefully."""
        from quilt_mcp.services.auth_metadata import catalog_info

        # Mock catalog info
        mock_catalog_info.return_value = {
            "catalog_name": "test-catalog",
            "is_authenticated": True,
            "logged_in_url": "https://test-catalog.com",
            "navigator_url": None,
            "registry_url": None,
            "region": "us-east-1",
            "tabulator_data_catalog": None,
        }

        # Make backend status raise an exception
        mock_backend_status.side_effect = Exception("Backend status check failed")

        result = catalog_info()

        # Should still have search_backend_status field with error info
        assert "search_backend_status" in result
        assert result["search_backend_status"]["available"] is False
        assert "error" in result["search_backend_status"]
