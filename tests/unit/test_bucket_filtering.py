"""Unit tests for bucket filtering in package search."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.search.backends.graphql import EnterpriseGraphQLBackend, PackageSearchResponse
from quilt_mcp.search.backends.base import SearchResult


class TestBucketFilteringPackageSearch:
    """Test that bucket filtering works correctly in package search."""

    @pytest.mark.asyncio
    async def test_search_packages_with_singular_bucket_filter(self, monkeypatch):
        """Test that singular 'bucket' parameter is correctly handled."""
        backend = EnterpriseGraphQLBackend()

        # Track the GraphQL variables that were sent
        graphql_variables = {}

        async def fake_execute(query, variables):
            nonlocal graphql_variables
            graphql_variables = variables
            return {
                "data": {
                    "searchPackages": {
                        "total": 1,
                        "stats": {},
                        "firstPage": {
                            "hits": [
                                {
                                    "id": "pkg-1",
                                    "score": 1.0,
                                    "bucket": "nextflowtower",
                                    "name": "test-package",
                                    "pointer": "latest",
                                    "hash": "abc123",
                                    "size": 1024,
                                    "modified": "2025-10-09T00:00:00Z",
                                    "totalEntriesCount": 5,
                                    "comment": "Test package",
                                    "workflow": {},
                                }
                            ],
                            "cursor": None,
                        },
                    }
                }
            }

        monkeypatch.setattr(backend, "_execute_graphql_query", fake_execute)
        monkeypatch.setattr(backend, "_fetch_more_packages", AsyncMock(return_value=([], None)))

        # Test with singular 'bucket' parameter (as string)
        with request_context("test-token", metadata={"session_id": "test"}):
            payload = await backend._search_packages_global(
                query="*",
                filters={"bucket": "nextflowtower"},
                limit=10,
                offset=0
            )

        # Verify the backend correctly sent the bucket filter to GraphQL
        assert graphql_variables["buckets"] == ["nextflowtower"], \
            f"Expected ['nextflowtower'], got {graphql_variables['buckets']}"

        # Verify results
        assert isinstance(payload, PackageSearchResponse)
        assert len(payload.results) == 1
        assert payload.results[0].metadata["bucket"] == "nextflowtower"

    @pytest.mark.asyncio
    async def test_search_packages_with_plural_buckets_filter(self, monkeypatch):
        """Test that plural 'buckets' parameter still works."""
        backend = EnterpriseGraphQLBackend()

        graphql_variables = {}

        async def fake_execute(query, variables):
            nonlocal graphql_variables
            graphql_variables = variables
            return {
                "data": {
                    "searchPackages": {
                        "total": 0,
                        "stats": {},
                        "firstPage": {
                            "hits": [],
                            "cursor": None,
                        },
                    }
                }
            }

        monkeypatch.setattr(backend, "_execute_graphql_query", fake_execute)
        monkeypatch.setattr(backend, "_fetch_more_packages", AsyncMock(return_value=([], None)))

        # Test with plural 'buckets' parameter (as list)
        with request_context("test-token", metadata={"session_id": "test"}):
            payload = await backend._search_packages_global(
                query="*",
                filters={"buckets": ["bucket1", "bucket2"]},
                limit=10,
                offset=0
            )

        # Verify the backend correctly sent the buckets filter to GraphQL
        assert graphql_variables["buckets"] == ["bucket1", "bucket2"], \
            f"Expected ['bucket1', 'bucket2'], got {graphql_variables['buckets']}"

    @pytest.mark.asyncio
    async def test_search_packages_with_bucket_as_list(self, monkeypatch):
        """Test that singular 'bucket' parameter as a list is handled."""
        backend = EnterpriseGraphQLBackend()

        graphql_variables = {}

        async def fake_execute(query, variables):
            nonlocal graphql_variables
            graphql_variables = variables
            return {
                "data": {
                    "searchPackages": {
                        "total": 0,
                        "stats": {},
                        "firstPage": {
                            "hits": [],
                            "cursor": None,
                        },
                    }
                }
            }

        monkeypatch.setattr(backend, "_execute_graphql_query", fake_execute)
        monkeypatch.setattr(backend, "_fetch_more_packages", AsyncMock(return_value=([], None)))

        # Test with singular 'bucket' parameter as a list (edge case)
        with request_context("test-token", metadata={"session_id": "test"}):
            payload = await backend._search_packages_global(
                query="*",
                filters={"bucket": ["nextflowtower"]},
                limit=10,
                offset=0
            )

        # Verify the backend correctly converted it to a list
        assert graphql_variables["buckets"] == ["nextflowtower"], \
            f"Expected ['nextflowtower'], got {graphql_variables['buckets']}"

    @pytest.mark.asyncio
    async def test_search_packages_no_bucket_filter(self, monkeypatch):
        """Test that search without bucket filter searches all buckets."""
        backend = EnterpriseGraphQLBackend()

        graphql_variables = {}

        async def fake_execute(query, variables):
            nonlocal graphql_variables
            graphql_variables = variables
            return {
                "data": {
                    "searchPackages": {
                        "total": 0,
                        "stats": {},
                        "firstPage": {
                            "hits": [],
                            "cursor": None,
                        },
                    }
                }
            }

        monkeypatch.setattr(backend, "_execute_graphql_query", fake_execute)
        monkeypatch.setattr(backend, "_fetch_more_packages", AsyncMock(return_value=([], None)))

        # Test without any bucket filter
        with request_context("test-token", metadata={"session_id": "test"}):
            payload = await backend._search_packages_global(
                query="*",
                filters=None,
                limit=10,
                offset=0
            )

        # Verify the backend sent an empty buckets list (searches all buckets)
        assert graphql_variables["buckets"] == [], \
            f"Expected [], got {graphql_variables['buckets']}"

