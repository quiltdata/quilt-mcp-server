"""Ensure package operations rely on JWT authorization helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from quilt_mcp.tools import package_ops


class _FakeQuiltService:
    def __init__(self):
        self.calls = []

    def create_package_revision(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "top_hash": "deadbeef",
            "entries_added": len(kwargs.get("s3_uris", [])),
            "files": [],
        }

    def create_bucket(self, *_args, **_kwargs):
        return SimpleNamespace(search=lambda *_a, **_kw: [])

    def get_session(self):
        raise AssertionError("legacy quilt3 session should not be used")

    def has_session_support(self):
        return False


@pytest.fixture
def fake_service(monkeypatch):
    service = _FakeQuiltService()
    monkeypatch.setattr(package_ops, "quilt_service", service)
    return service


def test_package_create_invokes_jwt_authorization(monkeypatch, fake_service):
    captured = {}

    def fake_check(tool_name, tool_args):
        captured["tool"] = tool_name
        captured["args"] = tool_args
        return {
            "authorized": True,
            "s3_client": SimpleNamespace(),
            "quilt_api": SimpleNamespace(),
        }

    monkeypatch.setattr(package_ops, "check_package_authorization", fake_check)

    result = package_ops.package_create(
        package_name="user/dataset",
        s3_uris=["s3://quilt-sandbox/data.csv"],
    )

    assert result["status"] == "success"
    assert captured["tool"] == "package_create"
    assert captured["args"]["package_name"] == "user/dataset"
    assert fake_service.calls, "create_package_revision should be invoked"


def test_package_update_invokes_jwt_authorization(monkeypatch, fake_service):
    captured = {}

    def fake_check(tool_name, tool_args):
        captured["tool"] = tool_name
        captured["args"] = tool_args
        return {
            "authorized": True,
            "s3_client": SimpleNamespace(),
            "quilt_api": SimpleNamespace(),
        }

    class _FakePackage:
        def __contains__(self, key):
            return False

        def set(self, logical_path, uri):
            pass

        def push(self, *args, **kwargs):
            return "hash"

        def set_meta(self, *_args, **_kwargs):
            pass

        @property
        def meta(self):
            return {}

    monkeypatch.setattr(package_ops, "check_package_authorization", fake_check)
    monkeypatch.setattr(package_ops.QuiltService, "browse_package", lambda *_args, **_kwargs: _FakePackage())

    result = package_ops.package_update(
        package_name="user/dataset",
        s3_uris=["s3://quilt-sandbox/data.csv"],
    )

    assert result["status"] == "success"
    assert captured["tool"] == "package_update"
    assert captured["args"]["package_name"] == "user/dataset"

