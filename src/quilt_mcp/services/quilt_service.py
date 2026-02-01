"""QuiltService - Centralized abstraction for all quilt3 operations.

This service provides a single point of access to all quilt3 functionality,
isolating the 84+ MCP tools from direct quilt3 dependencies.
"""

from __future__ import annotations

from typing import Any, Iterator, Dict, List, Optional
from pathlib import Path

import quilt3

from quilt_mcp.utils import get_dns_name_from_url


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
    # Note: is_authenticated() and get_logged_in_url() migrated to QuiltOps.get_auth_status()
    # Available via auth_metadata service layer

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
            from quilt_mcp.utils import normalize_url

            session = quilt3.session.get_session()
            # Normalize URL - ensure no trailing slash
            normalized_url = normalize_url(catalog_url)
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

    # Note: get_catalog_info() migrated to QuiltOps.get_auth_status() + get_catalog_config()
    # Available via auth_metadata.catalog_info()

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

    # Package Operations Methods
    # Based on usage analysis: 18 calls across packages.py, package_ops.py, etc.
    # Note: browse_package() and list_packages() migrated to QuiltOps
    # Remaining methods support tools not yet migrated

    # Search Operations Methods
    # Based on usage analysis: 1 call in packages.py
    # Note: get_search_api() migrated to direct imports in backends

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
