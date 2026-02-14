from __future__ import annotations

import contextlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest
from sqlalchemy.exc import SQLAlchemyError

from quilt_mcp.services.athena_service import AthenaQueryService


def _service_with_backend(backend: Mock | None = None) -> AthenaQueryService:
    return AthenaQueryService(backend=backend or Mock())


def test_get_workgroup_precedence_and_cache(monkeypatch: pytest.MonkeyPatch):
    svc = _service_with_backend()
    svc.workgroup_name = "explicit"
    assert svc._get_workgroup("us-east-1") == "explicit"

    svc2 = _service_with_backend()
    monkeypatch.setenv("ATHENA_WORKGROUP", "env-wg")
    assert svc2._get_workgroup("us-east-1") == "env-wg"
    monkeypatch.delenv("ATHENA_WORKGROUP")

    svc3 = _service_with_backend()
    svc3._discover_workgroup = lambda _region: "discovered"  # type: ignore[method-assign]
    got = svc3._get_workgroup("us-west-2")
    assert got == "discovered"
    svc3._discover_workgroup = lambda _region: "other"  # type: ignore[method-assign]
    assert svc3._get_workgroup("us-west-2") == "discovered"


def test_discover_workgroup_priority_and_fallback(monkeypatch: pytest.MonkeyPatch):
    svc = _service_with_backend()
    svc.list_workgroups = lambda: [  # type: ignore[method-assign]
        {"name": "primary", "output_location": "s3://x"},
        {"name": "quilt-team", "output_location": "s3://y"},
    ]
    assert svc._discover_workgroup("us-east-1") == "quilt-team"

    svc.list_workgroups = lambda: []  # type: ignore[method-assign]
    assert svc._discover_workgroup("us-east-1") == "primary"

    monkeypatch.setenv("ATHENA_WORKGROUP", "fallback-env")
    svc.list_workgroups = lambda: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[method-assign]
    assert svc._discover_workgroup("us-east-1") == "fallback-env"


def test_client_creation_fallbacks(monkeypatch: pytest.MonkeyPatch):
    backend = Mock()
    backend.get_aws_client.side_effect = RuntimeError("backend unavailable")
    svc = _service_with_backend(backend)

    monkeypatch.setattr("quilt_mcp.services.athena_service.boto3.client", lambda name, **_k: f"{name}-client")
    assert svc._create_glue_client() == "glue-client"
    assert svc._create_s3_client() == "s3-client"


def test_get_athena_credentials_success_and_none():
    creds = SimpleNamespace(access_key="AKIA", secret_key="SECRET", token="TOKEN")
    signer = SimpleNamespace(_credentials=creds)
    athena_client = SimpleNamespace(_request_signer=signer)
    backend = Mock()
    backend.get_aws_client.return_value = athena_client
    svc = _service_with_backend(backend)
    got = svc._get_athena_credentials("us-east-1")
    assert got is creds

    backend.get_aws_client.side_effect = RuntimeError("no client")
    assert svc._get_athena_credentials("us-east-1") is None


def test_create_sqlalchemy_engine_with_and_without_credentials(monkeypatch: pytest.MonkeyPatch):
    svc = _service_with_backend()
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")
    svc._get_workgroup = lambda _region: "wg"  # type: ignore[method-assign]
    monkeypatch.setattr(
        "quilt_mcp.services.athena_service.create_engine", lambda cs, echo=False: {"cs": cs, "echo": echo}
    )

    svc._get_athena_credentials = lambda **_k: None  # type: ignore[method-assign]
    e1 = svc._create_sqlalchemy_engine()
    assert "work_group=wg" in e1["cs"]
    assert "catalog_name=AwsDataCatalog" in e1["cs"]

    creds = SimpleNamespace(access_key="A", secret_key="S", token="T")
    svc._get_athena_credentials = lambda **_k: creds  # type: ignore[method-assign]
    e2 = svc._create_sqlalchemy_engine()
    assert "A:S@" in e2["cs"]
    assert "aws_session_token=T" in e2["cs"]


def test_discover_databases_and_tables_paths():
    svc = _service_with_backend()
    svc.execute_query = lambda *_a, **_k: {"success": False, "error": "q-fail"}  # type: ignore[method-assign]
    assert svc.discover_databases()["success"] is False
    assert svc.discover_tables("db")["success"] is False

    df_dbs = pd.DataFrame([["db1"], ["db2"]])
    svc.execute_query = lambda *_a, **_k: {"success": True, "data": df_dbs}  # type: ignore[method-assign]
    dbs = svc.discover_databases("AwsDataCatalog")
    assert dbs["success"] is True
    assert dbs["count"] == 2

    df_tbl = pd.DataFrame([["t1"], ["t2"]])
    svc.execute_query = lambda *_a, **_k: {"success": True, "data": df_tbl}  # type: ignore[method-assign]
    tbls = svc.discover_tables("db", table_pattern="t%")
    assert tbls["success"] is True
    assert tbls["count"] == 2
    assert tbls["tables"][0]["database_name"] == "db"


