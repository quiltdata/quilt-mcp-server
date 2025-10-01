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
        """List package tools with usage guidance.

        Returns:
            Package tools data with categories and usage examples
        """
        return {
            "primary_tools": {
                "package_create": {
                    "description": "Main package creation tool with templates and dry-run",
                    "use_when": "Creating new packages with smart defaults",
                    "example": 'package_create("team/dataset", ["s3://bucket/file.csv"])',
                },
                "package_browse": {
                    "description": "Browse package contents with file tree view",
                    "use_when": "Exploring package structure and files",
                    "example": 'package_browse("team/dataset", recursive=True)',
                },
                "package_validate": {
                    "description": "Validate package integrity and accessibility",
                    "use_when": "Checking package health and file accessibility",
                    "example": 'package_validate("team/dataset")',
                },
            },
            "specialized_tools": {
                "package_create_from_s3": {
                    "description": "Advanced S3-to-package creation with organization",
                    "use_when": "Creating packages from entire S3 buckets/prefixes",
                    "example": 'package_create_from_s3("bucket-name", "team/dataset")',
                },
            },
            "utility_tools": {
                "list_metadata_templates": {
                    "description": "Show available metadata templates",
                    "example": "list_metadata_templates()",
                },
                "catalog_search": {
                    "description": "Search packages by content",
                    "example": 'catalog_search("genomics")',
                },
            },
            "workflow_guide": {
                "new_package": [
                    "1. package_create() - Create with template",
                    "2. package_browse() - Verify contents",
                    "3. package_validate() - Check integrity",
                    "4. catalog_url() - Get sharing URL",
                ],
                "explore_existing": [
                    "1. package_browse() - Explore structure",
                    "2. package_contents_search() - Find specific files",
                ],
            },
        }

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
