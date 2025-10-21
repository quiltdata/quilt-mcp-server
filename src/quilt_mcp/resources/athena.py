"""Athena resources for MCP."""

import asyncio
from typing import Dict, Optional

from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.services.athena_read_service import (
    athena_databases_list,
    athena_workgroups_list,
    athena_table_schema,
    athena_query_history,
)


class AthenaDatabasesResource(MCPResource):
    """List available Athena databases."""

    @property
    def uri_scheme(self) -> str:
        return "athena"

    @property
    def uri_pattern(self) -> str:
        return "athena://databases"

    @property
    def name(self) -> str:
        return "Athena Databases"

    @property
    def description(self) -> str:
        return "List all available databases in AWS Glue Data Catalog"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await asyncio.to_thread(athena_databases_list)

        # Convert Pydantic model to dict
        result_dict = result.model_dump() if hasattr(result, 'model_dump') else result

        if not result_dict.get("success"):
            raise Exception(f"Failed to list databases: {result_dict.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result_dict.get("databases", []),
                "metadata": {
                    "total_count": len(result_dict.get("databases", [])),
                    "has_more": False,
                },
            },
        )


class AthenaWorkgroupsResource(MCPResource):
    """List available Athena workgroups."""

    @property
    def uri_scheme(self) -> str:
        return "athena"

    @property
    def uri_pattern(self) -> str:
        return "athena://workgroups"

    @property
    def name(self) -> str:
        return "Athena Workgroups"

    @property
    def description(self) -> str:
        return "List all accessible Athena workgroups"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await asyncio.to_thread(athena_workgroups_list)

        # Convert Pydantic model to dict
        result_dict = result.model_dump() if hasattr(result, 'model_dump') else result

        if not result_dict.get("success"):
            raise Exception(f"Failed to list workgroups: {result_dict.get('error', 'Unknown error')}")

        return ResourceResponse(
            uri=uri,
            content={
                "items": result_dict.get("workgroups", []),
                "metadata": {
                    "total_count": len(result_dict.get("workgroups", [])),
                    "has_more": False,
                },
            },
        )


class AthenaTableSchemaResource(MCPResource):
    """Get table schema."""

    @property
    def uri_scheme(self) -> str:
        return "athena"

    @property
    def uri_pattern(self) -> str:
        return "athena://databases/{database}/tables/{table}/schema"

    @property
    def name(self) -> str:
        return "Athena Table Schema"

    @property
    def description(self) -> str:
        return "Get detailed schema for a specific table"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "database" not in params or "table" not in params:
            raise ValueError("Database and table names required in URI")

        result = await asyncio.to_thread(
            athena_table_schema, database_name=params["database"], table_name=params["table"]
        )

        # Convert Pydantic model to dict
        result_dict = result.model_dump() if hasattr(result, 'model_dump') else result

        if not result_dict.get("success"):
            raise Exception(f"Failed to get schema: {result_dict.get('error', 'Unknown error')}")

        return ResourceResponse(uri=uri, content=result_dict)


class AthenaQueryHistoryResource(MCPResource):
    """Athena query execution history."""

    @property
    def uri_scheme(self) -> str:
        return "athena"

    @property
    def uri_pattern(self) -> str:
        return "athena://queries/history"

    @property
    def name(self) -> str:
        return "Athena Query History"

    @property
    def description(self) -> str:
        return "Recent query execution history"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        result = await asyncio.to_thread(athena_query_history)

        # Convert Pydantic model to dict
        result_dict = result.model_dump() if hasattr(result, 'model_dump') else result

        if not result_dict.get("success"):
            raise Exception(f"Failed to get query history: {result_dict.get('error', 'Unknown error')}")

        return ResourceResponse(uri=uri, content=result_dict)
