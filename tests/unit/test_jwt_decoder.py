"""Unit tests for JWT decoding and validation."""

from __future__ import annotations

import time

import jwt
import pytest

from quilt_mcp.services.jwt_decoder import JwtConfigError, JwtDecodeError, get_jwt_decoder


def _encode(payload: dict, secret: str) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def test_decode_valid_token(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)
    monkeypatch.delenv("MCP_JWT_ISSUER", raising=False)
    monkeypatch.delenv("MCP_JWT_AUDIENCE", raising=False)

    payload = {"sub": "user-1", "exp": int(time.time()) + 300}
    token = _encode(payload, secret)

    decoder = get_jwt_decoder()
    claims = decoder.decode(token)

    assert claims["sub"] == "user-1"


def test_decode_expired_token(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)

    payload = {"sub": "user-1", "exp": int(time.time()) - 10}
    token = _encode(payload, secret)

    decoder = get_jwt_decoder()
    with pytest.raises(JwtDecodeError) as excinfo:
        decoder.decode(token)

    assert excinfo.value.code == "token_expired"


def test_decode_invalid_signature(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)

    payload = {"sub": "user-1", "exp": int(time.time()) + 300}
    token = _encode(payload, "wrong-secret")

    decoder = get_jwt_decoder()
    with pytest.raises(JwtDecodeError) as excinfo:
        decoder.decode(token)

    assert excinfo.value.code == "invalid_signature"


def test_decode_requires_exp(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)

    payload = {"sub": "user-1"}
    token = _encode(payload, secret)

    decoder = get_jwt_decoder()
    with pytest.raises(JwtDecodeError) as excinfo:
        decoder.decode(token)

    assert excinfo.value.code == "invalid_token"


def test_decode_malformed_token(monkeypatch):
    monkeypatch.setenv("MCP_JWT_SECRET", "test-secret")
    decoder = get_jwt_decoder()

    with pytest.raises(JwtDecodeError) as excinfo:
        decoder.decode("not-a-jwt")

    assert excinfo.value.code == "invalid_token"


def test_decode_with_issuer_audience(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)
    monkeypatch.setenv("MCP_JWT_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("MCP_JWT_AUDIENCE", "quilt-mcp")

    payload = {
        "sub": "user-1",
        "exp": int(time.time()) + 300,
        "iss": "https://issuer.example.com",
        "aud": "quilt-mcp",
    }
    token = _encode(payload, secret)

    decoder = get_jwt_decoder()
    claims = decoder.decode(token)

    assert claims["aud"] == "quilt-mcp"


def test_decode_with_invalid_issuer(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)
    monkeypatch.setenv("MCP_JWT_ISSUER", "https://issuer.example.com")

    payload = {
        "sub": "user-1",
        "exp": int(time.time()) + 300,
        "iss": "https://other.example.com",
    }
    token = _encode(payload, secret)

    decoder = get_jwt_decoder()
    with pytest.raises(JwtDecodeError) as excinfo:
        decoder.decode(token)

    assert excinfo.value.code == "invalid_issuer"


def test_validate_config_requires_secret(monkeypatch):
    monkeypatch.delenv("MCP_JWT_SECRET", raising=False)
    monkeypatch.delenv("MCP_JWT_SECRET_SSM_PARAMETER", raising=False)

    decoder = get_jwt_decoder()
    with pytest.raises(JwtConfigError):
        decoder.validate_config()
