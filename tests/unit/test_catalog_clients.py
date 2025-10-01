"""Stateless catalog client behaviour tests."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest


def test_execute_catalog_query_requires_token():
    from quilt_mcp.clients import catalog

    with pytest.raises(ValueError):
        catalog.execute_catalog_query(
            "https://catalog.example/graphql",
            query="query Test { ping }",
            variables={},
            auth_token="",
        )


@patch("quilt_mcp.clients.catalog.requests.post")
def test_execute_catalog_query_forwards_token(mock_post):
    from quilt_mcp.clients import catalog

    response = Mock()
    response.json.return_value = {"data": {"ping": "pong"}}
    response.raise_for_status.return_value = None
    mock_post.return_value = response

    result = catalog.execute_catalog_query(
        "https://catalog.example/graphql",
        query="query Test { ping }",
        variables={"foo": "bar"},
        auth_token="token-123",
    )

    assert result == {"ping": "pong"}

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer token-123"
    assert headers["Content-Type"] == "application/json"


def test_rest_request_requires_token():
    from quilt_mcp.clients import catalog

    with pytest.raises(ValueError):
        catalog.catalog_rest_request(
            method="GET",
            url="https://catalog.example/api/users",
            auth_token="",
        )


@patch("quilt_mcp.clients.catalog.requests.request")
def test_rest_request_forwards_token(mock_request):
    from quilt_mcp.clients import catalog

    response = Mock()
    response.json.return_value = {"users": []}
    response.raise_for_status.return_value = None
    mock_request.return_value = response

    payload = catalog.catalog_rest_request(
        method="GET",
        url="https://catalog.example/api/users",
        auth_token="token-456",
    )

    assert payload == {"users": []}

    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args
    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer token-456"
    assert headers["Content-Type"] == "application/json"


