"""
Platform_Admin_Ops implementation for Platform GraphQL backend.

This module provides the admin operations implementation for the Platform backend
using GraphQL queries and mutations. It implements the AdminOps interface using
Platform's admin GraphQL API.
"""

import logging
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .platform_backend import Platform_Backend

from quilt_mcp.ops.admin_ops import AdminOps
from quilt_mcp.ops.exceptions import (
    AuthenticationError,
    BackendError,
    ValidationError,
    NotFoundError,
    PermissionError,
)
from quilt_mcp.domain.user import User
from quilt_mcp.domain.role import Role
from quilt_mcp.domain.sso_config import SSOConfig

logger = logging.getLogger(__name__)

_ROLE_SELECTION = """
__typename
... on ManagedRole {
    id
    name
    arn
}
... on UnmanagedRole {
    id
    name
    arn
}
"""

_USER_SELECTION = f"""
name
email
isActive
isAdmin
isSsoOnly
isService
dateJoined
lastLogin
role {{
    {_ROLE_SELECTION}
}}
extraRoles {{
    {_ROLE_SELECTION}
}}
"""

_USER_RESULT_SELECTION = f"""
__typename
... on User {{
    {_USER_SELECTION}
}}
... on InvalidInput {{
    errors {{
        path
        message
        name
        context
    }}
}}
... on OperationError {{
    message
    name
    context
}}
"""


