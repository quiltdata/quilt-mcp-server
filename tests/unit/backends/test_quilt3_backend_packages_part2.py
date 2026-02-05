"""
Tests for Quilt3_Backend package operations, specifically create_package_revision().

This module tests the Quilt3_Backend implementation of package operations
following TDD principles, with focus on create_package_revision() method.
"""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.ops.exceptions import ValidationError, BackendError
from quilt_mcp.domain.package_creation import Package_Creation_Result


class TestQuilt3BackendUpdatePackageRevision:
    """Test update_package_revision method implementation in Quilt3_Backend."""

    @pytest.fixture
    def backend(self):
        """Create Quilt3_Backend instance for testing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    def test_update_package_revision_successful_update(self, backend):
        """Test successful package update with new files."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock existing package
            mock_existing_pkg = Mock()
            mock_existing_pkg.meta = {"description": "Original package"}

            # Mock Package.browse to return existing package
            mock_quilt3.Package.browse.return_value = mock_existing_pkg

            # Mock push to return hash
            mock_existing_pkg.push.return_value = "updated123hash456"

            result = backend.update_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/new_file.txt", "s3://bucket/folder/another.csv"],
                registry="s3://test-registry",
                metadata={"updated": "true"},
                message="Test update",
            )

            # Verify Package.browse was called
            mock_quilt3.Package.browse.assert_called_once_with("user/package", registry="s3://test-registry")

            # Verify files were added to package
            assert mock_existing_pkg.set.call_count == 2
            mock_existing_pkg.set.assert_any_call("new_file.txt", "s3://bucket/new_file.txt")  # Flattened
            mock_existing_pkg.set.assert_any_call("another.csv", "s3://bucket/folder/another.csv")  # Flattened

            # Verify metadata was merged
            mock_existing_pkg.set_meta.assert_called_once()
            merged_meta = mock_existing_pkg.set_meta.call_args[0][0]
            assert merged_meta["description"] == "Original package"  # Original preserved
            assert merged_meta["updated"] == "true"  # New metadata added

            # Verify push was called with correct parameters
            push_args = mock_existing_pkg.push.call_args
            assert push_args[0][0] == "user/package"
            assert push_args[1]['registry'] == "s3://test-registry"
            assert push_args[1]['message'] == "Test update"
            assert push_args[1]['force'] is True
            assert 'selector_fn' in push_args[1]

            # Verify result
            assert result.success is True
            assert result.package_name == "user/package"
            assert result.top_hash == "updated123hash456"
            assert result.registry == "s3://test-registry"
            assert result.file_count == 2

    def test_update_package_revision_auto_organize_true(self, backend):
        """Test package update with auto_organize=True preserves folder structure."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_existing_pkg = Mock()
            mock_existing_pkg.meta = {}
            mock_quilt3.Package.browse.return_value = mock_existing_pkg
            mock_existing_pkg.push.return_value = "test-hash"

            result = backend.update_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/folder/subfolder/file.txt"],
                registry="s3://test-registry",
                auto_organize=True,
            )

            # Verify folder structure is preserved
            mock_existing_pkg.set.assert_called_with(
                "folder/subfolder/file.txt", "s3://bucket/folder/subfolder/file.txt"
            )
            assert result.success is True

    def test_update_package_revision_auto_organize_false(self, backend):
        """Test package update with auto_organize=False flattens to filename."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_existing_pkg = Mock()
            mock_existing_pkg.meta = {}
            mock_quilt3.Package.browse.return_value = mock_existing_pkg
            mock_existing_pkg.push.return_value = "test-hash"

            result = backend.update_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/folder/subfolder/file.txt"],
                registry="s3://test-registry",
                auto_organize=False,
            )

            # Verify filename is flattened
            mock_existing_pkg.set.assert_called_with("file.txt", "s3://bucket/folder/subfolder/file.txt")
            assert result.success is True

    def test_update_package_revision_copy_behavior(self, backend):
        """Test package update with different copy behaviors."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_existing_pkg = Mock()
            mock_existing_pkg.meta = {}
            mock_quilt3.Package.browse.return_value = mock_existing_pkg
            mock_existing_pkg.push.return_value = "test-hash"

            # Test copy="none" (default)
            result = backend.update_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/file.txt"],
                registry="s3://test-registry",
                copy="none",
            )

            push_args = mock_existing_pkg.push.call_args
            selector_fn = push_args[1]['selector_fn']
            assert selector_fn("test_key", "test_entry") is False  # Should not copy
            assert result.success is True

            # Reset and test copy="all"
            mock_existing_pkg.reset_mock()
            result = backend.update_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/file.txt"],
                registry="s3://test-registry",
                copy="all",
            )

            push_args = mock_existing_pkg.push.call_args
            selector_fn = push_args[1]['selector_fn']
            assert selector_fn("test_key", "test_entry") is True  # Should copy
            assert result.success is True

    def test_update_package_revision_metadata_merging(self, backend):
        """Test metadata merging behavior."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_existing_pkg = Mock()
            mock_existing_pkg.meta = {"original": "value", "shared": "old_value"}
            mock_quilt3.Package.browse.return_value = mock_existing_pkg
            mock_existing_pkg.push.return_value = "test-hash"

            result = backend.update_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/file.txt"],
                registry="s3://test-registry",
                metadata={"new": "value", "shared": "new_value"},
            )

            # Verify metadata was merged correctly
            mock_existing_pkg.set_meta.assert_called_once()
            merged_meta = mock_existing_pkg.set_meta.call_args[0][0]
            assert merged_meta["original"] == "value"  # Original preserved
            assert merged_meta["new"] == "value"  # New added
            assert merged_meta["shared"] == "new_value"  # New overwrites old
            assert result.success is True

    def test_update_package_revision_no_metadata(self, backend):
        """Test package update without metadata."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_existing_pkg = Mock()
            mock_existing_pkg.meta = {"existing": "value"}
            mock_quilt3.Package.browse.return_value = mock_existing_pkg
            mock_existing_pkg.push.return_value = "test-hash"

            result = backend.update_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/file.txt"],
                registry="s3://test-registry",
                metadata=None,
            )

            # Verify no metadata operations
            mock_existing_pkg.set_meta.assert_not_called()
            assert result.success is True

    def test_update_package_revision_existing_package_no_metadata(self, backend):
        """Test package update when existing package has no metadata."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_existing_pkg = Mock()
            # Simulate existing package with no metadata (accessing .meta raises exception)
            mock_existing_pkg.meta = Mock(side_effect=Exception("No metadata"))
            mock_quilt3.Package.browse.return_value = mock_existing_pkg
            mock_existing_pkg.push.return_value = "test-hash"

            result = backend.update_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/file.txt"],
                registry="s3://test-registry",
                metadata={"new": "value"},
            )

            # Verify metadata was set (starting fresh since existing had none)
            mock_existing_pkg.set_meta.assert_called_once()
            merged_meta = mock_existing_pkg.set_meta.call_args[0][0]
            assert merged_meta == {"new": "value"}
            assert result.success is True

    def test_update_package_revision_skips_invalid_uris(self, backend):
        """Test that invalid URIs are skipped during update."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_existing_pkg = Mock()
            mock_existing_pkg.meta = {}
            mock_quilt3.Package.browse.return_value = mock_existing_pkg
            mock_existing_pkg.push.return_value = "test-hash"

            result = backend.update_package_revision(
                package_name="user/package",
                s3_uris=[
                    "s3://bucket/valid.txt",
                    "not-s3-uri",  # Should be skipped
                    "s3://bucket",  # No key, should be skipped
                    "s3://bucket/folder/",  # Directory, should be skipped
                    "s3://bucket/another_valid.csv",
                ],
                registry="s3://test-registry",
            )

            # Verify only valid URIs were added
            assert mock_existing_pkg.set.call_count == 2
            mock_existing_pkg.set.assert_any_call("valid.txt", "s3://bucket/valid.txt")
            mock_existing_pkg.set.assert_any_call("another_valid.csv", "s3://bucket/another_valid.csv")
            assert result.success is True
            assert result.file_count == 2

    def test_update_package_revision_validation_errors(self, backend):
        """Test validation error handling."""
        # Test invalid package name
        with pytest.raises(ValidationError) as exc_info:
            backend.update_package_revision(
                package_name="invalid-name",  # No slash
                s3_uris=["s3://bucket/file.txt"],
                registry="s3://test-registry",
            )
        assert "Package name must be in 'user/package' format" in str(exc_info.value)

        # Test invalid registry
        with pytest.raises(ValidationError) as exc_info:
            backend.update_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/file.txt"],
                registry="not-s3-uri",
            )
        assert "Registry must be an S3 URI" in str(exc_info.value)

        # Test empty S3 URIs
        with pytest.raises(ValidationError) as exc_info:
            backend.update_package_revision(
                package_name="user/package",
                s3_uris=[],
                registry="s3://test-registry",
            )
        assert "S3 URIs must be a non-empty list" in str(exc_info.value)

    def test_update_package_revision_browse_error(self, backend):
        """Test error handling when browsing existing package fails."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_quilt3.Package.browse.side_effect = Exception("Package not found")

            with pytest.raises(BackendError) as exc_info:
                backend.update_package_revision(
                    package_name="user/package",
                    s3_uris=["s3://bucket/file.txt"],
                    registry="s3://test-registry",
                )

            assert "Quilt3 backend update_package_revision failed" in str(exc_info.value)
            assert "Package not found" in str(exc_info.value)

    def test_update_package_revision_push_error(self, backend):
        """Test error handling when push fails."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_existing_pkg = Mock()
            mock_existing_pkg.meta = {}
            mock_quilt3.Package.browse.return_value = mock_existing_pkg
            mock_existing_pkg.push.side_effect = Exception("Push failed")

            with pytest.raises(BackendError) as exc_info:
                backend.update_package_revision(
                    package_name="user/package",
                    s3_uris=["s3://bucket/file.txt"],
                    registry="s3://test-registry",
                )

            assert "Quilt3 backend update_package_revision failed" in str(exc_info.value)
            assert "Push failed" in str(exc_info.value)

    def test_update_package_revision_push_returns_none(self, backend):
        """Test handling when push returns None (failed push)."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_existing_pkg = Mock()
            mock_existing_pkg.meta = {}
            mock_quilt3.Package.browse.return_value = mock_existing_pkg
            mock_existing_pkg.push.return_value = None  # Failed push

            result = backend.update_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/file1.txt", "s3://bucket/file2.txt"],
                registry="s3://test-registry",
            )

            assert result.success is False
            assert result.top_hash == ""
            assert result.file_count == 2

    def test_update_package_revision_metadata_merge_error(self, backend):
        """Test handling when metadata merging fails."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_existing_pkg = Mock()
            mock_existing_pkg.meta = {}
            mock_existing_pkg.set_meta.side_effect = Exception("Metadata error")
            mock_quilt3.Package.browse.return_value = mock_existing_pkg
            mock_existing_pkg.push.return_value = "test-hash"

            # Should not raise exception, just log warning and continue
            result = backend.update_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/file.txt"],
                registry="s3://test-registry",
                metadata={"test": "value"},
            )

            # Update should still succeed despite metadata error
            assert result.success is True
            assert result.top_hash == "test-hash"

    def test_update_package_revision_result_generation(self, backend):
        """Test Package_Creation_Result generation."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_existing_pkg = Mock()
            mock_existing_pkg.meta = {}
            mock_quilt3.Package.browse.return_value = mock_existing_pkg
            mock_existing_pkg.push.return_value = "final123hash456"

            result = backend.update_package_revision(
                package_name="user/test-package",
                s3_uris=["s3://bucket/file1.txt", "s3://bucket/folder/file2.csv", "s3://bucket/file3.json"],
                registry="s3://my-registry",
                message="Custom update message",
            )

            assert result.success is True
            assert result.package_name == "user/test-package"
            assert result.top_hash == "final123hash456"
            assert result.registry == "s3://my-registry"
            assert result.file_count == 3
            assert result.catalog_url is not None  # Should generate catalog URL
