#!/usr/bin/env python3
"""
Smoke tests for Quilt MCP server tool functions (no external Quilt module).
"""

import pytest
from quilt_mcp.tools.catalog import catalog_status
from quilt_mcp.tools.packages import (
    package_browse,
    package_contents_search,
)
from quilt_mcp.tools.search import catalog_search


@pytest.mark.aws
def test_quilt_tools():
    # Catalog status tool returns a structured dict
    result = catalog_status()
    assert isinstance(result, dict)

    # Basic catalog search should return dict (replaces packages_list)
    try:
        pkgs = catalog_search(query="*", scope="catalog", limit=10)
        assert isinstance(pkgs, dict)
    except Exception as e:
        if "AccessDenied" in str(e) or "S3NoValidClientError" in str(e):
            # Expected in environments without proper AWS permissions
            pkgs = {"results": [], "error": "Access denied"}
        else:
            raise

    # Browse nonexistent package should return error dict, not raise
    browse = package_browse("nonexistent/package")
    assert isinstance(browse, dict)

    # Searching within nonexistent package should also return a dict response
    search = package_contents_search("nonexistent/package", "README.md")
    assert isinstance(search, dict)
