"""Tests for Quilt3Backend implementation.

This test module validates that Quilt3Backend correctly wraps QuiltService
and implements the QuiltBackend protocol.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestQuilt3BackendInstantiation:
    """Test Quilt3Backend instantiation and initialization."""

    def test_backend_module_exists(self):
        """Test that quilt3_backend module exists."""
        from quilt_mcp.backends import quilt3_backend

        assert quilt3_backend is not None

    def test_quilt3_backend_class_exists(self):
        """Test that Quilt3Backend class is defined."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        assert Quilt3Backend is not None

    def test_backend_instantiates(self):
        """Test that Quilt3Backend can be instantiated."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        assert backend is not None

    def test_backend_wraps_quilt_service(self):
        """Test that Quilt3Backend wraps a QuiltService instance."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        assert hasattr(backend, '_service')
        assert backend._service is not None


class TestQuilt3BackendProtocolCompliance:
    """Test that Quilt3Backend satisfies QuiltBackend protocol."""

    def test_backend_implements_protocol(self):
        """Test that Quilt3Backend implements QuiltBackend protocol."""
        from quilt_mcp.backends.protocol import QuiltBackend
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        # Runtime check that backend satisfies protocol
        assert isinstance(backend, QuiltBackend)

    def test_all_protocol_methods_present(self):
        """Test that Quilt3Backend has all protocol methods."""
        from quilt_mcp.backends.protocol import QuiltBackend
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        protocol_methods = [
            name
            for name in dir(QuiltBackend)
            if not name.startswith('_') and callable(getattr(QuiltBackend, name, None))
        ]

        for method_name in protocol_methods:
            assert hasattr(backend, method_name), f"Missing method: {method_name}"
            assert callable(getattr(backend, method_name)), f"{method_name} is not callable"


class TestQuilt3BackendAuthMethods:
    """Test authentication and configuration methods."""

    def test_is_authenticated_delegates(self):
        """Test is_authenticated() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        with patch.object(backend._service, 'is_authenticated', return_value=True) as mock_method:
            result = backend.is_authenticated()
            assert result is True
            mock_method.assert_called_once()

    def test_get_logged_in_url_delegates(self):
        """Test get_logged_in_url() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        with patch.object(backend._service, 'get_logged_in_url', return_value="https://example.com") as mock_method:
            result = backend.get_logged_in_url()
            assert result == "https://example.com"
            mock_method.assert_called_once()

    def test_get_config_delegates(self):
        """Test get_config() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        expected_config = {"navigator_url": "https://example.com"}
        with patch.object(backend._service, 'get_config', return_value=expected_config) as mock_method:
            result = backend.get_config()
            assert result == expected_config
            mock_method.assert_called_once()

    def test_set_config_delegates(self):
        """Test set_config() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        with patch.object(backend._service, 'set_config') as mock_method:
            backend.set_config("https://example.com")
            mock_method.assert_called_once_with("https://example.com")

    def test_get_catalog_info_delegates(self):
        """Test get_catalog_info() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        expected_info = {"catalog_name": "test", "is_authenticated": True}
        with patch.object(backend._service, 'get_catalog_info', return_value=expected_info) as mock_method:
            result = backend.get_catalog_info()
            assert result == expected_info
            mock_method.assert_called_once()


class TestQuilt3BackendSessionMethods:
    """Test session and GraphQL methods."""

    def test_has_session_support_delegates(self):
        """Test has_session_support() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        with patch.object(backend._service, 'has_session_support', return_value=True) as mock_method:
            result = backend.has_session_support()
            assert result is True
            mock_method.assert_called_once()

    def test_get_session_delegates(self):
        """Test get_session() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        mock_session = Mock()
        with patch.object(backend._service, 'get_session', return_value=mock_session) as mock_method:
            result = backend.get_session()
            assert result is mock_session
            mock_method.assert_called_once()

    def test_get_registry_url_delegates(self):
        """Test get_registry_url() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        with patch.object(backend._service, 'get_registry_url', return_value="https://registry.com") as mock_method:
            result = backend.get_registry_url()
            assert result == "https://registry.com"
            mock_method.assert_called_once()

    def test_create_botocore_session_delegates(self):
        """Test create_botocore_session() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        mock_boto_session = Mock()
        with patch.object(backend._service, 'create_botocore_session', return_value=mock_boto_session) as mock_method:
            result = backend.create_botocore_session()
            assert result is mock_boto_session
            mock_method.assert_called_once()


class TestQuilt3BackendPackageMethods:
    """Test package operation methods."""

    def test_create_package_revision_delegates(self):
        """Test create_package_revision() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        expected_result = {"status": "success", "top_hash": "abc123"}
        with patch.object(backend._service, 'create_package_revision', return_value=expected_result) as mock_method:
            result = backend.create_package_revision(
                package_name="test/package", s3_uris=["s3://bucket/key"], metadata={"key": "value"}
            )
            assert result == expected_result
            # Backend passes all parameters including defaults
            mock_method.assert_called_once_with(
                package_name="test/package",
                s3_uris=["s3://bucket/key"],
                metadata={"key": "value"},
                registry=None,
                message="Package created via QuiltService",
                auto_organize=True,
                copy="all",
            )

    def test_browse_package_delegates(self):
        """Test browse_package() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        mock_package = Mock()
        with patch.object(backend._service, 'browse_package', return_value=mock_package) as mock_method:
            result = backend.browse_package(package_name="test/package", registry="s3://bucket")
            assert result is mock_package
            # Backend passes all parameters including defaults
            mock_method.assert_called_once_with(package_name="test/package", registry="s3://bucket", top_hash=None)

    def test_list_packages_delegates(self):
        """Test list_packages() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        expected_packages = iter(["test/package1", "test/package2"])
        with patch.object(backend._service, 'list_packages', return_value=expected_packages) as mock_method:
            result = backend.list_packages(registry="s3://bucket")
            assert result is expected_packages
            mock_method.assert_called_once_with(registry="s3://bucket")


