"""QuiltOps abstract interface for domain-driven Quilt operations.

This module defines the abstract base class that provides a backend-agnostic interface
for Quilt operations. Implementations can use either quilt3 library or Platform GraphQL
while maintaining consistent domain-driven operations for MCP tools.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from ..domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config


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
        for operations when no explicit registry is specified. This URL is
        typically set through catalog configuration or authentication.

        Returns:
            Registry S3 URL (e.g., "s3://my-registry-bucket") or None if not configured

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
