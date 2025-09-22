"""Package MCP Resources.

This module implements MCP resources for package-related functions like
tools discovery.
"""

from typing import Dict, Any, List
from .base import MCPResource


class PackageToolsResource(MCPResource):
    """MCP resource for package tools listing."""

    def __init__(self):
        """Initialize PackageToolsResource."""
        super().__init__("package://tools")

    async def list_items(self, **params) -> Dict[str, Any]:
        """List package tools.

        Returns:
            Package tools data in original format
        """
        # Import here to avoid circular imports and maintain compatibility
        from ..tools.package_management import package_tools_list

        # Call the original sync function
        return package_tools_list()

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract tools list from package tools data."""
        return raw_data.get("tools", [])

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from package tools data."""
        metadata = super()._extract_metadata(raw_data)

        # Add package tools-specific metadata
        if "categories" in raw_data:
            metadata["categories"] = raw_data["categories"]
        if "usage_tips" in raw_data:
            metadata["usage_tips"] = raw_data["usage_tips"]

        return metadata