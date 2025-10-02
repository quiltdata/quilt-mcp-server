"""Stateless bucket tool tests ensuring token enforcement and client usage."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Dict
from unittest.mock import Mock, MagicMock, patch

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import buckets


@contextmanager
def runtime_token(token: str | None):
    with request_context(token, metadata={"session_id": "session"} if token else None):
        yield


def test_bucket_objects_search_uses_runtime_token(monkeypatch):
    captured: Dict[str, Dict] = {}

    def fake_search(**kwargs):
        captured.update(kwargs)
        return {"results": ["match"], "bucket": "bucket"}

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog")
    monkeypatch.setattr("quilt_mcp.clients.catalog.catalog_bucket_search", fake_search)

    with runtime_token("token"):
        result = buckets.bucket_objects_search("s3://bucket", "query", limit=5)

    assert captured["auth_token"] == "token"
    assert captured["bucket"] == "bucket"
    assert captured["query"] == "query"
    assert captured["limit"] == 5
    assert result["results"] == ["match"]


def test_bucket_objects_search_requires_token():
    result = buckets.bucket_objects_search("bucket", "query")
    assert result["success"] is False
    assert "Authorization token" in result["error"]


@patch("quilt_mcp.clients.catalog.catalog_bucket_search")
def test_bucket_objects_search_propagates_errors(fake_search, monkeypatch):
    fake_search.side_effect = RuntimeError("boom")
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog")

    with runtime_token("token"):
        result = buckets.bucket_objects_search("bucket", "query")

    assert result["error"].startswith("Failed to search bucket")
    assert "boom" in result["error"]


def test_bucket_objects_search_graphql_uses_catalog(monkeypatch):
    captured: Dict[str, Dict] = {}

    def fake_graphql(**kwargs):
        captured.update(kwargs)
        return {
            "objects": {
                "edges": [{"node": {"key": "obj"}}],
                "pageInfo": {"endCursor": "c", "hasNextPage": False},
            }
        }

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog")
    monkeypatch.setattr("quilt_mcp.clients.catalog.catalog_bucket_search_graphql", fake_graphql)

    with runtime_token("token"):
        result = buckets.bucket_objects_search_graphql(
            bucket="bucket",
            object_filter={"extension": "csv"},
            first=10,
            after="cursor",
        )

    assert captured["auth_token"] == "token"
    assert captured["bucket"] == "bucket"
    assert captured["object_filter"] == {"extension": "csv"}
    assert captured["first"] == 10
    assert captured["after"] == "cursor"
    assert result["objects"][0]["key"] == "obj"


def test_bucket_objects_search_graphql_requires_token():
    result = buckets.bucket_objects_search_graphql("bucket")
    assert result["success"] is False
    assert "Authorization token" in result["error"]


@patch("quilt_mcp.clients.catalog.catalog_bucket_search_graphql")
def test_bucket_objects_search_graphql_propagates_errors(fake_graphql, monkeypatch):
    fake_graphql.side_effect = RuntimeError("boom")
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog")

    with runtime_token("token"):
        result = buckets.bucket_objects_search_graphql("bucket")

    assert result["success"] is False
    assert "boom" in result["error"]


@patch("quilt_mcp.utils._get_bearer_auth_service")
def test_bucket_object_info_uses_request_scoped_client(mock_get_auth_service, monkeypatch):
    fake_session = MagicMock()
    fake_client = MagicMock()
    fake_session.client.return_value = fake_client

    fake_auth_result = MagicMock()
    fake_auth_service = MagicMock()
    fake_auth_service.authenticate_header.return_value = fake_auth_result
    fake_auth_service.build_boto3_session.return_value = fake_session
    mock_get_auth_service.return_value = fake_auth_service

    fake_client.head_object.return_value = {
        "ContentLength": 123,
        "ContentType": "text/plain",
        "ETag": "etag",
        "LastModified": "2025-10-02T00:00:00+00:00",
        "Metadata": {},
        "StorageClass": "STANDARD",
        "CacheControl": "no-cache",
    }

    with runtime_token("token"):
        result = buckets.bucket_object_info("s3://bucket/key.txt")

    fake_auth_service.authenticate_header.assert_called_once_with("Bearer token")
    fake_auth_service.build_boto3_session.assert_called_once_with(fake_auth_result)
    fake_session.client.assert_called_once_with("s3")
    fake_client.head_object.assert_called_once_with(Bucket="bucket", Key="key.txt")
    assert result["bucket"] == "bucket"
    assert result["key"] == "key.txt"


@patch("quilt_mcp.utils._get_bearer_auth_service")
def test_bucket_object_link_uses_request_scoped_client(mock_get_auth_service):
    fake_session = MagicMock()
    fake_client = MagicMock()
    fake_session.client.return_value = fake_client

    fake_auth_result = MagicMock()
    fake_auth_service = MagicMock()
    fake_auth_service.authenticate_header.return_value = fake_auth_result
    fake_auth_service.build_boto3_session.return_value = fake_session
    mock_get_auth_service.return_value = fake_auth_service

    fake_client.generate_presigned_url.return_value = "https://signed"

    with runtime_token("token"):
        result = buckets.bucket_object_link("s3://bucket/key.txt")

    fake_auth_service.authenticate_header.assert_called_once_with("Bearer token")
    fake_auth_service.build_boto3_session.assert_called_once_with(fake_auth_result)
    fake_session.client.assert_called_once_with("s3")
    fake_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "bucket", "Key": "key.txt"},
        ExpiresIn=3600,
    )
    assert result["presigned_url"] == "https://signed"


@pytest.fixture
def test_token():
    """Get test token from environment."""
    token = os.getenv("QUILT_TEST_TOKEN")
    if not token:
        pytest.skip("QUILT_TEST_TOKEN not set - skipping tests requiring authentication")
    return token


@pytest.fixture
def catalog_url(monkeypatch):
    """Set catalog URL to demo."""
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://demo.quiltdata.com")
    return "https://demo.quiltdata.com"


class TestBucketsDiscovery:
    """Test bucket discovery via catalog GraphQL (real calls to demo)."""

    def test_discovery_mode_no_action(self):
        """Test discovery mode returns module info (no auth needed)."""
        result = buckets.buckets()

        assert result.get("module") == "buckets"
        assert "discover" in result.get("actions", [])
        assert "object_fetch" in result.get("actions", [])
        assert "objects_list" in result.get("actions", [])

    def test_buckets_discover_success(self, test_token, catalog_url):
        """Test successful bucket discovery with real GraphQL call."""
        with request_context(test_token, metadata={"path": "/buckets"}):
            result = buckets.buckets(action="discover")

        # Should succeed with valid token
        assert result.get("success") is True, f"Discovery failed: {result.get('error')}"

        # Should have buckets from real demo catalog
        assert "buckets" in result
        assert isinstance(result["buckets"], list)
        assert result["total_buckets"] > 0

        # Should have categorized buckets
        assert "categorized_buckets" in result
        assert "write_access" in result["categorized_buckets"]
        assert "read_access" in result["categorized_buckets"]

        # Should have user email
        assert "user_email" in result
        assert result["user_email"] == "simon@quiltdata.io"

    def test_buckets_discover_no_token(self, catalog_url):
        """Test discovery fails gracefully without token."""
        with request_context(None, metadata={"path": "/buckets"}):
            result = buckets.buckets(action="discover")

        assert result["success"] is False
        assert "token required" in result["error"].lower()

    def test_buckets_discover_invalid_token(self, catalog_url):
        """Test discovery handles invalid token."""
        invalid_token = "invalid.jwt.token"

        with request_context(invalid_token, metadata={"path": "/buckets"}):
            result = buckets.buckets(action="discover")

        # Should fail with authentication error
        assert result["success"] is False
        assert "401" in result["error"] or "unauthorized" in result["error"].lower()

    def test_buckets_discover_catalog_url_not_configured(self, monkeypatch):
        """Test error when catalog URL not configured."""
        token_value = "test.jwt.token"

        # Mock resolve_catalog_url to return None
        monkeypatch.setattr(
            "quilt_mcp.tools.buckets.resolve_catalog_url",
            lambda: None
        )

        with request_context(token_value, metadata={"path": "/buckets"}):
            result = buckets.buckets(action="discover")

        assert result["success"] is False
        assert "catalog url" in result["error"].lower()
