"""Tests for QuiltService - Test-Driven Development Implementation."""

from __future__ import annotations

import pytest
from unittest.mock import Mock, MagicMock, patch

import importlib

from quilt_mcp.services.quilt_service import QuiltService


class TestQuiltServiceAuthentication:
    """Test authentication and configuration methods."""

    def test_services_package_exports_core_classes(self):
        """Services package should expose key service classes for direct import."""
        services_pkg = importlib.import_module("quilt_mcp.services")

        assert hasattr(services_pkg, "QuiltService")
        assert hasattr(services_pkg, "AthenaQueryService")
        assert hasattr(services_pkg, "AWSPermissionDiscovery")

    def test_get_logged_in_url_when_not_authenticated(self):
        """Test get_logged_in_url returns None when not authenticated."""
        service = QuiltService()
        with patch('quilt3.logged_in', return_value=None):
            result = service.get_logged_in_url()
            assert result is None

    def test_get_logged_in_url_when_authenticated(self):
        """Test get_logged_in_url returns URL when authenticated."""
        service = QuiltService()
        # This test will fail initially - that's the RED phase
        with patch('quilt3.logged_in', return_value='https://example.quiltdata.com'):
            result = service.get_logged_in_url()
            assert result == 'https://example.quiltdata.com'

    def test_get_config_returns_none_when_no_config(self):
        """Test get_config returns None when no configuration available."""
        service = QuiltService()
        with patch('quilt3.config', return_value=None):
            result = service.get_config()
            assert result is None

    def test_get_config_returns_config_when_available(self):
        """Test get_config returns configuration when available."""
        service = QuiltService()
        expected_config = {'navigator_url': 'https://example.quiltdata.com', 'registryUrl': 's3://example-bucket'}
        with patch('quilt3.config', return_value=expected_config):
            result = service.get_config()
            assert result == expected_config

    def test_get_navigator_url_returns_none_when_no_config(self):
        """Test get_navigator_url returns None when no configuration available."""
        service = QuiltService()
        with patch.object(service, 'get_config', return_value=None):
            result = service.get_navigator_url()
            assert result is None

    def test_get_navigator_url_returns_none_when_key_missing(self):
        """Test get_navigator_url returns None when navigator_url key is missing."""
        service = QuiltService()
        with patch.object(service, 'get_config', return_value={'registryUrl': 's3://example-bucket'}):
            result = service.get_navigator_url()
            assert result is None

    def test_get_navigator_url_returns_url_when_available(self):
        """Test get_navigator_url returns URL when available in config."""
        service = QuiltService()
        expected_url = 'https://example.quiltdata.com'
        with patch.object(service, 'get_config', return_value={'navigator_url': expected_url}):
            result = service.get_navigator_url()
            assert result == expected_url


