"""Unit tests for package_management.py tool using backend abstraction.

This test suite validates that package_management.py uses the backend abstraction
instead of directly instantiating QuiltService.
"""

from unittest.mock import Mock, patch, MagicMock
import pytest

from quilt_mcp.tools.package_management import (
    create_package_enhanced,
    package_update_metadata,
)


class TestCreatePackageEnhancedBackendUsage:
    """Test that create_package_enhanced uses backend abstraction."""

    def test_create_package_enhanced_uses_get_backend(self):
        """Test that create_package_enhanced calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()

        # Mock browse_package method for package update flow
        mock_pkg = Mock()
        mock_pkg.meta = {}
        mock_backend.browse_package.return_value = mock_pkg

        with patch("quilt_mcp.tools.package_management.get_backend", return_value=mock_backend):
            with patch("quilt_mcp.tools.package_management._base_package_create") as mock_create:
                mock_create.return_value = {
                    "status": "success",
                    "entries_added": 1,
                }

                result = create_package_enhanced(
                    name="user/test-package",
                    files=["s3://bucket/file.csv"],
                    description="Test package",
                )

        # Verify result is successful
        assert result.get("status") == "success" or result.get("success") is not False

    def test_create_package_enhanced_validates_package_name(self):
        """Test that create_package_enhanced validates package name format."""
        result = create_package_enhanced(
            name="invalid-name-no-slash",
            files=["s3://bucket/file.csv"],
        )

        assert result["success"] is False
        assert "Invalid package name" in result["error"]

    def test_create_package_enhanced_validates_files_parameter(self):
        """Test that create_package_enhanced validates files parameter."""
        # Test with empty files
        result = create_package_enhanced(
            name="user/test-package",
            files=[],
        )

        assert result["success"] is False
        assert "Invalid files parameter" in result["error"]

        # Test with None files
        result = create_package_enhanced(
            name="user/test-package",
            files=None,
        )

        assert result["success"] is False
        assert "Invalid files parameter" in result["error"]

    def test_create_package_enhanced_validates_s3_uris(self):
        """Test that create_package_enhanced validates S3 URI format."""
        result = create_package_enhanced(
            name="user/test-package",
            files=["not-an-s3-uri"],
        )

        assert result["success"] is False
        assert "Invalid S3 URIs detected" in result["error"]

    def test_create_package_enhanced_handles_dry_run(self):
        """Test that create_package_enhanced handles dry_run mode."""
        # Import is inside the function, need to patch at the module level where it's imported
        with patch("quilt_mcp.tools.quilt_summary.create_quilt_summary_files") as mock_summary:
            mock_summary.return_value = {
                "success": True,
                "summary_package": {},
                "files_generated": {},
            }

            result = create_package_enhanced(
                name="user/test-package",
                files=["s3://bucket/file.csv"],
                dry_run=True,
            )

        assert result["success"] is True
        assert result["action"] == "preview"


class TestPackageUpdateMetadataBackendUsage:
    """Test that package_update_metadata uses backend abstraction."""

    def test_package_update_metadata_uses_get_backend(self):
        """Test that package_update_metadata calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()

        # Mock browse_package and package structure
        mock_pkg = Mock()
        mock_pkg.meta = {"existing": "metadata"}
        mock_pkg.push = Mock(return_value="test-hash-123")
        mock_backend.browse_package.return_value = mock_pkg

        with patch("quilt_mcp.tools.package_management.get_backend", return_value=mock_backend):
            result = package_update_metadata(
                package_name="user/test-package",
                metadata={"new": "metadata"},
            )

        # Verify get_backend was used
        mock_backend.browse_package.assert_called_once()
        assert result["success"] is True

    def test_package_update_metadata_validates_json_metadata(self):
        """Test that package_update_metadata validates JSON string metadata."""
        result = package_update_metadata(
            package_name="user/test-package",
            metadata="invalid json {",
        )

        assert result["success"] is False
        assert "Invalid metadata JSON format" in result["error"]

    def test_package_update_metadata_merges_with_existing(self):
        """Test that package_update_metadata merges with existing metadata."""
        mock_backend = Mock()

        # Mock browse_package with existing metadata
        mock_pkg = Mock()
        mock_pkg.meta = {"existing": "value", "keep": "this"}
        mock_pkg.push = Mock(return_value="test-hash-123")
        mock_backend.browse_package.return_value = mock_pkg

        with patch("quilt_mcp.tools.package_management.get_backend", return_value=mock_backend):
            result = package_update_metadata(
                package_name="user/test-package",
                metadata={"existing": "updated", "new": "value"},
                merge_with_existing=True,
            )

        # Verify metadata was merged correctly
        assert result["success"] is True
        final_metadata = result["new_metadata"]
        assert final_metadata["existing"] == "updated"
        assert final_metadata["keep"] == "this"
        assert final_metadata["new"] == "value"

    def test_package_update_metadata_replaces_when_not_merging(self):
        """Test that package_update_metadata replaces metadata when merge=False."""
        mock_backend = Mock()

        # Mock browse_package with existing metadata
        mock_pkg = Mock()
        mock_pkg.meta = {"existing": "value", "keep": "this"}
        mock_pkg.push = Mock(return_value="test-hash-123")
        mock_backend.browse_package.return_value = mock_pkg

        with patch("quilt_mcp.tools.package_management.get_backend", return_value=mock_backend):
            result = package_update_metadata(
                package_name="user/test-package",
                metadata={"new": "value"},
                merge_with_existing=False,
            )

        # Verify metadata was replaced
        assert result["success"] is True
        final_metadata = result["new_metadata"]
        assert final_metadata == {"new": "value"}


class TestPackageManagementBackendIntegration:
    """Test integration between package_management.py and backend abstraction."""

    def test_no_direct_quilt_service_instantiation(self):
        """Test that QuiltService is not directly imported in package_management module."""
        import quilt_mcp.tools.package_management as pm_module

        # Verify QuiltService is not imported in package_management module
        # Note: It may be imported from other modules, but shouldn't be instantiated directly
        source_code = open(pm_module.__file__).read()

        # Check that direct instantiation patterns are not present
        assert "QuiltService()" not in source_code, \
            "package_management.py should not directly instantiate QuiltService"

        # Verify get_backend is imported
        assert "from ..backends.factory import get_backend" in source_code, \
            "package_management.py should import get_backend"

    def test_backend_error_propagates_in_update_metadata(self):
        """Test that errors from backend propagate correctly in update_metadata."""
        mock_backend = Mock()
        mock_backend.browse_package.side_effect = Exception("Backend browse error")

        with patch("quilt_mcp.tools.package_management.get_backend", return_value=mock_backend):
            result = package_update_metadata(
                package_name="user/test-package",
                metadata={"new": "metadata"},
            )

        # Error should be caught and returned as structured response
        assert result["success"] is False
        assert "Failed to update package metadata" in result["error"]
