"""Unit tests for JWT auth service role assumption."""

from __future__ import annotations

import datetime
import time

import boto3
import pytest
from botocore.stub import Stubber

from quilt_mcp.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context
from quilt_mcp.services.jwt_auth_service import JwtAuthServiceError, JWTAuthService


def _assume_role_response() -> dict:
    return {
        "Credentials": {
            "AccessKeyId": "ASIA_TEST_ACCESS",
            "SecretAccessKey": "test-secret",
            "SessionToken": "token",
            "Expiration": datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        },
        "AssumedRoleUser": {
            "AssumedRoleId": "AROA1234567890:test",
            "Arn": "arn:aws:sts::123456789012:assumed-role/test/mcp-user",
        },
    }


def test_jwt_auth_requires_runtime_auth():
    service = JWTAuthService()
    with pytest.raises(JwtAuthServiceError) as excinfo:
        service.get_boto3_session()

    assert excinfo.value.code == "missing_jwt"


def test_jwt_auth_requires_role_arn(monkeypatch):
    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims={"sub": "user"})
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)
    try:
        service = JWTAuthService()
        with pytest.raises(JwtAuthServiceError) as excinfo:
            service.get_boto3_session()
        assert excinfo.value.code == "missing_role_arn"
    finally:
        reset_runtime_context(token_handle)


def test_jwt_auth_requires_sub(monkeypatch):
    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="token",
        claims={"role_arn": "arn:aws:iam::123456789012:role/TestRole"},
    )
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)
    try:
        service = JWTAuthService()
        with pytest.raises(JwtAuthServiceError) as excinfo:
            service.get_boto3_session()
        assert excinfo.value.code == "missing_sub"
    finally:
        reset_runtime_context(token_handle)


def test_jwt_auth_assumes_role(monkeypatch):
    fixed_time = 1700000000
    monkeypatch.setattr(time, "time", lambda: fixed_time)

    role_arn = "arn:aws:iam::123456789012:role/TestRole"
    claims = {
        "sub": "user-123",
        "role_arn": role_arn,
        "session_tags": {"team": "data"},
        "transitive_tag_keys": ["team"],
    }
    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims=claims)
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)

    sts_client = boto3.client("sts", region_name="us-east-1")
    stubber = Stubber(sts_client)
    expected_params = {
        "RoleArn": role_arn,
        "RoleSessionName": "mcp-user-123-1700000000",
        "DurationSeconds": 3600,
        "SourceIdentity": "user-123",
        "Tags": [{"Key": "team", "Value": "data"}],
        "TransitiveTagKeys": ["team"],
    }
    stubber.add_response("assume_role", _assume_role_response(), expected_params)
    stubber.activate()

    original_client = boto3.client
    monkeypatch.setattr(
        boto3,
        "client",
        lambda service, region_name=None: sts_client
        if service == "sts"
        else original_client(service, region_name=region_name),
    )

    try:
        service = JWTAuthService()
        session = service.get_boto3_session()
        credentials = session.get_credentials()
        assert credentials is not None
        assert credentials.access_key == "ASIA_TEST_ACCESS"

        # Second call should use cached session (no extra assume_role calls).
        session_again = service.get_boto3_session()
        assert session_again is session
    finally:
        stubber.deactivate()
        reset_runtime_context(token_handle)


def test_jwt_auth_handles_sts_failure(monkeypatch):
    role_arn = "arn:aws:iam::123456789012:role/TestRole"
    claims = {"sub": "user-123", "role_arn": role_arn}
    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims=claims)
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)

    sts_client = boto3.client("sts", region_name="us-east-1")
    stubber = Stubber(sts_client)
    stubber.add_client_error("assume_role", service_error_code="AccessDenied")
    stubber.activate()

    original_client = boto3.client
    monkeypatch.setattr(
        boto3,
        "client",
        lambda service, region_name=None: sts_client
        if service == "sts"
        else original_client(service, region_name=region_name),
    )

    try:
        service = JWTAuthService()
        with pytest.raises(JwtAuthServiceError) as excinfo:
            service.get_boto3_session()
        assert excinfo.value.code == "assume_role_failed"
    finally:
        stubber.deactivate()
        reset_runtime_context(token_handle)
