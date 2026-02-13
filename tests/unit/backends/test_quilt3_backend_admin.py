"""
Tests for Quilt3_Backend admin operations.

This module tests the admin mixin integration and basic functionality
of the Quilt3_Backend admin operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError, NotFoundError, PermissionError
from quilt_mcp.domain.user import User
from quilt_mcp.domain.role import Role
from quilt_mcp.domain.sso_config import SSOConfig


class TestQuilt3BackendAdminIntegration:
    """Test the integration of admin functionality into Quilt3_Backend."""

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_quilt3_backend_has_admin_property(self, mock_quilt3):
        """Test that Quilt3_Backend has admin property that returns self."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        backend = Quilt3_Backend()

        # Admin property should return self since backend inherits from admin mixin
        assert backend.admin is backend

        # Verify admin methods are accessible
        assert hasattr(backend.admin, 'list_users')
        assert hasattr(backend.admin, 'get_user')
        assert hasattr(backend.admin, 'create_user')
        assert hasattr(backend.admin, 'delete_user')
        assert hasattr(backend.admin, 'list_roles')
        assert hasattr(backend.admin, 'get_sso_config')
        assert hasattr(backend.admin, 'set_sso_config')
        # Note: remove_sso_config was removed, use set_sso_config(None) instead

    @patch('quilt_mcp.backends.quilt3_backend_base.quilt3')
    def test_admin_methods_are_callable(self, mock_quilt3):
        """Test that admin methods are callable through the backend."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        backend = Quilt3_Backend()

        # Verify methods are callable
        assert callable(backend.admin.list_users)
        assert callable(backend.admin.get_user)
        assert callable(backend.admin.create_user)
        assert callable(backend.admin.delete_user)
        assert callable(backend.admin.set_user_email)
        assert callable(backend.admin.set_user_admin)
        assert callable(backend.admin.set_user_active)
        assert callable(backend.admin.reset_user_password)
        assert callable(backend.admin.set_user_role)
        assert callable(backend.admin.add_user_roles)
        assert callable(backend.admin.remove_user_roles)
        assert callable(backend.admin.list_roles)
        assert callable(backend.admin.get_sso_config)
        assert callable(backend.admin.set_sso_config)
        # Note: remove_sso_config was removed, use set_sso_config(None) instead


class TestQuilt3BackendAdminBasicFunctionality:
    """Test basic admin functionality through the backend."""

    @pytest.fixture
    def backend(self):
        """Create Quilt3_Backend instance for testing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    @patch('quilt3.admin.users')
    def test_list_users_basic_functionality(self, mock_admin_users, backend):
        """Test basic list_users functionality."""
        # Mock quilt3 user objects
        mock_user1 = Mock()
        mock_user1.name = "user1"
        mock_user1.email = "user1@example.com"
        mock_user1.is_active = True
        mock_user1.is_admin = False
        mock_user1.is_sso_only = False
        mock_user1.is_service = False
        mock_user1.date_joined = None
        mock_user1.last_login = None
        mock_user1.role = None
        mock_user1.extra_roles = []

        mock_admin_users.list.return_value = [mock_user1]

        # Call through backend.admin
        result = backend.admin.list_users()

        # Verify result
        assert len(result) == 1
        assert isinstance(result[0], User)
        assert result[0].name == "user1"
        assert result[0].email == "user1@example.com"
        assert result[0].is_active is True
        assert result[0].is_admin is False

    @patch('quilt3.admin.users')
    def test_get_user_basic_functionality(self, mock_admin_users, backend):
        """Test basic get_user functionality."""
        # Mock quilt3 user object
        mock_user = Mock()
        mock_user.name = "testuser"
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        mock_user.is_admin = True
        mock_user.is_sso_only = False
        mock_user.is_service = False
        mock_user.date_joined = None
        mock_user.last_login = None
        mock_user.role = None
        mock_user.extra_roles = []

        mock_admin_users.get.return_value = mock_user

        # Call through backend.admin
        result = backend.admin.get_user("testuser")

        # Verify result
        assert isinstance(result, User)
        assert result.name == "testuser"
        assert result.email == "test@example.com"
        assert result.is_admin is True

        # Verify quilt3 was called correctly
        mock_admin_users.get.assert_called_once_with("testuser")

    @patch('quilt3.admin.roles')
    def test_list_roles_basic_functionality(self, mock_admin_roles, backend):
        """Test basic list_roles functionality."""
        # Mock quilt3 role objects
        mock_role1 = Mock()
        mock_role1.id = "role1"
        mock_role1.name = "Admin"
        mock_role1.arn = "arn:aws:iam::123456789012:role/Admin"
        mock_role1.type = "admin"

        mock_admin_roles.list.return_value = [mock_role1]

        # Call through backend.admin
        result = backend.admin.list_roles()

        # Verify result
        assert len(result) == 1
        assert isinstance(result[0], Role)
        assert result[0].id == "role1"
        assert result[0].name == "Admin"
        assert result[0].arn == "arn:aws:iam::123456789012:role/Admin"
        assert result[0].type == "admin"

    def test_validation_error_propagation(self, backend):
        """Test that validation errors are properly propagated."""
        with pytest.raises(ValidationError) as exc_info:
            backend.admin.get_user("")  # Empty username should raise ValidationError

        assert "Username cannot be empty" in str(exc_info.value)

    def test_import_error_handling(self, backend):
        """Test handling when quilt3.admin modules are not available."""
        # Simulate ImportError when trying to import quilt3.admin.users
        with patch('builtins.__import__', side_effect=ImportError("Module not found")):
            with pytest.raises(AuthenticationError) as exc_info:
                backend.admin.list_users()

            assert "Admin functionality not available" in str(exc_info.value)


