"""Functional tests for governance workflows using mocked admin backends."""

import pytest
from unittest.mock import MagicMock, Mock, patch

from quilt_mcp.context.request_context import RequestContext
from quilt_mcp.domain.role import Role
from quilt_mcp.domain.sso_config import SSOConfig
from quilt_mcp.domain.user import User
from quilt_mcp.ops.exceptions import NotFoundError
from quilt_mcp.services import governance_service as governance


@pytest.fixture
def admin_available(monkeypatch):
    monkeypatch.setattr(governance, "ADMIN_AVAILABLE", True)


@pytest.fixture
def mock_context():
    """Mock RequestContext for testing."""
    return Mock(spec=RequestContext)


@pytest.fixture
def mock_quilt_ops():
    mock_ops = MagicMock()
    mock_admin = MagicMock()

    role = Role(id="1", name="admin", arn="arn:aws:iam::123456789012:role/admin", type="ManagedRole")
    user = User(
        name="admin_user",
        email="admin@example.com",
        is_active=True,
        is_admin=True,
        is_sso_only=False,
        is_service=False,
        date_joined="2023-01-01T00:00:00Z",
        last_login="2023-01-02T00:00:00Z",
        role=role,
        extra_roles=[],
    )

    mock_admin.list_users.return_value = [user]
    mock_admin.create_user.return_value = user
    mock_admin.list_roles.return_value = [role]
    mock_admin.get_sso_config.return_value = SSOConfig("config", "2023-01-01T00:00:00Z", user)

    mock_ops.admin = mock_admin
    return mock_ops


class TestGovernanceIntegration:
    """Integration tests for governance functionality."""

    @pytest.mark.asyncio
    async def test_admin_availability_check(self, admin_available, mock_quilt_ops):
        service = governance.GovernanceService(mock_quilt_ops)
        error_check = service._check_admin_available()
        assert error_check is None

    @pytest.mark.asyncio
    async def test_sso_config_get_integration(self, admin_available, mock_quilt_ops, mock_context):
        result = await governance.admin_sso_config_get(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is True
        assert "sso_config" in result
        assert result["sso_config"]["text"] == "config"

    @pytest.mark.asyncio
    async def test_tabulator_open_query_get_integration(self, admin_available, mock_quilt_ops, mock_context):
        with patch("quilt_mcp.services.governance_service.quilt3.admin.tabulator.get_open_query", return_value=True):
            result = await governance.admin_tabulator_open_query_get(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is True
        assert result["open_query_enabled"] is True


class TestGovernanceWorkflows:
    """Test complete governance workflows."""

    @pytest.mark.asyncio
    async def test_user_management_workflow(self, admin_available, mock_quilt_ops, mock_context):
        users_result = await governance.admin_users_list(quilt_ops=mock_quilt_ops, context=mock_context)
        assert users_result["success"] is True

        mock_quilt_ops.admin.get_user.side_effect = NotFoundError("User not found", {"error_type": "user_not_found"})
        user_result = await governance.admin_user_get(
            "nonexistent_test_user_12345", quilt_ops=mock_quilt_ops, context=mock_context
        )
        assert user_result["success"] is False
        assert "User not found" in user_result["error"]

        create_result = await governance.admin_user_create("", "", "", quilt_ops=mock_quilt_ops, context=mock_context)
        assert create_result["success"] is False
        assert "Username cannot be empty" in create_result["error"]


class TestGovernanceErrorHandling:
    """Test error handling in integration scenarios."""

    @pytest.mark.asyncio
    async def test_insufficient_privileges_handling(self, mock_quilt_ops, mock_context):
        with patch.object(governance, "ADMIN_AVAILABLE", False):
            result = await governance.admin_users_list(quilt_ops=mock_quilt_ops, context=mock_context)

            assert result["success"] is False
            assert "Admin functionality not available" in result["error"]

    @pytest.mark.asyncio
    async def test_network_error_handling(self, admin_available, mock_context):
        mock_quilt_ops = MagicMock()
        mock_quilt_ops.admin.list_users.side_effect = Exception("Network error")

        result = await governance.admin_users_list(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is False
        assert "Failed to list users" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_input_handling(self, admin_available, mock_quilt_ops, mock_context):
        result = await governance.admin_user_get("", quilt_ops=mock_quilt_ops, context=mock_context)
        assert result["success"] is False
        assert "Username cannot be empty" in result["error"]

        result = await governance.admin_user_create(
            "test", "invalid-email", "role", quilt_ops=mock_quilt_ops, context=mock_context
        )
        assert result["success"] is False
        assert "Invalid email format" in result["error"]

        result = await governance.admin_sso_config_set("", quilt_ops=mock_quilt_ops, context=mock_context)
        assert result["success"] is False
        assert "SSO configuration cannot be empty" in result["error"]


class TestGovernanceTableFormatting:
    """Test table formatting in integration scenarios."""

    @pytest.mark.asyncio
    async def test_users_table_formatting(self, admin_available, mock_quilt_ops, mock_context):
        result = await governance.admin_users_list(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is True
        assert "formatted_table" in result or "display_hint" in result

        for user in result["users"]:
            assert "name" in user
            assert "email" in user
            assert "is_active" in user
            assert "is_admin" in user

    @pytest.mark.asyncio
    async def test_roles_table_formatting(self, admin_available, mock_quilt_ops, mock_context):
        result = await governance.admin_roles_list(quilt_ops=mock_quilt_ops, context=mock_context)

        assert result["success"] is True
        assert "formatted_table" in result or "display_hint" in result

        for role in result["roles"]:
            assert "id" in role
            assert "name" in role
            assert "type" in role
            assert "arn" in role
