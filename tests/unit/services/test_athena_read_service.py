from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from quilt_mcp.services import athena_read_service as ars


def test_sanitize_query_for_logging_replaces_percent():
    assert ars._sanitize_query_for_logging("select 100% as p") == "select 100%% as p"


@pytest.mark.parametrize(
    ("query", "error", "expected_fragment"),
    [
        ('SELECT * FROM "db-with-dash".t', "mismatched input", "double quotes"),
        ("SELECT * FROM missing", "TABLE_NOT_FOUND", "SHOW DATABASES"),
        ("SELECT * FROM t WHERE c LIKE '%foo%'", "format string", "formatting issues"),
    ],
)
def test_suggest_query_fix_common_cases(query: str, error: str, expected_fragment: str):
    suggestion = ars._suggest_query_fix(query, error)
    assert expected_fragment in suggestion


def test_athena_databases_list_success_and_error_response():
    service = Mock()
    service.discover_databases.return_value = {
        "success": True,
        "databases": [{"name": "db1", "description": "d"}],
        "count": 1,
        "data_catalog_name": "AwsDataCatalog",
    }
    result = ars.athena_databases_list(service=service)
    assert result.success is True
    assert result.count == 1
    assert result.databases[0].name == "db1"

    service.discover_databases.return_value = {"success": False, "error": "boom"}
    err = ars.athena_databases_list(service=service)
    assert err.success is False
    assert "boom" in err.error


def test_athena_tables_list_uses_default_pattern_and_handles_exception():
    service = Mock()
    service.discover_tables.return_value = {
        "success": True,
        "tables": [{"name": "t1", "database_name": "db"}],
        "database_name": "db",
        "data_catalog_name": "AwsDataCatalog",
        "count": 1,
    }
    result = ars.athena_tables_list(database="db", service=service)
    assert result.success is True
    assert result.tables[0].name == "t1"
    service.discover_tables.assert_called_once_with("db", data_catalog_name="AwsDataCatalog", table_pattern="*")

    service.discover_tables.side_effect = RuntimeError("no tables")
    err = ars.athena_tables_list(database="db", service=service)
    assert err.success is False
    assert "no tables" in err.error


def test_athena_table_schema_success_and_error_result():
    service = Mock()
    service.get_table_metadata.return_value = {
        "success": True,
        "table_name": "tbl",
        "database_name": "db",
        "data_catalog_name": "AwsDataCatalog",
        "columns": [{"name": "c1", "type": "string"}],
        "partitions": [{"name": "p1", "type": "string"}],
    }
    result = ars.athena_table_schema(database="db", table="tbl", service=service)
    assert result.success is True
    assert result.columns[0].name == "c1"
    assert result.partitions[0].name == "p1"

    service.get_table_metadata.return_value = {"success": False, "error": "missing"}
    err = ars.athena_table_schema(database="db", table="tbl", service=service)
    assert err.success is False
    assert "missing" in err.error


