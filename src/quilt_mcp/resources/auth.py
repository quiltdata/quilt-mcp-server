"""Authentication resources for MCP."""

import asyncio
from typing import Dict, Optional

from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.services.auth_metadata import (
    auth_status,
    catalog_info,
    filesystem_status,
)


class AuthStatusResource(MCPResource):
    """Authentication status and configuration."""

    @property
    def uri_scheme(self) -> str:
        return "auth"

    @property
    def uri_pattern(self) -> str:
        return "auth://status"

    @property
    def name(self) -> str:
        return "Authentication Status"

    @property
    def description(self) -> str:
        return "Current authentication status and catalog configuration"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await asyncio.to_thread(auth_status)
        return ResourceResponse(uri=uri, content=result)


class CatalogInfoResource(MCPResource):
    """Catalog configuration details."""

    @property
    def uri_scheme(self) -> str:
        return "auth"

    @property
    def uri_pattern(self) -> str:
        return "auth://catalog/info"

    @property
    def name(self) -> str:
        return "Catalog Information"

    @property
    def description(self) -> str:
        return "Detailed catalog configuration and connectivity information"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await asyncio.to_thread(catalog_info)
        return ResourceResponse(uri=uri, content=result)


class FilesystemStatusResource(MCPResource):
    """Filesystem access status."""

    @property
    def uri_scheme(self) -> str:
        return "auth"

    @property
    def uri_pattern(self) -> str:
        return "auth://filesystem/status"

    @property
    def name(self) -> str:
        return "Filesystem Status"

    @property
    def description(self) -> str:
        return "Filesystem access permissions and writable directories"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await asyncio.to_thread(filesystem_status)
        return ResourceResponse(uri=uri, content=result)
