"""S3 MCP Resources.

This module implements MCP resources for S3-related functions like
bucket discovery and permissions.
"""

from typing import Dict, Any, List
from .base import MCPResource


class S3BucketsResource(MCPResource):
    """MCP resource for S3 buckets discovery."""

    def __init__(self):
        """Initialize S3BucketsResource."""
        super().__init__("s3://buckets")

    async def list_items(self, **params) -> Dict[str, Any]:
        """List available S3 buckets.

        Returns:
            S3 buckets data in original format
        """
        # Import here to avoid circular imports and maintain compatibility
        from ..tools.unified_package import list_available_resources

        # Call the original sync function
        return list_available_resources()

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract buckets list from S3 buckets data.

        Flattens writable and readable buckets into a single list.
        """
        items = []

        # Add writable buckets
        writable = raw_data.get("writable_buckets", [])
        for bucket in writable:
            bucket_item = bucket.copy()
            bucket_item["access_type"] = "writable"
            items.append(bucket_item)

        # Add readable buckets
        readable = raw_data.get("readable_buckets", [])
        for bucket in readable:
            bucket_item = bucket.copy()
            bucket_item["access_type"] = "readable"
            items.append(bucket_item)

        return items

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from S3 buckets data."""
        metadata = super()._extract_metadata(raw_data)

        # Add S3-specific metadata
        if "summary" in raw_data:
            metadata["summary"] = raw_data["summary"]
        if "recommendations" in raw_data:
            metadata["recommendations"] = raw_data["recommendations"]
        if "registries" in raw_data:
            metadata["registries"] = raw_data["registries"]

        return metadata