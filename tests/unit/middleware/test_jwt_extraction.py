"""Unit tests for JWT extraction middleware behavior."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quilt_mcp.context.runtime_context import get_runtime_access_token
from quilt_mcp.middleware.jwt_extraction import JwtExtractionMiddleware


async def _token_echo_endpoint(_request):
    return JSONResponse({"token": get_runtime_access_token()})


def _build_client(require_jwt: bool = True) -> TestClient:
    app = Starlette(routes=[Route("/mcp", _token_echo_endpoint)])
    app.add_middleware(JwtExtractionMiddleware, require_jwt=require_jwt)
    return TestClient(app)


def test_missing_authorization_header_returns_401(monkeypatch):
    monkeypatch.delenv("QUILT_FALLBACK_JWT", raising=False)
    client = _build_client(require_jwt=True)

    response = client.get("/mcp")

    assert response.status_code == 401
    assert response.json()["error"] == "JWT authentication required. Provide Authorization: Bearer header."


def test_uses_fallback_jwt_when_header_missing(monkeypatch):
    monkeypatch.setenv("QUILT_FALLBACK_JWT", "fallback-token")
    client = _build_client(require_jwt=True)

    response = client.get("/mcp")

    assert response.status_code == 200
    assert response.json() == {"token": "fallback-token"}


def test_authorization_header_takes_precedence_over_fallback(monkeypatch):
    monkeypatch.setenv("QUILT_FALLBACK_JWT", "fallback-token")
    client = _build_client(require_jwt=True)

    response = client.get("/mcp", headers={"Authorization": "Bearer header-token"})

    assert response.status_code == 200
    assert response.json() == {"token": "header-token"}


def test_invalid_authorization_header_rejected_even_with_fallback(monkeypatch):
    monkeypatch.setenv("QUILT_FALLBACK_JWT", "fallback-token")
    client = _build_client(require_jwt=True)

    response = client.get("/mcp", headers={"Authorization": "Basic abc"})

    assert response.status_code == 401
    assert response.json()["error"] == "Invalid Authorization header. Expected Bearer token."


def test_empty_bearer_token_rejected(monkeypatch):
    monkeypatch.delenv("QUILT_FALLBACK_JWT", raising=False)
    client = _build_client(require_jwt=True)

    response = client.get("/mcp", headers={"Authorization": "Bearer   "})

    assert response.status_code == 401
    assert response.json()["error"] == "JWT authentication required. Provide Authorization: Bearer header."


def test_health_endpoints_bypass_jwt_requirement(monkeypatch):
    monkeypatch.delenv("QUILT_FALLBACK_JWT", raising=False)
    app = Starlette(
        routes=[
            Route("/", _token_echo_endpoint),
            Route("/health", _token_echo_endpoint),
            Route("/healthz", _token_echo_endpoint),
        ]
    )
    app.add_middleware(JwtExtractionMiddleware, require_jwt=True)
    client = TestClient(app)

    # All health endpoints should work without JWT
    for path in ["/", "/health", "/healthz"]:
        response = client.get(path)
        assert response.status_code == 200, f"Failed for {path}"
        assert response.json() == {"token": None}


def test_require_jwt_false_bypasses_jwt_requirement(monkeypatch):
    monkeypatch.delenv("QUILT_FALLBACK_JWT", raising=False)
    client = _build_client(require_jwt=False)

    response = client.get("/mcp")

    assert response.status_code == 200
    assert response.json() == {"token": None}
