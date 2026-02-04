"""Security tests for request-scoped credential isolation."""

from __future__ import annotations

import asyncio

import pytest

from quilt_mcp.context.factory import RequestContextFactory
from quilt_mcp.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context


@pytest.mark.asyncio
async def test_credentials_are_isolated_between_users():
    factory = RequestContextFactory(mode="single-user")

    async def _run(user_id: str):
        auth_state = RuntimeAuthState(
            scheme="Bearer",
            access_token=f"token-{user_id}",
            claims={"id": user_id},
        )
        token_handle = push_runtime_context(environment="web-service", auth=auth_state)
        try:
            context = factory.create_context()
            return context.auth_service.get_user_identity()
        finally:
            reset_runtime_context(token_handle)

    user_a, user_b = await asyncio.gather(_run("user-a"), _run("user-b"))
    assert user_a["user_id"] == "user-a"
    assert user_b["user_id"] == "user-b"


def test_credentials_cleared_after_request():
    factory = RequestContextFactory(mode="single-user")
    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="token",
        claims={"id": "user-1"},
    )
    token_handle = push_runtime_context(environment="web-service", auth=auth_state)
    try:
        context = factory.create_context()
        assert context.auth_service.get_user_identity()["user_id"] == "user-1"
    finally:
        reset_runtime_context(token_handle)

    assert context.auth_service.get_user_identity()["user_id"] is None
