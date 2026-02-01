"""Unit tests for IAMAuthService behavior."""

from __future__ import annotations

import sys
from types import ModuleType

import boto3

from quilt_mcp.services.iam_auth_service import IAMAuthService


def test_iam_auth_service_uses_quilt3_session_when_available(monkeypatch):
    session = boto3.Session()

    quilt3_stub = ModuleType("quilt3")
    quilt3_stub.logged_in = lambda: True
    quilt3_stub.get_boto3_session = lambda: session
    monkeypatch.delenv("QUILT_DISABLE_QUILT3_SESSION", raising=False)
    monkeypatch.setitem(sys.modules, "quilt3", quilt3_stub)

    service = IAMAuthService()
    assert service.get_session() is session


def test_iam_auth_service_falls_back_without_quilt3(monkeypatch):
    monkeypatch.delitem(sys.modules, "quilt3", raising=False)

    service = IAMAuthService()
    session = service.get_session()
    assert isinstance(session, boto3.Session)


def test_iam_auth_service_is_valid_false_when_credentials_missing(monkeypatch):
    class StubSession:
        def get_credentials(self):
            return None

    service = IAMAuthService()
    monkeypatch.setattr(service, "get_session", lambda: StubSession())
    assert service.is_valid() is False


def test_iam_auth_service_is_valid_true_when_credentials_present(monkeypatch):
    class StubSession:
        def get_credentials(self):
            return object()

    service = IAMAuthService()
    monkeypatch.setattr(service, "get_session", lambda: StubSession())
    assert service.is_valid() is True


def test_iam_auth_service_get_user_identity(monkeypatch):
    class StubStsClient:
        def get_caller_identity(self):
            return {"Arn": "arn:aws:iam::123456789012:user/test", "Account": "123456789012"}

    class StubSession:
        def client(self, name: str):
            assert name == "sts"
            return StubStsClient()

    service = IAMAuthService()
    monkeypatch.setattr(service, "get_session", lambda: StubSession())
    identity = service.get_user_identity()

    assert identity["user_id"] == "arn:aws:iam::123456789012:user/test"
    assert identity["account_id"] == "123456789012"
