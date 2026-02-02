"""Unit tests for Platform_Backend core behavior."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
import sys

import pytest

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError, NotFoundError
from quilt_mcp.runtime_context import (
    RuntimeAuthState,
    get_runtime_environment,
    push_runtime_context,
    reset_runtime_context,
)


def _push_jwt_context(claims=None):
    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="test-token",
        claims=claims
        or {
            "catalog_token": "test-catalog-token",
            "catalog_url": "https://example.quiltdata.com",
            "registry_url": "https://registry.quiltdata.com",
        },
    )
    return push_runtime_context(environment=get_runtime_environment(), auth=auth_state)


def _make_backend(monkeypatch, claims=None):
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context(claims)
    try:
        from quilt_mcp.backends.platform_backend import Platform_Backend

        return Platform_Backend()
    finally:
        reset_runtime_context(token)


def test_platform_backend_requires_catalog_token(monkeypatch):
    from quilt_mcp.backends.platform_backend import Platform_Backend

    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    with pytest.raises(AuthenticationError):
        Platform_Backend()


def test_platform_backend_uses_env_graphql_endpoint(monkeypatch):
    from quilt_mcp.backends.platform_backend import Platform_Backend

    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context({"catalog_token": "token", "catalog_url": "https://example.quiltdata.com"})
    try:
        backend = Platform_Backend()
    finally:
        reset_runtime_context(token)

    assert backend.get_graphql_endpoint() == "https://registry.example.com/graphql"
    assert backend.get_graphql_auth_headers() == {"Authorization": "Bearer token"}


def test_execute_graphql_query_success(monkeypatch):
    from quilt_mcp.backends.platform_backend import Platform_Backend

    token = _push_jwt_context()
    try:
        backend = Platform_Backend()
    finally:
        reset_runtime_context(token)

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"ok": True}}

    backend._session.post = lambda *args, **kwargs: DummyResponse()
    result = backend.execute_graphql_query("query { ok }")
    assert result["data"]["ok"] is True


def test_execute_graphql_query_graphql_error(monkeypatch):
    from quilt_mcp.backends.platform_backend import Platform_Backend

    token = _push_jwt_context()
    try:
        backend = Platform_Backend()
    finally:
        reset_runtime_context(token)

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"errors": [{"message": "boom"}]}

    backend._session.post = lambda *args, **kwargs: DummyResponse()
    with pytest.raises(BackendError):
        backend.execute_graphql_query("query { ok }")


def test_get_auth_status(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {"me": {"name": "User", "email": "user@example.com", "isAdmin": False}}
    }

    backend._catalog_url = "https://example.quiltdata.com"
    status = backend.get_auth_status()
    assert status.is_authenticated is True
    assert status.logged_in_url == "https://example.quiltdata.com"


def test_list_buckets(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {"bucketConfigs": [{"name": "bucket-a"}, {"name": "bucket-b"}]}
    }

    buckets = backend.list_buckets()
    assert [bucket.name for bucket in buckets] == ["bucket-a", "bucket-b"]


def test_get_catalog_config(monkeypatch):
    backend = _make_backend(monkeypatch)

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "region": "us-east-1",
                "apiGatewayEndpoint": "https://api.example.com",
                "registryUrl": "https://registry.example.com",
                "analyticsBucket": "quilt-demo-analyticsbucket-123",
            }

    backend._session.get = lambda *args, **kwargs: DummyResponse()
    config = backend.get_catalog_config("https://example.quiltdata.com")
    assert config.registry_url == "https://registry.example.com"
    assert config.stack_prefix == "quilt-demo"


def test_configure_catalog_derives_registry(monkeypatch):
    from quilt_mcp.backends.platform_backend import Platform_Backend

    # Create backend without pre-existing registry_url
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context({"catalog_token": "token"})
    try:
        backend = Platform_Backend()
        # Clear any registry_url that might have been set
        backend._registry_url = None
        backend.configure_catalog("https://nightly.quilttest.com")
        assert backend.get_registry_url() == "https://nightly-registry.quilttest.com"
    finally:
        reset_runtime_context(token)


def test_diff_packages_detects_changes(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "p1": {"revision": {"contentsFlatMap": {"a.txt": {"size": 1, "hash": "h1", "physicalKey": "s3://b/a"}}}},
            "p2": {
                "revision": {
                    "contentsFlatMap": {
                        "a.txt": {"size": 2, "hash": "h2", "physicalKey": "s3://b/a"},
                        "b.txt": {"size": 1, "hash": "h3", "physicalKey": "s3://b/b"},
                    }
                }
            },
        }
    }
    diff = backend.diff_packages("team/a", "team/b", "s3://bucket")
    assert diff["added"] == ["b.txt"]
    assert diff["modified"] == ["a.txt"]


def test_create_and_update_package_revision(monkeypatch):
    backend = _make_backend(monkeypatch)

    @contextmanager
    def _noop_creds():
        yield

    backend._with_aws_credentials = _noop_creds

    class FakePackage:
        def __init__(self):
            self.meta = {}
            self.set_calls = []

        def set(self, logical_key, s3_uri):
            self.set_calls.append((logical_key, s3_uri))

        def set_meta(self, meta):
            self.meta = meta

        def push(self, *args, **kwargs):
            return "top-hash"

        @classmethod
        def browse(cls, *args, **kwargs):
            return cls()

    fake_quilt3 = SimpleNamespace(Package=FakePackage)
    monkeypatch.setitem(sys.modules, "quilt3", fake_quilt3)

    created = backend.create_package_revision(
        "team/pkg",
        ["s3://bucket/path/file.txt"],
        metadata={"k": "v"},
        registry="s3://bucket",
        copy=False,
    )
    assert created.success is True

    updated = backend.update_package_revision(
        "team/pkg",
        ["s3://bucket/path/new.txt"],
        registry="s3://bucket",
        metadata={"k2": "v2"},
    )
    assert updated.success is True


def test_search_packages_transforms_hits(monkeypatch):
    from quilt_mcp.backends.platform_backend import Platform_Backend

    token = _push_jwt_context()
    try:
        backend = Platform_Backend()
    finally:
        reset_runtime_context(token)

    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "searchPackages": {
                "__typename": "PackagesSearchResultSet",
                "firstPage": {
                    "hits": [
                        {
                            "name": "team/data",
                            "bucket": "test-bucket",
                            "hash": "abc123",
                            "modified": "2024-01-01T00:00:00Z",
                            "comment": "commit",
                            "meta": '{"description": "desc", "tags": ["tag1", "tag2"]}',
                        }
                    ]
                },
            }
        }
    }

    results = backend.search_packages("data", "s3://test-bucket")
    assert len(results) == 1
    assert results[0].name == "team/data"
    assert results[0].description == "desc"
    assert results[0].tags == ["tag1", "tag2"]
    assert results[0].top_hash == "abc123"


def test_browse_content_dir_children(monkeypatch):
    from quilt_mcp.backends.platform_backend import Platform_Backend

    token = _push_jwt_context()
    try:
        backend = Platform_Backend()
    finally:
        reset_runtime_context(token)

    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "package": {
                "revision": {
                    "dir": {
                        "path": "",
                        "size": 0,
                        "children": [
                            {"__typename": "PackageFile", "path": "file.txt", "size": 10, "physicalKey": "s3://b/f"},
                            {"__typename": "PackageDir", "path": "subdir", "size": 0},
                        ],
                    },
                    "file": None,
                }
            }
        }
    }

    results = backend.browse_content("team/data", "s3://test-bucket")
    assert {entry.path for entry in results} == {"file.txt", "subdir"}
    types = {entry.path: entry.type for entry in results}
    assert types["file.txt"] == "file"
    assert types["subdir"] == "directory"


def test_get_content_url_presigned(monkeypatch):
    from quilt_mcp.backends.platform_backend import Platform_Backend

    token = _push_jwt_context()
    try:
        backend = Platform_Backend()
    finally:
        reset_runtime_context(token)

    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {"package": {"revision": {"file": {"physicalKey": "s3://bucket/key"}}}}
    }

    mock_client = SimpleNamespace(generate_presigned_url=lambda *args, **kwargs: "https://signed")
    backend.get_boto3_client = lambda *args, **kwargs: mock_client

    url = backend.get_content_url("team/data", "s3://bucket", "key")
    assert url == "https://signed"


def test_list_all_packages_paginates(monkeypatch):
    from quilt_mcp.backends.platform_backend import Platform_Backend

    token = _push_jwt_context()
    try:
        backend = Platform_Backend()
    finally:
        reset_runtime_context(token)

    responses = [
        {"data": {"packages": {"total": 101, "page": [{"name": "a"}]}}},
        {"data": {"packages": {"total": 101, "page": [{"name": "b"}]}}},
    ]

    def _side_effect(*args, **kwargs):
        return responses.pop(0)

    backend.execute_graphql_query = _side_effect

    results = backend.list_all_packages("s3://test-bucket")
    assert results == ["a", "b"]


def test_get_package_info_missing(monkeypatch):
    from quilt_mcp.backends.platform_backend import Platform_Backend

    token = _push_jwt_context()
    try:
        backend = Platform_Backend()
    finally:
        reset_runtime_context(token)

    backend.execute_graphql_query = lambda *args, **kwargs: {"data": {"package": None}}

    with pytest.raises(NotFoundError):
        backend.get_package_info("team/missing", "s3://test-bucket")
