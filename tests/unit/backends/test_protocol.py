"""Tests for QuiltBackend protocol definition.

This test module validates that the QuiltBackend protocol correctly defines
the contract for backend implementations, covering all QuiltService operations.
"""

from typing import Protocol, runtime_checkable
import pytest


def test_protocol_module_exists():
    """Test that the backends.protocol module exists and is importable."""
    from quilt_mcp.backends import protocol

    assert protocol is not None


def test_quilt_backend_protocol_exists():
    """Test that QuiltBackend protocol class is defined."""
    from quilt_mcp.backends.protocol import QuiltBackend

    assert QuiltBackend is not None
    # Verify it's a Protocol
    assert issubclass(QuiltBackend, Protocol)


def test_protocol_is_runtime_checkable():
    """Test that QuiltBackend protocol is runtime checkable."""
    from quilt_mcp.backends.protocol import QuiltBackend

    # Should be decorated with @runtime_checkable
    assert hasattr(QuiltBackend, '__protocol_attrs__')


class TestProtocolAuthenticationMethods:
    """Test that protocol defines all authentication methods."""

    def test_has_is_authenticated_method(self):
        """Test protocol defines is_authenticated() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'is_authenticated')

    def test_has_get_logged_in_url_method(self):
        """Test protocol defines get_logged_in_url() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_logged_in_url')

    def test_has_get_config_method(self):
        """Test protocol defines get_config() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_config')

    def test_has_set_config_method(self):
        """Test protocol defines set_config() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'set_config')

    def test_has_get_catalog_info_method(self):
        """Test protocol defines get_catalog_info() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_catalog_info')


class TestProtocolSessionMethods:
    """Test that protocol defines all session methods."""

    def test_has_has_session_support_method(self):
        """Test protocol defines has_session_support() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'has_session_support')

    def test_has_get_session_method(self):
        """Test protocol defines get_session() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_session')

    def test_has_get_registry_url_method(self):
        """Test protocol defines get_registry_url() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_registry_url')

    def test_has_create_botocore_session_method(self):
        """Test protocol defines create_botocore_session() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'create_botocore_session')


class TestProtocolPackageMethods:
    """Test that protocol defines all package operation methods."""

    def test_has_create_package_revision_method(self):
        """Test protocol defines create_package_revision() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'create_package_revision')

    def test_has_browse_package_method(self):
        """Test protocol defines browse_package() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'browse_package')

    def test_has_list_packages_method(self):
        """Test protocol defines list_packages() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'list_packages')


class TestProtocolBucketMethods:
    """Test that protocol defines all bucket operation methods."""

    def test_has_create_bucket_method(self):
        """Test protocol defines create_bucket() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'create_bucket')


class TestProtocolSearchMethods:
    """Test that protocol defines all search methods."""

    def test_has_get_search_api_method(self):
        """Test protocol defines get_search_api() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_search_api')


class TestProtocolAdminMethods:
    """Test that protocol defines all admin operation methods."""

    def test_has_is_admin_available_method(self):
        """Test protocol defines is_admin_available() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'is_admin_available')

    def test_has_get_tabulator_admin_method(self):
        """Test protocol defines get_tabulator_admin() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_tabulator_admin')

    def test_has_get_users_admin_method(self):
        """Test protocol defines get_users_admin() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_users_admin')

    def test_has_get_roles_admin_method(self):
        """Test protocol defines get_roles_admin() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_roles_admin')

    def test_has_get_sso_config_admin_method(self):
        """Test protocol defines get_sso_config_admin() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_sso_config_admin')

    def test_has_get_admin_exceptions_method(self):
        """Test protocol defines get_admin_exceptions() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_admin_exceptions')


class TestProtocolBackwardCompatibility:
    """Test that protocol defines backward compatibility methods."""

    def test_has_get_quilt3_module_method(self):
        """Test protocol defines get_quilt3_module() method."""
        from quilt_mcp.backends.protocol import QuiltBackend

        assert hasattr(QuiltBackend, 'get_quilt3_module')


class TestProtocolMethodSignatures:
    """Test that protocol methods have correct signatures using annotations."""

    def test_method_annotations_exist(self):
        """Test that protocol methods have type annotations."""
        from quilt_mcp.backends.protocol import QuiltBackend
        import inspect

        # Get all methods defined in protocol
        methods = [
            name
            for name in dir(QuiltBackend)
            if not name.startswith('_') and callable(getattr(QuiltBackend, name, None))
        ]

        # Should have at least 21 core methods (Phase 1 protocol)
        # Note: Admin methods from main branch will be added in Phase 4
        assert len(methods) >= 21

        # Check that key methods have annotations
        for method_name in ['is_authenticated', 'list_packages', 'create_package_revision']:
            method = getattr(QuiltBackend, method_name)
            assert hasattr(method, '__annotations__'), f"{method_name} should have type annotations"


def test_protocol_completeness():
    """Test that protocol covers all QuiltService public methods."""
    from quilt_mcp.backends.protocol import QuiltBackend
    from quilt_mcp.services.quilt_service import QuiltService

    # Get all public methods from QuiltService
    service_methods = {
        name for name in dir(QuiltService) if not name.startswith('_') and callable(getattr(QuiltService, name))
    }

    # Get all methods from protocol
    protocol_methods = {
        name for name in dir(QuiltBackend) if not name.startswith('_') and callable(getattr(QuiltBackend, name, None))
    }

    # Remove __init__ as protocols don't typically define it
    service_methods.discard('__init__')

    # Protocol should cover all public QuiltService methods
    missing_methods = service_methods - protocol_methods
    assert len(missing_methods) == 0, f"Protocol missing methods: {missing_methods}"
