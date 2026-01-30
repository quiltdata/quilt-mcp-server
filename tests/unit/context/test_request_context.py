"""Unit tests for RequestContext."""

from __future__ import annotations

import pytest

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


@pytest.mark.parametrize(
    ("request_id", "tenant_id", "auth_service", "expected_message"),
    [
        (None, "tenant-a", object(), "request_id"),
        ("req-1", None, object(), "tenant_id"),
        ("req-1", "tenant-a", None, "auth_service"),
    ],
)
def test_request_context_requires_required_fields(
    request_id, tenant_id, auth_service, expected_message
):
    with pytest.raises(TypeError) as excinfo:
        RequestContext(
            request_id=request_id,
            tenant_id=tenant_id,
            user_id="user-1",
            auth_service=auth_service,
            permission_service=object(),
            workflow_service=object(),
        )

    assert expected_message in str(excinfo.value)


def test_request_context_is_authenticated_reflects_auth_service():
    class StubAuthService:
        def __init__(self, valid: bool) -> None:
            self._valid = valid

        def is_valid(self) -> bool:
            return self._valid

    authenticated = RequestContext(
        request_id="req-1",
        tenant_id="tenant-a",
        user_id="user-1",
        auth_service=StubAuthService(True),
        permission_service=object(),
        workflow_service=object(),
    )
    unauthenticated = RequestContext(
        request_id="req-2",
        tenant_id="tenant-a",
        user_id=None,
        auth_service=StubAuthService(False),
        permission_service=object(),
        workflow_service=object(),
    )

    assert authenticated.is_authenticated is True
    assert unauthenticated.is_authenticated is False