class Platform_Admin_Ops(AdminOps):
    """Admin operations for Platform backend using GraphQL.

    This class implements the AdminOps interface using Platform's GraphQL API.
    It provides domain-driven admin operations while using GraphQL queries
    and mutations to interact with the Platform backend.

    The implementation follows the Platform GraphQL patterns:
    - Uses the parent backend's execute_graphql_query method
    - Transforms GraphQL responses to domain objects
    - Maps GraphQL errors to domain exceptions
    - Provides comprehensive error handling and logging
    """

    def __init__(self, backend: "Platform_Backend"):
        """Initialize Platform admin operations.

        Args:
            backend: Parent Platform_Backend instance
        """
        self._backend = backend

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
            logger.debug("Listing users via Platform GraphQL")

            query = """
                query ListUsers {
                    admin {
                        user {
                            list {
                                """
            query += _USER_SELECTION
            query += """
                            }
                        }
                    }
                }
            """

            result = self._backend.execute_graphql_query(query)
            users_data = result.get("data", {}).get("admin", {}).get("user", {}).get("list", [])

            # Transform GraphQL users to domain objects
            domain_users = [self._transform_graphql_user(user_data) for user_data in users_data]

            logger.debug(f"Successfully listed {len(domain_users)} users")
            return domain_users

        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            self._handle_graphql_error(e, "list users")
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

            query = """
                query GetUser($name: String!) {
                    admin {
                        user {
                            get(name: $name) {
                                """
            query += _USER_SELECTION
            query += """
                            }
                        }
                    }
                }
            """

            result = self._backend.execute_graphql_query(query, variables={"name": name})
            user_data = result.get("data", {}).get("admin", {}).get("user", {}).get("get")

            if not user_data:
                raise NotFoundError(f"User not found: {name}")

            domain_user = self._transform_graphql_user(user_data)

            logger.debug(f"Successfully retrieved user: {name}")
            return domain_user

        except ValidationError:
            raise
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get user {name}: {e}")
            self._handle_graphql_error(e, f"get user {name}")
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

            mutation = """
                mutation CreateUser($input: UserInput!) {
                    admin {
                        user {
                            create(input: $input) {
                                """
            mutation += _USER_RESULT_SELECTION
            mutation += """
                            }
                        }
                    }
                }
            """

            user_input = {
                "name": name,
                "email": email,
                "role": role,
                "extraRoles": extra_roles if extra_roles is not None else [],
            }

            result = self._backend.execute_graphql_query(mutation, variables={"input": user_input})
            create_result = result.get("data", {}).get("admin", {}).get("user", {}).get("create", {})
            user_payload = self._extract_user_payload(create_result)

            error_message = self._extract_result_error(create_result)
            if error_message:
                raise ValidationError(f"Failed to create user: {error_message}")

            if not user_payload:
                raise BackendError("Failed to create user: No user data returned")

            if create_result.get("__typename") and create_result.get("__typename") != "User":
                raise BackendError("Failed to create user: No user data returned")

            domain_user = self._transform_graphql_user(user_payload)

            logger.debug(f"Successfully created user: {name}")
            return domain_user

        except (ValidationError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to create user {name}: {e}")
            self._handle_graphql_error(e, f"create user {name}")
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

            mutation = """
                mutation DeleteUser($name: String!) {
                    admin {
                        user {
                            mutate(name: $name) {
                                delete {
                                    __typename
                                    ... on InvalidInput {
                                        errors {
                                            path
                                            message
                                            name
                                            context
                                        }
                                    }
                                    ... on OperationError {
                                        message
                                        name
                                        context
                                    }
                                }
                            }
                        }
                    }
                }
            """

            result = self._backend.execute_graphql_query(mutation, variables={"name": name})
            delete_result = result.get("data", {}).get("admin", {}).get("user", {}).get("mutate", {}).get("delete", {})

            if not delete_result:
                raise NotFoundError(f"User not found: {name}")
            error_message = self._extract_result_error(delete_result)
            if error_message:
                raise ValidationError(f"Failed to delete user: {error_message}")

            logger.debug(f"Successfully deleted user: {name}")

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(f"Failed to delete user {name}: {e}")
            self._handle_graphql_error(e, f"delete user {name}")

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

            mutation = """
                mutation SetUserEmail($name: String!, $email: String!) {
                    admin {
                        user {
                            mutate(name: $name) {
                                setEmail(email: $email) {
                                    """
            mutation += _USER_RESULT_SELECTION
            mutation += """
                                }
                            }
                        }
                    }
                }
            """

            result = self._backend.execute_graphql_query(mutation, variables={"name": name, "email": email})
            set_email_result = (
                result.get("data", {}).get("admin", {}).get("user", {}).get("mutate", {}).get("setEmail", {})
            )
            user_payload = self._extract_user_payload(set_email_result)

            error_message = self._extract_result_error(set_email_result)
            if error_message:
                if "not found" in error_message.lower():
                    raise NotFoundError(f"User not found: {name}")
                raise ValidationError(f"Failed to set email: {error_message}")

            if not user_payload:
                raise BackendError("Failed to set email: No user data returned")

            if set_email_result.get("__typename") and set_email_result.get("__typename") != "User":
                raise BackendError("Failed to set email: No user data returned")

            domain_user = self._transform_graphql_user(user_payload)

            logger.debug(f"Successfully set email for user: {name}")
            return domain_user

        except (ValidationError, NotFoundError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to set email for user {name}: {e}")
            self._handle_graphql_error(e, f"set email for user {name}")
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

            mutation = """
                mutation SetUserAdmin($name: String!, $admin: Boolean!) {
                    admin {
                        user {
                            mutate(name: $name) {
                                setAdmin(admin: $admin) {
                                    """
            mutation += _USER_RESULT_SELECTION
            mutation += """
                                }
                            }
                        }
                    }
                }
            """

            result = self._backend.execute_graphql_query(mutation, variables={"name": name, "admin": admin})
            set_admin_result = (
                result.get("data", {}).get("admin", {}).get("user", {}).get("mutate", {}).get("setAdmin", {})
            )
            user_payload = self._extract_user_payload(set_admin_result)

            error_message = self._extract_result_error(set_admin_result)
            if error_message:
                if "not found" in error_message.lower():
                    raise NotFoundError(f"User not found: {name}")
                raise ValidationError(f"Failed to set admin status: {error_message}")

            if not user_payload:
                raise BackendError("Failed to set admin status: No user data returned")

            if set_admin_result.get("__typename") and set_admin_result.get("__typename") != "User":
                raise BackendError("Failed to set admin status: No user data returned")

            domain_user = self._transform_graphql_user(user_payload)

            logger.debug(f"Successfully set admin status for user: {name}")
            return domain_user

        except (ValidationError, NotFoundError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to set admin status for user {name}: {e}")
            self._handle_graphql_error(e, f"set admin status for user {name}")
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

            mutation = """
                mutation SetUserActive($name: String!, $active: Boolean!) {
                    admin {
                        user {
                            mutate(name: $name) {
                                setActive(active: $active) {
                                    """
            mutation += _USER_RESULT_SELECTION
            mutation += """
                                }
                            }
                        }
                    }
                }
            """

            result = self._backend.execute_graphql_query(mutation, variables={"name": name, "active": active})
            set_active_result = (
                result.get("data", {}).get("admin", {}).get("user", {}).get("mutate", {}).get("setActive", {})
            )
            user_payload = self._extract_user_payload(set_active_result)

            error_message = self._extract_result_error(set_active_result)
            if error_message:
                if "not found" in error_message.lower():
                    raise NotFoundError(f"User not found: {name}")
                raise ValidationError(f"Failed to set active status: {error_message}")

            if not user_payload:
                raise BackendError("Failed to set active status: No user data returned")

            if set_active_result.get("__typename") and set_active_result.get("__typename") != "User":
                raise BackendError("Failed to set active status: No user data returned")

            domain_user = self._transform_graphql_user(user_payload)

            logger.debug(f"Successfully set active status for user: {name}")
            return domain_user

        except (ValidationError, NotFoundError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to set active status for user {name}: {e}")
            self._handle_graphql_error(e, f"set active status for user {name}")
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

            mutation = """
                mutation ResetUserPassword($name: String!) {
                    admin {
                        user {
                            mutate(name: $name) {
                                resetPassword {
                                    __typename
                                    ... on InvalidInput {
                                        errors {
                                            path
                                            message
                                            name
                                            context
                                        }
                                    }
                                    ... on OperationError {
                                        message
                                        name
                                        context
                                    }
                                }
                            }
                        }
                    }
                }
            """

            result = self._backend.execute_graphql_query(mutation, variables={"name": name})
            reset_result = (
                result.get("data", {}).get("admin", {}).get("user", {}).get("mutate", {}).get("resetPassword", {})
            )

            if not reset_result:
                raise NotFoundError(f"User not found: {name}")
            error_message = self._extract_result_error(reset_result)
            if error_message:
                raise ValidationError(f"Failed to reset password: {error_message}")

            logger.debug(f"Successfully reset password for user: {name}")

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            logger.error(f"Failed to reset password for user {name}: {e}")
            self._handle_graphql_error(e, f"reset password for user {name}")

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

            mutation = """
                mutation SetUserRole($name: String!, $role: String!, $extraRoles: [String!], $append: Boolean!) {
                    admin {
                        user {
                            mutate(name: $name) {
                                setRole(role: $role, extraRoles: $extraRoles, append: $append) {
                                    """
            mutation += _USER_RESULT_SELECTION
            mutation += """
                                }
                            }
                        }
                    }
                }
            """

            variables = {
                "name": name,
                "role": role,
                "extraRoles": extra_roles if extra_roles is not None else [],
                "append": append,
            }

            result = self._backend.execute_graphql_query(mutation, variables=variables)
            set_role_result = (
                result.get("data", {}).get("admin", {}).get("user", {}).get("mutate", {}).get("setRole", {})
            )
            user_payload = self._extract_user_payload(set_role_result)

            error_message = self._extract_result_error(set_role_result)
            if error_message:
                if "not found" in error_message.lower():
                    raise NotFoundError(f"User or role not found: {error_message}")
                raise ValidationError(f"Failed to set role: {error_message}")

            if not user_payload:
                raise BackendError("Failed to set role: No user data returned")

            if set_role_result.get("__typename") and set_role_result.get("__typename") != "User":
                raise BackendError("Failed to set role: No user data returned")

            domain_user = self._transform_graphql_user(user_payload)

            logger.debug(f"Successfully set role for user: {name}")
            return domain_user

        except (ValidationError, NotFoundError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to set role for user {name}: {e}")
            self._handle_graphql_error(e, f"set role for user {name}")
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

            mutation = """
                mutation AddUserRoles($name: String!, $roles: [String!]!) {
                    admin {
                        user {
                            mutate(name: $name) {
                                addRoles(roles: $roles) {
                                    """
            mutation += _USER_RESULT_SELECTION
            mutation += """
                                }
                            }
                        }
                    }
                }
            """

            result = self._backend.execute_graphql_query(mutation, variables={"name": name, "roles": roles})
            add_roles_result = (
                result.get("data", {}).get("admin", {}).get("user", {}).get("mutate", {}).get("addRoles", {})
            )
            user_payload = self._extract_user_payload(add_roles_result)

            error_message = self._extract_result_error(add_roles_result)
            if error_message:
                if "not found" in error_message.lower():
                    raise NotFoundError(f"User or role not found: {error_message}")
                raise ValidationError(f"Failed to add roles: {error_message}")

            if not user_payload:
                raise BackendError("Failed to add roles: No user data returned")

            if add_roles_result.get("__typename") and add_roles_result.get("__typename") != "User":
                raise BackendError("Failed to add roles: No user data returned")

            domain_user = self._transform_graphql_user(user_payload)

            logger.debug(f"Successfully added roles to user: {name}")
            return domain_user

        except (ValidationError, NotFoundError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to add roles to user {name}: {e}")
            self._handle_graphql_error(e, f"add roles to user {name}")
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

            mutation = """
                mutation RemoveUserRoles($name: String!, $roles: [String!]!, $fallback: String) {
                    admin {
                        user {
                            mutate(name: $name) {
                                removeRoles(roles: $roles, fallback: $fallback) {
                                    """
            mutation += _USER_RESULT_SELECTION
            mutation += """
                                }
                            }
                        }
                    }
                }
            """

            variables = {"name": name, "roles": roles}
            if fallback is not None:
                variables["fallback"] = fallback

            result = self._backend.execute_graphql_query(mutation, variables=variables)
            remove_roles_result = (
                result.get("data", {}).get("admin", {}).get("user", {}).get("mutate", {}).get("removeRoles", {})
            )
            user_payload = self._extract_user_payload(remove_roles_result)

            error_message = self._extract_result_error(remove_roles_result)
            if error_message:
                if "not found" in error_message.lower():
                    raise NotFoundError(f"User or role not found: {error_message}")
                raise ValidationError(f"Failed to remove roles: {error_message}")

            if not user_payload:
                raise BackendError("Failed to remove roles: No user data returned")

            if remove_roles_result.get("__typename") and remove_roles_result.get("__typename") != "User":
                raise BackendError("Failed to remove roles: No user data returned")

            domain_user = self._transform_graphql_user(user_payload)

            logger.debug(f"Successfully removed roles from user: {name}")
            return domain_user

        except (ValidationError, NotFoundError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to remove roles from user {name}: {e}")
            self._handle_graphql_error(e, f"remove roles from user {name}")
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
            logger.debug("Listing roles via Platform GraphQL")

            query = """
                query ListRoles {
                    roles {
                        """
            query += _ROLE_SELECTION
            query += """
                    }
                }
            """

            result = self._backend.execute_graphql_query(query)
            roles_data = result.get("data", {}).get("roles", [])

            # Transform GraphQL roles to domain objects
            domain_roles = [self._transform_graphql_role(role_data) for role_data in roles_data]

            logger.debug(f"Successfully listed {len(domain_roles)} roles")
            return domain_roles

        except Exception as e:
            logger.error(f"Failed to list roles: {e}")
            self._handle_graphql_error(e, "list roles")
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
            logger.debug("Getting SSO configuration via Platform GraphQL")

            query = """
                query GetSSOConfig {
                    admin {
                        ssoConfig {
                            text
                            timestamp
                            uploader {
                                name
                                email
                            }
                        }
                    }
                }
            """

            result = self._backend.execute_graphql_query(query)
            sso_config_data = result.get("data", {}).get("admin", {}).get("ssoConfig")

            if not sso_config_data:
                logger.debug("No SSO configuration found")
                return None

            domain_sso_config = self._transform_graphql_sso_config(sso_config_data)

            logger.debug("Successfully retrieved SSO configuration")
            return domain_sso_config

        except Exception as e:
            logger.error(f"Failed to get SSO configuration: {e}")
            self._handle_graphql_error(e, "get SSO configuration")
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
            # Serialize config to JSON string (backend expects string)
            config_str: Optional[str] = None
            if config is not None:
                if isinstance(config, str):
                    if not config.strip():
                        raise ValidationError("SSO configuration cannot be empty")
                    config_str = config
                elif not config:
                    raise ValidationError("SSO configuration cannot be empty")
                else:
                    config_str = json.dumps(config)

            logger.debug("Setting SSO configuration via Platform GraphQL")

            mutation = """
                mutation SetSSOConfig($config: String) {
                    admin {
                        setSsoConfig(config: $config) {
                            __typename
                            ... on SsoConfig {
                                text
                                timestamp
                                uploader {
                                    name
                                    email
                                }
                            }
                            ... on InvalidInput {
                                errors {
                                    path
                                    message
                                    name
                                    context
                                }
                            }
                            ... on OperationError {
                                message
                                name
                                context
                            }
                        }
                    }
                }
            """

            result = self._backend.execute_graphql_query(mutation, variables={"config": config_str})
            set_sso_result = result.get("data", {}).get("admin", {}).get("setSsoConfig", {})
            sso_payload = self._extract_sso_payload(set_sso_result)

            if config is None:
                if set_sso_result is None:
                    logger.debug("Successfully removed SSO configuration")
                    return None
                error_message = self._extract_result_error(set_sso_result)
                if error_message:
                    raise ValidationError(f"Failed to set SSO config: {error_message}")
                logger.debug("Successfully removed SSO configuration")
                return None

            error_message = self._extract_result_error(set_sso_result)
            if error_message:
                raise ValidationError(f"Failed to set SSO config: {error_message}")

            if not sso_payload:
                raise BackendError("Failed to set SSO config: No config data returned")

            if set_sso_result.get("__typename") and set_sso_result.get("__typename") != "SsoConfig":
                raise BackendError("Failed to set SSO config: No config data returned")

            domain_sso_config = self._transform_graphql_sso_config(sso_payload)

            logger.debug("Successfully set SSO configuration")
            return domain_sso_config

        except (ValidationError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to set SSO configuration: {e}")
            self._handle_graphql_error(e, "set SSO configuration")
            raise  # pragma: no cover

    # ========================================================================
    # Transformation Methods
    # ========================================================================

    def _transform_graphql_user(self, user_data: Dict[str, Any]) -> User:
        """Transform GraphQL user response to domain User object.

        Args:
            user_data: User data from GraphQL response

        Returns:
            Domain User object
        """
        try:
            # Transform role if present
            role = None
            role_data = user_data.get("role")
            if role_data:
                role = self._transform_graphql_role(role_data)

            # Transform extra roles if present
            extra_roles = []
            extra_roles_data = user_data.get("extraRoles", [])
            if extra_roles_data:
                extra_roles = [self._transform_graphql_role(r) for r in extra_roles_data]

            return User(
                name=user_data.get("name", ""),
                email=user_data.get("email", ""),
                is_active=user_data.get("isActive", False),
                is_admin=user_data.get("isAdmin", False),
                is_sso_only=user_data.get("isSsoOnly", False),
                is_service=user_data.get("isService", False),
                date_joined=user_data.get("dateJoined"),
                last_login=user_data.get("lastLogin"),
                role=role,
                extra_roles=extra_roles,
            )
        except Exception as e:
            logger.error(f"Failed to transform GraphQL user to domain object: {e}")
            raise BackendError(f"Failed to transform user data: {str(e)}")

    def _transform_graphql_role(self, role_data: Dict[str, Any]) -> Role:
        """Transform GraphQL role response to domain Role object.

        Args:
            role_data: Role data from GraphQL response

        Returns:
            Domain Role object
        """
        try:
            role_type = role_data.get("type")
            if not role_type:
                role_type = role_data.get("__typename", "")
            return Role(
                id=role_data.get("id"),
                name=role_data.get("name", ""),
                arn=role_data.get("arn"),
                type=role_type,
            )
        except Exception as e:
            logger.error(f"Failed to transform GraphQL role to domain object: {e}")
            raise BackendError(f"Failed to transform role data: {str(e)}")

    def _extract_result_error(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract a user-friendly error message from GraphQL union result."""
        if not isinstance(result, dict):
            return "Invalid GraphQL response"

        typename = result.get("__typename")
        if typename == "OperationError":
            return result.get("message") or "Operation failed"
        if typename == "InvalidInput":
            errors = result.get("errors") or []
            messages: list[str] = [
                str(err.get("message")) for err in errors if isinstance(err, dict) and err.get("message")
            ]
            return "; ".join(messages) if messages else "Invalid input"

        # Backward compatibility for older response wrappers.
        message = result.get("message")
        if isinstance(message, str):
            lowered = message.lower()
            if any(
                marker in lowered
                for marker in (
                    "error",
                    "failed",
                    "invalid",
                    "not found",
                    "already exists",
                    "denied",
                    "unauthorized",
                )
            ):
                return message
        return None

    def _extract_user_payload(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return a User payload from either direct or wrapped GraphQL result shapes."""
        if not isinstance(result, dict):
            return None
        user = result.get("user")
        if isinstance(user, dict):
            return user
        if result.get("name"):
            return result
        return None

    def _extract_sso_payload(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return an SSO payload from either direct or wrapped GraphQL result shapes."""
        if not isinstance(result, dict):
            return None
        sso_config = result.get("ssoConfig")
        if isinstance(sso_config, dict):
            return sso_config
        if result.get("text"):
            return result
        return None

    def _transform_graphql_sso_config(self, sso_config_data: Dict[str, Any]) -> SSOConfig:
        """Transform GraphQL SSO config response to domain SSOConfig object.

        Args:
            sso_config_data: SSO config data from GraphQL response

        Returns:
            Domain SSOConfig object
        """
        try:
            # Transform uploader if present
            uploader = None
            uploader_data = sso_config_data.get("uploader")
            if uploader_data:
                uploader = self._transform_graphql_user(uploader_data)

            return SSOConfig(
                text=sso_config_data.get("text", ""),
                timestamp=sso_config_data.get("timestamp"),
                uploader=uploader,
            )
        except Exception as e:
            logger.error(f"Failed to transform GraphQL SSO config to domain object: {e}")
            raise BackendError(f"Failed to transform SSO config data: {str(e)}")

    # ========================================================================
    # Error Handling
    # ========================================================================

    def _handle_graphql_error(self, e: Exception, operation: str):
        """Handle GraphQL errors with appropriate domain exceptions.

        Maps GraphQL errors to domain exceptions while preserving error context
        and providing appropriate error messages.

        Args:
            e: The original exception
            operation: Description of the operation that failed

        Raises:
            Appropriate domain exception based on the original exception type
        """
        error_message = str(e)

        # Check for specific error patterns in the message
        if "authentication" in error_message.lower() or "unauthorized" in error_message.lower():
            raise AuthenticationError(
                f"Authentication failed: {error_message}", {"operation": operation, "error_type": "auth_error"}
            )
        elif "permission" in error_message.lower() or "forbidden" in error_message.lower():
            raise PermissionError(
                f"Permission denied: {error_message}", {"operation": operation, "error_type": "permission_error"}
            )
        elif "not found" in error_message.lower():
            raise NotFoundError(
                f"Resource not found: {error_message}", {"operation": operation, "error_type": "not_found"}
            )
        elif "validation" in error_message.lower() or "invalid" in error_message.lower():
            raise ValidationError(
                f"Validation failed: {error_message}", {"operation": operation, "error_type": "validation_error"}
            )
        else:
            raise BackendError(
                f"Failed to {operation}: {error_message}", {"operation": operation, "error_type": "unknown"}
            )
