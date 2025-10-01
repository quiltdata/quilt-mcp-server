"""MCP Resources Package.

This package provides the MCP resource framework for consolidating list-type functions
into standardized MCP resources with backward compatibility.
"""

from .base import MCPResource, ResourceResponse, ResourceRegistry
from .admin import AdminUsersResource, AdminRolesResource
from .s3 import S3BucketsResource
from .athena import AthenaDatabasesResource, AthenaWorkgroupsResource
from .metadata import (
    MetadataTemplatesResource,
    MetadataExamplesResource,
    MetadataTroubleshootingResource,
)
from .workflow import WorkflowResource
from .package import PackageToolsResource
from .tabulator import TabulatorTablesResource

__all__ = [
    # Base framework
    "MCPResource",
    "ResourceResponse",
    "ResourceRegistry",
    # Admin resources
    "AdminUsersResource",
    "AdminRolesResource",
    # S3 resources
    "S3BucketsResource",
    # Athena resources
    "AthenaDatabasesResource",
    "AthenaWorkgroupsResource",
    # Metadata resources
    "MetadataTemplatesResource",
    "MetadataExamplesResource",
    "MetadataTroubleshootingResource",
    # Workflow resources
    "WorkflowResource",
    # Package resources
    "PackageToolsResource",
    # Tabulator resources
    "TabulatorTablesResource",
]


def create_default_registry() -> ResourceRegistry:
    """Create a default resource registry with all standard resources.

    Admin resources (admin://*) are only registered if the user has admin credentials.

    Returns:
        ResourceRegistry with all MCP resources registered
    """
    from quilt_mcp.services.quilt_service import QuiltService

    registry = ResourceRegistry()

    # Check if user has admin credentials
    service = QuiltService()
    has_admin = service.has_admin_credentials()

    # Register admin resources only if user has credentials
    # NOTE: Admin resources follow URI convention of 'admin://*' scheme.
    # This is enforced by code review and documented in CLAUDE.md.
    # Future: Consider resource-level metadata (@requires_admin) for more flexibility.
    if has_admin:
        registry.register("admin://users", AdminUsersResource())
        registry.register("admin://roles", AdminRolesResource())

    # Register all non-admin resources
    registry.register("s3://buckets", S3BucketsResource())
    registry.register("athena://databases", AthenaDatabasesResource())
    registry.register("athena://workgroups", AthenaWorkgroupsResource())
    registry.register("metadata://templates", MetadataTemplatesResource())
    registry.register("metadata://examples", MetadataExamplesResource())
    registry.register("metadata://troubleshooting", MetadataTroubleshootingResource())
    registry.register("workflow://workflows", WorkflowResource())
    registry.register("package://tools", PackageToolsResource())
    registry.register("tabulator://{bucket}/tables", TabulatorTablesResource())

    return registry


# Global default registry instance
default_registry = create_default_registry()