class TestQuilt3BackendAdminErrorHandling:
    """Test error handling in admin operations."""

    @pytest.fixture
    def backend(self):
        """Create Quilt3_Backend instance for testing."""
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    @patch('quilt3.admin.users')
    @patch('quilt3.admin.exceptions')
    def test_user_not_found_error_mapping(self, mock_admin_exceptions, mock_admin_users, backend):
        """Test that UserNotFoundError is properly mapped to NotFoundError."""
        # Create mock exception
        mock_user_not_found = Exception("User 'nonexistent' not found")
        mock_admin_exceptions.UserNotFoundError = type(mock_user_not_found)

        # Make get() raise the exception
        mock_admin_users.get.side_effect = mock_admin_exceptions.UserNotFoundError("User 'nonexistent' not found")

        with pytest.raises(NotFoundError) as exc_info:
            backend.admin.get_user("nonexistent")

        assert "User not found" in str(exc_info.value)
        assert exc_info.value.context["operation"] == "get user nonexistent"
        assert exc_info.value.context["error_type"] == "user_not_found"

    @patch('quilt3.admin.users')
    def test_generic_error_mapping(self, mock_admin_users, backend):
        """Test that generic errors are mapped to BackendError."""
        mock_admin_users.list.side_effect = Exception("Network error")

        with pytest.raises(BackendError) as exc_info:
            backend.admin.list_users()

        assert "Failed to list users" in str(exc_info.value)
        assert exc_info.value.context["operation"] == "list users"
        assert exc_info.value.context["error_type"] == "unknown"


