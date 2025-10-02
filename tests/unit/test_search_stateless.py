"""Stateless search tool tests ensuring token enforcement and client usage."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Dict
from unittest.mock import Mock, MagicMock, patch

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import search


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

    def test_discovery_mode_no_action(self):
        """Test discovery mode returns module info (no auth needed)."""
        result = search.search()

        assert result.get("module") == "search"
        assert "discover" in result.get("actions", [])
        assert "unified_search" in result.get("actions", [])
        assert "suggest" in result.get("actions", [])
        assert "explain" in result.get("actions", [])

    def test_search_discover_success(self, test_token, catalog_url):
        """Test successful search discovery."""
        with request_context(test_token, metadata={"path": "/search"}):
            result = search.search(action="discover")

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

    def test_search_discover_no_token(self, catalog_url):
        """Test discovery fails gracefully without token."""
        with request_context(None, metadata={"path": "/search"}):
            result = search.search(action="discover")

        assert result["success"] is False
        assert "token required" in result["error"].lower()

    def test_search_discover_catalog_url_not_configured(self, monkeypatch):
        """Test error when catalog URL not configured."""
        token_value = "test.jwt.token"

        # Mock resolve_catalog_url to return None
        monkeypatch.setattr(
            "quilt_mcp.tools.search.resolve_catalog_url",
            lambda: None
        )

        with request_context(token_value, metadata={"path": "/search"}):
            result = search.search(action="discover")

        assert result["success"] is False
        assert "catalog url" in result["error"].lower()


class TestSearchActions:
    """Test search action functionality."""

    @patch("quilt_mcp.tools.search._unified_search")
    def test_unified_search_calls_backend(self, mock_unified_search, test_token, catalog_url):
        """Test unified search calls the backend function."""
        mock_unified_search.return_value = {"results": ["test"]}

        with request_context(test_token, metadata={"path": "/search"}):
            result = search.search(
                action="unified_search",
                params={"query": "test query", "limit": 10}
            )

        mock_unified_search.assert_called_once_with(
            query="test query",
            scope="global",
            target="",
            backends=["auto"],  # Default value
            limit=10,
            include_metadata=True,
            include_content_preview=False,
            explain_query=False,
            filters=None,
            count_only=False,
        )
        assert result == {"results": ["test"]}

    @patch("quilt_mcp.tools.search._search_suggest")
    def test_search_suggest_calls_backend(self, mock_search_suggest, test_token, catalog_url):
        """Test search suggest calls the backend function."""
        mock_search_suggest.return_value = {"suggestions": ["test"]}

        with request_context(test_token, metadata={"path": "/search"}):
            result = search.search(
                action="suggest",
                params={"partial_query": "test", "limit": 5}
            )

        mock_search_suggest.assert_called_once_with(
            partial_query="test",
            context="",
            suggestion_types=["auto"],  # Default value
            limit=5,
        )
        assert result == {"suggestions": ["test"]}

    @patch("quilt_mcp.tools.search._search_explain")
    def test_search_explain_calls_backend(self, mock_search_explain, test_token, catalog_url):
        """Test search explain calls the backend function."""
        mock_search_explain.return_value = {"explanation": "test"}

        with request_context(test_token, metadata={"path": "/search"}):
            result = search.search(
                action="explain",
                params={"query": "test query"}
            )

        mock_search_explain.assert_called_once_with(query="test query")
        assert result == {"explanation": "test"}


class TestSearchErrorHandling:
    """Test error handling for invalid inputs."""

    def test_invalid_action(self, test_token, catalog_url):
        """Test invalid action returns error."""
        with request_context(test_token, metadata={"path": "/search"}):
            result = search.search(action="totally_invalid_action")

        assert result["success"] is False
        assert "unknown" in result["error"].lower()

    @patch("quilt_mcp.tools.search._unified_search")
    def test_unified_search_backend_error(self, mock_unified_search, test_token, catalog_url):
        """Test unified search handles backend errors."""
        mock_unified_search.side_effect = Exception("Backend error")

        with request_context(test_token, metadata={"path": "/search"}):
            result = search.search(
                action="unified_search",
                params={"query": "test"}
            )

        assert result["success"] is False
        assert "failed" in result["error"].lower()
        assert "execute search action" in result["error"].lower()

    @patch("quilt_mcp.tools.search._search_suggest")
    def test_search_suggest_backend_error(self, mock_search_suggest, test_token, catalog_url):
        """Test search suggest handles backend errors."""
        mock_search_suggest.side_effect = Exception("Backend error")

        with request_context(test_token, metadata={"path": "/search"}):
            result = search.search(
                action="suggest",
                params={"partial_query": "test"}
            )

        assert result["success"] is False
        assert "failed" in result["error"].lower()
        assert "execute search action" in result["error"].lower()

    @patch("quilt_mcp.tools.search._search_explain")
    def test_search_explain_backend_error(self, mock_search_explain, test_token, catalog_url):
        """Test search explain handles backend errors."""
        mock_search_explain.side_effect = Exception("Backend error")

        with request_context(test_token, metadata={"path": "/search"}):
            result = search.search(
                action="explain",
                params={"query": "test"}
            )

        assert result["success"] is False
        assert "failed" in result["error"].lower()
        assert "execute search action" in result["error"].lower()


class TestSearchIntegration:
    """Test integration with real search backends (if available)."""

    def test_search_discover_real(self, test_token, catalog_url):
        """Test search discovery with real catalog."""
        with request_context(test_token, metadata={"path": "/search"}):
            result = search.search(action="discover")

        # Should succeed and return capabilities
        assert result.get("success") is True
        assert "search_capabilities" in result
        assert "available_backends" in result

    @patch("quilt_mcp.tools.search._unified_search")
    def test_unified_search_integration(self, mock_unified_search, test_token, catalog_url):
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
            result = search.search(
                action="unified_search",
                params={
                    "query": "test",
                    "scope": "global",
                    "limit": 10,
                    "include_metadata": True,
                }
            )

        # Should return the mocked result
        assert result.get("success") is True
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["name"] == "test/package"
