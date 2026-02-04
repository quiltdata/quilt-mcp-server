"""Unit tests for permission service context access in tools."""

from __future__ import annotations

from quilt_mcp.context.propagation import reset_current_context, set_current_context
from quilt_mcp.context.request_context import RequestContext
from quilt_mcp.tools import error_recovery, packages


def test_packages_uses_context_permission_service():
    sentinel = object()
    context = RequestContext(
        request_id="req-1",
        user_id="user-1",
        auth_service=object(),
        permission_service=sentinel,
        workflow_service=object(),
    )

    token = set_current_context(context)
    try:
        assert packages._current_permission_service() is sentinel
    finally:
        reset_current_context(token)


def test_error_recovery_uses_context_permission_service():
    sentinel = object()
    context = RequestContext(
        request_id="req-2",
        user_id="user-1",
        auth_service=object(),
        permission_service=sentinel,
        workflow_service=object(),
    )

    token = set_current_context(context)
    try:
        assert error_recovery._current_permission_service() is sentinel
    finally:
        reset_current_context(token)
