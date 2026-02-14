"""Simple tests for get_resource tool - testing actual functionality."""

import pytest
from quilt_mcp.tools.resource_access import get_resource
from quilt_mcp.tools.responses import GetResourceSuccess, GetResourceError
from quilt_mcp.config import set_test_mode_config


class TestGetResourceSimple:
    """Test get_resource tool with actual service calls."""

    @pytest.fixture(autouse=True)
    def _default_local_mode(self):
        set_test_mode_config(multiuser_mode=False)

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

    @pytest.mark.asyncio
    async def test_permission_error_path(self, monkeypatch):
        class _BoomModule:
            @staticmethod
            def denied():
                raise RuntimeError("403 permission denied")

        monkeypatch.setattr(
            "quilt_mcp.tools.resource_access._get_resource_service_map",
            lambda: {"auth://boom": ("boom.module", "denied", False)},
        )
        monkeypatch.setattr("importlib.import_module", lambda _name: _BoomModule)
        result = await get_resource(uri="auth://boom")
        assert isinstance(result, GetResourceError)
        assert result.suggested_actions is not None
        assert "required privileges" in " ".join(result.suggested_actions).lower()

    @pytest.mark.asyncio
    async def test_static_not_implemented_path(self, monkeypatch):
        monkeypatch.setattr(
            "quilt_mcp.tools.resource_access._get_resource_service_map",
            lambda: {"static://missing": (None, None, False)},
        )

        result = await get_resource(uri="static://missing")
        assert isinstance(result, GetResourceError)
        assert "not implemented" in result.error.lower()

    @pytest.mark.asyncio
    async def test_async_service_and_model_dump_serialization(self, monkeypatch):
        class _Model:
            def model_dump(self):
                return {"k": "v"}

        class _AsyncModule:
            @staticmethod
            async def a_func():
                return _Model()

        monkeypatch.setattr(
            "quilt_mcp.tools.resource_access._get_resource_service_map",
            lambda: {"auth://async": ("any.module", "a_func", True)},
        )
        monkeypatch.setattr("importlib.import_module", lambda _name: _AsyncModule)
        result = await get_resource(uri="auth://async")
        assert isinstance(result, GetResourceSuccess)
        assert result.data == {"k": "v"}

    @pytest.mark.asyncio
    async def test_athena_history_special_case_and_generic_error_path(self, monkeypatch):
        class _SyncModule:
            @staticmethod
            def history():
                return {"unexpected": "ignored-by-special-case"}

        monkeypatch.setattr(
            "quilt_mcp.tools.resource_access._get_resource_service_map",
            lambda: {"athena://query/history": ("any.module", "history", False)},
        )
        monkeypatch.setattr("importlib.import_module", lambda _name: _SyncModule)
        monkeypatch.setattr(
            "quilt_mcp.services.athena_read_service.athena_query_history",
            lambda **_kwargs: 123,
        )
        ok = await get_resource(uri="athena://query/history")
        assert isinstance(ok, GetResourceSuccess)
        assert ok.data == {"result": "123"}

        class _BoomModule:
            @staticmethod
            def boom():
                raise RuntimeError("plain failure")

        monkeypatch.setattr(
            "quilt_mcp.tools.resource_access._get_resource_service_map",
            lambda: {"auth://boom2": ("any.module", "boom", False)},
        )
        monkeypatch.setattr("importlib.import_module", lambda _name: _BoomModule)
        err = await get_resource(uri="auth://boom2")
        assert isinstance(err, GetResourceError)
        assert err.possible_fixes is not None