def test_get_table_metadata_parsing_and_error(monkeypatch: pytest.MonkeyPatch):
    class Cursor:
        def execute(self, _query):
            return None

        def fetchall(self):
            return [
                ("# header\tignored\t",),
                ("id\tbigint\tidentifier",),
                ("partition_date\tstring\tpart",),
                (" \t \t ",),
            ]

    class Conn:
        def cursor(self):
            return Cursor()

    fake_pyathena = SimpleNamespace(connect=lambda **_kwargs: Conn())
    monkeypatch.setitem(sys.modules, "pyathena", fake_pyathena)

    svc = _service_with_backend()
    svc._get_workgroup = lambda _region: "wg"  # type: ignore[method-assign]
    svc._get_athena_credentials = lambda **_k: None  # type: ignore[method-assign]
    meta = svc.get_table_metadata("db", "tbl")
    assert meta["success"] is True
    assert any(c["name"] == "id" for c in meta["columns"])
    assert any(p["name"] == "partition_date" for p in meta["partitions"])

    monkeypatch.setitem(
        sys.modules, "pyathena", SimpleNamespace(connect=lambda **_k: (_ for _ in ()).throw(RuntimeError("x")))
    )
    err = svc.get_table_metadata("db", "tbl")
    assert err["success"] is False


def test_execute_query_success_sqlalchemy_error_and_generic_error(monkeypatch: pytest.MonkeyPatch):
    svc = _service_with_backend()
    svc._base_connection_string = "awsathena://base"
    svc._engine = object()
    monkeypatch.setattr("quilt_mcp.services.athena_service.suppress_stdout", contextlib.nullcontext)
    monkeypatch.setattr("quilt_mcp.services.athena_service.create_engine", lambda *_a, **_k: object())

    df = pd.DataFrame({"a": [1, 2, 3]})
    monkeypatch.setattr("quilt_mcp.services.athena_service.pd.read_sql_query", lambda *_a, **_k: df)
    ok = svc.execute_query("SELECT 1", database_name="db", max_results=2)
    assert ok["success"] is True
    assert ok["truncated"] is True
    assert ok["row_count"] == 2
    assert ok["total_rows"] == "2+"

    monkeypatch.setattr(
        "quilt_mcp.services.athena_service.pd.read_sql_query",
        lambda *_a, **_k: (_ for _ in ()).throw(SQLAlchemyError("sql-bad")),
    )
    sql_err = svc.execute_query("SELECT 1")
    assert sql_err["success"] is False
    assert "SQL execution error" in sql_err["error"]

    monkeypatch.setattr(
        "quilt_mcp.services.athena_service.pd.read_sql_query",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    err = svc.execute_query("SELECT 1")
    assert err["success"] is False
    assert "Query execution failed" in err["error"]


def test_format_results_formats_and_error(monkeypatch: pytest.MonkeyPatch):
    svc = _service_with_backend()
    df = pd.DataFrame({"a": [1], "b": ["x"]})
    base = {"success": True, "data": df}

    json_res = svc.format_results(base, "json")
    assert json_res["format"] == "json"
    assert isinstance(json_res["formatted_data"], list)

    csv_res = svc.format_results(base, "csv")
    assert csv_res["format"] == "csv"
    assert "a,b" in csv_res["formatted_data"]

    monkeypatch.setattr("quilt_mcp.utils.formatting.format_as_table", lambda _x: "TABLE")
    table_res = svc.format_results(base, "table")
    assert table_res["formatted_data"] == "TABLE"

    monkeypatch.setattr(
        "pandas.DataFrame.to_parquet",
        lambda self, buffer, index=False: buffer.write(b"PARQUET"),
    )
    parquet_res = svc.format_results(base, "parquet")
    assert isinstance(parquet_res["formatted_data"], str)
    assert parquet_res["format"] == "parquet"

    monkeypatch.setattr("quilt_mcp.utils.formatting.should_use_table_format", lambda _x: True)
    monkeypatch.setattr("quilt_mcp.utils.formatting.format_as_table", lambda _x: "AUTO_TABLE")
    auto = svc.format_results(base, "json")
    assert auto["display_format"] == "table"
    assert auto["formatted_data_table"] == "AUTO_TABLE"

    passthrough = svc.format_results({"success": False}, "json")
    assert passthrough["success"] is False

    class BadDF:
        def to_dict(self, **_kwargs):
            raise RuntimeError("format-bad")

    err = svc.format_results({"success": True, "data": BadDF()}, "json")
    assert err["success"] is False
    assert "Failed to format results" in err["error"]


def test_list_workgroups_success_and_error(monkeypatch: pytest.MonkeyPatch):
    backend = Mock()
    client = Mock()
    backend.get_aws_client.return_value = client
    svc = _service_with_backend(backend)

    client.list_work_groups.return_value = {
        "WorkGroups": [
            {"Name": "disabled", "State": "DISABLED", "Description": "d"},
            {"Name": "zeta", "State": "ENABLED", "Description": "z"},
            {"Name": "quilt-alpha", "State": "ENABLED", "Description": "qa"},
        ]
    }
    client.get_work_group.side_effect = [
        {
            "WorkGroup": {
                "Description": "z-desc",
                "Configuration": {"ResultConfiguration": {"OutputLocation": "s3://z"}},
            }
        },
        RuntimeError("detail-fail"),
    ]

    rows = svc.list_workgroups()
    assert len(rows) == 2
    assert rows[0]["name"] == "quilt-alpha"
    assert rows[0]["description"] == "qa"  # fallback from list when detail call fails
    assert rows[1]["name"] == "zeta"
    assert rows[1]["output_location"] == "s3://z"

    backend.get_aws_client.side_effect = RuntimeError("athena-down")
    with pytest.raises(RuntimeError):
        svc.list_workgroups()
