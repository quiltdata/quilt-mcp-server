"""Behavior-driven tests for the tabulator service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from quilt_mcp.services import tabulator_service as tabulator


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
    yield


def test_create_table_normalizes_parser_format(monkeypatch: pytest.MonkeyPatch):
    """Test that parser format is normalized - DEPRECATED TEST.

    This test is now deprecated as table creation logic has moved to tools layer.
    Keeping for backward compatibility with query operations.
    """
    pytest.skip("Table creation moved to TabulatorMixin - test deprecated")


def test_create_table_returns_validation_errors(monkeypatch: pytest.MonkeyPatch):
    """Test validation errors - DEPRECATED TEST.

    This test is now deprecated as table creation logic has moved to tools layer.
    Validation now handled by TabulatorMixin in backend.
    """
    pytest.skip("Table creation moved to TabulatorMixin - test deprecated")


# TESTS FOR _tabulator_query, tabulator_buckets_list, and tabulator_bucket_query


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
    monkeypatch.setattr("quilt_mcp.services.auth_metadata.catalog_info", mock_catalog_info)

    # Mock athena_query_execute
    mock_execute = MagicMock(return_value={"success": True, "rows": [], "row_count": 0})
    monkeypatch.setattr("quilt_mcp.services.athena_read_service.athena_query_execute", mock_execute)

    # Call the private function
    from quilt_mcp.services.tabulator_service import _tabulator_query

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
    monkeypatch.setattr("quilt_mcp.services.auth_metadata.catalog_info", mock_catalog_info)

    # Mock athena_query_execute
    mock_execute = MagicMock(return_value={"success": True, "formatted_data": []})
    monkeypatch.setattr("quilt_mcp.services.athena_read_service.athena_query_execute", mock_execute)

    # Call with database_name
    from quilt_mcp.services.tabulator_service import _tabulator_query

    result = _tabulator_query("SELECT * FROM test_table LIMIT 1", database_name="test-bucket")

    # Verify athena_query_execute was called with database_name
    call_kwargs = mock_execute.call_args.kwargs
    assert call_kwargs["database_name"] == "test-bucket"
    assert call_kwargs["data_catalog_name"] == "quilt_example_catalog"


def test_tabulator_query_fails_without_catalog_config(monkeypatch: pytest.MonkeyPatch):
    """Test that _tabulator_query fails gracefully without catalog configuration."""
    # Mock catalog_info to return no tabulator_data_catalog
    mock_catalog_info = MagicMock(return_value={"status": "success", "is_authenticated": True})
    monkeypatch.setattr("quilt_mcp.services.auth_metadata.catalog_info", mock_catalog_info)

    # Call should fail
    from quilt_mcp.services.tabulator_service import _tabulator_query

    result = _tabulator_query("SHOW DATABASES")

    assert result["success"] is False
    assert "tabulator_data_catalog not configured" in result["error"]


def test_tabulator_bucket_query_calls_tabulator_query_with_database(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_bucket_query calls _tabulator_query with database_name."""
    # Mock _tabulator_query
    mock_query = MagicMock(
        return_value={
            "success": True,
            "formatted_data": [{"col1": "value1"}],
        }
    )
    monkeypatch.setattr("quilt_mcp.services.tabulator_service._tabulator_query", mock_query)

    # Call the function
    from quilt_mcp.services.tabulator_service import tabulator_bucket_query
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
    from quilt_mcp.services.tabulator_service import tabulator_bucket_query
    import asyncio

    # Call with empty bucket_name
    result = asyncio.run(tabulator_bucket_query(bucket_name="", query="SELECT * FROM table"))

    assert result["success"] is False
    assert "bucket_name" in result["error"].lower()


def test_tabulator_bucket_query_validates_query(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_bucket_query validates query parameter."""
    from quilt_mcp.services.tabulator_service import tabulator_bucket_query
    import asyncio

    # Call with empty query
    result = asyncio.run(tabulator_bucket_query(bucket_name="test-bucket", query=""))

    assert result["success"] is False
    assert "query" in result["error"].lower()
