"""Tests for QuiltService admin availability checking."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

from quilt_mcp.services.quilt_service import QuiltService
from quilt_mcp.services.exceptions import AdminNotAvailableError


class TestAdminAvailability:
    """Test admin availability checking methods."""

    def test_is_admin_available_returns_true_when_modules_present(self):
        """Test that is_admin_available returns True when admin modules exist."""
        service = QuiltService()

        # Mock successful import of all admin modules
        mock_users = MagicMock()
        mock_roles = MagicMock()
        mock_sso = MagicMock()
        mock_tabulator = MagicMock()

        with patch.dict('sys.modules', {
            'quilt3.admin.users': mock_users,
            'quilt3.admin.roles': mock_roles,
            'quilt3.admin.sso_config': mock_sso,
            'quilt3.admin.tabulator': mock_tabulator,
        }, clear=False):
            result = service.is_admin_available()

        # Should return boolean True
        assert result is True
        assert isinstance(result, bool)

    def test_is_admin_available_returns_false_when_modules_missing(self):
        """Test that is_admin_available returns False when admin modules missing."""
        service = QuiltService()

        # Create a dict that explicitly maps admin modules to None to simulate missing modules
        missing_modules = {
            'quilt3.admin.users': None,
            'quilt3.admin.roles': None,
            'quilt3.admin.sso_config': None,
            'quilt3.admin.tabulator': None,
        }

        with patch.dict('sys.modules', missing_modules, clear=False):
            result = service.is_admin_available()

        # Should return boolean False
        assert result is False
        assert isinstance(result, bool)

    def test_get_admin_exceptions_returns_exception_types(self):
        """Test that _get_admin_exceptions returns dict of exception types."""
        service = QuiltService()

        # Create mock exception classes
        class MockQuilt3AdminError(Exception):
            pass

        class MockUserNotFoundError(Exception):
            pass

        class MockBucketNotFoundError(Exception):
            pass

        # Mock the admin exceptions module
        mock_exceptions_module = MagicMock()
        mock_exceptions_module.Quilt3AdminError = MockQuilt3AdminError
        mock_exceptions_module.UserNotFoundError = MockUserNotFoundError
        mock_exceptions_module.BucketNotFoundError = MockBucketNotFoundError

        with patch.dict('sys.modules', {'quilt3.admin.exceptions': mock_exceptions_module}, clear=False):
            exceptions = service._get_admin_exceptions()

        # Should return dict mapping names to types
        assert isinstance(exceptions, dict)
        assert 'Quilt3AdminError' in exceptions
        assert 'UserNotFoundError' in exceptions
        assert 'BucketNotFoundError' in exceptions

        # Values should be exception types (classes)
        assert exceptions['Quilt3AdminError'] == MockQuilt3AdminError
        assert exceptions['UserNotFoundError'] == MockUserNotFoundError
        assert exceptions['BucketNotFoundError'] == MockBucketNotFoundError

    def test_get_admin_exceptions_raises_when_unavailable(self):
        """Test that _get_admin_exceptions raises AdminNotAvailableError when unavailable."""
        service = QuiltService()

        # Set the module to None to simulate missing module
        with patch.dict('sys.modules', {'quilt3.admin.exceptions': None}, clear=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service._get_admin_exceptions()

        assert "Admin operations not available" in str(exc_info.value)


class TestRequireAdminHelper:
    """Test _require_admin() helper method."""

    def test_require_admin_succeeds_when_admin_available(self):
        """Test that _require_admin() succeeds silently when admin is available."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=True):
            # Should not raise any exception
            service._require_admin()

    def test_require_admin_raises_when_admin_unavailable(self):
        """Test that _require_admin() raises AdminNotAvailableError when unavailable."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service._require_admin()

        assert "Admin operations not available" in str(exc_info.value)

    def test_require_admin_with_custom_message(self):
        """Test that _require_admin() can include custom context in error message."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service._require_admin("Operation 'list_users' requires admin access")

        error_message = str(exc_info.value)
        assert "Admin operations not available" in error_message
        assert "list_users" in error_message


class TestAdminMethodsErrorHandling:
    """Test that admin methods use new exceptions properly."""

    def test_get_users_admin_raises_admin_not_available_error(self):
        """Test that get_users_admin raises AdminNotAvailableError when unavailable."""
        service = QuiltService()

        # Mock is_admin_available to return False
        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.get_users_admin()

        assert "Admin operations not available" in str(exc_info.value)

    def test_get_roles_admin_raises_admin_not_available_error(self):
        """Test that get_roles_admin raises AdminNotAvailableError when unavailable."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.get_roles_admin()

        assert "Admin operations not available" in str(exc_info.value)

    def test_get_sso_config_admin_raises_admin_not_available_error(self):
        """Test that get_sso_config_admin raises AdminNotAvailableError when unavailable."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.get_sso_config_admin()

        assert "Admin operations not available" in str(exc_info.value)

    def test_get_tabulator_admin_raises_admin_not_available_error(self):
        """Test that get_tabulator_admin raises AdminNotAvailableError when unavailable."""
        service = QuiltService()

        with patch.object(service, 'is_admin_available', return_value=False):
            with pytest.raises(AdminNotAvailableError) as exc_info:
                service.get_tabulator_admin()

        assert "Admin operations not available" in str(exc_info.value)

    def test_get_users_admin_succeeds_when_available(self):
        """Test that get_users_admin returns module when available."""
        service = QuiltService()

        mock_users_module = MagicMock()

        with patch.object(service, 'is_admin_available', return_value=True):
            # Mock the actual import that happens inside the method
            with patch.dict('sys.modules', {'quilt3.admin.users': mock_users_module}, clear=False):
                result = service.get_users_admin()

        assert result == mock_users_module

    def test_get_roles_admin_succeeds_when_available(self):
        """Test that get_roles_admin returns module when available."""
        service = QuiltService()

        mock_roles_module = MagicMock()

        with patch.object(service, 'is_admin_available', return_value=True):
            with patch.dict('sys.modules', {'quilt3.admin.roles': mock_roles_module}, clear=False):
                result = service.get_roles_admin()

        assert result == mock_roles_module

    def test_get_sso_config_admin_succeeds_when_available(self):
        """Test that get_sso_config_admin returns module when available."""
        service = QuiltService()

        mock_sso_module = MagicMock()

        with patch.object(service, 'is_admin_available', return_value=True):
            with patch.dict('sys.modules', {'quilt3.admin.sso_config': mock_sso_module}, clear=False):
                result = service.get_sso_config_admin()

        assert result == mock_sso_module

    def test_get_tabulator_admin_succeeds_when_available(self):
        """Test that get_tabulator_admin returns module when available."""
        service = QuiltService()

        mock_tabulator_module = MagicMock()

        with patch.object(service, 'is_admin_available', return_value=True):
            with patch.dict('sys.modules', {'quilt3.admin.tabulator': mock_tabulator_module}, clear=False):
                result = service.get_tabulator_admin()

        assert result == mock_tabulator_module
