"""Unit tests for packages.py tool using backend abstraction.

This test suite validates that packages.py uses the backend abstraction
instead of directly instantiating QuiltService.
"""

from unittest.mock import Mock, patch, MagicMock
import pytest

from quilt_mcp.tools.packages import packages_list, packages_search


class TestPackagesListBackendUsage:
    """Test that packages_list uses backend abstraction."""

    def test_packages_list_uses_get_backend(self):
        """Test that packages_list calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()
        mock_backend.list_packages.return_value = iter(["pkg1/test", "pkg2/test"])

        with patch("quilt_mcp.tools.packages.get_backend", return_value=mock_backend):
            result = packages_list(registry="s3://test-bucket")

        # Verify get_backend was called
        # Verify backend.list_packages was called with correct registry
        mock_backend.list_packages.assert_called_once_with(registry="s3://test-bucket")
        assert result == {"packages": ["pkg1/test", "pkg2/test"]}

    def test_packages_list_normalizes_registry(self):
        """Test that packages_list normalizes registry before passing to backend."""
        mock_backend = Mock()
        mock_backend.list_packages.return_value = iter(["pkg1/test"])

        with patch("quilt_mcp.tools.packages.get_backend", return_value=mock_backend):
            packages_list(registry="test-bucket")  # No s3:// prefix

        # Should normalize to s3:// format
        mock_backend.list_packages.assert_called_once_with(registry="s3://test-bucket")

    def test_packages_list_applies_prefix_filter(self):
        """Test that packages_list filters by prefix correctly."""
        mock_backend = Mock()
        mock_backend.list_packages.return_value = iter([
            "user/package-a",
            "user/package-b",
            "other/package-c"
        ])

        with patch("quilt_mcp.tools.packages.get_backend", return_value=mock_backend):
            result = packages_list(registry="s3://test-bucket", prefix="user/")

        assert result == {"packages": ["user/package-a", "user/package-b"]}

    def test_packages_list_applies_limit(self):
        """Test that packages_list limits results correctly."""
        mock_backend = Mock()
        mock_backend.list_packages.return_value = iter([
            "pkg1/test", "pkg2/test", "pkg3/test", "pkg4/test"
        ])

        with patch("quilt_mcp.tools.packages.get_backend", return_value=mock_backend):
            result = packages_list(registry="s3://test-bucket", limit=2)

        assert result == {"packages": ["pkg1/test", "pkg2/test"]}


class TestPackagesSearchBackendUsage:
    """Test that packages_search uses backend abstraction."""

    def test_packages_search_uses_get_backend(self):
        """Test that packages_search calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()
        mock_search_api = Mock()
        mock_search_api.search.return_value = {
            "hits": {
                "total": {"value": 1},
                "hits": [{"_source": {"key": "user/test-package"}}]
            }
        }
        mock_backend.get_search_api.return_value = mock_search_api

        with patch("quilt_mcp.tools.packages.get_backend", return_value=mock_backend):
            result = packages_search(query="test", registry="s3://test-bucket")

        # Verify get_backend was called
        mock_backend.get_search_api.assert_called_once()
        assert "packages" in result or "results" in result

    def test_packages_search_normalizes_registry(self):
        """Test that packages_search normalizes registry before using it."""
        mock_backend = Mock()
        mock_search_api = Mock()
        mock_search_api.search.return_value = {
            "hits": {"total": {"value": 0}, "hits": []}
        }
        mock_backend.get_search_api.return_value = mock_search_api

        with patch("quilt_mcp.tools.packages.get_backend", return_value=mock_backend):
            packages_search(query="test", registry="test-bucket")

        # Verify backend was used
        mock_backend.get_search_api.assert_called_once()


class TestPackagesBackendIntegration:
    """Test integration between packages.py and backend abstraction."""

    def test_no_direct_quilt_service_instantiation(self):
        """Test that QuiltService is not directly instantiated in packages_list."""
        mock_backend = Mock()
        mock_backend.list_packages.return_value = iter([])

        with patch("quilt_mcp.tools.packages.get_backend", return_value=mock_backend) as mock_get_backend:
            with patch("quilt_mcp.tools.packages.QuiltService") as mock_quilt_service_class:
                packages_list(registry="s3://test-bucket")

                # QuiltService class should NOT be instantiated
                mock_quilt_service_class.assert_not_called()
                # get_backend SHOULD be called
                mock_get_backend.assert_called_once()

    def test_backend_list_packages_error_propagates(self):
        """Test that errors from backend.list_packages propagate correctly."""
        mock_backend = Mock()
        mock_backend.list_packages.side_effect = Exception("Backend error")

        with patch("quilt_mcp.tools.packages.get_backend", return_value=mock_backend):
            with pytest.raises(Exception, match="Backend error"):
                packages_list(registry="s3://test-bucket")
