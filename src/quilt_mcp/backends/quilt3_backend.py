"""
Quilt3_Backend implementation.

This module provides the concrete implementation of QuiltOps using the quilt3 library.
All quilt3 operations are wrapped with proper error handling and transformation to domain objects.

The implementation is organized into modular components:
- quilt3_backend_base: Core initialization and shared utilities
- quilt3_backend_packages: Package operations
- quilt3_backend_content: Content operations
- quilt3_backend_buckets: Bucket operations
- quilt3_backend_session: Session, config, and AWS operations
"""

import logging
from typing import List, Dict, Any, Optional

from quilt_mcp.ops.quilt_ops import QuiltOps
from quilt_mcp.ops.exceptions import NotFoundError
from quilt_mcp.domain.package_info import Package_Info
from quilt_mcp.domain.content_info import Content_Info
from quilt_mcp.domain.bucket_info import Bucket_Info
from quilt_mcp.backends.quilt3_backend_base import Quilt3_Backend_Base, quilt3, requests, boto3
from quilt_mcp.backends.quilt3_backend_packages import Quilt3_Backend_Packages
from quilt_mcp.backends.quilt3_backend_content import Quilt3_Backend_Content
from quilt_mcp.backends.quilt3_backend_buckets import Quilt3_Backend_Buckets
from quilt_mcp.backends.quilt3_backend_session import Quilt3_Backend_Session
from quilt_mcp.backends.quilt3_backend_admin import Quilt3_Backend_Admin
from quilt_mcp.ops.tabulator_mixin import TabulatorMixin

logger = logging.getLogger(__name__)


