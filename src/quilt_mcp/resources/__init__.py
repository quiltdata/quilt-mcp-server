"""MCP Resources framework for Quilt."""

from quilt_mcp.resources.base import ResourceRegistry, get_registry

# Phase 1 resources
from quilt_mcp.resources.admin import (
    AdminUsersResource,
    AdminRolesResource,
    AdminConfigResource,
    AdminUserResource,
    AdminSSOConfigResource,
    AdminTabulatorConfigResource,
)
from quilt_mcp.resources.athena import (
    AthenaDatabasesResource,
    AthenaWorkgroupsResource,
    AthenaTableSchemaResource,
    AthenaQueryHistoryResource,
)
from quilt_mcp.resources.metadata import (
    MetadataTemplatesResource,
    MetadataExamplesResource,
    MetadataTroubleshootingResource,
    MetadataTemplateResource,
)
from quilt_mcp.resources.workflow import WorkflowsResource, WorkflowStatusResource
from quilt_mcp.resources.tabulator import TabulatorBucketsResource, TabulatorTablesResource

# Phase 2 resources
from quilt_mcp.resources.auth import (
    AuthStatusResource,
    CatalogInfoResource,
    FilesystemStatusResource,
)
from quilt_mcp.resources.permissions import (
    PermissionsDiscoverResource,
    BucketRecommendationsResource,
    BucketAccessResource,
)


def register_all_resources():
    """Register all Phase 1 + Phase 2 resources."""
    registry = get_registry()

    # Phase 1: Admin resources (general ones first)
    registry.register(AdminUsersResource())
    registry.register(AdminRolesResource())
    registry.register(AdminConfigResource())

    # Phase 2: Auth resources
    registry.register(AuthStatusResource())
    registry.register(CatalogInfoResource())
    registry.register(FilesystemStatusResource())

    # Phase 2: Permissions resources
    registry.register(PermissionsDiscoverResource())
    registry.register(BucketRecommendationsResource())
    registry.register(BucketAccessResource())  # Parameterized

    # Phase 2: Admin nested config resources (more specific)
    registry.register(AdminSSOConfigResource())
    registry.register(AdminTabulatorConfigResource())

    # Phase 2: Admin parameterized resources (most specific - must come after AdminUsersResource)
    registry.register(AdminUserResource())

    # Phase 1: Athena resources (general ones first)
    registry.register(AthenaDatabasesResource())
    registry.register(AthenaWorkgroupsResource())

    # Phase 2: Athena nested and parameterized resources
    registry.register(AthenaQueryHistoryResource())
    registry.register(AthenaTableSchemaResource())  # Parameterized

    # Phase 1: Metadata resources (general ones first)
    registry.register(MetadataTemplatesResource())
    registry.register(MetadataExamplesResource())
    registry.register(MetadataTroubleshootingResource())

    # Phase 2: Metadata parameterized resources (most specific)
    registry.register(MetadataTemplateResource())

    # Phase 1: Workflow resources (general ones first)
    registry.register(WorkflowsResource())

    # Phase 2: Workflow parameterized resources (most specific)
    registry.register(WorkflowStatusResource())

    # Phase 1: Tabulator resources (general ones first)
    registry.register(TabulatorBucketsResource())

    # Phase 2: Tabulator parameterized resources (most specific)
    registry.register(TabulatorTablesResource())


def create_default_registry() -> ResourceRegistry:
    """Create a default resource registry with all standard resources.

    This is a legacy function maintained for backward compatibility with scripts.
    New code should use get_registry() instead.

    Returns:
        ResourceRegistry with all MCP resources registered
    """
    registry = get_registry()
    register_all_resources()
    return registry


__all__ = [
    "ResourceRegistry",
    "get_registry",
    "register_all_resources",
    "create_default_registry",
]
