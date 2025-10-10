"""Quilt3Backend - Backend implementation using quilt3 SDK.

This module provides a thin wrapper around QuiltService that implements the
QuiltBackend protocol. It delegates all operations to the existing QuiltService,
preserving all functionality while enabling backend abstraction.

The wrapper adds zero business logic - it's purely a delegation layer that
enables protocol-based backend switching.
"""

from typing import Any, Iterator, Dict, List, Optional

from quilt_mcp.services.quilt_service import QuiltService


class Quilt3Backend:
    """Backend implementation using quilt3 SDK.

    This class wraps QuiltService and implements the QuiltBackend protocol through
    structural subtyping. All methods delegate directly to the wrapped service
    instance, maintaining identical behavior and error handling.

    Example:
        >>> backend = Quilt3Backend()
        >>> packages = backend.list_packages(registry="s3://my-bucket")
        >>> info = backend.get_catalog_info()
    """

    def __init__(self) -> None:
        """Initialize Quilt3Backend with a QuiltService instance."""
        self._service = QuiltService()

    # Authentication & Configuration Methods

    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated with Quilt.

        Returns:
            True if authenticated, False otherwise
        """
        return self._service.is_authenticated()

    def get_logged_in_url(self) -> str | None:
        """Get the URL of the catalog the user is logged into.

        Returns:
            Catalog URL if authenticated, None otherwise
        """
        return self._service.get_logged_in_url()

    def get_config(self) -> dict[str, Any] | None:
        """Get current Quilt configuration.

        Returns:
            Configuration dictionary or None if not available
        """
        return self._service.get_config()

    def set_config(self, catalog_url: str) -> None:
        """Set Quilt catalog configuration.

        Args:
            catalog_url: URL of the catalog to configure
        """
        self._service.set_config(catalog_url)

    def get_catalog_info(self) -> dict[str, Any]:
        """Get comprehensive catalog information.

        Returns:
            Dict with catalog_name, navigator_url, registry_url,
            logged_in_url, and is_authenticated
        """
        return self._service.get_catalog_info()

    # Session & GraphQL Methods

    def has_session_support(self) -> bool:
        """Check if session is available and functional.

        Returns:
            True if session support is available
        """
        return self._service.has_session_support()

    def get_session(self) -> Any:
        """Get authenticated requests session.

        Returns:
            Authenticated session object

        Raises:
            Exception: If session is not available
        """
        return self._service.get_session()

    def get_registry_url(self) -> str | None:
        """Get registry URL from session.

        Returns:
            Registry URL or None if not available
        """
        return self._service.get_registry_url()

    def create_botocore_session(self) -> Any:
        """Create authenticated botocore session.

        Returns:
            Botocore session object

        Raises:
            Exception: If session creation fails
        """
        return self._service.create_botocore_session()

    # Package Operations Methods

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

        Args:
            package_name: Name of the package to create
            s3_uris: List of S3 URIs to include in the package
            metadata: Optional metadata dictionary for the package
            registry: Target registry (uses default if None)
            message: Commit message for package creation
            auto_organize: True for smart folder organization,
                          False for simple flattening
            copy: Copy mode for objects - "all", "none", or "same_bucket"

        Returns:
            Dict with package creation results

        Raises:
            ValueError: If input parameters are invalid
            Exception: If package creation or push fails
        """
        return self._service.create_package_revision(
            package_name=package_name,
            s3_uris=s3_uris,
            metadata=metadata,
            registry=registry,
            message=message,
            auto_organize=auto_organize,
            copy=copy,
        )

    def browse_package(self, package_name: str, registry: str, top_hash: str | None = None, **kwargs: Any) -> Any:
        """Browse an existing package.

        Args:
            package_name: Name of the package to browse
            registry: Registry URL
            top_hash: Specific version hash (optional)
            **kwargs: Additional arguments for browse operation

        Returns:
            Package instance
        """
        return self._service.browse_package(package_name=package_name, registry=registry, top_hash=top_hash, **kwargs)

    def list_packages(self, registry: str) -> Iterator[str]:
        """List all packages in a registry.

        Args:
            registry: Registry URL

        Returns:
            Iterator of package names
        """
        return self._service.list_packages(registry=registry)

    # Bucket Operations Methods

    def create_bucket(self, bucket_uri: str) -> Any:
        """Create a Bucket instance for S3 operations.

        Args:
            bucket_uri: S3 URI for the bucket

        Returns:
            Bucket instance
        """
        return self._service.create_bucket(bucket_uri=bucket_uri)

    # Search Operations Methods

    def get_search_api(self) -> Any:
        """Get search API for package searching.

        Returns:
            Search API module
        """
        return self._service.get_search_api()

    # Admin Operations Methods (Conditional)

    def is_admin_available(self) -> bool:
        """Check if admin modules are available.

        Returns:
            True if admin functionality is available
        """
        return self._service.is_admin_available()

    def get_tabulator_admin(self) -> Any:
        """Get tabulator admin module.

        Returns:
            Admin tabulator module

        Raises:
            ImportError: If admin modules not available
        """
        return self._service.get_tabulator_admin()

    def get_users_admin(self) -> Any:
        """Get users admin module.

        Returns:
            Admin users module

        Raises:
            ImportError: If admin modules not available
        """
        return self._service.get_users_admin()

    def get_roles_admin(self) -> Any:
        """Get roles admin module.

        Returns:
            Admin roles module

        Raises:
            ImportError: If admin modules not available
        """
        return self._service.get_roles_admin()

    def get_sso_config_admin(self) -> Any:
        """Get SSO config admin module.

        Returns:
            Admin SSO config module

        Raises:
            ImportError: If admin modules not available
        """
        return self._service.get_sso_config_admin()

    def get_admin_exceptions(self) -> dict[str, type]:
        """Get admin exception classes.

        Returns:
            Dict mapping exception names to exception classes

        Raises:
            ImportError: If admin modules not available
        """
        return self._service.get_admin_exceptions()

    # Backward Compatibility Methods

    def get_quilt3_module(self) -> Any:
        """Get the quilt3 module for backward compatibility.

        Returns:
            The quilt3 module
        """
        return self._service.get_quilt3_module()