class Quilt3_Backend(
    Quilt3_Backend_Session,
    TabulatorMixin,
    Quilt3_Backend_Buckets,
    Quilt3_Backend_Content,
    Quilt3_Backend_Packages,
    Quilt3_Backend_Admin,
    Quilt3_Backend_Base,
    QuiltOps,
):
    """Backend implementation using quilt3 library.

    This class composes multiple mixins to provide the complete QuiltOps interface:
    - Session: Auth status, catalog config, GraphQL endpoint/auth, and boto3 access
    - TabulatorMixin: Tabulator table management (backend-agnostic GraphQL operations)
    - Base: Core initialization and shared utilities
    - Packages: Package search, retrieval, and transformations
    - Content: Content browsing and URL generation
    - Buckets: Bucket listing and transformations
    - Admin: User management, role management, and SSO configuration

    Architecture:
    - TabulatorMixin provides generic execute_graphql_query() implementation
    - Quilt3_Backend_Session provides quilt3-specific auth (get_graphql_auth_headers, get_graphql_endpoint)
    - This design allows TabulatorMixin to work with any backend (quilt3, HTTP headers, etc.)
    """

    @property
    def admin(self):
        """Access to admin operations.

        Provides access to administrative operations including user management,
        role management, and SSO configuration through the AdminOps interface.

        Returns:
            AdminOps interface (self, since this class inherits from Quilt3_Backend_Admin)

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When admin functionality is not available or fails to initialize
            PermissionError: When user lacks admin privileges
        """
        return self

    # =========================================================================
    # Backend Primitives (Template Method Pattern)
    # =========================================================================
    # These methods implement the abstract backend primitives defined in QuiltOps.
    # They wrap quilt3 library calls without adding validation or transformation logic.

    def _backend_create_empty_package(self) -> Any:
        """Create a new empty quilt3 package (backend primitive).

        Returns:
            quilt3.Package object
        """
        return self.quilt3.Package()

    def _backend_add_file_to_package(self, package: Any, logical_key: str, s3_uri: str) -> None:
        """Add a file reference to quilt3 package (backend primitive).

        Args:
            package: quilt3.Package object
            logical_key: Logical path within package
            s3_uri: S3 URI of file to add
        """
        package.set(logical_key, s3_uri)

    def _backend_set_package_metadata(self, package: Any, metadata: Dict[str, Any]) -> None:
        """Set metadata on quilt3 package (backend primitive).

        Args:
            package: quilt3.Package object
            metadata: Metadata dictionary
        """
        package.set_meta(metadata)

    def _backend_push_package(self, package: Any, package_name: str, registry: str, message: str, copy: bool) -> str:
        """Push quilt3 package to registry (backend primitive).

        Args:
            package: quilt3.Package object
            package_name: Full package name
            registry: Registry S3 URL
            message: Commit message
            copy: If True, copy objects. If False, create shallow references.

        Returns:
            Top hash of pushed package (empty string if push fails)
        """
        if copy:
            # Deep copy objects to registry bucket
            top_hash = package.push(package_name, registry=registry, message=message)
        else:
            # Shallow references only (no copy)
            top_hash = package.push(
                package_name, registry=registry, message=message, selector_fn=lambda logical_key, entry: False
            )

        return top_hash or ""

    def _backend_get_package(self, package_name: str, registry: str, top_hash: Optional[str] = None) -> Any:
        """Retrieve quilt3 package from registry (backend primitive).

        Args:
            package_name: Full package name
            registry: Registry S3 URL
            top_hash: Optional specific version hash

        Returns:
            quilt3.Package object

        Raises:
            Exception: If package not found (will be wrapped by base class)
        """
        if top_hash:
            return self.quilt3.Package.browse(package_name, registry=registry, top_hash=top_hash)
        else:
            return self.quilt3.Package.browse(package_name, registry=registry)

    def _backend_get_package_entries(self, package: Any) -> Dict[str, Dict[str, Any]]:
        """Get all entries from quilt3 package (backend primitive).

        Args:
            package: quilt3.Package object

        Returns:
            Dict mapping logical_key to entry metadata
        """
        entries = {}
        for logical_key, entry in package.walk():
            if not entry.is_dir:
                entries[logical_key] = {
                    "physicalKey": entry.physical_key,
                    "size": entry.size,
                    "hash": entry.hash,
                }
        return entries

    def _backend_get_package_metadata(self, package: Any) -> Dict[str, Any]:
        """Get metadata from quilt3 package (backend primitive).

        Args:
            package: quilt3.Package object

        Returns:
            Package metadata dictionary (empty dict if no metadata)
        """
        return package.meta or {}

    def _backend_search_packages(self, query: str, registry: str) -> List[Dict[str, Any]]:
        """Execute Elasticsearch package search via quilt3 (backend primitive).

        Args:
            query: Search query string (empty string returns all packages)
            registry: Registry S3 URL

        Returns:
            List of package data dictionaries (not domain objects)
        """
        from quilt3.search_util import search_api

        # Extract bucket name from registry for index pattern
        bucket_name = registry.replace("s3://", "").split("/")[0]
        index_pattern = f"{bucket_name}_packages"

        # Convert string query to Elasticsearch DSL query
        if query.strip() == "":
            # Empty query - match all packages (manifest documents only)
            es_query = {
                "query": {
                    "bool": {
                        "must": [
                            {"match_all": {}},
                            {"exists": {"field": "ptr_name"}},  # Only manifest documents
                        ]
                    }
                },
                "size": 1000,
            }
        else:
            # Escape special ES characters but preserve wildcards
            escaped_query = self._escape_elasticsearch_query(query)
            es_query = {
                "query": {
                    "bool": {
                        "must": [
                            {"query_string": {"query": escaped_query}},
                            {"exists": {"field": "ptr_name"}},  # Only manifest documents
                        ]
                    }
                },
                "size": 1000,
            }

        # Execute search
        response = search_api(query=es_query, index=index_pattern, limit=1000)

        if "error" in response:
            raise Exception(f"Search API error: {response['error']}")

        # Extract and return hits as raw dictionaries
        hits = response.get("hits", {}).get("hits", [])
        results = []
        for hit in hits:
            source = hit.get("_source", {})
            results.append(
                {
                    "name": source.get("ptr_name", ""),
                    "description": source.get("description", ""),
                    "tags": source.get("tags", []),
                    "modified": source.get("ptr_last_modified", ""),
                    "bucket": bucket_name,
                    "top_hash": source.get("top_hash", ""),
                    "registry": registry,
                }
            )

        return results

    def _backend_diff_packages(self, pkg1: Any, pkg2: Any) -> Dict[str, List[str]]:
        """Compute diff between two quilt3 packages (backend primitive).

        Args:
            pkg1: First quilt3.Package object
            pkg2: Second quilt3.Package object

        Returns:
            Dict with keys "added", "deleted", "modified"
        """
        # Use quilt3's built-in diff functionality
        diff_result = pkg1.diff(pkg2)

        # Convert tuple (added, deleted, modified) to dictionary
        if isinstance(diff_result, tuple) and len(diff_result) == 3:
            added, deleted, modified = diff_result
            return {
                "added": [str(path) for path in added] if added else [],
                "deleted": [str(path) for path in deleted] if deleted else [],
                "modified": [str(path) for path in modified] if modified else [],
            }
        else:
            # If diff_result is already a dict or unexpected format, use as-is
            return diff_result if isinstance(diff_result, dict) else {"raw": [str(diff_result)]}

    def _backend_browse_package_content(self, package: Any, path: str) -> List[Dict[str, Any]]:
        """List contents of quilt3 package at path (backend primitive).

        Args:
            package: quilt3.Package object
            path: Path within package to browse

        Returns:
            List of content entry dictionaries (not domain objects)
        """
        # Navigate to path if specified
        if path:
            package = package[path]

        # Walk the package and return entries
        entries = []
        for key, entry in package.walk():
            entries.append(
                {
                    "path": key,
                    "size": entry.size if hasattr(entry, 'size') else None,
                    "type": "directory" if entry.is_dir else "file",
                }
            )

        return entries

    def _backend_get_file_url(
        self, package_name: str, registry: str, path: str, top_hash: Optional[str] = None
    ) -> str:
        """Generate download URL for file in quilt3 package (backend primitive).

        Args:
            package_name: Full package name
            registry: Registry S3 URL
            path: Path to file within package
            top_hash: Optional specific version hash

        Returns:
            Presigned URL for file download
        """
        # Browse package
        if top_hash:
            package = self.quilt3.Package.browse(package_name, registry=registry, top_hash=top_hash)
        else:
            package = self.quilt3.Package.browse(package_name, registry=registry)

        # Get presigned URL
        return str(package.get_url(path))

    def _backend_get_session_info(self) -> Dict[str, Any]:
        """Get quilt3 session information (backend primitive).

        Returns:
            Dict with session info
        """
        logged_in_url = self.quilt3.logged_in()
        return {
            "is_authenticated": bool(logged_in_url),
            "catalog_url": logged_in_url,
            "registry_url": None,  # Will be derived from catalog config if needed
        }

    def _backend_get_catalog_config(self, catalog_url: str) -> Dict[str, Any]:
        """Fetch catalog config.json (backend primitive).

        Args:
            catalog_url: Catalog URL

        Returns:
            Raw config dictionary

        Raises:
            Exception: If config fetch fails
        """
        from quilt_mcp.utils.common import normalize_url

        normalized_url = normalize_url(catalog_url)
        config_url = f"{normalized_url}/config.json"

        response = requests.get(config_url, timeout=10)
        response.raise_for_status()

        result: Dict[str, Any] = response.json()
        return result

    def _backend_list_buckets(self) -> List[Dict[str, Any]]:
        """List S3 buckets via boto3 (backend primitive).

        Returns:
            List of bucket information dictionaries
        """
        s3_client = self.get_boto3_client('s3')
        response = s3_client.list_buckets()

        buckets = []
        for bucket in response.get('Buckets', []):
            buckets.append(
                {
                    "name": bucket['Name'],
                    "created": bucket.get('CreationDate'),
                }
            )

        return buckets

    def _backend_get_boto3_session(self) -> Any:
        """Get boto3 session with quilt3 credentials (backend primitive).

        Returns:
            boto3.Session object
        """
        # Extract credentials from quilt3 session
        catalog_url = self.quilt3.logged_in()
        if not catalog_url:
            from quilt_mcp.ops.exceptions import AuthenticationError

            raise AuthenticationError("Not logged in to quilt3")

        # Get config to extract credentials
        config = self.get_catalog_config(catalog_url)

        # Create boto3 session (quilt3 handles credentials internally)
        # For now, use default session - quilt3 manages credentials
        return boto3.Session()

    def _transform_search_result_to_package_info(self, result: Dict[str, Any], registry: str) -> Package_Info:
        """Transform quilt3 search result to Package_Info (backend primitive).

        Args:
            result: Backend-specific search result dictionary
            registry: Registry URL for context

        Returns:
            Package_Info domain object
        """
        # Create mock package object for transformation
        mock_package = type('MockPackage', (), {})()
        mock_package.name = result.get("name", "")
        mock_package.description = result.get("description", "")
        mock_package.tags = result.get("tags", [])
        mock_package.modified = result.get("modified", "")
        mock_package.registry = registry
        mock_package.bucket = result.get("bucket", "")
        mock_package.top_hash = result.get("top_hash", "")

        # Use existing _transform_package from mixin
        return self._transform_package(mock_package)

    def _transform_content_entry_to_content_info(self, entry: Dict[str, Any]) -> Content_Info:
        """Transform quilt3 content entry to Content_Info (backend primitive).

        Args:
            entry: Backend-specific content entry dictionary

        Returns:
            Content_Info domain object
        """
        return Content_Info(
            path=entry.get("path", ""),
            size=entry.get("size"),
            type=entry.get("type", "file"),
            modified_date=None,  # quilt3 doesn't provide this in walk()
            download_url=None,  # Not available in browse results
        )

    def _escape_elasticsearch_query(self, query: str) -> str:
        """Escape special characters in Elasticsearch query_string queries.

        Helper method for _backend_search_packages primitive.

        Args:
            query: Raw query string

        Returns:
            Escaped query string
        """
        # Characters that need to be escaped (omit * and ? for wildcard support)
        special_chars = ['\\', '+', '-', '=', '>', '<', '!', '(', ')', '{', '}', '[', ']', '^', '"', '~', ':', '/']

        escaped = query
        for char in special_chars:
            escaped = escaped.replace(char, '\\' + char)

        return escaped
