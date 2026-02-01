"""Integration tests for IAM and JWT auth modes."""

from __future__ import annotations

import time
from pathlib import Path

import boto3
import jwt
import pytest
from botocore.stub import ANY, Stubber
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quilt_mcp.middleware.jwt_middleware import JwtAuthMiddleware
from quilt_mcp.config import set_test_mode_config
from quilt_mcp.tools.auth_helpers import check_s3_authorization


@pytest.mark.integration
def test_iam_mode_allows_requests(monkeypatch):
    # Still need AWS credentials for IAM testing
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    set_test_mode_config(multitenant_mode=False)

    async def handler(request):
        auth_ctx = check_s3_authorization("auth_echo", {})
        return JSONResponse({"authorized": auth_ctx.authorized, "auth_type": auth_ctx.auth_type})

    app = Starlette(routes=[Route("/tool", handler, methods=["POST"])])
    client = TestClient(app)

    response = client.post(
        "/tool",
        json={},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["authorized"] is True


@pytest.mark.integration
def test_iam_mode_ignores_authorization_header(monkeypatch):
    # Still need AWS credentials for IAM testing
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    set_test_mode_config(multitenant_mode=False)

    async def handler(request):
        auth_ctx = check_s3_authorization("auth_echo", {})
        return JSONResponse({"authorized": auth_ctx.authorized, "auth_type": auth_ctx.auth_type})

    app = Starlette(routes=[Route("/tool", handler, methods=["POST"])])
    client = TestClient(app)

    response = client.post(
        "/tool",
        json={},
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["authorized"] is True
    assert body["auth_type"] == "iam"


@pytest.mark.integration
def test_iam_mode_allows_profile_credentials(monkeypatch, tmp_path: Path):
    credentials = tmp_path / "credentials"
    credentials.write_text(
        "[test]\naws_access_key_id = TESTKEY\naws_secret_access_key = TESTSECRET\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(credentials))
    monkeypatch.setenv("AWS_PROFILE", "test")
    set_test_mode_config(multitenant_mode=False)

    async def handler(request):
        auth_ctx = check_s3_authorization("auth_echo", {})
        return JSONResponse({"authorized": auth_ctx.authorized, "auth_type": auth_ctx.auth_type})

    app = Starlette(routes=[Route("/tool", handler, methods=["POST"])])
    client = TestClient(app)

    response = client.post("/tool", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["authorized"] is True


@pytest.mark.integration
def test_jwt_mode_requires_valid_token(monkeypatch):
    secret = "test-secret"
    # Still need JWT secret for JWT testing
    monkeypatch.setenv("MCP_JWT_SECRET", secret)
    set_test_mode_config(multitenant_mode=True)

    async def handler(request):
        auth_ctx = check_s3_authorization("auth_echo", {})
        return JSONResponse({"authorized": auth_ctx.authorized, "auth_type": auth_ctx.auth_type})

    app = Starlette(routes=[Route("/tool", handler, methods=["POST"])])
    app.add_middleware(JwtAuthMiddleware, require_jwt=True)
    client = TestClient(app)

    missing = client.post(
        "/tool",
        json={},
    )
    assert missing.status_code in {401, 403}

    payload = {
        "sub": "user-1",
        "role_arn": "arn:aws:iam::123456789012:role/TestRole",
        "session_tags": {"team": "data"},
        "transitive_tag_keys": ["team"],
        "exp": int(time.time()) + 300,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")

    sts_client = boto3.client("sts", region_name="us-east-1")
    stubber = Stubber(sts_client)
    stubber.add_response(
        "assume_role",
        {
            "Credentials": {
                "AccessKeyId": "ASIA_TEST_ACCESS",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
                "Expiration": time.time() + 3600,
            }
        },
        {
            "RoleArn": payload["role_arn"],
            "RoleSessionName": ANY,
            "DurationSeconds": 3600,
            "SourceIdentity": "user-1",
            "Tags": [{"Key": "team", "Value": "data"}],
            "TransitiveTagKeys": ["team"],
        },
    )
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
        ok = client.post("/tool", json={}, headers={"Authorization": f"Bearer {token}"})
    finally:
        stubber.deactivate()

    assert ok.status_code == 200


@pytest.mark.integration
def test_jwt_mode_rejects_invalid_token(monkeypatch):
    secret = "test-secret"
    # Still need JWT secret for JWT testing
    monkeypatch.setenv("MCP_JWT_SECRET", secret)
    set_test_mode_config(multitenant_mode=True)

    async def handler(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/tool", handler, methods=["POST"])])
    app.add_middleware(JwtAuthMiddleware, require_jwt=True)
    client = TestClient(app)

    payload = {"sub": "user-1", "exp": int(time.time()) + 300}
    token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

    response = client.post("/tool", json={}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
