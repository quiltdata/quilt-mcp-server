"""Tests for get_resource tool function."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from quilt_mcp.models.responses import (
    GetResourceSuccess,
    GetResourceError,
    ResourceMetadata,
)
from datetime import datetime


class TestGetResourceTool:
    """Test get_resource tool wrapper function."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock ResourceManager."""
        manager = Mock()
        manager.get_resource = AsyncMock()
        manager.get_discovery_data = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_get_resource_static_uri_success(self, mock_manager):
        """Test successful static URI resource retrieval."""
        from quilt_mcp.tools.resource_access import get_resource

        # Setup mock response
        mock_data = {
            "uri": "auth://status",
            "resource_name": "Auth Status",
            "data": {"authenticated": True, "catalog": "demo.quiltdata.com"},
            "mime_type": "application/json",
        }
        mock_manager.get_resource.return_value = mock_data

        # Execute with mocked manager
        with patch('quilt_mcp.tools.resource_access.ResourceManager', return_value=mock_manager):
            result = await get_resource(uri="auth://status")

        # Verify response structure
        assert isinstance(result, GetResourceSuccess)
        assert result.success is True
        assert result.uri == "auth://status"
        assert result.resource_name == "Auth Status"
        assert result.data == {"authenticated": True, "catalog": "demo.quiltdata.com"}
        assert result.mime_type == "application/json"
        assert isinstance(result.timestamp, datetime)

        # Verify manager was called correctly
        mock_manager.get_resource.assert_called_once_with("auth://status")

    @pytest.mark.asyncio
    async def test_get_resource_discovery_mode(self, mock_manager):
        """Test discovery mode with empty URI."""
        from quilt_mcp.tools.resource_access import get_resource

        # Setup mock discovery data
        mock_discovery = {
            "auth": [
                ResourceMetadata(
                    uri="auth://status",
                    name="Auth Status",
                    description="Check authentication status",
                    is_template=False,
                    template_variables=[],
                    requires_admin=False,
                    category="auth",
                )
            ],
            "admin": [
                ResourceMetadata(
                    uri="admin://users",
                    name="Admin Users List",
                    description="List all users",
                    is_template=False,
                    template_variables=[],
                    requires_admin=True,
                    category="admin",
                )
            ],
        }
        mock_manager.get_discovery_data.return_value = mock_discovery

        # Execute with empty string (discovery mode)
        with patch('quilt_mcp.tools.resource_access.ResourceManager', return_value=mock_manager):
            result = await get_resource(uri="")

        # Verify response is discovery data
        assert isinstance(result, GetResourceSuccess)
        assert result.success is True
        assert result.uri == "discovery://resources"
        assert result.resource_name == "Available Resources"
        assert "auth" in result.data
        assert "admin" in result.data

        # Verify discovery data structure
        auth_resources = result.data["auth"]
        assert len(auth_resources) == 1
        assert auth_resources[0]["uri"] == "auth://status"

        # Verify manager was called correctly
        mock_manager.get_discovery_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_resource_none_uri_discovery(self, mock_manager):
        """Test discovery mode with None URI."""
        from quilt_mcp.tools.resource_access import get_resource

        # Setup mock discovery data
        mock_discovery = {"auth": []}
        mock_manager.get_discovery_data.return_value = mock_discovery

        # Execute with None (discovery mode)
        with patch('quilt_mcp.tools.resource_access.ResourceManager', return_value=mock_manager):
            result = await get_resource(uri=None)

        # Verify response is discovery data
        assert isinstance(result, GetResourceSuccess)
        assert result.uri == "discovery://resources"

        # Verify manager was called correctly
        mock_manager.get_discovery_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_resource_invalid_uri_format(self, mock_manager):
        """Test error handling for invalid URI format."""
        from quilt_mcp.tools.resource_access import get_resource

        # Setup mock to raise ValueError
        mock_manager.get_resource.side_effect = ValueError("Invalid URI format: no-scheme")

        # Execute with invalid URI
        with patch('quilt_mcp.tools.resource_access.ResourceManager', return_value=mock_manager):
            result = await get_resource(uri="no-scheme")

        # Verify error response
        assert isinstance(result, GetResourceError)
        assert result.success is False
        assert "Invalid URI format" in result.error
        assert result.cause == "ValueError"
        assert result.possible_fixes is not None
        assert len(result.possible_fixes) > 0

    @pytest.mark.asyncio
    async def test_get_resource_unknown_uri(self, mock_manager):
        """Test error handling for unknown URI."""
        from quilt_mcp.tools.resource_access import get_resource

        # Setup mock to raise KeyError
        mock_manager.get_resource.side_effect = KeyError("Resource URI not recognized: unknown://test")

        # Execute with unknown URI
        with patch('quilt_mcp.tools.resource_access.ResourceManager', return_value=mock_manager):
            result = await get_resource(uri="unknown://test")

        # Verify error response
        assert isinstance(result, GetResourceError)
        assert result.success is False
        assert "not recognized" in result.error
        assert result.cause == "KeyError"
        assert result.valid_uris is not None  # Should list available URIs

    @pytest.mark.asyncio
    async def test_get_resource_service_error(self, mock_manager):
        """Test error handling for service function failure."""
        from quilt_mcp.tools.resource_access import get_resource

        # Setup mock to raise RuntimeError
        mock_manager.get_resource.side_effect = RuntimeError("Service unavailable")

        # Execute
        with patch('quilt_mcp.tools.resource_access.ResourceManager', return_value=mock_manager):
            result = await get_resource(uri="auth://status")

        # Verify error response
        assert isinstance(result, GetResourceError)
        assert result.success is False
        assert "Service unavailable" in result.error
        assert result.cause == "RuntimeError"

    @pytest.mark.asyncio
    async def test_get_resource_admin_unauthorized(self, mock_manager):
        """Test error handling for admin resource without privileges."""
        from quilt_mcp.tools.resource_access import get_resource

        # Setup mock to raise authorization error
        error_msg = "Unauthorized: Admin privileges required"
        mock_manager.get_resource.side_effect = RuntimeError(error_msg)

        # Execute admin resource
        with patch('quilt_mcp.tools.resource_access.ResourceManager', return_value=mock_manager):
            result = await get_resource(uri="admin://users")

        # Verify error response
        assert isinstance(result, GetResourceError)
        assert "Unauthorized" in result.error
        assert result.suggested_actions is not None
        assert any("admin" in action.lower() for action in result.suggested_actions)

    @pytest.mark.asyncio
    async def test_get_resource_with_template_phase1(self, mock_manager):
        """Test template URI handling in Phase 1 (should fail)."""
        from quilt_mcp.tools.resource_access import get_resource

        # Setup mock to raise KeyError for template
        mock_manager.get_resource.side_effect = KeyError("Template URIs not supported in Phase 1")

        # Execute template URI
        with patch('quilt_mcp.tools.resource_access.ResourceManager', return_value=mock_manager):
            result = await get_resource(uri="metadata://templates/standard")

        # Verify error response
        assert isinstance(result, GetResourceError)
        assert result.success is False
        assert "not supported" in result.error or "not recognized" in result.error

    @pytest.mark.asyncio
    async def test_get_resource_mime_type_preservation(self, mock_manager):
        """Test MIME type is preserved from service response."""
        from quilt_mcp.tools.resource_access import get_resource

        # Setup mock with custom MIME type
        mock_data = {
            "uri": "test://resource",
            "resource_name": "Test Resource",
            "data": {"test": "data"},
            "mime_type": "text/plain",
        }
        mock_manager.get_resource.return_value = mock_data

        # Execute
        with patch('quilt_mcp.tools.resource_access.ResourceManager', return_value=mock_manager):
            result = await get_resource(uri="test://resource")

        # Verify MIME type preserved
        assert isinstance(result, GetResourceSuccess)
        assert result.mime_type == "text/plain"

    @pytest.mark.asyncio
    async def test_get_resource_unexpected_exception(self, mock_manager):
        """Test handling of unexpected exceptions."""
        from quilt_mcp.tools.resource_access import get_resource

        # Setup mock to raise unexpected exception
        mock_manager.get_resource.side_effect = Exception("Unexpected error")

        # Execute
        with patch('quilt_mcp.tools.resource_access.ResourceManager', return_value=mock_manager):
            result = await get_resource(uri="auth://status")

        # Verify generic error response
        assert isinstance(result, GetResourceError)
        assert result.success is False
        assert "Unexpected error" in result.error
        assert result.cause == "Exception"

    @pytest.mark.asyncio
    async def test_get_resource_discovery_serialization(self, mock_manager):
        """Test discovery data is properly serialized."""
        from quilt_mcp.tools.resource_access import get_resource

        # Setup mock with ResourceMetadata objects
        metadata = ResourceMetadata(
            uri="test://resource",
            name="Test",
            description="Test resource",
            is_template=True,
            template_variables=["param"],
            requires_admin=False,
            category="test",
        )
        mock_discovery = {"test": [metadata]}
        mock_manager.get_discovery_data.return_value = mock_discovery

        # Execute
        with patch('quilt_mcp.tools.resource_access.ResourceManager', return_value=mock_manager):
            result = await get_resource(uri="")

        # Verify proper serialization
        assert isinstance(result, GetResourceSuccess)
        test_resources = result.data["test"]
        assert isinstance(test_resources, list)
        assert isinstance(test_resources[0], dict)
        assert test_resources[0]["uri"] == "test://resource"
        assert test_resources[0]["is_template"] is True
        assert test_resources[0]["template_variables"] == ["param"]
