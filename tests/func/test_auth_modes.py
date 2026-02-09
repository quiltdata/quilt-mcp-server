"""Integration tests for IAM and JWT auth modes."""

from __future__ import annotations

from pathlib import Path
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quilt_mcp.config import set_test_mode_config
from quilt_mcp.tools.auth_helpers import check_s3_authorization


def test_iam_mode_allows_requests(monkeypatch):
    # Still need AWS credentials for IAM testing
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    set_test_mode_config(multiuser_mode=False)

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


def test_iam_mode_ignores_authorization_header(monkeypatch):
    # Still need AWS credentials for IAM testing
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    set_test_mode_config(multiuser_mode=False)

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


def test_iam_mode_allows_profile_credentials(monkeypatch, tmp_path: Path):
    credentials = tmp_path / "credentials"
    credentials.write_text(
        "[test]\naws_access_key_id = TESTKEY\naws_secret_access_key = TESTSECRET\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(credentials))
    monkeypatch.setenv("AWS_PROFILE", "test")
    set_test_mode_config(multiuser_mode=False)

    async def handler(request):
        auth_ctx = check_s3_authorization("auth_echo", {})
        return JSONResponse({"authorized": auth_ctx.authorized, "auth_type": auth_ctx.auth_type})

    app = Starlette(routes=[Route("/tool", handler, methods=["POST"])])
    client = TestClient(app)

    response = client.post("/tool", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["authorized"] is True
