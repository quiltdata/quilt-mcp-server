"""Stateless search tool tests ensuring token enforcement and client usage."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Dict
from unittest.mock import Mock, MagicMock, patch, AsyncMock

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import search
from quilt_mcp.search.backends.base import (
    BackendResponse,
    BackendStatus,
    BackendType,
    SearchResult,
)
from quilt_mcp.search.backends.graphql import EnterpriseGraphQLBackend, PackageSearchResponse
from quilt_mcp.search.tools.unified_search import UnifiedSearchEngine


@contextmanager
def runtime_token(token: str | None):
    with request_context(token, metadata={"session_id": "session"} if token else None):
        yield


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


class TestSearchDiscovery:
    """Test search discovery functionality."""

    @pytest.mark.asyncio
    async def test_discovery_mode_no_action(self):
        """Test discovery mode returns module info (no auth needed)."""
        result = await search.search()

        assert result.get("module") == "search"
        assert "discover" in result.get("actions", [])
        assert "unified_search" in result.get("actions", [])
        assert "suggest" in result.get("actions", [])

    @pytest.mark.asyncio
    async def test_search_discover_success(self, test_token, catalog_url):
        """Test successful search discovery."""
        with request_context(test_token, metadata={"path": "/search"}):
            result = await search.search(action="discover")

        # Should succeed with valid token
        assert result.get("success") is True, f"Discovery failed: {result.get('error')}"

        # Should have search capabilities
        assert "search_capabilities" in result
        assert "available_backends" in result
        assert "search_scopes" in result
        assert "supported_filters" in result
        assert "common_queries" in result

        # Check expected capabilities
        capabilities = result["search_capabilities"]
        assert capabilities.get("unified_search") is True
        assert capabilities.get("graphql_search") is True

        # Check expected backends
        backends = result["available_backends"]
        assert "auto" in backends
        assert "graphql" in backends
        assert "elasticsearch" in backends
        assert "s3" in backends

    @pytest.mark.asyncio
    async def test_search_discover_no_token(self, catalog_url):
        """Test discovery fails gracefully without token."""
        with request_context(None, metadata={"path": "/search"}):
            result = await search.search(action="discover")

        assert result["success"] is False
        assert "token required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_search_discover_catalog_url_not_configured(self, monkeypatch):
        """Test error when catalog URL not configured."""
        token_value = "test.jwt.token"

        # Mock resolve_catalog_url to return None
        monkeypatch.setattr("quilt_mcp.tools.search.resolve_catalog_url", lambda: None)

        with request_context(token_value, metadata={"path": "/search"}):
            result = await search.search(action="discover")

        assert result["success"] is False
        assert "catalog url" in result["error"].lower()


class TestSearchActions:
    """Test search action functionality."""

    @pytest.mark.asyncio
    @patch("quilt_mcp.tools.search._unified_search", new_callable=AsyncMock)
    async def test_unified_search_calls_backend(self, mock_unified_search, test_token, catalog_url):
        """Test unified search calls the backend function."""
        mock_unified_search.return_value = {"results": ["test"]}

        with request_context(test_token, metadata={"path": "/search"}):
            result = await search.search(action="unified_search", params={"query": "test query", "limit": 10})

        mock_unified_search.assert_called_once_with(
            query="test query",
            scope="global",
            target="",
            backends=["graphql"],
            limit=10,
            include_metadata=False,
            include_content_preview=False,
            explain_query=False,
            filters=None,
            count_only=False,
        )
        assert result == {"results": ["test"]}

    @pytest.mark.asyncio
    @patch("quilt_mcp.tools.search._search_suggest")
    async def test_search_suggest_calls_backend(self, mock_search_suggest, test_token, catalog_url):
        """Test search suggest calls the backend function."""
        mock_search_suggest.return_value = {"suggestions": ["test"]}

        with request_context(test_token, metadata={"path": "/search"}):
            result = await search.search(action="suggest", params={"partial_query": "test", "limit": 5})

        mock_search_suggest.assert_called_once_with(
            partial_query="test",
            context="",
            suggestion_types=["auto"],  # Default value
            limit=5,
        )
        assert result == {"suggestions": ["test"]}

    @pytest.mark.asyncio
    @patch("quilt_mcp.tools.search._search_explain")
    async def test_search_explain_calls_backend(self, mock_search_explain, test_token, catalog_url):
        """Test search explain calls the backend function."""
        mock_search_explain.return_value = {"explanation": "test"}

        with request_context(test_token, metadata={"path": "/search"}):
            result = await search.search(action="explain", params={"query": "test query"})

        mock_search_explain.assert_called_once_with(query="test query")
        assert result == {"explanation": "test"}


class TestSearchErrorHandling:
    """Test error handling for invalid inputs."""

    @pytest.mark.asyncio
    async def test_invalid_action(self, test_token, catalog_url):
        """Test invalid action returns error."""
        with request_context(test_token, metadata={"path": "/search"}):
            result = await search.search(action="totally_invalid_action")

        assert result["success"] is False
        assert "unknown" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("quilt_mcp.tools.search._unified_search", new_callable=AsyncMock)
    async def test_unified_search_backend_error(self, mock_unified_search, test_token, catalog_url):
        """Test unified search handles backend errors."""
        mock_unified_search.side_effect = Exception("Backend error")

        with request_context(test_token, metadata={"path": "/search"}):
            result = await search.search(action="unified_search", params={"query": "test"})

        assert result["success"] is False
        assert "failed" in result["error"].lower()
        assert "execute search action" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("quilt_mcp.tools.search._search_suggest")
    async def test_search_suggest_backend_error(self, mock_search_suggest, test_token, catalog_url):
        """Test search suggest handles backend errors."""
        mock_search_suggest.side_effect = Exception("Backend error")

        with request_context(test_token, metadata={"path": "/search"}):
            result = await search.search(action="suggest", params={"partial_query": "test"})

        assert result["success"] is False
        assert "failed" in result["error"].lower()
        assert "execute search action" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("quilt_mcp.tools.search._search_explain")
    async def test_search_explain_backend_error(self, mock_search_explain, test_token, catalog_url):
        """Test search explain handles backend errors."""
        mock_search_explain.side_effect = Exception("Backend error")

        with request_context(test_token, metadata={"path": "/search"}):
            result = await search.search(action="explain", params={"query": "test"})

        assert result["success"] is False
        assert "failed" in result["error"].lower()
        assert "execute search action" in result["error"].lower()


class TestGraphQLBackendFilters:
    """Tests for GraphQL backend filter logic."""

    def test_build_objects_filter_wildcard(self):
        backend = EnterpriseGraphQLBackend()

        filt, blank = backend._build_objects_filter("*.csv", None)

        assert filt == {"key": {"wildcard": "*.csv"}}
        assert blank is True

    def test_build_objects_filter_extension_keyword(self):
        backend = EnterpriseGraphQLBackend()

        filt, blank = backend._build_objects_filter("csv", None)

        assert filt == {"key": {"wildcard": "*.csv"}}
        assert blank is True

    def test_build_objects_filter_extension_with_dot(self):
        backend = EnterpriseGraphQLBackend()

        filt, blank = backend._build_objects_filter(".csv", None)

        assert filt == {"key": {"wildcard": "*.csv"}}
        assert blank is True


class TestGraphQLBackendSearch:
    """Tests for GraphQL backend search behaviour."""

    @pytest.mark.asyncio
    async def test_search_objects_blank_search_for_wildcard(self, monkeypatch):
        backend = EnterpriseGraphQLBackend()

        async def fake_execute(query, variables):
            fake_execute.calls.append(variables)
            return {
                "data": {
                    "searchObjects": {
                        "__typename": "ObjectsSearchResultSet",
                        "total": 1,
                        "firstPage": {
                            "hits": [
                                {
                                    "bucket": "demo-bucket",
                                    "key": "path/file.csv",
                                    "version": "v1",
                                    "size": 1024,
                                    "modified": "2025-10-03T00:00:00Z",
                                    "deleted": False,
                                    "score": 1.0,
                                    "indexedContent": None,
                                }
                            ],
                            "cursor": None,
                        },
                    }
                }
            }

        fake_execute.calls = []
        monkeypatch.setattr(backend, "_execute_graphql_query", fake_execute)
        monkeypatch.setattr(backend, "_fetch_more_objects", AsyncMock(return_value=([], None)))

        payload = await backend._search_objects_global("*.csv", None, limit=5)

        assert len(payload.results) == 1
        assert fake_execute.calls[0]["searchString"] == ""
        assert payload.stats == {}

    @pytest.mark.asyncio
    async def test_search_objects_paginates_results(self, monkeypatch):
        backend = EnterpriseGraphQLBackend()

        async def fake_execute(query, variables):
            return {
                "data": {
                    "searchObjects": {
                        "__typename": "ObjectsSearchResultSet",
                        "total": 5,
                        "firstPage": {
                            "hits": [
                                {
                                    "bucket": "demo-bucket",
                                    "key": f"file-{i}.csv",
                                    "version": "v1",
                                    "size": 10,
                                    "modified": "2025-10-03T00:00:00Z",
                                    "deleted": False,
                                    "score": 1.0,
                                    "indexedContent": None,
                                }
                                for i in range(2)
                            ],
                            "cursor": "cursor-1",
                        },
                    }
                }
            }

        more_hits = [
            {
                "bucket": "demo-bucket",
                "key": f"file-{i}.csv",
                "version": "v1",
                "size": 10,
                "modified": "2025-10-03T00:00:00Z",
                "deleted": False,
                "score": 0.9,
                "indexedContent": None,
            }
            for i in range(2, 5)
        ]

        monkeypatch.setattr(backend, "_execute_graphql_query", fake_execute)
        fetch_more_mock = AsyncMock(return_value=(more_hits, None))
        monkeypatch.setattr(backend, "_fetch_more_objects", fetch_more_mock)

        payload = await backend._search_objects_global("*.csv", None, limit=4)

        assert len(payload.results) == 4
        fetch_more_mock.assert_awaited()
        returned_keys = {res.logical_key for res in payload.results}
        assert "file-3.csv" in returned_keys

    @pytest.mark.asyncio
    async def test_auto_search_prefers_packages_for_domain_queries(self, monkeypatch):
        backend = EnterpriseGraphQLBackend()

        monkeypatch.setenv("QUILT_CATALOG_URL", "https://example.com")

        packages_mock = AsyncMock(return_value=[])
        objects_mock = AsyncMock()

        monkeypatch.setattr(backend, "_search_packages_global", packages_mock)
        monkeypatch.setattr(backend, "_resolve_object_search", objects_mock)

        with request_context("test-token", metadata={"session_id": "session"}):
            response = await backend.search(query="glioblastoma", search_type="auto", limit=5)

        packages_mock.assert_awaited_once()
        objects_mock.assert_not_called()
        assert response.status == BackendStatus.AVAILABLE

    @pytest.mark.asyncio
    async def test_search_packages_global_paginates_with_cursor(self, monkeypatch):
        backend = EnterpriseGraphQLBackend()

        first_page_hits = [
            {
                "id": f"pkg-{i}",
                "score": 1.0,
                "bucket": "demo-bucket",
                "name": f"package-{i}",
                "pointer": "pointer",
                "hash": "hash",
                "size": 1024,
                "modified": "2025-10-03T00:00:00Z",
                "totalEntriesCount": 5,
                "comment": "",
                "workflow": {},
            }
            for i in range(3)
        ]

        extra_hits = [
            {
                "id": f"pkg-{i}",
                "score": 0.9,
                "bucket": "demo-bucket",
                "name": f"package-{i}",
                "pointer": "pointer",
                "hash": "hash",
                "size": 1024,
                "modified": "2025-10-03T00:00:00Z",
                "totalEntriesCount": 5,
                "comment": "",
                "workflow": {},
            }
            for i in range(3, 6)
        ]

        async def fake_execute(query, variables):
            return {
                "data": {
                    "searchPackages": {
                        "total": 6,
                        "firstPage": {
                            "hits": first_page_hits,
                            "cursor": "cursor-1",
                        },
                    }
                }
            }

        fetch_more_mock = AsyncMock(return_value=(extra_hits, None))

        monkeypatch.setattr(backend, "_execute_graphql_query", fake_execute)
        monkeypatch.setattr(backend, "_fetch_more_packages", fetch_more_mock)

        payload = await backend._search_packages_global("glioblastoma", filters=None, limit=5, offset=0)

        assert isinstance(payload, PackageSearchResponse)
        assert len(payload.results) == 5
        fetch_more_mock.assert_awaited()
        returned_titles = {res.title for res in payload.results}
        assert "demo-bucket/package-4" in returned_titles
        assert payload.total == 6
        assert payload.next_cursor is None


class TestUnifiedSearchEngine:
    """Validate unified search enrichment metadata."""

    @pytest.mark.asyncio
    async def test_available_extensions_surface_in_response(self, monkeypatch):
        engine = UnifiedSearchEngine()

        fake_result = SearchResult(
            id="obj-1",
            type="file",
            title="file.csv",
            description="",
            s3_uri="s3://demo/file.csv",
            metadata={"bucket": "demo", "extension": "csv"},
            score=1.0,
            backend="graphql",
        )

        backend_response = BackendResponse(
            backend_type=BackendType.GRAPHQL,
            status=BackendStatus.AVAILABLE,
            results=[fake_result],
            total=1,
            raw_response={
                "objects": {
                    "ext_stats": [{"key": "csv", "count": 7}, {"key": "h5", "count": 2}],
                    "total": 15,
                    "next_cursor": "cursor-123",
                }
            },
        )

        monkeypatch.setattr(
            engine,
            "_execute_parallel_searches",
            AsyncMock(return_value=[backend_response]),
        )

        result = await engine.search(query="csv", search_type="objects", limit=5)

        assert result["available_extensions"][0] == {"extension": "csv", "count": 7}
        assert result["available_extensions"][1] == {"extension": "h5", "count": 2}
        assert result["object_total"] == 15
        assert result["next_cursor"] == "cursor-123"


class TestSearchIntegration:
    """Test integration with real search backends (if available)."""

    @pytest.mark.asyncio
    async def test_search_discover_real(self, test_token, catalog_url):
        """Test search discovery with real catalog."""
        with request_context(test_token, metadata={"path": "/search"}):
            result = await search.search(action="discover")

        # Should succeed and return capabilities
        assert result.get("success") is True
        assert "search_capabilities" in result
        assert "available_backends" in result

    @pytest.mark.asyncio
    @patch("quilt_mcp.tools.search._unified_search", new_callable=AsyncMock)
    async def test_unified_search_integration(self, mock_unified_search, test_token, catalog_url):
        """Test unified search integration."""
        # Mock a successful search result
        mock_unified_search.return_value = {
            "success": True,
            "results": [
                {
                    "type": "package",
                    "name": "test/package",
                    "description": "Test package",
                    "score": 0.95,
                }
            ],
            "total": 1,
            "query": "test",
            "backend": "elasticsearch",
        }

        with request_context(test_token, metadata={"path": "/search"}):
            result = await search.search(
                action="unified_search",
                params={
                    "query": "test",
                    "scope": "global",
                    "limit": 10,
                    "include_metadata": True,
                },
            )

        # Should return the mocked result
        assert result.get("success") is True
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["name"] == "test/package"
