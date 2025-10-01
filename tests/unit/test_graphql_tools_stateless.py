"""Stateless tests for GraphQL helper functions using catalog client."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import graphql


@contextmanager
def runtime_token(token: str):
    with request_context(token, metadata={"session_id": "graphql"}):
        yield


def test_catalog_graphql_query_requires_token(monkeypatch):
    monkeypatch.delenv("QUILT_CATALOG_URL", raising=False)
    result = graphql.catalog_graphql_query("query")
    assert result["success"] is False
    assert "token" in result["error"].lower()


def test_objects_search_graphql_calls_catalog(monkeypatch):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://catalog")

    mock_response = {
        "objects": {
            "edges": [
                {
                    "node": {
                        "key": "data.csv",
                        "size": 123,
                        "updated": "2025-01-01",
                        "contentType": "text/csv",
                        "extension": "csv",
                        "package": None,
                    }
                }
            ],
            "pageInfo": {"endCursor": "c", "hasNextPage": False},
        }
    }

    with runtime_token("token"):
        with patch(
            "quilt_mcp.clients.catalog.catalog_graphql_query",
            return_value=mock_response,
        ) as mock_query:
            result = graphql.objects_search_graphql("bucket")

    mock_query.assert_called_once()
    _, kwargs = mock_query.call_args
    assert kwargs["auth_token"] == "token"
    assert result["success"] is True
    assert result["objects"][0]["key"] == "data.csv"
