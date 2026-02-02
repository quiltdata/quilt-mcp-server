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
    backend.execute_graphql_query = lambda *args, **kwargs: {"data": {"packages": {"total": 0, "page": []}}}

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


def test_create_package_revision_basic(monkeypatch):
    """Create package with files using GraphQL mutation."""
    backend = _make_backend(monkeypatch)

    # Mock successful packageConstruct response
    def mock_graphql(query, variables=None):
        return {
            "data": {
                "packageConstruct": {
                    "__typename": "PackagePushSuccess",
                    "package": {"name": "user/test-pkg"},
                    "revision": {"hash": "test-hash-123"},
                }
            }
        }

    backend.execute_graphql_query = mock_graphql

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
    """Include package metadata using GraphQL mutation."""
    backend = _make_backend(monkeypatch)

    # Track the variables passed to GraphQL
    captured_variables = {}

    def mock_graphql(query, variables=None):
        captured_variables.update(variables or {})
        return {
            "data": {
                "packageConstruct": {
                    "__typename": "PackagePushSuccess",
                    "package": {"name": "user/metadata-pkg"},
                    "revision": {"hash": "meta-hash-456"},
                }
            }
        }

    backend.execute_graphql_query = mock_graphql

    metadata = {"description": "Test package", "version": "1.0"}
    result = backend.create_package_revision(
        "user/metadata-pkg",
        ["s3://bucket/data.txt"],
        metadata=metadata,
        registry="s3://bucket",
    )

    assert result.success is True
    assert captured_variables["params"]["userMeta"] == metadata


def test_create_package_revision_copy_mode(monkeypatch):
    """Test copy=True promotes the package after creation."""
    backend = _make_backend(monkeypatch)

    call_count = [0]

    def mock_graphql(query, variables=None):
        call_count[0] += 1
        if "packageConstruct" in query:
            # packageConstruct mutation
            return {
                "data": {
                    "packageConstruct": {
                        "__typename": "PackagePushSuccess",
                        "package": {"name": "user/copy-pkg"},
                        "revision": {"hash": "original-hash"},
                    }
                }
            }
        elif "packagePromote" in query:
            # packagePromote mutation
            return {
                "data": {
                    "packagePromote": {
                        "__typename": "PackagePushSuccess",
                        "revision": {"hash": "promoted-hash"},
                    }
                }
            }

    backend.execute_graphql_query = mock_graphql

    # Test copy=False (symlink mode) - should not promote
    result = backend.create_package_revision(
        "user/symlink-pkg", ["s3://bucket/file.txt"], registry="s3://bucket", copy=False
    )
    assert result.success is True
    assert call_count[0] == 1  # Only packageConstruct called

    # Test copy=True - should promote after construct
    call_count[0] = 0
    result = backend.create_package_revision(
        "user/copy-pkg", ["s3://bucket/file.txt"], registry="s3://bucket", copy=True
    )
    assert result.success is True
    assert result.top_hash == "promoted-hash"  # Should return promoted hash
    assert call_count[0] == 2  # Both packageConstruct and packagePromote called


def test_create_package_revision_invalid_input(monkeypatch):
    """Handle GraphQL InvalidInputFailure response."""
    backend = _make_backend(monkeypatch)

    def mock_graphql_error(query, variables=None):
        return {
            "data": {
                "packageConstruct": {
                    "__typename": "PackagePushInvalidInputFailure",
                    "errors": [{"path": "entries.0.physicalKey", "message": "S3 object does not exist"}],
                }
            }
        }

    backend.execute_graphql_query = mock_graphql_error

    with pytest.raises(ValidationError, match="Invalid package input"):
        backend.create_package_revision(
            "user/pkg",
            ["s3://bucket/nonexistent-file.txt"],  # Valid URI format, but GraphQL will reject it
            registry="s3://bucket",
        )


def test_create_package_revision_compute_failure(monkeypatch):
    """Handle GraphQL ComputeFailure response."""
    backend = _make_backend(monkeypatch)

    def mock_graphql_error(query, variables=None):
        return {
            "data": {
                "packageConstruct": {"__typename": "PackagePushComputeFailure", "message": "Lambda execution timeout"}
            }
        }

    backend.execute_graphql_query = mock_graphql_error

    with pytest.raises(BackendError, match="Package creation compute failure"):
        backend.create_package_revision("user/pkg", ["s3://bucket/file.txt"], registry="s3://bucket")


def test_create_package_revision_promote_failure(monkeypatch):
    """Handle promotion failure when copy=True."""
    backend = _make_backend(monkeypatch)

    call_count = [0]

    def mock_graphql(query, variables=None):
        call_count[0] += 1
        if "packageConstruct" in query:
            return {
                "data": {
                    "packageConstruct": {
                        "__typename": "PackagePushSuccess",
                        "package": {"name": "user/pkg"},
                        "revision": {"hash": "original-hash"},
                    }
                }
            }
        elif "packagePromote" in query:
            return {
                "data": {
                    "packagePromote": {
                        "__typename": "OperationError",
                        "message": "S3 copy operation failed",
                    }
                }
            }

    backend.execute_graphql_query = mock_graphql

    with pytest.raises(BackendError, match="Package promotion error"):
        backend.create_package_revision("user/pkg", ["s3://bucket/file.txt"], registry="s3://bucket", copy=True)


# ---------------------------------------------------------------------
# Package Updates
# ---------------------------------------------------------------------


