"""Additional coverage for Elasticsearch backend error and edge paths."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from quilt_mcp.domain.auth_status import Auth_Status
from quilt_mcp.search.backends.base import BackendStatus
from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend

pytestmark = pytest.mark.anyio


def _make_backend():
    from quilt_mcp.backends.quilt3_backend import Quilt3_Backend

    mock_backend = Mock(spec=Quilt3_Backend)
    mock_backend.get_auth_status.return_value = Auth_Status(
        is_authenticated=True,
        logged_in_url="https://example.quiltdata.com",
        catalog_name="example.quiltdata.com",
        registry_url="https://example-registry.quiltdata.com",
    )
    mock_backend.get_registry_url.return_value = "https://example-registry.quiltdata.com"
    mock_backend.get_graphql_auth_headers.return_value = {"Authorization": "Bearer token"}
    return Quilt3ElasticsearchBackend(backend=mock_backend), mock_backend


def test_invalid_scope_and_empty_bucket_pattern():
    backend, _ = _make_backend()
    with pytest.raises(ValueError, match="Invalid scope"):
        backend.build_index_pattern_for_scope("bad-scope", ["bucket"])

    with patch.object(backend, "_get_available_buckets", return_value=[]):
        assert backend._build_index_pattern("file", "") == ""


def test_execute_search_api_headers_fallback_and_search_api_fallback(monkeypatch):
    backend, mock_backend = _make_backend()

    mock_backend.get_graphql_auth_headers.side_effect = RuntimeError("no auth header")
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"hits": {"hits": []}}
    with patch("quilt_mcp.search.backends.elasticsearch.requests.get", return_value=response) as req_get:
        result = backend._execute_search_api({"query": {"match_all": {}}}, "bucket", 5)
        assert result["hits"]["hits"] == []
        assert req_get.call_args.kwargs["headers"] == {}

    mock_backend.get_registry_url.return_value = None
    with patch("quilt_mcp.search.backends.elasticsearch.search_api", return_value={"hits": {"hits": []}}):
        result = backend._execute_search_api({"query": {"match_all": {}}}, "bucket", 5)
        assert "hits" in result


async def test_search_unavailable_and_invalid_scope_handler():
    backend, _ = _make_backend()
    backend._initialized = True
    backend._session_available = False
    backend._auth_error = None
    response = await backend.search("q")
    assert response.status == BackendStatus.UNAVAILABLE

    backend._session_available = True
    with patch.object(backend, "_build_index_pattern", return_value="bucket"), patch(
        "quilt_mcp.search.backends.elasticsearch.asyncio.to_thread",
        side_effect=lambda fn, *args: fn(*args),
    ):
        # Remove handler to hit invalid scope path
        backend.scope_handlers.pop("file", None)
        invalid = await backend.search("q", scope="file")
    assert invalid.status == BackendStatus.ERROR
    assert "Invalid scope" in (invalid.error_message or "")


async def test_search_empty_pattern_filters_and_error_response():
    backend, _ = _make_backend()
    backend._session_available = True

    with patch.object(backend, "_build_index_pattern", return_value=""):
        empty = await backend.search("q", scope="file")
    assert empty.status == BackendStatus.AVAILABLE
    assert empty.total == 0

    # Build response error path and BackendError formatting path
    with patch.object(backend, "_build_index_pattern", return_value="bucket"), patch(
        "quilt_mcp.search.backends.elasticsearch.asyncio.to_thread",
        side_effect=lambda fn, *args: {"error": "es failed"},
    ):
        errored = await backend.search(
            "query",
            scope="global",
            filters={
                "file_extensions": [".csv", "json"],
                "size_gt": 1,
                "size_min": 2,
                "size_max": 9,
                "created_after": "2024-01-01",
                "created_before": "2025-01-01",
            },
            limit=10,
        )
    assert errored.status == BackendStatus.ERROR
    assert "es failed" in (errored.error_message or "")


async def test_search_retry_403_then_success(monkeypatch):
    backend, _ = _make_backend()
    backend._session_available = True
    with patch.object(backend, "_build_index_pattern", return_value="a,b"), patch.object(
        backend, "_get_available_buckets", return_value=["a", "b", "c"]
    ):
        calls = {"n": 0}

        async def fake_to_thread(fn, *args):
            calls["n"] += 1
            if calls["n"] == 1:
                raise Exception("403 forbidden")
            return {"hits": {"hits": []}}

        monkeypatch.setattr("quilt_mcp.search.backends.elasticsearch.asyncio.to_thread", fake_to_thread)
        result = await backend.search("q", scope="file", bucket="", limit=5)

    assert result.status == BackendStatus.AVAILABLE
    assert calls["n"] >= 2


def test_normalize_results_skips_none():
    backend, _ = _make_backend()
    handler = Mock()
    handler.parse_result.side_effect = [None, Mock(type="file")]
    backend.scope_handlers["file"] = handler

    results = backend._normalize_results([{"_index": "b1"}, {"_index": "b2"}], "file")
    assert len(results) == 1
