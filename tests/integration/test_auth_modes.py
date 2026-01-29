"""Integration tests for IAM and JWT auth modes."""

from __future__ import annotations

import time

import boto3
import jwt
import pytest
from botocore.stub import ANY, Stubber
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quilt_mcp.middleware.jwt_middleware import JwtAuthMiddleware
from quilt_mcp.services.auth_service import reset_auth_service
from quilt_mcp.tools.auth_helpers import check_s3_authorization


@pytest.mark.integration
def test_iam_mode_allows_requests(monkeypatch):
    monkeypatch.setenv("MCP_REQUIRE_JWT", "false")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    reset_auth_service()

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
def test_jwt_mode_requires_valid_token(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_REQUIRE_JWT", "true")
    monkeypatch.setenv("MCP_JWT_SECRET", secret)
    reset_auth_service()

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

    payload = {"sub": "user-1", "role_arn": "arn:aws:iam::123456789012:role/TestRole", "exp": int(time.time()) + 300}
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
