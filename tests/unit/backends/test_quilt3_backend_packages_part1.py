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
