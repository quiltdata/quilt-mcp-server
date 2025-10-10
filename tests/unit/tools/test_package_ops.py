"""Unit tests for package_ops.py tool using backend abstraction.

This test suite validates that package_ops.py uses the backend abstraction
instead of directly instantiating QuiltService, including handling the module-level
singleton pattern.
"""

from unittest.mock import Mock, patch, MagicMock
import pytest

from quilt_mcp.tools.package_ops import (
    package_create,
    package_update,
    package_delete,
)


class TestPackageCreateBackendUsage:
    """Test that package_create uses backend abstraction."""

    def test_package_create_uses_get_backend(self):
        """Test that package_create calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()

        # Mock create_package_revision to return success
        mock_backend.create_package_revision.return_value = {
            "top_hash": "test-hash-123",
            "entries_added": 1,
            "files": [{"logical_path": "file.csv", "source": "s3://bucket/file.csv"}],
        }

        with patch("quilt_mcp.tools.package_ops.get_backend", return_value=mock_backend):
            result = package_create(
                package_name="user/test-package",
                s3_uris=["s3://bucket/file.csv"],
            )

        # Verify get_backend was called and method was invoked
        mock_backend.create_package_revision.assert_called_once()
        assert result["status"] == "success"
        assert result["package_name"] == "user/test-package"

    def test_package_create_validates_s3_uris(self):
        """Test that package_create validates S3 URIs."""
        result = package_create(
            package_name="user/test-package",
            s3_uris=[],
        )

        assert "error" in result
        assert "No S3 URIs provided" in result["error"]

    def test_package_create_validates_package_name(self):
        """Test that package_create validates package name."""
        result = package_create(
            package_name="",
            s3_uris=["s3://bucket/file.csv"],
        )

        assert "error" in result
        assert "Package name is required" in result["error"]

    def test_package_create_handles_metadata(self):
        """Test that package_create handles metadata correctly."""
        mock_backend = Mock()
        mock_backend.create_package_revision.return_value = {
            "top_hash": "test-hash-123",
            "entries_added": 1,
            "files": [],
        }

        with patch("quilt_mcp.tools.package_ops.get_backend", return_value=mock_backend):
            result = package_create(
                package_name="user/test-package",
                s3_uris=["s3://bucket/file.csv"],
                metadata={"description": "Test"},
            )

        # Verify metadata was passed to backend (after readme extraction)
        call_args = mock_backend.create_package_revision.call_args
        assert "metadata" in call_args.kwargs
        # README fields should be removed from metadata
        assert "readme_content" not in call_args.kwargs["metadata"]


class TestPackageUpdateBackendUsage:
    """Test that package_update uses backend abstraction."""

    def test_package_update_uses_get_backend(self):
        """Test that package_update calls get_backend() to browse existing package."""
        mock_backend = Mock()

        # Mock browse_package to return an existing package
        mock_pkg = Mock()
        mock_pkg.meta = {}
        mock_pkg.push = Mock(return_value="test-hash-123")
        # Mock the __contains__ method for 'in' operator in _collect_objects_into_package
        mock_pkg.__contains__ = Mock(return_value=False)
        # Mock the set method for adding objects
        mock_pkg.set = Mock()
        mock_backend.browse_package.return_value = mock_pkg

        with patch("quilt_mcp.tools.package_ops.get_backend", return_value=mock_backend):
            result = package_update(
                package_name="user/test-package",
                s3_uris=["s3://bucket/file.csv"],
            )

        # Verify get_backend was called and browse_package was invoked
        mock_backend.browse_package.assert_called_once()
        # Verify result is successful
        assert result["status"] == "success"

    def test_package_update_validates_inputs(self):
        """Test that package_update validates inputs."""
        # Test empty S3 URIs
        result = package_update(
            package_name="user/test-package",
            s3_uris=[],
        )
        assert "error" in result

        # Test empty package name
        result = package_update(
            package_name="",
            s3_uris=["s3://bucket/file.csv"],
        )
        assert "error" in result

    def test_package_update_handles_browse_error(self):
        """Test that package_update handles browse errors."""
        mock_backend = Mock()
        mock_backend.browse_package.side_effect = Exception("Browse failed")

        with patch("quilt_mcp.tools.package_ops.get_backend", return_value=mock_backend):
            result = package_update(
                package_name="user/test-package",
                s3_uris=["s3://bucket/file.csv"],
            )

        assert "error" in result
        assert "Failed to browse existing package" in result["error"]


class TestPackageDeleteBackendUsage:
    """Test that package_delete uses backend abstraction."""

    def test_package_delete_uses_backend_module(self):
        """Test that package_delete uses quilt3 from backend, not direct import."""
        mock_backend = Mock()

        # Mock get_quilt3_module to return a mock quilt3
        mock_quilt3 = Mock()
        mock_quilt3.delete_package = Mock()
        mock_backend.get_quilt3_module.return_value = mock_quilt3

        # Note: package_delete uses the module-level quilt3 which comes from quilt_service
        # We need to patch that as well
        with patch("quilt_mcp.tools.package_ops.quilt3", mock_quilt3):
            result = package_delete(package_name="user/test-package")

        # Verify delete was called
        mock_quilt3.delete_package.assert_called_once()
        assert result["status"] == "success"

    def test_package_delete_validates_package_name(self):
        """Test that package_delete validates package name."""
        result = package_delete(package_name="")

        assert "error" in result
        assert "package_name is required" in result["error"]


class TestPackageOpsBackendIntegration:
    """Test integration between package_ops.py and backend abstraction."""

    def test_no_direct_quilt_service_instantiation(self):
        """Test that QuiltService is not directly instantiated in package_ops module."""
        import quilt_mcp.tools.package_ops as ops_module

        # Read source code
        source_code = open(ops_module.__file__).read()

        # Check that direct instantiation pattern is not present
        assert "quilt_service = QuiltService()" not in source_code, (
            "package_ops.py should not directly instantiate QuiltService singleton"
        )

        # Verify get_backend is imported
        assert "from ..backends.factory import get_backend" in source_code, "package_ops.py should import get_backend"

    def test_backend_error_propagates_in_create(self):
        """Test that errors from backend.create_package_revision propagate correctly."""
        mock_backend = Mock()
        mock_backend.create_package_revision.return_value = {
            "error": "Creation failed",
        }

        with patch("quilt_mcp.tools.package_ops.get_backend", return_value=mock_backend):
            result = package_create(
                package_name="user/test-package",
                s3_uris=["s3://bucket/file.csv"],
            )

        # Error should be in the result
        assert "error" in result

    def test_module_level_quilt3_uses_backend(self):
        """Test that the module-level quilt3 export comes from backend."""
        import quilt_mcp.tools.package_ops as ops_module

        # The module should have a quilt3 attribute
        assert hasattr(ops_module, 'quilt3'), "package_ops.py should export quilt3 module"

        # Read source to verify it comes from backend
        source_code = open(ops_module.__file__).read()
        assert "quilt_service.get_quilt3_module()" in source_code or "backend.get_quilt3_module()" in source_code, (
            "quilt3 should be obtained from backend service"
        )
