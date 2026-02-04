"""Unit tests for request context propagation helpers."""

from __future__ import annotations

import asyncio

import pytest

from quilt_mcp.context.exceptions import ContextNotAvailableError
from quilt_mcp.context.propagation import (
    get_current_context,
    reset_current_context,
    set_current_context,
)
from quilt_mcp.context.request_context import RequestContext


def _make_context(request_id: str) -> RequestContext:
    return RequestContext(
        request_id=request_id,
        user_id="user",
        auth_service=object(),
        permission_service=object(),
        workflow_service=object(),
    )


def test_set_and_get_current_context():
    context = _make_context("req-1")
    token = set_current_context(context)
    try:
        assert get_current_context() is context
    finally:
        reset_current_context(token)


def test_get_current_context_raises_when_missing():
    with pytest.raises(ContextNotAvailableError):
        get_current_context()


def test_context_is_cleared_after_reset():
    context = _make_context("req-2")
    token = set_current_context(context)
    reset_current_context(token)
    with pytest.raises(ContextNotAvailableError):
        get_current_context()


@pytest.mark.asyncio
async def test_context_is_async_safe():
    async def _run(request_id: str):
        context = _make_context(request_id)
        token = set_current_context(context)
        try:
            await asyncio.sleep(0)
            return get_current_context().request_id
        finally:
            reset_current_context(token)

    results = await asyncio.gather(_run("req-a"), _run("req-b"))
    assert set(results) == {"req-a", "req-b"}
