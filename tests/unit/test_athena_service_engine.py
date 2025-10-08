"""Unit tests for AthenaQueryService engine configuration."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from quilt_mcp.services.athena_service import AthenaQueryService


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
