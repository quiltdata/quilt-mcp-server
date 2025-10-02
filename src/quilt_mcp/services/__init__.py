"""Service layer integrations exposed by the Quilt MCP server."""

from .athena_service import AthenaQueryService

# Note: AWSPermissionDiscovery has been replaced with catalog-based permissions
# queries in src/quilt_mcp/tools/permissions.py
# Note: QuiltService has been removed - all functionality replaced with stateless GraphQL calls

__all__ = [
    "AthenaQueryService",
]
