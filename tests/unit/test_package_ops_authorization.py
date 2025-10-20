from __future__ import annotations

import pytest

from quilt_mcp.tools import packages
from quilt_mcp.tools.auth_helpers import AuthorizationContext


class FakeQuiltService:
    def __init__(self) -> None:
        self.calls: dict[str, dict] = {}

    def create_package_revision(self, **kwargs):
        self.calls["create_package_revision"] = kwargs
        return {
            "top_hash": "deadbeef",
            "entries_added": len(kwargs.get("s3_uris", [])),
            "files": kwargs.get("s3_uris", []),
        }


@pytest.fixture
def fake_service(monkeypatch):
    service = FakeQuiltService()
    monkeypatch.setattr(packages, "quilt_service", service)
    return service


def _authorized_context(auth_type: str = "jwt") -> AuthorizationContext:
    return AuthorizationContext(authorized=True, auth_type=auth_type, session=None, s3_client=None)


def test_package_create_attaches_auth_type(monkeypatch, fake_service):
    monkeypatch.setattr(packages, "check_package_authorization", lambda *_, **__: _authorized_context("jwt"))

    result = packages.package_create(
        package_name="team/example",
        s3_uris=["s3://bucket/object"],
    )

    assert result["auth_type"] == "jwt"
    assert result["status"] == "success"
    assert fake_service.calls["create_package_revision"]["package_name"] == "team/example"


def test_package_create_respects_strict_mode(monkeypatch, fake_service):
    strict_ctx = AuthorizationContext(
        authorized=False,
        auth_type=None,
        session=None,
        s3_client=None,
        error="JWT required",
        strict=True,
    )
    monkeypatch.setattr(packages, "check_package_authorization", lambda *_, **__: strict_ctx)

    result = packages.package_create(
        package_name="team/example",
        s3_uris=["s3://bucket/object"],
    )

    assert result["error"] == "JWT required"
    assert result["strict_mode"] is True
