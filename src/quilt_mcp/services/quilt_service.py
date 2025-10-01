"""QuiltService - Centralized abstraction for all quilt3 operations.

This service provides a single point of access to all quilt3 functionality,
isolating the 84+ MCP tools from direct quilt3 dependencies.
"""

from __future__ import annotations

from typing import Any, Iterator, Dict, List, Optional, TYPE_CHECKING
from pathlib import Path

import quilt3

from .exceptions import (
    AdminNotAvailableError,
    UserNotFoundError,
    UserAlreadyExistsError,
    RoleNotFoundError,
    RoleAlreadyExistsError,
    BucketNotFoundError,
    PackageNotFoundError,
)

if TYPE_CHECKING:
    import boto3
    import requests


class QuiltService:
    """Centralized abstraction for all quilt3 operations.

    This service encapsulates all quilt3 API access patterns identified in the
    usage analysis, providing a unified interface for:

    - Authentication & Configuration
    - Package Operations
    - Session & GraphQL Access
    - AWS Client Access
    - Bucket Operations
    - Search Operations
    - Admin Operations (conditional)

    All methods preserve the exact behavior and error handling patterns
    of the underlying quilt3 APIs while providing isolation for future
    backend flexibility.
    """

    def __init__(self) -> None:
        """Initialize the QuiltService instance."""
        pass

    # Authentication & Configuration Methods
    # Based on usage analysis: 19 calls across auth.py, utils.py, permission_discovery.py

    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated with Quilt.

        Returns:
            True if authenticated, False otherwise
        """
        logged_in_url = self.get_logged_in_url()
        return bool(logged_in_url)

    def get_logged_in_url(self) -> str | None:
        """Get the URL of the catalog the user is logged into.

        Returns:
            Catalog URL if authenticated, None otherwise
        """
        try:
            return quilt3.logged_in()
        except Exception:
            return None

    def get_config(self) -> dict[str, Any] | None:
        """Get current Quilt configuration.

        Returns:
            Configuration dictionary or None if not available
        """
        try:
            return quilt3.config()
        except Exception:
            return None

    def set_config(self, catalog_url: str) -> None:
        """Set Quilt catalog configuration.

        Args:
            catalog_url: URL of the catalog to configure
        """
        quilt3.config(catalog_url)

    def get_navigator_url(self) -> str | None:
        """Get navigator_url from Quilt configuration.

        Returns:
            Navigator URL or None if not available
        """
        config = self.get_config()
        if config:
            return config.get("navigator_url")
        return None

    def get_catalog_info(self) -> dict[str, Any]:
        """Get comprehensive catalog information.

        Returns:
            Dict with catalog_name, navigator_url, registry_url,
            logged_in_url, and is_authenticated
        """
        catalog_info: dict[str, Any] = {
            "catalog_name": None,
            "navigator_url": None,
            "registry_url": None,
            "logged_in_url": None,
            "is_authenticated": False,
        }

        try:
            # Get current authentication status
            logged_in_url = self.get_logged_in_url()
            if logged_in_url:
                catalog_info["logged_in_url"] = logged_in_url
                catalog_info["is_authenticated"] = True
                catalog_info["catalog_name"] = self._extract_catalog_name_from_url(logged_in_url)
        except Exception:
            pass

        try:
            # Get configuration details
            config = self.get_config()
            if config:
                navigator_url = config.get("navigator_url")
                registry_url = config.get("registryUrl")

                catalog_info["navigator_url"] = navigator_url
                catalog_info["registry_url"] = registry_url

                # If we don't have a catalog name from authentication, try config
                if not catalog_info["catalog_name"] and navigator_url:
                    catalog_info["catalog_name"] = self._extract_catalog_name_from_url(navigator_url)
                elif not catalog_info["catalog_name"] and registry_url:
                    catalog_info["catalog_name"] = self._extract_catalog_name_from_url(registry_url)
        except Exception:
            pass

        # Fallback catalog name if nothing found
        if not catalog_info["catalog_name"]:
            catalog_info["catalog_name"] = "unknown"

        return catalog_info

    def _extract_catalog_name_from_url(self, url: str) -> str:
        """Extract a human-readable catalog name from a Quilt catalog URL.

        Args:
            url: The catalog URL (e.g., 'https://nightly.quilttest.com')

        Returns:
            A simplified catalog name (e.g., 'nightly.quilttest.com')
        """
        from urllib.parse import urlparse

        if not url:
            return "unknown"

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or parsed.netloc
            if hostname:
                # Remove common subdomain prefixes that don't add semantic value
                if hostname.startswith("www."):
                    hostname = hostname[4:]
                return hostname
            return url
        except Exception:
            return url

    # Session & GraphQL Methods
    # Based on usage analysis: 12 calls across multiple files

    def has_session_support(self) -> bool:
        """Check if quilt3.session is available and functional.

        Returns:
            True if session support is available
        """
        try:
            return hasattr(quilt3, "session") and hasattr(quilt3.session, "get_session")
        except Exception:
            return False

    def get_session(self) -> requests.Session | None:
        """Get authenticated requests session.

        Returns:
            Authenticated session object

        Raises:
            Exception: If session is not available
        """
        if not self.has_session_support():
            raise Exception("quilt3 session not available")
        return quilt3.session.get_session()

    def get_registry_url(self) -> str | None:
        """Get registry URL from session.

        Returns:
            Registry URL or None if not available
        """
        try:
            if hasattr(quilt3.session, "get_registry_url"):
                return quilt3.session.get_registry_url()
            return None
        except Exception:
            return None

    def create_botocore_session(self) -> boto3.Session:
        """Create authenticated botocore session.

        Returns:
            Botocore session object

        Raises:
            Exception: If session creation fails
        """
        return quilt3.session.create_botocore_session()

    # Package Operations Methods
    # Based on usage analysis: 18 calls across packages.py, package_ops.py, etc.

    def create_package_revision(
        self,
        package_name: str,
        s3_uris: List[str],
        metadata: Optional[Dict] = None,
        registry: Optional[str] = None,
        message: str = "Package created via QuiltService",
        auto_organize: bool = True,
        copy: str = "all",
    ) -> Dict[str, Any]:
        """Create and push package in single operation.

        This method replaces the object-based manipulation pattern and provides
        complete package creation without exposing quilt3.Package objects.

        Args:
            package_name: Name of the package to create
            s3_uris: List of S3 URIs to include in the package
            metadata: Optional metadata dictionary for the package
            registry: Target registry (uses default if None)
            message: Commit message for package creation
            auto_organize: True for smart folder organization (s3_package style),
                          False for simple flattening (package_ops style)
            copy: Copy mode for objects - "all" (copy all), "none" (copy none),
                 or "same_bucket" (copy only objects in same bucket as registry)

        Returns:
            Dict with package creation results, never quilt3.Package objects

        Raises:
            ValueError: If input parameters are invalid
            Exception: If package creation or push fails
        """
        # Validate inputs
        self._validate_package_inputs(package_name, s3_uris)

        # Create empty package instance (internal use only)
        pkg = quilt3.Package()

        # Normalize registry
        normalized_registry = self._normalize_registry(registry) if registry else None

        # Populate package with files based on organization strategy
        self._populate_package_files(pkg, s3_uris, auto_organize)

        # Set metadata if provided
        if metadata:
            pkg.set_meta(metadata)

        # Build selector function based on copy mode
        selector_fn = self._build_selector_fn(copy, normalized_registry) if copy != "all" else None

        # Push package and get hash
        top_hash = self._push_package(pkg, package_name, normalized_registry, message, selector_fn)

        # Return dictionary result - NEVER expose quilt3.Package objects
        return self._build_creation_result(package_name, top_hash, normalized_registry, message)

    def browse_package(
        self, package_name: str, registry: str, top_hash: str | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Browse an existing package.

        Args:
            package_name: Name of the package to browse
            registry: Registry URL
            top_hash: Specific version hash (optional)
            **kwargs: Additional arguments for Package.browse()

        Returns:
            Package instance
        """
        browse_args = {"registry": registry}
        if top_hash:
            browse_args["top_hash"] = top_hash
        browse_args.update(kwargs)

        return quilt3.Package.browse(package_name, **browse_args)

    def list_packages(self, registry: str) -> Iterator[str]:
        """List all packages in a registry.

        Args:
            registry: Registry URL

        Returns:
            Iterator of package names
        """
        return quilt3.list_packages(registry=registry)

    def delete_package(self, name: str, registry: str | None = None) -> None:
        """Delete a package from the registry.

        Args:
            name: Package name in format "namespace/package"
            registry: Registry URL (optional, uses quilt3 default if not provided)

        Raises:
            PackageNotFoundError: If package doesn't exist
        """
        try:
            # Normalize registry if provided
            normalized_registry = self._normalize_registry(registry) if registry else None

            # Call quilt3.delete_package with appropriate arguments
            if normalized_registry:
                quilt3.delete_package(name, registry=normalized_registry)
            else:
                quilt3.delete_package(name)
        except Exception as e:
            # Wrap any exception as PackageNotFoundError
            raise PackageNotFoundError(f"Package '{name}' not found") from e

    # Bucket Operations Methods
    # Based on usage analysis: 4 calls in packages.py and buckets.py

    def create_bucket(self, bucket_uri: str) -> dict[str, Any]:
        """Create a Bucket instance for S3 operations.

        Args:
            bucket_uri: S3 URI for the bucket

        Returns:
            Bucket instance
        """
        return quilt3.Bucket(bucket_uri)

    # Search Operations Methods
    # Based on usage analysis: 1 call in packages.py

    def get_search_api(self) -> Any:
        """Get search API for package searching.

        Returns:
            Search API module
        """
        from quilt3.search_util import search_api

        return search_api

    # Admin Operations Methods (Conditional)
    # Based on usage analysis: 11 calls in tabulator.py and governance.py

    def is_admin_available(self) -> bool:
        """Check if quilt3.admin modules are available.

        Returns:
            True if admin functionality is available, False otherwise
        """
        try:
            import quilt3.admin.users
            import quilt3.admin.roles
            import quilt3.admin.sso_config
            import quilt3.admin.tabulator

            return True
        except ImportError:
            return False

    def _require_admin(self, context: str | None = None) -> None:
        """Ensure admin functionality is available, raise if not.

        Args:
            context: Optional context message to include in error

        Raises:
            AdminNotAvailableError: If admin modules are not available
        """
        if not self.is_admin_available():
            message = "Admin operations not available. quilt3.admin module not installed."
            if context:
                message = f"{message} {context}"
            raise AdminNotAvailableError(message)

    def _get_admin_exceptions(self) -> dict[str, type]:
        """Get admin exception classes from quilt3.admin.

        Returns:
            Dict mapping exception names to exception classes

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        try:
            import quilt3.admin.exceptions

            return {
                'Quilt3AdminError': quilt3.admin.exceptions.Quilt3AdminError,
                'UserNotFoundError': quilt3.admin.exceptions.UserNotFoundError,
                'BucketNotFoundError': quilt3.admin.exceptions.BucketNotFoundError,
            }
        except ImportError as e:
            raise AdminNotAvailableError(f"Admin operations not available. quilt3.admin module not installed: {e}")

    def get_tabulator_admin(self) -> Any:
        """Get tabulator admin module.

        Returns:
            quilt3.admin.tabulator module

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        if not self.is_admin_available():
            raise AdminNotAvailableError("Admin operations not available. quilt3.admin module not installed.")

        import quilt3.admin.tabulator

        return quilt3.admin.tabulator

    def get_users_admin(self) -> Any:
        """Get users admin module.

        Returns:
            quilt3.admin.users module

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        if not self.is_admin_available():
            raise AdminNotAvailableError("Admin operations not available. quilt3.admin module not installed.")

        import quilt3.admin.users

        return quilt3.admin.users

    def get_roles_admin(self) -> Any:
        """Get roles admin module.

        Returns:
            quilt3.admin.roles module

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        if not self.is_admin_available():
            raise AdminNotAvailableError("Admin operations not available. quilt3.admin module not installed.")

        import quilt3.admin.roles

        return quilt3.admin.roles

    def get_sso_config_admin(self) -> Any:
        """Get SSO config admin module.

        Returns:
            quilt3.admin.sso_config module

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        if not self.is_admin_available():
            raise AdminNotAvailableError("Admin operations not available. quilt3.admin module not installed.")

        import quilt3.admin.sso_config

        return quilt3.admin.sso_config

    def get_admin_exceptions(self) -> dict[str, type]:
        """Get admin exception classes.

        DEPRECATED: Use _get_admin_exceptions() for internal use.

        Returns:
            Dict mapping exception names to exception classes

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        return self._get_admin_exceptions()

    def get_quilt3_module(self) -> Any:
        """Get the quilt3 module for backward compatibility.

        Returns:
            The quilt3 module
        """
        return quilt3

    # User Management Methods (Phase 2.1)

    def _get_users_admin_module(self) -> Any:
        """Get the users admin module.

        Returns:
            quilt3.admin.users module

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        self._require_admin(context="User management operations require admin access.")
        import quilt3.admin.users

        return quilt3.admin.users

    def _handle_user_operation_error(self, error: Exception, username: str) -> None:
        """Handle errors from user management operations.

        This helper centralizes the error handling pattern used across
        user management methods that reference a specific username.

        Args:
            error: The exception caught from quilt3.admin.users operation
            username: The username that was being operated on

        Raises:
            UserNotFoundError: If the error is a quilt3 UserNotFoundError
            Exception: Re-raises any other exceptions unchanged
        """
        admin_exceptions = self._get_admin_exceptions()
        quilt3_user_not_found = admin_exceptions.get('UserNotFoundError')

        # Check if this is a UserNotFoundError from quilt3.admin
        if quilt3_user_not_found and isinstance(error, quilt3_user_not_found):
            raise UserNotFoundError(f"User '{username}' not found") from error

        # Re-raise any other exceptions
        raise

    def list_users(self) -> list[dict[str, Any]]:
        """List all users in the catalog.

        Returns:
            List of user dictionaries with user information

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        users_admin = self._get_users_admin_module()
        return users_admin.list()

    def get_user(self, name: str) -> dict[str, Any]:
        """Get detailed information about a specific user.

        Args:
            name: Username to retrieve

        Returns:
            User dictionary with detailed information

        Raises:
            AdminNotAvailableError: If admin modules not available
            UserNotFoundError: If user does not exist
        """
        users_admin = self._get_users_admin_module()

        try:
            return users_admin.get(name)
        except Exception as e:
            self._handle_user_operation_error(e, name)

    def create_user(self, name: str, email: str, role: str, extra_roles: Optional[list[str]]) -> dict[str, Any]:
        """Create a new user in the catalog.

        Args:
            name: Username for the new user
            email: Email address for the new user
            role: Primary role for the user
            extra_roles: Additional roles to assign to the user (optional)

        Returns:
            User dictionary with created user information

        Raises:
            AdminNotAvailableError: If admin modules not available
            UserAlreadyExistsError: If user already exists
        """
        users_admin = self._get_users_admin_module()

        # Get admin exceptions for proper error handling
        admin_exceptions = self._get_admin_exceptions()
        quilt3_admin_error = admin_exceptions.get('Quilt3AdminError')

        try:
            return users_admin.create(
                name=name,
                email=email,
                role=role,
                extra_roles=extra_roles,
            )
        except Exception as e:
            # Check if this is a Quilt3AdminError indicating user already exists
            if quilt3_admin_error and isinstance(e, quilt3_admin_error):
                if "already exists" in str(e):
                    raise UserAlreadyExistsError(f"User '{name}' already exists") from e
            # Re-raise any other exceptions
            raise

    def delete_user(self, name: str) -> None:
        """Delete a user from the catalog.

        Args:
            name: Username to delete

        Raises:
            AdminNotAvailableError: If admin modules not available
            UserNotFoundError: If user does not exist
        """
        users_admin = self._get_users_admin_module()

        try:
            users_admin.delete(name)
        except Exception as e:
            self._handle_user_operation_error(e, name)

    def set_user_email(self, name: str, email: str) -> dict[str, Any]:
        """Update a user's email address.

        Args:
            name: Username to update
            email: New email address

        Returns:
            User dictionary with updated information

        Raises:
            AdminNotAvailableError: If admin modules not available
            UserNotFoundError: If user does not exist
        """
        users_admin = self._get_users_admin_module()

        try:
            return users_admin.set_email(name, email)
        except Exception as e:
            self._handle_user_operation_error(e, name)

    def set_user_role(self, name: str, role: str, extra_roles: Optional[list[str]], append: bool) -> dict[str, Any]:
        """Update a user's role and extra roles.

        Args:
            name: Username to update
            role: Primary role to assign
            extra_roles: Additional roles to assign (optional)
            append: Whether to append extra_roles to existing ones (True) or replace them (False)

        Returns:
            User dictionary with updated information

        Raises:
            AdminNotAvailableError: If admin modules not available
            UserNotFoundError: If user does not exist
        """
        users_admin = self._get_users_admin_module()

        try:
            return users_admin.set_role(name, role, extra_roles, append)
        except Exception as e:
            self._handle_user_operation_error(e, name)

    def set_user_active(self, name: str, active: bool) -> dict[str, Any]:
        """Update a user's active status.

        Args:
            name: Username to update
            active: Whether the user should be active

        Returns:
            User dictionary with updated information

        Raises:
            AdminNotAvailableError: If admin modules not available
            UserNotFoundError: If user does not exist
        """
        users_admin = self._get_users_admin_module()

        try:
            return users_admin.set_active(name, active)
        except Exception as e:
            self._handle_user_operation_error(e, name)

    def set_user_admin(self, name: str, admin: bool) -> dict[str, Any]:
        """Update a user's admin status.

        Args:
            name: Username to update
            admin: Whether the user should have admin privileges

        Returns:
            User dictionary with updated information

        Raises:
            AdminNotAvailableError: If admin modules not available
            UserNotFoundError: If user does not exist
        """
        users_admin = self._get_users_admin_module()

        try:
            return users_admin.set_admin(name, admin)
        except Exception as e:
            self._handle_user_operation_error(e, name)

    def add_user_roles(self, name: str, roles: list[str]) -> dict[str, Any]:
        """Add roles to a user.

        Args:
            name: Username to update
            roles: List of roles to add to the user

        Returns:
            User dictionary with updated information

        Raises:
            AdminNotAvailableError: If admin modules not available
            UserNotFoundError: If user does not exist
        """
        users_admin = self._get_users_admin_module()

        try:
            return users_admin.add_roles(name, roles)
        except Exception as e:
            self._handle_user_operation_error(e, name)

    def remove_user_roles(self, name: str, roles: list[str], fallback: Optional[str]) -> dict[str, Any]:
        """Remove roles from a user.

        Args:
            name: Username to update
            roles: List of roles to remove from the user
            fallback: Fallback role if the primary role is removed (optional)

        Returns:
            User dictionary with updated information

        Raises:
            AdminNotAvailableError: If admin modules not available
            UserNotFoundError: If user does not exist
        """
        users_admin = self._get_users_admin_module()

        try:
            return users_admin.remove_roles(name, roles, fallback)
        except Exception as e:
            self._handle_user_operation_error(e, name)

    def reset_user_password(self, name: str) -> dict[str, Any]:
        """Reset a user's password.

        Args:
            name: Username to reset password for

        Returns:
            Dictionary with password reset status information

        Raises:
            AdminNotAvailableError: If admin modules not available
            UserNotFoundError: If user does not exist
        """
        users_admin = self._get_users_admin_module()

        try:
            return users_admin.reset_password(name)
        except Exception as e:
            self._handle_user_operation_error(e, name)

    # Role Management Methods (Phase 3.1)

    def _get_roles_admin_module(self) -> Any:
        """Get the roles admin module.

        Returns:
            quilt3.admin.roles module

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        self._require_admin(context="Role management operations require admin access.")
        import quilt3.admin.roles

        return quilt3.admin.roles

    def _handle_role_operation_error(self, error: Exception, rolename: str) -> None:
        """Handle errors from role management operations.

        This helper centralizes the error handling pattern used across
        role management methods that reference a specific role name.

        Args:
            error: The exception caught from quilt3.admin.roles operation
            rolename: The role name that was being operated on

        Raises:
            RoleNotFoundError: If the error indicates role not found
            Exception: Re-raises any other exceptions unchanged
        """
        admin_exceptions = self._get_admin_exceptions()
        quilt3_admin_error = admin_exceptions.get('Quilt3AdminError')

        # Check if this is a Quilt3AdminError indicating role not found
        if quilt3_admin_error and isinstance(error, quilt3_admin_error):
            error_msg = str(error).lower()
            if "not found" in error_msg or "does not exist" in error_msg:
                raise RoleNotFoundError(f"Role '{rolename}' not found") from error

        # Re-raise any other exceptions
        raise

    def list_roles(self) -> list[dict[str, Any]]:
        """List all roles in the catalog.

        Returns:
            List of role dictionaries with role information

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        roles_admin = self._get_roles_admin_module()
        return roles_admin.list()

    def get_role(self, name: str) -> dict[str, Any]:
        """Get detailed information about a specific role.

        Args:
            name: Role name to retrieve

        Returns:
            Role dictionary with detailed information

        Raises:
            AdminNotAvailableError: If admin modules not available
            RoleNotFoundError: If role does not exist
        """
        roles_admin = self._get_roles_admin_module()

        try:
            return roles_admin.get(name)
        except Exception as e:
            self._handle_role_operation_error(e, name)

    def create_role(self, name: str, permissions: dict[str, Any]) -> dict[str, Any]:
        """Create a new role in the catalog.

        Args:
            name: Role name for the new role
            permissions: Permissions dictionary for the role

        Returns:
            Role dictionary with created role information

        Raises:
            AdminNotAvailableError: If admin modules not available
            RoleAlreadyExistsError: If role already exists
        """
        roles_admin = self._get_roles_admin_module()

        # Get admin exceptions for proper error handling
        admin_exceptions = self._get_admin_exceptions()
        quilt3_admin_error = admin_exceptions.get('Quilt3AdminError')

        try:
            return roles_admin.create(name, permissions)
        except Exception as e:
            # Check if this is a Quilt3AdminError indicating role already exists
            if quilt3_admin_error and isinstance(e, quilt3_admin_error):
                if "already exists" in str(e):
                    raise RoleAlreadyExistsError(f"Role '{name}' already exists") from e
            # Re-raise any other exceptions
            raise

    def delete_role(self, name: str) -> None:
        """Delete a role from the catalog.

        Args:
            name: Role name to delete

        Raises:
            AdminNotAvailableError: If admin modules not available
            RoleNotFoundError: If role does not exist
        """
        roles_admin = self._get_roles_admin_module()

        try:
            roles_admin.delete(name)
        except Exception as e:
            self._handle_role_operation_error(e, name)

    # SSO Configuration Methods
    # Phase 3.2: SSO configuration operations

    def _get_sso_admin_module(self) -> Any:
        """Get the SSO configuration admin module.

        Returns:
            quilt3.admin.sso_config module

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        self._require_admin(context="SSO configuration operations require admin access.")
        import quilt3.admin.sso_config

        return quilt3.admin.sso_config

    def get_sso_config(self) -> str | None:
        """Get current SSO configuration.

        Returns:
            SSO configuration string if configured, None otherwise

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        sso_admin = self._get_sso_admin_module()
        return sso_admin.get()

    def set_sso_config(self, config: str) -> dict[str, Any]:
        """Set SSO configuration.

        Args:
            config: SSO configuration string (typically YAML format)

        Returns:
            SSO config object (despite type annotation saying dict - matches pattern of user methods)

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        sso_admin = self._get_sso_admin_module()
        # Return the config object directly, matching the pattern used by user management methods
        # Type annotation is incorrect but maintained for API consistency
        return sso_admin.set(config)

    def remove_sso_config(self) -> dict[str, Any]:
        """Remove SSO configuration.

        Returns:
            Result of remove operation (type annotation is dict but may vary)

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        sso_admin = self._get_sso_admin_module()
        # The module's remove() method may call set(None), so just pass through the result
        return sso_admin.set(None)

    # Tabulator Administration Methods
    # Phase 3.3: Tabulator administration operations

    def _get_tabulator_admin_module(self) -> Any:
        """Get the tabulator admin module.

        Returns:
            quilt3.admin.tabulator module

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        self._require_admin(context="Tabulator administration operations require admin access.")
        import quilt3.admin.tabulator

        return quilt3.admin.tabulator

    def _handle_tabulator_operation_error(self, error: Exception, bucket_name: str) -> None:
        """Handle errors from tabulator operations.

        This helper centralizes the error handling pattern used across
        tabulator methods that reference a specific bucket.

        Args:
            error: The exception caught from quilt3.admin.tabulator operation
            bucket_name: The bucket name that was being operated on

        Raises:
            BucketNotFoundError: If the error indicates bucket not found
            Exception: Re-raises any other exceptions unchanged
        """
        admin_exceptions = self._get_admin_exceptions()
        quilt3_bucket_not_found = admin_exceptions.get('BucketNotFoundError')

        # Check if this is a BucketNotFoundError from quilt3.admin
        if quilt3_bucket_not_found and isinstance(error, quilt3_bucket_not_found):
            raise BucketNotFoundError(f"Bucket '{bucket_name}' not found") from error

        # Re-raise any other exceptions
        raise

    def get_tabulator_access(self) -> bool:
        """Get current tabulator access status (open query).

        Returns:
            True if tabulator access is enabled, False otherwise

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        tabulator_admin = self._get_tabulator_admin_module()
        return tabulator_admin.get_open_query()

    def set_tabulator_access(self, enabled: bool) -> dict[str, Any]:
        """Set tabulator access status (open query).

        Args:
            enabled: Whether to enable or disable tabulator access

        Returns:
            Dict with operation status and enabled state

        Raises:
            AdminNotAvailableError: If admin modules not available
        """
        tabulator_admin = self._get_tabulator_admin_module()
        tabulator_admin.set_open_query(enabled)

        return {
            "status": "success",
            "enabled": enabled,
            "message": f"Tabulator access {'enabled' if enabled else 'disabled'}",
        }

    def list_tabulator_tables(self, bucket: str) -> list[dict[str, Any]]:
        """List all tabulator tables in a bucket.

        Args:
            bucket: Bucket name to list tables from

        Returns:
            List of table dictionaries with table information

        Raises:
            AdminNotAvailableError: If admin modules not available
            BucketNotFoundError: If bucket does not exist
        """
        tabulator_admin = self._get_tabulator_admin_module()

        try:
            tables = tabulator_admin.list_tables(bucket)

            # Convert table objects to dictionaries
            result = []
            for table in tables:
                table_dict = {
                    "name": table.name,
                    "config": table.config,
                }
                result.append(table_dict)

            return result
        except Exception as e:
            self._handle_tabulator_operation_error(e, bucket)

    def create_tabulator_table(self, bucket: str, name: str, config: dict[str, Any] | str) -> dict[str, Any]:
        """Create a new tabulator table.

        Args:
            bucket: Bucket name to create table in
            name: Name for the new table
            config: Table configuration (dict or YAML string)

        Returns:
            Dict with table creation status and details

        Raises:
            AdminNotAvailableError: If admin modules not available
            BucketNotFoundError: If bucket does not exist
        """
        tabulator_admin = self._get_tabulator_admin_module()

        # Convert dict config to YAML string if needed
        if isinstance(config, dict):
            import yaml

            config_str = yaml.dump(config)
        else:
            config_str = config

        try:
            tabulator_admin.set_table(bucket_name=bucket, table_name=name, config=config_str)

            return {
                "status": "success",
                "table_name": name,
                "bucket_name": bucket,
                "message": f"Tabulator table '{name}' created successfully",
            }
        except Exception as e:
            self._handle_tabulator_operation_error(e, bucket)

    def delete_tabulator_table(self, bucket: str, name: str) -> None:
        """Delete a tabulator table.

        Args:
            bucket: Bucket name containing the table
            name: Name of the table to delete

        Raises:
            AdminNotAvailableError: If admin modules not available
            BucketNotFoundError: If bucket does not exist
        """
        tabulator_admin = self._get_tabulator_admin_module()

        try:
            # Delete by setting config to None
            tabulator_admin.set_table(bucket_name=bucket, table_name=name, config=None)
        except Exception as e:
            self._handle_tabulator_operation_error(e, bucket)

    def rename_tabulator_table(self, bucket: str, old_name: str, new_name: str) -> dict[str, Any]:
        """Rename a tabulator table.

        Args:
            bucket: Bucket name containing the table
            old_name: Current name of the table
            new_name: New name for the table

        Returns:
            Dict with rename status and details

        Raises:
            AdminNotAvailableError: If admin modules not available
            BucketNotFoundError: If bucket does not exist
        """
        tabulator_admin = self._get_tabulator_admin_module()

        try:
            tabulator_admin.rename_table(bucket_name=bucket, table_name=old_name, new_table_name=new_name)

            return {
                "status": "success",
                "old_name": old_name,
                "new_name": new_name,
                "bucket_name": bucket,
                "message": f"Tabulator table renamed from '{old_name}' to '{new_name}'",
            }
        except Exception as e:
            self._handle_tabulator_operation_error(e, bucket)

    # Helper methods for create_package_revision

    def _validate_package_inputs(self, package_name: str, s3_uris: List[str]) -> None:
        """Validate inputs for package creation.

        Args:
            package_name: Package name to validate
            s3_uris: List of S3 URIs to validate

        Raises:
            ValueError: If inputs are invalid
        """
        if not package_name or not package_name.strip():
            raise ValueError("Package name cannot be empty")

        if not s3_uris:
            raise ValueError("At least one S3 URI must be provided")

        # Validate package name format (basic check)
        if "/" not in package_name:
            raise ValueError("Package name must be in 'namespace/name' format")

    def _populate_package_files(self, pkg: Any, s3_uris: List[str], auto_organize: bool) -> None:
        """Populate package with files using the specified organization strategy.

        Args:
            pkg: Package instance to populate
            s3_uris: List of S3 URIs to add
            auto_organize: Whether to use smart organization or flattening
        """
        if auto_organize:
            self._add_files_with_smart_organization(pkg, s3_uris)
        else:
            self._add_files_with_flattening(pkg, s3_uris)

    def _add_files_with_smart_organization(self, pkg: Any, s3_uris: List[str]) -> None:
        """Add files to package using smart folder organization.

        Args:
            pkg: Package instance to populate
            s3_uris: List of S3 URIs to organize and add
        """
        organized_structure = self._organize_s3_files_smart(s3_uris)

        # Build URI-to-key mapping for efficient lookup
        uri_to_key = {}
        for s3_uri in s3_uris:
            parts = s3_uri.replace("s3://", "").split("/")
            if len(parts) >= 2:
                key = "/".join(parts[1:])
                uri_to_key[key] = s3_uri

        # Add files according to organized structure
        for folder, objects in organized_structure.items():
            for obj in objects:
                source_key = obj["Key"]

                # Determine logical path in package
                if folder:
                    logical_path = f"{folder}/{Path(source_key).name}"
                else:
                    logical_path = Path(source_key).name

                # Find matching S3 URI
                s3_uri = uri_to_key.get(source_key)
                if s3_uri:
                    pkg.set(logical_path, s3_uri)

    def _add_files_with_flattening(self, pkg: Any, s3_uris: List[str]) -> None:
        """Add files to package using simple flattening strategy.

        Args:
            pkg: Package instance to populate
            s3_uris: List of S3 URIs to add with flattened keys
        """
        collected_objects = self._collect_objects_flat(s3_uris)

        for obj in collected_objects:
            pkg.set(obj["logical_key"], obj["s3_uri"])

    def _push_package(
        self,
        pkg: Any,
        package_name: str,
        registry: Optional[str],
        message: str,
        selector_fn: Optional[callable] = None,
    ) -> str:
        """Push package to registry and return top hash.

        Args:
            pkg: Package instance to push
            package_name: Name of the package
            registry: Target registry (optional)
            message: Commit message
            selector_fn: Optional selector function for copy behavior

        Returns:
            Top hash of the pushed package

        Raises:
            Exception: If push fails
        """
        push_args = {"message": message, "force": True}
        if registry:
            push_args["registry"] = registry
        if selector_fn:
            push_args["selector_fn"] = selector_fn

        return pkg.push(package_name, **push_args)

    def _build_creation_result(
        self, package_name: str, top_hash: str, registry: Optional[str], message: str
    ) -> Dict[str, Any]:
        """Build the package creation result dictionary.

        Args:
            package_name: Name of the created package
            top_hash: Hash of the created package
            registry: Registry where package was created
            message: Commit message used

        Returns:
            Dictionary with creation results
        """
        return {
            "status": "success",
            "action": "created",
            "package_name": package_name,
            "top_hash": top_hash,
            "registry": registry or "default",
            "message": message,
        }

    def _normalize_registry(self, registry: Optional[str]) -> Optional[str]:
        """Normalize registry URL format.

        Args:
            registry: Registry URL to normalize

        Returns:
            Normalized registry URL
        """
        if not registry:
            return None

        # Basic normalization - ensure s3:// prefix for S3 registries
        if registry.startswith("s3://"):
            return registry
        elif "/" in registry and not registry.startswith("http"):
            return f"s3://{registry}"
        else:
            return registry

    def _organize_s3_files_smart(self, s3_uris: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Smart organization of S3 files into logical folders.

        This implements the s3_package.py organization strategy.

        Args:
            s3_uris: List of S3 URIs to organize

        Returns:
            Dict mapping folder names to lists of file objects
        """
        organized = {}

        for s3_uri in s3_uris:
            # Extract key from S3 URI
            parts = s3_uri.replace("s3://", "").split("/")
            if len(parts) < 2:
                continue

            bucket = parts[0]
            key = "/".join(parts[1:])

            # Determine folder based on file extension and path
            file_path = Path(key)
            file_ext = file_path.suffix.lower()

            # Simple folder classification based on file extension
            if file_ext in ['.csv', '.tsv', '.json', '.parquet']:
                folder = "data"
            elif file_ext in ['.txt', '.md', '.rst', '.pdf']:
                folder = "docs"
            elif file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg']:
                folder = "images"
            elif file_ext in ['.py', '.r', '.sql', '.sh']:
                folder = "scripts"
            else:
                folder = "misc"

            if folder not in organized:
                organized[folder] = []

            organized[folder].append(
                {
                    "Key": key,
                    "Size": 1000,  # Mock size for testing
                    "LastModified": "2023-01-01T00:00:00Z",
                }
            )

        return organized

    def _collect_objects_flat(self, s3_uris: List[str]) -> List[Dict[str, str]]:
        """Collect S3 objects with simple flattened logical keys.

        This implements the package_ops.py flattening strategy.

        Args:
            s3_uris: List of S3 URIs to collect

        Returns:
            List of objects with s3_uri and logical_key
        """
        collected = []

        for s3_uri in s3_uris:
            # Extract filename from S3 URI for logical key
            parts = s3_uri.replace("s3://", "").split("/")
            if len(parts) >= 2:
                filename = parts[-1]  # Just the filename
                collected.append({"s3_uri": s3_uri, "logical_key": filename})

        return collected

    def _build_selector_fn(self, copy_mode: str, target_registry: Optional[str]):
        """Build a Quilt selector_fn based on desired copy behavior.

        Args:
            copy_mode: Copy mode - "all", "none", or "same_bucket"
            target_registry: Target registry for bucket comparison

        Returns:
            Callable selector function for quilt3.Package.push()
        """
        if not target_registry:
            # Default behavior if no registry
            return lambda _logical_key, _entry: copy_mode == "all"

        # Extract target bucket from registry
        target_bucket = target_registry.replace("s3://", "").split("/", 1)[0]

        def selector_all(_logical_key, _entry):
            return True

        def selector_none(_logical_key, _entry):
            return False

        def selector_same_bucket(_logical_key, entry):
            try:
                physical_key = str(getattr(entry, "physical_key", ""))
            except Exception:
                physical_key = ""
            if not physical_key.startswith("s3://"):
                return False
            try:
                bucket = physical_key.split("/", 3)[2]
            except Exception:
                return False
            return bucket == target_bucket

        if copy_mode == "none":
            return selector_none
        elif copy_mode == "same_bucket":
            return selector_same_bucket
        else:  # "all" or default
            return selector_all
