"""Behavior tests for JWT-enforced bucket tools."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from quilt_mcp.tools import buckets


def _boom(*_args, **_kwargs):
    raise AssertionError("get_s3_client should not be called when JWT auth is active")


class _FakeS3Client:
    def __init__(self) -> None:
        self.called = False

    def list_objects_v2(self, **kwargs):
        self.called = True
        return {
            "Contents": [
                {
                    "Key": "dataset/file.csv",
                    "Size": 123,
                    "LastModified": "2024-01-01T00:00:00Z",
                    "ETag": "etag",
                    "StorageClass": "STANDARD",
                }
            ],
            "IsTruncated": False,
            "KeyCount": 1,
        }


class _FakeHeadClient:
    def __init__(self) -> None:
        self.calls = []

    def head_object(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "ContentLength": 42,
            "ContentType": "text/plain",
            "ETag": "etag",
            "LastModified": "2024-01-01T00:00:00Z",
            "Metadata": {"owner": "user"},
            "StorageClass": "STANDARD",
            "CacheControl": "no-cache",
        }

    def generate_presigned_url(self, *_args, **_kwargs):
        self.calls.append(("presign", _args, _kwargs))
        return "https://example.com"


class _FakeBody:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, _size: int) -> bytes:
        return self._payload


class _FakeGetClient:
    def __init__(self, payload: bytes) -> None:
        self.calls = []
        self._payload = payload

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "Body": _FakeBody(self._payload),
            "ContentType": "text/plain",
        }


class _FakePutClient:
    def __init__(self) -> None:
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)
        return {"ETag": "etag"}


def test_bucket_objects_list_requires_jwt_authorization(monkeypatch):
    fake_client = _FakeS3Client()
    captured = {}

    def fake_check(tool_name, tool_args):
        captured["tool"] = tool_name
        captured["args"] = tool_args
        return {"authorized": True, "s3_client": fake_client}

    monkeypatch.setattr("quilt_mcp.tools.buckets.check_s3_authorization", fake_check, raising=False)
    monkeypatch.setattr("quilt_mcp.tools.buckets.get_s3_client", _boom, raising=False)

    result = buckets.bucket_objects_list("quilt-sandbox", include_signed_urls=False)

    assert captured["tool"] == "bucket_objects_list"
    assert captured["args"]["bucket_name"] == "quilt-sandbox"
    assert fake_client.called is True
    assert result["bucket"] == "quilt-sandbox"
    assert result["objects"][0]["key"] == "dataset/file.csv"


def test_bucket_object_info_uses_jwt_authorization(monkeypatch):
    fake_client = _FakeHeadClient()
    captured = {}

    def fake_check(tool_name, tool_args):
        captured["tool"] = tool_name
        captured["args"] = tool_args
        return {"authorized": True, "s3_client": fake_client}

    monkeypatch.setattr("quilt_mcp.tools.buckets.check_s3_authorization", fake_check, raising=False)
    monkeypatch.setattr("quilt_mcp.tools.buckets.get_s3_client", _boom, raising=False)

    result = buckets.bucket_object_info("s3://quilt-sandbox/data.csv")

    assert captured["tool"] == "bucket_object_info"
    assert captured["args"]["bucket_name"] == "quilt-sandbox"
    assert fake_client.calls
    assert result["bucket"] == "quilt-sandbox"
    assert result["key"] == "data.csv"


def test_bucket_object_text_uses_jwt_authorization(monkeypatch):
    payload = b"hello world"
    fake_client = _FakeGetClient(payload)
    captured = {}

    def fake_check(tool_name, tool_args):
        captured["tool"] = tool_name
        captured["args"] = tool_args
        return {"authorized": True, "s3_client": fake_client}

    monkeypatch.setattr("quilt_mcp.tools.buckets.check_s3_authorization", fake_check, raising=False)
    monkeypatch.setattr("quilt_mcp.tools.buckets.get_s3_client", _boom, raising=False)

    result = buckets.bucket_object_text("s3://quilt-sandbox/data.csv", max_bytes=64)

    assert captured["tool"] == "bucket_object_text"
    assert captured["args"]["bucket_name"] == "quilt-sandbox"
    assert fake_client.calls
    assert result["text"] == "hello world"


def test_bucket_authorization_without_client_returns_error(monkeypatch):
    def fake_check(tool_name, tool_args):
        return {"authorized": True}

    monkeypatch.setattr("quilt_mcp.tools.buckets.check_s3_authorization", fake_check, raising=False)
    monkeypatch.setattr("quilt_mcp.tools.buckets.get_s3_client", _boom, raising=False)

    result = buckets.bucket_objects_list("quilt-sandbox", include_signed_urls=False)

    assert result["success"] is False
    assert "S3 client" in result["error"]


def test_bucket_authorization_failure_does_not_fallback(monkeypatch):
    def fake_check(tool_name, tool_args):
        return {"authorized": False, "error": "missing jwt"}

    monkeypatch.setattr("quilt_mcp.tools.buckets.check_s3_authorization", fake_check, raising=False)
    monkeypatch.setattr("quilt_mcp.tools.buckets._check_traditional_authorization", _boom, raising=False)

    result = buckets.bucket_objects_list("quilt-sandbox", include_signed_urls=False)

    assert result["success"] is False
    assert "missing jwt" in result["error"]


def test_bucket_object_fetch_uses_jwt_authorization(monkeypatch):
    payload = b"abc123"
    fake_client = _FakeGetClient(payload)
    captured = {}

    def fake_check(tool_name, tool_args):
        captured["tool"] = tool_name
        captured["args"] = tool_args
        return {"authorized": True, "s3_client": fake_client}

    monkeypatch.setattr("quilt_mcp.tools.buckets.check_s3_authorization", fake_check, raising=False)
    monkeypatch.setattr("quilt_mcp.tools.buckets.get_s3_client", _boom, raising=False)

    result = buckets.bucket_object_fetch("s3://quilt-sandbox/data.csv", base64_encode=False)

    assert captured["tool"] == "bucket_object_fetch"
    assert captured["args"]["bucket_name"] == "quilt-sandbox"
    assert fake_client.calls
    assert result["text"] == "abc123"


def test_bucket_object_link_uses_jwt_authorization(monkeypatch):
    fake_client = _FakeHeadClient()
    captured = {}

    def fake_check(tool_name, tool_args):
        captured["tool"] = tool_name
        captured["args"] = tool_args
        return {"authorized": True, "s3_client": fake_client}

    monkeypatch.setattr("quilt_mcp.tools.buckets.check_s3_authorization", fake_check, raising=False)
    monkeypatch.setattr("quilt_mcp.tools.buckets.get_s3_client", _boom, raising=False)

    result = buckets.bucket_object_link("s3://quilt-sandbox/data.csv")

    assert captured["tool"] == "bucket_object_link"
    assert captured["args"]["bucket_name"] == "quilt-sandbox"
    assert fake_client.calls
    assert result["presigned_url"] == "https://example.com"


def test_bucket_objects_put_uses_jwt_authorization(monkeypatch):
    fake_client = _FakePutClient()
    captured = {}

    def fake_check(tool_name, tool_args):
        captured["tool"] = tool_name
        captured["args"] = tool_args
        return {"authorized": True, "s3_client": fake_client}

    monkeypatch.setattr("quilt_mcp.tools.buckets.check_s3_authorization", fake_check, raising=False)
    monkeypatch.setattr("quilt_mcp.tools.buckets.get_s3_client", _boom, raising=False)

    result = buckets.bucket_objects_put(
        "quilt-sandbox",
        [{"key": "data.csv", "text": "hello", "content_type": "text/plain"}],
    )

    assert captured["tool"] == "bucket_objects_put"
    assert captured["args"]["bucket_name"] == "quilt-sandbox"
    assert fake_client.calls
    assert result["uploaded"] == 1
