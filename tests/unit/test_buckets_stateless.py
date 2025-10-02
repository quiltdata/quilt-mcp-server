"""Stateless bucket tool tests ensuring token enforcement and client usage."""

from __future__ import annotations

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
