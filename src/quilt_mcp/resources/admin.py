"""Admin resources for MCP."""

from typing import Dict, Optional

from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.services.governance_service import (
    admin_users_list,
    admin_roles_list,
    admin_sso_config_get,
    admin_tabulator_open_query_get,
    admin_user_get,
)


class AdminUsersResource(MCPResource):
    """List all users in the registry."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_pattern(self) -> str:
        return "admin://users"

    @property
    def name(self) -> str:
        return "Admin Users List"

    @property
    def description(self) -> str:
        return "List all users in the Quilt registry with their roles and status"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await admin_users_list()

        if not result.get("success"):
            raise Exception(f"Failed to list users: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("users", []),
                "metadata": {
                    "total_count": result.get("count", 0),
                    "has_more": False,
                    "continuation_token": None,
                },
            },
        )


class AdminRolesResource(MCPResource):
    """List all available roles."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_pattern(self) -> str:
        return "admin://roles"

    @property
    def name(self) -> str:
        return "Admin Roles List"

    @property
    def description(self) -> str:
        return "List all available roles in the Quilt registry"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await admin_roles_list()

        if not result.get("success"):
            raise Exception(f"Failed to list roles: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("roles", []),
                "metadata": {
                    "total_count": result.get("count", 0),
                    "has_more": False,
                    "continuation_token": None,
                },
            },
        )


class AdminConfigResource(MCPResource):
    """Combined admin configuration resource."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_pattern(self) -> str:
        return "admin://config"

    @property
    def name(self) -> str:
        return "Admin Configuration"

    @property
    def description(self) -> str:
        return "Combined admin configuration (SSO, tabulator settings)"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        # Gather all config settings
        sso_result = await admin_sso_config_get()
        tabulator_result = await admin_tabulator_open_query_get()

        config = {
            "sso": {
                "configured": sso_result.get("configured", False),
                "config": sso_result.get("config"),
            },
            "tabulator": {"open_query_enabled": tabulator_result.get("open_query_enabled", False)},
        }

        return ResourceResponse(uri=uri, content=config)


class AdminUserResource(MCPResource):
    """Get specific user details."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_pattern(self) -> str:
        return "admin://users/{name}"

    @property
    def name(self) -> str:
        return "Admin User Details"

    @property
    def description(self) -> str:
        return "Get detailed information about a specific user"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "name" not in params:
            raise ValueError("User name required in URI")

        username = params["name"]
        result = await admin_user_get(name=username)

        if not result.get("success"):
            raise Exception(f"Failed to get user {username}: {result.get('error', 'Unknown error')}")

        return ResourceResponse(uri=uri, content=result)


class AdminSSOConfigResource(MCPResource):
    """SSO configuration."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_pattern(self) -> str:
        return "admin://config/sso"

    @property
    def name(self) -> str:
        return "SSO Configuration"

    @property
    def description(self) -> str:
        return "Current SSO configuration"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await admin_sso_config_get()
        return ResourceResponse(uri=uri, content=result)


class AdminTabulatorConfigResource(MCPResource):
    """Tabulator open query configuration."""

    @property
    def uri_scheme(self) -> str:
        return "admin"

    @property
    def uri_pattern(self) -> str:
        return "admin://config/tabulator"

    @property
    def name(self) -> str:
        return "Tabulator Configuration"

    @property
    def description(self) -> str:
        return "Tabulator open query configuration"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await admin_tabulator_open_query_get()
        return ResourceResponse(uri=uri, content=result)
