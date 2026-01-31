"""QuiltService - Centralized abstraction for all quilt3 operations.

This service provides a single point of access to all quilt3 functionality,
isolating the 84+ MCP tools from direct quilt3 dependencies.
"""

from __future__ import annotations

from typing import Any, Iterator, Dict, List, Optional
from pathlib import Path

import quilt3


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
            return quilt3.logged_in()  # type: ignore[no-any-return]
        except Exception:
            return None

    def get_config(self) -> dict[str, Any] | None:
        """Get current Quilt configuration.

        Returns:
            Configuration dictionary or None if not available
        """
        try:
            return quilt3.config()  # type: ignore[no-any-return]
        except Exception:
            return None

    def get_catalog_config(self, catalog_url: str) -> dict[str, Any] | None:
        """Get catalog configuration from <catalog>/config.json.

        Fetches and filters the catalog configuration to return only essential
        AWS infrastructure keys, plus derives the stack prefix and tabulator catalog name.

        Args:
            catalog_url: URL of the catalog (e.g., 'https://example.quiltdata.com')

        Returns:
            Filtered catalog configuration dict with keys: region, api_gateway_endpoint,
            analytics_bucket, stack_prefix (from analytics_bucket), and tabulator_data_catalog
            (format: 'quilt-<stack-prefix>-tabulator'). Returns None if not available.

        Raises:
            Exception: If session is not available (not authenticated)
        """
        # Check if session support is available before attempting to use it
        if not self.has_session_support():
            raise Exception("quilt3 session not available - user may not be authenticated")

        try:
            # Use requests session to fetch config.json from catalog
            session = self.get_session()
            # Normalize URL - ensure no trailing slash
            normalized_url = catalog_url.rstrip("/")
            config_url = f"{normalized_url}/config.json"

            response = session.get(config_url, timeout=10)
            response.raise_for_status()

            full_config = response.json()

            # Extract only the keys we need (converting to snake_case)
            filtered_config: dict[str, Any] = {}

            if "region" in full_config:
                filtered_config["region"] = full_config["region"]

            if "apiGatewayEndpoint" in full_config:
                filtered_config["api_gateway_endpoint"] = full_config["apiGatewayEndpoint"]

            if "analyticsBucket" in full_config:
                analytics_bucket = full_config["analyticsBucket"]
                filtered_config["analytics_bucket"] = analytics_bucket

                # Derive stack prefix from analytics bucket name
                # Example: "quilt-staging-analyticsbucket-10ort3e91tnoa" -> "quilt-staging"
                if "-analyticsbucket" in analytics_bucket.lower():
                    stack_prefix = analytics_bucket.split("-analyticsbucket")[0]
                    filtered_config["stack_prefix"] = stack_prefix

                    # Derive tabulator data catalog name from stack prefix
                    # Example: "quilt-staging" -> "quilt-quilt-staging-tabulator"
                    filtered_config["tabulator_data_catalog"] = f"quilt-{stack_prefix}-tabulator"

            return filtered_config if filtered_config else None
        except Exception as e:
            # Re-raise with context if it's a session-related error
            if "session" in str(e).lower() or "auth" in str(e).lower():
                raise Exception(f"Failed to fetch catalog config: {e}") from e
            return None

    def set_config(self, catalog_url: str) -> None:
        """Set Quilt catalog configuration.

        Args:
            catalog_url: URL of the catalog to configure
        """
        quilt3.config(catalog_url)

    def get_catalog_info(self) -> dict[str, Any]:
        """Get comprehensive catalog information.

        Returns:
            Dict with the following keys (all keys always present, values may be None):
            - catalog_name: Catalog name or "unknown"
            - navigator_url: Navigator URL if configured
            - registry_url: Registry URL if configured
            - is_authenticated: Boolean authentication status
            - logged_in_url: Login URL if authenticated
            - region: AWS region if catalog config available (does not require authentication)
            - tabulator_data_catalog: Tabulator catalog name if catalog config available (does not require authentication)
        """
        catalog_info: dict[str, Any] = {
            "catalog_name": None,
            "navigator_url": None,
            "registry_url": None,
            "is_authenticated": False,
            "logged_in_url": None,
            "region": None,
            "tabulator_data_catalog": None,
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

        # Fetch catalog config (works with or without authentication)
        try:
            catalog_url = (
                catalog_info.get("logged_in_url")
                or catalog_info.get("navigator_url")
                or catalog_info.get("registry_url")
            )
            if catalog_url:
                catalog_config = self.get_catalog_config(catalog_url)
                if catalog_config:
                    catalog_info["region"] = catalog_config.get("region")
                    catalog_info["tabulator_data_catalog"] = catalog_config.get("tabulator_data_catalog")
        except Exception:
            # Don't fail if catalog config fetch fails
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

    def get_session(self) -> Any:
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
                return quilt3.session.get_registry_url()  # type: ignore[no-any-return]
            return None
        except Exception:
            return None

    def create_botocore_session(self) -> Any:
        """Create authenticated botocore session.

        Returns:
            Botocore session object

        Raises:
            Exception: If session creation fails
        """
        return quilt3.session.create_botocore_session()

    # Package Operations Methods
    # Based on usage analysis: 18 calls across packages.py, package_ops.py, etc.

    def browse_package(self, package_name: str, registry: str, top_hash: str | None = None, **kwargs: Any) -> Any:
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
        return quilt3.list_packages(registry=registry)  # type: ignore[no-any-return]

    # Bucket Operations Methods
    # Based on usage analysis: 4 calls in packages.py and buckets.py

    def create_bucket(self, bucket_uri: str) -> Any:
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
            True if admin functionality is available
        """
        try:
            import quilt3.admin.users
            import quilt3.admin.roles
            import quilt3.admin.sso_config
            import quilt3.admin.tabulator

            return True
        except ImportError:
            return False

    def get_tabulator_admin(self) -> Any:
        """Get tabulator admin module.

        Returns:
            quilt3.admin.tabulator module

        Raises:
            ImportError: If admin modules not available
        """
        import quilt3.admin.tabulator

        return quilt3.admin.tabulator

    def get_users_admin(self) -> Any:
        """Get users admin module.

        Returns:
            quilt3.admin.users module

        Raises:
            ImportError: If admin modules not available
        """
        import quilt3.admin.users

        return quilt3.admin.users

    def get_roles_admin(self) -> Any:
        """Get roles admin module.

        Returns:
            quilt3.admin.roles module

        Raises:
            ImportError: If admin modules not available
        """
        import quilt3.admin.roles

        return quilt3.admin.roles

    def get_sso_config_admin(self) -> Any:
        """Get SSO config admin module.

        Returns:
            quilt3.admin.sso_config module

        Raises:
            ImportError: If admin modules not available
        """
        import quilt3.admin.sso_config

        return quilt3.admin.sso_config

    def get_admin_exceptions(self) -> dict[str, type]:
        """Get admin exception classes.

        Returns:
            Dict mapping exception names to exception classes

        Raises:
            ImportError: If admin modules not available
        """
        import quilt3.admin.exceptions

        return {
            'Quilt3AdminError': quilt3.admin.exceptions.Quilt3AdminError,
            'UserNotFoundError': quilt3.admin.exceptions.UserNotFoundError,
            'BucketNotFoundError': quilt3.admin.exceptions.BucketNotFoundError,
        }

    def get_quilt3_module(self) -> Any:
        """Get the quilt3 module for backward compatibility.

        Returns:
            The quilt3 module
        """
        return quilt3
