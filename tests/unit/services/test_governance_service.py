"""
Unit tests for Quilt governance and administration tools.

These tests mock the QuiltOps.admin API to test the governance functionality
in isolation without requiring actual admin privileges.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List, Optional

from quilt_mcp.services import governance_service as governance
from quilt_mcp.ops.quilt_ops import QuiltOps
from quilt_mcp.domain.user import User
from quilt_mcp.domain.role import Role
from quilt_mcp.domain.sso_config import SSOConfig
from quilt_mcp.ops.exceptions import NotFoundError, BackendError, ValidationError
from quilt_mcp.context.request_context import RequestContext


@pytest.fixture
def mock_context():
    """Mock RequestContext for testing."""
    return Mock(spec=RequestContext)


@pytest.fixture
def mock_admin_available():
    """Mock admin functionality as available."""
    with patch.object(governance, "ADMIN_AVAILABLE", True):
        yield


@pytest.fixture
def mock_admin_unavailable():
    """Mock admin functionality as unavailable."""
    with patch.object(governance, "ADMIN_AVAILABLE", False):
        yield


@pytest.fixture
def sample_users():
    """Sample users for testing."""
    admin_role = Role(id="1", name="admin", arn="arn:aws:iam::123456789012:role/admin", type="ManagedRole")
    user_role = Role(id="2", name="user", arn="arn:aws:iam::123456789012:role/user", type="ManagedRole")

    return [
        User(
            name="admin_user",
            email="admin@example.com",
            is_active=True,
            is_admin=True,
            is_sso_only=False,
            is_service=False,
            date_joined="2023-01-01T00:00:00Z",
            last_login="2023-01-02T00:00:00Z",
            role=admin_role,
            extra_roles=[],
        ),
        User(
            name="regular_user",
            email="user@example.com",
            is_active=True,
            is_admin=False,
            is_sso_only=False,
            is_service=False,
            date_joined="2023-01-01T00:00:00Z",
            last_login="2023-01-02T00:00:00Z",
            role=user_role,
            extra_roles=[],
        ),
        User(
            name="inactive_user",
            email="inactive@example.com",
            is_active=False,
            is_admin=False,
            is_sso_only=False,
            is_service=False,
            date_joined="2023-01-01T00:00:00Z",
            last_login="2023-01-02T00:00:00Z",
            role=user_role,
            extra_roles=[],
        ),
    ]


@pytest.fixture
def sample_roles():
    """Sample roles for testing."""
    return [
        Role(id="1", name="admin", arn="arn:aws:iam::123456789012:role/admin", type="ManagedRole"),
        Role(id="2", name="user", arn="arn:aws:iam::123456789012:role/user", type="ManagedRole"),
        Role(id="3", name="readonly", arn="arn:aws:iam::123456789012:role/readonly", type="UnmanagedRole"),
    ]


@pytest.fixture
def mock_quilt_ops():
    """Mock QuiltOps instance with admin interface."""
    mock_ops = MagicMock(spec=QuiltOps)
    mock_admin = MagicMock()
    mock_ops.admin = mock_admin
    return mock_ops


@pytest.fixture
def governance_service_with_mock_ops(mock_quilt_ops):
    """Create GovernanceService with mocked QuiltOps."""
    return governance.GovernanceService(mock_quilt_ops)


class TestGovernanceService:
    """Test the GovernanceService class."""

    def test_init_with_admin_available(self, mock_admin_available, mock_quilt_ops):
        """Test service initialization when admin is available."""
        service = governance.GovernanceService(mock_quilt_ops)
        assert service.admin_available is True

    def test_init_with_admin_unavailable(self, mock_admin_unavailable, mock_quilt_ops):
        """Test service initialization when admin is unavailable."""
        service = governance.GovernanceService(mock_quilt_ops)
        assert service.admin_available is False

    def test_check_admin_available_success(self, mock_admin_available, mock_quilt_ops):
        """Test admin availability check when available."""
        service = governance.GovernanceService(mock_quilt_ops)
        result = service._check_admin_available()
        assert result is None

    def test_check_admin_available_failure(self, mock_admin_unavailable):
        """Test admin availability check when unavailable."""
        service = governance.GovernanceService()
        result = service._check_admin_available()
        assert result is not None
        assert result["success"] is False
        assert "Admin functionality not available" in result["error"]


class TestUserManagement:
    """Test user management functions."""

    @pytest.mark.asyncio
    async def test_admin_user_create_success(self, mock_admin_available, sample_users, mock_quilt_ops, mock_context):
        """Test successful user creation."""
        new_user = sample_users[0]
        mock_quilt_ops.admin.create_user.return_value = new_user

        result = await governance.admin_user_create(
            name="new_user", email="new@example.com", role="user", quilt_ops=mock_quilt_ops, context=mock_context
        )

        assert result["success"] is True
        assert result["user"]["name"] == "admin_user"  # Mock returns sample user
        assert "Successfully created user" in result["message"]
        mock_quilt_ops.admin.create_user.assert_called_once_with(
            name="new_user", email="new@example.com", role="user", extra_roles=[]
        )

    @pytest.mark.asyncio
    async def test_admin_user_create_validation_errors(self, mock_admin_available, mock_quilt_ops, mock_context):
        """Test user creation with validation errors."""
        # Empty name
        result = await governance.admin_user_create(
            "", "email@example.com", "user", quilt_ops=mock_quilt_ops, context=mock_context
        )
        assert result["success"] is False
        assert "Username cannot be empty" in result["error"]

        # Empty email
        result = await governance.admin_user_create("user", "", "user", quilt_ops=mock_quilt_ops, context=mock_context)
        assert result["success"] is False
        assert "Email cannot be empty" in result["error"]

        # Invalid email
        result = await governance.admin_user_create(
            "user", "invalid-email", "user", quilt_ops=mock_quilt_ops, context=mock_context
        )
        assert result["success"] is False
        assert "Invalid email format" in result["error"]

        # Empty role
        result = await governance.admin_user_create(
            "user", "email@example.com", "", quilt_ops=mock_quilt_ops, context=mock_context
        )
        assert result["success"] is False
        assert "Role cannot be empty" in result["error"]

    @pytest.mark.asyncio
    async def test_admin_user_get_success(self, mock_admin_available, sample_users, mock_quilt_ops, mock_context):
        """Test successful user retrieval."""
        user = sample_users[0]
        mock_quilt_ops.admin.get_user.return_value = user

        result = await governance.admin_user_get("admin_user", quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is True
        assert result["user"]["name"] == "admin_user"
        assert "Retrieved user information" in result["message"]
        mock_quilt_ops.admin.get_user.assert_called_once_with("admin_user")

    @pytest.mark.asyncio
    async def test_admin_users_list_success(self, mock_admin_available, sample_users, mock_quilt_ops, mock_context):
        """Test successful user listing."""
        mock_quilt_ops.admin.list_users.return_value = sample_users

        result = await governance.admin_users_list(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is True
        assert len(result["users"]) == 3
        assert result["users"][0]["name"] == "admin_user"
        assert "Found 3 users" in result["message"]
        mock_quilt_ops.admin.list_users.assert_called_once()

    @pytest.mark.asyncio
    async def test_admin_user_delete_success(self, mock_admin_available, mock_quilt_ops, mock_context):
        """Test successful user deletion."""
        mock_quilt_ops.admin.delete_user.return_value = None

        result = await governance.admin_user_delete("test_user", quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is True
        assert "Successfully deleted user" in result["message"]
        mock_quilt_ops.admin.delete_user.assert_called_once_with("test_user")

    @pytest.mark.asyncio
    async def test_admin_user_set_email_success(
        self, mock_admin_available, sample_users, mock_quilt_ops, mock_context
    ):
        """Test successful email update."""
        updated_user = sample_users[0]
        mock_quilt_ops.admin.set_user_email.return_value = updated_user

        result = await governance.admin_user_set_email(
            "test_user", "updated@example.com", quilt_ops=mock_quilt_ops, context=mock_context
        )

        assert result["success"] is True
        assert result["user"]["name"] == "admin_user"
        assert "Successfully updated email" in result["message"]
        mock_quilt_ops.admin.set_user_email.assert_called_once_with("test_user", "updated@example.com")

    @pytest.mark.asyncio
    async def test_admin_user_set_admin_success(
        self, mock_admin_available, sample_users, mock_quilt_ops, mock_context
    ):
        """Test successful admin status update."""
        updated_user = sample_users[0]
        mock_quilt_ops.admin.set_user_admin.return_value = updated_user

        result = await governance.admin_user_set_admin(
            "test_user", True, quilt_ops=mock_quilt_ops, context=mock_context
        )

        assert result["success"] is True
        assert result["user"]["name"] == "admin_user"
        assert "Successfully granted admin privileges" in result["message"]
        mock_quilt_ops.admin.set_user_admin.assert_called_once_with("test_user", True)

    @pytest.mark.asyncio
    async def test_admin_user_set_active_success(
        self, mock_admin_available, sample_users, mock_quilt_ops, mock_context
    ):
        """Test successful active status update."""
        updated_user = sample_users[0]
        mock_quilt_ops.admin.set_user_active.return_value = updated_user

        result = await governance.admin_user_set_active(
            "test_user", True, quilt_ops=mock_quilt_ops, context=mock_context
        )

        assert result["success"] is True
        assert result["user"]["name"] == "admin_user"
        assert "Successfully activated user" in result["message"]
        mock_quilt_ops.admin.set_user_active.assert_called_once_with("test_user", True)

    @pytest.mark.asyncio
    async def test_admin_user_reset_password_success(self, mock_admin_available, mock_quilt_ops, mock_context):
        """Test successful password reset."""
        mock_quilt_ops.admin.reset_user_password.return_value = None

        result = await governance.admin_user_reset_password(
            "test_user", quilt_ops=mock_quilt_ops, context=mock_context
        )

        assert result["success"] is True
        assert "Successfully reset password" in result["message"]
        mock_quilt_ops.admin.reset_user_password.assert_called_once_with("test_user")

    @pytest.mark.asyncio
    async def test_admin_user_set_role_success(self, mock_admin_available, sample_users, mock_quilt_ops, mock_context):
        """Test successful role assignment."""
        updated_user = sample_users[0]
        mock_quilt_ops.admin.set_user_role.return_value = updated_user

        result = await governance.admin_user_set_role(
            name="test_user", role="admin", extra_roles=["user"], quilt_ops=mock_quilt_ops, context=mock_context
        )

        assert result["success"] is True
        assert result["user"]["name"] == "admin_user"
        assert "Successfully updated roles" in result["message"]
        mock_quilt_ops.admin.set_user_role.assert_called_once_with(
            name="test_user", role="admin", extra_roles=["user"], append=False
        )

    @pytest.mark.asyncio
    async def test_admin_user_add_roles_success(
        self, mock_admin_available, sample_users, mock_quilt_ops, mock_context
    ):
        """Test successful role addition."""
        updated_user = sample_users[0]
        mock_quilt_ops.admin.add_user_roles.return_value = updated_user

        result = await governance.admin_user_add_roles(
            "test_user", ["new_role"], quilt_ops=mock_quilt_ops, context=mock_context
        )

        assert result["success"] is True
        assert result["user"]["name"] == "admin_user"
        assert "Successfully added roles" in result["message"]
        mock_quilt_ops.admin.add_user_roles.assert_called_once_with("test_user", ["new_role"])

    @pytest.mark.asyncio
    async def test_admin_user_remove_roles_success(
        self, mock_admin_available, sample_users, mock_quilt_ops, mock_context
    ):
        """Test successful role removal."""
        updated_user = sample_users[0]
        mock_quilt_ops.admin.remove_user_roles.return_value = updated_user

        result = await governance.admin_user_remove_roles(
            "test_user", ["old_role"], quilt_ops=mock_quilt_ops, context=mock_context
        )

        assert result["success"] is True
        assert result["user"]["name"] == "admin_user"
        assert "Successfully removed roles" in result["message"]
        mock_quilt_ops.admin.remove_user_roles.assert_called_once_with("test_user", ["old_role"], None)


class TestRoleManagement:
    """Test role management functions."""

    @pytest.mark.asyncio
    async def test_admin_roles_list_success(self, mock_admin_available, sample_roles, mock_quilt_ops, mock_context):
        """Test successful role listing."""
        mock_quilt_ops.admin.list_roles.return_value = sample_roles

        result = await governance.admin_roles_list(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is True
        assert len(result["roles"]) == 3
        assert result["roles"][0]["name"] == "admin"
        assert "Found 3 roles" in result["message"]
        mock_quilt_ops.admin.list_roles.assert_called_once()


class TestSSOConfiguration:
    """Test SSO configuration functions."""

    @pytest.mark.asyncio
    async def test_admin_sso_config_get_success(
        self, mock_admin_available, sample_users, mock_quilt_ops, mock_context
    ):
        """Test successful SSO config retrieval."""
        uploader = sample_users[0]
        sso_config = SSOConfig("test config", "2023-01-01T00:00:00Z", uploader)
        mock_quilt_ops.admin.get_sso_config.return_value = sso_config

        result = await governance.admin_sso_config_get(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is True
        assert result["sso_config"]["text"] == "test config"
        assert "Retrieved SSO configuration" in result["message"]
        mock_quilt_ops.admin.get_sso_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_admin_sso_config_get_none(self, mock_admin_available, mock_quilt_ops, mock_context):
        """Test SSO config retrieval when none exists."""
        mock_quilt_ops.admin.get_sso_config.return_value = None

        result = await governance.admin_sso_config_get(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is True
        assert result["sso_config"] is None
        assert "No SSO configuration found" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_sso_config_set_success(
        self, mock_admin_available, sample_users, mock_quilt_ops, mock_context
    ):
        """Test successful SSO config setting."""
        uploader = sample_users[0]
        sso_config = SSOConfig("new config", "2023-01-01T00:00:00Z", uploader)
        mock_quilt_ops.admin.set_sso_config.return_value = sso_config

        # Pass dict instead of string (new behavior)
        result = await governance.admin_sso_config_set(
            {"provider": "saml", "config": "new config"}, quilt_ops=mock_quilt_ops, context=mock_context
        )

        assert result["success"] is True
        assert result["sso_config"]["text"] == "new config"
        assert "Successfully updated SSO configuration" in result["message"]
        # Backend now receives dict (serialization happens in backend)
        mock_quilt_ops.admin.set_sso_config.assert_called_once_with({"provider": "saml", "config": "new config"})

    @pytest.mark.asyncio
    async def test_admin_sso_config_set_empty(self, mock_admin_available, mock_quilt_ops, mock_context):
        """Test SSO config setting with empty config."""
        result = await governance.admin_sso_config_set({}, quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is False
        assert "SSO configuration cannot be empty" in result["error"]

    @pytest.mark.asyncio
    async def test_admin_sso_config_remove_success(self, mock_admin_available, mock_quilt_ops, mock_context):
        """Test successful SSO config removal."""
        # Now uses set_sso_config(None) instead of remove_sso_config()
        mock_quilt_ops.admin.set_sso_config.return_value = None

        result = await governance.admin_sso_config_remove(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is True
        assert "Successfully removed SSO configuration" in result["message"]
        mock_quilt_ops.admin.set_sso_config.assert_called_once_with(None)


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_user_not_found_error(self, mock_admin_available, mock_quilt_ops, mock_context):
        """Test handling of user not found errors."""
        mock_quilt_ops.admin.get_user.side_effect = NotFoundError("User not found", {"error_type": "user_not_found"})

        result = await governance.admin_user_get("nonexistent", quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is False
        assert "User not found" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_admin_error(self, mock_admin_available, mock_quilt_ops, mock_context):
        """Test handling of generic admin errors."""
        mock_quilt_ops.admin.list_users.side_effect = BackendError("Admin operation failed")

        result = await governance.admin_users_list(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is False
        assert "Admin operation failed" in result["error"]

    @pytest.mark.asyncio
    async def test_validation_error(self, mock_admin_available, mock_quilt_ops, mock_context):
        """Test handling of validation errors from QuiltOps."""
        mock_quilt_ops.admin.create_user.side_effect = ValidationError("Invalid role name")

        result = await governance.admin_user_create(
            "user", "valid@email.com", "role", quilt_ops=mock_quilt_ops, context=mock_context
        )

        assert result["success"] is False
        assert "Validation error" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_exception(self, mock_admin_available, mock_quilt_ops, mock_context):
        """Test handling of generic exceptions."""
        mock_quilt_ops.admin.list_users.side_effect = Exception("Unexpected error")

        result = await governance.admin_users_list(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is False
        assert "Failed to list users" in result["error"]

    @pytest.mark.asyncio
    async def test_admin_unavailable_error(self, mock_admin_unavailable, mock_quilt_ops, mock_context):
        """Test handling when admin functionality is unavailable."""
        result = await governance.admin_users_list(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is False
        assert "Admin functionality not available" in result["error"]
