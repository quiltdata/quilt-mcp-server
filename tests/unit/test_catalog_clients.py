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


def test_catalog_package_create_infers_bucket_and_uses_full_name(monkeypatch):
    from quilt_mcp.clients import catalog

    captured: dict[str, object] = {}

    def fake_graphql_query(*, registry_url, query, variables, auth_token, timeout=30, session=None):
        captured["registry_url"] = registry_url
        captured["variables"] = variables
        captured["auth_token"] = auth_token
        return {
            "packageConstruct": {
                "package": {"bucket": "demo-bucket", "name": "demo-team/csv-data"},
                "revision": {"hash": "top-hash-123"},
            }
        }

    monkeypatch.setattr(catalog, "catalog_graphql_query", fake_graphql_query)

    result = catalog.catalog_package_create(
        registry_url="https://demo.quiltdata.com",
        package_name="demo-team/csv-data",
        auth_token="token-xyz",
        s3_uris=[
            "s3://demo-bucket/data/readme.md",
            "s3://demo-bucket/data/table.csv",
        ],
        metadata={"description": "Example"},
        message="Create package",
        flatten=False,
        copy_mode="all",
    )

    assert result["success"] is True
    assert result["top_hash"] == "top-hash-123"

    variables = captured["variables"]
    assert variables["params"]["bucket"] == "demo-bucket"
    assert variables["params"]["name"] == "demo-team/csv-data"
    assert variables["params"]["userMeta"] == {"description": "Example"}
    entries = variables["src"]["entries"]
    assert entries[0]["logicalKey"] == "data/readme.md"
    assert entries[0]["physicalKey"] == "s3://demo-bucket/data/readme.md"
    assert entries[1]["logicalKey"] == "data/table.csv"
    assert entries[1]["physicalKey"] == "s3://demo-bucket/data/table.csv"


def test_catalog_package_create_rejects_multiple_buckets():
    from quilt_mcp.clients import catalog

    result = catalog.catalog_package_create(
        registry_url="https://demo.quiltdata.com",
        package_name="demo-team/csv-data",
        auth_token="token-xyz",
        s3_uris=[
            "s3://demo-bucket-1/data/readme.md",
            "s3://demo-bucket-2/data/table.csv",
        ],
        metadata={},
        message="Create package",
        flatten=True,
        copy_mode="all",
    )

    assert result["success"] is False
    assert "same S3 bucket" in result["error"]
