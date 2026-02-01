"""Tests for tenant extraction helpers."""

from __future__ import annotations

from quilt_mcp.context.tenant_extraction import extract_tenant_id
from quilt_mcp.runtime_context import RuntimeAuthState


def test_extract_tenant_from_claims():
    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims={"tenant_id": "tenant-1"})
    assert extract_tenant_id(auth_state) == "tenant-1"


def test_extract_tenant_from_session_metadata():
    auth_state = RuntimeAuthState(
        scheme="IAM",
        extras={"session_metadata": {"tenant_id": "tenant-meta"}},
    )
    assert extract_tenant_id(auth_state) == "tenant-meta"


def test_extract_tenant_from_jwt(monkeypatch):
    class _StubDecoder:
        def decode(self, token: str):
            return {"tenant_id": "tenant-jwt"}

    monkeypatch.setattr(
        "quilt_mcp.context.tenant_extraction.get_jwt_decoder",
        lambda: _StubDecoder(),
    )

    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims={})
    assert extract_tenant_id(auth_state) == "tenant-jwt"


def test_extract_tenant_from_env(monkeypatch):
    monkeypatch.setenv("QUILT_TENANT_ID", "tenant-env")
    assert extract_tenant_id(None) == "tenant-env"
