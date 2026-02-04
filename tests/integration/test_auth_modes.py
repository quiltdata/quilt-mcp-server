"""Integration tests for IAM and JWT auth modes."""

from __future__ import annotations

from pathlib import Path
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quilt_mcp.middleware.jwt_middleware import JwtAuthMiddleware
from quilt_mcp.config import set_test_mode_config
from quilt_mcp.tools.auth_helpers import check_s3_authorization, check_package_authorization
from tests.jwt_helpers import get_sample_catalog_token


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
def test_jwt_mode_requires_valid_token(monkeypatch):
    secret = "test-secret"
    # Still need JWT secret for JWT testing
    monkeypatch.setenv("MCP_JWT_SECRET", secret)
    set_test_mode_config(multiuser_mode=True)

    async def handler(request):
        auth_ctx = check_package_authorization("auth_echo", {})
        return JSONResponse({"authorized": auth_ctx.authorized, "auth_type": auth_ctx.auth_type})

    app = Starlette(routes=[Route("/tool", handler, methods=["POST"])])
    app.add_middleware(JwtAuthMiddleware, require_jwt=True)
    client = TestClient(app)

    missing = client.post(
        "/tool",
        json={},
    )
    assert missing.status_code in {401, 403}

    token = get_sample_catalog_token()
    ok = client.post("/tool", json={}, headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200


@pytest.mark.integration
def test_jwt_mode_rejects_invalid_token(monkeypatch):
    secret = "test-secret"
    # Still need JWT secret for JWT testing
    monkeypatch.setenv("MCP_JWT_SECRET", secret)
    set_test_mode_config(multiuser_mode=True)

    async def handler(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/tool", handler, methods=["POST"])])
    app.add_middleware(JwtAuthMiddleware, require_jwt=True)
    client = TestClient(app)

    token = get_sample_catalog_token()
    token = token[:-1] + ("a" if token[-1] != "a" else "b")

    response = client.post("/tool", json={}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
