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
                return quilt3.session.get_registry_url()
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
        return quilt3.list_packages(registry=registry)

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
