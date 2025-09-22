"""Tabulator MCP Resources.

This module implements MCP resources for tabulator-related functions like
table discovery.
"""

from typing import Dict, Any, List
from .base import MCPResource


class TabulatorTablesResource(MCPResource):
    """MCP resource for tabulator tables listing."""

    def __init__(self):
        """Initialize TabulatorTablesResource."""
        super().__init__("tabulator://{bucket}/tables")

    async def list_items(self, bucket_name: str, **params) -> Dict[str, Any]:
        """List tabulator tables for a bucket.

        Args:
            bucket_name: Name of the bucket to list tables for

        Returns:
            Tabulator tables data in original format
        """
        # Import here to avoid circular imports and maintain compatibility
        from ..tools.tabulator import tabulator_tables_list

        # Call the original async function
        return await tabulator_tables_list(bucket_name=bucket_name)

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract tables list from tabulator tables data."""
        return raw_data.get("tables", [])

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from tabulator tables data."""
        metadata = super()._extract_metadata(raw_data)

        # Add tabulator-specific metadata
        if "bucket_name" in raw_data:
            metadata["bucket_name"] = raw_data["bucket_name"]

        return metadata

    def get_uri_pattern(self) -> str:
        """Get the URI pattern for this resource with bucket parameter."""
        return "tabulator://{bucket}/tables"