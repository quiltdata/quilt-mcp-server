"""Unit tests for JWTAuthService behavior."""

from __future__ import annotations

import time

import pytest

from quilt_mcp.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context
from quilt_mcp.services.jwt_decoder import JwtDecodeError
from quilt_mcp.services.jwt_auth_service import JWTAuthService


def test_jwt_auth_service_is_valid_false_without_auth():
    service = JWTAuthService()
    assert service.is_valid() is False


def test_jwt_auth_service_is_valid_respects_expiration(monkeypatch):
    now = 1_700_000_000
    monkeypatch.setattr(time, "time", lambda: now)

    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="token",
        claims={"sub": "user-1", "exp": now + 60},
    )
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)
    try:
        service = JWTAuthService()
        assert service.is_valid() is True
    finally:
        reset_runtime_context(token_handle)

    expired_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="token",
        claims={"sub": "user-1", "exp": now - 1},
    )
    token_handle = push_runtime_context(environment="web-service", auth=expired_state)
    try:
        service = JWTAuthService()
        assert service.is_valid() is False
    finally:
        reset_runtime_context(token_handle)


def test_jwt_auth_service_is_valid_false_on_invalid_token(monkeypatch):
    class StubDecoder:
        def decode(self, token: str) -> dict:
            raise JwtDecodeError("invalid_jwt", "Bad token")

    monkeypatch.setattr("quilt_mcp.services.jwt_auth_service.get_jwt_decoder", lambda: StubDecoder())

    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims=None)
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)
    try:
        service = JWTAuthService()
        assert service.is_valid() is False
    finally:
        reset_runtime_context(token_handle)


def test_jwt_auth_service_get_user_identity_from_claims():
    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="token",
        claims={"sub": "user-1", "email": "user@example.com"},
    )
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)
    try:
        service = JWTAuthService()
        identity = service.get_user_identity()
    finally:
        reset_runtime_context(token_handle)

    assert identity["user_id"] == "user-1"
    assert identity["email"] == "user@example.com"


def test_jwt_auth_service_get_user_identity_decodes_token(monkeypatch):
    class StubDecoder:
        def decode(self, token: str) -> dict:
            return {"sub": "user-2", "email": "decoded@example.com"}

    monkeypatch.setattr("quilt_mcp.services.jwt_auth_service.get_jwt_decoder", lambda: StubDecoder())

    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims=None)
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)
    try:
        service = JWTAuthService()
        identity = service.get_user_identity()
    finally:
        reset_runtime_context(token_handle)

    assert identity["user_id"] == "user-2"
    assert identity["email"] == "decoded@example.com"
