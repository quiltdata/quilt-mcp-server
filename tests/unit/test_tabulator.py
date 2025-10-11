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
    """Test that tabulator_table_query uses catalog from catalog_info."""
    from quilt_mcp.tools import athena_glue

    # Mock catalog_info to return a custom catalog
    mock_catalog_info = MagicMock(
        return_value={
            "status": "success",
            "is_authenticated": True,
            "tabulator_data_catalog": "CustomCatalog",
        }
    )
    monkeypatch.setattr("quilt_mcp.tools.auth.catalog_info", mock_catalog_info)

    # Mock athena_query_execute
    mock_execute = MagicMock(return_value={"success": True, "rows": [], "row_count": 0})
    monkeypatch.setattr("quilt_mcp.tools.athena_glue.athena_query_execute", mock_execute)

    # Call the function
    result = athena_glue.tabulator_table_query(bucket_name="test-bucket", query="SELECT * FROM test_table")

    # Verify catalog_info was called
    mock_catalog_info.assert_called_once()

    # Verify the catalog from catalog_info was used
    call_kwargs = mock_execute.call_args.kwargs
    assert call_kwargs["data_catalog_name"] == "CustomCatalog"
    assert result["success"] is True


# NEW TESTS FOR _tabulator_query, tabulator_buckets_list, and tabulator_bucket_query


def test_tabulator_query_discovers_catalog_from_catalog_info(monkeypatch: pytest.MonkeyPatch):
    """Test that _tabulator_query auto-discovers tabulator_data_catalog."""
    # Mock catalog_info
    mock_catalog_info = MagicMock(
        return_value={
            "status": "success",
            "is_authenticated": True,
            "tabulator_data_catalog": "quilt_example_catalog",
        }
    )
    monkeypatch.setattr("quilt_mcp.tools.auth.catalog_info", mock_catalog_info)

    # Mock athena_query_execute
    mock_execute = MagicMock(return_value={"success": True, "rows": [], "row_count": 0})
    monkeypatch.setattr("quilt_mcp.tools.athena_glue.athena_query_execute", mock_execute)

    # Call the private function
    from quilt_mcp.tools.tabulator import _tabulator_query

    result = _tabulator_query("SHOW DATABASES")

    # Verify catalog_info was called
    mock_catalog_info.assert_called_once()

    # Verify athena_query_execute was called with discovered catalog
    mock_execute.assert_called_once()
    call_kwargs = mock_execute.call_args.kwargs
    assert call_kwargs["data_catalog_name"] == "quilt_example_catalog"
    assert call_kwargs["query"] == "SHOW DATABASES"
    assert call_kwargs.get("database_name") is None  # No database for catalog-level query


def test_tabulator_query_accepts_database_name(monkeypatch: pytest.MonkeyPatch):
    """Test that _tabulator_query accepts optional database_name parameter."""
    # Mock catalog_info
    mock_catalog_info = MagicMock(
        return_value={
            "status": "success",
            "tabulator_data_catalog": "quilt_example_catalog",
        }
    )
    monkeypatch.setattr("quilt_mcp.tools.auth.catalog_info", mock_catalog_info)

    # Mock athena_query_execute
    mock_execute = MagicMock(return_value={"success": True, "formatted_data": []})
    monkeypatch.setattr("quilt_mcp.tools.athena_glue.athena_query_execute", mock_execute)

    # Call with database_name
    from quilt_mcp.tools.tabulator import _tabulator_query

    result = _tabulator_query("SELECT * FROM test_table LIMIT 1", database_name="test-bucket")

    # Verify athena_query_execute was called with database_name
    call_kwargs = mock_execute.call_args.kwargs
    assert call_kwargs["database_name"] == "test-bucket"
    assert call_kwargs["data_catalog_name"] == "quilt_example_catalog"


def test_tabulator_query_fails_without_catalog_config(monkeypatch: pytest.MonkeyPatch):
    """Test that _tabulator_query fails gracefully without catalog configuration."""
    # Mock catalog_info to return no tabulator_data_catalog
    mock_catalog_info = MagicMock(return_value={"status": "success", "is_authenticated": True})
    monkeypatch.setattr("quilt_mcp.tools.auth.catalog_info", mock_catalog_info)

    # Call should fail
    from quilt_mcp.tools.tabulator import _tabulator_query

    result = _tabulator_query("SHOW DATABASES")

    assert result["success"] is False
    assert "tabulator_data_catalog not configured" in result["error"]


def test_tabulator_buckets_list_calls_tabulator_query(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_buckets_list calls _tabulator_query with SHOW DATABASES."""
    # Mock _tabulator_query
    mock_query = MagicMock(
        return_value={
            "success": True,
            "formatted_data": [
                {"database_name": "bucket-one"},
                {"database_name": "bucket-two"},
            ],
        }
    )
    monkeypatch.setattr("quilt_mcp.tools.tabulator._tabulator_query", mock_query)

    # Call the function
    from quilt_mcp.tools.tabulator import tabulator_buckets_list
    import asyncio

    result = asyncio.run(tabulator_buckets_list())

    # Verify _tabulator_query was called with SHOW DATABASES
    mock_query.assert_called_once()
    call_args = mock_query.call_args[0]
    assert "SHOW DATABASES" in call_args[0]

    # Verify result structure
    assert result["success"] is True
    assert "buckets" in result
    assert len(result["buckets"]) == 2


def test_tabulator_buckets_list_handles_query_failure(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_buckets_list handles _tabulator_query failures."""
    # Mock _tabulator_query to fail
    mock_query = MagicMock(return_value={"success": False, "error": "Catalog not configured"})
    monkeypatch.setattr("quilt_mcp.tools.tabulator._tabulator_query", mock_query)

    # Call should propagate error
    from quilt_mcp.tools.tabulator import tabulator_buckets_list
    import asyncio

    result = asyncio.run(tabulator_buckets_list())

    assert result["success"] is False
    assert "error" in result


def test_tabulator_bucket_query_calls_tabulator_query_with_database(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_bucket_query calls _tabulator_query with database_name."""
    # Mock _tabulator_query
    mock_query = MagicMock(
        return_value={
            "success": True,
            "formatted_data": [{"col1": "value1"}],
        }
    )
    monkeypatch.setattr("quilt_mcp.tools.tabulator._tabulator_query", mock_query)

    # Call the function
    from quilt_mcp.tools.tabulator import tabulator_bucket_query
    import asyncio

    result = asyncio.run(tabulator_bucket_query(bucket_name="test-bucket", query="SELECT * FROM test_table LIMIT 1"))

    # Verify _tabulator_query was called with database_name
    mock_query.assert_called_once()
    call_kwargs = mock_query.call_args.kwargs
    assert call_kwargs["query"] == "SELECT * FROM test_table LIMIT 1"
    assert call_kwargs["database_name"] == "test-bucket"

    # Verify result
    assert result["success"] is True


def test_tabulator_bucket_query_validates_bucket_name(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_bucket_query validates bucket_name parameter."""
    from quilt_mcp.tools.tabulator import tabulator_bucket_query
    import asyncio

    # Call with empty bucket_name
    result = asyncio.run(tabulator_bucket_query(bucket_name="", query="SELECT * FROM table"))

    assert result["success"] is False
    assert "bucket_name" in result["error"].lower()


def test_tabulator_bucket_query_validates_query(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_bucket_query validates query parameter."""
    from quilt_mcp.tools.tabulator import tabulator_bucket_query
    import asyncio

    # Call with empty query
    result = asyncio.run(tabulator_bucket_query(bucket_name="test-bucket", query=""))

    assert result["success"] is False
    assert "query" in result["error"].lower()
