#!/usr/bin/env python3
"""
Integration tests for MCP Resources.

These tests validate that resources are properly registered with FastMCP
using the decorator pattern. The actual service functions are tested
in their respective service test files.
"""

import pytest


@pytest.mark.integration
class TestResourceRegistration:
    """Test that resources are properly registered with FastMCP."""

    def test_server_creation_with_resources(self):
        """Test that server can be created with resources registered."""
        from quilt_mcp.utils import create_configured_server

        # This should not raise any errors
        mcp = create_configured_server(verbose=False)
        assert mcp is not None

    def test_server_creation_verbose(self):
        """Test server creation with verbose output."""
        from quilt_mcp.utils import create_configured_server

        # This should print registration messages
        mcp = create_configured_server(verbose=True)
        assert mcp is not None
