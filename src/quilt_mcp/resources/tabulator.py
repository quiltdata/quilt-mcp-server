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
        """List all tabulator tables configured for a bucket.

        Tabulator tables enable SQL querying across multiple Quilt packages,
        aggregating data based on configurable patterns and schemas.

        Args:
            bucket_name: Name of the bucket to list tables for

        Returns:
            Dict containing:
            - success: Whether the operation succeeded
            - tables: List of tabulator tables with their configurations
            - bucket_name: The bucket name that was queried
            - count: Number of tables found
        """
        from ..tools.tabulator import get_tabulator_service
        from ..utils import format_error_response
        import logging

        logger = logging.getLogger(__name__)

        try:
            service = get_tabulator_service()
            return service.list_tables(bucket_name)
        except Exception as e:
            logger.error(f"Error in tabulator list_items: {e}")
            return format_error_response(f"Failed to list tabulator tables: {str(e)}")

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
