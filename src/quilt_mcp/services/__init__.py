"""Service layer integrations exposed by the Quilt MCP server."""

from .quilt_service import QuiltService
from .athena_service import AthenaQueryService

# Note: AWSPermissionDiscovery has been replaced with catalog-based permissions
# queries in src/quilt_mcp/tools/permissions.py

__all__ = [
    "QuiltService",
    "AthenaQueryService",
]
