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

    @abstractmethod
    def search_packages(self, query: str, registry: str) -> List[Package_Info]:
        """Search for packages matching the given query.

        Searches for Quilt packages in the specified registry that match the query string.
        The search behavior may vary by backend but should return semantically equivalent
        results across all implementations.

        Args:
            query: Search query string to match against package names, descriptions, tags
            registry: Registry URL (e.g., "s3://my-registry-bucket") to search within

        Returns:
            List of Package_Info objects representing matching packages

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails (network, API errors, etc.)
            ValidationError: When query or registry parameters are invalid
        """
        pass

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

    @abstractmethod
    def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
        """Browse contents of a package at the specified path.

        Lists files and directories within a package, starting from the given path.
        Returns both file and directory entries with appropriate metadata for each.

        Args:
            package_name: Full package name in "user/package" format
            registry: Registry URL where the package is stored
            path: Path within the package to browse (defaults to root)

        Returns:
            List of Content_Info objects representing files and directories

        Raises:
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails or package/path is not found
            ValidationError: When parameters are invalid or path doesn't exist
        """
        pass

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

    @abstractmethod
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
        """Create and push a package revision in a single operation.

        Creates a new package revision with the specified files and metadata,
        then pushes it to the registry. This is a complete operation that
        handles the entire package creation workflow.

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
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails (S3 access, push errors, etc.)
            ValidationError: When parameters are invalid (malformed URIs, invalid names)
            PermissionError: When user lacks permission to create packages in registry
        """
        pass

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

    @abstractmethod
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
        """Update an existing package with new files.

        Updates an existing package by adding new files from the specified S3 URIs.
        This operation browses the existing package, adds the new files, and pushes
        the updated package to the registry.

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
            AuthenticationError: When authentication credentials are invalid or missing
            BackendError: When the backend operation fails (S3 access, push errors, etc.)
            ValidationError: When parameters are invalid (malformed URIs, invalid names)
            NotFoundError: When the package doesn't exist in the registry
            PermissionError: When user lacks permission to update packages in registry
        """
        pass
