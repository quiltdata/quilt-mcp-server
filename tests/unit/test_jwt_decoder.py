"""Unit tests for JWT decoding and validation."""

from __future__ import annotations

import pytest

from quilt_mcp.services.jwt_decoder import JwtConfigError, JwtDecodeError, get_jwt_decoder
from tests.jwt_helpers import (
    get_expired_catalog_token,
    get_extra_claim_catalog_token,
    get_missing_exp_catalog_token,
    get_sample_catalog_claims,
    get_sample_catalog_token,
)


def test_decode_valid_token(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)
    monkeypatch.delenv("MCP_JWT_ISSUER", raising=False)
    monkeypatch.delenv("MCP_JWT_AUDIENCE", raising=False)

    token = get_sample_catalog_token()
    payload = get_sample_catalog_claims()
    decoder = get_jwt_decoder()
    claims = decoder.decode(token)

    assert claims["id"] == payload["id"]
    assert claims["uuid"] == payload["uuid"]


def test_decode_expired_token(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)
    token = get_expired_catalog_token()

    decoder = get_jwt_decoder()
    with pytest.raises(JwtDecodeError) as excinfo:
        decoder.decode(token)

    assert excinfo.value.code == "token_expired"


def test_decode_invalid_signature(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)

    token = get_sample_catalog_token()
    token = token[:-1] + ("a" if token[-1] != "a" else "b")

    decoder = get_jwt_decoder()
    with pytest.raises(JwtDecodeError) as excinfo:
        decoder.decode(token)

    assert excinfo.value.code == "invalid_signature"


def test_decode_requires_exp(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)

    token = get_missing_exp_catalog_token()

    decoder = get_jwt_decoder()
    with pytest.raises(JwtDecodeError) as excinfo:
        decoder.decode(token)

    assert excinfo.value.code == "invalid_token"


def test_decode_rejects_extra_claims(monkeypatch):
    secret = "test-secret"
    monkeypatch.setenv("MCP_JWT_SECRET", secret)

    token = get_extra_claim_catalog_token()

    decoder = get_jwt_decoder()
    with pytest.raises(JwtDecodeError) as excinfo:
        decoder.decode(token)

    assert excinfo.value.code == "invalid_claims"


def test_decode_malformed_token(monkeypatch):
    monkeypatch.setenv("MCP_JWT_SECRET", "test-secret")
    decoder = get_jwt_decoder()

    with pytest.raises(JwtDecodeError) as excinfo:
        decoder.decode("not-a-jwt")

    assert excinfo.value.code == "invalid_token"


def test_validate_config_requires_secret(monkeypatch):
    monkeypatch.delenv("MCP_JWT_SECRET", raising=False)
    monkeypatch.delenv("MCP_JWT_SECRET_SSM_PARAMETER", raising=False)

    decoder = get_jwt_decoder()
    with pytest.raises(JwtConfigError):
        decoder.validate_config()
