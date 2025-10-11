"""Behavior-driven tests for the tabulator service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

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
    monkeypatch.setattr(
        tabulator,
        "quilt_service",
        SimpleNamespace(get_tabulator_admin=lambda: None),
    )
    yield


def test_create_table_normalizes_parser_format(monkeypatch: pytest.MonkeyPatch):
    service = tabulator.TabulatorService()
    service.admin_available = True

    dummy_admin = DummyTabulatorAdmin()
    monkeypatch.setattr(tabulator.quilt_service, "get_tabulator_admin", lambda: dummy_admin)

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

    call = dummy_admin.calls[0]
    assert call[0] == "set_table"
    config_yaml = call[1]["config"]
    assert "format: csv" in config_yaml


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


def test_tabulator_table_query_gets_catalog_from_catalog_info(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_table_query retrieves data_catalog_name from catalog_info."""
    from quilt_mcp.tools import athena_glue

    # Mock catalog_info to return a known data catalog
    mock_catalog_info = MagicMock(
        return_value={
            "status": "success",
            "is_authenticated": True,
            "tabulator_data_catalog": "quilt_example_catalog",
            "region": "us-east-1",
        }
    )
    monkeypatch.setattr("quilt_mcp.tools.auth.catalog_info", mock_catalog_info)

    # Mock athena_query_execute to capture the call
    mock_execute = MagicMock(return_value={"success": True, "rows": [], "row_count": 0})
    monkeypatch.setattr("quilt_mcp.tools.athena_glue.athena_query_execute", mock_execute)

    # Call the wrapper (now in athena_glue module)
    result = athena_glue.tabulator_table_query(bucket_name="test-bucket", query="SELECT * FROM test_table LIMIT 10")

    # Verify catalog_info was called
    mock_catalog_info.assert_called_once()

    # Verify athena_query_execute was called with correct parameters
    mock_execute.assert_called_once()
    call_kwargs = mock_execute.call_args.kwargs

    assert call_kwargs["query"] == "SELECT * FROM test_table LIMIT 10"
    assert call_kwargs["database_name"] == "test-bucket"
    assert call_kwargs["data_catalog_name"] == "quilt_example_catalog"
    assert result["success"] is True


def test_tabulator_table_query_fails_without_tabulator_catalog(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_table_query fails when tabulator_data_catalog is not configured."""
    from quilt_mcp.tools import athena_glue

    # Mock catalog_info to return no tabulator_data_catalog
    mock_catalog_info = MagicMock(
        return_value={"status": "success", "is_authenticated": True, "catalog_name": "example-catalog"}
    )
    monkeypatch.setattr("quilt_mcp.tools.auth.catalog_info", mock_catalog_info)

    # Call the wrapper without explicit data_catalog_name
    result = athena_glue.tabulator_table_query(bucket_name="test-bucket", query="SELECT * FROM test_table")

    # Verify it returns an error
    assert result["success"] is False
    assert "tabulator_data_catalog not configured" in result["error"]
    assert "Check catalog configuration" in result["error"]


def test_tabulator_table_query_works_unauthenticated_with_catalog_config(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_table_query works when unauthenticated but catalog config available."""
    from quilt_mcp.tools import athena_glue

    # Mock catalog_info to return tabulator_data_catalog even when not authenticated
    mock_catalog_info = MagicMock(
        return_value={
            "status": "success",
            "is_authenticated": False,
            "catalog_name": "example-catalog",
            "tabulator_data_catalog": "quilt_example_catalog",  # Config available without auth
        }
    )
    monkeypatch.setattr("quilt_mcp.tools.auth.catalog_info", mock_catalog_info)

    # Mock athena_query_execute
    mock_execute = MagicMock(return_value={"success": True, "rows": [], "row_count": 0})
    monkeypatch.setattr("quilt_mcp.tools.athena_glue.athena_query_execute", mock_execute)

    # Call the wrapper
    result = athena_glue.tabulator_table_query(bucket_name="test-bucket", query="SELECT * FROM test_table")

    # Verify it worked
    assert result["success"] is True
    call_kwargs = mock_execute.call_args.kwargs
    assert call_kwargs["data_catalog_name"] == "quilt_example_catalog"


def test_tabulator_table_query_allows_explicit_catalog_override(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_table_query allows explicit data_catalog_name override."""
    from quilt_mcp.tools import athena_glue

    # Mock catalog_info - won't be used because we provide explicit catalog
    mock_catalog_info = MagicMock(return_value={"status": "success", "is_authenticated": False})
    monkeypatch.setattr("quilt_mcp.tools.auth.catalog_info", mock_catalog_info)

    # Mock athena_query_execute
    mock_execute = MagicMock(return_value={"success": True, "rows": [], "row_count": 0})
    monkeypatch.setattr("quilt_mcp.tools.athena_glue.athena_query_execute", mock_execute)

    # Call with explicit override
    result = athena_glue.tabulator_table_query(
        bucket_name="test-bucket", query="SELECT * FROM test_table", data_catalog_name="CustomCatalog"
    )

    # Verify catalog_info was NOT called because we provided explicit catalog
    mock_catalog_info.assert_not_called()

    # Verify the override was used
    call_kwargs = mock_execute.call_args.kwargs
    assert call_kwargs["data_catalog_name"] == "CustomCatalog"
    assert result["success"] is True
