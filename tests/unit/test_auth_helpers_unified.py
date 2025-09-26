"""Tests for JWT-driven tool authorization helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from quilt_mcp.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context
from quilt_mcp.tools.auth_helpers import check_s3_authorization


@pytest.fixture
def boto3_session(mock_s3_client: Mock) -> Mock:
    session = Mock(name="boto3_session")
    session.client.return_value = mock_s3_client
    session.region_name = "us-east-1"
    return session


@pytest.fixture
def mock_s3_client() -> Mock:
    return Mock(name="s3_client")


def _runtime_token(claims: dict, aws_credentials: dict | None = None):
    auth_state = RuntimeAuthState(
        scheme="jwt",
        access_token="token",
        claims=claims,
        extras={"aws_credentials": aws_credentials or {}},
    )
    return push_runtime_context(environment="web-jwt", auth=auth_state)


@patch("quilt_mcp.services.bearer_auth_service.boto3.Session")
def test_s3_authorization_succeeds_with_bucket_and_permission(session_cls, boto3_session, mock_s3_client):
    session_cls.return_value = boto3_session
    claims = {
        "permissions": ["s3:ListBucket", "s3:GetObject", "s3:GetBucketLocation"],
        "buckets": ["quilt-sandbox"],
        "roles": ["ReadOnlyQuilt"],
    }
    aws_creds = {
        "access_key_id": "AKIA123",
        "secret_access_key": "secret",
        "session_token": "token",
        "region": "us-east-1",
    }

    token = _runtime_token(claims, aws_creds)
    try:
        result = check_s3_authorization("bucket_objects_list", {"bucket_name": "quilt-sandbox"})
    finally:
        reset_runtime_context(token)

    assert result["authorized"] is True
    assert result["s3_client"] is mock_s3_client


def test_s3_authorization_fails_without_bucket_access():
    claims = {
        "permissions": ["s3:ListBucket", "s3:GetObject", "s3:GetBucketLocation"],
        "buckets": ["quilt-sandbox"],
        "roles": ["ReadOnlyQuilt"],
    }
    token = _runtime_token(claims)

    try:
        result = check_s3_authorization("bucket_objects_list", {"bucket_name": "other-bucket"})
    finally:
        reset_runtime_context(token)

    assert result["authorized"] is False
    assert "Access denied" in result["error"]


def test_s3_authorization_fails_without_permission():
    claims = {
        "permissions": ["s3:GetObject"],  # Missing ListBucket
        "buckets": ["quilt-sandbox"],
        "roles": ["ReadOnlyQuilt"],
    }
    token = _runtime_token(claims)

    try:
        result = check_s3_authorization("bucket_objects_list", {"bucket_name": "quilt-sandbox"})
    finally:
        reset_runtime_context(token)

    assert result["authorized"] is False
    assert "Missing required permission" in result["error"]