def test_update_package_revision_adds_files(monkeypatch):
    """Add files to existing package using GraphQL."""
    backend = _make_backend(monkeypatch)

    call_count = [0]

    def mock_graphql(query, variables=None):
        call_count[0] += 1
        if "GetPackageForUpdate" in query:
            # Query existing package
            return {
                "data": {
                    "package": {
                        "revision": {
                            "hash": "existing-hash",
                            "userMeta": {"existing": "metadata"},
                            "contentsFlatMap": {
                                "old-file.txt": {
                                    "physicalKey": "s3://bucket/old-file.txt",
                                    "size": 100,
                                    "hash": "old-hash",
                                }
                            },
                        }
                    }
                }
            }
        else:
            # PackageConstruct mutation
            return {
                "data": {
                    "packageConstruct": {
                        "__typename": "PackagePushSuccess",
                        "package": {"name": "user/existing-pkg"},
                        "revision": {"hash": "update-hash-789"},
                    }
                }
            }

    backend.execute_graphql_query = mock_graphql

    result = backend.update_package_revision(
        "user/existing-pkg",
        ["s3://bucket/new-file.txt"],
        registry="s3://bucket",
    )

    assert result.success is True
    assert result.top_hash == "update-hash-789"
    assert result.file_count == 1


def test_update_package_revision_updates_metadata(monkeypatch):
    """Merge metadata using GraphQL."""
    backend = _make_backend(monkeypatch)

    captured_variables = {}

    def mock_graphql(query, variables=None):
        if "GetPackageForUpdate" in query:
            # Query existing package
            return {
                "data": {
                    "package": {
                        "revision": {
                            "hash": "existing-hash",
                            "userMeta": {"key1": "original", "key2": "preserve"},
                            "contentsFlatMap": {},
                        }
                    }
                }
            }
        else:
            # PackageConstruct mutation
            captured_variables.update(variables or {})
            return {
                "data": {
                    "packageConstruct": {
                        "__typename": "PackagePushSuccess",
                        "package": {"name": "user/pkg"},
                        "revision": {"hash": "merged-hash"},
                    }
                }
            }

    backend.execute_graphql_query = mock_graphql

    new_metadata = {"key1": "updated", "key3": "new"}
    result = backend.update_package_revision(
        "user/pkg",
        ["s3://bucket/file.txt"],
        registry="s3://bucket",
        metadata=new_metadata,
    )

    assert result.success is True
    # Metadata should be merged (original + updates)
    merged_meta = captured_variables["params"]["userMeta"]
    assert merged_meta["key1"] == "updated"
    assert merged_meta["key2"] == "preserve"
    assert merged_meta["key3"] == "new"


def test_update_package_revision_preserves_existing(monkeypatch):
    """Don't lose existing files using GraphQL."""
    backend = _make_backend(monkeypatch)

    captured_variables = {}

    def mock_graphql(query, variables=None):
        if "GetPackageForUpdate" in query:
            # Query existing package with existing file
            return {
                "data": {
                    "package": {
                        "revision": {
                            "hash": "existing-hash",
                            "userMeta": {},
                            "contentsFlatMap": {
                                "existing.txt": {
                                    "physicalKey": "s3://bucket/existing.txt",
                                    "size": 100,
                                    "hash": "existing-hash",
                                }
                            },
                        }
                    }
                }
            }
        else:
            # PackageConstruct mutation
            captured_variables.update(variables or {})
            return {
                "data": {
                    "packageConstruct": {
                        "__typename": "PackagePushSuccess",
                        "package": {"name": "user/pkg"},
                        "revision": {"hash": "preserve-hash"},
                    }
                }
            }

    backend.execute_graphql_query = mock_graphql

    result = backend.update_package_revision(
        "user/pkg",
        ["s3://bucket/new.txt"],
        registry="s3://bucket",
    )

    assert result.success is True
    # Both existing and new files should be present in entries
    entries = captured_variables["src"]["entries"]
    logical_keys = [e["logicalKey"] for e in entries]
    assert "existing.txt" in logical_keys
    assert "new.txt" in logical_keys


def test_update_package_revision_copy_mode(monkeypatch):
    """Test that copy != 'none' promotes the package after update."""
    backend = _make_backend(monkeypatch)

    call_count = [0]

    def mock_graphql(query, variables=None):
        call_count[0] += 1
        if "GetPackageForUpdate" in query:
            # Query existing package
            return {
                "data": {
                    "package": {
                        "revision": {
                            "hash": "existing-hash",
                            "userMeta": {},
                            "contentsFlatMap": {
                                "old.txt": {
                                    "physicalKey": "s3://bucket/old.txt",
                                    "size": 100,
                                    "hash": "old-hash",
                                }
                            },
                        }
                    }
                }
            }
        elif "packageConstruct" in query:
            # PackageConstruct mutation
            return {
                "data": {
                    "packageConstruct": {
                        "__typename": "PackagePushSuccess",
                        "package": {"name": "user/pkg"},
                        "revision": {"hash": "updated-hash"},
                    }
                }
            }
        elif "packagePromote" in query:
            # PackagePromote mutation
            return {
                "data": {
                    "packagePromote": {
                        "__typename": "PackagePushSuccess",
                        "revision": {"hash": "promoted-updated-hash"},
                    }
                }
            }

    backend.execute_graphql_query = mock_graphql

    # Test copy='all' - should promote after update
    result = backend.update_package_revision("user/pkg", ["s3://bucket/new.txt"], registry="s3://bucket", copy="all")
    assert result.success is True
    assert result.top_hash == "promoted-updated-hash"
    assert call_count[0] == 3  # Query + Construct + Promote

    # Test copy='new' - should also promote
    call_count[0] = 0
    result = backend.update_package_revision("user/pkg", ["s3://bucket/newer.txt"], registry="s3://bucket", copy="new")
    assert result.success is True
    assert result.top_hash == "promoted-updated-hash"
    assert call_count[0] == 3  # Query + Construct + Promote
