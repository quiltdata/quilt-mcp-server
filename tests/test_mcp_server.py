#!/usr/bin/env python3
"""
Smoke tests for Quilt MCP server tool functions (no external Quilt module).
"""

from quilt_mcp.tools.auth import auth_status
from quilt_mcp.tools.packages import packages_list, package_browse, package_contents_search


def test_quilt_tools():
    # Auth tool returns a structured dict
    result = auth_status()
    assert isinstance(result, dict)

    # Basic listing call should return dict (mocked in unit runs)
    pkgs = packages_list()
    assert isinstance(pkgs, dict)

    # Browse nonexistent package should return error dict, not raise
    browse = package_browse("nonexistent/package")
    assert isinstance(browse, dict)

    # Searching within nonexistent package should also return a dict response
    search = package_contents_search("nonexistent/package", "README.md")
    assert isinstance(search, dict)
