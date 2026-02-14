from __future__ import annotations

import base64
from types import SimpleNamespace

from quilt_mcp.tools import buckets
from quilt_mcp.tools.auth_helpers import AuthorizationContext


def _authorized_ctx(client, auth_type: str = "iam") -> AuthorizationContext:
    return AuthorizationContext(authorized=True, auth_type=auth_type, s3_client=client)


class _VersionError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


def test_bucket_objects_list_auth_failure(monkeypatch):
    monkeypatch.setattr(
        "quilt_mcp.tools.buckets.check_s3_authorization",
        lambda *_a, **_k: AuthorizationContext(authorized=False, error="denied"),
    )
    result = buckets.bucket_objects_list("s3://demo")
    assert "denied" in result.error
    assert result.bucket == "demo"


def test_bucket_objects_list_success_and_exception(monkeypatch):
    class Client:
        def list_objects_v2(self, **kwargs):
            assert kwargs["Bucket"] == "demo"
            return {
                "Contents": [{"Key": "k1", "Size": 1, "ETag": "e1"}],
                "IsTruncated": True,
                "NextContinuationToken": "nxt",
            }

    monkeypatch.setattr("quilt_mcp.tools.buckets.check_s3_authorization", lambda *_a, **_k: _authorized_ctx(Client()))
    monkeypatch.setattr("quilt_mcp.tools.buckets.generate_signed_url", lambda s3_uri: f"url:{s3_uri}")
    ok = buckets.bucket_objects_list("demo", include_signed_urls=True)
    assert ok.success is True
    assert ok.count == 1
    assert ok.objects[0].signed_url == "url:s3://demo/k1"
    assert ok.next_continuation_token == "nxt"

    class BoomClient:
        def list_objects_v2(self, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "quilt_mcp.tools.buckets.check_s3_authorization",
        lambda *_a, **_k: _authorized_ctx(BoomClient()),
    )
    err = buckets.bucket_objects_list("demo")
    assert "Failed to list objects" in err.error


def test_bucket_object_info_paths(monkeypatch):
    bad = buckets.bucket_object_info("not-an-s3-uri")
    assert "Invalid S3 URI" in bad.error

    monkeypatch.setattr(
        "quilt_mcp.tools.buckets.check_s3_authorization",
        lambda *_a, **_k: AuthorizationContext(authorized=False, error="auth-no"),
    )
    denied = buckets.bucket_object_info("s3://b/k")
    assert "auth-no" in denied.error

    class OkClient:
        def head_object(self, **kwargs):
            assert kwargs["VersionId"] == "v1"
            return {"ContentLength": 10, "ETag": "e", "Metadata": {"m": "1"}}

    monkeypatch.setattr(
        "quilt_mcp.tools.buckets.check_s3_authorization", lambda *_a, **_k: _authorized_ctx(OkClient())
    )
    ok = buckets.bucket_object_info("s3://b/k?versionId=v1")
    assert ok.success is True
    assert ok.object.version_id == "v1"
    assert ok.object.size == 10

    class ErrClient:
        def __init__(self, code: str):
            self.code = code

        def head_object(self, **_kwargs):
            raise _VersionError(self.code)

    monkeypatch.setattr(
        "quilt_mcp.tools.buckets.check_s3_authorization",
        lambda *_a, **_k: _authorized_ctx(ErrClient("NoSuchVersion")),
    )
    no_ver = buckets.bucket_object_info("s3://b/k?versionId=v1")
    assert "Version v1 not found" in no_ver.error

    monkeypatch.setattr(
        "quilt_mcp.tools.buckets.check_s3_authorization",
        lambda *_a, **_k: _authorized_ctx(ErrClient("AccessDenied")),
    )
    access = buckets.bucket_object_info("s3://b/k?versionId=v1")
    assert "Access denied for version v1" in access.error


def test_bucket_object_text_paths(monkeypatch):
    class Body:
        def read(self, _n):
            return b"abcdef"

    class Client:
        def get_object(self, **kwargs):
            if kwargs.get("VersionId") is not None:
                assert kwargs["VersionId"] == "v2"
            return {"Body": Body()}

    monkeypatch.setattr("quilt_mcp.tools.buckets.check_s3_authorization", lambda *_a, **_k: _authorized_ctx(Client()))
    ok = buckets.bucket_object_text("s3://b/k?versionId=v2", max_bytes=3)
    assert ok.success is True
    assert ok.truncated is True
    assert ok.bytes_read == 3

    err = buckets.bucket_object_text("s3://b/k", encoding="definitely-invalid-codec")
    assert "Decode failed" in err.error


