"""Stateless search backend tests verifying catalog integration."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.search.backends.elasticsearch import Quilt3ElasticsearchBackend


@contextmanager
def runtime_token(token: str):
    with request_context(token, metadata={"session_id": "search"}):
        yield


@pytest.mark.asyncio
async def test_search_bucket_uses_catalog_search(monkeypatch):
    mock_response = {"results": [{"_source": {"key": "data.csv", "size": 123}}]}

    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog")
    mock_search = Mock(return_value=mock_response)
    monkeypatch.setattr("quilt_mcp.clients.catalog.catalog_bucket_search", mock_search)

    backend = Quilt3ElasticsearchBackend()

    with runtime_token("token"):
        resp = await backend._search_bucket("query", "test-bucket", None, limit=5)

    mock_search.assert_called_once()
    assert resp
    assert resp[0].logical_key == "data.csv"


@pytest.mark.asyncio
async def test_search_bucket_requires_token(monkeypatch):
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    backend = Quilt3ElasticsearchBackend()
    resp = await backend._search_bucket("query", "bucket", None, limit=5)
    assert resp == []
