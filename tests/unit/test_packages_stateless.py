"""Stateless package tool tests validating catalog client integration."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable
from unittest.mock import Mock, patch

import pytest

from quilt_mcp.runtime import request_context
from quilt_mcp.tools import packages


@contextmanager
def runtime_token(token: str | None):
    """Helper context manager for setting the active runtime token."""

    with request_context(token, metadata={"session_id": "test-session"} if token else None):
        yield


def test_packages_list_forwards_filters_and_truncates_results():
    items = ["user/data", "other/unmatched", "user/more"]

    with (
        runtime_token("token"),
        patch("quilt_mcp.clients.catalog.catalog_packages_list", return_value=items) as mock_list,
    ):
        result = packages.packages_list(
            registry="https://registry.example.com",
            limit=1,
            prefix="user/",
        )

    mock_list.assert_called_once_with(
        registry_url="https://registry.example.com",
        auth_token="token",
        limit=1,
        prefix="user/",
    )
    assert result == {"packages": ["user/data"]}


def test_packages_list_missing_token_returns_error():
    result = packages.packages_list(registry="https://registry.example.com")

    assert result["success"] is False
    assert "Authorization token" in result["error"]


def _make_entry(logical: str, physical: str | None = None, size: int | None = None) -> dict[str, object]:
    entry = {"logicalKey": logical, "hash": "abc123"}
    if physical is not None:
        entry["physicalKey"] = physical
    if size is not None:
        entry["size"] = size
    return entry


def test_package_contents_search_filters_case_insensitive_and_signs_urls():
    entries = [
        _make_entry("Test/File.txt", "s3://bucket/Test/File.txt", 1024),
        _make_entry("other.doc", "s3://bucket/other.doc", 2048),
    ]

    with (
        runtime_token("token"),
        patch("quilt_mcp.clients.catalog.catalog_package_entries", return_value=entries) as mock_entries,
        patch("quilt_mcp.tools.packages.generate_signed_url", return_value="https://signed") as mock_sign,
    ):
        result = packages.package_contents_search(
            package_name="user/pkg",
            query="test",
            registry="https://registry.example.com",
        )

    mock_entries.assert_called_once_with(
        registry_url="https://registry.example.com",
        package_name="user/pkg",
        auth_token="token",
    )
    mock_sign.assert_called_once_with("s3://bucket/Test/File.txt")

    assert result["count"] == 1
    match = result["matches"][0]
    assert match["logical_key"] == "Test/File.txt"
    assert match["download_url"] == "https://signed"


def test_package_contents_search_missing_token_returns_error():
    result = packages.package_contents_search(
        package_name="user/pkg",
        query="anything",
        registry="https://registry.example.com",
    )

    assert result["success"] is False
    assert "Authorization token" in result["error"]


def _package_graphql_response(entries: Iterable[dict[str, object]]):
    return {
        "package": {
            "name": "user/pkg",
            "hash": "deadbeef",
            "updated": "2025-10-01T00:00:00Z",
            "entries": {
                "edges": [{"node": node} for node in entries],
            },
        }
    }


def test_package_browse_builds_summary_and_applies_limit():
    nodes = [
        _make_entry("file1.txt", "s3://bucket/file1.txt", 1024),
        _make_entry("dir/", None, None),
        _make_entry("file2.txt", "s3://bucket/file2.txt", 2048),
    ]

    with (
        runtime_token("token"),
        patch(
            "quilt_mcp.tools.packages.catalog_client.catalog_graphql_query",
            return_value=_package_graphql_response(nodes),
        ) as mock_query,
        patch("quilt_mcp.tools.packages.generate_signed_url", return_value="https://signed") as mock_sign,
    ):
        result = packages.package_browse(
            package_name="user/pkg",
            registry="https://registry.example.com",
            top=2,
        )

    mock_query.assert_called_once()
    mock_sign.assert_called_once_with("s3://bucket/file1.txt")

    assert result["success"] is True
    assert result["total_entries"] == 2
    assert result["summary"]["total_files"] == 1
    assert result["entries"][0]["logical_key"] == "file1.txt"


def test_package_browse_missing_token_returns_error():
    result = packages.package_browse("user/pkg", registry="https://registry.example.com")

    assert result["success"] is False
    assert "Authorization token" in result["error"]


def test_package_browse_graphql_error_propagates_failure():
    with (
        runtime_token("token"),
        patch(
            "quilt_mcp.tools.packages.catalog_client.catalog_graphql_query",
            side_effect=RuntimeError("boom"),
        ),
    ):
        result = packages.package_browse("user/pkg", registry="https://registry.example.com")

    assert result["success"] is False
    assert result["error"] == "Failed to fetch package contents"
    assert result["cause"] == "boom"


def test_package_diff_placeholder_response():
    with runtime_token("token"):
        result = packages.package_diff("user/pkg", "user/other", registry="https://registry.example.com")

    assert result["success"] is False
    assert "not yet implemented" in result["error"]
    assert result["package1"] == "user/pkg"
    assert result["package2"] == "user/other"


def test_packages_search_returns_results():
    gql_response = {
        "packages": {
            "edges": [
                {"node": {"name": "user/pkg1", "topHash": "hash1", "description": "Package 1"}},
                {"node": {"name": "user/pkg2", "topHash": "hash2", "description": "Package 2"}},
            ],
            "pageInfo": {"endCursor": "cursor", "hasNextPage": False},
        }
    }

    with (
        runtime_token("token"),
        patch(
            "quilt_mcp.tools.packages.catalog_client.catalog_graphql_query",
            return_value=gql_response,
        ) as mock_query,
    ):
        result = packages.packages_search(
            query="pkg",
            registry="https://registry.example.com",
            limit=2,
            from_=0,
        )

    mock_query.assert_called_once()
    assert result["success"] is True
    assert len(result["results"]) == 2
    assert result["results"][0]["name"] == "user/pkg1"
    assert result["pagination"]["end_cursor"] == "cursor"


def test_packages_search_handles_graphql_error():
    with (
        runtime_token("token"),
        patch(
            "quilt_mcp.tools.packages.catalog_client.catalog_graphql_query",
            side_effect=RuntimeError("backend boom"),
        ),
    ):
        result = packages.packages_search(
            query="pkg",
            registry="https://registry.example.com",
        )

    assert result["success"] is False
    assert "backend boom" in result["error"]
