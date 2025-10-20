"""Service layer package for Quilt MCP.

Modules should be imported directly (e.g., ``quilt_mcp.services.auth_service``)
to avoid importing optional dependencies at package import time.
"""

from .athena_service import AthenaQueryService
from .permission_discovery import AWSPermissionDiscovery
from .quilt_service import QuiltService

__all__ = ["QuiltService", "AthenaQueryService", "AWSPermissionDiscovery"]
