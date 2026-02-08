"""Unit tests for tool handler context integration."""

from __future__ import annotations

import pytest

from quilt_mcp.context.factory import RequestContextFactory
from quilt_mcp.context.handler import extract_auth_info, wrap_tool_with_context
from quilt_mcp.context.request_context import RequestContext


def test_tool_handler_injects_context():
    """Test that wrapper injects context as a keyword argument."""
    factory = RequestContextFactory(mode="single-user")

    def tool(*, context: RequestContext) -> str:
        return context.request_id

    wrapped = wrap_tool_with_context(tool, factory)
    request_id = wrapped()
    assert request_id


def test_tool_handler_injects_context_with_args():
    """Test that wrapper injects context alongside other arguments."""
    factory = RequestContextFactory(mode="single-user")

    def tool(bucket: str, *, context: RequestContext) -> str:
        return f"{bucket}:{context.request_id}"

    wrapped = wrap_tool_with_context(tool, factory)
    result = wrapped("my-bucket")
    assert result.startswith("my-bucket:")


def test_tool_handler_propagates_errors():
    """Test that wrapper propagates exceptions from the tool."""
    factory = RequestContextFactory(mode="single-user")

    def tool(*, context: RequestContext) -> None:
        _ = context.request_id
        raise RuntimeError("boom")

    wrapped = wrap_tool_with_context(tool, factory)
    with pytest.raises(RuntimeError, match="boom"):
        wrapped()


@pytest.mark.asyncio
async def test_tool_handler_injects_context_async():
    """Test that wrapper injects context for async functions."""
    factory = RequestContextFactory(mode="single-user")

    async def tool(*, context: RequestContext) -> str:
        return context.request_id

    wrapped = wrap_tool_with_context(tool, factory)
    request_id = await wrapped()
    assert request_id


def test_extract_auth_info_from_headers():
    auth = extract_auth_info({"Authorization": "Bearer token"})
    assert auth is not None
    assert auth.access_token == "token"

    assert extract_auth_info({"Authorization": "Basic xyz"}) is None
    assert extract_auth_info({}) is None
