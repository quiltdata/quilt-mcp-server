"""Unit tests for auth helper functions."""

from __future__ import annotations

import pytest

from quilt_mcp.tools import auth_helpers
from quilt_mcp.context.propagation import reset_current_context, set_current_context
from quilt_mcp.context.request_context import RequestContext


def test_check_package_authorization_uses_passed_auth_service(monkeypatch):
    class StubAuthService:
        auth_type = "iam"

        def __init__(self) -> None:
            self.session = object()

        def get_boto3_session(self):
            return self.session

    stub = StubAuthService()

    def _unexpected_factory():
        raise AssertionError("create_auth_service should not be called when auth_service is provided")

    monkeypatch.setattr(auth_helpers, "create_auth_service", _unexpected_factory)

    context = auth_helpers.check_package_authorization("tool", {}, auth_service=stub)

    assert context.authorized is True
    assert context.auth_type == "iam"
    assert context.session is stub.session


def test_check_package_authorization_uses_context_auth_service(monkeypatch):
    class StubAuthService:
        auth_type = "iam"

        def __init__(self) -> None:
            self.session = object()

        def get_boto3_session(self):
            return self.session

        def get_user_identity(self):
            return {"user_id": "user-1"}

        def is_valid(self):
            return True

    stub = StubAuthService()
    request_context = RequestContext(
        request_id="req-1",
        user_id="user-1",
        auth_service=stub,
        permission_service=object(),
        workflow_service=object(),
    )

    def _unexpected_factory():
        raise AssertionError("create_auth_service should not be called when context is set")

    monkeypatch.setattr(auth_helpers, "create_auth_service", _unexpected_factory)

    token = set_current_context(request_context)
    try:
        context = auth_helpers.check_package_authorization("tool", {})
    finally:
        reset_current_context(token)

    assert context.authorized is True
    assert context.auth_type == "iam"
    assert context.session is stub.session


def test_check_s3_authorization_uses_passed_auth_service(monkeypatch):
    class StubSession:
        def __init__(self):
            self.client_calls = []

        def client(self, name: str):
            self.client_calls.append(name)
            return object()

    class StubAuthService:
        auth_type = "iam"

        def __init__(self) -> None:
            self.session = StubSession()

        def get_boto3_session(self):
            return self.session

    stub = StubAuthService()

    def _unexpected_factory():
        raise AssertionError("create_auth_service should not be called when auth_service is provided")

    monkeypatch.setattr(auth_helpers, "create_auth_service", _unexpected_factory)

    context = auth_helpers.check_s3_authorization("tool", {}, auth_service=stub)

    assert context.authorized is True
    assert context.auth_type == "iam"
    assert context.session is stub.session
    assert context.s3_client is not None
    assert stub.session.client_calls == ["s3"]
