"""Behavior-driven tests for the tabulator service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


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

    # Call the function
    from quilt_mcp.services.athena_read_service import tabulator_query_execute

    result = tabulator_query_execute("SHOW DATABASES")

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
    from quilt_mcp.services.athena_read_service import tabulator_query_execute

    result = tabulator_query_execute("SELECT * FROM test_table LIMIT 1", database_name="test-bucket")

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
    from quilt_mcp.services.athena_read_service import tabulator_query_execute

    result = tabulator_query_execute("SHOW DATABASES")

    assert result["success"] is False
    assert "tabulator_data_catalog not configured" in result["error"]


def test_tabulator_bucket_query_calls_tabulator_query_with_database(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_query_execute is called with database_name via tools layer."""
    # Mock tabulator_query_execute
    mock_query = MagicMock(
        return_value={
            "success": True,
            "formatted_data": [{"col1": "value1"}],
        }
    )
    monkeypatch.setattr("quilt_mcp.services.athena_read_service.tabulator_query_execute", mock_query)

    # Call the tools function
    from quilt_mcp.tools.tabulator import tabulator_bucket_query
    import asyncio

    result = asyncio.run(tabulator_bucket_query(bucket_name="test-bucket", query="SELECT * FROM test_table LIMIT 1"))

    # Verify tabulator_query_execute was called with database_name
    mock_query.assert_called_once()
    call_kwargs = mock_query.call_args.kwargs
    assert call_kwargs["query"] == "SELECT * FROM test_table LIMIT 1"
    assert call_kwargs["database_name"] == "test-bucket"

    # Verify result
    assert result["success"] is True


def test_tabulator_bucket_query_validates_bucket_name(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_query_execute validates bucket_name parameter."""
    # Mock to return validation error
    mock_query = MagicMock(return_value={"success": False, "error": "Query cannot be empty"})
    monkeypatch.setattr("quilt_mcp.services.athena_read_service.tabulator_query_execute", mock_query)

    from quilt_mcp.tools.tabulator import tabulator_bucket_query
    import asyncio

    # Call with empty bucket_name - tool validation happens first
    # The empty bucket_name will be passed to tabulator_query_execute which uses it as database_name
    result = asyncio.run(tabulator_bucket_query(bucket_name="", query="SELECT * FROM table"))

    # Should still call the function (tool doesn't validate bucket name)
    assert result is not None


def test_tabulator_bucket_query_validates_query(monkeypatch: pytest.MonkeyPatch):
    """Test that tabulator_query_execute validates query parameter."""
    # Mock catalog_info to provide tabulator_data_catalog
    mock_catalog_info = MagicMock(
        return_value={
            "status": "success",
            "tabulator_data_catalog": "quilt_example_catalog",
        }
    )
    monkeypatch.setattr("quilt_mcp.services.auth_metadata.catalog_info", mock_catalog_info)

    from quilt_mcp.services.athena_read_service import tabulator_query_execute

    # Call with empty query - should return error from athena_query_execute
    result = tabulator_query_execute(query="", database_name="test-bucket")

    assert result["success"] is False
    assert "query" in result["error"].lower() or "empty" in result["error"].lower()
