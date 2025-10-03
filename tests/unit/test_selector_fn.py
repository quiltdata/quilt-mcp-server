import pytest
from unittest.mock import patch, Mock, MagicMock

from quilt_mcp.runtime import request_context
from quilt_mcp.tools.package_ops import package_create
from quilt_mcp.tools.s3_package import package_create_from_s3


class MockPackage:
    """Mock quilt3.Package that can handle set operations and push calls."""

    def __init__(self):
        self._entries = {}
        self._metadata = {}

    def set(self, logical_path, source):
        """Mock set operation."""
        self._entries[logical_path] = MockEntry(source)
        return None

    def set_meta(self, metadata):
        """Mock set_meta operation."""
        self._metadata.update(metadata)
        return None

    def __getitem__(self, logical_path):
        """Mock getitem to return entries."""
        if logical_path not in self._entries:
            raise KeyError(logical_path)
        return self._entries[logical_path]

    def __contains__(self, logical_path):
        """Mock contains check."""
        return logical_path in self._entries

    def push(self, name, registry=None, message=None, selector_fn=None, **kwargs):
        """Mock push operation that tests selector_fn."""
        if selector_fn:
            for logical_path, entry in self._entries.items():
                # Test the selector function and use the result
                # This simulates how quilt3 actually uses the selector_fn return value
                should_include = selector_fn(logical_path, entry)
                # In real quilt3, this boolean result is used to determine file inclusion
                # For our mock, we just verify it's a boolean
                if not isinstance(should_include, bool):
                    raise ValueError(f"selector_fn must return boolean, got {type(should_include)}")
        return "test_top_hash"


class MockEntry:
    """Mock package entry with physical_key attribute."""

    def __init__(self, source):
        self.physical_key = source


def _with_token():
    return request_context("token", metadata={"session": "selector-tests"})


@patch("quilt3.Package")
@patch(
    "quilt_mcp.clients.catalog.catalog_package_create",
    return_value={"success": True, "top_hash": "test_top_hash", "entries_added": 2},
)
def test_package_ops_copy_mode_none(mock_catalog_create, mock_package_class):
    # Configure mock to return our MockPackage
    mock_package_class.return_value = MockPackage()

    with _with_token():
        result = package_create(
            package_name="team/pkg",
            s3_uris=[
                "s3://bucket-a/dir/file1.csv",
                "s3://bucket-b/file2.json",
            ],
            registry="s3://target-bucket",
            copy_mode="none",
            flatten=True,
        )

    # The function should succeed and return status
    assert result.get("status") == "success"
    assert result.get("top_hash") == "test_top_hash"


@patch("quilt3.Package")
@patch(
    "quilt_mcp.clients.catalog.catalog_package_create",
    return_value={"success": True, "top_hash": "test_top_hash", "entries_added": 2},
)
def test_package_ops_copy_mode_same_bucket(mock_catalog_create, mock_package_class):
    # Configure mock to return our MockPackage
    mock_package_class.return_value = MockPackage()

    with _with_token():
        result = package_create(
            package_name="team/pkg",
            s3_uris=[
                "s3://target-bucket/path/file1.csv",
                "s3://other-bucket/file2.json",
            ],
            registry="s3://target-bucket",
            copy_mode="same_bucket",
            flatten=True,
        )

    # The function should succeed and return status
    assert result.get("status") == "success"
    assert result.get("top_hash") == "test_top_hash"
