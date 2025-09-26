"""JWT-only middleware behaviour tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastmcp import FastMCP
from starlette.testclient import TestClient
from starlette.responses import JSONResponse

from quilt_mcp.utils import build_http_app


TEST_SECRET = "test-secret"
TEST_KID = "test-kid"


def _make_token(**overrides: Any) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": "user-123",
        "username": "test-user",
        "permissions": ["s3:ListBucket", "s3:GetObject"],
        "buckets": ["quilt-sandbox"],
        "roles": ["ReadOnlyQuilt"],
        "aws_role_arn": "arn:aws:iam::123456789012:role/QuiltReadOnly",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "scope": "read",
        "level": "read",
    }
    payload.update(overrides)
    headers = {"kid": TEST_KID, "typ": "JWT", "alg": "HS256"}
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256", headers=headers)


@pytest.fixture(autouse=True)
def configure_secret(monkeypatch):
    monkeypatch.setenv("MCP_ENHANCED_JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("MCP_ENHANCED_JWT_KID", TEST_KID)
    # Reset cached auth service so patched secrets take effect
    import quilt_mcp.services.bearer_auth_service as bas
    bas._auth_service = None
    yield


@pytest.fixture
def jwt_app():
    mcp = FastMCP("test-jwt")

    @mcp.tool()
    def noop() -> str:
        """Simple tool to ensure MPC setup"""
        return "ok"

    app = build_http_app(mcp, transport="http")

    async def secure_endpoint(request):
        from quilt_mcp.runtime_context import get_runtime_environment, get_runtime_claims

        return JSONResponse(
            {
                "environment": get_runtime_environment(),
                "claims": get_runtime_claims(),
            }
        )

    app.router.add_route("/secure", secure_endpoint, methods=["GET"])

    return app


def test_missing_authorization_header_returns_401(jwt_app):
    with TestClient(jwt_app) as client:
        response = client.get("/secure")

    assert response.status_code == 401
    body = response.json()
    assert body["error"] == "missing_authorization"
    assert body["detail"].startswith("Bearer token required")


def test_invalid_token_signature_returns_401(jwt_app):
    bad_token = _make_token()

    with TestClient(jwt_app) as client:
        response = client.get(
            "/secure",
            headers={"Authorization": f"Bearer {bad_token}wrong"},
        )

    assert response.status_code == 401
    body = response.json()
    assert body["error"] == "invalid_token"


def test_valid_token_sets_runtime_context(jwt_app):
    token = _make_token()

    with TestClient(jwt_app) as client:
        response = client.get(
            "/secure",
            headers={"Authorization": f"Bearer {token}"},
        )

    body = response.json()
    assert response.status_code == 200, body
    payload = response.json()
    assert payload["environment"] == "web-jwt"
    claims = payload["claims"]
    assert claims["permissions"] == ["s3:ListBucket", "s3:GetObject"]
    assert claims["buckets"] == ["quilt-sandbox"]
    assert claims["roles"] == ["ReadOnlyQuilt"]

