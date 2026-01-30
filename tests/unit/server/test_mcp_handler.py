"""Unit tests for tool handler context integration."""

from __future__ import annotations

import pytest

from quilt_mcp.context.exceptions import ContextNotAvailableError
from quilt_mcp.context.factory import RequestContextFactory
from quilt_mcp.context.handler import extract_auth_info, wrap_tool_with_context
from quilt_mcp.context.propagation import get_current_context


def test_tool_handler_creates_and_clears_context():
    factory = RequestContextFactory(mode="single-user")

    def tool() -> str:
        return get_current_context().request_id

    wrapped = wrap_tool_with_context(tool, factory)
    request_id = wrapped()
    assert request_id

    with pytest.raises(ContextNotAvailableError):
        get_current_context()


def test_tool_handler_cleans_up_on_error():
    factory = RequestContextFactory(mode="single-user")

    def tool() -> None:
        _ = get_current_context().request_id
        raise RuntimeError("boom")

    wrapped = wrap_tool_with_context(tool, factory)
    with pytest.raises(RuntimeError):
        wrapped()

    with pytest.raises(ContextNotAvailableError):
        get_current_context()


def test_extract_auth_info_from_headers():
    auth = extract_auth_info({"Authorization": "Bearer token"})
    assert auth is not None
    assert auth.access_token == "token"

    assert extract_auth_info({"Authorization": "Basic xyz"}) is None
    assert extract_auth_info({}) is None
