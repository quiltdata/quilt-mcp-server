import pytest
from unittest.mock import patch, Mock, MagicMock

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
                # Test the selector function
                selector_fn(logical_path, entry)
        return "test_top_hash"


class MockEntry:
    """Mock package entry with physical_key attribute."""
    
    def __init__(self, source):
        self.physical_key = source


@patch("quilt3.Package")
def test_package_ops_copy_mode_none(mock_package_class):
    # Configure mock to return our MockPackage
    mock_package_class.return_value = MockPackage()
    
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
def test_package_ops_copy_mode_same_bucket(mock_package_class):
    # Configure mock to return our MockPackage
    mock_package_class.return_value = MockPackage()
    
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


@patch("quilt3.Package")
@patch("quilt_mcp.tools.s3_package._discover_s3_objects")
@patch("quilt_mcp.tools.s3_package._validate_bucket_access")
@patch("quilt_mcp.tools.s3_package.bucket_access_check")
def test_s3_package_copy_mode_none(mock_access_check, mock_validate, mock_discover, mock_package_class):
    # Configure mock to return our MockPackage
    mock_package_class.return_value = MockPackage()
    
    # Simulate write access to target registry
    mock_access_check.return_value = {"success": True, "access_summary": {"can_write": True}}
    mock_validate.return_value = None
    mock_discover.return_value = [
        {"Key": "data/file1.csv", "Size": 100},
        {"Key": "data/file2.csv", "Size": 200},
    ]

    result = package_create_from_s3(
        source_bucket="source-bucket",
        package_name="team/pkg",
        target_registry="s3://target-bucket",
        copy_mode="none",
        auto_organize=True,
        description="test",
    )

    # The function should succeed and return success
    assert result.get("success") is True
    assert result.get("package_hash") == "test_top_hash"

