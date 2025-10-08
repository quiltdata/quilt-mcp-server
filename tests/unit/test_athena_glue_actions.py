import pytest
from unittest.mock import MagicMock, patch

from quilt_mcp.tools.athena_glue import (
    athena_tables_list,
    athena_table_schema,
    athena_tables_overview,
    athena_query_execute,
)


@patch("quilt_mcp.tools.athena_glue.AthenaQueryService")
def test_tables_list_accepts_database_alias(mock_service_class):
    mock_service = mock_service_class.return_value
    mock_service.discover_tables.return_value = {"success": True, "tables": [], "count": 0}

    result = athena_tables_list(database="example-db")

    mock_service.discover_tables.assert_called_once_with("example-db", "AwsDataCatalog", None)
    assert result["success"] is True


@patch("quilt_mcp.tools.athena_glue.AthenaQueryService")
def test_table_schema_accepts_aliases(mock_service_class):
    mock_service = mock_service_class.return_value
    mock_service.get_table_metadata.return_value = {"success": True, "columns": []}

    result = athena_table_schema(database="db", table="tbl")

    mock_service.get_table_metadata.assert_called_once_with("db", "tbl", "AwsDataCatalog")
    assert result["success"] is True


@patch("quilt_mcp.tools.athena_glue.AthenaQueryService")
def test_tables_overview_builds_summary(mock_service_class):
    mock_service = mock_service_class.return_value
    mock_service.discover_databases.return_value = {
        "success": True,
        "databases": [
            {"name": "db1"},
            {"name": "db2"},
        ],
    }
    mock_service.discover_tables.side_effect = [
        {"success": True, "tables": ["a", "b"], "count": 2},
        {"success": False, "error": "no access"},
    ]

    result = athena_tables_overview(include_tables=True)

    assert result["success"] is True
    assert result["database_count"] == 2
    db1, db2 = result["databases"]
    assert db1["database_name"] == "db1"
    assert db1["table_count"] == 2
    assert db1["tables"] == ["a", "b"]
    assert db2["error"] == "no access"


@patch("quilt_mcp.tools.athena_glue.AthenaQueryService")
def test_query_execute_accepts_database_alias(mock_service_class):
    mock_service = mock_service_class.return_value
    mock_service.execute_query.return_value = {"success": True, "data": []}
    mock_service.format_results.return_value = {"success": True, "formatted_data": []}

    result = athena_query_execute("SELECT 1", database="analytics")

    mock_service.execute_query.assert_called_once_with("SELECT 1", "analytics", 1000)
    assert result["success"] is True
