"""Integration tests for auth service isolation."""

from __future__ import annotations

import asyncio

import pytest

from quilt_mcp.context.factory import RequestContextFactory
from quilt_mcp.runtime_context import RuntimeAuthState, push_runtime_context, reset_runtime_context


@pytest.mark.asyncio
async def test_concurrent_requests_have_isolated_auth_services():
    factory = RequestContextFactory(mode="single-user")

    async def _run(user_id: str):
        auth_state = RuntimeAuthState(
            scheme="Bearer",
            access_token=f"token-{user_id}",
            claims={"sub": user_id},
        )
        token_handle = push_runtime_context(environment="web-service", auth=auth_state)
        try:
            context = factory.create_context()
            identity = context.auth_service.get_user_identity()
            return context.auth_service, identity["user_id"]
        finally:
            reset_runtime_context(token_handle)

    results = await asyncio.gather(*[_run(f"user-{i}") for i in range(10)])
    services = {id(result[0]) for result in results}
    user_ids = {result[1] for result in results}

    assert len(services) == 10
    assert user_ids == {f"user-{i}" for i in range(10)}
