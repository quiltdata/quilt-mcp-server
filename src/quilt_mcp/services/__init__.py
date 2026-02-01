"""Service layer package for Quilt MCP.

Modules should be imported directly (e.g., ``quilt_mcp.services.auth_service``)
to avoid importing optional dependencies at package import time.
"""

from .athena_service import AthenaQueryService
from .permission_discovery import AWSPermissionDiscovery

__all__ = ["AthenaQueryService", "AWSPermissionDiscovery"]
