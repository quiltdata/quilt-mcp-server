"""
Tests for Quilt3_Backend package operations, specifically create_package_revision().

This module tests the Quilt3_Backend implementation of package operations
following TDD principles, with focus on create_package_revision() method.
"""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.ops.exceptions import ValidationError, BackendError
from quilt_mcp.domain.package_creation import Package_Creation_Result


class TestQuilt3BackendCreatePackageRevisionValidation:
    """Test validation logic in Quilt3_Backend create_package_revision implementation."""

    @pytest.fixture
    def backend(self):
        """Create Quilt3_Backend instance for testing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    def test_validate_package_creation_inputs_empty_package_name(self, backend):
        """Test validation fails for empty package name."""
        with pytest.raises(ValidationError) as exc_info:
            backend._validate_package_creation_inputs("", ["s3://bucket/file.txt"])

        assert "Package name must be a non-empty string" in str(exc_info.value)
        assert exc_info.value.context["field"] == "package_name"

    def test_validate_package_creation_inputs_invalid_package_format(self, backend):
        """Test validation fails for invalid package name format."""
        invalid_names = ["no-slash", "/starts-with-slash", "too/many/slashes"]

        for invalid_name in invalid_names:
            with pytest.raises(ValidationError) as exc_info:
                backend._validate_package_creation_inputs(invalid_name, ["s3://bucket/file.txt"])

            assert "Package name must be in 'user/package' format" in str(exc_info.value)

    def test_validate_package_creation_inputs_empty_s3_uris(self, backend):
        """Test validation fails for empty S3 URIs list."""
        with pytest.raises(ValidationError) as exc_info:
            backend._validate_package_creation_inputs("user/package", [])

        assert "S3 URIs must be a non-empty list" in str(exc_info.value)

    def test_validate_package_creation_inputs_invalid_s3_uri_format(self, backend):
        """Test validation fails for invalid S3 URI formats."""
        test_cases = [
            (["not-s3-uri"], "must start with 's3://'"),
            (["s3://bucket"], "must include bucket and key"),
        ]

        for invalid_uris, expected_error in test_cases:
            with pytest.raises(ValidationError) as exc_info:
                backend._validate_package_creation_inputs("user/package", invalid_uris)

            assert expected_error in str(exc_info.value)

    def test_validate_package_creation_inputs_mixed_valid_invalid_uris(self, backend):
        """Test validation fails when list contains both valid and invalid URIs."""
        mixed_uris = ["s3://bucket/valid.txt", "invalid-uri"]

        with pytest.raises(ValidationError) as exc_info:
            backend._validate_package_creation_inputs("user/package", mixed_uris)

        assert "Invalid S3 URI at index 1" in str(exc_info.value)


class TestQuilt3BackendLogicalKeyExtraction:
    """Test logical key extraction logic in Quilt3_Backend."""

    @pytest.fixture
    def backend(self):
        """Create Quilt3_Backend instance for testing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    def test_extract_logical_key_auto_organize_true(self, backend):
        """Test logical key extraction with auto_organize=True preserves folder structure."""
        test_cases = [
            ("s3://bucket/file.txt", "file.txt"),
            ("s3://bucket/folder/file.txt", "folder/file.txt"),
            ("s3://bucket/path/to/deep/file.csv", "path/to/deep/file.csv"),
        ]

        for s3_uri, expected_key in test_cases:
            result = backend._extract_logical_key(s3_uri, auto_organize=True)
            assert result == expected_key

    def test_extract_logical_key_auto_organize_false(self, backend):
        """Test logical key extraction with auto_organize=False flattens to filename."""
        test_cases = [
            ("s3://bucket/file.txt", "file.txt"),
            ("s3://bucket/folder/file.txt", "file.txt"),
            ("s3://bucket/path/to/deep/file.csv", "file.csv"),
        ]

        for s3_uri, expected_key in test_cases:
            result = backend._extract_logical_key(s3_uri, auto_organize=False)
            assert result == expected_key


