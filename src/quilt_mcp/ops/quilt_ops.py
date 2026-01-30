"""QuiltOps abstract interface for domain-driven Quilt operations.

This module defines the abstract base class that provides a backend-agnostic interface
for Quilt operations. Implementations can use either quilt3 library or Platform GraphQL
while maintaining consistent domain-driven operations for MCP tools.
"""

from abc import ABC, abstractmethod
from typing import List
from ..domain import Package_Info, Content_Info, Bucket_Info


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
