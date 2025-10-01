"""Behavior-driven tests for the tabulator service."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from quilt_mcp.tools import tabulator


class DummyTabulatorAdmin:
    def __init__(self, response=None):
        self.response = response or SimpleNamespace()
        self.calls = []

    def set_table(self, **kwargs):
        self.calls.append(("set_table", kwargs))
        return self.response


@pytest.fixture(autouse=True)
def ensure_admin_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(tabulator, "ADMIN_AVAILABLE", True)
    service = tabulator.TabulatorService()
    service.admin_available = True

    # Create a mock QuiltService with all required methods
    mock_service = SimpleNamespace(
        get_tabulator_admin=lambda: None,
        list_tabulator_tables=lambda bucket: [],
        create_tabulator_table=lambda bucket, name, config: {},
        delete_tabulator_table=lambda bucket, name: None,
        rename_tabulator_table=lambda bucket, old_name, new_name: {},
        get_tabulator_access=lambda: False,
        set_tabulator_access=lambda enabled: {},
    )
    monkeypatch.setattr(tabulator, "quilt_service", mock_service)
    yield


def test_create_table_normalizes_parser_format(monkeypatch: pytest.MonkeyPatch):
    service = tabulator.TabulatorService()
    service.admin_available = True

    # Mock QuiltService.create_tabulator_table method
    def mock_create_table(bucket, name, config):
        return {
            "status": "success",
            "table_name": name,
            "bucket_name": bucket,
            "message": f"Tabulator table '{name}' created successfully",
        }

    monkeypatch.setattr(tabulator.quilt_service, "create_tabulator_table", mock_create_table)

    result = service.create_table(
        bucket_name="demo-bucket",
        table_name="demo-table",
        schema=[{"name": "id", "type": "STRING"}],
        package_pattern=r"namespace/.+",
        logical_key_pattern=r".*",
        parser_config={"format": "CSV"},
    )

    assert result["success"] is True
    assert result["parser_config"]["format"] == "csv"
    assert result["parser_config"]["delimiter"] == ","
    assert result["config"]  # Config YAML should be generated
    assert "format: csv" in result["config"]


def test_create_table_returns_validation_errors(monkeypatch: pytest.MonkeyPatch):
    service = tabulator.TabulatorService()
    service.admin_available = True

    result = service.create_table(
        bucket_name="",
        table_name="",
        schema=[],
        package_pattern="",
        logical_key_pattern="",
        parser_config={"format": "csv"},
    )

    assert result["success"] is False
    assert any("Bucket name cannot be empty" in err for err in result["error_details"])
    assert any("Schema cannot be empty" in err for err in result["error_details"])
