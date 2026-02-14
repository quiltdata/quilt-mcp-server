"""Additional tests for MCP resources registration and serialization."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quilt_mcp.tools.resources import _serialize_result, register_resources


class _ModeConfig:
    def __init__(self, is_local_dev: bool):
        self.is_local_dev = is_local_dev


def _capture_registered_resources():
    mcp = MagicMock()
    registered: dict[str, object] = {}

    def _resource(uri, **_kwargs):
        def _decorator(func):
            registered[uri] = func
            return func

        return _decorator

    mcp.resource = _resource
    return mcp, registered


def test_serialize_result_supports_model_dump():
    class _Model:
        def model_dump(self):
            return {"ok": True}

    parsed = json.loads(_serialize_result(_Model()))
    assert parsed == {"ok": True}


@pytest.mark.asyncio
async def test_register_resources_core_auth_and_athena_paths():
    mcp, resources = _capture_registered_resources()

    with (
        patch("quilt_mcp.config.get_mode_config", return_value=_ModeConfig(is_local_dev=False)),
        patch("quilt_mcp.services.auth_metadata.auth_status", return_value={"auth": True}),
        patch("quilt_mcp.services.auth_metadata.catalog_info", return_value={"catalog": "ok"}),
        patch("quilt_mcp.services.auth_metadata.filesystem_status", return_value={"writable": True}),
        patch("quilt_mcp.services.athena_read_service.athena_databases_list", return_value={"dbs": ["a"]}),
        patch("quilt_mcp.services.athena_read_service.athena_workgroups_list", return_value={"wgs": ["b"]}),
        patch("quilt_mcp.services.athena_read_service.athena_query_history", return_value={"history": []}),
        patch("quilt_mcp.services.athena_read_service.tabulator_list_buckets", return_value={"buckets": ["x"]}),
    ):
        register_resources(mcp)

        auth_status = json.loads(await resources["auth://status"]())
        catalog = json.loads(await resources["auth://catalog/info"]())
        filesystem = json.loads(await resources["auth://filesystem/status"]())
        athena_dbs = json.loads(await resources["athena://databases"]())
        athena_wgs = json.loads(await resources["athena://workgroups"]())
        athena_hist = json.loads(await resources["athena://query/history"]())
        tab_buckets = json.loads(await resources["tabulator://buckets"]())

    assert auth_status == {"auth": True}
    assert catalog == {"catalog": "ok"}
    assert filesystem == {"writable": True}
    assert athena_dbs == {"dbs": ["a"]}
    assert athena_wgs == {"wgs": ["b"]}
    assert athena_hist == {"history": []}
    assert tab_buckets == {"buckets": ["x"]}


@pytest.mark.asyncio
async def test_admin_roles_returns_generic_error_payload_for_non_auth_failure():
    mcp, resources = _capture_registered_resources()

    with (
        patch("quilt_mcp.config.get_mode_config", return_value=_ModeConfig(is_local_dev=False)),
        patch(
            "quilt_mcp.services.governance_service.admin_roles_list",
            new_callable=AsyncMock,
            side_effect=Exception("service unavailable"),
        ),
        patch("quilt_mcp.context.factory.RequestContextFactory") as mock_factory,
    ):
        mock_factory.return_value.create_context.return_value = MagicMock()
        register_resources(mcp)
        payload = json.loads(await resources["admin://roles"]())

    assert payload["error"] == "Failed to list roles"
    assert "service unavailable" in payload["message"]


@pytest.mark.asyncio
async def test_local_dev_resources_registered_and_callable():
    mcp, resources = _capture_registered_resources()

    with (
        patch("quilt_mcp.config.get_mode_config", return_value=_ModeConfig(is_local_dev=True)),
        patch("quilt_mcp.services.metadata_service.list_metadata_templates", return_value={"templates": ["t"]}),
        patch("quilt_mcp.services.metadata_service.show_metadata_examples", return_value={"examples": ["e"]}),
        patch("quilt_mcp.services.workflow_service.workflow_list_all", return_value={"workflows": []}),
        patch("quilt_mcp.context.factory.RequestContextFactory") as mock_factory,
    ):
        mock_factory.return_value.create_context.return_value = MagicMock()
        register_resources(mcp)
        templates = json.loads(await resources["metadata://templates"]())
        examples = json.loads(await resources["metadata://examples"]())
        troubleshooting = json.loads(await resources["metadata://troubleshooting"]())
        workflows = json.loads(await resources["workflow://workflows"]())

    assert templates == {"templates": ["t"]}
    assert examples == {"examples": ["e"]}
    assert troubleshooting["status"] == "info"
    assert workflows == {"workflows": []}
