"""Unit tests for base resource classes."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Optional

from quilt_mcp.resources.base import (
    ResourceResponse,
    MCPResource,
    ResourceRegistry,
    get_registry,
)


class TestResourceResponse:
    """Test ResourceResponse class."""

    def test_to_dict_json(self):
        """Test to_dict with JSON content."""
        response = ResourceResponse(
            uri="test://resource",
            mime_type="application/json",
            content={"key": "value"},
        )

        result = response.to_dict()

        assert result["uri"] == "test://resource"
        assert result["mimeType"] == "application/json"
        assert json.loads(result["text"]) == {"key": "value"}

    def test_to_dict_text(self):
        """Test to_dict with text content."""
        response = ResourceResponse(
            uri="test://resource",
            mime_type="text/plain",
            content="Hello, world!",
        )

        result = response.to_dict()

        assert result["uri"] == "test://resource"
        assert result["mimeType"] == "text/plain"
        assert result["text"] == "Hello, world!"

    def test_serialize_content_json(self):
        """Test JSON serialization."""
        response = ResourceResponse(
            uri="test://resource",
            content={"nested": {"data": [1, 2, 3]}},
        )

        text = response._serialize_content()
        assert json.loads(text) == {"nested": {"data": [1, 2, 3]}}

    def test_serialize_content_non_json(self):
        """Test non-JSON serialization."""
        response = ResourceResponse(
            uri="test://resource",
            mime_type="text/plain",
            content=12345,
        )

        text = response._serialize_content()
        assert text == "12345"


class TestMCPResource:
    """Test MCPResource base class."""

    @pytest.fixture
    def mock_resource(self):
        """Create a mock resource for testing."""

        class MockResource(MCPResource):
            @property
            def uri_scheme(self) -> str:
                return "test"

            @property
            def uri_pattern(self) -> str:
                return "test://items"

            @property
            def name(self) -> str:
                return "Test Resource"

            @property
            def description(self) -> str:
                return "A test resource"

            async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
                return ResourceResponse(uri=uri, content={"test": "data"})

        return MockResource()

    @pytest.fixture
    def parameterized_resource(self):
        """Create a parameterized mock resource for testing."""

        class ParamResource(MCPResource):
            @property
            def uri_scheme(self) -> str:
                return "test"

            @property
            def uri_pattern(self) -> str:
                return "test://items/{id}"

            @property
            def name(self) -> str:
                return "Test Param Resource"

            @property
            def description(self) -> str:
                return "A parameterized test resource"

            async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
                return ResourceResponse(uri=uri, content={"id": params.get("id") if params else None})

        return ParamResource()

    @pytest.mark.anyio
    async def test_read_with_logging_enabled(self, mock_resource):
        """Test read method with logging enabled."""
        with patch("quilt_mcp.resources.base.resource_config") as mock_config:
            mock_config.RESOURCE_ACCESS_LOGGING = True

            with patch("quilt_mcp.resources.base.logger") as mock_logger:
                response = await mock_resource.read("test://items")

                assert response.uri == "test://items"
                assert response.content == {"test": "data"}
                mock_logger.info.assert_called_once()
                assert "test://items" in mock_logger.info.call_args[0][0]

    @pytest.mark.anyio
    async def test_read_with_logging_disabled(self, mock_resource):
        """Test read method with logging disabled."""
        with patch("quilt_mcp.resources.base.resource_config") as mock_config:
            mock_config.RESOURCE_ACCESS_LOGGING = False

            with patch("quilt_mcp.resources.base.logger") as mock_logger:
                response = await mock_resource.read("test://items")

                assert response.uri == "test://items"
                mock_logger.info.assert_not_called()

    @pytest.mark.anyio
    async def test_read_with_error(self, mock_resource):
        """Test read method handles errors correctly."""
        with patch.object(mock_resource, "_read_impl", side_effect=ValueError("Test error")):
            with patch("quilt_mcp.resources.base.logger") as mock_logger:
                with pytest.raises(ValueError, match="Test error"):
                    await mock_resource.read("test://items")

                mock_logger.error.assert_called_once()
                assert "failed" in mock_logger.error.call_args[0][0].lower()

    def test_matches_exact(self, mock_resource):
        """Test matches method with exact URI."""
        assert mock_resource.matches("test://items") is True
        assert mock_resource.matches("test://other") is False
        assert mock_resource.matches("other://items") is False

    def test_matches_parameterized(self, parameterized_resource):
        """Test matches method with parameterized URI."""
        assert parameterized_resource.matches("test://items/123") is True
        assert parameterized_resource.matches("test://items/abc") is True
        assert parameterized_resource.matches("test://items") is False
        assert parameterized_resource.matches("test://items/123/extra") is False

    def test_extract_params_exact(self, mock_resource):
        """Test extract_params with exact URI."""
        params = mock_resource.extract_params("test://items")
        assert params == {}

    def test_extract_params_parameterized(self, parameterized_resource):
        """Test extract_params with parameterized URI."""
        params = parameterized_resource.extract_params("test://items/123")
        assert params == {"id": "123"}

    def test_extract_params_no_match(self, mock_resource):
        """Test extract_params with non-matching URI."""
        params = mock_resource.extract_params("test://other")
        assert params == {}

    def test_template_to_regex_simple(self):
        """Test URI template to regex conversion."""
        pattern = MCPResource._template_to_regex("test://items")
        assert pattern == "^test://items$"

    def test_template_to_regex_parameterized(self):
        """Test URI template to regex with parameters."""
        pattern = MCPResource._template_to_regex("test://items/{id}")
        assert "(?P<id>[^/]+)" in pattern

    def test_template_to_regex_multiple_params(self):
        """Test URI template with multiple parameters."""
        pattern = MCPResource._template_to_regex("test://db/{database}/tables/{table}")
        assert "(?P<database>[^/]+)" in pattern
        assert "(?P<table>[^/]+)" in pattern


class TestResourceRegistry:
    """Test ResourceRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        return ResourceRegistry()

    @pytest.fixture
    def mock_resource_class(self):
        """Create a mock resource class for testing."""

        class MockResource(MCPResource):
            def __init__(self, pattern: str, name: str):
                self._pattern = pattern
                self._name = name

            @property
            def uri_scheme(self) -> str:
                return "test"

            @property
            def uri_pattern(self) -> str:
                return self._pattern

            @property
            def name(self) -> str:
                return self._name

            @property
            def description(self) -> str:
                return f"Description for {self._name}"

            async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
                return ResourceResponse(uri=uri, content={"name": self._name, "params": params})

        return MockResource

    def test_register_and_get(self, registry, mock_resource_class):
        """Test registering and retrieving a resource."""
        resource = mock_resource_class("test://items", "Items")
        registry.register(resource)

        retrieved = registry.get("test://items")
        assert retrieved is resource

    def test_get_nonexistent(self, registry):
        """Test getting a non-existent resource."""
        retrieved = registry.get("test://nonexistent")
        assert retrieved is None

    def test_pattern_matching_order(self, registry, mock_resource_class):
        """Test that pattern matching respects registration order."""
        # More specific pattern registered first
        specific = mock_resource_class("test://items/special", "Special")
        general = mock_resource_class("test://items/{id}", "General")

        registry.register(specific)
        registry.register(general)

        # Specific match
        retrieved = registry.get("test://items/special")
        assert retrieved.name == "Special"

        # General match
        retrieved = registry.get("test://items/123")
        assert retrieved.name == "General"

    def test_pattern_matching_reverse_order(self, registry, mock_resource_class):
        """Test that general patterns registered first still work."""
        general = mock_resource_class("test://items/{id}", "General")
        specific = mock_resource_class("test://items/special", "Special")

        # Register general first (this is not ideal but should still work)
        registry.register(general)
        registry.register(specific)

        # Specific should match first because it was registered second
        retrieved = registry.get("test://items/special")
        # Note: This will actually match the general pattern first
        # This demonstrates why registration order matters
        assert retrieved.name == "General"

    def test_list_resources(self, registry, mock_resource_class):
        """Test listing all registered resources."""
        resource1 = mock_resource_class("test://items", "Items")
        resource2 = mock_resource_class("test://users", "Users")

        registry.register(resource1)
        registry.register(resource2)

        resources = registry.list_resources()

        assert len(resources) == 2
        assert resources[0]["uri"] == "test://items"
        assert resources[0]["name"] == "Items"
        assert resources[1]["uri"] == "test://users"
        assert resources[1]["name"] == "Users"

    @pytest.mark.anyio
    async def test_read_resource_success(self, registry, mock_resource_class):
        """Test reading a resource through the registry."""
        resource = mock_resource_class("test://items/{id}", "Items")
        registry.register(resource)

        response = await registry.read_resource("test://items/123")

        assert response.uri == "test://items/123"
        assert response.content["name"] == "Items"
        assert response.content["params"]["id"] == "123"

    @pytest.mark.anyio
    async def test_read_resource_not_found(self, registry):
        """Test reading a non-existent resource raises error."""
        with pytest.raises(ValueError, match="No resource handler"):
            await registry.read_resource("test://nonexistent")