class TestQuilt3BackendCatalogUrlGeneration:
    """Test catalog URL generation logic in Quilt3_Backend."""

    @pytest.fixture
    def backend(self):
        """Create Quilt3_Backend instance for testing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    def test_build_catalog_url_success(self, backend):
        """Test successful catalog URL generation."""
        result = backend._build_catalog_url("user/package", "s3://my-registry-bucket")

        assert result is not None
        assert "my-registry-bucket" in result
        assert "user/package" in result
        assert result.startswith("https://")


class TestQuilt3BackendCreatePackageRevisionImplementation:
    """Test the full create_package_revision implementation in Quilt3_Backend."""

    @pytest.fixture
    def backend(self):
        """Create Quilt3_Backend instance for testing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    def test_create_package_revision_successful_creation(self, backend):
        """Test successful package creation and push."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_package = Mock()
            mock_quilt3.Package.return_value = mock_package
            mock_package.push.return_value = "abc123def456"

            with patch.object(backend, 'get_registry_url', return_value="s3://default-registry"):
                result = backend.create_package_revision(
                    package_name="user/package",
                    s3_uris=["s3://bucket/file1.txt", "s3://bucket/folder/file2.csv"],
                    metadata={"description": "Test package"},
                    message="Test commit",
                )

            # Verify package creation workflow
            mock_quilt3.Package.assert_called_once()
            assert mock_package.set.call_count == 2
            mock_package.set.assert_any_call("file1.txt", "s3://bucket/file1.txt")
            mock_package.set.assert_any_call("folder/file2.csv", "s3://bucket/folder/file2.csv")
            mock_package.set_meta.assert_called_once_with({"description": "Test package"})

            # Verify result
            assert result.success is True
            assert result.package_name == "user/package"
            assert result.top_hash == "abc123def456"
            assert result.file_count == 2

    def test_create_package_revision_with_registry_parameter(self, backend):
        """Test package creation with explicit registry parameter."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_package = Mock()
            mock_quilt3.Package.return_value = mock_package
            mock_package.push.return_value = "test-hash"

            result = backend.create_package_revision(
                package_name="user/package", s3_uris=["s3://bucket/file.txt"], registry="s3://custom-registry"
            )

            push_args = mock_package.push.call_args
            assert push_args[1]['registry'] == "s3://custom-registry"
            assert result.registry == "s3://custom-registry"

    def test_create_package_revision_without_metadata(self, backend):
        """Test package creation without metadata."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_package = Mock()
            mock_quilt3.Package.return_value = mock_package
            mock_package.push.return_value = "test-hash"

            with patch.object(backend, 'get_registry_url', return_value="s3://default-registry"):
                result = backend.create_package_revision(package_name="user/package", s3_uris=["s3://bucket/file.txt"])

            mock_package.set_meta.assert_not_called()
            assert result.success is True

    def test_create_package_revision_copy_behavior(self, backend):
        """Test package creation with copy parameter."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_package = Mock()
            mock_quilt3.Package.return_value = mock_package
            mock_package.push.return_value = "test-hash"

            with patch.object(backend, 'get_registry_url', return_value="s3://default-registry"):
                # Test copy=False uses selector_fn
                result = backend.create_package_revision(
                    package_name="user/package", s3_uris=["s3://bucket/file.txt"], copy=False
                )

                push_args = mock_package.push.call_args
                assert 'selector_fn' in push_args[1]
                assert result.success is True

                # Reset and test copy=True doesn't use selector_fn
                mock_package.reset_mock()
                result = backend.create_package_revision(
                    package_name="user/package", s3_uris=["s3://bucket/file.txt"], copy=True
                )

                push_args = mock_package.push.call_args
                assert 'selector_fn' not in push_args[1]

    def test_create_package_revision_auto_organize_behavior(self, backend):
        """Test package creation with different auto_organize settings."""
        s3_uris = ["s3://bucket/folder/subfolder/file.txt"]

        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_package = Mock()
            mock_quilt3.Package.return_value = mock_package
            mock_package.push.return_value = "test-hash"

            with patch.object(backend, 'get_registry_url', return_value="s3://default-registry"):
                # Test auto_organize=True preserves folder structure
                result = backend.create_package_revision(
                    package_name="user/package", s3_uris=s3_uris, auto_organize=True
                )

                mock_package.set.assert_called_with("folder/subfolder/file.txt", s3_uris[0])
                assert result.success is True

                # Test auto_organize=False flattens to filename
                mock_package.reset_mock()
                result = backend.create_package_revision(
                    package_name="user/package2", s3_uris=s3_uris, auto_organize=False
                )

                mock_package.set.assert_called_with("file.txt", s3_uris[0])
                assert result.success is True


