#!/usr/bin/env python3
"""
Smoke tests for Quilt MCP server tool functions (no external Quilt module).
"""

import pytest
from quilt_mcp.services.auth_metadata import auth_status
from quilt_mcp.tools.packages import (
    packages_list,
    package_browse,
)
from quilt_mcp.tools.search import search_catalog


@pytest.mark.integration
def test_quilt_tools():
    # Auth tool returns a structured dict
    result = auth_status()
    assert isinstance(result, dict)

    # Basic listing call should return dict (mocked in unit runs)
    try:
        pkgs = packages_list()
        assert isinstance(pkgs, dict)
    except Exception as e:
        if "AccessDenied" in str(e) or "S3NoValidClientError" in str(e) or "Authentication failed" in str(e):
            # Expected in environments without proper AWS permissions
            pkgs = {"packages": [], "error": "Access denied"}
        else:
            raise

    # Browse nonexistent package should return error dict, not raise
    browse = package_browse("nonexistent/package")
    assert isinstance(browse, dict)

    # Searching within nonexistent package should also return a dict response
    search = search_catalog(query="README.md", scope="package", target="nonexistent/package")
    assert isinstance(search, dict)