class TestQuilt3BackendAdminCoverageBoost:
    """Targeted branch coverage tests for admin mixin."""

    @pytest.fixture
    def backend(self):
        from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

        with patch('quilt_mcp.backends.quilt3_backend_base.quilt3'):
            return Quilt3_Backend()

    @staticmethod
    def _mock_user(name: str = "user1") -> Mock:
        user = Mock()
        user.name = name
        user.email = f"{name}@example.com"
        user.is_active = True
        user.is_admin = False
        user.is_sso_only = False
        user.is_service = False
        user.date_joined = None
        user.last_login = None
        user.role = None
        user.extra_roles = []
        return user

    @patch('quilt3.admin.users')
    def test_user_mutation_validation_branches(self, _mock_admin_users, backend):
        with pytest.raises(ValidationError):
            backend.admin.create_user("", "a@example.com", "reader")
        with pytest.raises(ValidationError):
            backend.admin.create_user("alice", "", "reader")
        with pytest.raises(ValidationError):
            backend.admin.create_user("alice", "a@example.com", "")
        with pytest.raises(ValidationError):
            backend.admin.delete_user("   ")
        with pytest.raises(ValidationError):
            backend.admin.set_user_email("", "a@example.com")
        with pytest.raises(ValidationError):
            backend.admin.set_user_email("alice", " ")
        with pytest.raises(ValidationError):
            backend.admin.set_user_admin("", True)
        with pytest.raises(ValidationError):
            backend.admin.set_user_active("", True)
        with pytest.raises(ValidationError):
            backend.admin.reset_user_password("")
        with pytest.raises(ValidationError):
            backend.admin.set_user_role("", "reader")
        with pytest.raises(ValidationError):
            backend.admin.set_user_role("alice", "")
        with pytest.raises(ValidationError):
            backend.admin.add_user_roles("alice", [])
        with pytest.raises(ValidationError):
            backend.admin.remove_user_roles("alice", [])

    @patch('quilt3.admin.users')
    def test_create_and_role_calls_use_expected_payloads(self, mock_admin_users, backend):
        mock_admin_users.create.return_value = self._mock_user("alice")
        mock_admin_users.set_role.return_value = self._mock_user("alice")
        mock_admin_users.add_roles.return_value = self._mock_user("alice")
        mock_admin_users.remove_roles.return_value = self._mock_user("alice")

        backend.admin.create_user("alice", "alice@example.com", "reader")
        backend.admin.set_user_role("alice", "writer", extra_roles=["admin"], append=True)
        backend.admin.add_user_roles("alice", ["x", "y"])
        backend.admin.remove_user_roles("alice", ["x"], fallback="reader")

        mock_admin_users.create.assert_called_once_with(
            name="alice",
            email="alice@example.com",
            role="reader",
            extra_roles=[],
        )
        mock_admin_users.set_role.assert_called_once_with(
            name="alice",
            role="writer",
            extra_roles=["admin"],
            append=True,
        )
        mock_admin_users.add_roles.assert_called_once_with("alice", ["x", "y"])
        mock_admin_users.remove_roles.assert_called_once_with("alice", ["x"], "reader")

    @patch('quilt3.admin.roles')
    def test_list_roles_import_error_maps_to_authentication(self, _mock_roles, backend):
        with patch('builtins.__import__', side_effect=ImportError("missing")):
            with pytest.raises(AuthenticationError):
                backend.admin.list_roles()

    @patch('quilt3.admin.sso_config')
    def test_get_sso_config_none_and_set_remove_paths(self, mock_sso_config, backend):
        mock_sso_config.get.return_value = None
        assert backend.admin.get_sso_config() is None

        mock_sso_config.set.return_value = None
        assert backend.admin.set_sso_config(None) is None
        mock_sso_config.set.assert_called_once_with(None)

    @patch('quilt3.admin.sso_config')
    def test_set_sso_config_validation_and_backend_none(self, mock_sso_config, backend):
        with pytest.raises(ValidationError):
            backend.admin.set_sso_config({})

        mock_sso_config.set.return_value = None
        with pytest.raises(BackendError):
            backend.admin.set_sso_config({"enabled": True})

    @patch('quilt3.admin.sso_config')
    def test_set_sso_config_success_with_uploader_transform(self, mock_sso_config, backend):
        uploader = self._mock_user("uploader")
        sso = Mock()
        sso.text = '{"enabled": true}'
        sso.timestamp = None
        sso.uploader = uploader
        mock_sso_config.set.return_value = sso

        result = backend.admin.set_sso_config({"enabled": True})
        assert isinstance(result, SSOConfig)
        assert result.uploader is not None
        assert result.uploader.name == "uploader"

    @patch('quilt3.admin.exceptions')
    def test_handle_admin_error_maps_known_exception_types(self, mock_admin_exceptions, backend):
        mock_admin_exceptions.UserNotFoundError = type("UserNotFoundError", (Exception,), {})
        mock_admin_exceptions.BucketNotFoundError = type("BucketNotFoundError", (Exception,), {})
        mock_admin_exceptions.Quilt3AdminError = type("Quilt3AdminError", (Exception,), {})

        with pytest.raises(NotFoundError):
            backend.admin._handle_admin_error(mock_admin_exceptions.BucketNotFoundError("b"), "op")
        with pytest.raises(BackendError):
            backend.admin._handle_admin_error(mock_admin_exceptions.Quilt3AdminError("x"), "op")
        with pytest.raises(PermissionError):
            backend.admin._handle_admin_error(PermissionError("nope"), "op")
        with pytest.raises(ValidationError):
            backend.admin._handle_admin_error(ValueError("bad"), "op")

    def test_handle_admin_error_fallback_when_exception_module_unavailable(self, backend):
        original_import = __import__

        def import_side_effect(name, *args, **kwargs):
            if name == "quilt3.admin.exceptions":
                raise ImportError("missing")
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=import_side_effect):
            with pytest.raises(BackendError) as exc:
                backend.admin._handle_admin_error(Exception("boom"), "list users")
        assert exc.value.context["error_type"] == "unknown"
