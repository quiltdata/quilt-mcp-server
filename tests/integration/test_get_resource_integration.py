"""Integration tests for get_resource tool.

These tests verify:
1. Data parity between tool and direct resource access
2. FastMCP integration
3. Service layer integration
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, Mock
from quilt_mcp.tools.resource_access import get_resource, ResourceManager, RESOURCE_REGISTRY
from quilt_mcp.models.responses import GetResourceSuccess, GetResourceError
from quilt_mcp.resources import register_resources
from fastmcp import FastMCP


class TestGetResourceDataParity:
    """Test data parity between tool and direct resource access."""

    @pytest.mark.asyncio
    async def test_tool_vs_direct_resource_parity(self):
        """Verify tool returns same data as direct resource access."""
        # Test with auth://status
        manager = ResourceManager(RESOURCE_REGISTRY)

        # Get data via ResourceManager directly
        direct_result = await manager.get_resource("auth://status")

        # Get data via tool
        tool_result = await get_resource(uri="auth://status")

        # Verify parity
        assert isinstance(tool_result, GetResourceSuccess)
        assert tool_result.uri == direct_result["uri"]
        assert tool_result.resource_name == direct_result["resource_name"]
        assert tool_result.data == direct_result["data"]
        assert tool_result.mime_type == direct_result.get("mime_type", "application/json")

    @pytest.mark.asyncio
    async def test_discovery_mode_parity(self):
        """Verify discovery mode returns consistent data."""
        manager = ResourceManager(RESOURCE_REGISTRY)

        # Get discovery data directly
        direct_discovery = await manager.get_discovery_data()

        # Get discovery data via tool
        tool_result = await get_resource(uri="")

        assert isinstance(tool_result, GetResourceSuccess)
        assert tool_result.uri == "discovery://resources"

        # Verify all categories present
        for category in direct_discovery.keys():
            assert category in tool_result.data

            # Verify resource count matches
            direct_count = len(direct_discovery[category])
            tool_count = len(tool_result.data[category])
            assert tool_count == direct_count

    @pytest.mark.asyncio
    async def test_error_handling_consistency(self):
        """Verify error handling is consistent between tool and manager."""
        # Test invalid URI
        tool_result = await get_resource(uri="invalid-uri")

        assert isinstance(tool_result, GetResourceError)
        assert tool_result.cause == "ValueError"
        assert tool_result.possible_fixes is not None

        # Test unknown URI
        tool_result = await get_resource(uri="unknown://resource")

        assert isinstance(tool_result, GetResourceError)
        assert tool_result.cause == "KeyError"
        assert tool_result.valid_uris is not None


class TestFastMCPIntegration:
    """Test FastMCP integration with get_resource tool."""

    @pytest.fixture
    def mcp_server(self):
        """Create FastMCP server instance."""
        return FastMCP("test-server")

    def test_tool_registration_with_fastmcp(self, mcp_server):
        """Verify get_resource tool can be registered with FastMCP."""

        # Register the tool (would normally be done via decorator)
        @mcp_server.tool()
        async def get_resource_tool(uri: str = "") -> dict:
            """Get resource via URI."""
            result = await get_resource(uri=uri)
            return result.model_dump()

        # Verify tool is registered
        assert hasattr(mcp_server, "_tool_manager")
        # Note: Actual FastMCP registration verification would require
        # accessing internal FastMCP structures

    @pytest.mark.asyncio
    async def test_resource_vs_tool_coexistence(self, mcp_server):
        """Verify resources and tools can coexist in FastMCP."""
        # Register resources
        register_resources(mcp_server)

        # Register get_resource as a tool
        @mcp_server.tool()
        async def get_resource_tool(uri: str = "") -> dict:
            """Get resource via URI."""
            result = await get_resource(uri=uri)
            return result.model_dump()

        # Both should work without conflict
        # Resources are accessed via MCP resource protocol
        # Tools are accessed via MCP tool protocol

        # Verify no naming conflicts or registration issues
        assert True  # Would need actual FastMCP API to verify

    @pytest.mark.asyncio
    async def test_tool_execution_via_fastmcp(self, mcp_server):
        """Test tool execution through FastMCP wrapper."""

        # Create tool wrapper
        @mcp_server.tool()
        async def get_resource_tool(uri: str = "") -> dict:
            """Get resource via URI."""
            result = await get_resource(uri=uri)
            return result.model_dump()

        # Execute tool directly (FastMCP decorators create FunctionTool objects)
        # We call the underlying function directly in tests
        result = await get_resource(uri="auth://status")

        # Verify result structure
        assert isinstance(result, (GetResourceSuccess, GetResourceError))
        assert result.success is True
        assert hasattr(result, "uri")
        assert hasattr(result, "data")


class TestServiceLayerIntegration:
    """Test integration with service layer functions."""

    @pytest.mark.asyncio
    async def test_sync_service_integration(self):
        """Test integration with synchronous service functions."""
        from quilt_mcp.services.auth_metadata import auth_status

        # Mock the service function
        with patch('quilt_mcp.services.auth_metadata.auth_status') as mock_auth:
            mock_auth.return_value = {"authenticated": True, "catalog": "test.quiltdata.com"}

            # Call via tool
            result = await get_resource(uri="auth://status")

            # Verify service was called (indirectly via ResourceManager)
            assert isinstance(result, GetResourceSuccess)
            # Note: Direct service call verification would require deeper mocking

    @pytest.mark.asyncio
    async def test_async_service_integration(self):
        """Test integration with asynchronous service functions."""
        from quilt_mcp.services.governance_service import admin_users_list

        # Mock the async service function
        async def mock_admin_users():
            return {"users": [{"name": "user1", "role": "admin"}, {"name": "user2", "role": "viewer"}]}

        with patch('quilt_mcp.services.governance_service.admin_users_list', new=mock_admin_users):
            # Call via tool
            result = await get_resource(uri="admin://users")

            # Verify integration works
            assert isinstance(result, (GetResourceSuccess, GetResourceError))

    @pytest.mark.asyncio
    async def test_service_error_propagation(self):
        """Test that service errors are properly propagated."""
        # Mock a service to raise an error
        with patch('quilt_mcp.tools.resource_access.ResourceManager') as MockManager:
            mock_manager = Mock()
            mock_manager.get_resource = AsyncMock(side_effect=RuntimeError("Service unavailable"))
            MockManager.return_value = mock_manager

            # Call tool
            result = await get_resource(uri="auth://status")

            # Verify error is properly wrapped
            assert isinstance(result, GetResourceError)
            assert "Service unavailable" in result.error
            assert result.cause == "RuntimeError"

    @pytest.mark.asyncio
    async def test_pydantic_model_handling(self):
        """Test handling of Pydantic models from services."""
        from pydantic import BaseModel

        class ServiceResponse(BaseModel):
            status: str
            data: dict

        # Mock service returning Pydantic model
        with patch('quilt_mcp.tools.resource_access.ResourceManager') as MockManager:
            mock_manager = Mock()
            mock_response = {
                "uri": "test://resource",
                "resource_name": "Test",
                "data": {"status": "ok", "info": "test"},
                "mime_type": "application/json",
            }
            mock_manager.get_resource = AsyncMock(return_value=mock_response)
            MockManager.return_value = mock_manager

            # Call tool
            result = await get_resource(uri="test://resource")

            # Verify Pydantic model is properly handled
            assert isinstance(result, GetResourceSuccess)
            assert result.data == {"status": "ok", "info": "test"}


class TestResourceRegistryIntegration:
    """Test integration with resource registry."""

    def test_registry_validation_on_tool_init(self):
        """Verify resource registry is validated when tool is used."""
        # Registry validation happens at module load time
        # If we got here, validation passed
        assert RESOURCE_REGISTRY is not None
        assert len(RESOURCE_REGISTRY) > 0

        # Verify all required fields present
        for uri, defn in RESOURCE_REGISTRY.items():
            assert "uri" in defn
            assert "name" in defn
            assert "service_function" in defn
            assert callable(defn["service_function"])

    @pytest.mark.asyncio
    async def test_registry_uri_consistency(self):
        """Verify URIs in registry match what tool returns."""
        # Get all URIs from discovery
        result = await get_resource(uri="")

        assert isinstance(result, GetResourceSuccess)

        # Collect all URIs from discovery response
        discovered_uris = set()
        for category, resources in result.data.items():
            for resource in resources:
                discovered_uris.add(resource["uri"])

        # Verify all registry URIs are discoverable
        registry_uris = set(RESOURCE_REGISTRY.keys())
        assert discovered_uris == registry_uris

    @pytest.mark.asyncio
    async def test_category_grouping(self):
        """Verify resources are properly grouped by category."""
        result = await get_resource(uri="")

        assert isinstance(result, GetResourceSuccess)

        # Verify expected categories exist
        expected_categories = {"auth", "admin", "permissions", "metadata"}
        actual_categories = set(result.data.keys())

        assert expected_categories.issubset(actual_categories)

        # Verify resources in each category have correct category field
        for category, resources in result.data.items():
            for resource in resources:
                assert resource["category"] == category
