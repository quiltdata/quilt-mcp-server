"""Base classes for MCP resources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json
import logging
import re
import time

from quilt_mcp.config import resource_config

logger = logging.getLogger(__name__)


@dataclass
class ResourceResponse:
    """Standard response format for MCP resources."""

    uri: str
    mime_type: str = "application/json"
    content: Any = None

    def to_dict(self) -> dict:
        """Convert to MCP resource response format."""
        return {
            "uri": self.uri,
            "mimeType": self.mime_type,
            "text": self._serialize_content(),
        }

    def _serialize_content(self) -> str:
        """Serialize content to string based on mime type."""
        if self.mime_type == "application/json":
            return json.dumps(self.content, indent=2)
        return str(self.content)


class MCPResource(ABC):
    """Base class for all MCP resources."""

    @property
    @abstractmethod
    def uri_scheme(self) -> str:
        """The URI scheme this resource handles (e.g., 'admin', 'athena')."""
        pass

    @property
    @abstractmethod
    def uri_pattern(self) -> str:
        """
        The URI pattern this resource matches (e.g., 'admin://users').
        This is also the URI template - can contain {param} placeholders.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for the resource."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this resource provides."""
        pass

    async def read(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        """
        Read the resource at the given URI with performance logging.

        Args:
            uri: Full URI to read (e.g., 'admin://users')
            params: Parameters extracted from URI template (for parameterized resources)

        Returns:
            ResourceResponse with the resource data

        Raises:
            ValueError: If URI is invalid or malformed
            PermissionError: If user lacks required permissions
            Exception: For other errors
        """
        start_time = time.time()

        try:
            response = await self._read_impl(uri, params)

            if resource_config.RESOURCE_ACCESS_LOGGING:
                elapsed = time.time() - start_time
                logger.info(f"Resource read: {uri} ({elapsed:.3f}s)")

            return response
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Resource read failed: {uri} ({elapsed:.3f}s) - {str(e)}")
            raise

    @abstractmethod
    async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
        """
        Implementation to be overridden by subclasses.

        Args:
            uri: Full URI to read (e.g., 'admin://users')
            params: Parameters extracted from URI template (for parameterized resources)

        Returns:
            ResourceResponse with the resource data

        Raises:
            ValueError: If URI is invalid or malformed
            PermissionError: If user lacks required permissions
            Exception: For other errors
        """
        pass

    def matches(self, uri: str) -> bool:
        """Check if this resource handles the given URI (with pattern matching)."""
        pattern = self._template_to_regex(self.uri_pattern)
        return bool(re.match(pattern, uri))

    def extract_params(self, uri: str) -> Dict[str, str]:
        """Extract parameters from URI based on template."""
        pattern = self._template_to_regex(self.uri_pattern)
        match = re.match(pattern, uri)
        if not match:
            return {}
        return match.groupdict()

    @staticmethod
    def _template_to_regex(template: str) -> str:
        """Convert URI template to regex pattern."""
        # Escape special regex characters except {}
        escaped = re.escape(template)
        # Replace {param} with named capture groups
        pattern = re.sub(r'\\{(\w+)\\}', r'(?P<\1>[^/]+)', escaped)
        return f'^{pattern}$'


class ResourceRegistry:
    """Registry for all MCP resources with pattern matching support."""

    def __init__(self):
        # Use list to maintain registration order (more specific patterns first)
        self._resources: List[MCPResource] = []

    def register(self, resource: MCPResource):
        """
        Register a resource.

        Note: Order matters for pattern matching. More specific patterns
        should be registered before more general ones.
        """
        self._resources.append(resource)

    def get(self, uri: str) -> Optional[MCPResource]:
        """Get resource handler for the given URI."""
        # Try pattern matching in registration order
        for resource in self._resources:
            if resource.matches(uri):
                return resource

        return None

    def list_resources(self) -> List[dict]:
        """List all registered resources."""
        return [
            {
                "uri": resource.uri_pattern,
                "name": resource.name,
                "description": resource.description,
                "mimeType": "application/json",
            }
            for resource in self._resources
        ]

    async def read_resource(self, uri: str) -> ResourceResponse:
        """Read a resource by URI with parameter extraction."""
        resource = self.get(uri)
        if not resource:
            raise ValueError(f"No resource handler for URI: {uri}")

        # Extract parameters from URI
        params = resource.extract_params(uri)
        return await resource.read(uri, params)


# Global registry instance
_registry = ResourceRegistry()


def get_registry() -> ResourceRegistry:
    """Get the global resource registry."""
    return _registry
