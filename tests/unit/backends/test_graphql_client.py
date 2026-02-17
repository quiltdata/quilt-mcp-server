from unittest.mock import Mock

import pytest

from quilt_mcp.backends.platform_graphql_client import PlatformGraphQLClient


def _mock_response(*, payload, raise_exc=None):
    response = Mock()
    response.json.return_value = payload
    if raise_exc is None:
        response.raise_for_status.return_value = None
    else:
        response.raise_for_status.side_effect = raise_exc
    return response


def test_execute_success_with_variables():
    session = Mock()
    response = _mock_response(payload={"data": {"ok": True}})
    session.post.return_value = response
    client = PlatformGraphQLClient(session, "https://example.invalid/graphql", "Bearer token")

    result = client.execute("query Test { ok }", {"x": 1})

    assert result == {"data": {"ok": True}}
    session.post.assert_called_once()
    _, kwargs = session.post.call_args
    assert kwargs["json"] == {"query": "query Test { ok }", "variables": {"x": 1}}
    assert kwargs["headers"]["Authorization"] == "Bearer token"
    response.raise_for_status.assert_called_once()


def test_execute_success_without_variables():
    session = Mock()
    response = _mock_response(payload={"data": {"ok": True}})
    session.post.return_value = response
    client = PlatformGraphQLClient(session, "https://example.invalid/graphql", "Bearer token")

    result = client.execute("query Test { ok }")

    assert result == {"data": {"ok": True}}
    _, kwargs = session.post.call_args
    assert kwargs["json"] == {"query": "query Test { ok }"}


def test_execute_raises_on_non_object_json():
    session = Mock()
    response = _mock_response(payload=["not", "a", "dict"])
    session.post.return_value = response
    client = PlatformGraphQLClient(session, "https://example.invalid/graphql", "Bearer token")

    with pytest.raises(ValueError, match="GraphQL response was not a JSON object"):
        client.execute("query Test { ok }")


def test_execute_propagates_http_errors():
    session = Mock()
    response = _mock_response(payload={"data": {}}, raise_exc=RuntimeError("http error"))
    session.post.return_value = response
    client = PlatformGraphQLClient(session, "https://example.invalid/graphql", "Bearer token")

    with pytest.raises(RuntimeError, match="http error"):
        client.execute("query Test { ok }")
