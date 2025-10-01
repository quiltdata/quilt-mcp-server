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

from quilt_mcp.tools import governance


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
    with patch.object(governance.quilt_service, "has_admin_credentials", return_value=True):
        yield


@pytest.fixture
def mock_admin_unavailable():
    """Mock admin functionality as unavailable."""
    with patch.object(governance.quilt_service, "has_admin_credentials", return_value=False):
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


class TestSSOConfiguration:
    """Test SSO configuration functions."""

    @pytest.mark.asyncio
    async def test_admin_sso_config_get_success(self, mock_admin_available):
        """Test successful SSO config retrieval."""
        uploader = MockUser("admin", "admin@example.com")
        sso_config = MockSSOConfig("test config", datetime.now(), uploader)

        with patch("quilt_mcp.tools.governance.quilt_service.get_sso_config", return_value=sso_config):
            result = await governance.admin_sso_config_get()

            assert result["success"] is True
            assert result["sso_config"]["text"] == "test config"
            assert result["sso_config"]["uploader"]["name"] == "admin"

    @pytest.mark.asyncio
    async def test_admin_sso_config_get_none(self, mock_admin_available):
        """Test SSO config retrieval when none exists."""
        with patch("quilt_mcp.tools.governance.quilt_service.get_sso_config", return_value=None):
            result = await governance.admin_sso_config_get()

            assert result["success"] is True
            assert result["sso_config"] is None
            assert "No SSO configuration found" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_sso_config_set_success(self, mock_admin_available):
        """Test successful SSO config setting."""
        uploader = MockUser("admin", "admin@example.com")
        sso_config = MockSSOConfig("new config", datetime.now(), uploader)

        with patch("quilt_mcp.tools.governance.quilt_service.set_sso_config", return_value=sso_config):
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
        with patch("quilt_mcp.tools.governance.quilt_service.remove_sso_config"):
            result = await governance.admin_sso_config_remove()

            assert result["success"] is True
            assert "Successfully removed SSO configuration" in result["message"]


class TestTabulatorAdmin:
    """Test enhanced tabulator administration functions."""

    @pytest.mark.asyncio
    async def test_admin_tabulator_access_get_success(self, mock_admin_available):
        """Test successful accessibility status retrieval."""
        with patch(
            "quilt_mcp.tools.governance.quilt_service.get_tabulator_access",
            return_value=True,
        ):
            result = await governance.admin_tabulator_access_get()

            assert result["success"] is True
            assert result["open_query_enabled"] is True
            assert "enabled" in result["message"]

    @pytest.mark.asyncio
    async def test_admin_tabulator_access_set_success(self, mock_admin_available):
        """Test successful accessibility status setting."""
        with patch("quilt_mcp.tools.governance.quilt_service.set_tabulator_access"):
            result = await governance.admin_tabulator_access_set(True)

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

        with patch("quilt_mcp.tools.governance.UserNotFoundError", MockUserNotFoundError):
            with patch(
                "quilt_mcp.tools.governance.quilt_service.get_user",
                side_effect=MockUserNotFoundError("User not found"),
            ):
                result = await governance.admin_user_get("nonexistent")

                assert result["success"] is False
                assert "User not found" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_admin_error(self, mock_admin_available):
        """Test handling of generic admin errors via AdminUsersResource."""
        from quilt_mcp.resources.admin import AdminUsersResource

        with patch("quilt_mcp.resources.admin.quilt_service.list_users") as mock_list_users:
            mock_list_users.side_effect = Exception("Admin error")
            resource = AdminUsersResource()
            result = await resource.list_items()

            assert result["success"] is False
            assert "Failed to list users" in result["error"]

    @pytest.mark.asyncio
    async def test_generic_exception(self, mock_admin_available):
        """Test handling of generic exceptions via AdminUsersResource."""
        from quilt_mcp.resources.admin import AdminUsersResource

        with patch("quilt_mcp.resources.admin.quilt_service.list_users") as mock_list_users:
            mock_list_users.side_effect = Exception("Generic error")
            resource = AdminUsersResource()
            result = await resource.list_items()

            assert result["success"] is False
            assert "Failed to list users" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__])
