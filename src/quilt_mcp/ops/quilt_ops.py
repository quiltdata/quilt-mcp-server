"""QuiltOps abstract interface for domain-driven Quilt operations.

This module defines the abstract base class that provides a backend-agnostic interface
for Quilt operations. Implementations can use either quilt3 library or Platform GraphQL
while maintaining consistent domain-driven operations for MCP tools.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from ..domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config, Package_Creation_Result
from .admin_ops import AdminOps


class QuiltOps(ABC):
    """Domain-driven abstraction for Quilt operations.

    This abstract base class defines the interface for backend-agnostic Quilt operations.
    It provides domain-driven methods that work with Quilt concepts rather than
    backend-specific types, enabling MCP tools to remain functional regardless of
    the underlying backend implementation (quilt3 library or Platform GraphQL).

    All methods return domain objects (Package_Info, Content_Info, Bucket_Info) that
    abstract away backend implementation details while providing consistent access
    to Quilt functionality.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        """Provide Pydantic core schema for QuiltOps abstract class.

        This allows Pydantic to handle QuiltOps types in function signatures
        without failing schema generation. Since QuiltOps is abstract and used
        as an optional parameter in service functions, we provide a simple
        schema that allows None values.
        """
        return core_schema.union_schema(
            [
                core_schema.none_schema(),
                core_schema.any_schema(),
            ]
        )

    # =========================================================================
    # Validation Methods (Concrete - Template Method Pattern)
    # =========================================================================
    # These methods provide input validation for all operations.
    # All validation logic lives in the base class to ensure consistency.

    def _validate_package_name(self, name: str) -> None:
        """Validate package name format.

        Package names must be in "user/package" format (two parts separated by /).

        Args:
            name: Package name to validate

        Raises:
            ValidationError: If name is invalid or malformed
        """
        import re
        from .exceptions import ValidationError

        if not name or not isinstance(name, str):
            raise ValidationError("Package name must be a non-empty string", {"field": "package_name"})

        if not re.match(r'^[^/]+/[^/]+$', name):
            raise ValidationError(
                "Package name must be in 'user/package' format", {"field": "package_name", "value": name}
            )

    def _validate_s3_uri(self, uri: str, index: Optional[int] = None) -> None:
        """Validate single S3 URI format.

        S3 URIs must start with 's3://' and include both bucket and key.

        Args:
            uri: S3 URI to validate
            index: Optional index in list (for error context)

        Raises:
            ValidationError: If URI is invalid or malformed
        """
        from .exceptions import ValidationError

        if not isinstance(uri, str) or not uri.startswith('s3://'):
            context: Dict[str, Any] = {"field": "s3_uri", "uri": uri}
            if index is not None:
                context["index"] = index
                error_msg = f"Invalid S3 URI at index {index}: must start with 's3://'"
            else:
                error_msg = "Invalid S3 URI: must start with 's3://'"
            raise ValidationError(error_msg, context)

        # Check for basic S3 URI structure (bucket and key)
        parts = uri[5:].split('/', 1)  # Remove 's3://' and split
        if len(parts) < 2 or not parts[0] or not parts[1]:
            context = {"field": "s3_uri", "uri": uri}
            if index is not None:
                context["index"] = index
                error_msg = f"Invalid S3 URI at index {index}: must include bucket and key"
            else:
                error_msg = "Invalid S3 URI: must include bucket and key"
            raise ValidationError(error_msg, context)

    def _validate_s3_uris(self, uris: List[str]) -> None:
        """Validate list of S3 URIs.

        Args:
            uris: List of S3 URIs to validate

        Raises:
            ValidationError: If list is empty or contains invalid URIs
        """
        from .exceptions import ValidationError

        if not uris or not isinstance(uris, list):
            raise ValidationError("S3 URIs must be a non-empty list", {"field": "s3_uris"})

        for i, uri in enumerate(uris):
            self._validate_s3_uri(uri, index=i)

    def _validate_registry(self, registry: str) -> None:
        """Validate registry format.

        Registry must be an S3 URI starting with 's3://'.

        Args:
            registry: Registry URL to validate

        Raises:
            ValidationError: If registry is invalid
        """
        from .exceptions import ValidationError

        if not registry or not isinstance(registry, str):
            raise ValidationError("Registry must be a non-empty string", {"field": "registry"})

        if not registry.startswith('s3://'):
            raise ValidationError(
                "Registry must be an S3 URI starting with 's3://'", {"field": "registry", "value": registry}
            )

    def _validate_package_creation_inputs(self, package_name: str, s3_uris: List[str]) -> None:
        """Validate inputs for package creation operation.

        Composite validation for create_package_revision().

        Args:
            package_name: Package name to validate
            s3_uris: List of S3 URIs to validate

        Raises:
            ValidationError: If any inputs are invalid
        """
        self._validate_package_name(package_name)
        self._validate_s3_uris(s3_uris)

    def _validate_package_update_inputs(self, package_name: str, s3_uris: List[str], registry: str) -> None:
        """Validate inputs for package update operation.

        Composite validation for update_package_revision().

        Args:
            package_name: Package name to validate
            s3_uris: List of S3 URIs to validate
            registry: Registry URL to validate

        Raises:
            ValidationError: If any inputs are invalid
        """
        self._validate_package_name(package_name)
        self._validate_registry(registry)

        # For update operations, validate list structure but allow individual URIs
        # to be invalid (they'll be skipped). Check that at least one URI is valid.
        from .exceptions import ValidationError

        if not s3_uris or not isinstance(s3_uris, list):
            raise ValidationError("S3 URIs must be a non-empty list", {"field": "s3_uris"})

        # Check that at least one URI could potentially be valid
        has_potential_valid_uri = any(
            isinstance(uri, str) and uri.startswith('s3://') and '/' in uri[5:] and not uri.endswith('/')
            for uri in s3_uris
        )

        if not has_potential_valid_uri:
            raise ValidationError(
                "No potentially valid S3 URIs found in list",
                {"field": "s3_uris", "note": "URIs must be strings starting with 's3://' and include bucket and key"},
            )

    # =========================================================================
    # Transformation Methods (Concrete - Template Method Pattern)
    # =========================================================================
    # These methods provide data transformation logic for all operations.
    # All transformation logic lives in the base class to ensure consistency.

    def _extract_logical_key(self, s3_uri: str, auto_organize: bool = True) -> str:
        """Extract logical key from S3 URI for package organization.

        Args:
            s3_uri: S3 URI in format s3://bucket/path/to/file.ext
            auto_organize: If True, preserve S3 folder structure as logical keys.
                         If False, flatten to just filenames.

        Returns:
            Logical key for use in package
        """
        if auto_organize:
            # Preserve S3 folder structure: s3://bucket/path/to/file.ext -> path/to/file.ext
            parts = s3_uri[5:].split('/', 1)  # Remove 's3://' and split on first '/'
            if len(parts) >= 2:
                return parts[1]  # Return everything after bucket name
            else:
                # Fallback: use filename if no path
                return s3_uri.split('/')[-1]
        else:
            # Flatten to just filename: s3://bucket/path/to/file.ext -> file.ext
            return s3_uri.split('/')[-1]

    def _extract_bucket_from_registry(self, registry: str) -> str:
        """Extract bucket name from registry URL.

        Handles various registry URL formats:
        - s3://bucket-name -> bucket-name
        - s3://bucket-name/prefix -> bucket-name
        - https://catalog.example.com -> catalog.example.com
        - bucket-name -> bucket-name

        Args:
            registry: Registry URL in various formats

        Returns:
            Bucket name extracted from registry URL
        """
        if not registry:
            return ""

        if registry.startswith("s3://"):
            return registry.replace("s3://", "").split("/")[0]

        if registry.startswith("http://") or registry.startswith("https://"):
            return registry.split("//", 1)[-1].split("/")[0]

        return registry.split("/")[0]

    def _build_catalog_url(self, package_name: str, registry: str) -> Optional[str]:
        """Build catalog URL for package viewing in web UI.

        Constructs a catalog URL that can be used to view the package in
        the Quilt catalog web interface. The exact URL format depends on
        the catalog domain.

        Args:
            package_name: Package name in user/package format
            registry: Registry S3 URL

        Returns:
            Catalog URL or None if cannot be constructed
        """
        try:
            bucket_name = self._extract_bucket_from_registry(registry)

            # Try to get catalog URL from logged-in session if available
            # (This will be backend-specific, so we provide a default implementation)
            # Concrete backends can override this for better URL construction

            # Simplified placeholder URL structure
            # Real implementation would determine actual catalog domain
            return f"https://catalog.example.com/b/{bucket_name}/packages/{package_name}"
        except Exception:
            # If URL construction fails, return None
            return None

    def _is_valid_s3_uri_for_update(self, s3_uri: str) -> bool:
        """Check if S3 URI is valid for update operation.

        Update operations are more permissive and skip invalid URIs rather
        than failing. This method checks if a URI meets minimum requirements.

        Args:
            s3_uri: S3 URI to check

        Returns:
            True if URI is valid for update, False otherwise
        """
        if not s3_uri.startswith("s3://"):
            return False

        without_scheme = s3_uri[5:]
        if "/" not in without_scheme:
            return False

        bucket, key = without_scheme.split("/", 1)
        if not key or key.endswith("/"):
            return False

        return True

    # =========================================================================
    # Backend Primitives (Abstract - Template Method Pattern)
    # =========================================================================
    # These abstract methods define the backend-specific operations that
    # concrete backend implementations must provide. The base class orchestrates
    # these primitives to implement high-level workflows.

    @abstractmethod
    def _backend_create_empty_package(self) -> Any:
        """Create a new empty package object (backend primitive).

        Returns a backend-specific package object that can be populated with files
        and metadata. This is a lightweight operation that doesn't perform I/O.

        Returns:
            Backend-specific package object (quilt3.Package or internal representation)

        Raises:
            BackendError: If package creation fails
        """
        pass

    @abstractmethod
    def _backend_add_file_to_package(self, package: Any, logical_key: str, s3_uri: str) -> None:
        """Add a file reference to a package (backend primitive).

        Adds the file at s3_uri with the given logical_key to the package.
        Does not copy the file - just adds a reference.

        Args:
            package: Backend-specific package object
            logical_key: Logical path within the package (e.g., "data/file.csv")
            s3_uri: S3 URI of the file to add (e.g., "s3://bucket/path/file.csv")

        Raises:
            BackendError: If adding file fails
        """
        pass

    @abstractmethod
    def _backend_set_package_metadata(self, package: Any, metadata: Dict[str, Any]) -> None:
        """Set package-level metadata (backend primitive).

        Sets or replaces all package metadata with the provided dictionary.

        Args:
            package: Backend-specific package object
            metadata: Metadata dictionary to attach to package

        Raises:
            BackendError: If setting metadata fails
        """
        pass

    @abstractmethod
    def _backend_push_package(self, package: Any, package_name: str, registry: str, message: str, copy: bool) -> str:
        """Push a package to the registry (backend primitive).

        Pushes the package to the specified registry with the given commit message.

        Args:
            package: Backend-specific package object to push
            package_name: Full package name in "user/package" format
            registry: Registry S3 URL
            message: Commit message for this revision
            copy: If True, deep copy objects to registry. If False, create shallow references.

        Returns:
            Top hash of the pushed package (empty string if push fails)

        Raises:
            BackendError: If push operation fails
        """
        pass

    @abstractmethod
    def _backend_get_package(self, package_name: str, registry: str, top_hash: Optional[str] = None) -> Any:
        """Retrieve an existing package from the registry (backend primitive).

        Fetches the package with the given name from the registry.

        Args:
            package_name: Full package name in "user/package" format
            registry: Registry S3 URL
            top_hash: Optional specific version hash (fetches latest if None)

        Returns:
            Backend-specific package object

        Raises:
            NotFoundError: If package doesn't exist
            BackendError: If retrieval fails
        """
        pass

    @abstractmethod
    def _backend_get_package_entries(self, package: Any) -> Dict[str, Dict[str, Any]]:
        """Get all entries (files) from a package (backend primitive).

        Returns a dictionary mapping logical_key to entry metadata.

        Args:
            package: Backend-specific package object

        Returns:
            Dict mapping logical_key to entry metadata (physicalKey, size, hash)

        Raises:
            BackendError: If extraction fails
        """
        pass

    @abstractmethod
    def _backend_get_package_metadata(self, package: Any) -> Dict[str, Any]:
        """Get package-level metadata (backend primitive).

        Args:
            package: Backend-specific package object

        Returns:
            Package metadata dictionary (empty dict if no metadata)
        """
        pass

    @abstractmethod
    def _backend_search_packages(self, query: str, registry: str) -> List[Dict[str, Any]]:
        """Execute backend-specific package search (backend primitive).

        Searches for packages matching the query in the registry.

        Args:
            query: Search query string (empty string returns all packages)
            registry: Registry S3 URL to search in

        Returns:
            List of package data dictionaries (not domain objects).
            Each dict must include: name, bucket, top_hash, modified

        Raises:
            BackendError: If search fails
        """
        pass

    @abstractmethod
    def _backend_diff_packages(self, pkg1: Any, pkg2: Any) -> Dict[str, List[str]]:
        """Compute differences between two packages (backend primitive).

        Compares the contents of two package objects.

        Args:
            pkg1: First backend-specific package object
            pkg2: Second backend-specific package object

        Returns:
            Dict with keys "added", "deleted", "modified", each mapping to list of paths

        Raises:
            BackendError: If diff computation fails
        """
        pass

    @abstractmethod
    def _backend_browse_package_content(self, package: Any, path: str) -> List[Dict[str, Any]]:
        """List contents of a package at a specific path (backend primitive).

        Args:
            package: Backend-specific package object
            path: Path within package to browse (empty string for root)

        Returns:
            List of content entry dictionaries (not domain objects).
            Each dict must include: path, type ("file" or "directory")

        Raises:
            NotFoundError: If path doesn't exist
            BackendError: If browse operation fails
        """
        pass

    @abstractmethod
    def _backend_get_file_url(
        self, package_name: str, registry: str, path: str, top_hash: Optional[str] = None
    ) -> str:
        """Generate a download URL for a file in a package (backend primitive).

        Args:
            package_name: Full package name in "user/package" format
            registry: Registry S3 URL
            path: Path to file within package
            top_hash: Optional specific version hash (uses latest if None)

        Returns:
            Presigned or direct URL for downloading the file

        Raises:
            NotFoundError: If file doesn't exist
            BackendError: If URL generation fails
        """
        pass

    @abstractmethod
    def _backend_get_session_info(self) -> Dict[str, Any]:
        """Get backend-specific session/authentication information (backend primitive).

        Returns:
            Dict with session info including: is_authenticated (bool), catalog_url (Optional[str])

        Raises:
            BackendError: If session info retrieval fails
        """
        pass

    @abstractmethod
    def _backend_get_catalog_config(self, catalog_url: str) -> Dict[str, Any]:
        """Fetch catalog configuration from a catalog URL (backend primitive).

        Fetches config.json from the catalog.

        Args:
            catalog_url: Catalog URL (e.g., "https://example.quiltdata.com")

        Returns:
            Raw config dictionary from config.json

        Raises:
            NotFoundError: If config not found
            BackendError: If fetch fails
        """
        pass

    @abstractmethod
    def _backend_list_buckets(self) -> List[Dict[str, Any]]:
        """List accessible S3 buckets (backend primitive).

        Returns:
            List of bucket information dictionaries (not domain objects).
            Each dict must include: name

        Raises:
            BackendError: If listing fails
        """
        pass

    @abstractmethod
    def _backend_get_boto3_session(self) -> Any:
        """Get authenticated boto3 session for AWS operations (backend primitive).

        Returns:
            Configured boto3.Session with valid credentials

        Raises:
            AuthenticationError: If not available or credentials invalid
        """
        pass

    @abstractmethod
    def _transform_search_result_to_package_info(self, result: Dict[str, Any], registry: str) -> Package_Info:
        """Transform backend search result to Package_Info domain object (backend primitive).

        Backends implement this to transform their specific search result format
        to the standard Package_Info domain object.

        Args:
            result: Backend-specific search result dictionary
            registry: Registry URL for context

        Returns:
            Package_Info domain object

        Raises:
            BackendError: If transformation fails
        """
        pass

    @abstractmethod
    def _transform_content_entry_to_content_info(self, entry: Dict[str, Any]) -> Content_Info:
        """Transform backend content entry to Content_Info domain object (backend primitive).

        Backends implement this to transform their specific content entry format
        to the standard Content_Info domain object.

        Args:
            entry: Backend-specific content entry dictionary

        Returns:
            Content_Info domain object

        Raises:
            BackendError: If transformation fails
        """
        pass

    @property
    @abstractmethod
    def admin(self) -> AdminOps:
        """Access to admin operations.

        Provides access to administrative operations including user management,
        role management, and SSO configuration. This property returns an AdminOps
        interface that abstracts backend-specific admin functionality.

        Returns:
            AdminOps interface for performing admin operations

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When admin functionality is not available or fails to initialize
            PermissionError: When user lacks admin privileges
        """
        pass

    @abstractmethod
    def get_auth_status(self) -> Auth_Status:
        """Get current authentication status.

        Retrieves the current authentication state including whether the user is
        authenticated, which catalog they're logged into, and the configured registry.
        This provides a unified view of authentication across different backends.

        Returns:
            Auth_Status object with authentication details

        Raises:
            BackendError: When the backend operation fails to retrieve auth status
        """
        pass

    def search_packages(self, query: str, registry: str) -> List[Package_Info]:
        """Search for packages matching the given query (concrete method).

        This is a Template Method that orchestrates backend primitives to implement
        the complete package search workflow.

        Workflow:
            1. Validate registry (validation in base class)
            2. Execute search (backend primitive)
            3. Transform results (transformation via backend primitive)
            4. Return list

        Args:
            query: Search query string to match against package names, descriptions, tags
            registry: Registry URL (e.g., "s3://my-registry-bucket") to search within

        Returns:
            List of Package_Info objects representing matching packages

        Raises:
            ValidationError: When registry parameter is invalid
            BackendError: When the backend operation fails (network, API errors, etc.)
        """
        from .exceptions import ValidationError, BackendError

        try:
            # STEP 1: VALIDATION
            self._validate_registry(registry)

            # STEP 2: EXECUTE SEARCH (backend primitive)
            search_results = self._backend_search_packages(query, registry)

            # STEP 3: TRANSFORM RESULTS (transformation via backend primitive)
            packages = []
            for result in search_results:
                package_info = self._transform_search_result_to_package_info(result, registry)
                packages.append(package_info)

            # STEP 4: RETURN
            return packages

        except ValidationError:
            raise
        except Exception as e:
            raise BackendError(
                f"Package search failed: {str(e)}", context={"query": query, "registry": registry}
            ) from e

    @abstractmethod
    def get_package_info(self, package_name: str, registry: str) -> Package_Info:
        """Get detailed information about a specific package.

        Retrieves comprehensive metadata for the specified package from the registry.
        This includes package description, tags, modification date, and version information.

        Args:
            package_name: Full package name in "user/package" format
            registry: Registry URL where the package is stored

        Returns:
            Package_Info object with detailed package metadata

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails or package is not found
            ValidationError: When package_name or registry parameters are invalid
        """
        pass

    def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
        """Browse contents of a package at the specified path (concrete method).

        This is a Template Method that orchestrates backend primitives to implement
        the complete content browsing workflow.

        Workflow:
            1. Validate inputs (validation in base class)
            2. Get package (backend primitive)
            3. Browse content (backend primitive)
            4. Transform results (transformation via backend primitive)
            5. Return list

        Args:
            package_name: Full package name in "user/package" format
            registry: Registry URL where the package is stored
            path: Path within the package to browse (defaults to root)

        Returns:
            List of Content_Info objects representing files and directories

        Raises:
            ValidationError: When parameters are invalid
            NotFoundError: When package or path doesn't exist
            BackendError: When the backend operation fails
        """
        from .exceptions import ValidationError, NotFoundError, BackendError

        try:
            # STEP 1: VALIDATION
            self._validate_package_name(package_name)
            self._validate_registry(registry)

            # STEP 2: GET PACKAGE (backend primitive)
            package = self._backend_get_package(package_name, registry)

            # STEP 3: BROWSE CONTENT (backend primitive)
            content_entries = self._backend_browse_package_content(package, path)

            # STEP 4: TRANSFORM RESULTS (transformation via backend primitive)
            contents = []
            for entry in content_entries:
                content_info = self._transform_content_entry_to_content_info(entry)
                contents.append(content_info)

            # STEP 5: RETURN
            return contents

        except (ValidationError, NotFoundError):
            raise
        except Exception as e:
            raise BackendError(
                f"Browse content failed: {str(e)}",
                context={"package_name": package_name, "registry": registry, "path": path},
            ) from e

    @abstractmethod
    def list_buckets(self) -> List[Bucket_Info]:
        """List accessible S3 buckets for Quilt operations.

        Returns information about S3 buckets that the current user can access
        for Quilt package operations. Includes bucket metadata and access permissions.

        Returns:
            List of Bucket_Info objects representing accessible buckets

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails or AWS access is denied
        """
        pass

    @abstractmethod
    def get_content_url(self, package_name: str, registry: str, path: str) -> str:
        """Get download URL for specific content within a package.

        Generates a URL that can be used to download or access the specified file
        within a package. The URL format may vary by backend but should provide
        direct access to the content.

        Args:
            package_name: Full package name in "user/package" format
            registry: Registry URL where the package is stored
            path: Path to the specific file within the package

        Returns:
            URL string for accessing the content

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails or content is not found
            ValidationError: When parameters are invalid or path doesn't exist
        """
        pass

    @abstractmethod
    def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
        """Get catalog configuration from the specified catalog URL.

        Retrieves the catalog configuration including AWS infrastructure details,
        API endpoints, and derived information like stack prefix and tabulator catalog name.
        This provides backend-agnostic access to catalog configuration data.

        Args:
            catalog_url: URL of the catalog (e.g., 'https://example.quiltdata.com')

        Returns:
            Catalog_Config object with configuration details

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails or catalog is unreachable
            ValidationError: When catalog_url parameter is invalid
            NotFoundError: When catalog configuration is not found
        """
        pass

    @abstractmethod
    def configure_catalog(self, catalog_url: str) -> None:
        """Configure the default catalog URL for subsequent operations.

        Sets the default catalog URL that will be used for operations that don't
        explicitly specify a catalog. This configuration persists across operations
        within the same session.

        Args:
            catalog_url: URL of the catalog to configure as default

        Raises:
            AuthenticationError: When authentication credentials are invalid
            BackendError: When the backend operation fails
            ValidationError: When catalog_url parameter is invalid
        """
        pass

    @abstractmethod
    def get_registry_url(self) -> Optional[str]:
        """Get the current default registry URL.

        Retrieves the currently configured default registry URL that is used
        for GraphQL queries. This URL is typically set through catalog configuration
        or authentication.

        Returns:
            Registry API URL (HTTPS) for GraphQL queries (e.g., "https://example-registry.quiltdata.com") or None if not configured

        Raises:
            BackendError: When the backend operation fails to retrieve registry URL
        """
        pass

    @abstractmethod
    def get_graphql_endpoint(self) -> str:
        """Get the GraphQL API endpoint URL.

        Returns the fully-qualified GraphQL endpoint URL for executing queries.
        This is typically derived from the catalog or registry configuration.

        Implementations:
        - Quilt3Backend: Constructs from quilt3 catalog config
        - HTTPBackend: Reads from environment or config
        - TestBackend: Returns mock endpoint

        Returns:
            GraphQL endpoint URL (e.g., "https://example.quiltdata.com/graphql")

        Raises:
            AuthenticationError: When not authenticated or no catalog configured
            BackendError: When endpoint cannot be determined
        """
        pass

    @abstractmethod
    def get_graphql_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for GraphQL requests.

        Returns HTTP headers containing authentication credentials (typically JWT)
        for authenticating GraphQL requests. The specific auth mechanism depends
        on the backend implementation.

        Implementations:
        - Quilt3Backend: Extracts JWT from quilt3 session
        - HTTPBackend: Extracts from incoming request context
        - TestBackend: Returns mock credentials

        Returns:
            Dict of HTTP headers (e.g., {"Authorization": "Bearer <token>"})

        Raises:
            AuthenticationError: When credentials are not available or invalid
            BackendError: When auth headers cannot be retrieved
        """
        pass

    @abstractmethod
    def execute_graphql_query(
        self,
        query: str,
        variables: Optional[Dict] = None,
        registry: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query against the catalog.

        Executes a GraphQL query against the catalog API, providing authenticated
        access to catalog data and operations. This method abstracts the underlying
        GraphQL implementation details while providing consistent query execution
        across different backends.

        Args:
            query: GraphQL query string to execute
            variables: Optional dictionary of query variables
            registry: Target registry URL (uses default if None)

        Returns:
            Dict[str, Any]: Dictionary containing the GraphQL response data

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the GraphQL query execution fails
            ValidationError: When query syntax is invalid or variables are malformed
        """
        pass

    # Tabulator operations (provided by TabulatorMixin)
    @abstractmethod
    def list_tabulator_tables(self, bucket: str) -> List[Dict[str, str]]:
        """List all tabulator tables in a bucket.

        Args:
            bucket: S3 bucket name

        Returns:
            List of dicts with 'name' and 'config' (YAML string) keys

        Raises:
            BackendError: If GraphQL query fails
            ValidationError: If bucket not found
        """
        ...

    @abstractmethod
    def get_tabulator_table(self, bucket: str, table_name: str) -> Dict[str, str]:
        """Get a specific tabulator table configuration.

        Args:
            bucket: S3 bucket name
            table_name: Table name

        Returns:
            Dict with 'name' and 'config' (YAML string) keys

        Raises:
            BackendError: If GraphQL query fails
            ValidationError: If table not found
        """
        ...

    @abstractmethod
    def create_tabulator_table(self, bucket: str, table_name: str, config: Optional[str]) -> Dict[str, Any]:
        """Create or update a tabulator table.

        Args:
            bucket: S3 bucket name
            table_name: Table name
            config: YAML configuration string

        Returns:
            Dict with operation result

        Raises:
            BackendError: If GraphQL mutation fails
            ValidationError: If configuration is invalid
            PermissionError: If user lacks write access
        """
        ...

    @abstractmethod
    def update_tabulator_table(self, bucket: str, table_name: str, config: str) -> Dict[str, Any]:
        """Update an existing tabulator table configuration.

        This is an alias for create_tabulator_table() since the GraphQL
        mutation handles both create and update.

        Args:
            bucket: S3 bucket name
            table_name: Table name
            config: YAML configuration string

        Returns:
            Dict with operation result
        """
        ...

    @abstractmethod
    def rename_tabulator_table(self, bucket: str, old_name: str, new_name: str) -> Dict[str, Any]:
        """Rename a tabulator table.

        Args:
            bucket: S3 bucket name
            old_name: Current table name
            new_name: New table name

        Returns:
            Dict with operation result

        Raises:
            BackendError: If GraphQL mutation fails
            ValidationError: If old table not found or new name invalid
        """
        ...

    @abstractmethod
    def delete_tabulator_table(self, bucket: str, table_name: str) -> Dict[str, Any]:
        """Delete a tabulator table.

        Deletion is implemented by setting config to null.

        Args:
            bucket: S3 bucket name
            table_name: Table name to delete

        Returns:
            Dict with operation result

        Raises:
            BackendError: If GraphQL mutation fails
        """
        ...

    @abstractmethod
    def get_open_query_status(self) -> Dict[str, Any]:
        """Get tabulator open query status via GraphQL.

        Returns:
            Dict with success flag and open_query_enabled status

        Raises:
            BackendError: If GraphQL query fails
        """
        ...

    @abstractmethod
    def set_open_query(self, enabled: bool) -> Dict[str, Any]:
        """Set tabulator open query status via GraphQL.

        Args:
            enabled: Whether to enable or disable open query

        Returns:
            Dict with success flag, current status, and message

        Raises:
            BackendError: If GraphQL mutation fails
        """
        ...

    @abstractmethod
    def get_boto3_client(
        self,
        service_name: str,
        region: Optional[str] = None,
    ) -> Any:
        """Get authenticated boto3 client for AWS services.

        Creates and returns a boto3 client for the specified AWS service,
        configured with the appropriate authentication credentials from the
        current session. This provides backend-agnostic access to AWS services
        needed for Quilt operations.

        Args:
            service_name: AWS service name (e.g., 'athena', 's3', 'glue')
            region: AWS region override (uses catalog region if None)

        Returns:
            Configured boto3 client for the specified service

        Raises:
            AuthenticationError: When AWS credentials are not available or invalid
            BackendError: When boto3 client creation fails
            ValidationError: When service_name is invalid or unsupported
        """
        pass

    def create_package_revision(
        self,
        package_name: str,
        s3_uris: List[str],
        metadata: Optional[Dict] = None,
        registry: Optional[str] = None,
        message: str = "Package created via QuiltOps",
        auto_organize: bool = True,
        copy: bool = False,
    ) -> Package_Creation_Result:
        """Create and push a package revision in a single operation (concrete method).

        This is a Template Method that orchestrates backend primitives to implement
        the complete package creation workflow. All validation, transformation, and
        orchestration logic lives here. Backends only implement primitives.

        Workflow:
            1. Validate inputs (validation in base class)
            2. Create empty package (backend primitive)
            3. Add files with logical keys (transformation + backend primitive)
            4. Set metadata (backend primitive)
            5. Push to registry (backend primitive)
            6. Build catalog URL (transformation in base class)
            7. Return result

        Args:
            package_name: Full package name in "user/package" format
            s3_uris: List of S3 URIs to include in the package
            metadata: Optional metadata dictionary to attach to the package
            registry: Target registry URL (uses default if None)
            message: Commit message for the package revision
            auto_organize: If True, preserve S3 folder structure as logical keys.
                         If False, flatten to just filenames (default: True)
            copy: Whether to copy files to registry bucket (default: False)
                - True: Deep copy objects to registry bucket
                - False: Create shallow references to original S3 locations (no copy)

        Returns:
            Package_Creation_Result with creation details and status

        Raises:
            ValidationError: When parameters are invalid (malformed URIs, invalid names)
            BackendError: When the backend operation fails (S3 access, push errors, etc.)
        """
        from .exceptions import ValidationError, BackendError

        try:
            # STEP 1: VALIDATION (all validation in base class)
            self._validate_package_creation_inputs(package_name, s3_uris)

            # Handle default registry
            if not registry:
                # Try to get default registry from backend
                default_registry = self.get_registry_url()
                if default_registry:
                    registry = default_registry
                else:
                    # Use a placeholder - backends will handle appropriately
                    registry = "s3://unknown-registry"

            # STEP 2: CREATE EMPTY PACKAGE (backend primitive)
            package = self._backend_create_empty_package()

            # STEP 3: ADD FILES (transformation + backend primitive)
            for s3_uri in s3_uris:
                logical_key = self._extract_logical_key(s3_uri, auto_organize)
                self._backend_add_file_to_package(package, logical_key, s3_uri)

            # STEP 4: SET METADATA (backend primitive)
            if metadata:
                self._backend_set_package_metadata(package, metadata)

            # STEP 5: PUSH PACKAGE (backend primitive)
            top_hash = self._backend_push_package(package, package_name, registry, message, copy)

            # STEP 6: BUILD CATALOG URL (transformation in base class)
            catalog_url = self._build_catalog_url(package_name, registry)

            # STEP 7: RETURN RESULT
            return Package_Creation_Result(
                package_name=package_name,
                top_hash=top_hash,
                registry=registry,
                catalog_url=catalog_url,
                file_count=len(s3_uris),
                success=bool(top_hash),
            )

        except (ValidationError, ValueError):
            # Re-raise validation errors as-is (ValueError from domain object validation)
            raise
        except Exception as e:
            # Wrap backend exceptions in BackendError
            error_context = {
                "package_name": package_name,
                "registry": registry if registry else "None",
                "file_count": len(s3_uris),
            }
            raise BackendError(f"Package creation failed: {str(e)}", context=error_context) from e

    @abstractmethod
    def list_all_packages(self, registry: str) -> List[str]:
        """List all package names in the specified registry.

        Retrieves a list of all package names available in the given registry.
        This provides a simple way to discover packages without detailed metadata.

        Args:
            registry: Registry URL to list packages from

        Returns:
            List[str]: List of package names in "user/package" format

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails or registry is unreachable
            ValidationError: When registry parameter is invalid
        """
        pass

    @abstractmethod
    def diff_packages(
        self,
        package1_name: str,
        package2_name: str,
        registry: str,
        package1_hash: Optional[str] = None,
        package2_hash: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Compare two package versions and return differences.

        Compares the contents of two package versions and returns the differences
        between them. This includes files that were added, deleted, or modified
        between the two package versions.

        Args:
            package1_name: Full name of the first package in "user/package" format
            package2_name: Full name of the second package in "user/package" format
            registry: Registry URL where both packages are stored
            package1_hash: Optional specific hash/version of the first package.
                         If None, uses the latest version.
            package2_hash: Optional specific hash/version of the second package.
                         If None, uses the latest version.

        Returns:
            Dict[str, List[str]]: Dictionary with difference categories:
                - "added": List of file paths that were added in package2
                - "deleted": List of file paths that were deleted from package1
                - "modified": List of file paths that were modified between versions

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails or packages are not found
            ValidationError: When package names, registry, or hash parameters are invalid
            NotFoundError: When one or both packages don't exist in the registry
        """
        pass

    def update_package_revision(
        self,
        package_name: str,
        s3_uris: List[str],
        registry: str,
        metadata: Optional[Dict] = None,
        message: str = "Package updated via QuiltOps",
        auto_organize: bool = False,
        copy: str = "none",
    ) -> Package_Creation_Result:
        """Update an existing package with new files (concrete method).

        This is a Template Method that orchestrates backend primitives to implement
        the complete package update workflow. All validation, transformation, and
        orchestration logic lives here.

        Workflow:
            1. Validate inputs (validation in base class)
            2. Get existing package (backend primitive)
            3. Get existing entries (backend primitive)
            4. Get existing metadata (backend primitive)
            5. Create new package (backend primitive)
            6. Add existing files (backend primitive loop)
            7. Add new files with logical keys (transformation + backend primitive)
            8. Merge metadata (orchestration in base class)
            9. Push updated package (backend primitive)
            10. Build catalog URL (transformation in base class)
            11. Return result

        Args:
            package_name: Full package name in "user/package" format
            s3_uris: List of S3 URIs to add to the package
            registry: Registry URL where the package is stored
            metadata: Optional metadata dictionary to merge with existing package metadata
            message: Commit message for the package update
            auto_organize: If True, preserve S3 folder structure as logical keys.
                         If False, flatten to just filenames (default: False)
            copy: Copy behavior for files:
                - "none": Create shallow references to original S3 locations (no copy)
                - "all": Deep copy all objects to registry bucket

        Returns:
            Package_Creation_Result with update details and status

        Raises:
            ValidationError: When parameters are invalid (malformed URIs, invalid names)
            NotFoundError: When the package doesn't exist in the registry
            BackendError: When the backend operation fails (S3 access, push errors, etc.)
        """
        from .exceptions import ValidationError, NotFoundError, BackendError

        try:
            # STEP 1: VALIDATION
            self._validate_package_update_inputs(package_name, s3_uris, registry)

            # STEP 2: GET EXISTING PACKAGE (backend primitive)
            existing_package = self._backend_get_package(package_name, registry)

            # STEP 3: GET EXISTING ENTRIES (backend primitive)
            existing_entries = self._backend_get_package_entries(existing_package)

            # STEP 4: GET EXISTING METADATA (backend primitive)
            existing_meta = self._backend_get_package_metadata(existing_package)

            # STEP 5: CREATE NEW PACKAGE (backend primitive)
            updated_package = self._backend_create_empty_package()

            # STEP 6: ADD EXISTING FILES (backend primitive loop)
            for logical_key, entry_data in existing_entries.items():
                # Extract physical key (different backends may use different field names)
                physical_key = entry_data.get("physicalKey") or entry_data.get("physical_key")
                if physical_key:
                    self._backend_add_file_to_package(updated_package, logical_key, physical_key)

            # STEP 7: ADD NEW FILES (transformation + backend primitive)
            added_count = 0
            for s3_uri in s3_uris:
                # Skip invalid URIs (update is permissive)
                if self._is_valid_s3_uri_for_update(s3_uri):
                    logical_key = self._extract_logical_key(s3_uri, auto_organize)
                    self._backend_add_file_to_package(updated_package, logical_key, s3_uri)
                    added_count += 1

            # STEP 8: MERGE METADATA (orchestration in base class)
            merged_meta = {**existing_meta, **(metadata or {})}
            self._backend_set_package_metadata(updated_package, merged_meta)

            # STEP 9: PUSH UPDATED PACKAGE (backend primitive)
            copy_bool = copy == "all"
            top_hash = self._backend_push_package(updated_package, package_name, registry, message, copy_bool)

            # STEP 10: BUILD CATALOG URL
            catalog_url = self._build_catalog_url(package_name, registry)

            # STEP 11: RETURN RESULT
            return Package_Creation_Result(
                package_name=package_name,
                top_hash=top_hash,
                registry=registry,
                catalog_url=catalog_url,
                file_count=added_count,
                success=bool(top_hash),
            )

        except (ValidationError, NotFoundError):
            # Re-raise domain exceptions as-is
            raise
        except Exception as e:
            # Wrap backend exceptions in BackendError
            error_context = {
                "package_name": package_name,
                "registry": registry,
                "file_count": len(s3_uris),
            }
            raise BackendError(f"Package update failed: {str(e)}", context=error_context) from e
