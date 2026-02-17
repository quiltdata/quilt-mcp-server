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

from tests.unit.backends.test_platform_backend_packages_part1 import _make_backend


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
        if "query GetPackage(" in query:
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
        if "query GetPackage(" in query:
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
        if "query GetPackage(" in query:
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
        if "query GetPackage(" in query:
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

    # Test copy='new' - base QuiltOps behavior treats it as non-copy
    call_count[0] = 0
    result = backend.update_package_revision("user/pkg", ["s3://bucket/newer.txt"], registry="s3://bucket", copy="new")
    assert result.success is True
    assert result.top_hash == "updated-hash"
    assert call_count[0] == 2  # Query + Construct
