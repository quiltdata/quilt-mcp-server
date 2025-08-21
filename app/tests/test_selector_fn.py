import pytest
from unittest.mock import patch

from quilt_mcp.tools.package_ops import package_create
from quilt_mcp.tools.s3_package import package_create_from_s3


def _make_push_assertions(expected_behaviors):
    """
    Build a replacement for quilt3.Package.push that asserts selector_fn decisions.

    expected_behaviors: list of tuples (logical_key, expect_true)
    """

    def _push(self, name, registry=None, message=None, selector_fn=None, **kwargs):  # type: ignore[no-redef]
        assert callable(selector_fn)
        for logical_key, expect in expected_behaviors:
            entry = self[logical_key]
            assert bool(selector_fn(logical_key, entry)) is expect
        return "test_top_hash"

    return _push


@patch("quilt3.Package.push")
def test_package_ops_copy_mode_none(mock_push):
    # Configure mock to assert selector always False
    mock_push.side_effect = _make_push_assertions([
        ("file1.csv", False),
        ("file2.json", False),
    ])

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

    assert result.get("status") == "success"
    assert result.get("top_hash") == "test_top_hash"


@patch("quilt3.Package.push")
def test_package_ops_copy_mode_same_bucket(mock_push):
    # One file in target bucket should be True, other should be False
    mock_push.side_effect = _make_push_assertions([
        ("file1.csv", True),   # s3://target-bucket/...
        ("file2.json", False), # s3://other-bucket/...
    ])

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

    assert result.get("status") == "success"
    assert result.get("top_hash") == "test_top_hash"


@patch("quilt3.Package.push")
@patch("quilt_mcp.tools.s3_package._discover_s3_objects")
@patch("quilt_mcp.tools.s3_package._validate_bucket_access")
@patch("quilt_mcp.tools.s3_package.bucket_access_check")
def test_s3_package_copy_mode_none(mock_access_check, mock_validate, mock_discover, mock_push):
    # Simulate write access to target registry
    mock_access_check.return_value = {"success": True, "access_summary": {"can_write": True}}
    mock_validate.return_value = None
    mock_discover.return_value = [
        {"Key": "data/file1.csv", "Size": 100},
        {"Key": "data/file2.csv", "Size": 200},
    ]

    # In enhanced creator, logical keys will be folder/name
    mock_push.side_effect = _make_push_assertions([
        ("data/processed/file1.csv", False),
        ("data/processed/file2.csv", False),
    ])

    result = package_create_from_s3(
        source_bucket="source-bucket",
        package_name="team/pkg",
        target_registry="s3://target-bucket",
        copy_mode="none",
        auto_organize=True,
        description="test",
    )

    assert result.get("success") is True
    assert result.get("package_hash") == "test_top_hash"

