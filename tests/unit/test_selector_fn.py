"""Behavior tests for canonical package creation helper delegation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quilt_mcp.tools.package_management import package_create


@patch("quilt_mcp.tools.package_management._base_package_create")
def test_package_create_passes_copy_mode_and_files(mock_base_create: MagicMock) -> None:
    """Ensure canonical package creation delegates to the base helper with copy mode."""
    mock_base_create.return_value = {"status": "success", "top_hash": "hash"}

    result = package_create(
        name="team/pkg",
        files=["s3://bucket-a/file1.csv", "s3://bucket-b/file2.json"],
        registry="s3://target-bucket",
        copy_mode="same_bucket",
    )

    assert result["status"] == "success"
    mock_base_create.assert_called_once()
    kwargs = mock_base_create.call_args.kwargs
    assert kwargs["package_name"] == "team/pkg"
    assert kwargs["s3_uris"] == ["s3://bucket-a/file1.csv", "s3://bucket-b/file2.json"]
    assert kwargs["registry"] == "s3://target-bucket"
    assert kwargs["copy_mode"] == "same_bucket"


def test_package_create_dry_run_returns_preview() -> None:
    """Dry-run requests should return preview metadata without invoking base helper."""
    result = package_create(
        name="team/pkg",
        files=["s3://bucket/file.csv"],
        dry_run=True,
        metadata_template="analytics",
    )

    assert result["success"] is True
    assert result["action"] == "preview"
    assert result["metadata_template"] == "analytics"
    assert result["files_count"] == 1


def test_package_create_validates_input_metadata() -> None:
    """Invalid metadata types should produce actionable error responses."""
    result = package_create(
        name="team/pkg",
        files=["s3://bucket/file.csv"],
        metadata=123,  # Invalid type
    )

    assert result["success"] is False
    assert "Invalid metadata type" in result["error"]
    assert result["provided_type"] == "int"
