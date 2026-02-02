"""Unit tests for Platform_Backend package operations."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
import sys

import pytest

from quilt_mcp.ops.exceptions import ValidationError, BackendError, NotFoundError
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
# Package Listing
# ---------------------------------------------------------------------


def test_list_all_packages_single_page(monkeypatch):
    """List packages < 100 (no pagination)."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {
            "packages": {
                "total": 3,
                "page": [
                    {"name": "user/pkg1"},
                    {"name": "user/pkg2"},
                    {"name": "team/pkg3"},
                ],
            }
        }
    }

    packages = backend.list_all_packages("s3://test-bucket")
    assert packages == ["user/pkg1", "user/pkg2", "team/pkg3"]


def test_list_all_packages_pagination(monkeypatch):
    """Test pagination with 101+ packages."""
    backend = _make_backend(monkeypatch)

    # Track which page is being requested
    call_count = [0]

    def mock_query(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First page
            return {
                "data": {
                    "packages": {
                        "total": 101,
                        "page": [{"name": f"user/pkg{i}"} for i in range(100)],
                    }
                }
            }
        else:
            # Second page
            return {"data": {"packages": {"total": 101, "page": [{"name": "user/pkg100"}]}}}

    backend.execute_graphql_query = mock_query
    packages = backend.list_all_packages("s3://test-bucket")

    assert len(packages) == 101
    assert packages[0] == "user/pkg0"
    assert packages[99] == "user/pkg99"
    assert packages[100] == "user/pkg100"


def test_list_all_packages_empty_bucket(monkeypatch):
    """Handle zero packages."""
    backend = _make_backend(monkeypatch)
    backend.execute_graphql_query = lambda *args, **kwargs: {
        "data": {"packages": {"total": 0, "page": []}}
    }

    packages = backend.list_all_packages("s3://test-bucket")
    assert packages == []


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
            "p2": {"revision": {"contentsFlatMap": {"a.txt": {"size": 200, "hash": "h2", "physicalKey": "s3://b/a2"}}}},
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


def test_create_package_revision_basic(monkeypatch):
    """Create package with files."""
    backend = _make_backend(monkeypatch)

    @contextmanager
    def _noop_creds():
        yield

    backend._with_aws_credentials = _noop_creds

    class FakePackage:
        def __init__(self):
            self.meta = {}
            self.files = []

        def set(self, logical_key, s3_uri):
            self.files.append((logical_key, s3_uri))

        def set_meta(self, meta):
            self.meta = meta

        def push(self, *args, **kwargs):
            return "test-hash-123"

    fake_quilt3 = SimpleNamespace(Package=FakePackage)
    monkeypatch.setitem(sys.modules, "quilt3", fake_quilt3)

    result = backend.create_package_revision(
        "user/test-pkg",
        ["s3://bucket/path/file1.txt", "s3://bucket/path/file2.csv"],
        registry="s3://bucket",
    )

    assert result.success is True
    assert result.package_name == "user/test-pkg"
    assert result.top_hash == "test-hash-123"
    assert result.file_count == 2


def test_create_package_revision_with_metadata(monkeypatch):
    """Include package metadata."""
    backend = _make_backend(monkeypatch)

    @contextmanager
    def _noop_creds():
        yield

    backend._with_aws_credentials = _noop_creds

    class FakePackage:
        def __init__(self):
            self.meta = {}
            self.files = []

        def set(self, logical_key, s3_uri):
            self.files.append((logical_key, s3_uri))

        def set_meta(self, meta):
            self.meta = meta

        def push(self, *args, **kwargs):
            return "meta-hash-456"

    fake_pkg_instance = FakePackage()
    fake_quilt3 = SimpleNamespace(Package=lambda: fake_pkg_instance)
    monkeypatch.setitem(sys.modules, "quilt3", fake_quilt3)

    metadata = {"description": "Test package", "version": "1.0"}
    result = backend.create_package_revision(
        "user/metadata-pkg",
        ["s3://bucket/data.txt"],
        metadata=metadata,
        registry="s3://bucket",
    )

    assert result.success is True
    assert fake_pkg_instance.meta == metadata


def test_create_package_revision_copy_mode(monkeypatch):
    """Test copy vs symlink."""
    backend = _make_backend(monkeypatch)

    @contextmanager
    def _noop_creds():
        yield

    backend._with_aws_credentials = _noop_creds

    push_calls = []

    class FakePackage:
        def __init__(self):
            self.meta = {}

        def set(self, logical_key, s3_uri):
            pass

        def set_meta(self, meta):
            pass

        def push(self, *args, **kwargs):
            push_calls.append(kwargs)
            return "copy-hash"

    fake_quilt3 = SimpleNamespace(Package=FakePackage)
    monkeypatch.setitem(sys.modules, "quilt3", fake_quilt3)

    # Test copy=False (symlink mode)
    result = backend.create_package_revision(
        "user/symlink-pkg", ["s3://bucket/file.txt"], registry="s3://bucket", copy=False
    )
    assert result.success is True
    assert "selector_fn" in push_calls[0]

    # Reset and test copy=True
    push_calls.clear()
    result = backend.create_package_revision(
        "user/copy-pkg", ["s3://bucket/file.txt"], registry="s3://bucket", copy=True
    )
    assert result.success is True
    assert "selector_fn" not in push_calls[0]


def test_create_package_revision_aws_credentials(monkeypatch):
    """Verify credential context manager usage."""
    backend = _make_backend(monkeypatch)

    creds_entered = [False]
    creds_exited = [False]

    @contextmanager
    def _track_creds():
        creds_entered[0] = True
        yield
        creds_exited[0] = True

    backend._with_aws_credentials = _track_creds

    class FakePackage:
        def __init__(self):
            self.meta = {}

        def set(self, logical_key, s3_uri):
            pass

        def set_meta(self, meta):
            pass

        def push(self, *args, **kwargs):
            return "creds-hash"

    fake_quilt3 = SimpleNamespace(Package=FakePackage)
    monkeypatch.setitem(sys.modules, "quilt3", fake_quilt3)

    result = backend.create_package_revision("user/pkg", ["s3://bucket/file.txt"], registry="s3://bucket")

    assert creds_entered[0] is True
    assert creds_exited[0] is True
    assert result.success is True


# ---------------------------------------------------------------------
# Package Updates
# ---------------------------------------------------------------------


def test_update_package_revision_adds_files(monkeypatch):
    """Add files to existing package."""
    backend = _make_backend(monkeypatch)

    @contextmanager
    def _noop_creds():
        yield

    backend._with_aws_credentials = _noop_creds

    class FakePackage:
        def __init__(self):
            self.meta = {"existing": "metadata"}
            self.files = {}

        def set(self, logical_key, s3_uri):
            self.files[logical_key] = s3_uri

        def set_meta(self, meta):
            self.meta = meta

        def push(self, *args, **kwargs):
            return "update-hash-789"

        @classmethod
        def browse(cls, *args, **kwargs):
            return cls()

    fake_quilt3 = SimpleNamespace(Package=FakePackage)
    monkeypatch.setitem(sys.modules, "quilt3", fake_quilt3)

    result = backend.update_package_revision(
        "user/existing-pkg",
        ["s3://bucket/new-file.txt"],
        registry="s3://bucket",
    )

    assert result.success is True
    assert result.top_hash == "update-hash-789"
    assert result.file_count == 1


def test_update_package_revision_updates_metadata(monkeypatch):
    """Merge metadata."""
    backend = _make_backend(monkeypatch)

    @contextmanager
    def _noop_creds():
        yield

    backend._with_aws_credentials = _noop_creds

    class FakePackage:
        def __init__(self):
            self.meta = {"key1": "original", "key2": "preserve"}
            self.files = {}
            self.final_meta = None

        def set(self, logical_key, s3_uri):
            self.files[logical_key] = s3_uri

        def set_meta(self, meta):
            self.final_meta = meta

        def push(self, *args, **kwargs):
            return "merged-hash"

        @classmethod
        def browse(cls, *args, **kwargs):
            return cls()

    fake_pkg = FakePackage()
    fake_quilt3 = SimpleNamespace(Package=type(fake_pkg))
    fake_quilt3.Package.browse = lambda *args, **kwargs: fake_pkg
    monkeypatch.setitem(sys.modules, "quilt3", fake_quilt3)

    new_metadata = {"key1": "updated", "key3": "new"}
    result = backend.update_package_revision(
        "user/pkg",
        ["s3://bucket/file.txt"],
        registry="s3://bucket",
        metadata=new_metadata,
    )

    assert result.success is True
    # Metadata should be merged (original + updates)
    assert fake_pkg.final_meta["key1"] == "updated"
    assert fake_pkg.final_meta["key2"] == "preserve"
    assert fake_pkg.final_meta["key3"] == "new"


def test_update_package_revision_preserves_existing(monkeypatch):
    """Don't lose existing files."""
    backend = _make_backend(monkeypatch)

    @contextmanager
    def _noop_creds():
        yield

    backend._with_aws_credentials = _noop_creds

    class FakePackage:
        def __init__(self):
            self.meta = {}
            self.files = {"existing.txt": "s3://bucket/existing.txt"}

        def set(self, logical_key, s3_uri):
            self.files[logical_key] = s3_uri

        def set_meta(self, meta):
            self.meta = meta

        def push(self, *args, **kwargs):
            return "preserve-hash"

        @classmethod
        def browse(cls, *args, **kwargs):
            return cls()

    fake_pkg = FakePackage()
    fake_quilt3 = SimpleNamespace(Package=type(fake_pkg))
    fake_quilt3.Package.browse = lambda *args, **kwargs: fake_pkg
    monkeypatch.setitem(sys.modules, "quilt3", fake_quilt3)

    result = backend.update_package_revision(
        "user/pkg",
        ["s3://bucket/new.txt"],
        registry="s3://bucket",
    )

    assert result.success is True
    # Both existing and new files should be present
    assert "existing.txt" in fake_pkg.files
    assert "new.txt" in fake_pkg.files
