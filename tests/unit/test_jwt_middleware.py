"""Unit tests for JWT middleware."""

from __future__ import annotations

import time

import jwt
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quilt_mcp.middleware.jwt_middleware import JwtAuthMiddleware
from quilt_mcp.runtime_context import get_runtime_auth, get_runtime_claims


def _encode(payload: dict, secret: str) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def _app() -> Starlette:
    async def handler(request):
        return JSONResponse({"claims": get_runtime_claims()})

    return Starlette(routes=[Route("/test", handler, methods=["POST"])])


def test_missing_authorization_header(monkeypatch):
    monkeypatch.setenv("MCP_JWT_SECRET", "test-secret")
    app = _app()
    app.add_middleware(JwtAuthMiddleware, require_jwt=True)

    client = TestClient(app)
    response = client.post("/test", json={})

    assert response.status_code == 401
    assert "jwt" in response.text.lower()


def test_invalid_token_rejected(monkeypatch):
    monkeypatch.setenv("MCP_JWT_SECRET", "test-secret")
    app = _app()
    app.add_middleware(JwtAuthMiddleware, require_jwt=True)

    client = TestClient(app)
    response = client.post("/test", json={}, headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == 403
    assert "invalid" in response.text.lower()


def test_valid_token_sets_runtime_auth(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)
    payload = {"sub": "user-1", "exp": int(time.time()) + 300}
    token = _encode(payload, secret)

    app = _app()
    app.add_middleware(JwtAuthMiddleware, require_jwt=True)

    client = TestClient(app)
    response = client.post("/test", json={}, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["claims"]["sub"] == "user-1"
    assert get_runtime_auth() is None
