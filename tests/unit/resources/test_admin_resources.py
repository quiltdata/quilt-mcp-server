"""Unit tests for admin resources."""

import pytest
from unittest.mock import Mock, patch

from quilt_mcp.resources.admin import (
    AdminUsersResource,
    AdminRolesResource,
    AdminConfigResource,
    AdminUserResource,
    AdminSSOConfigResource,
    AdminTabulatorConfigResource,
)


class TestAdminUsersResource:
    """Test AdminUsersResource."""

    @pytest.fixture
    def resource(self):
        return AdminUsersResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful users list retrieval."""
        mock_result = {
            "success": True,
            "users": [
                {"name": "alice", "email": "alice@example.com", "role": "admin"},
                {"name": "bob", "email": "bob@example.com", "role": "user"},
            ],
            "count": 2,
        }

        with patch("quilt_mcp.resources.admin.admin_users_list") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("admin://users")

            assert response.uri == "admin://users"
            assert response.mime_type == "application/json"
            assert response.content["items"] == mock_result["users"]
            assert response.content["metadata"]["total_count"] == 2
            assert response.content["metadata"]["has_more"] is False

    @pytest.mark.anyio
    async def test_read_failure(self, resource):
        """Test users list retrieval failure."""
        mock_result = {"success": False, "error": "Access denied"}

        with patch("quilt_mcp.resources.admin.admin_users_list") as mock_tool:
            mock_tool.return_value = mock_result

            with pytest.raises(Exception, match="Failed to list users"):
                await resource.read("admin://users")

    @pytest.mark.anyio
    async def test_read_admin_unavailable(self, resource):
        """Test users list when admin functionality unavailable."""
        mock_result = {"success": False, "error": "Admin functionality not available. quilt3.admin module not found."}

        with patch("quilt_mcp.resources.admin.admin_users_list") as mock_tool:
            mock_tool.return_value = mock_result

            with pytest.raises(Exception, match="Admin functionality not available"):
                await resource.read("admin://users")

    @pytest.mark.anyio
    async def test_read_invalid_uri(self, resource):
        """Test with invalid URI."""
        with pytest.raises(ValueError, match="Invalid URI"):
            await resource.read("admin://wrong")

    def test_properties(self, resource):
        """Test resource properties."""
        assert resource.uri_scheme == "admin"
        assert resource.uri_pattern == "admin://users"
        assert "users" in resource.name.lower()
        assert len(resource.description) > 0


class TestAdminRolesResource:
    """Test AdminRolesResource."""

    @pytest.fixture
    def resource(self):
        return AdminRolesResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful roles list retrieval."""
        mock_result = {
            "success": True,
            "roles": [
                {"name": "admin", "permissions": ["all"]},
                {"name": "user", "permissions": ["read"]},
            ],
            "count": 2,
        }

        with patch("quilt_mcp.resources.admin.admin_roles_list") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("admin://roles")

            assert response.uri == "admin://roles"
            assert response.content["items"] == mock_result["roles"]
            assert response.content["metadata"]["total_count"] == 2

    @pytest.mark.anyio
    async def test_read_failure(self, resource):
        """Test roles list retrieval failure."""
        mock_result = {"success": False, "error": "Permission error"}

        with patch("quilt_mcp.resources.admin.admin_roles_list") as mock_tool:
            mock_tool.return_value = mock_result

            with pytest.raises(Exception, match="Failed to list roles"):
                await resource.read("admin://roles")

    @pytest.mark.anyio
    async def test_read_admin_unavailable(self, resource):
        """Test roles list when admin functionality unavailable."""
        mock_result = {"success": False, "error": "Admin functionality not available. quilt3.admin module not found."}

        with patch("quilt_mcp.resources.admin.admin_roles_list") as mock_tool:
            mock_tool.return_value = mock_result

            with pytest.raises(Exception, match="Admin functionality not available"):
                await resource.read("admin://roles")


