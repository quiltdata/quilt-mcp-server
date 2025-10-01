"""
Quilt Governance and Administration Tools

This module provides MCP tools for Quilt administrative functions including
user management, role management, SSO configuration, and enhanced tabulator
administration.

These tools require administrative privileges in the Quilt catalog and provide
secure access to governance capabilities.
"""

import logging
from typing import Dict, List, Any, Optional
from ..utils import format_error_response
from ..formatting import format_users_as_table, format_roles_as_table

logger = logging.getLogger(__name__)

# QuiltService provides admin module access
from ..services.quilt_service import QuiltService

# Initialize service
quilt_service = QuiltService()

# Export exception classes for backward compatibility with tests
admin_exceptions = quilt_service.get_admin_exceptions()
UserNotFoundError = admin_exceptions.get('UserNotFoundError', Exception)
BucketNotFoundError = admin_exceptions.get('BucketNotFoundError', Exception)
Quilt3AdminError = admin_exceptions.get('Quilt3AdminError', Exception)


class GovernanceService:
    """Service for managing Quilt governance and administration."""

    def __init__(self, use_quilt_auth: bool = True):
        self.use_quilt_auth = use_quilt_auth

    def _handle_admin_error(self, e: Exception, operation: str) -> Dict[str, Any]:
        """Handle admin operation errors with appropriate messaging."""
        try:
            # Use module-level exception classes so tests can patch them
            if isinstance(e, UserNotFoundError):
                return format_error_response(f"User not found: {str(e)}")
            elif isinstance(e, BucketNotFoundError):
                return format_error_response(f"Bucket not found: {str(e)}")
            elif isinstance(e, Quilt3AdminError):
                return format_error_response(f"Admin operation failed: {str(e)}")

            operation_str = str(operation) if operation is not None else "perform admin operation"
            error_str = str(e) if e is not None else "Unknown error"
            logger.error(f"Failed to {operation_str}: {error_str}")
            return format_error_response(f"Failed to {operation_str}: {error_str}")
        except Exception as format_error:
            # Fallback if even error formatting fails
            logger.error(f"Error handling failed: {format_error}")
            return format_error_response("Admin operation failed due to an error in error handling")


# User Management Functions


async def admin_user_get(name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific user.

    Args:
        name: Username to retrieve

    Returns:
        Dict containing user information or error details
    """
    try:
        service = GovernanceService()

        if not name:
            return format_error_response("Username cannot be empty")

        user = quilt_service.get_user(name)

        if user is None:
            return format_error_response(f"User '{name}' not found")

        user_data = {
            "name": user.name,
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "is_sso_only": user.is_sso_only,
            "is_service": user.is_service,
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "role": (
                {
                    "name": user.role.name,
                    "id": user.role.id,
                    "arn": user.role.arn,
                    "type": user.role.typename__,
                }
                if user.role
                else None
            ),
            "extra_roles": (
                [
                    {
                        "name": role.name,
                        "id": role.id,
                        "arn": role.arn,
                        "type": role.typename__,
                    }
                    for role in user.extra_roles
                ]
                if user.extra_roles
                else []
            ),
        }

        return {
            "success": True,
            "user": user_data,
            "message": f"Retrieved user information for '{name}'",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, f"get user '{name}'")


async def admin_user_create(
    name: str, email: str, role: str, extra_roles: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Create a new user in the registry.

    Args:
        name: Username for the new user
        email: Email address for the new user
        role: Primary role for the user
        extra_roles: Additional roles to assign to the user

    Returns:
        Dict containing creation result and user information
    """
    try:
        service = GovernanceService()

        # Validate inputs
        if not name:
            return format_error_response("Username cannot be empty")
        if not email:
            return format_error_response("Email cannot be empty")
        if not role:
            return format_error_response("Role cannot be empty")

        # Basic email validation
        if "@" not in email or "." not in email:
            return format_error_response("Invalid email format")

        user = quilt_service.create_user(name=name, email=email, role=role, extra_roles=extra_roles or [])

        user_data = {
            "name": user.name,
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "role": user.role.name if user.role else None,
            "extra_roles": ([role.name for role in user.extra_roles] if user.extra_roles else []),
        }

        return {
            "success": True,
            "user": user_data,
            "message": f"Successfully created user '{name}' with role '{role}'",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, f"create user '{name}'")


async def admin_user_delete(name: str) -> Dict[str, Any]:
    """
    Delete a user from the registry.

    Args:
        name: Username to delete

    Returns:
        Dict containing deletion result
    """
    try:
        service = GovernanceService()

        if not name:
            return format_error_response("Username cannot be empty")

        quilt_service.delete_user(name)

        return {"success": True, "message": f"Successfully deleted user '{name}'"}

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, f"delete user '{name}'")


