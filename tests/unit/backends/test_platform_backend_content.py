"""Unit tests for Platform_Backend content operations."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from quilt_mcp.ops.exceptions import NotFoundError, BackendError
from quilt_mcp.runtime_context import (
    RuntimeAuthState,
    get_runtime_environment,
    push_runtime_context,
    reset_runtime_context,
)


def _push_jwt_context(claims=None):
    auth_state = RuntimeAuthState(
        scheme="Bearer",
        access_token="test-token",
        claims=claims
        or {
            "catalog_token": "test-catalog-token",
            "catalog_url": "https://example.quiltdata.com",
            "registry_url": "https://registry.quiltdata.com",
        },
    )
    return push_runtime_context(environment=get_runtime_environment(), auth=auth_state)


def _make_backend(monkeypatch, claims=None):
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context(claims)
    try:
        from quilt_mcp.backends.platform_backend import Platform_Backend

        return Platform_Backend()
    finally:
        reset_runtime_context(token)


# ---------------------------------------------------------------------
# Content Browsing
# ---------------------------------------------------------------------


def test_browse_content_root_directory(monkeypatch):
    """List root-level files/dirs."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "package": {
                "revision": {
                    "dir": {
                        "path": "",
                        "size": 0,
                        "children": [
                            {
                                "__typename": "PackageFile",
                                "path": "README.md",
                                "size": 1024,
                                "physicalKey": "s3://b/r",
                            },
                            {"__typename": "PackageDir", "path": "data", "size": 0},
                            {
                                "__typename": "PackageFile",
                                "path": "config.json",
                                "size": 512,
                                "physicalKey": "s3://b/c",
                            },
                        ],
                    },
                    "file": None,
                }
            }
        }
    }

    results = backend.browse_content("user/pkg", "s3://test-bucket", "")
    assert len(results) == 3
    paths = {entry.path for entry in results}
    assert paths == {"README.md", "data", "config.json"}

    # Check types
    readme = next(e for e in results if e.path == "README.md")
    assert readme.type == "file"
    assert readme.size == 1024

    data_dir = next(e for e in results if e.path == "data")
    assert data_dir.type == "directory"
    assert data_dir.size == 0


def test_browse_content_subdirectory(monkeypatch):
    """Browse with logical_key path."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "package": {
                "revision": {
                    "dir": {
                        "path": "data/raw",
                        "size": 0,
                        "children": [
                            {
                                "__typename": "PackageFile",
                                "path": "data/raw/file1.csv",
                                "size": 2048,
                                "physicalKey": "s3://b/f1",
                            },
                            {
                                "__typename": "PackageFile",
                                "path": "data/raw/file2.csv",
                                "size": 3072,
                                "physicalKey": "s3://b/f2",
                            },
                        ],
                    },
                    "file": None,
                }
            }
        }
    }

    results = backend.browse_content("user/pkg", "s3://test-bucket", "data/raw")
    assert len(results) == 2
    assert all(e.type == "file" for e in results)
    assert {e.path for e in results} == {"data/raw/file1.csv", "data/raw/file2.csv"}


def test_browse_content_mixed_children(monkeypatch):
    """Files and directories together."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "package": {
                "revision": {
                    "dir": {
                        "path": "analysis",
                        "size": 0,
                        "children": [
                            {"__typename": "PackageDir", "path": "analysis/models", "size": 0},
                            {
                                "__typename": "PackageFile",
                                "path": "analysis/results.txt",
                                "size": 512,
                                "physicalKey": "s3://b/r",
                            },
                            {"__typename": "PackageDir", "path": "analysis/plots", "size": 0},
                            {
                                "__typename": "PackageFile",
                                "path": "analysis/summary.md",
                                "size": 256,
                                "physicalKey": "s3://b/s",
                            },
                        ],
                    },
                    "file": None,
                }
            }
        }
    }

    results = backend.browse_content("user/pkg", "s3://test-bucket", "analysis")
    assert len(results) == 4

    files = [e for e in results if e.type == "file"]
    dirs = [e for e in results if e.type == "directory"]

    assert len(files) == 2
    assert len(dirs) == 2
    assert {f.path for f in files} == {"analysis/results.txt", "analysis/summary.md"}
    assert {d.path for d in dirs} == {"analysis/models", "analysis/plots"}


def test_browse_content_empty_directory(monkeypatch):
    """Handle empty directories."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "package": {
                "revision": {
                    "dir": {"path": "empty", "size": 0, "children": []},
                    "file": None,
                }
            }
        }
    }

    results = backend.browse_content("user/pkg", "s3://test-bucket", "empty")
    assert results == []


def test_browse_content_single_file(monkeypatch):
    """When path points to a file, not dir."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "package": {
                "revision": {
                    "dir": None,
                    "file": {"path": "document.pdf", "size": 10240, "physicalKey": "s3://b/doc"},
                }
            }
        }
    }

    results = backend.browse_content("user/pkg", "s3://test-bucket", "document.pdf")
    assert len(results) == 1
    assert results[0].path == "document.pdf"
    assert results[0].type == "file"
    assert results[0].size == 10240