def test_bucket_objects_put_mixed_results(monkeypatch):
    class Client:
        def put_object(self, **kwargs):
            if kwargs["Key"] == "boom":
                raise RuntimeError("upload failed")
            return {"ETag": "etag"}

    monkeypatch.setattr("quilt_mcp.tools.buckets.check_s3_authorization", lambda *_a, **_k: _authorized_ctx(Client()))

    result = buckets.bucket_objects_put(
        bucket="demo",
        items=[
            {"key": "ok.txt", "text": "ok", "encoding": "utf-8"},
            {"key": "bad-enc", "text": "x", "encoding": "bad-encoding"},
            {"key": "bad-b64", "data": "###"},
            {"key": "boom", "data": base64.b64encode(b"x").decode("ascii")},
        ],
    )
    assert result.success is True
    assert result.requested == 4
    assert result.uploaded == 1
    assert result.failed == 3
    assert any(r.key == "bad-enc" and "encode failed" in (r.error or "") for r in result.results)
    assert any(r.key == "bad-b64" and "base64 decode failed" in (r.error or "") for r in result.results)
    assert any(r.key == "boom" and "upload failed" in (r.error or "") for r in result.results)


def test_bucket_object_fetch_base64_text_and_fallback(monkeypatch):
    class Body:
        def __init__(self, payload: bytes):
            self.payload = payload

        def read(self, _n):
            return self.payload

    class Client:
        def __init__(self, payload: bytes):
            self.payload = payload

        def get_object(self, **_kwargs):
            return {"Body": Body(self.payload), "ContentType": "application/octet-stream"}

    monkeypatch.setattr(
        "quilt_mcp.tools.buckets.check_s3_authorization", lambda *_a, **_k: _authorized_ctx(Client(b"abc"))
    )
    b64 = buckets.bucket_object_fetch("s3://b/k", base64_encode=True)
    assert b64.success is True
    assert b64.is_base64 is True
    assert b64.data == "YWJj"

    monkeypatch.setattr(
        "quilt_mcp.tools.buckets.check_s3_authorization",
        lambda *_a, **_k: _authorized_ctx(Client(b"hello")),
    )
    txt = buckets.bucket_object_fetch("s3://b/k", base64_encode=False)
    assert txt.success is True
    assert txt.is_base64 is False
    assert txt.data == "hello"

    monkeypatch.setattr(
        "quilt_mcp.tools.buckets.check_s3_authorization", lambda *_a, **_k: _authorized_ctx(Client(b"\xff\xfe"))
    )
    fb = buckets.bucket_object_fetch("s3://b/k", base64_encode=False)
    assert fb.success is True
    assert fb.is_base64 is True


def test_bucket_object_fetch_and_link_version_errors(monkeypatch):
    class ErrClient:
        def __init__(self, code: str):
            self.code = code

        def get_object(self, **_kwargs):
            raise _VersionError(self.code)

        def generate_presigned_url(self, *_args, **_kwargs):
            raise _VersionError(self.code)

    monkeypatch.setattr(
        "quilt_mcp.tools.buckets.check_s3_authorization",
        lambda *_a, **_k: _authorized_ctx(ErrClient("NoSuchVersion")),
    )
    f_err = buckets.bucket_object_fetch("s3://b/k?versionId=v3")
    assert "Version v3 not found" in f_err.error
    l_err = buckets.bucket_object_link("s3://b/k?versionId=v3")
    assert "Version v3 not found" in l_err.error

    class LinkClient:
        def generate_presigned_url(self, *_args, **_kwargs):
            return "https://signed"

    monkeypatch.setattr(
        "quilt_mcp.tools.buckets.check_s3_authorization",
        lambda *_a, **_k: _authorized_ctx(LinkClient(), auth_type="jwt"),
    )
    ok = buckets.bucket_object_link("s3://b/k", expiration=60)
    assert ok.success is True
    assert ok.signed_url == "https://signed"
    assert ok.auth_type == "jwt"


def test_internal_helpers():
    assert buckets._normalize_bucket("s3://demo/path") == "demo"
    assert buckets._normalize_bucket("demo") == "demo"
    payload = {}
    enriched = buckets._attach_auth_metadata(payload, SimpleNamespace(auth_type="iam"))
    assert enriched["auth_type"] == "iam"