async def admin_user_set_email(name: str, email: str) -> Dict[str, Any]:
    """
    Update a user's email address.

    Args:
        name: Username to update
        email: New email address

    Returns:
        Dict containing update result and user information
    """
    try:
        service = GovernanceService()

        if not name:
            return format_error_response("Username cannot be empty")
        if not email:
            return format_error_response("Email cannot be empty")

        # Basic email validation
        if "@" not in email or "." not in email:
            return format_error_response("Invalid email format")

        user = quilt_service.set_user_email(name, email)

        return {
            "success": True,
            "user": {"name": user.name, "email": user.email},
            "message": f"Successfully updated email for user '{name}' to '{email}'",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, f"set email for user '{name}'")


async def admin_user_set_admin(name: str, admin: bool) -> Dict[str, Any]:
    """
    Set the admin status for a user.

    Args:
        name: Username to update
        admin: Whether the user should have admin privileges

    Returns:
        Dict containing update result and user information
    """
    try:
        service = GovernanceService()

        if not name:
            return format_error_response("Username cannot be empty")

        user = quilt_service.set_user_admin(name, admin)

        return {
            "success": True,
            "user": {"name": user.name, "is_admin": user.is_admin},
            "message": f"Successfully {'granted' if admin else 'revoked'} admin privileges for user '{name}'",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, f"set admin status for user '{name}'")


async def admin_user_set_active(name: str, active: bool) -> Dict[str, Any]:
    """
    Set the active status for a user.

    Args:
        name: Username to update
        active: Whether the user should be active

    Returns:
        Dict containing update result and user information
    """
    try:
        service = GovernanceService()

        if not name:
            return format_error_response("Username cannot be empty")

        user = quilt_service.set_user_active(name, active)

        return {
            "success": True,
            "user": {"name": user.name, "is_active": user.is_active},
            "message": f"Successfully {'activated' if active else 'deactivated'} user '{name}'",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, f"set active status for user '{name}'")


async def admin_user_reset_password(name: str) -> Dict[str, Any]:
    """
    Reset a user's password.

    Args:
        name: Username to reset password for

    Returns:
        Dict containing reset result
    """
    try:
        service = GovernanceService()

        if not name:
            return format_error_response("Username cannot be empty")

        quilt_service.reset_user_password(name)

        return {
            "success": True,
            "message": f"Successfully reset password for user '{name}'. User will need to set a new password on next login.",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, f"reset password for user '{name}'")


async def admin_user_set_role(
    name: str, role: str, extra_roles: Optional[List[str]] = None, append: bool = False
) -> Dict[str, Any]:
    """
    Set the primary and extra roles for a user.

    Args:
        name: Username to update
        role: Primary role to assign
        extra_roles: Additional roles to assign
        append: Whether to append extra roles to existing ones (True) or replace them (False)

    Returns:
        Dict containing update result and user information
    """
    try:
        service = GovernanceService()

        if not name:
            return format_error_response("Username cannot be empty")
        if not role:
            return format_error_response("Role cannot be empty")

        user = quilt_service.set_user_role(name=name, role=role, extra_roles=extra_roles or [], append=append)

        return {
            "success": True,
            "user": {
                "name": user.name,
                "role": user.role.name if user.role else None,
                "extra_roles": ([r.name for r in user.extra_roles] if user.extra_roles else []),
            },
            "message": f"Successfully updated roles for user '{name}'",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, f"set roles for user '{name}'")


async def admin_user_add_roles(name: str, roles: List[str]) -> Dict[str, Any]:
    """
    Add roles to a user.

    Args:
        name: Username to update
        roles: List of roles to add

    Returns:
        Dict containing update result and user information
    """
    try:
        service = GovernanceService()

        if not name:
            return format_error_response("Username cannot be empty")
        if not roles:
            return format_error_response("Roles list cannot be empty")

        user = quilt_service.add_user_roles(name, roles)

        return {
            "success": True,
            "user": {
                "name": user.name,
                "role": user.role.name if user.role else None,
                "extra_roles": ([r.name for r in user.extra_roles] if user.extra_roles else []),
            },
            "message": f"Successfully added roles {roles} to user '{name}'",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, f"add roles to user '{name}'")


