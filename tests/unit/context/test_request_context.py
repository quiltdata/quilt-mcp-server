"""Unit tests for RequestContext."""

from __future__ import annotations

from quilt_mcp.context.request_context import RequestContext


def test_request_context_stores_fields():
    context = RequestContext(
        request_id="req-1",
        tenant_id="tenant-a",
        user_id="user-1",
        auth_service=object(),
        permission_service=object(),
        workflow_service=object(),
    )

    assert context.request_id == "req-1"
    assert context.tenant_id == "tenant-a"
    assert context.user_id == "user-1"
