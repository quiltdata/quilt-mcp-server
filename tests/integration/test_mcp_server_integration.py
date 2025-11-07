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
    # Auth tool returns a Pydantic model or dict
    result = auth_status()
    assert hasattr(result, 'success') or isinstance(result, dict)

    # Basic listing call should return Pydantic model (mocked in unit runs)
    try:
        # Uses default registry
        pkgs = packages_list(registry="s3://quilt-ernest-staging")
        assert hasattr(pkgs, 'success') or hasattr(pkgs, 'error')
    except Exception as e:
        if "AccessDenied" in str(e) or "S3NoValidClientError" in str(e) or "Authentication failed" in str(e):
            # Expected in environments without proper AWS permissions
            pass
        else:
            raise

    # Browse nonexistent package should return error response, not raise
    browse = package_browse(package_name="nonexistent/package")
    assert hasattr(browse, 'success') or hasattr(browse, 'error')

    # Searching within nonexistent package should also return a dict response
    search = search_catalog(query="README.md", scope="package", target="nonexistent/package")
    assert isinstance(search, dict)