async def admin_user_remove_roles(name: str, roles: List[str], fallback: Optional[str] = None) -> Dict[str, Any]:
    """
    Remove roles from a user.

    Args:
        name: Username to update
        roles: List of roles to remove
        fallback: Fallback role if the primary role is removed

    Returns:
        Dict containing update result and user information
    """
    try:
        service = GovernanceService()

        if not name:
            return format_error_response("Username cannot be empty")
        if not roles:
            return format_error_response("Roles list cannot be empty")

        user = quilt_service.remove_user_roles(name, roles, fallback)

        return {
            "success": True,
            "user": {
                "name": user.name,
                "role": user.role.name if user.role else None,
                "extra_roles": ([r.name for r in user.extra_roles] if user.extra_roles else []),
            },
            "message": f"Successfully removed roles {roles} from user '{name}'",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, f"remove roles from user '{name}'")


# Role Management Functions
# (admin_roles_list deleted - now available as resource admin://roles)


# SSO Configuration Functions


async def admin_sso_config_get() -> Dict[str, Any]:
    """
    Get the current SSO configuration.

    Returns:
        Dict containing SSO configuration or None if not configured
    """
    try:
        service = GovernanceService()

        sso_config = quilt_service.get_sso_config()

        if sso_config is None:
            return {
                "success": True,
                "sso_config": None,
                "message": "No SSO configuration found",
            }

        config_data = {
            "text": sso_config.text,
            "timestamp": (sso_config.timestamp.isoformat() if sso_config.timestamp else None),
            "uploader": (
                {"name": sso_config.uploader.name, "email": sso_config.uploader.email} if sso_config.uploader else None
            ),
        }

        return {
            "success": True,
            "sso_config": config_data,
            "message": "Retrieved SSO configuration",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, "get SSO configuration")


async def admin_sso_config_set(config: str) -> Dict[str, Any]:
    """
    Set the SSO configuration.

    Args:
        config: SSO configuration text

    Returns:
        Dict containing update result and configuration information
    """
    try:
        service = GovernanceService()

        if not config:
            return format_error_response("SSO configuration cannot be empty")

        # set_sso_config returns the SSO config object (despite type annotation saying dict)
        sso_config = quilt_service.set_sso_config(config)

        if sso_config is None:
            return format_error_response("Failed to set SSO configuration")

        config_data = {
            "text": sso_config.text,
            "timestamp": (sso_config.timestamp.isoformat() if sso_config.timestamp else None),
            "uploader": (
                {"name": sso_config.uploader.name, "email": sso_config.uploader.email} if sso_config.uploader else None
            ),
        }

        return {
            "success": True,
            "sso_config": config_data,
            "message": "Successfully updated SSO configuration",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, "set SSO configuration")


async def admin_sso_config_remove() -> Dict[str, Any]:
    """
    Remove the SSO configuration.

    Returns:
        Dict containing removal result
    """
    try:
        service = GovernanceService()

        quilt_service.remove_sso_config()

        return {"success": True, "message": "Successfully removed SSO configuration"}

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, "remove SSO configuration")


# Enhanced Tabulator Administration Functions


async def admin_tabulator_access_get() -> Dict[str, Any]:
    """Fetch the current tabulator accessibility status."""
    try:
        service = GovernanceService()

        open_query_enabled = quilt_service.get_tabulator_access()

        return {
            "success": True,
            "open_query_enabled": open_query_enabled,
            "message": f"Tabular accessibility is {'enabled' if open_query_enabled else 'disabled'}",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, "retrieve tabular accessibility status")


async def admin_tabulator_access_set(enabled: bool) -> Dict[str, Any]:
    """Update the tabulator accessibility status."""
    try:
        service = GovernanceService()

        quilt_service.set_tabulator_access(enabled)

        return {
            "success": True,
            "open_query_enabled": enabled,
            "message": f"Successfully {'enabled' if enabled else 'disabled'} tabular accessibility",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, "update tabular accessibility status")