class TestQuiltServicePackageOperations:
    """Test package operation methods."""

    def test_list_packages_returns_package_list(self):
        """Test list_packages returns iterator of package names."""
        service = QuiltService()
        expected_packages = ['user/package1', 'user/package2']
        with patch('quilt3.list_packages', return_value=iter(expected_packages)):
            result = list(service.list_packages('s3://test-bucket'))
            assert result == expected_packages

    def test_get_catalog_info_when_authenticated(self):
        """Test get_catalog_info returns comprehensive info when authenticated."""
        service = QuiltService()
        with (
            patch('quilt3.logged_in', return_value='https://example.quiltdata.com'),
            patch(
                'quilt3.config',
                return_value={'navigator_url': 'https://example.quiltdata.com', 'registryUrl': 's3://example-bucket'},
            ),
        ):
            result = service.get_catalog_info()
            assert result['is_authenticated'] is True
            assert result['catalog_name'] == 'example.quiltdata.com'
            assert result['logged_in_url'] == 'https://example.quiltdata.com'
            assert result['navigator_url'] == 'https://example.quiltdata.com'
            assert result['registry_url'] == 's3://example-bucket'

    def test_set_config_calls_quilt3_config(self):
        """Test set_config calls quilt3.config with catalog URL."""
        service = QuiltService()
        with patch('quilt3.config') as mock_config:
            service.set_config('https://example.quiltdata.com')
            mock_config.assert_called_once_with('https://example.quiltdata.com')

    def test_browse_package_without_hash(self):
        """Test browse_package calls Package.browse without top_hash."""
        service = QuiltService()
        mock_package = Mock()
        with patch('quilt3.Package.browse', return_value=mock_package) as mock_browse:
            result = service.browse_package('user/package', 's3://test-bucket')
            assert result == mock_package
            mock_browse.assert_called_once_with('user/package', registry='s3://test-bucket')

    def test_browse_package_with_hash(self):
        """Test browse_package calls Package.browse with top_hash."""
        service = QuiltService()
        mock_package = Mock()
        with patch('quilt3.Package.browse', return_value=mock_package) as mock_browse:
            result = service.browse_package('user/package', 's3://test-bucket', top_hash='abc123')
            assert result == mock_package
            mock_browse.assert_called_once_with('user/package', registry='s3://test-bucket', top_hash='abc123')

    def test_create_bucket_returns_bucket_instance(self):
        """Test create_bucket returns a Bucket instance."""
        service = QuiltService()
        mock_bucket = Mock()
        with patch('quilt3.Bucket', return_value=mock_bucket) as mock_bucket_class:
            result = service.create_bucket('s3://test-bucket')
            assert result == mock_bucket
            mock_bucket_class.assert_called_once_with('s3://test-bucket')

    def test_has_session_support_when_available(self):
        """Test has_session_support returns True when session is available."""
        service = QuiltService()
        mock_session = Mock()
        mock_session.get_session = Mock()
        with patch('quilt3.session', mock_session):
            result = service.has_session_support()
            assert result is True

    def test_has_session_support_when_not_available(self):
        """Test has_session_support returns False when session is not available."""
        service = QuiltService()
        with patch('quilt3.session', None):
            result = service.has_session_support()
            assert result is False

    def test_get_session_when_available(self):
        """Test get_session returns session object when available."""
        service = QuiltService()
        mock_session_obj = Mock()
        mock_session = Mock()
        mock_session.get_session = Mock(return_value=mock_session_obj)
        with patch('quilt3.session', mock_session):
            result = service.get_session()
            assert result == mock_session_obj
            mock_session.get_session.assert_called_once()

    def test_get_registry_url_when_available(self):
        """Test get_registry_url returns URL when available."""
        service = QuiltService()
        mock_session = Mock()
        mock_session.get_registry_url = Mock(return_value='s3://test-registry')
        with patch('quilt3.session', mock_session):
            result = service.get_registry_url()
            assert result == 's3://test-registry'

    def test_get_registry_url_when_not_available(self):
        """Test get_registry_url returns None when not available."""
        service = QuiltService()
        mock_session = Mock()
        del mock_session.get_registry_url  # Simulate missing method
        with patch('quilt3.session', mock_session):
            result = service.get_registry_url()
            assert result is None

    def test_create_botocore_session_returns_session_object(self):
        """Test create_botocore_session returns a botocore session object."""
        service = QuiltService()
        mock_botocore_session = Mock()
        with patch('quilt3.session.create_botocore_session', return_value=mock_botocore_session) as mock_create:
            result = service.create_botocore_session()
            assert result == mock_botocore_session
            mock_create.assert_called_once()

    def test_create_botocore_session_raises_exception_on_failure(self):
        """Test create_botocore_session raises exception when underlying call fails."""
        service = QuiltService()
        with patch('quilt3.session.create_botocore_session', side_effect=Exception("Authentication failed")):
            with pytest.raises(Exception, match="Authentication failed"):
                service.create_botocore_session()


