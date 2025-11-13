"""Simple tests for get_resource tool - testing actual functionality."""

import pytest
from quilt_mcp.tools.resource_access import get_resource
from quilt_mcp.models.responses import GetResourceSuccess, GetResourceError


class TestGetResourceSimple:
    """Test get_resource tool with actual service calls."""

    @pytest.mark.asyncio
    async def test_discovery_mode(self):
        """Test discovery mode lists all 17 resources."""
        result = await get_resource()

        assert isinstance(result, GetResourceSuccess)
        assert result.success is True
        assert result.uri == "discovery://resources"
        assert "resources" in result.data
        assert result.data["count"] == 17
        assert len(result.data["resources"]) == 17

    @pytest.mark.asyncio
    async def test_discovery_mode_with_empty_string(self):
        """Test discovery mode with empty string URI."""
        result = await get_resource(uri="")

        assert isinstance(result, GetResourceSuccess)
        assert result.data["count"] == 17

    @pytest.mark.asyncio
    async def test_unknown_uri(self):
        """Test error handling for unknown URI."""
        result = await get_resource(uri="unknown://resource")

        assert isinstance(result, GetResourceError)
        assert result.success is False
        assert "not found" in result.error.lower()
        assert result.valid_uris is not None
        assert len(result.valid_uris) == 17

    @pytest.mark.asyncio
    async def test_static_resource_auth_status(self):
        """Test accessing auth://status resource."""
        result = await get_resource(uri="auth://status")

        assert isinstance(result, GetResourceSuccess)
        assert result.uri == "auth://status"
        assert result.resource_name == "Auth Status"
        assert isinstance(result.data, dict)

    @pytest.mark.asyncio
    async def test_static_resource_troubleshooting(self):
        """Test static response for troubleshooting resource."""
        result = await get_resource(uri="metadata://troubleshooting")

        assert isinstance(result, GetResourceSuccess)
        assert result.uri == "metadata://troubleshooting"
        assert "message" in result.data
