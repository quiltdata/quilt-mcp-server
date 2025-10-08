"""Stateless tabulator tool tests."""

from __future__ import annotations

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import tabulator

from contextlib import contextmanager
from unittest.mock import Mock


@contextmanager
def runtime_token(token: str | None):
    metadata = {"session_id": "tabulator-tests"} if token else None
    with request_context(token, metadata=metadata):
        yield


@pytest.mark.asyncio
async def test_tabulator_list_requires_token():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    result = await tabulator.tabulator_tables_list("bucket")
    monkeypatch.undo()
    assert result["success"] is False
    assert "Authorization token" in result["error"]


@pytest.mark.asyncio
async def test_tabulator_list_requires_catalog_url(monkeypatch):
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    with runtime_token("token"):
        result = await tabulator.tabulator_tables_list("bucket")
    assert result["success"] is False
    assert "Catalog URL" in result["error"]


@pytest.mark.asyncio
async def test_tabulator_tables_list_uses_catalog(monkeypatch):
    captured: dict[str, object] = {}

    def fake_catalog_list(**kwargs):
        captured.update(kwargs)
        return {
            "name": "bucket",
            "tabulatorTables": [
                {"name": "table1", "config": "config: value"},
                {"name": "table2", "config": "config: other"},
            ],
        }

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_tables_list",
        fake_catalog_list,
    )

    with runtime_token("token-value"):
        result = await tabulator.tabulator_tables_list("bucket")

    assert captured["auth_token"] == "token-value"
    assert captured["registry_url"] == "https://catalog.example.com"
    assert captured["bucket_name"] == "bucket"
    assert result["success"] is True
    assert result["table_count"] == 2
    assert {table["name"] for table in result["tables"]} == {"table1", "table2"}
    assert "tables_table" in result  # formatted view injected


def _raise_runtime_error(*_args, **_kwargs):
    raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_tabulator_tables_list_handles_error(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_tables_list",
        _raise_runtime_error,
    )

    with runtime_token("token"):
        result = await tabulator.tabulator_tables_list("bucket")

    assert result["success"] is False
    assert "Failed to list" in result["error"]
    assert "boom" in result["error"]


@pytest.mark.asyncio
async def test_tabulator_table_create_calls_catalog(monkeypatch):
    captured: dict[str, object] = {}

    def fake_set(**kwargs):
        captured.update(kwargs)
        return {
            "name": "bucket",
            "tabulatorTables": [{"name": "table", "config": "config: value"}],
        }

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_table_set",
        fake_set,
    )

    with runtime_token("token"):
        result = await tabulator.tabulator_table_create(
            bucket_name="bucket",
            table_name="table",
            config_yaml="config: value",
        )

    assert captured["bucket_name"] == "bucket"
    assert captured["table_name"] == "table"
    assert captured["config_yaml"] == "config: value"
    assert result["success"] is True
    assert result["table"]["name"] == "table"


@pytest.mark.asyncio
async def test_tabulator_table_create_requires_config():
    result = await tabulator.tabulator_table_create("bucket", "table", "")
    assert result["success"] is False
    assert "configuration" in result["error"]


@pytest.mark.asyncio
async def test_tabulator_table_create_propagates_errors(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_table_set",
        _raise_runtime_error,
    )

    with runtime_token("token"):
        result = await tabulator.tabulator_table_create("bucket", "table", "config: value")

    assert result["success"] is False
    assert "Failed to create" in result["error"]


@pytest.mark.asyncio
async def test_tabulator_table_delete_calls_catalog(monkeypatch):
    captured = {}

    def fake_delete(**kwargs):
        captured.update(kwargs)
        return {"name": "bucket", "tabulatorTables": []}

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_table_set",
        fake_delete,
    )

    with runtime_token("token"):
        result = await tabulator.tabulator_table_delete("bucket", "table")

    assert captured["config_yaml"] is None
    assert result["success"] is True
    assert "deleted" in result["message"]


