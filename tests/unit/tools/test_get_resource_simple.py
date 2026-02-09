"""Simple tests for get_resource tool - testing actual functionality."""

import pytest
from quilt_mcp.tools.resource_access import get_resource
from quilt_mcp.tools.responses import GetResourceSuccess, GetResourceError
from quilt_mcp.config import set_test_mode_config


class TestGetResourceSimple:
    """Test get_resource tool with actual service calls."""

    @pytest.mark.asyncio
    async def test_discovery_mode(self):
        """Test discovery mode lists all resources."""
        result = await get_resource()

        assert isinstance(result, GetResourceSuccess)
        assert result.success is True
        assert result.uri == "discovery://resources"
        assert "resources" in result.data
        assert result.data["count"] > 10  # Should have at least 10+ resources
        assert len(result.data["resources"]) > 10

    @pytest.mark.asyncio
    async def test_discovery_mode_with_empty_string(self):
        """Test discovery mode with empty string URI."""
        result = await get_resource(uri="")

        assert isinstance(result, GetResourceSuccess)
        assert result.data["count"] > 10  # Should have at least 10+ resources

    @pytest.mark.asyncio
    async def test_unknown_uri(self):
        """Test error handling for unknown URI."""
        result = await get_resource(uri="unknown://resource")

        assert isinstance(result, GetResourceError)
        assert result.success is False
        assert "not found" in result.error.lower()
        assert result.valid_uris is not None
        assert len(result.valid_uris) > 10  # Should have at least 10+ valid URIs

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

    @pytest.mark.asyncio
    async def test_multiuser_hides_stateful_resources(self):
        """Multiuser mode should not expose stateful resources."""
        set_test_mode_config(multiuser_mode=True)

        result = await get_resource()
        assert isinstance(result, GetResourceSuccess)
        uris = {entry["uri"] for entry in result.data["resources"]}
        assert "workflow://workflows" not in uris
        assert "metadata://templates" not in uris
        assert "metadata://examples" not in uris
        assert "metadata://troubleshooting" not in uris

        missing = await get_resource(uri="workflow://workflows")
        assert isinstance(missing, GetResourceError)
        assert "not found" in missing.error.lower()
