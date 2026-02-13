"""Functional-style coverage tests for Elasticsearch backend logic."""

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
    return Quilt3ElasticsearchBackend(backend=mock_backend)


async def test_func_search_handles_empty_index_pattern():
    backend = _make_backend()
    backend._initialized = True
    backend._session_available = True

    with patch.object(backend, "_build_index_pattern", return_value=""):
        result = await backend.search("query", scope="file")

    assert result.status == BackendStatus.AVAILABLE
    assert result.total == 0


async def test_func_search_retry_on_403_then_success(monkeypatch):
    backend = _make_backend()
    backend._initialized = True
    backend._session_available = True

    with patch.object(backend, "_build_index_pattern", return_value="a,b,c"), patch.object(
        backend, "_get_available_buckets", return_value=["a", "b", "c", "d"]
    ):
        calls = {"n": 0}

        async def fake_to_thread(fn, *args):
            calls["n"] += 1
            if calls["n"] == 1:
                raise Exception("403 forbidden")
            return {"hits": {"hits": []}}

        monkeypatch.setattr("quilt_mcp.search.backends.elasticsearch.asyncio.to_thread", fake_to_thread)
        result = await backend.search("query", scope="file", bucket="", limit=5)

    assert result.status == BackendStatus.AVAILABLE
    assert calls["n"] >= 2


async def test_func_search_returns_error_response_on_backend_error(monkeypatch):
    backend = _make_backend()
    backend._initialized = True
    backend._session_available = True

    with patch.object(backend, "_build_index_pattern", return_value="bucket"):
        async def fake_to_thread(fn, *args):
            return {"error": "functional failure"}

        monkeypatch.setattr("quilt_mcp.search.backends.elasticsearch.asyncio.to_thread", fake_to_thread)
        result = await backend.search("query", scope="global", filters={"size_min": 10}, limit=5)

    assert result.status == BackendStatus.ERROR
    assert "functional failure" in (result.error_message or "")