@pytest.mark.asyncio
async def test_tabulator_table_rename_calls_catalog(monkeypatch):
    captured = {}

    def fake_rename(**kwargs):
        captured.update(kwargs)
        return {
            "name": "bucket",
            "tabulatorTables": [{"name": "new-name", "config": "config: value"}],
        }

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_table_rename",
        fake_rename,
    )

    with runtime_token("token"):
        result = await tabulator.tabulator_table_rename("bucket", "old-name", "new-name")

    assert captured["table_name"] == "old-name"
    assert captured["new_table_name"] == "new-name"
    assert result["success"] is True
    assert result["new_table_name"] == "new-name"


@pytest.mark.asyncio
async def test_tabulator_table_get_returns_specific_table(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")

    def fake_list(**kwargs):
        return {
            "name": "bucket",
            "tabulatorTables": [{"name": "table", "config": "config: value"}],
        }

    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_tables_list",
        fake_list,
    )

    with runtime_token("token"):
        result = await tabulator.tabulator_table_get("bucket", "table")

    assert result["success"] is True
    assert result["table"]["name"] == "table"


@pytest.mark.asyncio
async def test_tabulator_table_get_missing(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")

    def fake_list(**kwargs):
        return {"name": "bucket", "tabulatorTables": []}

    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_tables_list",
        fake_list,
    )

    with runtime_token("token"):
        result = await tabulator.tabulator_table_get("bucket", "missing")

    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_tabulator_open_query_status(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_open_query_status",
        lambda **_: True,
    )

    with runtime_token("token"):
        result = await tabulator.tabulator_open_query_status()

    assert result["success"] is True
    assert result["open_query_enabled"] is True


@pytest.mark.asyncio
async def test_tabulator_open_query_toggle(monkeypatch):
    captured = {}

    def fake_toggle(**kwargs):
        captured.update(kwargs)
        return False

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_open_query_set",
        fake_toggle,
    )

    with runtime_token("token"):
        result = await tabulator.tabulator_open_query_toggle(False)

    assert captured["enabled"] is False
    assert result["success"] is True
    assert result["open_query_enabled"] is False


@pytest.mark.asyncio
async def test_tabulator_open_query_toggle_requires_bool():
    result = await tabulator.tabulator_open_query_toggle("yes")
    assert result["success"] is False
    assert "boolean" in result["error"]


@pytest.mark.asyncio
async def test_tabulator_dispatcher_handles_json_string_params(monkeypatch):
    """Test that the dispatcher can handle params as a JSON string (issue #207)."""
    import json
    
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    
    def fake_list(**kwargs):
        return {
            "name": "test-bucket",
            "tabulatorTables": [{"name": "table1", "config": "config: value"}],
        }
    
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_tables_list",
        fake_list,
    )
    
    # Create params as a JSON string (simulating what the LLM/MCP client might do)
    params_as_json_string = json.dumps({"bucket_name": "test-bucket"})
    
    with runtime_token("token"):
        result = await tabulator.tabulator(
            action="tables_list",
            params=params_as_json_string,  # Pass as string instead of dict
        )
    
    assert result["success"] is True
    assert result["bucket_name"] == "test-bucket"
    assert result["table_count"] == 1


@pytest.mark.asyncio
async def test_tabulator_dispatcher_handles_invalid_json_string():
    """Test that invalid JSON in params returns a clear error."""
    result = await tabulator.tabulator(
        action="tables_list",
        params='{"invalid json',  # Invalid JSON string
    )
    
    assert result["success"] is False
    assert "Invalid JSON in params" in result["error"]


@pytest.mark.asyncio
async def test_tabulator_dispatcher_still_handles_dict_params(monkeypatch):
    """Test that normal dict params still work (backwards compatibility)."""
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog.example.com")
    
    def fake_list(**kwargs):
        return {
            "name": "test-bucket",
            "tabulatorTables": [{"name": "table1", "config": "config: value"}],
        }
    
    monkeypatch.setattr(
        "quilt_mcp.clients.catalog.catalog_tabulator_tables_list",
        fake_list,
    )
    
    with runtime_token("token"):
        result = await tabulator.tabulator(
            action="tables_list",
            params={"bucket_name": "test-bucket"},  # Pass as dict (normal case)
        )
    
    assert result["success"] is True
    assert result["bucket_name"] == "test-bucket"
    assert result["table_count"] == 1
