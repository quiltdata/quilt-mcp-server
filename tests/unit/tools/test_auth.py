"""Unit tests for auth.py tool using backend abstraction.

This test suite validates that auth.py uses the backend abstraction
instead of directly instantiating QuiltService.
"""

from unittest.mock import Mock, patch
import pytest

from quilt_mcp.tools.auth import (
    auth_status,
    catalog_info,
    catalog_name,
    configure_catalog,
    switch_catalog,
    _get_catalog_info,
)


class TestAuthStatusBackendUsage:
    """Test that auth_status uses backend abstraction."""

    def test_auth_status_uses_get_backend(self):
        """Test that auth_status calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()
        mock_backend.get_catalog_info.return_value = {
            "catalog_name": "test-catalog",
            "is_authenticated": True,
            "navigator_url": "https://test.example.com",
            "registry_url": "s3://test-bucket",
            "logged_in_url": "https://test.example.com",
        }
        mock_backend.get_logged_in_url.return_value = "https://test.example.com"
        mock_backend.get_config.return_value = {"registryUrl": "s3://test-bucket"}

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = auth_status()

        # Verify get_backend was called
        assert result["status"] == "authenticated"
        assert result["catalog_name"] == "test-catalog"
        mock_backend.get_catalog_info.assert_called_once()
        mock_backend.get_logged_in_url.assert_called_once()

    def test_auth_status_not_authenticated(self):
        """Test auth_status when not authenticated."""
        mock_backend = Mock()
        mock_backend.get_catalog_info.return_value = {
            "catalog_name": "test-catalog",
            "is_authenticated": False,
            "navigator_url": None,
            "registry_url": None,
            "logged_in_url": None,
        }
        mock_backend.get_logged_in_url.return_value = None

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = auth_status()

        assert result["status"] == "not_authenticated"
        assert "setup_instructions" in result

    def test_auth_status_error_propagates(self):
        """Test that errors from backend propagate correctly."""
        mock_backend = Mock()
        mock_backend.get_catalog_info.side_effect = Exception("Backend error")

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = auth_status()

        assert result["status"] == "error"
        assert "Backend error" in result["error"]


class TestCatalogInfoBackendUsage:
    """Test that catalog_info uses backend abstraction."""

    def test_catalog_info_uses_get_backend(self):
        """Test that catalog_info calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()
        mock_backend.get_catalog_info.return_value = {
            "catalog_name": "test-catalog",
            "is_authenticated": True,
            "navigator_url": "https://test.example.com",
            "registry_url": "s3://test-bucket",
            "logged_in_url": "https://test.example.com",
        }

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = catalog_info()

        # Verify get_backend was called via _get_catalog_info
        assert result["status"] == "success"
        assert result["catalog_name"] == "test-catalog"
        assert result["is_authenticated"] is True
        mock_backend.get_catalog_info.assert_called_once()

    def test_catalog_info_includes_urls(self):
        """Test that catalog_info includes URLs when available."""
        mock_backend = Mock()
        mock_backend.get_catalog_info.return_value = {
            "catalog_name": "test-catalog",
            "is_authenticated": True,
            "navigator_url": "https://nav.example.com",
            "registry_url": "s3://registry-bucket",
            "logged_in_url": "https://logged-in.example.com",
        }

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = catalog_info()

        assert result["navigator_url"] == "https://nav.example.com"
        assert result["registry_url"] == "s3://registry-bucket"
        assert result["logged_in_url"] == "https://logged-in.example.com"


