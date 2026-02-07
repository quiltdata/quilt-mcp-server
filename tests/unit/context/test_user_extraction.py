"""Tests for user extraction helpers."""

from __future__ import annotations

from quilt_mcp.context.user_extraction import extract_user_id
from quilt_mcp.runtime_context import RuntimeAuthState


def test_extract_user_from_claims_id():
    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims={"id": "user-1"})
    assert extract_user_id(auth_state) == "user-1"


def test_extract_user_from_claims_uuid():
    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims={"uuid": "user-uuid"})
    assert extract_user_id(auth_state) == "user-uuid"


def test_extract_user_from_claims_sub():
    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims={"sub": "user-sub"})
    assert extract_user_id(auth_state) is None


def test_extract_user_accepts_extra_claims():
    """Test that extra claims are allowed (no validation, pure extraction)."""
    auth_state = RuntimeAuthState(scheme="Bearer", access_token="token", claims={"id": "user-1", "role": "admin"})
    assert extract_user_id(auth_state) == "user-1"
