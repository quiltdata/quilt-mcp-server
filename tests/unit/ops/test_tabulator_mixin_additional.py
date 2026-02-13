"""Additional unit tests for TabulatorMixin branch coverage."""

from unittest.mock import Mock, patch

import pytest
import requests

from quilt_mcp.ops.exceptions import AuthenticationError, BackendError
from quilt_mcp.ops.tabulator_mixin import TabulatorMixin


class ConcreteBackend(TabulatorMixin):
    """Concrete backend using real execute_graphql_query implementation."""

    def get_graphql_endpoint(self) -> str:
        return "https://example.test/graphql"

    def get_graphql_auth_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer token"}


def test_execute_graphql_query_success_with_variables():
    backend = ConcreteBackend()
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"data": {"ok": True}}

    with patch("requests.post", return_value=mock_response) as mock_post:
        result = backend.execute_graphql_query("query { ok }", {"x": 1})

    assert result == {"data": {"ok": True}}
    mock_post.assert_called_once_with(
        "https://example.test/graphql",
        json={"query": "query { ok }", "variables": {"x": 1}},
        headers={"Authorization": "Bearer token"},
    )


def test_execute_graphql_query_raises_backend_error_for_graphql_errors():
    backend = ConcreteBackend()
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"errors": [{"message": "boom"}, {"message": "bad input"}]}

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(BackendError, match="boom; bad input"):
            backend.execute_graphql_query("query { bad }")


def test_execute_graphql_query_raises_authentication_error_on_403():
    backend = ConcreteBackend()
    response = Mock()
    response.status_code = 403
    response.text = "forbidden"

    http_error = requests.HTTPError("forbidden")
    http_error.response = response
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = http_error

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(AuthenticationError, match="not authorized"):
            backend.execute_graphql_query("query { denied }")


def test_execute_graphql_query_parses_http_error_graphql_payload():
    backend = ConcreteBackend()
    response = Mock()
    response.status_code = 500
    response.text = "internal"
    response.json.return_value = {"errors": [{"message": "resolver failed"}]}

    http_error = requests.HTTPError("internal")
    http_error.response = response
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = http_error

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(BackendError, match="resolver failed"):
            backend.execute_graphql_query("query { broken }")


def test_get_open_query_status_success_and_default_false():
    backend = ConcreteBackend()
    backend.execute_graphql_query = Mock(
        side_effect=[
            {"data": {"admin": {"tabulatorOpenQuery": True}}},
            {"data": {"admin": {}}},
        ]
    )

    first = backend.get_open_query_status()
    second = backend.get_open_query_status()

    assert first == {"success": True, "open_query_enabled": True}
    assert second == {"success": True, "open_query_enabled": False}


def test_get_open_query_status_wraps_backend_error():
    backend = ConcreteBackend()
    backend.execute_graphql_query = Mock(side_effect=Exception("down"))

    with pytest.raises(BackendError, match="Failed to get open query status"):
        backend.get_open_query_status()


def test_set_open_query_formats_enabled_and_disabled_messages():
    backend = ConcreteBackend()
    backend.execute_graphql_query = Mock(
        side_effect=[
            {"data": {"admin": {"setTabulatorOpenQuery": {"tabulatorOpenQuery": True}}}},
            {"data": {"admin": {"setTabulatorOpenQuery": {"tabulatorOpenQuery": False}}}},
        ]
    )

    enabled = backend.set_open_query(True)
    disabled = backend.set_open_query(False)

    assert enabled["message"] == "Open query enabled"
    assert disabled["message"] == "Open query disabled"


def test_set_open_query_defaults_to_requested_value_when_response_missing():
    backend = ConcreteBackend()
    backend.execute_graphql_query = Mock(return_value={"data": {"admin": {}}})

    result = backend.set_open_query(True)

    assert result["success"] is True
    assert result["open_query_enabled"] is True
    assert result["message"] == "Open query enabled"


def test_set_open_query_wraps_backend_error():
    backend = ConcreteBackend()
    backend.execute_graphql_query = Mock(side_effect=Exception("bad"))

    with pytest.raises(BackendError, match="Failed to set open query status"):
        backend.set_open_query(True)


def test_abstract_methods_raise_not_implemented():
    mixin = TabulatorMixin()
    with pytest.raises(NotImplementedError):
        mixin.get_graphql_endpoint()
    with pytest.raises(NotImplementedError):
        mixin.get_graphql_auth_headers()
