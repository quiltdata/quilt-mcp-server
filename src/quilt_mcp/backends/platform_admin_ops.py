"""
Platform_Admin_Ops implementation for Platform GraphQL backend.

This module provides the admin operations implementation for the Platform backend
using GraphQL queries and mutations. It implements the AdminOps interface using
Platform's admin GraphQL API.
"""

import logging
from typing import List, Optional, Dict, Any

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
from quilt_mcp.domain.policy import Permission, Policy
from quilt_mcp.domain.sso_config import SSOConfig
from quilt_mcp.backends.protocols.admin import AdminBackendProtocol

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

_INVALID_INPUT_SELECTION = """
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
"""

# Policy.roles is [ManagedRole!]!, a concrete type, so it needs no inline fragment.
_POLICY_SELECTION = """
id
title
arn
managed
permissions {
    bucket {
        name
    }
    level
}
roles {
    id
    name
    arn
}
"""

_POLICY_RESULT_SELECTION = f"""
__typename
... on Policy {{
    {_POLICY_SELECTION}
}}
{_INVALID_INPUT_SELECTION}
"""

_ROLE_MUTATION_ERRORS = {
    "RoleNameExists": "A role with that name already exists",
    "RoleNameReserved": "That role name is reserved",
    "RoleNameInvalid": "That role name is invalid",
    "RoleHasTooManyPoliciesToAttach": "Too many policies to attach to the role",
    "RoleIsManaged": "Role is managed",
    "RoleIsUnmanaged": "Role is unmanaged",
    "RoleNameUsedBySsoConfig": "Role name is used by the SSO configuration",
    "RoleAssigned": "Role is still assigned to users",
    "SsoConfigConflict": "Role conflicts with the SSO configuration",
}


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

    def __init__(self, backend: AdminBackendProtocol):
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

    # ========================================================================
    # Policy Management
    # ========================================================================

    def list_policies(self) -> List[Policy]:
        """List all policies in the registry."""
        try:
            query = (
                """
                query PoliciesList {
                    policies {
                """
                + _POLICY_SELECTION
                + """
                    }
                }
            """
            )

            result = self._backend.execute_graphql_query(query)
            policies_data = result.get("data", {}).get("policies", []) or []
            return [self._transform_graphql_policy(p) for p in policies_data]

        except Exception as e:
            logger.error(f"Failed to list policies: {e}")
            self._handle_graphql_error(e, "list policies")
            return []  # pragma: no cover

    def get_policy(self, id_or_title: str) -> Optional[Policy]:
        """Get a policy by ID or title. Returns None when it does not exist."""
        try:
            if not id_or_title or not id_or_title.strip():
                raise ValidationError("Policy ID or title cannot be empty")

            query = (
                """
                query PolicyGet($id: ID!) {
                    policy(id: $id) {
                """
                + _POLICY_SELECTION
                + """
                    }
                }
            """
            )

            # The registry only looks policies up by ID, and `policy(id: ID!)` may
            # either return null or reject a title outright depending on how strictly
            # it validates the ID scalar. Both mean "not an ID", so a failed lookup
            # falls through to the title scan rather than surfacing as an error —
            # otherwise every title-addressed patch and delete would break.
            policy_data = None
            try:
                result = self._backend.execute_graphql_query(query, variables={"id": id_or_title})
                policy_data = result.get("data", {}).get("policy")
            except Exception as e:
                logger.debug(f"Policy ID lookup failed for {id_or_title!r}, trying title: {e}")

            if policy_data:
                return self._transform_graphql_policy(policy_data)

            return next((p for p in self.list_policies() if p.title == id_or_title), None)

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to get policy {id_or_title}: {e}")
            self._handle_graphql_error(e, f"get policy {id_or_title}")
            raise  # pragma: no cover

    def create_managed_policy(
        self,
        title: str,
        permissions: List[Permission],
        role_ids: Optional[List[str]] = None,
    ) -> Policy:
        """Create a Quilt-managed policy from a set of bucket permissions."""
        try:
            if not title or not title.strip():
                raise ValidationError("Policy title cannot be empty")

            mutation = (
                """
                mutation PolicyCreateManaged($input: ManagedPolicyInput!) {
                    policyCreateManaged(input: $input) {
                """
                + _POLICY_RESULT_SELECTION
                + """
                    }
                }
            """
            )

            policy_input = {
                "title": title,
                "permissions": [self._to_permission_input(p) for p in permissions],
                "roles": role_ids or [],
            }

            result = self._backend.execute_graphql_query(mutation, variables={"input": policy_input})
            payload = result.get("data", {}).get("policyCreateManaged", {})
            return self._unwrap_policy_result(payload, f"create managed policy {title}")

        except (ValidationError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to create managed policy {title}: {e}")
            self._handle_graphql_error(e, f"create managed policy {title}")
            raise  # pragma: no cover

    def create_unmanaged_policy(self, title: str, arn: str, role_ids: Optional[List[str]] = None) -> Policy:
        """Create a policy wrapping an existing IAM policy ARN."""
        try:
            if not title or not title.strip():
                raise ValidationError("Policy title cannot be empty")
            if not arn or not arn.strip():
                raise ValidationError("Policy ARN cannot be empty")

            mutation = (
                """
                mutation PolicyCreateUnmanaged($input: UnmanagedPolicyInput!) {
                    policyCreateUnmanaged(input: $input) {
                """
                + _POLICY_RESULT_SELECTION
                + """
                    }
                }
            """
            )

            policy_input = {"title": title, "arn": arn, "roles": role_ids or []}

            result = self._backend.execute_graphql_query(mutation, variables={"input": policy_input})
            payload = result.get("data", {}).get("policyCreateUnmanaged", {})
            return self._unwrap_policy_result(payload, f"create unmanaged policy {title}")

        except (ValidationError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to create unmanaged policy {title}: {e}")
            self._handle_graphql_error(e, f"create unmanaged policy {title}")
            raise  # pragma: no cover

    def patch_managed_policy(
        self,
        id_or_title: str,
        title: Optional[str] = None,
        permissions: Optional[List[Permission]] = None,
        role_ids: Optional[List[str]] = None,
    ) -> Policy:
        """Partially update a managed policy; unspecified fields keep their values."""
        try:
            current = self._resolve_policy(id_or_title)
            if not current.managed:
                raise ValidationError(f"Cannot patch_managed on an unmanaged policy: {id_or_title}")

            mutation = (
                """
                mutation PolicyUpdateManaged($id: ID!, $input: ManagedPolicyInput!) {
                    policyUpdateManaged(id: $id, input: $input) {
                """
                + _POLICY_RESULT_SELECTION
                + """
                    }
                }
            """
            )

            # policyUpdateManaged replaces the whole policy, so unspecified fields
            # are refilled from the current one.
            policy_input = {
                "title": title if title is not None else current.title,
                "permissions": [
                    self._to_permission_input(p)
                    for p in (permissions if permissions is not None else current.permissions)
                ],
                "roles": role_ids if role_ids is not None else list(current.role_ids),
            }

            result = self._backend.execute_graphql_query(mutation, variables={"id": current.id, "input": policy_input})
            payload = result.get("data", {}).get("policyUpdateManaged", {})
            return self._unwrap_policy_result(payload, f"patch managed policy {id_or_title}")

        except (ValidationError, NotFoundError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to patch managed policy {id_or_title}: {e}")
            self._handle_graphql_error(e, f"patch managed policy {id_or_title}")
            raise  # pragma: no cover

    def patch_unmanaged_policy(
        self,
        id_or_title: str,
        title: Optional[str] = None,
        arn: Optional[str] = None,
        role_ids: Optional[List[str]] = None,
    ) -> Policy:
        """Partially update an unmanaged policy; unspecified fields keep their values."""
        try:
            current = self._resolve_policy(id_or_title)
            if current.managed:
                raise ValidationError(f"Cannot patch_unmanaged on a managed policy: {id_or_title}")

            mutation = (
                """
                mutation PolicyUpdateUnmanaged($id: ID!, $input: UnmanagedPolicyInput!) {
                    policyUpdateUnmanaged(id: $id, input: $input) {
                """
                + _POLICY_RESULT_SELECTION
                + """
                    }
                }
            """
            )

            policy_input = {
                "title": title if title is not None else current.title,
                "arn": arn if arn is not None else current.arn,
                "roles": role_ids if role_ids is not None else list(current.role_ids),
            }

            result = self._backend.execute_graphql_query(mutation, variables={"id": current.id, "input": policy_input})
            payload = result.get("data", {}).get("policyUpdateUnmanaged", {})
            return self._unwrap_policy_result(payload, f"patch unmanaged policy {id_or_title}")

        except (ValidationError, NotFoundError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to patch unmanaged policy {id_or_title}: {e}")
            self._handle_graphql_error(e, f"patch unmanaged policy {id_or_title}")
            raise  # pragma: no cover

    def delete_policy(self, id_or_title: str) -> None:
        """Delete a policy from the registry."""
        try:
            current = self._resolve_policy(id_or_title)

            mutation = (
                """
                mutation PolicyDelete($id: ID!) {
                    policyDelete(id: $id) {
                        __typename
                """
                + _INVALID_INPUT_SELECTION
                + """
                    }
                }
            """
            )

            result = self._backend.execute_graphql_query(mutation, variables={"id": current.id})
            payload = result.get("data", {}).get("policyDelete", {}) or {}

            typename = payload.get("__typename")
            if typename == "Ok":
                return
            error_message = self._extract_result_error(payload)
            if error_message:
                if typename == "OperationError":
                    raise BackendError(f"Failed to delete policy: {error_message}")
                raise ValidationError(f"Failed to delete policy: {error_message}")
            # Anything that is not an explicit Ok must raise. Falling through would
            # report a policy as deleted while it still exists and still grants access.
            raise BackendError(f"Failed to delete policy: unexpected result {typename or 'no __typename'}")

        except (ValidationError, NotFoundError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to delete policy {id_or_title}: {e}")
            self._handle_graphql_error(e, f"delete policy {id_or_title}")
            raise  # pragma: no cover

    # ========================================================================
    # Role Mutations
    # ========================================================================

    def get_role(self, id_or_name: str) -> Optional[Role]:
        """Get a role by ID or name. Returns None when it does not exist."""
        try:
            if not id_or_name or not id_or_name.strip():
                raise ValidationError("Role ID or name cannot be empty")

            query = (
                """
                query RoleGet($id: ID!) {
                    role(id: $id) {
                """
                + _ROLE_SELECTION
                + """
                    }
                }
            """
            )

            result = self._backend.execute_graphql_query(query, variables={"id": id_or_name})
            role_data = result.get("data", {}).get("role")
            if role_data:
                return self._transform_graphql_role(role_data)

            # role(id:) is ID-only, so a name needs the list.
            return next((r for r in self.list_roles() if r.name == id_or_name), None)

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to get role {id_or_name}: {e}")
            self._handle_graphql_error(e, f"get role {id_or_name}")
            raise  # pragma: no cover

    def create_managed_role(self, name: str, policy_ids: Optional[List[str]] = None) -> Role:
        """Create a Quilt-managed role from a set of policy IDs."""
        try:
            if not name or not name.strip():
                raise ValidationError("Role name cannot be empty")

            mutation = (
                """
                mutation RoleCreateManaged($input: ManagedRoleInput!) {
                    roleCreateManaged(input: $input) {
                        __typename
                        ... on RoleCreateSuccess {
                            role {
                """
                + _ROLE_SELECTION
                + """
                            }
                        }
                    }
                }
            """
            )

            role_input = {"name": name, "policies": policy_ids or []}

            result = self._backend.execute_graphql_query(mutation, variables={"input": role_input})
            payload = result.get("data", {}).get("roleCreateManaged", {})
            return self._unwrap_role_result(payload, f"create managed role {name}", "RoleCreateSuccess")

        except (ValidationError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to create managed role {name}: {e}")
            self._handle_graphql_error(e, f"create managed role {name}")
            raise  # pragma: no cover

    def create_unmanaged_role(self, name: str, arn: str) -> Role:
        """Create a role wrapping an existing IAM role ARN."""
        try:
            if not name or not name.strip():
                raise ValidationError("Role name cannot be empty")
            if not arn or not arn.strip():
                raise ValidationError("Role ARN cannot be empty")

            mutation = (
                """
                mutation RoleCreateUnmanaged($input: UnmanagedRoleInput!) {
                    roleCreateUnmanaged(input: $input) {
                        __typename
                        ... on RoleCreateSuccess {
                            role {
                """
                + _ROLE_SELECTION
                + """
                            }
                        }
                    }
                }
            """
            )

            result = self._backend.execute_graphql_query(mutation, variables={"input": {"name": name, "arn": arn}})
            payload = result.get("data", {}).get("roleCreateUnmanaged", {})
            return self._unwrap_role_result(payload, f"create unmanaged role {name}", "RoleCreateSuccess")

        except (ValidationError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to create unmanaged role {name}: {e}")
            self._handle_graphql_error(e, f"create unmanaged role {name}")
            raise  # pragma: no cover

    def delete_role(self, id_or_name: str) -> None:
        """Delete a role from the registry."""
        try:
            current = self._resolve_role(id_or_name)

            mutation = """
                mutation RoleDelete($id: ID!) {
                    roleDelete(id: $id) {
                        __typename
                    }
                }
            """

            result = self._backend.execute_graphql_query(mutation, variables={"id": current.id})
            payload = result.get("data", {}).get("roleDelete", {}) or {}

            typename = payload.get("__typename")
            if typename == "RoleDeleteSuccess":
                return
            if typename == "RoleDoesNotExist":
                raise NotFoundError(f"Role not found: {id_or_name}")
            if typename in _ROLE_MUTATION_ERRORS:
                raise ValidationError(f"Failed to delete role: {_ROLE_MUTATION_ERRORS[typename]}")
            # Anything that is not an explicit success must raise, or a role that still
            # exists and still grants access would be reported as deleted.
            raise BackendError(f"Failed to delete role: unexpected result {typename or 'no __typename'}")

        except (ValidationError, NotFoundError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to delete role {id_or_name}: {e}")
            self._handle_graphql_error(e, f"delete role {id_or_name}")
            raise  # pragma: no cover

    def set_default_role(self, id_or_name: str) -> Role:
        """Set the role assigned to new users by default."""
        try:
            current = self._resolve_role(id_or_name)

            mutation = (
                """
                mutation RoleSetDefault($id: ID!) {
                    roleSetDefault(id: $id) {
                        __typename
                        ... on RoleSetDefaultSuccess {
                            role {
                """
                + _ROLE_SELECTION
                + """
                            }
                        }
                    }
                }
            """
            )

            result = self._backend.execute_graphql_query(mutation, variables={"id": current.id})
            payload = result.get("data", {}).get("roleSetDefault", {})
            return self._unwrap_role_result(payload, f"set default role {id_or_name}", "RoleSetDefaultSuccess")

        except (ValidationError, NotFoundError, BackendError):
            raise
        except Exception as e:
            logger.error(f"Failed to set default role {id_or_name}: {e}")
            self._handle_graphql_error(e, f"set default role {id_or_name}")
            raise  # pragma: no cover

    # ========================================================================
    # Policy / role helpers
    # ========================================================================

    def _resolve_policy(self, id_or_title: str) -> Policy:
        """Resolve a policy by ID or title, raising NotFoundError when absent."""
        policy = self.get_policy(id_or_title)
        if policy is None:
            raise NotFoundError(f"Policy not found: {id_or_title}")
        return policy

    def _resolve_role(self, id_or_name: str) -> Role:
        """Resolve a role by ID or name, raising NotFoundError when absent."""
        role = self.get_role(id_or_name)
        if role is None:
            raise NotFoundError(f"Role not found: {id_or_name}")
        return role

    def _to_permission_input(self, permission: Permission) -> Dict[str, Any]:
        """Convert a domain Permission to a GraphQL PermissionInput."""
        return {"bucket": permission.bucket, "level": permission.level}

    def _unwrap_policy_result(self, payload: Dict[str, Any], operation: str) -> Policy:
        """Turn a PolicyResult union into a domain Policy or the matching exception."""
        if not isinstance(payload, dict) or not payload:
            raise BackendError(f"Failed to {operation}: No policy data returned")

        typename = payload.get("__typename")
        error_message = self._extract_result_error(payload)
        if error_message:
            if typename == "OperationError":
                raise BackendError(f"Failed to {operation}: {error_message}")
            raise ValidationError(f"Failed to {operation}: {error_message}")

        # Require the success typename rather than treating an unknown one as success:
        # a payload missing __typename would otherwise transform into an empty Policy
        # and be reported as a policy that was never created.
        if typename != "Policy":
            raise BackendError(f"Failed to {operation}: unexpected result {typename or 'no __typename'}")

        return self._transform_graphql_policy(payload)

    def _unwrap_role_result(self, payload: Dict[str, Any], operation: str, success_typename: str) -> Role:
        """Turn a role mutation union into a domain Role or the matching exception."""
        if not isinstance(payload, dict) or not payload:
            raise BackendError(f"Failed to {operation}: No role data returned")

        typename = payload.get("__typename")
        if typename == "RoleDoesNotExist":
            raise NotFoundError(f"Failed to {operation}: role does not exist")
        if typename in _ROLE_MUTATION_ERRORS:
            raise ValidationError(f"Failed to {operation}: {_ROLE_MUTATION_ERRORS[typename]}")

        role_data = payload.get("role")
        if not isinstance(role_data, dict):
            raise BackendError(f"Failed to {operation}: No role data returned")
        if typename and typename != success_typename:
            raise BackendError(f"Failed to {operation}: unexpected result {typename}")

        return self._transform_graphql_role(role_data)

    def _transform_graphql_policy(self, policy_data: Dict[str, Any]) -> Policy:
        """Transform a GraphQL Policy selection into the domain Policy object."""
        try:
            # No default for `level`: it is the security-relevant field. A missing or
            # unrecognized level must fail loudly rather than be reported as READ —
            # a silent downgrade would tell an admin a policy is read-only, and would
            # then be written back to the registry by a patch that refills from
            # current values.
            permissions = [
                Permission(
                    bucket=(p.get("bucket") or {}).get("name", ""),
                    level=p["level"],
                )
                for p in policy_data.get("permissions") or []
            ]
            return Policy(
                id=policy_data.get("id"),
                title=policy_data.get("title", ""),
                arn=policy_data.get("arn"),
                managed=bool(policy_data.get("managed", False)),
                permissions=permissions,
                role_ids=[r["id"] for r in policy_data.get("roles") or [] if r.get("id")],
            )
        except Exception as e:
            logger.error(f"Failed to transform GraphQL policy to domain object: {e}")
            raise BackendError(f"Failed to transform policy data: {str(e)}")

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
