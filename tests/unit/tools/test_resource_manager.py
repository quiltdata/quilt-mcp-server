"""Tests for ResourceManager class."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from quilt_mcp.tools.resource_access import (
    ResourceManager,
    ResourceDefinition,
    RESOURCE_REGISTRY,
)


class TestResourceManagerInit:
    """Test ResourceManager initialization."""

    def test_init_with_registry(self):
        """Test ResourceManager initializes with registry."""
        manager = ResourceManager(RESOURCE_REGISTRY)

        assert manager is not None
        assert manager._registry == RESOURCE_REGISTRY

    def test_static_uris_filtered(self):
        """Test static URIs are pre-filtered for fast lookup."""
        manager = ResourceManager(RESOURCE_REGISTRY)

        # Should contain 4 static resources
        assert len(manager._static_uris) == 4
        assert "auth://status" in manager._static_uris
        assert "admin://users" in manager._static_uris

        # Should NOT contain template resource
        assert "metadata://templates/{template}" not in manager._static_uris


class TestResourceManagerStaticLookup:
    """Test static URI lookup."""

    @pytest.fixture
    def manager(self):
        """Create ResourceManager instance."""
        return ResourceManager(RESOURCE_REGISTRY)

    @pytest.mark.asyncio
    async def test_static_uri_lookup_success(self, manager):
        """Test successful static URI lookup."""
        result = await manager.get_resource("auth://status")

        assert "uri" in result
        assert result["uri"] == "auth://status"
        assert "resource_name" in result
        assert "data" in result
        assert "mime_type" in result

    @pytest.mark.asyncio
    async def test_invalid_uri_format_raises_value_error(self, manager):
        """Test invalid URI format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid URI format"):
            await manager.get_resource("invalid-no-scheme")

    @pytest.mark.asyncio
    async def test_unknown_uri_raises_key_error(self, manager):
        """Test unknown URI raises KeyError."""
        with pytest.raises(KeyError, match="not recognized"):
            await manager.get_resource("unknown://resource")

    @pytest.mark.asyncio
    async def test_template_uri_raises_key_error_phase1(self, manager):
        """Test template URI raises KeyError in Phase 1."""
        # Phase 1: Template URIs not supported yet
        with pytest.raises(KeyError):
            await manager.get_resource("metadata://templates/{template}")


class TestResourceManagerServiceInvocation:
    """Test service function invocation."""

    @pytest.mark.asyncio
    async def test_sync_service_function_invocation(self):
        """Test sync service function called via asyncio.to_thread."""
        def mock_sync_service():
            return {"test": "data"}

        registry = {
            "test://sync": {
                "uri": "test://sync",
                "name": "Test",
                "description": "Test",
                "service_function": mock_sync_service,
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},
            }
        }

        manager = ResourceManager(registry)
        result = await manager.get_resource("test://sync")

        assert result["data"]["test"] == "data"

    @pytest.mark.asyncio
    async def test_async_service_function_invocation(self):
        """Test async service function called directly."""
        async def mock_async_service():
            return {"async": "data"}

        registry = {
            "test://async": {
                "uri": "test://async",
                "name": "Test",
                "description": "Test",
                "service_function": mock_async_service,
                "is_async": True,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},
            }
        }

        manager = ResourceManager(registry)
        result = await manager.get_resource("test://async")

        assert result["data"]["async"] == "data"

    @pytest.mark.asyncio
    async def test_pydantic_model_deserialization(self):
        """Test Pydantic model result is deserialized to dict."""
        from pydantic import BaseModel

        class MockResponse(BaseModel):
            field1: str
            field2: int

        def mock_service():
            return MockResponse(field1="value", field2=42)

        registry = {
            "test://pydantic": {
                "uri": "test://pydantic",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},
            }
        }

        manager = ResourceManager(registry)
        result = await manager.get_resource("test://pydantic")

        # Should be deserialized to dict
        assert isinstance(result["data"], dict)
        assert result["data"]["field1"] == "value"
        assert result["data"]["field2"] == 42

    @pytest.mark.asyncio
    async def test_dict_result_pass_through(self):
        """Test dict result passes through unchanged."""
        def mock_service():
            return {"key": "value"}

        registry = {
            "test://dict": {
                "uri": "test://dict",
                "name": "Test",
                "description": "Test",
                "service_function": mock_service,
                "is_async": False,
                "is_template": False,
                "template_variables": [],
                "requires_admin": False,
                "category": "test",
                "parameter_mapping": {},
            }
        }

        manager = ResourceManager(registry)
        result = await manager.get_resource("test://dict")

        assert result["data"] == {"key": "value"}


class TestResourceManagerDiscoveryMode:
    """Test discovery mode functionality."""

    @pytest.fixture
    def manager(self):
        """Create ResourceManager instance."""
        return ResourceManager(RESOURCE_REGISTRY)

    @pytest.mark.asyncio
    async def test_discovery_mode_empty_string(self, manager):
        """Test empty string triggers discovery mode."""
        result = await manager.get_discovery_data()

        assert isinstance(result, dict)
        assert "auth" in result
        assert "admin" in result
        assert "permissions" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_discovery_mode_none(self, manager):
        """Test None triggers discovery mode."""
        result = await manager.get_resource(None)

        # Should return discovery data structure
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_discovery_data_structure(self, manager):
        """Test discovery mode returns correct data structure."""
        result = await manager.get_discovery_data()

        # Check auth category
        auth_resources = result["auth"]
        assert len(auth_resources) == 2
        assert all(hasattr(r, "uri") for r in auth_resources)
        assert all(hasattr(r, "name") for r in auth_resources)
        assert all(r.category == "auth" for r in auth_resources)

    @pytest.mark.asyncio
    async def test_discovery_includes_template_resources(self, manager):
        """Test discovery mode includes template resources."""
        result = await manager.get_discovery_data()

        metadata_resources = result["metadata"]
        assert len(metadata_resources) == 1

        template_resource = metadata_resources[0]
        assert template_resource.is_template is True
        assert "template" in template_resource.template_variables

    @pytest.mark.asyncio
    async def test_discovery_resources_sorted_by_uri(self, manager):
        """Test resources within category are sorted by URI."""
        result = await manager.get_discovery_data()

        auth_uris = [r.uri for r in result["auth"]]
        assert auth_uris == sorted(auth_uris)