class TestQuilt3BackendCreatePackageRevisionErrorHandling:
    """Test error handling in create_package_revision implementation."""

    @pytest.fixture
    def backend(self):
        """Create Quilt3_Backend instance for testing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    def test_validation_error_propagation(self, backend):
        """Test that ValidationError is propagated without wrapping."""
        with pytest.raises(ValidationError) as exc_info:
            backend.create_package_revision(
                package_name="invalid-name",  # No slash
                s3_uris=["s3://bucket/file.txt"],
            )

        assert "Package name must be in 'user/package' format" in str(exc_info.value)

    def test_package_creation_error_wrapped_in_backend_error(self, backend):
        """Test that package creation errors are wrapped in BackendError."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_quilt3.Package.side_effect = Exception("Package creation failed")

            with pytest.raises(BackendError) as exc_info:
                backend.create_package_revision(package_name="user/package", s3_uris=["s3://bucket/file.txt"])

            assert "Quilt3 backend create_package_revision failed" in str(exc_info.value)
            assert "Package creation failed" in str(exc_info.value)

    def test_package_push_error_wrapped_in_backend_error(self, backend):
        """Test that package.push() errors are wrapped in BackendError."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_package = Mock()
            mock_quilt3.Package.return_value = mock_package
            mock_package.push.side_effect = Exception("Registry not accessible")

            with pytest.raises(BackendError) as exc_info:
                backend.create_package_revision(package_name="user/package", s3_uris=["s3://bucket/file.txt"])

            assert "Quilt3 backend create_package_revision failed" in str(exc_info.value)

    def test_push_failure_returns_failed_result(self, backend):
        """Test that push returning None/empty results in failed Package_Creation_Result."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_package = Mock()
            mock_quilt3.Package.return_value = mock_package
            mock_package.push.return_value = None  # Failed push

            with patch.object(backend, 'get_registry_url', return_value="s3://test-registry"):
                result = backend.create_package_revision(
                    package_name="user/package", s3_uris=["s3://bucket/file1.txt", "s3://bucket/file2.txt"]
                )

            assert result.success is False
            assert result.top_hash == ""
            assert result.file_count == 2


class TestQuilt3BackendCreatePackageRevisionResultGeneration:
    """Test Package_Creation_Result generation in create_package_revision."""

    @pytest.fixture
    def backend(self):
        """Create Quilt3_Backend instance for testing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    def test_successful_result_with_explicit_registry(self, backend):
        """Test successful result generation with explicit registry."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_package = Mock()
            mock_quilt3.Package.return_value = mock_package
            mock_package.push.return_value = "abc123def456"

            result = backend.create_package_revision(
                package_name="user/package",
                s3_uris=["s3://bucket/file1.txt", "s3://bucket/file2.txt"],
                registry="s3://custom-registry",
                metadata={"version": "1.0"},
            )

            assert result.success is True
            assert result.package_name == "user/package"
            assert result.top_hash == "abc123def456"
            assert result.registry == "s3://custom-registry"
            assert result.file_count == 2
            assert result.catalog_url is not None

    def test_successful_result_without_registry_param(self, backend):
        """Test result generation when no registry parameter provided (no default bucket exists)."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_package = Mock()
            mock_quilt3.Package.return_value = mock_package
            mock_package.push.return_value = "xyz789abc123"
            mock_quilt3.logged_in.return_value = None

            result = backend.create_package_revision(package_name="user/package", s3_uris=["s3://bucket/file.txt"])

            assert result.success is True
            assert result.registry == "s3://unknown-registry"  # No default - must be provided explicitly
            assert result.catalog_url is None  # Can't build without logged-in catalog

    def test_failed_result_generation(self, backend):
        """Test failed result generation when push fails."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            mock_package = Mock()
            mock_quilt3.Package.return_value = mock_package
            mock_package.push.return_value = None

            with patch.object(backend, 'get_registry_url', return_value="s3://test-registry"):
                result = backend.create_package_revision(
                    package_name="user/package", s3_uris=["s3://bucket/file1.txt", "s3://bucket/file2.txt"]
                )

            assert result.success is False
            assert result.top_hash == ""
            assert result.file_count == 2


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


