"""Unit tests for AthenaQueryService engine configuration."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from quilt_mcp.services.athena_service import AthenaQueryService
from botocore.exceptions import ClientError


class FakeRow:
    def __init__(self, mapping):
        self._mapping = mapping
        self._values = tuple(mapping[key] for key in mapping)

    def __getitem__(self, index):
        return self._values[index]


class FakeResult:
    def __init__(self, rows, keys):
        self._rows = [FakeRow(row) for row in rows]
        self._keys = keys

    def fetchall(self):
        return self._rows

    def keys(self):
        return self._keys


class FakeConnection:
    def __init__(self, result):
        self._result = result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def exec_driver_sql(self, query):
        return self._result


class FakeEngine:
    def __init__(self, result):
        self._result = result

    def connect(self):
        return FakeConnection(self._result)


def _make_fake_credentials(access_key: str = "AKIA123", secret_key: str = "SECRET123", token: str | None = None):
    fake_creds = MagicMock()
    fake_creds.access_key = access_key
    fake_creds.secret_key = secret_key
    fake_creds.token = token
    fake_creds.get_frozen_credentials.return_value = fake_creds
    return fake_creds


@patch("quilt_mcp.services.athena_service.create_engine")
def test_engine_uses_workgroup_output_location(mock_create_engine):
    """Ensure the SQLAlchemy connection string respects workgroup output location."""

    service = AthenaQueryService(use_jwt_auth=False)

    fake_session = MagicMock()
    fake_session.get_credentials.return_value = _make_fake_credentials()

    with patch.object(service, "_build_boto3_session", return_value=fake_session), patch.object(
        service, "_determine_region", return_value="us-east-1"
    ), patch.object(
        service,
        "_discover_workgroup",
        return_value={"name": "analytics", "output_location": "s3://athena-results-bucket/path/"},
    ):
        service._create_sqlalchemy_engine()

    assert mock_create_engine.call_count == 1
    connection_string = mock_create_engine.call_args[0][0]
    assert "work_group=analytics" in connection_string
    assert "s3_staging_dir=s3%3A%2F%2Fathena-results-bucket%2Fpath%2F" in connection_string


@patch("quilt_mcp.services.athena_service.create_engine")
def test_engine_falls_back_to_env_staging_dir(mock_create_engine):
    """Ensure the engine uses configured staging directory when workgroup lacks one."""

    service = AthenaQueryService(use_jwt_auth=False)

    fake_session = MagicMock()
    fake_session.get_credentials.return_value = _make_fake_credentials()

    with patch.object(service, "_build_boto3_session", return_value=fake_session), patch.object(
        service, "_determine_region", return_value="us-east-1"
    ), patch.object(
        service, "_discover_workgroup", return_value={"name": "primary", "output_location": None}
    ), patch.dict(os.environ, {"ATHENA_QUERY_RESULT_LOCATION": "s3://custom-bucket/results/"}):
        service._create_sqlalchemy_engine()

    connection_string = mock_create_engine.call_args[0][0]
    assert "s3_staging_dir=s3%3A%2F%2Fcustom-bucket%2Fresults%2F" in connection_string


@patch("quilt_mcp.services.athena_service.create_engine")
def test_engine_derives_default_staging_dir_when_not_configured(mock_create_engine):
    """Ensure a deterministic default staging directory is constructed when not configured."""

    service = AthenaQueryService(use_jwt_auth=False)

    fake_session = MagicMock()
    fake_session.get_credentials.return_value = _make_fake_credentials()
    fake_sts_client = MagicMock()
    fake_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
    fake_session.client.return_value = fake_sts_client

    with patch.object(service, "_build_boto3_session", return_value=fake_session), patch.object(
        service, "_determine_region", return_value="us-west-2"
    ), patch.object(
        service, "_discover_workgroup", return_value={"name": "primary", "output_location": None}
    ), patch.dict(os.environ, {}, clear=True):
        service._create_sqlalchemy_engine()

    connection_string = mock_create_engine.call_args[0][0]
    expected = "s3_staging_dir=s3%3A%2F%2Faws-athena-query-results-123456789012-us-west-2%2F"
    assert expected in connection_string
    fake_session.client.assert_called_once_with("sts")


def test_get_table_metadata_uses_glue_columns():
    """Glue get_table response should be normalized into column metadata."""

    service = AthenaQueryService(use_jwt_auth=False)
    mock_glue = MagicMock()
    mock_glue.get_table.return_value = {
        "Table": {
            "StorageDescriptor": {
                "Columns": [
                    {"Name": "id", "Type": "string"},
                    {"Name": "value", "Type": "int", "Comment": "test"},
                ],
                "Location": "s3://bucket/path/",
                "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                "Compressed": False,
                "SerdeInfo": {"SerializationLibrary": "org.openx.data.jsonserde.JsonSerDe"},
            },
            "PartitionKeys": [{"Name": "date", "Type": "string"}],
            "TableType": "EXTERNAL_TABLE",
            "Description": "Sample table",
            "Owner": "owner",
            "CreateTime": "2024-01-01T00:00:00Z",
            "UpdateTime": "2024-02-01T00:00:00Z",
            "Parameters": {"classification": "json"},
        }
    }
    service._glue_client = mock_glue

    result = service.get_table_metadata("db", "table")

    assert result["success"] is True
    assert result["columns"][0]["name"] == "id"
    assert result["partitions"][0]["name"] == "date"
    assert result["storage_descriptor"]["location"] == "s3://bucket/path/"


def test_get_table_metadata_falls_back_to_describe():
    """When Glue access is denied, fallback DESCRIBE query should be used."""

    service = AthenaQueryService(use_jwt_auth=False)
    mock_glue = MagicMock()
    mock_glue.get_table.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "GetTable"
    )
    service._glue_client = mock_glue

    fake_result = FakeResult(
        rows=[{"col_name": "id", "data_type": "string", "comment": ""}],
        keys=("col_name", "data_type", "comment"),
    )
    service._engine = FakeEngine(fake_result)

    result = service.get_table_metadata("db", "table")

    assert result["success"] is True
    assert result["columns"][0]["name"] == "id"


def test_get_table_metadata_handles_missing_table():
    """EntityNotFoundException should return a formatted error."""

    service = AthenaQueryService(use_jwt_auth=False)
    mock_glue = MagicMock()
    mock_glue.get_table.side_effect = ClientError(
        {"Error": {"Code": "EntityNotFoundException", "Message": "not found"}}, "GetTable"
    )
    service._glue_client = mock_glue

    result = service.get_table_metadata("db", "table")

    assert result["success"] is False
    assert "Table not found" in result["error"]
