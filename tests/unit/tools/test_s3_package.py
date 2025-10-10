"""Unit tests for s3_package.py tool using backend abstraction.

This test suite validates that s3_package.py uses the backend abstraction
instead of directly instantiating QuiltService.
"""

from unittest.mock import Mock, patch, MagicMock
import pytest

from quilt_mcp.tools.s3_package import (
    package_create_from_s3,
    _create_enhanced_package,
)


class TestPackageCreateFromS3BackendUsage:
    """Test that package_create_from_s3 uses backend abstraction."""

    def test_package_create_from_s3_validates_package_name(self):
        """Test that package_create_from_s3 validates package name format."""
        result = package_create_from_s3(
            source_bucket="test-bucket",
            package_name="invalid-name",  # No slash
        )

        assert result["success"] is False
        assert "Invalid package name" in result["error"]

    def test_package_create_from_s3_validates_bucket_name(self):
        """Test that package_create_from_s3 rejects s3:// prefix in bucket name."""
        result = package_create_from_s3(
            source_bucket="s3://test-bucket",  # Should not have s3:// prefix
            package_name="user/test-package",
        )

        assert result["success"] is False
        assert "Invalid bucket name format" in result["error"]

    def test_package_create_from_s3_uses_get_backend_in_create_enhanced(self):
        """Test that _create_enhanced_package uses get_backend() internally."""
        mock_backend = Mock()

        # Mock create_package_revision
        mock_backend.create_package_revision.return_value = {
            "top_hash": "test-hash-123",
            "entries_added": 2,
        }

        with patch("quilt_mcp.tools.s3_package.get_backend", return_value=mock_backend):
            result = _create_enhanced_package(
                s3_client=Mock(),
                organized_structure={"root": [{"Key": "file1.csv"}, {"Key": "file2.csv"}]},
                source_bucket="test-bucket",
                package_name="user/test-package",
                target_registry="s3://target-bucket",
                description="Test package",
                enhanced_metadata={"quilt": {}},
                readme_content="# Test README",
            )

        # Verify get_backend was called
        mock_backend.create_package_revision.assert_called_once()
        assert result["top_hash"] == "test-hash-123"

    def test_package_create_from_s3_handles_dry_run(self):
        """Test that package_create_from_s3 handles dry_run mode without creating package."""
        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.head_bucket = Mock()
        mock_s3_client.get_paginator = Mock()

        # Mock paginator
        mock_paginator = Mock()
        mock_pages = [{"Contents": [{"Key": "file1.csv", "Size": 100}]}]
        mock_paginator.paginate.return_value = mock_pages
        mock_s3_client.get_paginator.return_value = mock_paginator

        with patch("quilt_mcp.tools.s3_package.get_s3_client", return_value=mock_s3_client):
            with patch("quilt_mcp.tools.s3_package.bucket_access_check") as mock_access:
                mock_access.return_value = {"success": True, "access_summary": {"can_write": True}}

                # Import is inside package_create_from_s3, patch at module level
                with patch("quilt_mcp.tools.quilt_summary.create_quilt_summary_files") as mock_summary:
                    mock_summary.return_value = {
                        "success": True,
                        "summary_package": {},
                        "files_generated": {},
                        "visualization_count": 0,
                    }

                    result = package_create_from_s3(
                        source_bucket="test-bucket",
                        package_name="user/test-package",
                        dry_run=True,
                    )

        assert result["success"] is True
        assert result["action"] == "preview"


class TestCreateEnhancedPackageBackendUsage:
    """Test that _create_enhanced_package uses backend abstraction."""

    def test_create_enhanced_package_uses_get_backend(self):
        """Test that _create_enhanced_package calls get_backend() instead of QuiltService()."""
        mock_backend = Mock()

        # Mock create_package_revision
        mock_backend.create_package_revision.return_value = {
            "top_hash": "test-hash-123",
            "entries_added": 1,
        }

        with patch("quilt_mcp.tools.s3_package.get_backend", return_value=mock_backend):
            result = _create_enhanced_package(
                s3_client=Mock(),
                organized_structure={"root": [{"Key": "file.csv"}]},
                source_bucket="test-bucket",
                package_name="user/test-package",
                target_registry="s3://target-bucket",
                description="Test",
                enhanced_metadata={"quilt": {}},
            )

        # Verify get_backend was called
        mock_backend.create_package_revision.assert_called_once()
        assert "top_hash" in result

    def test_create_enhanced_package_handles_readme_content(self):
        """Test that _create_enhanced_package adds readme_content to metadata for processing."""
        mock_backend = Mock()
        mock_backend.create_package_revision.return_value = {
            "top_hash": "test-hash-123",
        }

        with patch("quilt_mcp.tools.s3_package.get_backend", return_value=mock_backend):
            _create_enhanced_package(
                s3_client=Mock(),
                organized_structure={"root": []},
                source_bucket="test-bucket",
                package_name="user/test-package",
                target_registry="s3://target-bucket",
                description="Test",
                enhanced_metadata={"quilt": {}},
                readme_content="# Test README",
            )

        # Verify readme_content was passed in metadata
        call_args = mock_backend.create_package_revision.call_args
        assert "metadata" in call_args.kwargs
        assert "readme_content" in call_args.kwargs["metadata"]

    def test_create_enhanced_package_handles_errors(self):
        """Test that _create_enhanced_package handles backend errors."""
        mock_backend = Mock()
        mock_backend.create_package_revision.return_value = {
            "error": "Creation failed",
        }

        with patch("quilt_mcp.tools.s3_package.get_backend", return_value=mock_backend):
            with pytest.raises(Exception, match="Creation failed"):
                _create_enhanced_package(
                    s3_client=Mock(),
                    organized_structure={"root": []},
                    source_bucket="test-bucket",
                    package_name="user/test-package",
                    target_registry="s3://target-bucket",
                    description="Test",
                    enhanced_metadata={"quilt": {}},
                )


class TestS3PackageBackendIntegration:
    """Test integration between s3_package.py and backend abstraction."""

    def test_no_direct_quilt_service_instantiation(self):
        """Test that QuiltService is not directly instantiated in s3_package module."""
        import quilt_mcp.tools.s3_package as s3_package_module

        # Read source code
        source_code = open(s3_package_module.__file__).read()

        # Check that direct instantiation pattern is not present
        assert "QuiltService()" not in source_code, "s3_package.py should not directly instantiate QuiltService"

        # Verify get_backend is imported
        assert "from ..backends.factory import get_backend" in source_code, "s3_package.py should import get_backend"

    def test_backend_error_propagates_in_create_enhanced(self):
        """Test that errors from backend.create_package_revision propagate correctly."""
        mock_backend = Mock()
        mock_backend.create_package_revision.side_effect = Exception("Backend error")

        with patch("quilt_mcp.tools.s3_package.get_backend", return_value=mock_backend):
            with pytest.raises(Exception, match="Backend error"):
                _create_enhanced_package(
                    s3_client=Mock(),
                    organized_structure={"root": []},
                    source_bucket="test-bucket",
                    package_name="user/test-package",
                    target_registry="s3://target-bucket",
                    description="Test",
                    enhanced_metadata={"quilt": {}},
                )
