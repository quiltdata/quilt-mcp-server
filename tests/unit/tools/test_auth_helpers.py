"""Unit tests for auth helper functions."""

from __future__ import annotations

import pytest

from quilt_mcp.tools import auth_helpers


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
