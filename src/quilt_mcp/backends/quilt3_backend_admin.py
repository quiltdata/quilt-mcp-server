"""
Quilt3_Backend admin mixin for administrative operations.

This module provides the admin mixin that implements AdminOps interface methods
using the quilt3.admin modules. It follows the established backend pattern with
proper error handling and transformation to domain objects.
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

from quilt_mcp.ops.admin_ops import AdminOps
from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, ValidationError, NotFoundError, PermissionError
from quilt_mcp.domain.user import User
from quilt_mcp.domain.role import Role
from quilt_mcp.domain.sso_config import SSOConfig

logger = logging.getLogger(__name__)


class Quilt3_Backend_Admin(AdminOps):
    """Mixin for admin-related operations using quilt3.admin modules.

    This mixin implements the AdminOps interface using quilt3.admin modules,
    providing domain-driven admin operations while maintaining compatibility
    with the existing quilt3 library patterns.

    The mixin follows the established pattern:
    - Uses self.quilt3 for library access (set by Quilt3_Backend_Base)
    - Transforms quilt3 objects to domain objects
    - Maps quilt3 exceptions to domain exceptions
    - Provides comprehensive error handling and logging
    """

    # Type hints for attributes and methods provided by Quilt3_Backend_Base
    if TYPE_CHECKING:
        quilt3: "ModuleType"

        def _normalize_datetime(self, dt: Any) -> Optional[str]: ...

    def list_users(self) -> List[User]:
        """List all users in the registry.

        Returns:
            List of User objects representing all registered users

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails (network, API errors, etc.)
            PermissionError: When user lacks admin privileges to list users
        """
        try:
            logger.debug("Listing users via quilt3.admin.users")

            # Import quilt3.admin.users dynamically to handle availability
            import quilt3.admin.users as admin_users

            quilt3_users = admin_users.list()

            # Transform quilt3 user objects to domain objects
            domain_users = [self._transform_quilt3_user_to_domain(user) for user in quilt3_users]

            logger.debug(f"Successfully listed {len(domain_users)} users")
            return domain_users

        except ImportError as e:
            logger.error(f"quilt3.admin.users not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            self._handle_admin_error(e, "list users")
            # This line should never be reached due to exception raising above
            return []  # pragma: no cover

    def get_user(self, name: str) -> User:
        """Get detailed information about a specific user.

        Args:
            name: Username to retrieve information for

        Returns:
            User object with detailed user information

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When name parameter is invalid
            NotFoundError: When the specified user doesn't exist
            PermissionError: When user lacks admin privileges to view user details
        """
        try:
            if not name or not name.strip():
                raise ValidationError("Username cannot be empty")

            logger.debug(f"Getting user: {name}")

            import quilt3.admin.users as admin_users

            quilt3_user = admin_users.get(name)
            domain_user = self._transform_quilt3_user_to_domain(quilt3_user)

            logger.debug(f"Successfully retrieved user: {name}")
            return domain_user

        except ImportError as e:
            logger.error(f"quilt3.admin.users not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except ValidationError:
            # Re-raise ValidationError without wrapping
            raise
        except Exception as e:
            logger.error(f"Failed to get user {name}: {e}")
            self._handle_admin_error(e, f"get user {name}")
            # This line should never be reached due to exception raising above
            raise  # pragma: no cover

    def create_user(self, name: str, email: str, role: str, extra_roles: Optional[List[str]] = None) -> User:
        """Create a new user in the registry.

        Args:
            name: Username for the new user
            email: Email address for the new user
            role: Primary role to assign to the user
            extra_roles: Additional roles to assign to the user (optional)

        Returns:
            User object representing the newly created user

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When parameters are invalid (invalid email, role names, etc.)
            PermissionError: When user lacks admin privileges to create users
            ValidationError: When a user with the same name already exists
        """
        try:
            if not name or not name.strip():
                raise ValidationError("Username cannot be empty")
            if not email or not email.strip():
                raise ValidationError("Email cannot be empty")
            if not role or not role.strip():
                raise ValidationError("Role cannot be empty")

            logger.debug(f"Creating user: {name} with email: {email} and role: {role}")

            import quilt3.admin.users as admin_users

            # Handle extra_roles parameter
            extra_roles_list = extra_roles if extra_roles is not None else []

            quilt3_user = admin_users.create(name=name, email=email, role=role, extra_roles=extra_roles_list)

            domain_user = self._transform_quilt3_user_to_domain(quilt3_user)

            logger.debug(f"Successfully created user: {name}")
            return domain_user

        except ImportError as e:
            logger.error(f"quilt3.admin.users not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to create user {name}: {e}")
            self._handle_admin_error(e, f"create user {name}")
            # This line should never be reached due to exception raising above
            raise  # pragma: no cover

    def delete_user(self, name: str) -> None:
        """Delete a user from the registry.

        Args:
            name: Username of the user to delete

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When name parameter is invalid
            NotFoundError: When the specified user doesn't exist
            PermissionError: When user lacks admin privileges to delete users
        """
        try:
            if not name or not name.strip():
                raise ValidationError("Username cannot be empty")

            logger.debug(f"Deleting user: {name}")

            import quilt3.admin.users as admin_users

            admin_users.delete(name)

            logger.debug(f"Successfully deleted user: {name}")

        except ImportError as e:
            logger.error(f"quilt3.admin.users not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to delete user {name}: {e}")
            self._handle_admin_error(e, f"delete user {name}")

    def set_user_email(self, name: str, email: str) -> User:
        """Update a user's email address.

        Args:
            name: Username of the user to update
            email: New email address for the user

        Returns:
            User object with updated email information

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When parameters are invalid (invalid email format, etc.)
            NotFoundError: When the specified user doesn't exist
            PermissionError: When user lacks admin privileges to modify users
        """
        try:
            if not name or not name.strip():
                raise ValidationError("Username cannot be empty")
            if not email or not email.strip():
                raise ValidationError("Email cannot be empty")

            logger.debug(f"Setting email for user {name}: {email}")

            import quilt3.admin.users as admin_users

            quilt3_user = admin_users.set_email(name, email)
            domain_user = self._transform_quilt3_user_to_domain(quilt3_user)

            logger.debug(f"Successfully set email for user: {name}")
            return domain_user

        except ImportError as e:
            logger.error(f"quilt3.admin.users not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to set email for user {name}: {e}")
            self._handle_admin_error(e, f"set email for user {name}")
            # This line should never be reached due to exception raising above
            raise  # pragma: no cover

    def set_user_admin(self, name: str, admin: bool) -> User:
        """Set the admin status for a user.

        Args:
            name: Username of the user to update
            admin: True to grant admin privileges, False to revoke

        Returns:
            User object with updated admin status

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When name parameter is invalid
            NotFoundError: When the specified user doesn't exist
            PermissionError: When user lacks admin privileges to modify user permissions
        """
        try:
            if not name or not name.strip():
                raise ValidationError("Username cannot be empty")

            logger.debug(f"Setting admin status for user {name}: {admin}")

            import quilt3.admin.users as admin_users

            quilt3_user = admin_users.set_admin(name, admin)
            domain_user = self._transform_quilt3_user_to_domain(quilt3_user)

            logger.debug(f"Successfully set admin status for user: {name}")
            return domain_user

        except ImportError as e:
            logger.error(f"quilt3.admin.users not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to set admin status for user {name}: {e}")
            self._handle_admin_error(e, f"set admin status for user {name}")
            # This line should never be reached due to exception raising above
            raise  # pragma: no cover

    def set_user_active(self, name: str, active: bool) -> User:
        """Set the active status for a user.

        Args:
            name: Username of the user to update
            active: True to activate the user, False to deactivate

        Returns:
            User object with updated active status

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When name parameter is invalid
            NotFoundError: When the specified user doesn't exist
            PermissionError: When user lacks admin privileges to modify users
        """
        try:
            if not name or not name.strip():
                raise ValidationError("Username cannot be empty")

            logger.debug(f"Setting active status for user {name}: {active}")

            import quilt3.admin.users as admin_users

            quilt3_user = admin_users.set_active(name, active)
            domain_user = self._transform_quilt3_user_to_domain(quilt3_user)

            logger.debug(f"Successfully set active status for user: {name}")
            return domain_user

        except ImportError as e:
            logger.error(f"quilt3.admin.users not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to set active status for user {name}: {e}")
            self._handle_admin_error(e, f"set active status for user {name}")
            # This line should never be reached due to exception raising above
            raise  # pragma: no cover

    def reset_user_password(self, name: str) -> None:
        """Reset a user's password.

        Args:
            name: Username of the user whose password should be reset

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When name parameter is invalid
            NotFoundError: When the specified user doesn't exist
            PermissionError: When user lacks admin privileges to reset passwords
        """
        try:
            if not name or not name.strip():
                raise ValidationError("Username cannot be empty")

            logger.debug(f"Resetting password for user: {name}")

            import quilt3.admin.users as admin_users

            admin_users.reset_password(name)

            logger.debug(f"Successfully reset password for user: {name}")

        except ImportError as e:
            logger.error(f"quilt3.admin.users not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to reset password for user {name}: {e}")
            self._handle_admin_error(e, f"reset password for user {name}")

    def set_user_role(
        self, name: str, role: str, extra_roles: Optional[List[str]] = None, append: bool = False
    ) -> User:
        """Set the primary and extra roles for a user.

        Args:
            name: Username of the user to update
            role: Primary role to assign to the user
            extra_roles: Additional roles to assign to the user (optional)
            append: If True, append to existing roles; if False, replace all roles

        Returns:
            User object with updated role assignments

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When parameters are invalid (invalid role names, etc.)
            NotFoundError: When the specified user or roles don't exist
            PermissionError: When user lacks admin privileges to modify user roles
        """
        try:
            if not name or not name.strip():
                raise ValidationError("Username cannot be empty")
            if not role or not role.strip():
                raise ValidationError("Role cannot be empty")

            logger.debug(f"Setting role for user {name}: {role}, extra_roles: {extra_roles}, append: {append}")

            import quilt3.admin.users as admin_users

            # Handle extra_roles parameter
            extra_roles_list = extra_roles if extra_roles is not None else []

            quilt3_user = admin_users.set_role(name=name, role=role, extra_roles=extra_roles_list, append=append)

            domain_user = self._transform_quilt3_user_to_domain(quilt3_user)

            logger.debug(f"Successfully set role for user: {name}")
            return domain_user

        except ImportError as e:
            logger.error(f"quilt3.admin.users not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to set role for user {name}: {e}")
            self._handle_admin_error(e, f"set role for user {name}")
            # This line should never be reached due to exception raising above
            raise  # pragma: no cover

    def add_user_roles(self, name: str, roles: List[str]) -> User:
        """Add roles to a user.

        Args:
            name: Username of the user to update
            roles: List of role names to add to the user

        Returns:
            User object with updated role assignments

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When parameters are invalid (invalid role names, etc.)
            NotFoundError: When the specified user or roles don't exist
            PermissionError: When user lacks admin privileges to modify user roles
        """
        try:
            if not name or not name.strip():
                raise ValidationError("Username cannot be empty")
            if not roles:
                raise ValidationError("Roles list cannot be empty")

            logger.debug(f"Adding roles to user {name}: {roles}")

            import quilt3.admin.users as admin_users

            quilt3_user = admin_users.add_roles(name, roles)
            domain_user = self._transform_quilt3_user_to_domain(quilt3_user)

            logger.debug(f"Successfully added roles to user: {name}")
            return domain_user

        except ImportError as e:
            logger.error(f"quilt3.admin.users not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to add roles to user {name}: {e}")
            self._handle_admin_error(e, f"add roles to user {name}")
            # This line should never be reached due to exception raising above
            raise  # pragma: no cover

    def remove_user_roles(self, name: str, roles: List[str], fallback: Optional[str] = None) -> User:
        """Remove roles from a user.

        Args:
            name: Username of the user to update
            roles: List of role names to remove from the user
            fallback: Optional fallback role to assign if all roles are removed

        Returns:
            User object with updated role assignments

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When parameters are invalid (invalid role names, etc.)
            NotFoundError: When the specified user or roles don't exist
            PermissionError: When user lacks admin privileges to modify user roles
        """
        try:
            if not name or not name.strip():
                raise ValidationError("Username cannot be empty")
            if not roles:
                raise ValidationError("Roles list cannot be empty")

            logger.debug(f"Removing roles from user {name}: {roles}, fallback: {fallback}")

            import quilt3.admin.users as admin_users

            quilt3_user = admin_users.remove_roles(name, roles, fallback)
            domain_user = self._transform_quilt3_user_to_domain(quilt3_user)

            logger.debug(f"Successfully removed roles from user: {name}")
            return domain_user

        except ImportError as e:
            logger.error(f"quilt3.admin.users not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to remove roles from user {name}: {e}")
            self._handle_admin_error(e, f"remove roles from user {name}")
            # This line should never be reached due to exception raising above
            raise  # pragma: no cover

    def list_roles(self) -> List[Role]:
        """List all available roles in the registry.

        Returns:
            List of Role objects representing all available roles

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails (network, API errors, etc.)
            PermissionError: When user lacks admin privileges to list roles
        """
        try:
            logger.debug("Listing roles via quilt3.admin.roles")

            import quilt3.admin.roles as admin_roles

            quilt3_roles = admin_roles.list()

            # Transform quilt3 role objects to domain objects
            domain_roles = [self._transform_quilt3_role_to_domain(role) for role in quilt3_roles]

            logger.debug(f"Successfully listed {len(domain_roles)} roles")
            return domain_roles

        except ImportError as e:
            logger.error(f"quilt3.admin.roles not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to list roles: {e}")
            self._handle_admin_error(e, "list roles")
            # This line should never be reached due to exception raising above
            return []  # pragma: no cover

    def get_sso_config(self) -> Optional[SSOConfig]:
        """Get the current SSO configuration.

        Returns:
            SSOConfig object with current configuration, or None if no config exists

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails (network, API errors, etc.)
            PermissionError: When user lacks admin privileges to view SSO configuration
        """
        try:
            logger.debug("Getting SSO configuration via quilt3.admin.sso_config")

            import quilt3.admin.sso_config as admin_sso_config

            quilt3_sso_config = admin_sso_config.get()

            if quilt3_sso_config is None:
                logger.debug("No SSO configuration found")
                return None

            domain_sso_config = self._transform_quilt3_sso_config_to_domain(quilt3_sso_config)

            logger.debug("Successfully retrieved SSO configuration")
            return domain_sso_config

        except ImportError as e:
            logger.error(f"quilt3.admin.sso_config not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except Exception as e:
            logger.error(f"Failed to get SSO configuration: {e}")
            self._handle_admin_error(e, "get SSO configuration")
            # This line should never be reached due to exception raising above
            return None  # pragma: no cover

    def set_sso_config(self, config: Optional[Dict[str, Any]]) -> Optional[SSOConfig]:
        """Set or remove the SSO configuration.

        Args:
            config: SSO configuration as a dictionary, or None to remove configuration

        Returns:
            SSOConfig object representing the updated configuration, or None if removed

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When config parameter is invalid
            PermissionError: When user lacks admin privileges to modify SSO configuration
        """
        import json

        try:
            # Serialize config to JSON string (quilt3 expects string or None)
            config_str: Optional[str] = None
            if config is not None:
                if not config:
                    raise ValidationError("SSO configuration cannot be empty")
                config_str = json.dumps(config)

            logger.debug("Setting SSO configuration via quilt3.admin.sso_config")

            import quilt3.admin.sso_config as admin_sso_config

            quilt3_sso_config = admin_sso_config.set(config_str)

            # If config was None (removal), return None
            if config is None:
                logger.debug("Successfully removed SSO configuration")
                return None

            if quilt3_sso_config is None:
                raise BackendError("Failed to set SSO config: No config data returned")

            domain_sso_config = self._transform_quilt3_sso_config_to_domain(quilt3_sso_config)

            logger.debug("Successfully set SSO configuration")
            return domain_sso_config

        except ImportError as e:
            logger.error(f"quilt3.admin.sso_config not available: {e}")
            raise AuthenticationError("Admin functionality not available - quilt3.admin modules not accessible")
        except (ValidationError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to set SSO configuration: {e}")
            self._handle_admin_error(e, "set SSO configuration")
            # This line should never be reached due to exception raising above
            raise  # pragma: no cover

    # ========================================================================
    # Transformation Methods
    # ========================================================================

    def _transform_quilt3_user_to_domain(self, quilt3_user) -> User:
        """Transform quilt3 user object to domain User object.

        Args:
            quilt3_user: User object from quilt3.admin.users

        Returns:
            Domain User object
        """
        try:
            # Transform role if present
            role = None
            if hasattr(quilt3_user, 'role') and quilt3_user.role is not None:
                role = self._transform_quilt3_role_to_domain(quilt3_user.role)

            # Transform extra roles if present
            extra_roles = []
            if hasattr(quilt3_user, 'extra_roles') and quilt3_user.extra_roles is not None:
                extra_roles = [self._transform_quilt3_role_to_domain(r) for r in quilt3_user.extra_roles]

            # Use base class datetime normalization methods
            date_joined = self._normalize_datetime(getattr(quilt3_user, 'date_joined', None))
            last_login = self._normalize_datetime(getattr(quilt3_user, 'last_login', None))

            return User(
                name=getattr(quilt3_user, 'name', ''),
                email=getattr(quilt3_user, 'email', ''),
                is_active=getattr(quilt3_user, 'is_active', False),
                is_admin=getattr(quilt3_user, 'is_admin', False),
                is_sso_only=getattr(quilt3_user, 'is_sso_only', False),
                is_service=getattr(quilt3_user, 'is_service', False),
                date_joined=date_joined,
                last_login=last_login,
                role=role,
                extra_roles=extra_roles,
            )
        except Exception as e:
            logger.error(f"Failed to transform quilt3 user to domain object: {e}")
            raise BackendError(f"Failed to transform user data: {str(e)}")

    def _transform_quilt3_role_to_domain(self, quilt3_role) -> Role:
        """Transform quilt3 role object to domain Role object.

        Args:
            quilt3_role: Role object from quilt3.admin.roles

        Returns:
            Domain Role object
        """
        try:
            return Role(
                id=getattr(quilt3_role, 'id', None),
                name=getattr(quilt3_role, 'name', ''),
                arn=getattr(quilt3_role, 'arn', None),
                type=getattr(quilt3_role, 'type', ''),
            )
        except Exception as e:
            logger.error(f"Failed to transform quilt3 role to domain object: {e}")
            raise BackendError(f"Failed to transform role data: {str(e)}")

    def _transform_quilt3_sso_config_to_domain(self, quilt3_sso_config) -> SSOConfig:
        """Transform quilt3 SSO config object to domain SSOConfig object.

        Args:
            quilt3_sso_config: SSO config object from quilt3.admin.sso_config

        Returns:
            Domain SSOConfig object
        """
        try:
            # Transform uploader if present
            uploader = None
            if hasattr(quilt3_sso_config, 'uploader') and quilt3_sso_config.uploader is not None:
                uploader = self._transform_quilt3_user_to_domain(quilt3_sso_config.uploader)

            # Use base class datetime normalization method
            timestamp = self._normalize_datetime(getattr(quilt3_sso_config, 'timestamp', None))

            return SSOConfig(text=getattr(quilt3_sso_config, 'text', ''), timestamp=timestamp, uploader=uploader)
        except Exception as e:
            logger.error(f"Failed to transform quilt3 SSO config to domain object: {e}")
            raise BackendError(f"Failed to transform SSO config data: {str(e)}")

    # ========================================================================
    # Error Handling
    # ========================================================================

    def _handle_admin_error(self, e: Exception, operation: str):
        """Handle admin operation errors with appropriate domain exceptions.

        Maps quilt3.admin exceptions to domain exceptions while preserving
        error context and providing appropriate error messages.

        Args:
            e: The original exception
            operation: Description of the operation that failed

        Raises:
            Appropriate domain exception based on the original exception type
        """
        try:
            # Import exception classes dynamically to handle availability
            import quilt3.admin.exceptions as admin_exceptions

            if isinstance(e, admin_exceptions.UserNotFoundError):
                raise NotFoundError(
                    f"User not found: {str(e)}", {"operation": operation, "error_type": "user_not_found"}
                )
            elif isinstance(e, admin_exceptions.BucketNotFoundError):
                raise NotFoundError(
                    f"Bucket not found: {str(e)}", {"operation": operation, "error_type": "bucket_not_found"}
                )
            elif isinstance(e, admin_exceptions.Quilt3AdminError):
                raise BackendError(
                    f"Admin operation failed: {str(e)}", {"operation": operation, "error_type": "admin_error"}
                )
            elif isinstance(e, PermissionError):
                raise PermissionError(f"Permission denied: {str(e)}", {"operation": operation})
            elif isinstance(e, ValidationError):
                raise ValidationError(f"Validation failed: {str(e)}", {"operation": operation})
            elif isinstance(e, ValueError):
                raise ValidationError(f"Invalid parameter: {str(e)}", {"operation": operation})
            else:
                raise BackendError(
                    f"Failed to {operation}: {str(e)}", {"operation": operation, "error_type": "unknown"}
                )

        except ImportError:
            # If we can't import admin exceptions, treat as generic backend error
            logger.error("Could not import quilt3.admin.exceptions for error handling")
            raise BackendError(f"Failed to {operation}: {str(e)}", {"operation": operation, "error_type": "unknown"})
