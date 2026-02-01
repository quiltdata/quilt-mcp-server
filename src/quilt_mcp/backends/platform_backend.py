"""Platform GraphQL backend stub implementation.

This module provides a stub implementation of the Platform GraphQL backend
that raises NotImplementedError for all operations, directing users to use
local development mode instead.
"""

from typing import List, Optional, Dict, Any
from ..ops.quilt_ops import QuiltOps
from ..domain import Package_Info, Content_Info, Bucket_Info, Auth_Status, Catalog_Config, Package_Creation_Result


class Platform_Backend(QuiltOps):
    """Platform GraphQL backend stub implementation.

    This is a stub implementation that raises NotImplementedError for all
    QuiltOps methods, providing clear error messages that direct users to
    use local development mode (QUILT_MULTITENANT_MODE=false) instead.
    """

    def __init__(self):
        """Initialize Platform Backend stub."""
        pass

    def get_auth_status(self) -> Auth_Status:
        """Get current authentication status."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def search_packages(self, query: str, registry: str) -> List[Package_Info]:
        """Search for packages matching the given query."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def get_package_info(self, package_name: str, registry: str) -> Package_Info:
        """Get detailed information about a specific package."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def browse_content(self, package_name: str, registry: str, path: str = "") -> List[Content_Info]:
        """Browse contents of a package at the specified path."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def list_buckets(self) -> List[Bucket_Info]:
        """List accessible S3 buckets for Quilt operations."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def get_content_url(self, package_name: str, registry: str, path: str) -> str:
        """Get download URL for specific content within a package."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
        """Get catalog configuration from the specified catalog URL."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def configure_catalog(self, catalog_url: str) -> None:
        """Configure the default catalog URL for subsequent operations."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def get_registry_url(self) -> Optional[str]:
        """Get the current default registry URL."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def execute_graphql_query(
        self,
        query: str,
        variables: Optional[Dict] = None,
        registry: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query against the catalog."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def get_boto3_client(
        self,
        service_name: str,
        region: Optional[str] = None,
    ) -> Any:
        """Get authenticated boto3 client for AWS services."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

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
        """Create and push a package revision in a single operation."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def list_all_packages(self, registry: str) -> List[str]:
        """List all package names in the specified registry."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )

    def diff_packages(
        self,
        package1_name: str,
        package2_name: str,
        registry: str,
        package1_hash: Optional[str] = None,
        package2_hash: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Compare two package versions and return differences."""
        raise NotImplementedError(
            "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
        )
