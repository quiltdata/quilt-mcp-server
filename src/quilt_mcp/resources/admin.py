"""Admin MCP Resources.

This module implements MCP resources for administrative functions like
user and role management.
"""

from typing import Dict, Any, List
from .base import MCPResource
from ..services.quilt_service import QuiltService
from ..formatting import format_users_as_table, format_roles_as_table
from ..utils import format_error_response


# Initialize service
quilt_service = QuiltService()


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
        try:
            if not ADMIN_AVAILABLE:
                return format_error_response(
                    "Admin functionality not available - check Quilt authentication and admin privileges"
                )

            # Use new QuiltService method that returns list of dicts
            users_data = quilt_service.list_users()

            result = {
                "success": True,
                "users": users_data,
                "count": len(users_data),
                "message": f"Found {len(users_data)} users",
            }

            # Add table formatting for better readability
            result = format_users_as_table(result)

            return result

        except Exception as e:
            error_str = str(e) if e is not None else "Unknown error"
            return format_error_response(f"Failed to list users: {error_str}")

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
        try:
            if not ADMIN_AVAILABLE:
                return format_error_response(
                    "Admin functionality not available - check Quilt authentication and admin privileges"
                )

            # Use new QuiltService method that returns list of dicts
            roles_data = quilt_service.list_roles()

            result = {
                "success": True,
                "roles": roles_data,
                "count": len(roles_data),
                "message": f"Found {len(roles_data)} roles",
            }

            # Add table formatting for better readability
            result = format_roles_as_table(result)

            return result

        except Exception as e:
            error_str = str(e) if e is not None else "Unknown error"
            return format_error_response(f"Failed to list roles: {error_str}")

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