class TestQuilt3BackendDiffPackages:
    """Test diff_packages method implementation in Quilt3_Backend."""

    @pytest.fixture
    def backend(self):
        """Create Quilt3_Backend instance for testing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    def test_diff_packages_without_hashes(self, backend):
        """Test package diffing without specific hashes (uses latest versions)."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff result as tuple (added, deleted, modified)
            mock_pkg1.diff.return_value = (
                ["new_file.txt", "folder/added.csv"],
                ["old_file.txt"],
                ["modified_file.txt", "data/changed.json"],
            )

            result = backend.diff_packages(
                package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
            )

            # Verify Package.browse calls
            assert mock_quilt3.Package.browse.call_count == 2
            mock_quilt3.Package.browse.assert_any_call("user/package1", registry="s3://test-registry")
            mock_quilt3.Package.browse.assert_any_call("user/package2", registry="s3://test-registry")

            # Verify diff call
            mock_pkg1.diff.assert_called_once_with(mock_pkg2)

            # Verify result format
            expected_result = {
                "added": ["new_file.txt", "folder/added.csv"],
                "deleted": ["old_file.txt"],
                "modified": ["modified_file.txt", "data/changed.json"],
            }
            assert result == expected_result

    def test_diff_packages_with_hashes(self, backend):
        """Test package diffing with specific hashes."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff result
            mock_pkg1.diff.return_value = ([], ["removed.txt"], [])

            result = backend.diff_packages(
                package1_name="user/package1",
                package2_name="user/package2",
                registry="s3://test-registry",
                package1_hash="abc123",
                package2_hash="def456",
            )

            # Verify Package.browse calls with hashes
            mock_quilt3.Package.browse.assert_any_call(
                "user/package1", registry="s3://test-registry", top_hash="abc123"
            )
            mock_quilt3.Package.browse.assert_any_call(
                "user/package2", registry="s3://test-registry", top_hash="def456"
            )

            # Verify result
            expected_result = {"added": [], "deleted": ["removed.txt"], "modified": []}
            assert result == expected_result

    def test_diff_packages_conditional_hash_handling(self, backend):
        """Test conditional hash handling logic."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff result
            mock_pkg1.diff.return_value = ([], [], ["updated.txt"])

            # Test with only package1_hash provided
            result = backend.diff_packages(
                package1_name="user/package1",
                package2_name="user/package2",
                registry="s3://test-registry",
                package1_hash="abc123",
                package2_hash=None,
            )

            # Verify first call has hash, second doesn't
            mock_quilt3.Package.browse.assert_any_call(
                "user/package1", registry="s3://test-registry", top_hash="abc123"
            )
            mock_quilt3.Package.browse.assert_any_call("user/package2", registry="s3://test-registry")

    def test_diff_packages_tuple_to_dict_transformation(self, backend):
        """Test tuple-to-dict transformation logic."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Test with empty tuple elements
            mock_pkg1.diff.return_value = ([], None, ["modified.txt"])

            result = backend.diff_packages(
                package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
            )

            # Verify empty/None values are handled correctly
            expected_result = {"added": [], "deleted": [], "modified": ["modified.txt"]}
            assert result == expected_result

    def test_diff_packages_non_tuple_result_handling(self, backend):
        """Test handling of non-tuple diff results."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff result as dict (unexpected format)
            mock_pkg1.diff.return_value = {"added": ["file1.txt"], "deleted": ["file2.txt"], "modified": ["file3.txt"]}

            result = backend.diff_packages(
                package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
            )

            # Should return the dict as-is
            expected_result = {"added": ["file1.txt"], "deleted": ["file2.txt"], "modified": ["file3.txt"]}
            assert result == expected_result

    def test_diff_packages_unexpected_result_format(self, backend):
        """Test handling of completely unexpected diff result format."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff result as string (unexpected format)
            mock_pkg1.diff.return_value = "unexpected result"

            result = backend.diff_packages(
                package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
            )

            # Should wrap in raw format
            expected_result = {"raw": ["unexpected result"]}
            assert result == expected_result

    def test_diff_packages_error_handling_package_not_found(self, backend):
        """Test error handling for missing packages."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock Package.browse to raise exception for first package
            mock_quilt3.Package.browse.side_effect = Exception("Package 'user/package1' not found")

            with pytest.raises(BackendError) as exc_info:
                backend.diff_packages(
                    package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
                )

            assert "Quilt3 backend diff_packages failed" in str(exc_info.value)
            assert "Package 'user/package1' not found" in str(exc_info.value)

            # Verify error context
            assert exc_info.value.context['package1_name'] == "user/package1"
            assert exc_info.value.context['package2_name'] == "user/package2"
            assert exc_info.value.context['registry'] == "s3://test-registry"

    def test_diff_packages_error_handling_invalid_hash(self, backend):
        """Test error handling for invalid hashes."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock Package.browse to raise exception for invalid hash
            mock_quilt3.Package.browse.side_effect = Exception("Invalid hash: invalid-hash")

            with pytest.raises(BackendError) as exc_info:
                backend.diff_packages(
                    package1_name="user/package1",
                    package2_name="user/package2",
                    registry="s3://test-registry",
                    package1_hash="invalid-hash",
                )

            assert "Quilt3 backend diff_packages failed" in str(exc_info.value)
            assert "Invalid hash: invalid-hash" in str(exc_info.value)

            # Verify error context includes hash
            assert exc_info.value.context['package1_hash'] == "invalid-hash"

    def test_diff_packages_error_handling_diff_operation_failure(self, backend):
        """Test error handling for diff operation failure."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock diff to raise exception
            mock_pkg1.diff.side_effect = Exception("Diff operation failed")

            with pytest.raises(BackendError) as exc_info:
                backend.diff_packages(
                    package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
                )

            assert "Quilt3 backend diff_packages failed" in str(exc_info.value)
            assert "Diff operation failed" in str(exc_info.value)

    def test_diff_packages_domain_dict_format_verification(self, backend):
        """Test that the method returns the correct domain dict format."""
        with patch.object(backend, 'quilt3') as mock_quilt3:
            # Mock package objects
            mock_pkg1 = Mock()
            mock_pkg2 = Mock()

            # Mock Package.browse calls
            mock_quilt3.Package.browse.side_effect = [mock_pkg1, mock_pkg2]

            # Mock comprehensive diff result
            mock_pkg1.diff.return_value = (
                ["added1.txt", "added2.csv", "folder/added3.json"],
                ["deleted1.txt", "deleted2.log"],
                ["modified1.txt", "data/modified2.csv", "config/modified3.yaml"],
            )

            result = backend.diff_packages(
                package1_name="user/package1", package2_name="user/package2", registry="s3://test-registry"
            )

            # Verify result is a dict with correct keys
            assert isinstance(result, dict)
            assert set(result.keys()) == {"added", "deleted", "modified"}

            # Verify all values are lists of strings
            for key, value in result.items():
                assert isinstance(value, list)
                for item in value:
                    assert isinstance(item, str)

            # Verify specific content
            assert len(result["added"]) == 3
            assert len(result["deleted"]) == 2
            assert len(result["modified"]) == 3

            # Verify string conversion works for path objects
            assert "added1.txt" in result["added"]
            assert "folder/added3.json" in result["added"]
