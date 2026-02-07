"""Unit tests for Platform_Backend package operations."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
import sys

import pytest

from quilt_mcp.ops.exceptions import ValidationError, BackendError, NotFoundError
from quilt_mcp.context.runtime_context import (
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
            "id": "user-1",
            "uuid": "uuid-1",
            "exp": 9999999999,
        },
    )
    return push_runtime_context(environment=get_runtime_environment(), auth=auth_state)


def _make_backend(monkeypatch, claims=None):
    monkeypatch.setenv("QUILT_CATALOG_URL", "https://example.quiltdata.com")
    monkeypatch.setenv("QUILT_REGISTRY_URL", "https://registry.example.com")
    monkeypatch.setenv("QUILT_GRAPHQL_ENDPOINT", "https://registry.example.com/graphql")
    token = _push_jwt_context(claims)
    try:
        from quilt_mcp.backends.platform_backend import Platform_Backend

        return Platform_Backend()
    finally:
        reset_runtime_context(token)


# ---------------------------------------------------------------------
# Search Operations
# ---------------------------------------------------------------------


def test_search_packages_basic_query(monkeypatch):
    """Test basic search with results."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "searchPackages": {
                "__typename": "PackagesSearchResultSet",
                "firstPage": {
                    "hits": [
                        {
                            "name": "user/dataset",
                            "bucket": "test-bucket",
                            "hash": "abc123",
                            "modified": "2024-01-01T00:00:00Z",
                            "comment": "Initial commit",
                            "meta": '{"description": "Test dataset"}',
                        }
                    ]
                },
            }
        }
    }

    results = backend.search_packages("dataset", "s3://test-bucket")
    assert len(results) == 1
    assert results[0].name == "user/dataset"
    assert results[0].top_hash == "abc123"
    assert results[0].description == "Test dataset"


def test_search_packages_transforms_metadata(monkeypatch):
    """Verify JSON metadata parsing in search results."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "searchPackages": {
                "__typename": "PackagesSearchResultSet",
                "firstPage": {
                    "hits": [
                        {
                            "name": "team/data",
                            "bucket": "test-bucket",
                            "hash": "def456",
                            "modified": "2024-02-01T00:00:00Z",
                            "comment": "Updated",
                            "meta": '{"description": "Updated dataset", "tags": ["tag1", "tag2"], "version": "1.0"}',
                        }
                    ]
                },
            }
        }
    }

    results = backend.search_packages("data", "s3://test-bucket")
    assert len(results) == 1
    assert results[0].description == "Updated dataset"
    assert results[0].tags == ["tag1", "tag2"]


def test_search_packages_empty_results(monkeypatch):
    """Handle empty result sets."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {"searchPackages": {"__typename": "EmptySearchResultSet", "_": None}}
    }

    results = backend.search_packages("nonexistent", "s3://test-bucket")
    assert results == []


def test_search_packages_pagination(monkeypatch):
    """Verify firstPage handling (size: 1000)."""
    backend = _make_backend(monkeypatch)

    # Create 3 mock hits
    hits = []
    for i in range(3):
        hits.append(
            {
                "name": f"user/dataset{i}",
                "bucket": "test-bucket",
                "hash": f"hash{i}",
                "modified": "2024-01-01T00:00:00Z",
                "comment": f"Dataset {i}",
                "meta": f'{{"description": "Dataset {i}"}}',
            }
        )

    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "searchPackages": {
                "__typename": "PackagesSearchResultSet",
                "firstPage": {"hits": hits},
            }
        }
    }

    results = backend.search_packages("dataset", "s3://test-bucket")
    assert len(results) == 3
    assert [r.name for r in results] == ["user/dataset0", "user/dataset1", "user/dataset2"]


def test_search_packages_malformed_meta(monkeypatch):
    """Handle invalid JSON in meta field."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "searchPackages": {
                "__typename": "PackagesSearchResultSet",
                "firstPage": {
                    "hits": [
                        {
                            "name": "user/data",
                            "bucket": "test-bucket",
                            "hash": "abc",
                            "modified": "2024-01-01T00:00:00Z",
                            "comment": "Fallback description",
                            "meta": "{invalid json",
                        }
                    ]
                },
            }
        }
    }

    results = backend.search_packages("data", "s3://test-bucket")
    assert len(results) == 1
    # Should fall back to comment when meta parsing fails
    assert results[0].description == "Fallback description"
    assert results[0].tags == []


# ---------------------------------------------------------------------
# Package Info Retrieval
# ---------------------------------------------------------------------


def test_get_package_info_success(monkeypatch):
    """Basic package info retrieval."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "package": {
                "bucket": "test-bucket",
                "name": "user/dataset",
                "modified": "2024-01-15T10:30:00Z",
                "revision": {
                    "hash": "abc123",
                    "message": "Initial version",
                    "userMeta": {"description": "Test package", "version": "1.0"},
                },
            }
        }
    }

    info = backend.get_package_info("user/dataset", "s3://test-bucket")
    assert info.name == "user/dataset"
    assert info.bucket == "test-bucket"
    assert info.top_hash == "abc123"
    assert info.description == "Test package"


