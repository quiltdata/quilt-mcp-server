import asyncio
import pytest
from unittest.mock import patch

from quilt_mcp.tools.tabulator import (
    tabulator_table_query,
    tabulator_table_preview,
    tabulator,
)


@patch("quilt_mcp.tools.tabulator.catalog_client.catalog_tabulator_query")
@patch("quilt_mcp.tools.tabulator.resolve_catalog_url", return_value="https://catalog.example")
@patch("quilt_mcp.tools.tabulator.get_active_token", return_value="token-123")
def test_tabulator_table_query_success(mock_token, mock_catalog_url, mock_query):
    mock_query.return_value = {
        "columns": ["sample_id", "tpm"],
        "columnTypes": ["STRING", "FLOAT"],
        "rows": [
            ["sample-1", 12.3],
            ["sample-2", 7.8],
        ],
        "rowCount": 2,
    }

    result = asyncio.run(
        tabulator_table_query(
            bucket_name="nextflowtower",
            table_name="sail-nextflow",
            limit=2,
            offset=0,
        )
    )

    assert result["success"] is True
    assert result["bucket_name"] == "nextflowtower"
    assert result["table_name"] == "sail-nextflow"
    assert result["row_count"] == 2
    assert result["columns"] == ["sample_id", "tpm"]
    assert "formatted_table" in result

    mock_query.assert_called_once_with(
        registry_url="https://catalog.example",
        bucket_name="nextflowtower",
        table_name="sail-nextflow",
        limit=2,
        offset=0,
        filters=None,
        order_by=None,
        selects=None,
        auth_token="token-123",
    )


@patch("quilt_mcp.tools.tabulator.catalog_client.catalog_tabulator_query")
@patch("quilt_mcp.tools.tabulator.resolve_catalog_url", return_value="https://catalog.example")
@patch("quilt_mcp.tools.tabulator.get_active_token", return_value="token-123")
def test_tabulator_table_query_handles_backend_error(mock_token, mock_catalog_url, mock_query):
    mock_query.return_value = {
        "error": "INVALID_FUNCTION_ARGUMENT: undefined group option",
    }

    result = asyncio.run(
        tabulator_table_query(
            bucket_name="nextflowtower",
            table_name="sail-nextflow",
        )
    )

    assert result["success"] is False
    assert "undefined group option" in result["error"]


@patch("quilt_mcp.tools.tabulator.catalog_client.catalog_tabulator_query")
@patch("quilt_mcp.tools.tabulator.resolve_catalog_url", return_value="https://catalog.example")
@patch("quilt_mcp.tools.tabulator.get_active_token", return_value="token")
def test_tabulator_table_preview_uses_default_limit(mock_token, mock_catalog_url, mock_query):
    mock_query.return_value = {
        "columns": ["gene", "tpm"],
        "rows": [],
    }

    asyncio.run(
        tabulator_table_preview(
            bucket_name="nextflowtower",
            table_name="sail-nextflow",
        )
    )

    mock_query.assert_called_once()
    _, kwargs = mock_query.call_args
    assert kwargs["limit"] == 10


@patch("quilt_mcp.tools.tabulator.catalog_client.catalog_tabulator_query", return_value={"rows": []})
@patch("quilt_mcp.tools.tabulator.resolve_catalog_url", return_value="https://catalog.example")
@patch("quilt_mcp.tools.tabulator.get_active_token", return_value="token")
def test_tabulator_dispatch_includes_query_action(mock_token, mock_catalog_url, mock_query):
    result = asyncio.run(
        tabulator(
            action="table_query",
            params={
                "bucket_name": "nextflowtower",
                "table_name": "sail-nextflow",
                "limit": 5,
            },
        )
    )

    assert result["success"] is True
    assert result["bucket_name"] == "nextflowtower"
