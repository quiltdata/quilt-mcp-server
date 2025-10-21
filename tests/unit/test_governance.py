"""
Unit tests for Quilt governance and administration tools.

These tests mock the quilt3.admin API to test the governance functionality
in isolation without requiring actual admin privileges.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List, Optional

# Import the governance module
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from quilt_mcp.services import governance_service as governance


class MockUser:
    """Mock user object for testing."""

    def __init__(
        self,
        name: str,
        email: str,
        is_active: bool = True,
        is_admin: bool = False,
        is_sso_only: bool = False,
        is_service: bool = False,
        date_joined: Optional[datetime] = None,
        last_login: Optional[datetime] = None,
        role: Optional[Mock] = None,
        extra_roles: Optional[List[Mock]] = None,
    ):
        self.name = name
        self.email = email
        self.is_active = is_active
        self.is_admin = is_admin
        self.is_sso_only = is_sso_only
        self.is_service = is_service
        self.date_joined = date_joined or datetime.now()
        self.last_login = last_login or datetime.now()
        self.role = role
        self.extra_roles = extra_roles or []


class MockRole:
    """Mock role object for testing."""

    def __init__(self, id: str, name: str, arn: str, typename__: str):
        self.id = id
        self.name = name
        self.arn = arn
        self.typename__ = typename__


class MockSSOConfig:
    """Mock SSO config object for testing."""

    def __init__(self, text: str, timestamp: datetime, uploader: MockUser):
        self.text = text
        self.timestamp = timestamp
        self.uploader = uploader


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
    admin_role = MockRole("1", "admin", "arn:aws:iam::123456789012:role/admin", "ManagedRole")
    user_role = MockRole("2", "user", "arn:aws:iam::123456789012:role/user", "ManagedRole")

    return [
        MockUser(name="admin_user", email="admin@example.com", is_admin=True, role=admin_role),
        MockUser(
            name="regular_user",
            email="user@example.com",
            is_admin=False,
            role=user_role,
        ),
        MockUser(
            name="inactive_user",
            email="inactive@example.com",
            is_active=False,
            role=user_role,
        ),
    ]


@pytest.fixture
def sample_roles():
    """Sample roles for testing."""
    return [
        MockRole("1", "admin", "arn:aws:iam::123456789012:role/admin", "ManagedRole"),
        MockRole("2", "user", "arn:aws:iam::123456789012:role/user", "ManagedRole"),
        MockRole("3", "readonly", "arn:aws:iam::123456789012:role/readonly", "UnmanagedRole"),
    ]


class TestGovernanceService:
    """Test the GovernanceService class."""

    def test_init_with_admin_available(self, mock_admin_available):
        """Test service initialization when admin is available."""
        service = governance.GovernanceService()
        assert service.admin_available is True

    def test_init_with_admin_unavailable(self, mock_admin_unavailable):
        """Test service initialization when admin is unavailable."""
        service = governance.GovernanceService()
        assert service.admin_available is False

    def test_check_admin_available_success(self, mock_admin_available):
        """Test admin availability check when available."""
        service = governance.GovernanceService()
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
    async def test_admin_user_create_success(self, mock_admin_available, sample_users):
        """Test successful user creation."""
        new_user = sample_users[0]
        with patch("quilt_mcp.services.governance_service.admin_users.create", return_value=new_user):
            result = await governance.admin_user_create(name="new_user", email="new@example.com", role="user")

            assert result["success"] is True
            assert result["user"]["name"] == "admin_user"  # Mock returns sample user
            assert "Successfully created user" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_user_create_validation_errors(self, mock_admin_available):
        """Test user creation with validation errors."""
        # Empty name
        result = await governance.admin_user_create("", "email@example.com", "user")
        assert result["success"] is False
        assert "Username cannot be empty" in result["error"]

        # Empty email
        result = await governance.admin_user_create("user", "", "user")
        assert result["success"] is False
        assert "Email cannot be empty" in result["error"]

        # Invalid email
        result = await governance.admin_user_create("user", "invalid-email", "user")
        assert result["success"] is False
        assert "Invalid email format" in result["error"]

        # Empty role
        result = await governance.admin_user_create("user", "email@example.com", "")
        assert result["success"] is False
        assert "Role cannot be empty" in result["error"]

    @pytest.mark.asyncio
    async def test_admin_user_delete_success(self, mock_admin_available):
        """Test successful user deletion."""
        with patch("quilt_mcp.services.governance_service.admin_users.delete"):
            result = await governance.admin_user_delete("test_user")

            assert result["success"] is True
            assert "Successfully deleted user" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_user_set_email_success(self, mock_admin_available, sample_users):
        """Test successful email update."""
        updated_user = sample_users[0]
        updated_user.email = "updated@example.com"

        with patch(
            "quilt_mcp.services.governance_service.admin_users.set_email",
            return_value=updated_user,
        ):
            result = await governance.admin_user_set_email("test_user", "updated@example.com")

            assert result["success"] is True
            assert result["user"]["email"] == "updated@example.com"

    @pytest.mark.asyncio
    async def test_admin_user_set_admin_success(self, mock_admin_available, sample_users):
        """Test successful admin status update."""
        updated_user = sample_users[1]
        updated_user.is_admin = True

        with patch(
            "quilt_mcp.services.governance_service.admin_users.set_admin",
            return_value=updated_user,
        ):
            result = await governance.admin_user_set_admin("test_user", True)

            assert result["success"] is True
            assert result["user"]["is_admin"] is True
            assert "granted admin privileges" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_user_set_active_success(self, mock_admin_available, sample_users):
        """Test successful active status update."""
        updated_user = sample_users[2]
        updated_user.is_active = True

        with patch(
            "quilt_mcp.services.governance_service.admin_users.set_active",
            return_value=updated_user,
        ):
            result = await governance.admin_user_set_active("test_user", True)

            assert result["success"] is True
            assert result["user"]["is_active"] is True
            assert "activated user" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_user_reset_password_success(self, mock_admin_available):
        """Test successful password reset."""
        with patch("quilt_mcp.services.governance_service.admin_users.reset_password"):
            result = await governance.admin_user_reset_password("test_user")

            assert result["success"] is True
            assert "Successfully reset password" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_user_set_role_success(self, mock_admin_available, sample_users):
        """Test successful role assignment."""
        updated_user = sample_users[0]

        with patch("quilt_mcp.services.governance_service.admin_users.set_role", return_value=updated_user):
            result = await governance.admin_user_set_role(name="test_user", role="admin", extra_roles=["user"])

            assert result["success"] is True
            assert "Successfully updated roles" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_user_add_roles_success(self, mock_admin_available, sample_users):
        """Test successful role addition."""
        updated_user = sample_users[0]

        with patch(
            "quilt_mcp.services.governance_service.admin_users.add_roles",
            return_value=updated_user,
        ):
            result = await governance.admin_user_add_roles("test_user", ["new_role"])

            assert result["success"] is True
            assert "Successfully added roles" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_user_remove_roles_success(self, mock_admin_available, sample_users):
        """Test successful role removal."""
        updated_user = sample_users[0]

        with patch(
            "quilt_mcp.services.governance_service.admin_users.remove_roles",
            return_value=updated_user,
        ):
            result = await governance.admin_user_remove_roles("test_user", ["old_role"])

            assert result["success"] is True
            assert "Successfully removed roles" in result["message"]


class TestRoleManagement:
    """Test role management functions."""

    pass


class TestSSOConfiguration:
    """Test SSO configuration functions."""

    @pytest.mark.asyncio
    async def test_admin_sso_config_set_success(self, mock_admin_available):
        """Test successful SSO config setting."""
        uploader = MockUser("admin", "admin@example.com")
        sso_config = MockSSOConfig("new config", datetime.now(), uploader)

        with patch("quilt_mcp.services.governance_service.admin_sso_config.set", return_value=sso_config):
            result = await governance.admin_sso_config_set("new config")

            assert result["success"] is True
            assert result["sso_config"]["text"] == "new config"
            assert "Successfully updated SSO configuration" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_sso_config_set_empty(self, mock_admin_available):
        """Test SSO config setting with empty config."""
        result = await governance.admin_sso_config_set("")

        assert result["success"] is False
        assert "SSO configuration cannot be empty" in result["error"]

    @pytest.mark.asyncio
    async def test_admin_sso_config_remove_success(self, mock_admin_available):
        """Test successful SSO config removal."""
        with patch("quilt_mcp.services.governance_service.admin_sso_config.set"):
            result = await governance.admin_sso_config_remove()

            assert result["success"] is True
            assert "Successfully removed SSO configuration" in result["message"]


class TestTabulatorAdmin:
    """Test enhanced tabulator administration functions."""

    @pytest.mark.asyncio
    async def test_admin_tabulator_open_query_set_success(self, mock_admin_available):
        """Test successful open query status setting."""
        with patch("quilt_mcp.services.governance_service.admin_tabulator.set_open_query"):
            result = await governance.admin_tabulator_open_query_set(True)

            assert result["success"] is True
            assert result["open_query_enabled"] is True
            assert "enabled" in result["message"]


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_user_not_found_error(self, mock_admin_available):
        """Test handling of UserNotFoundError."""

        # Mock the exception since we don't have the actual quilt3.admin module
        class MockUserNotFoundError(Exception):
            pass

        with patch("quilt_mcp.services.governance_service.UserNotFoundError", MockUserNotFoundError):
            with patch(
                "quilt_mcp.services.governance_service.admin_users.get",
                side_effect=MockUserNotFoundError("User not found"),
            ):
                result = await governance.admin_user_get("nonexistent")

                assert result["success"] is False
                assert "User not found" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_admin_error(self, mock_admin_available):
        """Test handling of generic admin errors."""

        # Mock the exception since we don't have the actual quilt3.admin module
        class MockQuilt3AdminError(Exception):
            pass

        with patch("quilt_mcp.services.governance_service.Quilt3AdminError", MockQuilt3AdminError):
            with patch(
                "quilt_mcp.services.governance_service.admin_users.list",
                side_effect=MockQuilt3AdminError("Admin error"),
            ):
                result = await governance.admin_users_list()

                assert result["success"] is False
                assert "Admin operation failed" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_exception(self, mock_admin_available):
        """Test handling of generic exceptions."""
        with patch(
            "quilt_mcp.services.governance_service.admin_users.list",
            side_effect=Exception("Generic error"),
        ):
            result = await governance.admin_users_list()

            assert result["success"] is False
            assert "Failed to list users" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__])
