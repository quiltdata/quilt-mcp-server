"""Metadata resources for MCP."""

import asyncio
from typing import Dict, Optional

from quilt_mcp.resources.base import MCPResource, ResourceResponse
from quilt_mcp.services.metadata_service import (
    fix_metadata_validation_issues,
    get_metadata_template,
    list_metadata_templates,
    show_metadata_examples,
)


class MetadataTemplatesResource(MCPResource):
    """List available metadata templates."""

    @property
    def uri_scheme(self) -> str:
        return "metadata"

    @property
    def uri_pattern(self) -> str:
        return "metadata://templates"

    @property
    def name(self) -> str:
        return "Metadata Templates"

    @property
    def description(self) -> str:
        return "List available metadata templates with descriptions"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await asyncio.to_thread(list_metadata_templates)

        return ResourceResponse(uri=uri, content=result)


class MetadataExamplesResource(MCPResource):
    """Show metadata usage examples."""

    @property
    def uri_scheme(self) -> str:
        return "metadata"

    @property
    def uri_pattern(self) -> str:
        return "metadata://examples"

    @property
    def name(self) -> str:
        return "Metadata Examples"

    @property
    def description(self) -> str:
        return "Comprehensive metadata usage examples with working patterns"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await asyncio.to_thread(show_metadata_examples)

        return ResourceResponse(uri=uri, content=result)


class MetadataTroubleshootingResource(MCPResource):
    """Metadata validation troubleshooting guide."""

    @property
    def uri_scheme(self) -> str:
        return "metadata"

    @property
    def uri_pattern(self) -> str:
        return "metadata://troubleshooting"

    @property
    def name(self) -> str:
        return "Metadata Troubleshooting"

    @property
    def description(self) -> str:
        return "Guidance for fixing metadata validation issues"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if uri != self.uri_pattern:
            raise ValueError(f"Invalid URI: {uri}")

        result = await asyncio.to_thread(fix_metadata_validation_issues)

        return ResourceResponse(uri=uri, content=result)


class MetadataTemplateResource(MCPResource):
    """Get a specific metadata template."""

    @property
    def uri_scheme(self) -> str:
        return "metadata"

    @property
    def uri_pattern(self) -> str:
        return "metadata://templates/{name}"

    @property
    def name(self) -> str:
        return "Metadata Template"

    @property
    def description(self) -> str:
        return "Get a specific metadata template by name"

    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        if not params or "name" not in params:
            raise ValueError("Template name required in URI")

        template_name = params["name"]
        result = await asyncio.to_thread(get_metadata_template, template_name=template_name)

        return ResourceResponse(uri=uri, content=result)
