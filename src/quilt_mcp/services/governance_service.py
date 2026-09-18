"""
Quilt Governance and Administration Tools

This module provides MCP tools for Quilt administrative functions including
user management, role management, SSO configuration, and enhanced tabulator
administration.

These tools require administrative privileges in the Quilt catalog and provide
secure access to governance capabilities.
"""

import logging
from typing import Annotated, Dict, List, Any, Optional
from pydantic import Field
from ..utils.common import format_error_response
from quilt_mcp.utils.formatting import format_users_as_table, format_roles_as_table
from ..ops.quilt_ops import QuiltOps
from ..ops.exceptions import NotFoundError, BackendError, ValidationError, AuthenticationError, PermissionError
from ..context.request_context import RequestContext

logger = logging.getLogger(__name__)

# Check admin availability and import modules directly for backward compatibility
try:
    import quilt3.admin.users
    import quilt3.admin.roles
    import quilt3.admin.sso_config
    import quilt3.admin.tabulator
    import quilt3.admin.exceptions

    ADMIN_AVAILABLE = True

    # Export exception classes for backward compatibility with tests
    UserNotFoundError = quilt3.admin.exceptions.UserNotFoundError
    BucketNotFoundError = quilt3.admin.exceptions.BucketNotFoundError
    Quilt3AdminError = quilt3.admin.exceptions.Quilt3AdminError

except ImportError:
    ADMIN_AVAILABLE = False
    # Fallback exception classes when admin is not available
    UserNotFoundError = Exception
    BucketNotFoundError = Exception
    Quilt3AdminError = Exception

if not ADMIN_AVAILABLE:
    logger.warning("quilt3.admin not available - governance functionality disabled")

# Create module-level admin objects for backward compatibility with tests
if ADMIN_AVAILABLE:
    admin_users = quilt3.admin.users
    admin_roles = quilt3.admin.roles
    admin_sso_config = quilt3.admin.sso_config
    admin_tabulator = quilt3.admin.tabulator
else:
    admin_users = None
    admin_roles = None
    admin_sso_config = None
    admin_tabulator = None


class GovernanceService:
    """Service for managing Quilt governance and administration."""

    def __init__(self, quilt_ops: Optional[QuiltOps] = None):
        self.quilt_ops = quilt_ops
        self.admin_available = ADMIN_AVAILABLE

    def _get_quilt_ops(self) -> QuiltOps:
        """Get QuiltOps instance, creating one if not provided."""
        if self.quilt_ops is None:
            from ..ops.factory import QuiltOpsFactory

            self.quilt_ops = QuiltOpsFactory.create()
        return self.quilt_ops

    def _check_admin_available(self) -> Optional[Dict[str, Any]]:
        """Check if admin functionality is available."""
        if not self.admin_available:
            return format_error_response(
                "Admin functionality not available - check Quilt authentication and admin privileges"
            )
        try:
            self._get_quilt_ops()
            return None
        except Exception as e:
            return format_error_response(f"QuiltOps instance not available - admin functionality disabled: {str(e)}")
        return None

    def _handle_admin_error(self, e: Exception, operation: str) -> Dict[str, Any]:
        """Handle admin operation errors with appropriate messaging."""
        try:
            # Handle domain exceptions from QuiltOps.admin
            if isinstance(e, NotFoundError):
                if "user_not_found" in e.context.get("error_type", ""):
                    return format_error_response(f"User not found: {str(e)}")
                elif "bucket_not_found" in e.context.get("error_type", ""):
                    return format_error_response(f"Bucket not found: {str(e)}")
                else:
                    return format_error_response(f"Not found: {str(e)}")
            elif isinstance(e, BackendError):
                return format_error_response(f"Admin operation failed: {str(e)}")
            elif isinstance(e, ValidationError):
                return format_error_response(f"Validation error: {str(e)}")
            elif isinstance(e, AuthenticationError):
                return format_error_response(f"Authentication error: {str(e)}")
            elif isinstance(e, PermissionError):
                return format_error_response(f"Permission denied: {str(e)}")

            # Fallback to legacy exception handling for backward compatibility
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

    def _transform_domain_user_to_response(self, user) -> Dict[str, Any]:
        """Transform domain User object to expected response format."""
        return {
            "name": user.name,
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "is_sso_only": user.is_sso_only,
            "is_service": user.is_service,
            "date_joined": user.date_joined,
            "last_login": user.last_login,
            "role": user.role.name if user.role else None,
            "extra_roles": [role.name for role in user.extra_roles] if user.extra_roles else [],
        }

    def _transform_domain_user_to_detailed_response(self, user) -> Dict[str, Any]:
        """Transform domain User object to detailed response format."""
        return {
            "name": user.name,
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "is_sso_only": user.is_sso_only,
            "is_service": user.is_service,
            "date_joined": user.date_joined,
            "last_login": user.last_login,
            "role": (
                {
                    "name": user.role.name,
                    "id": user.role.id,
                    "arn": user.role.arn,
                    "type": user.role.type,
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
                        "type": role.type,
                    }
                    for role in user.extra_roles
                ]
                if user.extra_roles
                else []
            ),
        }

    def _transform_domain_role_to_response(self, role) -> Dict[str, Any]:
        """Transform domain Role object to expected response format."""
        return {
            "id": role.id,
            "name": role.name,
            "arn": role.arn,
            "type": role.type,
        }

    def _transform_domain_policy_to_response(self, policy) -> Dict[str, Any]:
        """Transform domain Policy object to expected response format."""
        return {
            "id": policy.id,
            "title": policy.title,
            "arn": policy.arn,
            "managed": policy.managed,
            "permissions": [{"bucket": p.bucket, "level": p.level} for p in policy.permissions],
            "role_ids": list(policy.role_ids),
        }

    def _transform_domain_sso_config_to_response(self, sso_config) -> Dict[str, Any]:
        """Transform domain SSOConfig object to expected response format."""
        return {
            "text": sso_config.text,
            "timestamp": sso_config.timestamp,
            "uploader": (
                {"name": sso_config.uploader.name, "email": sso_config.uploader.email} if sso_config.uploader else None
            ),
        }