def test_get_package_info_missing_package(monkeypatch):
    """Raise NotFoundError for null package."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {"data": {"package": None}}

    with pytest.raises(NotFoundError, match="Package not found"):
        backend.get_package_info("user/missing", "s3://test-bucket")


def test_get_package_info_transforms_metadata(monkeypatch):
    """Parse metadata JSON from userMeta."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "package": {
                "bucket": "test-bucket",
                "name": "team/data",
                "modified": "2024-02-01T00:00:00Z",
                "revision": {
                    "hash": "def456",
                    "message": "Updated",
                    "userMeta": '{"description": "Parsed from JSON", "tags": ["experimental", "test"]}',
                },
            }
        }
    }

    info = backend.get_package_info("team/data", "s3://test-bucket")
    assert info.description == "Parsed from JSON"
    assert info.tags == ["experimental", "test"]


def test_get_package_info_handles_null_fields(monkeypatch):
    """Handle optional fields gracefully."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "package": {
                "bucket": "test-bucket",
                "name": "user/minimal",
                "modified": None,
                "revision": {"hash": "xyz789", "message": None, "userMeta": None},
            }
        }
    }

    info = backend.get_package_info("user/minimal", "s3://test-bucket")
    assert info.name == "user/minimal"
    assert info.top_hash == "xyz789"
    assert info.description is None
    assert info.modified_date == "None"


# ---------------------------------------------------------------------
# Package Diffing
# ---------------------------------------------------------------------


def test_diff_packages_detects_added_files(monkeypatch):
    """Identify new files in package2."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "p1": {"revision": {"contentsFlatMap": {"a.txt": {"size": 100, "hash": "h1", "physicalKey": "s3://b/a"}}}},
            "p2": {
                "revision": {
                    "contentsFlatMap": {
                        "a.txt": {"size": 100, "hash": "h1", "physicalKey": "s3://b/a"},
                        "b.txt": {"size": 200, "hash": "h2", "physicalKey": "s3://b/b"},
                    }
                }
            },
        }
    }

    diff = backend.diff_packages("team/pkg1", "team/pkg2", "s3://test-bucket")
    assert diff["added"] == ["b.txt"]
    assert diff["modified"] == []
    assert diff["deleted"] == []


def test_diff_packages_detects_modified_files(monkeypatch):
    """Detect size/hash changes."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "p1": {"revision": {"contentsFlatMap": {"a.txt": {"size": 100, "hash": "h1", "physicalKey": "s3://b/a"}}}},
            "p2": {
                "revision": {"contentsFlatMap": {"a.txt": {"size": 200, "hash": "h2", "physicalKey": "s3://b/a2"}}}
            },
        }
    }

    diff = backend.diff_packages("team/pkg1", "team/pkg2", "s3://test-bucket")
    assert diff["added"] == []
    assert diff["modified"] == ["a.txt"]
    assert diff["deleted"] == []


def test_diff_packages_detects_removed_files(monkeypatch):
    """Identify deleted files."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "p1": {
                "revision": {
                    "contentsFlatMap": {
                        "a.txt": {"size": 100, "hash": "h1", "physicalKey": "s3://b/a"},
                        "b.txt": {"size": 200, "hash": "h2", "physicalKey": "s3://b/b"},
                    }
                }
            },
            "p2": {"revision": {"contentsFlatMap": {"a.txt": {"size": 100, "hash": "h1", "physicalKey": "s3://b/a"}}}},
        }
    }

    diff = backend.diff_packages("team/pkg1", "team/pkg2", "s3://test-bucket")
    assert diff["added"] == []
    assert diff["modified"] == []
    assert diff["deleted"] == ["b.txt"]


def test_diff_packages_identical_packages(monkeypatch):
    """Handle no changes."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "p1": {"revision": {"contentsFlatMap": {"a.txt": {"size": 100, "hash": "h1", "physicalKey": "s3://b/a"}}}},
            "p2": {"revision": {"contentsFlatMap": {"a.txt": {"size": 100, "hash": "h1", "physicalKey": "s3://b/a"}}}},
        }
    }

    diff = backend.diff_packages("team/pkg1", "team/pkg1", "s3://test-bucket")
    assert diff["added"] == []
    assert diff["modified"] == []
    assert diff["deleted"] == []


def test_diff_packages_complex_scenario(monkeypatch):
    """Mixed adds/modifies/removes."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "p1": {
                "revision": {
                    "contentsFlatMap": {
                        "keep.txt": {"size": 100, "hash": "h1", "physicalKey": "s3://b/k"},
                        "modify.txt": {"size": 200, "hash": "h2", "physicalKey": "s3://b/m1"},
                        "delete.txt": {"size": 300, "hash": "h3", "physicalKey": "s3://b/d"},
                    }
                }
            },
            "p2": {
                "revision": {
                    "contentsFlatMap": {
                        "keep.txt": {"size": 100, "hash": "h1", "physicalKey": "s3://b/k"},
                        "modify.txt": {"size": 250, "hash": "h2b", "physicalKey": "s3://b/m2"},
                        "add.txt": {"size": 400, "hash": "h4", "physicalKey": "s3://b/a"},
                    }
                }
            },
        }
    }

    diff = backend.diff_packages("team/pkg1", "team/pkg2", "s3://test-bucket")
    assert diff["added"] == ["add.txt"]
    assert diff["modified"] == ["modify.txt"]
    assert diff["deleted"] == ["delete.txt"]


# ---------------------------------------------------------------------
# Package Creation
# ---------------------------------------------------------------------
