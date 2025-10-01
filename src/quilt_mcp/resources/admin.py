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
ADMIN_AVAILABLE = quilt_service.is_admin_available()


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

            admin_users = quilt_service.get_users_admin()
            users = admin_users.list()

            # Convert users to dictionaries for better handling
            users_data = []
            for user in users:
                user_dict = {
                    "name": user.name,
                    "email": user.email,
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                    "is_sso_only": user.is_sso_only,
                    "is_service": user.is_service,
                    "date_joined": (user.date_joined.isoformat() if user.date_joined else None),
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "role": user.role.name if user.role else None,
                    "extra_roles": ([role.name for role in user.extra_roles] if user.extra_roles else []),
                }
                users_data.append(user_dict)

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

            admin_roles = quilt_service.get_roles_admin()
            roles = admin_roles.list()

            # Convert roles to dictionaries for better handling
            roles_data = []
            for role in roles:
                role_dict = {
                    "id": getattr(role, "id", None),
                    "name": getattr(role, "name", None),
                    "arn": getattr(role, "arn", None),
                    "type": getattr(role, "typename", getattr(role, "type", "unknown")),
                }
                roles_data.append(role_dict)

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
