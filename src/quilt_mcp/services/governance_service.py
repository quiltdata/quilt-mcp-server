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
from ..utils import format_error_response
from ..formatting import format_users_as_table, format_roles_as_table
from ..ops.quilt_ops import QuiltOps
from ..ops.exceptions import NotFoundError, BackendError, ValidationError, AuthenticationError, PermissionError

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

    def __init__(self, quilt_ops: Optional[QuiltOps] = None, use_quilt_auth: bool = True):
        self.quilt_ops = quilt_ops
        self.use_quilt_auth = use_quilt_auth
        self.admin_available = ADMIN_AVAILABLE and use_quilt_auth

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


async def admin_users_list(quilt_ops: Optional[QuiltOps] = None) -> Dict[str, Any]:
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
    quilt_ops: Optional[QuiltOps] = None,
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
    quilt_ops: Optional[QuiltOps] = None,
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
    quilt_ops: Optional[QuiltOps] = None,
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
    quilt_ops: Optional[QuiltOps] = None,
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
    quilt_ops: Optional[QuiltOps] = None,
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
    quilt_ops: Optional[QuiltOps] = None,
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
    quilt_ops: Optional[QuiltOps] = None,
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
    quilt_ops: Optional[QuiltOps] = None,
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
    quilt_ops: Optional[QuiltOps] = None,
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
    quilt_ops: Optional[QuiltOps] = None,
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


async def admin_roles_list(quilt_ops: Optional[QuiltOps] = None) -> Dict[str, Any]:
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


async def admin_sso_config_get(quilt_ops: Optional[QuiltOps] = None) -> Dict[str, Any]:
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
        str,
        Field(
            description="SSO configuration text",
            examples=["<saml_config>...</saml_config>", "provider_config_string"],
        ),
    ],
    quilt_ops: Optional[QuiltOps] = None,
) -> Dict[str, Any]:
    """Set the SSO configuration - Quilt governance and administrative operations

    Args:
        config: SSO configuration text
        quilt_ops: QuiltOps instance for admin operations (optional, will create if not provided)

    Returns:
        Dict containing update result and configuration information

    Next step:
        Communicate the governance change and confirm with adjacent admin tools if needed.

    Example:
        ```python
        from quilt_mcp.tools import governance

        result = governance.admin_sso_config_set(
            config="<saml_config>...</saml_config>",
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

        # Use QuiltOps.admin interface
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


async def admin_sso_config_remove(quilt_ops: Optional[QuiltOps] = None) -> Dict[str, Any]:
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
        quilt_ops_instance = service._get_quilt_ops()
        quilt_ops_instance.admin.remove_sso_config()

        return {"success": True, "message": "Successfully removed SSO configuration"}

    except Exception as e:
        return service._handle_admin_error(e, "remove SSO configuration")


# Enhanced Tabulator Administration Functions


async def admin_tabulator_open_query_get(quilt_ops: Optional[QuiltOps] = None) -> Dict[str, Any]:
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

        # Note: Tabulator operations are not yet part of AdminOps interface
        # Using direct import for backward compatibility
        import quilt3.admin.tabulator as admin_tabulator

        open_query_enabled = admin_tabulator.get_open_query()

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

        import quilt3.admin.tabulator as admin_tabulator

        admin_tabulator.set_open_query(enabled)

        return {
            "success": True,
            "open_query_enabled": enabled,
            "message": f"Successfully {'enabled' if enabled else 'disabled'} tabulator open query",
        }

    except Exception as e:
        service = GovernanceService()
        return service._handle_admin_error(e, "set tabulator open query status")
