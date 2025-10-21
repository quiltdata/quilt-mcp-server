"""Permissions resources for MCP."""

import asyncio
from typing import Dict, Optional

from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.services.permissions_service import (
    bucket_recommendations_get,
    check_bucket_access,
    discover_permissions,
)


class PermissionsDiscoverResource(MCPResource):
    """AWS permissions discovery."""

    @property
    def uri_scheme(self) -> str:
        return "permissions"

    @property
    def uri_pattern(self) -> str:
        return "permissions://discover"

    @property
    def name(self) -> str:
        return "Permissions Discovery"

    @property
    def description(self) -> str:
        return "Discover AWS permissions for current user/role"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await asyncio.to_thread(discover_permissions)
        return ResourceResponse(uri=uri, content=result)


class BucketRecommendationsResource(MCPResource):
    """Bucket recommendations based on permissions."""

    @property
    def uri_scheme(self) -> str:
        return "permissions"

    @property
    def uri_pattern(self) -> str:
        return "permissions://recommendations"

    @property
    def name(self) -> str:
        return "Bucket Recommendations"

    @property
    def description(self) -> str:
        return "Smart bucket recommendations based on permissions and context"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await asyncio.to_thread(bucket_recommendations_get)
        return ResourceResponse(uri=uri, content=result)


class BucketAccessResource(MCPResource):
    """Bucket-specific access check."""

    @property
    def uri_scheme(self) -> str:
        return "permissions"

    @property
    def uri_pattern(self) -> str:
        return "permissions://buckets/{bucket}/access"

    @property
    def name(self) -> str:
        return "Bucket Access Check"

    @property
    def description(self) -> str:
        return "Check access permissions for a specific bucket"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "bucket" not in params:
            raise ValueError("Bucket name required in URI")

        bucket_name = params["bucket"]
        result = await asyncio.to_thread(check_bucket_access, bucket_name=bucket_name)

        return ResourceResponse(uri=uri, content=result)
