"""QuiltBackend Protocol - Contract for backend implementations.

This module defines the QuiltBackend protocol that all backend implementations
must satisfy. The protocol uses structural subtyping (Protocol) rather than
inheritance, enabling flexible implementations without tight coupling.

The protocol covers:
- Authentication & Configuration (5 methods)
- Session & GraphQL Access (4 methods)
- Package Operations (3 methods)
- Bucket Operations (1 method)
- Search Operations (1 method)
- Admin Operations (6 methods, conditional)
- Backward Compatibility (1 method)

All methods preserve the exact behavior and error handling patterns of the
underlying quilt3 APIs while providing isolation for future backend flexibility.
"""

from typing import Protocol, runtime_checkable, Any, Iterator, Dict, List, Optional


@runtime_checkable
class QuiltBackend(Protocol):
    """Protocol defining the contract for Quilt catalog backend implementations.

    This protocol abstracts over different backend implementations (quilt3 SDK,
    GraphQL) without requiring tools to change. Backend implementations provide
    the same interface regardless of underlying technology.

    All methods are defined as protocol methods without implementation. Concrete
    backends (Quilt3Backend, GraphQLBackend) must implement all methods to satisfy
    the protocol contract.
    """

    # Authentication & Configuration Methods

    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated with Quilt.

        Returns:
            True if authenticated, False otherwise
        """
        ...

    def get_logged_in_url(self) -> str | None:
        """Get the URL of the catalog the user is logged into.

        Returns:
            Catalog URL if authenticated, None otherwise
        """
        ...

    def get_config(self) -> dict[str, Any] | None:
        """Get current Quilt configuration.

        Returns:
            Configuration dictionary or None if not available
        """
        ...

    def set_config(self, catalog_url: str) -> None:
        """Set Quilt catalog configuration.

        Args:
            catalog_url: URL of the catalog to configure
        """
        ...

    def get_catalog_info(self) -> dict[str, Any]:
        """Get comprehensive catalog information.

        Returns:
            Dict with catalog_name, navigator_url, registry_url,
            logged_in_url, and is_authenticated
        """
        ...

    # Session & GraphQL Methods

    def has_session_support(self) -> bool:
        """Check if session is available and functional.

        Returns:
            True if session support is available
        """
        ...

    def get_session(self) -> Any:
        """Get authenticated requests session.

        Returns:
            Authenticated session object

        Raises:
            Exception: If session is not available
        """
        ...

    def get_registry_url(self) -> str | None:
        """Get registry URL from session.

        Returns:
            Registry URL or None if not available
        """
        ...

    def create_botocore_session(self) -> Any:
        """Create authenticated botocore session.

        Returns:
            Botocore session object

        Raises:
            Exception: If session creation fails
        """
        ...

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
        ...

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
        ...

    def list_packages(self, registry: str) -> Iterator[str]:
        """List all packages in a registry.

        Args:
            registry: Registry URL

        Returns:
            Iterator of package names
        """
        ...

    # Bucket Operations Methods

    def create_bucket(self, bucket_uri: str) -> Any:
        """Create a Bucket instance for S3 operations.

        Args:
            bucket_uri: S3 URI for the bucket

        Returns:
            Bucket instance
        """
        ...

    # Search Operations Methods

    def get_search_api(self) -> Any:
        """Get search API for package searching.

        Returns:
            Search API module
        """
        ...

    # Admin Operations Methods (Conditional)

    def is_admin_available(self) -> bool:
        """Check if admin modules are available.

        Returns:
            True if admin functionality is available
        """
        ...

    def get_tabulator_admin(self) -> Any:
        """Get tabulator admin module.

        Returns:
            Admin tabulator module

        Raises:
            ImportError: If admin modules not available
        """
        ...

    def get_users_admin(self) -> Any:
        """Get users admin module.

        Returns:
            Admin users module

        Raises:
            ImportError: If admin modules not available
        """
        ...

    def get_roles_admin(self) -> Any:
        """Get roles admin module.

        Returns:
            Admin roles module

        Raises:
            ImportError: If admin modules not available
        """
        ...

    def get_sso_config_admin(self) -> Any:
        """Get SSO config admin module.

        Returns:
            Admin SSO config module

        Raises:
            ImportError: If admin modules not available
        """
        ...

    def get_admin_exceptions(self) -> dict[str, type]:
        """Get admin exception classes.

        Returns:
            Dict mapping exception names to exception classes

        Raises:
            ImportError: If admin modules not available
        """
        ...

    # Backward Compatibility Methods

    def get_quilt3_module(self) -> Any:
        """Get the quilt3 module for backward compatibility.

        Returns:
            The quilt3 module
        """
        ...
