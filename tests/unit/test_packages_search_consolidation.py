"""Behavior tests for package search consolidation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


@patch("quilt_mcp.tools.packages.catalog_search")
def test_packages_search_delegates_to_catalog_search(mock_catalog_search: MagicMock) -> None:
    """packages_search should proxy to catalog_search with catalog scope."""
    import quilt_mcp.tools.packages as package_tools

    mock_catalog_search.return_value = {"success": True}

    result = package_tools.packages_search(
        "genomics data",
        registry="s3://example",
        limit=25,
        from_=5,
    )

    mock_catalog_search.assert_called_once_with(
        query="genomics data",
        scope="catalog",
        target="s3://example",
        limit=25,
        filters={"registry": "s3://example", "offset": 5},
    )
    assert result == mock_catalog_search.return_value


@patch("quilt_mcp.tools.packages.QuiltService")
@patch("quilt_mcp.tools.packages.generate_signed_url", return_value="signed")
def test_package_contents_search_legacy_path(
    mock_signed_url: MagicMock,
    mock_quilt_service: MagicMock,
) -> None:
    """Legacy within-package search continues to work until catalog delegation lands."""
    from quilt_mcp.tools import packages

    mock_pkg = MagicMock()
    mock_pkg.keys.return_value = ["data/file.csv", "other.txt"]
    mock_entry = MagicMock()
    mock_entry.physical_key = "s3://bucket/data/file.csv"
    mock_entry.size = 123
    mock_entry.hash = "hash"
    mock_pkg.__getitem__.return_value = mock_entry
    mock_quilt_service.return_value.browse_package.return_value = mock_pkg

    result = packages.package_contents_search(
        package_name="team/pkg",
        query="file",
        registry="s3://example",
        include_signed_urls=True,
    )

    mock_quilt_service.return_value.browse_package.assert_called_once_with("team/pkg", registry="s3://example")
    assert result["count"] == 1
    assert result["matches"][0]["logical_key"] == "data/file.csv"
    assert result["matches"][0]["download_url"] == "signed"