# User Management Functions


async def admin_users_list(*, quilt_ops: Optional[QuiltOps] = None, context: RequestContext) -> Dict[str, Any]:
    """List all users in the registry with detailed information - Quilt governance and administrative operations

    Args:
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing:
        - success: Whether the operation succeeded
        - users: List of users with detailed information
        - count: Number of users found
        - formatted_table: Table-formatted output for better readability

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_users_list()
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        domain_users = quilt_ops_instance.admin.list_users()

        # Transform domain users to response format
        users_data = [service._transform_domain_user_to_response(user) for user in domain_users]

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
        return service._handle_admin_error(e, "list users")


async def admin_user_get(
    name: Annotated[
        str,
        Field(
            description="Username to retrieve",
            examples=["john-doe", "admin-user"],
        ),
    ],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Get detailed information about a specific user - Quilt governance and administrative operations

    Args:
        name: Username to retrieve
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing user information or error details

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_user_get(
            name="example-name",
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        if not name:
            return format_error_response("Username cannot be empty")

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        domain_user = quilt_ops_instance.admin.get_user(name)

        user_data = service._transform_domain_user_to_detailed_response(domain_user)

        return {
            "success": True,
            "user": user_data,
            "message": f"Retrieved user information for '{name}'",
        }

    except Exception as e:
        return service._handle_admin_error(e, f"get user '{name}'")


async def admin_user_create(
    name: Annotated[
        str,
        Field(
            description="Username for the new user",
            examples=["john-doe", "new-analyst"],
        ),
    ],
    email: Annotated[
        str,
        Field(
            description="Email address for the new user",
            examples=["user@example.com", "analyst@company.org"],
        ),
    ],
    role: Annotated[
        str,
        Field(
            description="Primary role for the user",
            examples=["viewer", "editor", "admin"],
        ),
    ],
    extra_roles: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="Additional roles to assign to the user",
            examples=[["data-scientist", "analyst"], []],
        ),
    ] = None,
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Create a new user in the registry - Quilt governance and administrative operations

    Args:
        name: Username for the new user
        email: Email address for the new user
        role: Primary role for the user
        extra_roles: Additional roles to assign to the user
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing creation result and user information

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_user_create(
            name="example-name",
            email="user@example.com",
            role="viewer",
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

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

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        domain_user = quilt_ops_instance.admin.create_user(
            name=name, email=email, role=role, extra_roles=extra_roles or []
        )

        user_data = service._transform_domain_user_to_response(domain_user)

        return {
            "success": True,
            "user": user_data,
            "message": f"Successfully created user '{name}' with role '{role}'",
        }

    except Exception as e:
        return service._handle_admin_error(e, f"create user '{name}'")


async def admin_user_delete(
    name: Annotated[
        str,
        Field(
            description="Username to delete",
            examples=["user-to-remove", "inactive-user"],
        ),
    ],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Delete a user from the registry - Quilt governance and administrative operations

    Args:
        name: Username to delete
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing deletion result

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_user_delete(
            name="example-name",
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        if not name:
            return format_error_response("Username cannot be empty")

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        quilt_ops_instance.admin.delete_user(name)

        return {"success": True, "message": f"Successfully deleted user '{name}'"}

    except Exception as e:
        return service._handle_admin_error(e, f"delete user '{name}'")


async def admin_user_set_email(
    name: Annotated[
        str,
        Field(
            description="Username to update",
            examples=["john-doe", "user123"],
        ),
    ],
    email: Annotated[
        str,
        Field(
            description="New email address",
            examples=["newemail@example.com", "updated@company.org"],
        ),
    ],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Update a user's email address - Quilt governance and administrative operations

    Args:
        name: Username to update
        email: New email address
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing update result and user information

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_user_set_email(
            name="example-name",
            email="user@example.com",
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        if not name:
            return format_error_response("Username cannot be empty")
        if not email:
            return format_error_response("Email cannot be empty")

        # Basic email validation
        if "@" not in email or "." not in email:
            return format_error_response("Invalid email format")

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        domain_user = quilt_ops_instance.admin.set_user_email(name, email)

        return {
            "success": True,
            "user": {"name": domain_user.name, "email": domain_user.email},
            "message": f"Successfully updated email for user '{name}' to '{email}'",
        }

    except Exception as e:
        return service._handle_admin_error(e, f"set email for user '{name}'")


async def admin_user_set_admin(
    name: Annotated[
        str,
        Field(
            description="Username to update",
            examples=["john-doe", "user123"],
        ),
    ],
    admin: Annotated[
        bool,
        Field(
            description="Whether the user should have admin privileges",
            examples=[True, False],
        ),
    ],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Set the admin status for a user - Quilt governance and administrative operations

    Args:
        name: Username to update
        admin: Whether the user should have admin privileges
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing update result and user information

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_user_set_admin(
            name="example-name",
            admin=True,
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        if not name:
            return format_error_response("Username cannot be empty")

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        domain_user = quilt_ops_instance.admin.set_user_admin(name, admin)

        return {
            "success": True,
            "user": {"name": domain_user.name, "is_admin": domain_user.is_admin},
            "message": f"Successfully {'granted' if admin else 'revoked'} admin privileges for user '{name}'",
        }

    except Exception as e:
        return service._handle_admin_error(e, f"set admin status for user '{name}'")


async def admin_user_set_active(
    name: Annotated[
        str,
        Field(
            description="Username to update",
            examples=["john-doe", "user123"],
        ),
    ],
    active: Annotated[
        bool,
        Field(
            description="Whether the user should be active",
            examples=[True, False],
        ),
    ],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Set the active status for a user - Quilt governance and administrative operations

    Args:
        name: Username to update
        active: Whether the user should be active
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing update result and user information

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_user_set_active(
            name="example-name",
            active=True,
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        if not name:
            return format_error_response("Username cannot be empty")

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        domain_user = quilt_ops_instance.admin.set_user_active(name, active)

        return {
            "success": True,
            "user": {"name": domain_user.name, "is_active": domain_user.is_active},
            "message": f"Successfully {'activated' if active else 'deactivated'} user '{name}'",
        }

    except Exception as e:
        return service._handle_admin_error(e, f"set active status for user '{name}'")


async def admin_user_reset_password(
    name: Annotated[
        str,
        Field(
            description="Username to reset password for",
            examples=["john-doe", "user123"],
        ),
    ],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Reset a user's password - Quilt governance and administrative operations

    Args:
        name: Username to reset password for
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing reset result

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_user_reset_password(
            name="example-name",
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        if not name:
            return format_error_response("Username cannot be empty")

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        quilt_ops_instance.admin.reset_user_password(name)

        return {
            "success": True,
            "message": f"Successfully reset password for user '{name}'. User will need to set a new password on next login.",
        }

    except Exception as e:
        return service._handle_admin_error(e, f"reset password for user '{name}'")


async def admin_user_set_role(
    name: Annotated[
        str,
        Field(
            description="Username to update",
            examples=["john-doe", "user123"],
        ),
    ],
    role: Annotated[
        str,
        Field(
            description="Primary role to assign",
            examples=["viewer", "editor", "admin"],
        ),
    ],
    extra_roles: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="Additional roles to assign",
            examples=[["data-scientist", "analyst"], []],
        ),
    ] = None,
    append: Annotated[
        bool,
        Field(
            default=False,
            description="Whether to append extra roles to existing ones (True) or replace them (False)",
        ),
    ] = False,
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Set the primary and extra roles for a user - Quilt governance and administrative operations

    Args:
        name: Username to update
        role: Primary role to assign
        extra_roles: Additional roles to assign
        append: Whether to append extra roles to existing ones (True) or replace them (False)
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing update result and user information

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_user_set_role(
            name="example-name",
            role="viewer",
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        if not name:
            return format_error_response("Username cannot be empty")
        if not role:
            return format_error_response("Role cannot be empty")

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        domain_user = quilt_ops_instance.admin.set_user_role(
            name=name, role=role, extra_roles=extra_roles or [], append=append
        )

        return {
            "success": True,
            "user": {
                "name": domain_user.name,
                "role": domain_user.role.name if domain_user.role else None,
                "extra_roles": [r.name for r in domain_user.extra_roles] if domain_user.extra_roles else [],
            },
            "message": f"Successfully updated roles for user '{name}'",
        }

    except Exception as e:
        return service._handle_admin_error(e, f"set roles for user '{name}'")


async def admin_user_add_roles(
    name: Annotated[
        str,
        Field(
            description="Username to update",
            examples=["john-doe", "user123"],
        ),
    ],
    roles: Annotated[
        List[str],
        Field(
            description="List of roles to add",
            examples=[["data-scientist", "analyst"], ["viewer"]],
        ),
    ],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Add roles to a user - Quilt governance and administrative operations

    Args:
        name: Username to update
        roles: List of roles to add
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing update result and user information

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_user_add_roles(
            name="example-name",
            roles=["viewer"],
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        if not name:
            return format_error_response("Username cannot be empty")
        if not roles:
            return format_error_response("Roles list cannot be empty")

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        domain_user = quilt_ops_instance.admin.add_user_roles(name, roles)

        return {
            "success": True,
            "user": {
                "name": domain_user.name,
                "role": domain_user.role.name if domain_user.role else None,
                "extra_roles": [r.name for r in domain_user.extra_roles] if domain_user.extra_roles else [],
            },
            "message": f"Successfully added roles {roles} to user '{name}'",
        }

    except Exception as e:
        return service._handle_admin_error(e, f"add roles to user '{name}'")


# Role Management Functions


async def admin_user_remove_roles(
    name: Annotated[
        str,
        Field(
            description="Username to update",
            examples=["john-doe", "user123"],
        ),
    ],
    roles: Annotated[
        List[str],
        Field(
            description="List of roles to remove",
            examples=[["data-scientist", "analyst"], ["viewer"]],
        ),
    ],
    fallback: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Fallback role if the primary role is removed",
            examples=["viewer", "editor"],
        ),
    ] = None,
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Remove roles from a user - Quilt governance and administrative operations

    Args:
        name: Username to update
        roles: List of roles to remove
        fallback: Fallback role if the primary role is removed
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing update result and user information

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_user_remove_roles(
            name="example-name",
            roles=["viewer"],
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        if not name:
            return format_error_response("Username cannot be empty")
        if not roles:
            return format_error_response("Roles list cannot be empty")

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        domain_user = quilt_ops_instance.admin.remove_user_roles(name, roles, fallback)

        return {
            "success": True,
            "user": {
                "name": domain_user.name,
                "role": domain_user.role.name if domain_user.role else None,
                "extra_roles": [r.name for r in domain_user.extra_roles] if domain_user.extra_roles else [],
            },
            "message": f"Successfully removed roles {roles} from user '{name}'",
        }

    except Exception as e:
        return service._handle_admin_error(e, f"remove roles from user '{name}'")


# Role Management Functions


async def admin_roles_list(*, quilt_ops: Optional[QuiltOps] = None, context: RequestContext) -> Dict[str, Any]:
    """List all available roles in the registry - Quilt governance and administrative operations

    Args:
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing:
        - success: Whether the operation succeeded
        - roles: List of roles with detailed information
        - count: Number of roles found
        - formatted_table: Table-formatted output for better readability

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_roles_list()
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        domain_roles = quilt_ops_instance.admin.list_roles()

        # Transform domain roles to response format
        roles_data = [service._transform_domain_role_to_response(role) for role in domain_roles]

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
        return service._handle_admin_error(e, "list roles")


