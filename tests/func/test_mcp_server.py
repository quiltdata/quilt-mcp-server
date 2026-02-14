#!/usr/bin/env python3
"""
Smoke tests for Quilt MCP server tool functions (no external Quilt module).
"""

import pytest
from unittest.mock import patch, Mock
from quilt_mcp.services.auth_metadata import auth_status
from quilt_mcp.tools.packages import (
    packages_list,
    package_browse,
)
from quilt_mcp.tools.search import search_catalog


@patch("quilt_mcp.tools.packages.QuiltOpsFactory.create")
@patch("quilt_mcp.search.backends.elasticsearch.QuiltOpsFactory.create")
@patch("quilt_mcp.ops.factory.quilt3")
@patch("quilt3.search_util.search_api", return_value={"hits": {"hits": []}})
@patch("quilt3.Package.browse")
def test_quilt_tools(mock_browse, mock_search, mock_quilt3, mock_search_ops_create, mock_packages_ops_create):
    # Setup session mock
    mock_quilt3.session.get_session_info.return_value = {"registry": "s3://quilt-ernest-staging"}
    mock_quilt_ops = Mock()
    mock_auth_status = Mock()
    mock_auth_status.registry_url = "s3://quilt-ernest-staging"
    mock_quilt_ops.get_auth_status.return_value = mock_auth_status
    mock_quilt_ops.browse_content.return_value = [
        Mock(path="README.md", size=123, type="file", download_url=None, modified_date=None)
    ]
    # package_browse now uses QuiltOps public metadata API
    mock_quilt_ops.get_package_metadata.return_value = {}
    mock_search_ops_create.return_value = mock_quilt_ops
    mock_packages_ops_create.return_value = mock_quilt_ops

    # Mock Package.browse to raise an error for nonexistent packages
    mock_browse.side_effect = Exception("Package not found")

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
    browse = package_browse(package_name="nonexistent/package", registry="s3://test-bucket")
    assert hasattr(browse, 'success') or hasattr(browse, 'error')

    # Searching within nonexistent package should also return a dict response
    search = search_catalog(query="README.md", scope="package", bucket="nonexistent/package")
    assert isinstance(search, dict)

    # Test default search (backend is automatically selected)
    search_default = search_catalog(query="test")
    assert isinstance(search_default, dict)