class TestAdminConfigResource:
    """Test AdminConfigResource."""

    @pytest.fixture
    def resource(self):
        return AdminConfigResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful config retrieval."""
        mock_sso_result = {
            "configured": True,
            "config": {"provider": "okta"},
        }
        mock_tabulator_result = {
            "open_query_enabled": True,
        }

        with patch("quilt_mcp.resources.admin.admin_sso_config_get") as mock_sso:
            with patch("quilt_mcp.resources.admin.admin_tabulator_open_query_get") as mock_tab:
                mock_sso.return_value = mock_sso_result
                mock_tab.return_value = mock_tabulator_result

                response = await resource.read("admin://config")

                assert response.uri == "admin://config"
                assert response.content["sso"]["configured"] is True
                assert response.content["sso"]["config"]["provider"] == "okta"
                assert response.content["tabulator"]["open_query_enabled"] is True

    def test_properties(self, resource):
        """Test resource properties."""
        assert resource.uri_pattern == "admin://config"


class TestAdminUserResource:
    """Test AdminUserResource (parameterized)."""

    @pytest.fixture
    def resource(self):
        return AdminUserResource()

    @pytest.mark.anyio
    async def test_read_with_params(self, resource):
        """Test reading user with parameters."""
        mock_result = {
            "success": True,
            "user": {"name": "alice", "email": "alice@example.com", "role": "admin"},
        }

        with patch("quilt_mcp.resources.admin.admin_user_get") as mock_tool:
            mock_tool.return_value = mock_result

            params = {"name": "alice"}
            response = await resource.read("admin://users/alice", params)

            assert response.uri == "admin://users/alice"
            assert response.content == mock_result
            mock_tool.assert_called_once_with(name="alice")

    @pytest.mark.anyio
    async def test_read_missing_param(self, resource):
        """Test reading user without parameters raises error."""
        with pytest.raises(ValueError, match="User name required"):
            await resource.read("admin://users/alice", params=None)

    @pytest.mark.anyio
    async def test_read_failure(self, resource):
        """Test user retrieval failure."""
        mock_result = {"success": False, "error": "User not found"}

        with patch("quilt_mcp.resources.admin.admin_user_get") as mock_tool:
            mock_tool.return_value = mock_result

            params = {"name": "nonexistent"}
            with pytest.raises(Exception, match="Failed to get user"):
                await resource.read("admin://users/nonexistent", params)

    @pytest.mark.anyio
    async def test_read_user_not_found(self, resource):
        """Test user retrieval when user does not exist."""
        mock_result = {"success": False, "error": "User 'ghost' not found"}

        with patch("quilt_mcp.resources.admin.admin_user_get") as mock_tool:
            mock_tool.return_value = mock_result

            params = {"name": "ghost"}
            with pytest.raises(Exception, match="not found"):
                await resource.read("admin://users/ghost", params)

    @pytest.mark.anyio
    async def test_read_empty_username(self, resource):
        """Test user retrieval with empty username."""
        params = {"name": ""}
        # The resource should validate empty username
        # This may raise ValueError or pass empty string to service
        # Testing service behavior through resource
        mock_result = {"success": False, "error": "Username cannot be empty"}

        with patch("quilt_mcp.resources.admin.admin_user_get") as mock_tool:
            mock_tool.return_value = mock_result

            with pytest.raises(Exception):
                await resource.read("admin://users/", params)

    def test_properties(self, resource):
        """Test resource properties."""
        assert resource.uri_pattern == "admin://users/{name}"
        assert "{name}" in resource.uri_pattern


class TestAdminSSOConfigResource:
    """Test AdminSSOConfigResource."""

    @pytest.fixture
    def resource(self):
        return AdminSSOConfigResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful SSO config retrieval."""
        mock_result = {
            "success": True,
            "sso_config": {"provider": "okta", "enabled": True},
        }

        with patch("quilt_mcp.resources.admin.admin_sso_config_get") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("admin://config/sso")

            assert response.uri == "admin://config/sso"
            assert response.content == mock_result

    @pytest.mark.anyio
    async def test_read_no_config(self, resource):
        """Test SSO config retrieval when no config exists."""
        mock_result = {"success": True, "sso_config": None, "message": "No SSO configuration found"}

        with patch("quilt_mcp.resources.admin.admin_sso_config_get") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("admin://config/sso")

            assert response.uri == "admin://config/sso"
            assert response.content["sso_config"] is None
            assert "No SSO configuration found" in response.content["message"]

    def test_properties(self, resource):
        """Test resource properties."""
        assert resource.uri_pattern == "admin://config/sso"


class TestAdminTabulatorConfigResource:
    """Test AdminTabulatorConfigResource."""

    @pytest.fixture
    def resource(self):
        return AdminTabulatorConfigResource()

    @pytest.mark.anyio
    async def test_read_success(self, resource):
        """Test successful Tabulator config retrieval."""
        mock_result = {
            "success": True,
            "open_query_enabled": False,
        }

        with patch("quilt_mcp.resources.admin.admin_tabulator_open_query_get") as mock_tool:
            mock_tool.return_value = mock_result

            response = await resource.read("admin://config/tabulator")

            assert response.uri == "admin://config/tabulator"
            assert response.content == mock_result

    def test_properties(self, resource):
        """Test resource properties."""
        assert resource.uri_pattern == "admin://config/tabulator"


class TestResourceMatching:
    """Test URI pattern matching across admin resources."""

    def test_users_vs_user_matching(self):
        """Test that users list and specific user have correct matching."""
        users_resource = AdminUsersResource()
        user_resource = AdminUserResource()

        # Users list should match exactly
        assert users_resource.matches("admin://users") is True
        assert users_resource.matches("admin://users/alice") is False

        # User resource should match with name
        assert user_resource.matches("admin://users/alice") is True
        assert user_resource.matches("admin://users") is False

    def test_config_vs_nested_config_matching(self):
        """Test that config and nested config resources match correctly."""
        config_resource = AdminConfigResource()
        sso_resource = AdminSSOConfigResource()
        tabulator_resource = AdminTabulatorConfigResource()

        # Main config should match exactly
        assert config_resource.matches("admin://config") is True
        assert config_resource.matches("admin://config/sso") is False

        # Nested configs should match their paths
        assert sso_resource.matches("admin://config/sso") is True
        assert sso_resource.matches("admin://config") is False

        assert tabulator_resource.matches("admin://config/tabulator") is True
        assert tabulator_resource.matches("admin://config") is False