# SSO Configuration Functions


async def admin_sso_config_get(*, quilt_ops: Optional[QuiltOps] = None, context: RequestContext) -> Dict[str, Any]:
    """Get the current SSO configuration - Quilt governance and administrative operations

    Args:
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing SSO configuration or None if not configured

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_sso_config_get()
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        # Use QuiltOps.admin interface
        quilt_ops_instance = service._get_quilt_ops()
        domain_sso_config = quilt_ops_instance.admin.get_sso_config()

        if domain_sso_config is None:
            return {
                "success": True,
                "sso_config": None,
                "message": "No SSO configuration found",
            }

        config_data = service._transform_domain_sso_config_to_response(domain_sso_config)

        return {
            "success": True,
            "sso_config": config_data,
            "message": "Retrieved SSO configuration",
        }

    except Exception as e:
        return service._handle_admin_error(e, "get SSO configuration")


async def admin_sso_config_set(
    config: Annotated[
        Dict[str, Any],
        Field(
            description="SSO configuration as a dictionary object",
            examples=[
                {"provider": "okta", "saml_config": "<saml_config>...</saml_config>"},
                {"provider": "saml", "entity_id": "https://example.com"},
            ],
        ),
    ],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Set the SSO configuration - Quilt governance and administrative operations

    Args:
        config: SSO configuration as a dictionary (will be JSON-serialized before sending to backend)
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing update result and configuration information

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_sso_config_set(
            config={"provider": "okta", "saml_config": "<saml_config>...</saml_config>"},
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        if not config:
            return format_error_response("SSO configuration cannot be empty")

        # Use QuiltOps.admin interface (backend handles JSON serialization)
        quilt_ops_instance = service._get_quilt_ops()
        domain_sso_config = quilt_ops_instance.admin.set_sso_config(config)

        config_data = service._transform_domain_sso_config_to_response(domain_sso_config)

        return {
            "success": True,
            "sso_config": config_data,
            "message": "Successfully updated SSO configuration",
        }

    except Exception as e:
        return service._handle_admin_error(e, "set SSO configuration")


async def admin_sso_config_remove(*, quilt_ops: Optional[QuiltOps] = None, context: RequestContext) -> Dict[str, Any]:
    """Remove the SSO configuration - Quilt governance and administrative operations

    Args:
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing removal result

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_sso_config_remove()
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        # Use QuiltOps.admin interface
        # Note: quilt3 uses set_sso_config(None) to remove config, there is no separate remove method
        quilt_ops_instance = service._get_quilt_ops()
        quilt_ops_instance.admin.set_sso_config(None)

        return {"success": True, "message": "Successfully removed SSO configuration"}

    except Exception as e:
        return service._handle_admin_error(e, "remove SSO configuration")