class TestCatalogNameBackendUsage:
    """Test that catalog_name uses backend abstraction."""

    def test_catalog_name_uses_get_backend(self):
        """Test that catalog_name calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()
        mock_backend.get_catalog_info.return_value = {
            "catalog_name": "test-catalog",
            "is_authenticated": True,
            "navigator_url": "https://test.example.com",
            "registry_url": None,
            "logged_in_url": "https://test.example.com",
        }

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = catalog_name()

        # Verify get_backend was called via _get_catalog_info
        assert result["status"] == "success"
        assert result["catalog_name"] == "test-catalog"
        assert result["detection_method"] == "authentication"
        mock_backend.get_catalog_info.assert_called_once()

    def test_catalog_name_detection_methods(self):
        """Test catalog_name detection method logic."""
        mock_backend = Mock()

        # Test navigator_config detection
        mock_backend.get_catalog_info.return_value = {
            "catalog_name": "test-catalog",
            "is_authenticated": False,
            "navigator_url": "https://test.example.com",
            "registry_url": None,
            "logged_in_url": None,
        }

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = catalog_name()

        assert result["detection_method"] == "navigator_config"


class TestConfigureCatalogBackendUsage:
    """Test that configure_catalog uses backend abstraction."""

    def test_configure_catalog_uses_get_backend(self):
        """Test that configure_catalog calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()
        mock_backend.set_config.return_value = None
        mock_backend.get_config.return_value = {"navigator_url": "https://test.example.com"}

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = configure_catalog("https://test.example.com")

        # Verify get_backend was called and methods invoked
        assert result["status"] == "success"
        mock_backend.set_config.assert_called_once_with("https://test.example.com")
        mock_backend.get_config.assert_called_once()

    def test_configure_catalog_validates_url(self):
        """Test that configure_catalog validates URL format."""
        result = configure_catalog("invalid-url")

        assert result["status"] == "error"
        assert "Invalid catalog URL format" in result["error"]

    def test_configure_catalog_error_propagates(self):
        """Test that errors from backend propagate correctly."""
        mock_backend = Mock()
        mock_backend.set_config.side_effect = Exception("Config error")

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = configure_catalog("https://test.example.com")

        assert result["status"] == "error"
        assert "Config error" in result["error"]


class TestSwitchCatalogBackendUsage:
    """Test that switch_catalog uses backend abstraction."""

    def test_switch_catalog_uses_get_backend(self):
        """Test that switch_catalog calls get_backend() via configure_catalog."""
        mock_backend = Mock()
        mock_backend.set_config.return_value = None
        mock_backend.get_config.return_value = {"navigator_url": "https://demo.quiltdata.com"}

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = switch_catalog("demo")

        # Verify get_backend was called via configure_catalog
        assert result["status"] == "success"
        assert result["action"] == "switched"
        mock_backend.set_config.assert_called_once()

    def test_switch_catalog_maps_friendly_names(self):
        """Test that switch_catalog maps friendly catalog names."""
        mock_backend = Mock()
        mock_backend.set_config.return_value = None
        mock_backend.get_config.return_value = {"navigator_url": "https://demo.quiltdata.com"}

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = switch_catalog("demo")

        # Verify demo maps to correct URL
        mock_backend.set_config.assert_called_once_with("https://demo.quiltdata.com")


class TestAuthBackendIntegration:
    """Test integration between auth.py and backend abstraction."""

    def test_no_direct_quilt_service_instantiation(self):
        """Test that QuiltService is not directly instantiated in public functions."""
        import quilt_mcp.tools.auth as auth_module

        # Note: auth.py still imports QuiltService but should use it via get_backend
        # We verify that get_backend is called, not that QuiltService isn't imported
        mock_backend = Mock()
        mock_backend.get_catalog_info.return_value = {
            "catalog_name": "test",
            "is_authenticated": False,
            "navigator_url": None,
            "registry_url": None,
            "logged_in_url": None,
        }

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend) as mock_get_backend:
            catalog_info()

            # get_backend SHOULD be called via _get_catalog_info
            mock_get_backend.assert_called()

    def test_get_catalog_info_uses_backend(self):
        """Test that _get_catalog_info helper uses backend."""
        mock_backend = Mock()
        mock_backend.get_catalog_info.return_value = {
            "catalog_name": "test",
            "is_authenticated": True,
            "navigator_url": "https://test.com",
            "registry_url": "s3://bucket",
            "logged_in_url": "https://test.com",
        }

        with patch("quilt_mcp.tools.auth.get_backend", return_value=mock_backend):
            result = _get_catalog_info()

        assert result["catalog_name"] == "test"
        mock_backend.get_catalog_info.assert_called_once()