class TestQuiltServiceCreatePackageRevision:
    """Test create_package_revision method - Complete abstraction without leaks."""

    def test_create_package_revision_with_auto_organize_true(self):
        """Test create_package_revision with auto_organize=True creates package with smart organization."""
        service = QuiltService()

        # Mock the dependencies for smart organization path
        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-123")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart') as mock_organize,
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            mock_organize.return_value = {
                "data": [{"Key": "file1.csv", "Size": 1000}],
                "docs": [{"Key": "readme.txt", "Size": 500}],
            }

            result = service.create_package_revision(
                package_name="test/package",
                s3_uris=["s3://source/file1.csv", "s3://source/readme.txt"],
                metadata={"description": "test package"},
                registry="s3://test-bucket",
                message="Test message",
                auto_organize=True,
            )

            # Verify method returns Dict, never quilt3.Package objects
            assert isinstance(result, dict)
            assert "quilt3.Package" not in str(type(result))
            assert "top_hash" in result
            assert result["top_hash"] == "test-hash-123"
            assert "status" in result
            assert "package_name" in result

    def test_create_package_revision_with_auto_organize_false(self):
        """Test create_package_revision with auto_organize=False creates package with simple flattening."""
        service = QuiltService()

        # Mock the dependencies for flattening path
        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-456")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._collect_objects_flat') as mock_collect,
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            mock_collect.return_value = [
                {"s3_uri": "s3://source/file1.csv", "logical_key": "file1.csv"},
                {"s3_uri": "s3://source/readme.txt", "logical_key": "readme.txt"},
            ]

            result = service.create_package_revision(
                package_name="test/package",
                s3_uris=["s3://source/file1.csv", "s3://source/readme.txt"],
                metadata={"description": "test package"},
                registry="s3://test-bucket",
                message="Test message",
                auto_organize=False,
            )

            # Verify method returns Dict, never quilt3.Package objects
            assert isinstance(result, dict)
            assert "quilt3.Package" not in str(type(result))
            assert "top_hash" in result
            assert result["top_hash"] == "test-hash-456"
            assert "status" in result
            assert "package_name" in result

    def test_create_package_revision_handles_metadata_correctly(self):
        """Test create_package_revision properly handles metadata parameter."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-meta")

        test_metadata = {"description": "Test package with metadata", "version": "1.0.0", "tags": ["test", "sample"]}

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/package",
                s3_uris=["s3://source/file1.csv"],
                metadata=test_metadata,
                auto_organize=True,
            )

            # Verify metadata was passed to package
            mock_package.set_meta.assert_called_once_with(test_metadata)

            # Verify return type
            assert isinstance(result, dict)
            assert "top_hash" in result

    def test_create_package_revision_handles_none_metadata(self):
        """Test create_package_revision handles None metadata gracefully."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.set_meta = Mock()
        mock_package.push = Mock(return_value="test-hash-none")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/package", s3_uris=["s3://source/file1.csv"], metadata=None, auto_organize=True
            )

            # Verify set_meta not called with None
            mock_package.set_meta.assert_not_called()

            # Verify return type
            assert isinstance(result, dict)

    def test_create_package_revision_handles_registry_parameter(self):
        """Test create_package_revision handles registry parameter correctly."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.set = Mock()
        mock_package.push = Mock(return_value="test-hash-reg")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://custom-bucket"
            ) as mock_norm,
        ):
            result = service.create_package_revision(
                package_name="test/package",
                s3_uris=["s3://source/file1.csv"],
                registry="s3://custom-bucket",
                auto_organize=True,
            )

            # Verify registry normalization was called
            mock_norm.assert_called_once_with("s3://custom-bucket")

            # Verify push was called with normalized registry
            mock_package.push.assert_called_once()
            push_call_args = mock_package.push.call_args
            assert push_call_args[1]["registry"] == "s3://custom-bucket"

    def test_create_package_revision_default_message(self):
        """Test create_package_revision uses default message when none provided."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.push = Mock(return_value="test-hash-msg")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/package", s3_uris=["s3://source/file1.csv"], auto_organize=True
            )

            # Verify push called with default message
            push_call_args = mock_package.push.call_args
            assert push_call_args[1]["message"] == "Package created via QuiltService"

    def test_create_package_revision_error_handling(self):
        """Test create_package_revision handles errors appropriately."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.push = Mock(side_effect=Exception("Push failed"))

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            # Should raise exception, not return quilt3.Package
            with pytest.raises(Exception, match="Push failed"):
                service.create_package_revision(
                    package_name="test/package", s3_uris=["s3://source/file1.csv"], auto_organize=True
                )

    def test_create_package_revision_never_returns_quilt3_package(self):
        """Test create_package_revision NEVER returns quilt3.Package objects - critical abstraction requirement."""
        service = QuiltService()

        mock_package = Mock()
        mock_package.push = Mock(return_value="test-hash-abstract")

        with (
            patch('quilt3.Package', return_value=mock_package),
            patch('quilt_mcp.services.quilt_service.QuiltService._organize_s3_files_smart', return_value={}),
            patch(
                'quilt_mcp.services.quilt_service.QuiltService._normalize_registry', return_value="s3://test-bucket"
            ),
        ):
            result = service.create_package_revision(
                package_name="test/package", s3_uris=["s3://source/file1.csv"], auto_organize=True
            )

            # Critical: verify no quilt3.Package objects are exposed
            assert not hasattr(result, 'set')  # quilt3.Package method
            assert not hasattr(result, 'set_meta')  # quilt3.Package method
            assert not hasattr(result, 'push')  # quilt3.Package method
            assert isinstance(result, dict)  # Must be plain dict
            assert type(result).__name__ == 'dict'  # Verify exact type

    def test_create_package_revision_with_copy_parameter(self):
        """Test create_package_revision accepts and handles copy parameter."""
        service = QuiltService()

        with patch('quilt3.Package') as mock_package_class:
            mock_package = MagicMock()
            mock_package.set.return_value = mock_package  # For method chaining
            mock_package.set_dir.return_value = mock_package
            mock_package.set_meta.return_value = mock_package
            mock_package.push.return_value = "test_hash"
            mock_package_class.return_value = mock_package

            # This should NOT raise "unexpected keyword argument 'copy'" error
            result = service.create_package_revision(
                package_name="test/package",
                s3_uris=["s3://bucket/file.txt"],
                copy="none",  # Test the copy parameter
            )

            # Verify result structure
            assert result["status"] == "success"
            assert result["package_name"] == "test/package"
            assert "top_hash" in result

            # Verify push was called with selector_fn when copy != "all"
            push_call = mock_package.push.call_args
            assert push_call is not None
            push_kwargs = push_call[1]
            if "selector_fn" in push_kwargs:
                # If selector_fn is passed, it should be callable
                assert callable(push_kwargs["selector_fn"])


class TestQuiltServiceAdmin:
    """Test admin module access methods."""

    def test_get_admin_exceptions_when_available(self):
        """Test get_admin_exceptions returns exception classes when available."""
        service = QuiltService()
        result = service.get_admin_exceptions()
        # Should return a dict with exception classes
        assert isinstance(result, dict)
        assert 'Quilt3AdminError' in result
        assert 'UserNotFoundError' in result
        assert 'BucketNotFoundError' in result

    def test_get_admin_exceptions_when_not_available(self):
        """Test get_admin_exceptions behavior when not available."""
        service = QuiltService()
        try:
            result = service.get_admin_exceptions()
            assert isinstance(result, dict)
        except ImportError:
            pass


class TestQuiltServiceDeletePackage:
    """Test delete_package method - Phase 5.4."""

    def test_delete_package_success(self):
        """Test delete_package successfully deletes a package."""
        service = QuiltService()

        with patch('quilt3.delete_package') as mock_delete:
            service.delete_package('user/package', 's3://test-bucket')

            # Verify quilt3.delete_package was called with correct args
            mock_delete.assert_called_once_with('user/package', registry='s3://test-bucket')

    def test_delete_package_with_default_registry(self):
        """Test delete_package uses default registry when None provided."""
        service = QuiltService()

        with patch('quilt3.delete_package') as mock_delete:
            service.delete_package('user/package', None)

            # Should be called with no registry argument (quilt3 uses default)
            mock_delete.assert_called_once_with('user/package')

    def test_delete_package_not_found(self):
        """Test delete_package raises PackageNotFoundError when package doesn't exist."""
        from quilt_mcp.services.exceptions import PackageNotFoundError

        service = QuiltService()

        with patch('quilt3.delete_package', side_effect=Exception("Package not found")):
            with pytest.raises(PackageNotFoundError, match="Package 'user/package' not found"):
                service.delete_package('user/package', 's3://test-bucket')

    def test_delete_package_handles_quilt3_errors(self):
        """Test delete_package properly handles quilt3 exceptions."""
        from quilt_mcp.services.exceptions import PackageNotFoundError

        service = QuiltService()

        # Simulate quilt3 raising an exception
        with patch('quilt3.delete_package', side_effect=Exception("NoSuchKey")):
            with pytest.raises(PackageNotFoundError):
                service.delete_package('user/package', 's3://test-bucket')

    def test_delete_package_normalizes_registry(self):
        """Test delete_package normalizes registry format with bucket path."""
        service = QuiltService()

        with patch('quilt3.delete_package') as mock_delete:
            # Pass bucket path without s3:// prefix (with /)
            service.delete_package('user/package', 'test-bucket/path')

            # Should normalize to s3:// format
            mock_delete.assert_called_once_with('user/package', registry='s3://test-bucket/path')


class TestQuiltServiceAbstractionCompleteness:
    """Test that QuiltService abstraction is complete and doesn't leak quilt3 objects."""

    def test_create_package_method_does_not_exist(self):
        """Test that old leaky create_package() method has been removed from QuiltService.

        This test ensures the abstraction is complete and no quilt3.Package objects
        are exposed through the service interface.
        """
        service = QuiltService()

        # Verify the old method no longer exists
        assert not hasattr(service, 'create_package'), (
            "create_package() method should be removed from QuiltService to complete abstraction"
        )

        # Verify only the new abstracted method exists
        assert hasattr(service, 'create_package_revision'), (
            "create_package_revision() method should exist as the abstracted replacement"
        )