# Enhanced Tabulator Administration Functions


async def admin_tabulator_open_query_get(
    *, quilt_ops: Optional[QuiltOps] = None, context: RequestContext
) -> Dict[str, Any]:
    """Get the current tabulator open query status - Quilt governance and administrative operations

    Args:
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing open query status

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_tabulator_open_query_get()
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    try:
        service = GovernanceService(quilt_ops)
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        quilt_ops_instance = service._get_quilt_ops()
        open_query_result = quilt_ops_instance.get_open_query_status()
        if not open_query_result.get("success"):
            return format_error_response(open_query_result.get("message", "Failed to get tabulator open query status"))
        open_query_enabled = bool(open_query_result.get("open_query_enabled", False))

        return {
            "success": True,
            "open_query_enabled": open_query_enabled,
            "message": f"Open query is {'enabled' if open_query_enabled else 'disabled'}",
        }

    except Exception as e:
        service = GovernanceService(quilt_ops)
        return service._handle_admin_error(e, "get tabulator open query status")


async def admin_tabulator_open_query_set(
    enabled: Annotated[
        bool,
        Field(
            description="Whether to enable open query",
            examples=[True, False],
        ),
    ],
    *,
    context: RequestContext,
) -> Dict[str, Any]:
    """Set the tabulator open query status - Quilt governance and administrative operations

    Args:
        enabled: Whether to enable open query

    Returns:
        Dict containing update result

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_tabulator_open_query_set(
            enabled=True,
        )
        # Next step: Communicate the governance change and confirm with adjacent admin tools if needed.
        ```
    """
    try:
        service = GovernanceService()
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        quilt_ops_instance = service._get_quilt_ops()
        set_result = quilt_ops_instance.set_open_query(enabled)
        if not set_result.get("success"):
            return format_error_response(set_result.get("message", "Failed to set tabulator open query status"))

        return {
            "success": True,
            "open_query_enabled": enabled,
            "message": f"Successfully {'enabled' if enabled else 'disabled'} tabulator open query",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, "set tabulator open query status")


# Policy Management Functions
#
# Policies carry the bucket-level permissions that roles attach and users inherit.
# Without these, the admin surface can read the access model but never change it.


def _permissions_from_input(permissions: List[Dict[str, Any]]) -> List[Any]:
    """Build domain Permission objects from tool input.

    Raises ValueError with an actionable message; callers turn that into an error
    response rather than letting a bare validation error reach the client.
    """
    from ..domain.policy import PERMISSION_LEVELS, Permission

    built = []
    for entry in permissions:
        if not isinstance(entry, dict):
            raise ValueError(
                f"each permission must be an object with 'bucket' and 'level', got {type(entry).__name__}"
            )
        bucket = entry.get("bucket")
        level = entry.get("level")
        if not bucket:
            raise ValueError("each permission needs a non-empty 'bucket'")
        if level not in PERMISSION_LEVELS:
            raise ValueError(f"permission level must be one of {list(PERMISSION_LEVELS)}, got {level!r}")
        built.append(Permission(bucket=bucket, level=level))
    return built


async def admin_policies_list(*, quilt_ops: Optional[QuiltOps] = None, context: RequestContext) -> Dict[str, Any]:
    """List all policies in the registry - Quilt governance and administrative operations

    Returns:
        Dict containing the policy list and count

    Next step:
        Attach a policy to a role with admin_role_create_managed, or inspect one with admin_policy_get.
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check

        policies = service._get_quilt_ops().admin.list_policies()
        policies_data = [service._transform_domain_policy_to_response(p) for p in policies]
        return {
            "success": True,
            "policies": policies_data,
            "count": len(policies_data),
            "message": f"Found {len(policies_data)} policies",
        }
    except Exception as e:
        return service._handle_admin_error(e, "list policies")


async def admin_policy_get(
    id_or_title: Annotated[
        str,
        Field(description="Policy ID or title", examples=["ReadOnlyAnalysts", "1a2b3c4d"]),
    ],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Get a policy by ID or title - Quilt governance and administrative operations

    Returns:
        Dict containing the policy, or an error when it does not exist
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check
        if not id_or_title:
            return format_error_response("Policy ID or title cannot be empty")

        policy = service._get_quilt_ops().admin.get_policy(id_or_title)
        if policy is None:
            return format_error_response(f"Policy not found: {id_or_title}")
        return {
            "success": True,
            "policy": service._transform_domain_policy_to_response(policy),
            "message": f"Found policy '{policy.title}'",
        }
    except Exception as e:
        return service._handle_admin_error(e, f"get policy '{id_or_title}'")


async def admin_policy_create_managed(
    title: Annotated[
        str,
        Field(description="Policy title", examples=["ReadOnlyAnalysts"]),
    ],
    permissions: Annotated[
        List[Dict[str, Any]],
        Field(
            description="Bucket permissions, each {'bucket': name, 'level': 'READ' or 'READ_WRITE'}",
            examples=[[{"bucket": "research-data", "level": "READ"}]],
        ),
    ],
    role_ids: Annotated[
        Optional[List[str]],
        Field(default=None, description="Role IDs to attach this policy to"),
    ] = None,
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Create a Quilt-managed policy from bucket permissions - Quilt governance and administrative operations

    Quilt owns the underlying IAM policy. Use admin_policy_create_unmanaged to wrap
    an IAM policy that already exists.

    Returns:
        Dict containing the created policy
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check
        if not title:
            return format_error_response("Policy title cannot be empty")
        if not permissions:
            return format_error_response("A managed policy needs at least one bucket permission")

        try:
            domain_permissions = _permissions_from_input(permissions)
        except ValueError as ve:
            return format_error_response(f"Invalid permissions: {ve}")

        policy = service._get_quilt_ops().admin.create_managed_policy(
            title=title, permissions=domain_permissions, role_ids=role_ids or []
        )
        return {
            "success": True,
            "policy": service._transform_domain_policy_to_response(policy),
            "message": f"Successfully created managed policy '{title}'",
        }
    except Exception as e:
        return service._handle_admin_error(e, f"create managed policy '{title}'")


async def admin_policy_create_unmanaged(
    title: Annotated[str, Field(description="Policy title", examples=["ExistingIAMPolicy"])],
    arn: Annotated[
        str,
        Field(description="Existing IAM policy ARN", examples=["arn:aws:iam::123456789012:policy/MyPolicy"]),
    ],
    role_ids: Annotated[
        Optional[List[str]],
        Field(default=None, description="Role IDs to attach this policy to"),
    ] = None,
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Create a policy wrapping an existing IAM policy ARN - Quilt governance and administrative operations

    Returns:
        Dict containing the created policy
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check
        if not title:
            return format_error_response("Policy title cannot be empty")
        if not arn:
            return format_error_response("Policy ARN cannot be empty")

        policy = service._get_quilt_ops().admin.create_unmanaged_policy(title=title, arn=arn, role_ids=role_ids or [])
        return {
            "success": True,
            "policy": service._transform_domain_policy_to_response(policy),
            "message": f"Successfully created unmanaged policy '{title}'",
        }
    except Exception as e:
        return service._handle_admin_error(e, f"create unmanaged policy '{title}'")


async def admin_policy_patch_managed(
    id_or_title: Annotated[str, Field(description="Policy ID or title")],
    title: Annotated[Optional[str], Field(default=None, description="New title (unchanged if omitted)")] = None,
    permissions: Annotated[
        Optional[List[Dict[str, Any]]],
        Field(
            default=None,
            description="Replacement bucket permissions (unchanged if omitted)",
            examples=[[{"bucket": "research-data", "level": "READ_WRITE"}]],
        ),
    ] = None,
    role_ids: Annotated[
        Optional[List[str]],
        Field(default=None, description="Replacement role IDs (unchanged if omitted)"),
    ] = None,
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Partially update a managed policy - Quilt governance and administrative operations

    Only the fields provided change; everything else keeps its current value.
    Fails if the target policy is unmanaged.

    Returns:
        Dict containing the updated policy
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check
        if not id_or_title:
            return format_error_response("Policy ID or title cannot be empty")
        if title is None and permissions is None and role_ids is None:
            return format_error_response("Nothing to update - provide title, permissions or role_ids")

        domain_permissions = None
        if permissions is not None:
            try:
                domain_permissions = _permissions_from_input(permissions)
            except ValueError as ve:
                return format_error_response(f"Invalid permissions: {ve}")

        policy = service._get_quilt_ops().admin.patch_managed_policy(
            id_or_title=id_or_title, title=title, permissions=domain_permissions, role_ids=role_ids
        )
        return {
            "success": True,
            "policy": service._transform_domain_policy_to_response(policy),
            "message": f"Successfully updated managed policy '{id_or_title}'",
        }
    except Exception as e:
        return service._handle_admin_error(e, f"patch managed policy '{id_or_title}'")


async def admin_policy_patch_unmanaged(
    id_or_title: Annotated[str, Field(description="Policy ID or title")],
    title: Annotated[Optional[str], Field(default=None, description="New title (unchanged if omitted)")] = None,
    arn: Annotated[Optional[str], Field(default=None, description="New IAM ARN (unchanged if omitted)")] = None,
    role_ids: Annotated[
        Optional[List[str]],
        Field(default=None, description="Replacement role IDs (unchanged if omitted)"),
    ] = None,
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Partially update an unmanaged policy - Quilt governance and administrative operations

    Only the fields provided change. Fails if the target policy is managed.

    Returns:
        Dict containing the updated policy
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check
        if not id_or_title:
            return format_error_response("Policy ID or title cannot be empty")
        if title is None and arn is None and role_ids is None:
            return format_error_response("Nothing to update - provide title, arn or role_ids")

        policy = service._get_quilt_ops().admin.patch_unmanaged_policy(
            id_or_title=id_or_title, title=title, arn=arn, role_ids=role_ids
        )
        return {
            "success": True,
            "policy": service._transform_domain_policy_to_response(policy),
            "message": f"Successfully updated unmanaged policy '{id_or_title}'",
        }
    except Exception as e:
        return service._handle_admin_error(e, f"patch unmanaged policy '{id_or_title}'")


async def admin_policy_delete(
    id_or_title: Annotated[str, Field(description="Policy ID or title")],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Delete a policy from the registry - Quilt governance and administrative operations

    Removes access the policy granted. Roles referencing it lose those permissions.

    Returns:
        Dict confirming the deletion
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check
        if not id_or_title:
            return format_error_response("Policy ID or title cannot be empty")

        service._get_quilt_ops().admin.delete_policy(id_or_title)
        return {
            "success": True,
            "message": f"Successfully deleted policy '{id_or_title}'",
        }
    except Exception as e:
        return service._handle_admin_error(e, f"delete policy '{id_or_title}'")


# Role Mutation Functions


async def admin_role_get(
    id_or_name: Annotated[str, Field(description="Role ID or name", examples=["ReadWriteRole"])],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Get a role by ID or name - Quilt governance and administrative operations

    Returns:
        Dict containing the role, or an error when it does not exist
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check
        if not id_or_name:
            return format_error_response("Role ID or name cannot be empty")

        role = service._get_quilt_ops().admin.get_role(id_or_name)
        if role is None:
            return format_error_response(f"Role not found: {id_or_name}")
        return {
            "success": True,
            "role": service._transform_domain_role_to_response(role),
            "message": f"Found role '{role.name}'",
        }
    except Exception as e:
        return service._handle_admin_error(e, f"get role '{id_or_name}'")


async def admin_role_create_managed(
    name: Annotated[str, Field(description="Role name", examples=["Analysts"])],
    policy_ids: Annotated[
        Optional[List[str]],
        Field(default=None, description="Policy IDs to attach to this role"),
    ] = None,
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Create a Quilt-managed role from policy IDs - Quilt governance and administrative operations

    List candidate policies with admin_policies_list first.

    Returns:
        Dict containing the created role
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check
        if not name:
            return format_error_response("Role name cannot be empty")

        role = service._get_quilt_ops().admin.create_managed_role(name=name, policy_ids=policy_ids or [])
        return {
            "success": True,
            "role": service._transform_domain_role_to_response(role),
            "message": f"Successfully created managed role '{name}'",
        }
    except Exception as e:
        return service._handle_admin_error(e, f"create managed role '{name}'")


async def admin_role_create_unmanaged(
    name: Annotated[str, Field(description="Role name")],
    arn: Annotated[
        str,
        Field(description="Existing IAM role ARN", examples=["arn:aws:iam::123456789012:role/MyRole"]),
    ],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Create a role wrapping an existing IAM role ARN - Quilt governance and administrative operations

    Returns:
        Dict containing the created role
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check
        if not name:
            return format_error_response("Role name cannot be empty")
        if not arn:
            return format_error_response("Role ARN cannot be empty")

        role = service._get_quilt_ops().admin.create_unmanaged_role(name=name, arn=arn)
        return {
            "success": True,
            "role": service._transform_domain_role_to_response(role),
            "message": f"Successfully created unmanaged role '{name}'",
        }
    except Exception as e:
        return service._handle_admin_error(e, f"create unmanaged role '{name}'")


async def admin_role_delete(
    id_or_name: Annotated[str, Field(description="Role ID or name")],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Delete a role from the registry - Quilt governance and administrative operations

    Fails when the role is still assigned to users, is reserved, or is referenced
    by the SSO config.

    Returns:
        Dict confirming the deletion
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check
        if not id_or_name:
            return format_error_response("Role ID or name cannot be empty")

        service._get_quilt_ops().admin.delete_role(id_or_name)
        return {
            "success": True,
            "message": f"Successfully deleted role '{id_or_name}'",
        }
    except Exception as e:
        return service._handle_admin_error(e, f"delete role '{id_or_name}'")


async def admin_role_set_default(
    id_or_name: Annotated[str, Field(description="Role ID or name to make the default")],
    *,
    quilt_ops: Optional[QuiltOps] = None,
    context: RequestContext,
) -> Dict[str, Any]:
    """Set the role assigned to new users by default - Quilt governance and administrative operations

    Affects every user created afterwards, so confirm the intended role first.

    Returns:
        Dict containing the new default role
    """
    service = GovernanceService(quilt_ops)
    try:
        error_check = service._check_admin_available()
        if error_check:
            return error_check
        if not id_or_name:
            return format_error_response("Role ID or name cannot be empty")

        role = service._get_quilt_ops().admin.set_default_role(id_or_name)
        return {
            "success": True,
            "role": service._transform_domain_role_to_response(role),
            "message": f"Successfully set '{role.name}' as the default role",
        }
    except Exception as e:
        return service._handle_admin_error(e, f"set default role '{id_or_name}'")