class TestGlobalRegistry:
    """Test global registry singleton."""

    def test_get_registry_singleton(self):
        """Test that get_registry returns the same instance."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_get_registry_returns_registry(self):
        """Test that get_registry returns a ResourceRegistry."""
        registry = get_registry()
        assert isinstance(registry, ResourceRegistry)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_resource_response_empty_content(self):
        """Test ResourceResponse with empty content."""
        response = ResourceResponse(uri="test://empty", content={})
        result = response.to_dict()
        assert json.loads(result["text"]) == {}

    def test_resource_response_null_content(self):
        """Test ResourceResponse with None content."""
        response = ResourceResponse(uri="test://null", content=None)
        result = response.to_dict()
        # JSON serialization converts None to "null"
        assert result["text"] == "null"

    def test_template_to_regex_special_characters(self):
        """Test template with special regex characters."""
        # URI with dots, which are special in regex
        pattern = MCPResource._template_to_regex("test://items.json")
        # Should properly escape the dot
        assert pattern == "^test://items\\.json$"

    def test_extract_params_special_characters(self):
        """Test parameter extraction with special characters."""

        class SpecialResource(MCPResource):
            @property
            def uri_scheme(self) -> str:
                return "test"

            @property
            def uri_pattern(self) -> str:
                return "test://items/{id}"

            @property
            def name(self) -> str:
                return "Test"

            @property
            def description(self) -> str:
                return "Test"

            async def _read_impl(self, uri: str, params: Optional[Dict[str, str]] = None) -> ResourceResponse:
                return ResourceResponse(uri=uri, content={})

        resource = SpecialResource()
        params = resource.extract_params("test://items/abc-123_def")
        assert params == {"id": "abc-123_def"}
