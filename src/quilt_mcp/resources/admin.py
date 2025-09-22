"""Admin MCP Resources.

This module implements MCP resources for administrative functions like
user and role management.
"""

from typing import Dict, Any, List
from .base import MCPResource


class AdminUsersResource(MCPResource):
    """MCP resource for admin users listing."""

    def __init__(self):
        """Initialize AdminUsersResource."""
        super().__init__("admin://users")

    async def list_items(self, **params) -> Dict[str, Any]:
        """List admin users.

        Returns:
            Admin users data in original format
        """
        # Import here to avoid circular imports and maintain compatibility
        from ..tools.governance import admin_users_list

        # Call the original async function
        return await admin_users_list()

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract users list from admin users data."""
        return raw_data.get("users", [])

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from admin users data."""
        metadata = super()._extract_metadata(raw_data)

        # Add admin-specific metadata
        if "formatted_table" in raw_data:
            metadata["has_table_format"] = True
        if "success" in raw_data:
            metadata["success"] = raw_data["success"]

        return metadata


class AdminRolesResource(MCPResource):
    """MCP resource for admin roles listing."""

    def __init__(self):
        """Initialize AdminRolesResource."""
        super().__init__("admin://roles")

    async def list_items(self, **params) -> Dict[str, Any]:
        """List admin roles.

        Returns:
            Admin roles data in original format
        """
        # Import here to avoid circular imports and maintain compatibility
        from ..tools.governance import admin_roles_list

        # Call the original async function
        return await admin_roles_list()

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract roles list from admin roles data."""
        return raw_data.get("roles", [])

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from admin roles data."""
        metadata = super()._extract_metadata(raw_data)

        # Add admin-specific metadata
        if "formatted_table" in raw_data:
            metadata["has_table_format"] = True
        if "success" in raw_data:
            metadata["success"] = raw_data["success"]

        return metadata