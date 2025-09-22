"""Base MCP Resource Framework.

This module provides the base classes and standardized response format for
MCP resources that consolidate list-type functions.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List


class ResourceResponse:
    """Standardized response format for MCP resources."""

    def __init__(self, resource_uri: str, items: List[Any], metadata: Dict[str, Any] = None):
        """Initialize ResourceResponse.

        Args:
            resource_uri: URI identifying the resource
            items: List of items returned by the resource
            metadata: Optional additional metadata
        """
        self.resource_uri = resource_uri
        self.resource_type = "list"
        self.items = items
        self.metadata = metadata or {}
        self.capabilities = self._get_default_capabilities()

    def _get_default_capabilities(self) -> Dict[str, Any]:
        """Get default capabilities for resources."""
        return {
            "filterable": False,
            "sortable": False,
            "paginatable": False
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format suitable for MCP responses."""
        return {
            "resource_uri": self.resource_uri,
            "resource_type": self.resource_type,
            "items": self.items,
            "metadata": {
                "total_count": len(self.items),
                "has_more": False,
                "continuation_token": None,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                **self.metadata
            },
            "capabilities": self.capabilities
        }


class MCPResource(ABC):
    """Abstract base class for MCP resources."""

    def __init__(self, uri: str):
        """Initialize MCPResource.

        Args:
            uri: URI pattern for this resource
        """
        self.uri = uri

    @abstractmethod
    async def list_items(self, **params) -> Dict[str, Any]:
        """List items for this resource.

        Args:
            **params: Resource-specific parameters

        Returns:
            Resource-specific response format
        """
        pass

    def get_uri_pattern(self) -> str:
        """Get the URI pattern for this resource."""
        return self.uri

    def get_capabilities(self) -> Dict[str, Any]:
        """Get capabilities for this resource."""
        return {
            "filterable": False,
            "sortable": False,
            "paginatable": False
        }

    async def to_mcp_response(self, **params) -> Dict[str, Any]:
        """Convert resource data to standardized MCP response format.

        Args:
            **params: Resource-specific parameters

        Returns:
            Standardized MCP resource response
        """
        # Get raw resource data
        raw_data = await self.list_items(**params)

        # Extract items from the raw data based on resource type
        items = self._extract_items(raw_data)

        # Create standardized response
        response = ResourceResponse(self.uri, items, self._extract_metadata(raw_data))
        return response.to_dict()

    def _extract_items(self, raw_data: Dict[str, Any]) -> List[Any]:
        """Extract items list from raw resource data.

        Override in subclasses for resource-specific extraction logic.
        """
        # Default implementation looks for common item list keys
        for key in ["items", "users", "roles", "buckets", "workflows", "templates"]:
            if key in raw_data:
                return raw_data[key]
        return []

    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from raw resource data.

        Override in subclasses for resource-specific metadata extraction.
        """
        metadata = {}

        # Extract common metadata fields
        if "count" in raw_data:
            metadata["original_count"] = raw_data["count"]
        if "status" in raw_data:
            metadata["status"] = raw_data["status"]
        if "message" in raw_data:
            metadata["message"] = raw_data["message"]

        return metadata


class ResourceRegistry:
    """Registry for MCP resources with discovery and routing capabilities."""

    def __init__(self):
        """Initialize ResourceRegistry."""
        self._resources: Dict[str, MCPResource] = {}

    def register(self, uri_pattern: str, resource: MCPResource) -> None:
        """Register a resource with the registry.

        Args:
            uri_pattern: URI pattern for the resource
            resource: MCPResource instance
        """
        self._resources[uri_pattern] = resource

    def has_resource(self, uri_pattern: str) -> bool:
        """Check if a resource is registered.

        Args:
            uri_pattern: URI pattern to check

        Returns:
            True if resource is registered
        """
        return uri_pattern in self._resources

    def get_resource(self, uri_pattern: str) -> MCPResource:
        """Get a registered resource.

        Args:
            uri_pattern: URI pattern for the resource

        Returns:
            MCPResource instance

        Raises:
            ValueError: If resource is not found
        """
        if uri_pattern not in self._resources:
            raise ValueError(f"Resource not found: {uri_pattern}")
        return self._resources[uri_pattern]

    def list_resources(self) -> List[str]:
        """List all registered resource URI patterns.

        Returns:
            List of URI patterns
        """
        return list(self._resources.keys())

    async def get_resource_data(self, uri_pattern: str, **params) -> Dict[str, Any]:
        """Get standardized resource data for a URI pattern.

        Args:
            uri_pattern: URI pattern for the resource
            **params: Resource-specific parameters

        Returns:
            Standardized MCP resource response

        Raises:
            ValueError: If resource is not found
        """
        resource = self.get_resource(uri_pattern)
        return await resource.to_mcp_response(**params)