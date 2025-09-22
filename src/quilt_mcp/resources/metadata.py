"""Metadata MCP Resources.

This module implements MCP resources for metadata-related functions like
template discovery.
"""

from typing import Dict, Any, List
from .base import MCPResource


class MetadataTemplatesResource(MCPResource):
    """MCP resource for metadata templates listing."""

    def __init__(self):
        """Initialize MetadataTemplatesResource."""
        super().__init__("metadata://templates")

    async def list_items(self, **params) -> Dict[str, Any]:
        """List metadata templates.

        Returns:
            Metadata templates data in original format
        """
        # Import here to avoid circular imports and maintain compatibility
        from ..tools.metadata_templates import list_metadata_templates

        # Call the original sync function
        return list_metadata_templates()

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract templates list from metadata templates data."""
        available_templates = raw_data.get("available_templates", {})

        # Convert template dict to list of items
        items = []
        for template_name, template_info in available_templates.items():
            item = template_info.copy()
            item["name"] = template_name
            items.append(item)

        return items

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from metadata templates data."""
        metadata = super()._extract_metadata(raw_data)

        # Add metadata template-specific metadata
        if "usage_examples" in raw_data:
            metadata["usage_examples"] = raw_data["usage_examples"]
        if "custom_template_tip" in raw_data:
            metadata["custom_template_tip"] = raw_data["custom_template_tip"]

        return metadata