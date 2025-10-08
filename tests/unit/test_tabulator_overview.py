import pytest
from unittest.mock import patch

from quilt_mcp.tools import tabulator


@pytest.mark.asyncio
async def test_tabulator_tables_overview_filters_empty():
    buckets = [
        {"name": "bucket-a", "tabulatorTables": [{"name": "t1", "config": "cfg"}]},
        {"name": "bucket-b", "tabulatorTables": []},
    ]

    with patch("quilt_mcp.tools.tabulator._missing_prerequisites", return_value=None), patch(
        "quilt_mcp.tools.tabulator.resolve_catalog_url", return_value="https://catalog"
    ), patch("quilt_mcp.tools.tabulator.get_active_token", return_value="token"), patch(
        "quilt_mcp.tools.tabulator.catalog_client.catalog_tabulator_buckets_with_tables",
        return_value=buckets,
    ):
        result = await tabulator.tabulator_tables_overview()

    assert result["success"] is True
    assert result["bucket_count"] == 1
    assert result["buckets"][0]["bucket_name"] == "bucket-a"
    assert result["buckets"][0]["table_count"] == 1