class TestQuilt3BackendBucketMethods:
    """Test bucket operation methods."""

    def test_create_bucket_delegates(self):
        """Test create_bucket() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        mock_bucket = Mock()
        with patch.object(backend._service, 'create_bucket', return_value=mock_bucket) as mock_method:
            result = backend.create_bucket(bucket_uri="s3://bucket")
            assert result is mock_bucket
            mock_method.assert_called_once_with(bucket_uri="s3://bucket")


class TestQuilt3BackendSearchMethods:
    """Test search operation methods."""

    def test_get_search_api_delegates(self):
        """Test get_search_api() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        mock_api = Mock()
        with patch.object(backend._service, 'get_search_api', return_value=mock_api) as mock_method:
            result = backend.get_search_api()
            assert result is mock_api
            mock_method.assert_called_once()


class TestQuilt3BackendAdminMethods:
    """Test admin operation methods."""

    def test_is_admin_available_delegates(self):
        """Test is_admin_available() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        with patch.object(backend._service, 'is_admin_available', return_value=True) as mock_method:
            result = backend.is_admin_available()
            assert result is True
            mock_method.assert_called_once()

    def test_get_tabulator_admin_delegates(self):
        """Test get_tabulator_admin() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        mock_admin = Mock()
        with patch.object(backend._service, 'get_tabulator_admin', return_value=mock_admin) as mock_method:
            result = backend.get_tabulator_admin()
            assert result is mock_admin
            mock_method.assert_called_once()

    def test_get_users_admin_delegates(self):
        """Test get_users_admin() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        mock_admin = Mock()
        with patch.object(backend._service, 'get_users_admin', return_value=mock_admin) as mock_method:
            result = backend.get_users_admin()
            assert result is mock_admin
            mock_method.assert_called_once()

    def test_get_roles_admin_delegates(self):
        """Test get_roles_admin() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        mock_admin = Mock()
        with patch.object(backend._service, 'get_roles_admin', return_value=mock_admin) as mock_method:
            result = backend.get_roles_admin()
            assert result is mock_admin
            mock_method.assert_called_once()

    def test_get_sso_config_admin_delegates(self):
        """Test get_sso_config_admin() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        mock_admin = Mock()
        with patch.object(backend._service, 'get_sso_config_admin', return_value=mock_admin) as mock_method:
            result = backend.get_sso_config_admin()
            assert result is mock_admin
            mock_method.assert_called_once()

    def test_get_admin_exceptions_delegates(self):
        """Test get_admin_exceptions() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        expected_exceptions = {'Quilt3AdminError': Exception}
        with patch.object(backend._service, 'get_admin_exceptions', return_value=expected_exceptions) as mock_method:
            result = backend.get_admin_exceptions()
            assert result == expected_exceptions
            mock_method.assert_called_once()


class TestQuilt3BackendBackwardCompatibility:
    """Test backward compatibility methods."""

    def test_get_quilt3_module_delegates(self):
        """Test get_quilt3_module() delegates to QuiltService."""
        from quilt_mcp.backends.quilt3_backend import Quilt3Backend

        backend = Quilt3Backend()
        mock_module = Mock()
        with patch.object(backend._service, 'get_quilt3_module', return_value=mock_module) as mock_method:
            result = backend.get_quilt3_module()
            assert result is mock_module
            mock_method.assert_called_once()
