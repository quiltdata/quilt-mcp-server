"""Tabulator resources for MCP."""

import asyncio
from typing import Dict, Optional

from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.services.tabulator_service import list_tabulator_buckets, list_tabulator_tables


class TabulatorBucketsResource(MCPResource):
    """List all buckets in Tabulator catalog."""

    @property
    def uri_scheme(self) -> str:
        return "tabulator"

    @property
    def uri_pattern(self) -> str:
        return "tabulator://buckets"

    @property
    def name(self) -> str:
        return "Tabulator Buckets"

    @property
    def description(self) -> str:
        return "List all buckets available in the Tabulator catalog"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await asyncio.to_thread(list_tabulator_buckets)

        if not result.get("success"):
            raise Exception(f"Failed to list buckets: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("buckets", []),
                "metadata": {
                    "total_count": result.get("count", 0),
                    "has_more": False,
                },
            },
        )


class TabulatorTablesResource(MCPResource):
    """List tables for a specific bucket."""

    @property
    def uri_scheme(self) -> str:
        return "tabulator"

    @property
    def uri_pattern(self) -> str:
        return "tabulator://buckets/{bucket}/tables"

    @property
    def name(self) -> str:
        return "Tabulator Tables"

    @property
    def description(self) -> str:
        return "List tabulator tables for a specific bucket"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "bucket" not in params:
            raise ValueError("Bucket name required in URI")

        bucket_name = params["bucket"]
        result = await asyncio.to_thread(list_tabulator_tables, bucket_name)

        if not result.get("success"):
            raise Exception(f"Failed to list tables: {result.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result.get("tables", []),
                "metadata": {
                    "bucket_name": bucket_name,
                    "total_count": result.get("count", 0),
                    "has_more": False,
                },
            },
        )