def test_athena_workgroups_list_success_and_exception(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
    service = Mock()
    service.list_workgroups.return_value = [{"name": "primary"}]

    result = ars.athena_workgroups_list(service=service)
    assert result.success is True
    assert result.region == "us-west-2"
    assert result.count == 1

    service.list_workgroups.side_effect = RuntimeError("wg-fail")
    err = ars.athena_workgroups_list(service=service)
    assert err.success is False
    assert "wg-fail" in err.error


def test_athena_query_execute_validation_errors():
    assert ars.athena_query_execute(query="")["success"] is False
    assert ars.athena_query_execute(query="SELECT * FROM `x`")["success"] is False
    assert ars.athena_query_execute(query="SELECT 1", max_results=0)["success"] is False
    assert ars.athena_query_execute(query="SELECT 1", output_format="xml")["success"] is False


def test_athena_query_execute_success_and_unsuccessful_result(monkeypatch: pytest.MonkeyPatch):
    service = Mock()
    service.execute_query.return_value = {"success": False, "error": "query-failed"}
    assert ars.athena_query_execute(query="SELECT 1", service=service)["error"] == "query-failed"

    service.execute_query.return_value = {"success": True, "rows": [{"a": 1}]}
    service.format_results.return_value = {"success": True, "formatted_data": [{"a": 1}], "format": "json"}
    monkeypatch.setattr(
        "quilt_mcp.utils.formatting.format_athena_results_as_table",
        lambda result: {**result, "table_enhanced": True},
    )

    result = ars.athena_query_execute(query="SELECT 1", service=service)
    assert result["success"] is True
    assert result["table_enhanced"] is True


@pytest.mark.parametrize(
    ("exc_msg", "query", "expected"),
    [
        ("missing glue:GetDatabase", "SELECT 1", "missing Glue permissions"),
        ("TABLE_NOT_FOUND: x", "SELECT * FROM x", "Table not found"),
        ("SCHEMA_NOT_FOUND: x", "SELECT * FROM x", "Database/schema not found"),
        ("mismatched input 'x' expecting", 'SELECT * FROM "db-x".t', "SQL syntax error"),
        ("not enough arguments for format string", "SELECT * FROM x WHERE y LIKE '%foo%'", "known issue"),
    ],
)
def test_athena_query_execute_exception_mapping(exc_msg: str, query: str, expected: str):
    service = Mock()
    service.execute_query.side_effect = RuntimeError(exc_msg)
    result = ars.athena_query_execute(query=query, service=service)
    assert result["success"] is False
    assert expected in result["error"]


def test_athena_query_execute_generic_exception_uses_suggestions():
    service = Mock()
    service.execute_query.side_effect = RuntimeError("mismatched input blah")
    result = ars.athena_query_execute(query='SELECT * FROM "db-with-dash".t', service=service)
    assert result["success"] is False
    assert "Suggestions:" in result["error"]


def test_athena_query_history_no_ids_and_filtered_entries():
    client = Mock()
    backend = Mock()
    backend.get_aws_client.return_value = client
    service = Mock()
    service.backend = backend

    client.list_query_executions.return_value = {"QueryExecutionIds": []}
    empty = ars.athena_query_history(service=service)
    assert empty.success is True
    assert empty.count == 0

    now = datetime.now(timezone.utc)
    client.list_query_executions.return_value = {"QueryExecutionIds": ["q1", "q2", "q3"]}
    client.batch_get_query_execution.return_value = {
        "QueryExecutions": [
            {
                "QueryExecutionId": "q1",
                "Query": "SELECT 1",
                "Status": {"State": "SUCCEEDED", "SubmissionDateTime": now, "CompletionDateTime": now},
                "Statistics": {"TotalExecutionTimeInMillis": 10, "DataScannedInBytes": 100},
                "ResultConfiguration": {"OutputLocation": "s3://x"},
                "WorkGroup": "primary",
                "QueryExecutionContext": {"Database": "db"},
            },
            {
                "QueryExecutionId": "q2",
                "Query": "SELECT 2",
                "Status": {"State": "FAILED", "SubmissionDateTime": now},
            },
            {
                "QueryExecutionId": "q3",
                "Query": "SELECT 3",
                "Status": {"State": "SUCCEEDED", "SubmissionDateTime": now - timedelta(days=10)},
            },
        ]
    }

    filtered = ars.athena_query_history(
        service=service,
        status_filter="SUCCEEDED",
        start_time=(now - timedelta(days=1)).isoformat(),
        end_time=(now + timedelta(hours=1)).isoformat(),
    )
    assert filtered.success is True
    assert filtered.count == 1
    assert filtered.query_history[0].query_execution_id == "q1"


def test_athena_query_history_exception_path():
    service = Mock()
    service.backend.get_aws_client.side_effect = RuntimeError("athena-down")
    result = ars.athena_query_history(service=service)
    assert result.success is False
    assert "athena-down" in result.error


def test_tabulator_list_buckets_success_passthrough_and_exception(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "quilt_mcp.services.athena_read_service.tabulator_query_execute",
        lambda _query: {
            "success": True,
            "formatted_data": [
                {"database_name": "db1"},
                {"db_name": "db2"},
                {"name": "db3"},
                {"other": "x"},
            ],
        },
    )
    result = ars.tabulator_list_buckets()
    assert result["success"] is True
    assert result["buckets"] == ["db1", "db2", "db3"]

    monkeypatch.setattr(
        "quilt_mcp.services.athena_read_service.tabulator_query_execute",
        lambda _query: {"success": False, "error": "nope"},
    )
    passthrough = ars.tabulator_list_buckets()
    assert passthrough["success"] is False

    def _explode(_query: str):
        raise RuntimeError("boom")

    monkeypatch.setattr("quilt_mcp.services.athena_read_service.tabulator_query_execute", _explode)
    err = ars.tabulator_list_buckets()
    assert err["success"] is False
    assert "boom" in err["error"]


def test_athena_query_validate_branches():
    assert ars.athena_query_validate("")["success"] is False
    assert ars.athena_query_validate("DROP TABLE x")["valid"] is False
    assert ars.athena_query_validate("BAD QUERY")["valid"] is False
    assert ars.athena_query_validate("SELECT * FROM `tbl`")["valid"] is False
    assert ars.athena_query_validate("SELECT (1")["valid"] is False
    assert ars.athena_query_validate("SELECT 1")["valid"] is False

    ok = ars.athena_query_validate("SELECT * FROM some_table")
    assert ok["success"] is True
    assert ok["valid"] is True
