"""AdminOps abstract interface for domain-driven admin operations.

This module defines the abstract base class that provides a backend-agnostic interface
for Quilt admin operations. Implementations can use either quilt3 library or Platform GraphQL
while maintaining consistent domain-driven operations for MCP tools.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from ..domain.user import User
from ..domain.role import Role
from ..domain.sso_config import SSOConfig


class AdminOps(ABC):
    """Abstract interface for admin operations.

    This abstract base class defines the interface for backend-agnostic Quilt admin operations.
    It provides domain-driven methods that work with Quilt admin concepts rather than
    backend-specific types, enabling MCP tools to remain functional regardless of
    the underlying backend implementation (quilt3 library or Platform GraphQL).

    All methods return domain objects (User, Role, SSOConfig) that abstract away
    backend implementation details while providing consistent access to Quilt
    admin functionality.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        """Provide Pydantic core schema for AdminOps abstract class.

        This allows Pydantic to handle AdminOps types in function signatures
        without failing schema generation. Since AdminOps is abstract and used
        as a property type, we provide a simple schema that allows any value.
        """
        return core_schema.union_schema(
            [
                core_schema.none_schema(),
                core_schema.any_schema(),
            ]
        )

    @abstractmethod
    def list_users(self) -> List[User]:
        """List all users in the registry.

        Retrieves a list of all users registered in the Quilt registry.
        This provides access to user management functionality across different backends.

        Returns:
            List of User objects representing all registered users

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails (network, API errors, etc.)
            PermissionError: When user lacks admin privileges to list users
        """
        pass

    @abstractmethod
    def get_user(self, name: str) -> User:
        """Get detailed information about a specific user.

        Retrieves comprehensive information for the specified user from the registry.
        This includes user status, roles, and metadata.

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
        pass

    @abstractmethod
    def create_user(self, name: str, email: str, role: str, extra_roles: Optional[List[str]] = None) -> User:
        """Create a new user in the registry.

        Creates a new user account with the specified name, email, and role assignments.
        The user will be created with default settings that can be modified later.

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
            ConflictError: When a user with the same name already exists
        """
        pass

    @abstractmethod
    def delete_user(self, name: str) -> None:
        """Delete a user from the registry.

        Removes the specified user account from the registry. This operation
        is typically irreversible and should be used with caution.

        Args:
            name: Username of the user to delete

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When name parameter is invalid
            NotFoundError: When the specified user doesn't exist
            PermissionError: When user lacks admin privileges to delete users
        """
        pass

    @abstractmethod
    def set_user_email(self, name: str, email: str) -> User:
        """Update a user's email address.

        Changes the email address for the specified user account.

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
        pass

    @abstractmethod
    def set_user_admin(self, name: str, admin: bool) -> User:
        """Set the admin status for a user.

        Grants or revokes administrative privileges for the specified user.

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
        pass

    @abstractmethod
    def set_user_active(self, name: str, active: bool) -> User:
        """Set the active status for a user.

        Activates or deactivates the specified user account.

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
        pass

    @abstractmethod
    def reset_user_password(self, name: str) -> None:
        """Reset a user's password.

        Initiates a password reset for the specified user. The exact behavior
        depends on the backend implementation (email notification, temporary password, etc.).

        Args:
            name: Username of the user whose password should be reset

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When name parameter is invalid
            NotFoundError: When the specified user doesn't exist
            PermissionError: When user lacks admin privileges to reset passwords
        """
        pass

    @abstractmethod
    def set_user_role(
        self, name: str, role: str, extra_roles: Optional[List[str]] = None, append: bool = False
    ) -> User:
        """Set the primary and extra roles for a user.

        Updates the role assignments for the specified user. Can either replace
        all roles or append to existing roles based on the append parameter.

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
        pass

    @abstractmethod
    def add_user_roles(self, name: str, roles: List[str]) -> User:
        """Add roles to a user.

        Adds the specified roles to the user's existing role assignments.

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
        pass

    @abstractmethod
    def remove_user_roles(self, name: str, roles: List[str], fallback: Optional[str] = None) -> User:
        """Remove roles from a user.

        Removes the specified roles from the user's role assignments. If a fallback
        role is provided, it will be assigned if all roles are removed.

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
        pass

    @abstractmethod
    def list_roles(self) -> List[Role]:
        """List all available roles in the registry.

        Retrieves a list of all roles that can be assigned to users in the registry.

        Returns:
            List of Role objects representing all available roles

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails (network, API errors, etc.)
            PermissionError: When user lacks admin privileges to list roles
        """
        pass

    @abstractmethod
    def get_sso_config(self) -> Optional[SSOConfig]:
        """Get the current SSO configuration.

        Retrieves the current SSO configuration from the registry, if one exists.

        Returns:
            SSOConfig object with current configuration, or None if no config exists

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails (network, API errors, etc.)
            PermissionError: When user lacks admin privileges to view SSO configuration
        """
        pass

    @abstractmethod
    def set_sso_config(self, config: str) -> SSOConfig:
        """Set the SSO configuration.

        Updates the SSO configuration in the registry with the provided configuration text.

        Args:
            config: SSO configuration text to set

        Returns:
            SSOConfig object representing the updated configuration

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            ValidationError: When config parameter is invalid
            PermissionError: When user lacks admin privileges to modify SSO configuration
        """
        pass

    @abstractmethod
    def remove_sso_config(self) -> None:
        """Remove the SSO configuration.

        Removes the current SSO configuration from the registry.

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails
            PermissionError: When user lacks admin privileges to modify SSO configuration
        """
        pass
