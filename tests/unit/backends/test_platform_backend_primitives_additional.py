"""Additional primitive/helper coverage for Platform_Backend."""

from __future__ import annotations

from datetime import datetime

import pytest
import requests

from quilt_mcp.ops.exceptions import AuthenticationError, NotFoundError, ValidationError
from tests.unit.backends.test_platform_backend_packages_part1 import _make_backend


def test_get_graphql_endpoint_missing_raises(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend._graphql_endpoint = None

    with pytest.raises(AuthenticationError, match="GraphQL endpoint not configured"):
        backend.get_graphql_endpoint()


def test_get_graphql_auth_headers_missing_token_raises(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend._access_token = ""

    with pytest.raises(AuthenticationError, match="Missing JWT access token"):
        backend.get_graphql_auth_headers()


def test_execute_graphql_query_non_object_json_raises_backend_error(monkeypatch):
    backend = _make_backend(monkeypatch)

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return ["not", "an", "object"]

    backend._session.post = lambda *args, **kwargs: DummyResponse()

    with pytest.raises(Exception, match="GraphQL response was not a JSON object"):
        backend.execute_graphql_query("query { ok }")


def test_execute_graphql_query_http_unauthorized_raises_auth_error(monkeypatch):
    backend = _make_backend(monkeypatch)

    class DummyResponse:
        status_code = 401
        text = "unauthorized"

        def raise_for_status(self):
            raise requests.HTTPError(response=self)

        def json(self):
            return {}

    backend._session.post = lambda *args, **kwargs: DummyResponse()

    with pytest.raises(AuthenticationError, match="not authorized"):
        backend.execute_graphql_query("query { ok }")


def test_execute_graphql_query_http_other_status_raises_backend_error(monkeypatch):
    backend = _make_backend(monkeypatch)

    class DummyResponse:
        status_code = 500
        text = "internal error"

        def raise_for_status(self):
            raise requests.HTTPError(response=self)

        def json(self):
            return {}

    backend._session.post = lambda *args, **kwargs: DummyResponse()

    with pytest.raises(Exception, match="internal error"):
        backend.execute_graphql_query("query { ok }")


def test_backend_get_package_not_found(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {"data": {"package": None}}

    with pytest.raises(NotFoundError, match="Package not found"):
        backend._backend_get_package("team/missing", "s3://bucket")


def test_backend_get_package_entries_ignores_non_dict_entries(monkeypatch):
    backend = _make_backend(monkeypatch)
    package = {"revision": {"contentsFlatMap": {"a.txt": {"physicalKey": "s3://b/a"}, "bad.txt": "skip"}}}

    entries = backend._backend_get_package_entries(package)
    assert list(entries.keys()) == ["a.txt"]
    assert entries["a.txt"]["physicalKey"] == "s3://b/a"


def test_backend_get_package_metadata_defaults_to_empty_dict(monkeypatch):
    backend = _make_backend(monkeypatch)

    assert backend._backend_get_package_metadata({"revision": {}}) == {}


def test_backend_search_packages_new_api_shape(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "searchPackages": {
                "__typename": "PackageSearchResults",
                "hits": [{"name": "team/data", "hash": "h1"}],
            }
        }
    }

    results = backend._backend_search_packages("data", "s3://bucket")
    assert results[0]["name"] == "team/data"
    assert results[0]["top_hash"] == "h1"


def test_backend_search_packages_invalid_input_raises(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {"searchPackages": {"__typename": "InvalidInput", "errors": [{"path": "q", "message": "bad"}]}}
    }

    with pytest.raises(ValidationError, match="Search invalid input"):
        backend._backend_search_packages("data", "s3://bucket")


def test_backend_search_packages_operation_error_raises(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {"searchPackages": {"__typename": "OperationError", "message": "failed"}}
    }

    with pytest.raises(Exception, match="Search operation error"):
        backend._backend_search_packages("data", "s3://bucket")


def test_backend_search_packages_unexpected_type_raises(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {"data": {"searchPackages": {"__typename": "WeirdType"}}}

    with pytest.raises(Exception, match="Unexpected search response type"):
        backend._backend_search_packages("data", "s3://bucket")


def test_backend_browse_package_content_file_fallback(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "package": {
                "revision": {
                    "dir": None,
                    "file": {"path": "only.csv", "size": 7, "physicalKey": "s3://b/only.csv"},
                }
            }
        }
    }

    result = backend._backend_browse_package_content({"name": "team/pkg", "bucket": "bucket"}, "only.csv")
    assert result == [{"path": "only.csv", "size": 7, "type": "file"}]


def test_backend_browse_package_content_path_not_found(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {"package": {"revision": {"dir": None, "file": None}}}
    }

    with pytest.raises(NotFoundError, match="Path not found"):
        backend._backend_browse_package_content({"name": "team/pkg", "bucket": "bucket"}, "missing")


def test_backend_get_file_url_missing_revision_hash_raises(monkeypatch):
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {"data": {"package": {"revision": {"hash": None}}}}

    with pytest.raises(Exception, match="Missing revision hash"):
        backend._backend_get_file_url("team/pkg", "s3://bucket", "x.txt")


def test_backend_get_session_info(monkeypatch):
    backend = _make_backend(monkeypatch)

    info = backend._backend_get_session_info()
    assert info["is_authenticated"] is True
    assert info["catalog_url"] == "https://example.quiltdata.com"
    assert info["registry_url"] == "https://registry.example.com"


def test_backend_get_boto3_session_not_supported(monkeypatch):
    backend = _make_backend(monkeypatch)

    with pytest.raises(AuthenticationError, match="not available"):
        backend._backend_get_boto3_session()


def test_helper_transforms_and_parsing(monkeypatch):
    backend = _make_backend(monkeypatch)

    assert backend._normalize_package_datetime(datetime(2025, 1, 1)) == "2025-01-01T00:00:00"
    assert backend._normalize_size("12") == 12
    assert backend._normalize_size("nan") is None
    assert backend._extract_description({"description": 123}, "fallback") == "123"
    assert backend._extract_description(None, "fallback") == "fallback"
    assert backend._extract_tags_from_meta({"tags": "single"}) == ["single"]
    assert backend._extract_tags_from_meta({"keywords": ["a", None, "b"]}) == ["a", "b"]
    assert backend._extract_tags_from_meta({"tags": 1}) == []
    assert backend._parse_meta('{"a": 1}') == {"a": 1}
    assert backend._parse_meta("[1,2,3]") is None
    assert backend._parse_meta("not-json") is None


def test_extract_bucket_from_registry_variants(monkeypatch):
    backend = _make_backend(monkeypatch)

    assert backend._extract_bucket_from_registry("") == ""
    assert backend._extract_bucket_from_registry("s3://my-bucket/path") == "my-bucket"
    assert (
        backend._extract_bucket_from_registry("https://my-bucket.s3.amazonaws.com/path")
        == "my-bucket.s3.amazonaws.com"
    )
    assert backend._extract_bucket_from_registry("plain-bucket/path") == "plain-bucket"