def test_browse_content_transforms_types(monkeypatch):
    """PackageFile vs PackageDir mapping."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "package": {
                "revision": {
                    "dir": {
                        "path": "",
                        "size": 0,
                        "children": [
                            {"__typename": "PackageFile", "path": "file.txt", "size": 100, "physicalKey": "s3://b/f"},
                            {"__typename": "PackageDir", "path": "folder", "size": 0},
                        ],
                    },
                    "file": None,
                }
            }
        }
    }

    results = backend.browse_content("user/pkg", "s3://test-bucket")

    file_entry = next(e for e in results if e.path == "file.txt")
    dir_entry = next(e for e in results if e.path == "folder")

    assert file_entry.type == "file"
    assert dir_entry.type == "directory"


# ---------------------------------------------------------------------
# Content URL Generation
# ---------------------------------------------------------------------


def test_get_content_url_presigned_s3(monkeypatch):
    """Generate S3 presigned URL."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {"package": {"revision": {"file": {"physicalKey": "s3://test-bucket/path/to/file.txt"}}}}
    }

    mock_client = SimpleNamespace(
        generate_presigned_url=lambda method,
        Params,
        ExpiresIn: "https://test-bucket.s3.amazonaws.com/path/to/file.txt?signature=abc"
    )
    backend.get_boto3_client = lambda *args, **kwargs: mock_client

    url = backend.get_content_url("user/pkg", "s3://test-bucket", "file.txt")
    assert url.startswith("https://")
    assert "signature=abc" in url


def test_get_content_url_resolves_physical_key(monkeypatch):
    """Verify GraphQL query for physicalKey."""
    backend = _make_backend(monkeypatch)

    query_calls = []

    def mock_query(query, variables=None, **kwargs):
        query_calls.append({"query": query, "variables": variables})
        return {"data": {"package": {"revision": {"file": {"physicalKey": "s3://my-bucket/actual/physical/key.csv"}}}}}

    backend.execute_graphql_query = mock_query

    mock_client = SimpleNamespace(generate_presigned_url=lambda method, Params, ExpiresIn: "https://presigned-url.com")
    backend.get_boto3_client = lambda *args, **kwargs: mock_client

    url = backend.get_content_url("team/dataset", "s3://my-bucket", "data/key.csv")

    assert len(query_calls) == 1
    assert query_calls[0]["variables"]["bucket"] == "my-bucket"
    assert query_calls[0]["variables"]["name"] == "team/dataset"
    assert query_calls[0]["variables"]["path"] == "data/key.csv"
    assert url == "https://presigned-url.com"


def test_get_content_url_missing_file(monkeypatch):
    """Handle file not found in package."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {"data": {"package": {"revision": {"file": None}}}}

    with pytest.raises(NotFoundError, match="File not found"):
        backend.get_content_url("user/pkg", "s3://bucket", "nonexistent.txt")


def test_get_content_url_custom_expiration(monkeypatch):
    """Test expiration parameter (note: current implementation uses hardcoded 3600)."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {"package": {"revision": {"file": {"physicalKey": "s3://bucket/file.txt"}}}}
    }

    presigned_calls = []

    def mock_presigned(method, Params, ExpiresIn):
        presigned_calls.append({"ExpiresIn": ExpiresIn})
        return "https://url.com"

    mock_client = SimpleNamespace(generate_presigned_url=mock_presigned)
    backend.get_boto3_client = lambda *args, **kwargs: mock_client

    url = backend.get_content_url("user/pkg", "s3://bucket", "file.txt")

    # Current implementation uses hardcoded 3600
    assert len(presigned_calls) == 1
    assert presigned_calls[0]["ExpiresIn"] == 3600
    assert url == "https://url.com"


def test_get_content_url_aws_credentials(monkeypatch):
    """Verify get_boto3_client is called (which uses auth service)."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {"package": {"revision": {"file": {"physicalKey": "s3://bucket/key.txt"}}}}
    }

    boto3_calls = []

    def mock_boto3_client(service_name, region=None):
        boto3_calls.append({"service": service_name, "region": region})
        return SimpleNamespace(
            generate_presigned_url=lambda method, Params, ExpiresIn: "https://authenticated-url.com"
        )

    backend.get_boto3_client = mock_boto3_client

    url = backend.get_content_url("user/pkg", "s3://bucket", "key.txt")

    assert len(boto3_calls) == 1
    assert boto3_calls[0]["service"] == "s3"
    assert url == "https://authenticated-url.com"
