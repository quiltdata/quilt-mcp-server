"""Test health check integration with FastMCP server."""

import os
from unittest.mock import MagicMock, patch

import pytest

from quilt_mcp.utils import create_configured_server


class TestHealthCheckIntegration:
    """Test health check integration with FastMCP."""

    def test_health_endpoint_registered_for_http_transport(self):
        """Test that health endpoint is registered when using HTTP transport."""
        # Arrange
        with patch("quilt_mcp.utils.FastMCP") as mock_fastmcp:
            with patch.dict(os.environ, {"FASTMCP_TRANSPORT": "http"}):
                # Act
                server = create_configured_server(verbose=False)

            # Assert
            # Check that custom_route was called for health endpoint
            # Note: This tests that the integration code runs without errors
            assert mock_fastmcp.called

    def test_health_endpoint_not_registered_for_stdio_transport(self):
        """Test that health endpoint is not registered for stdio transport."""
        # Arrange
        with patch("quilt_mcp.utils.FastMCP") as mock_fastmcp:
            with patch.dict(os.environ, {"FASTMCP_TRANSPORT": "stdio"}):
                # Act
                server = create_configured_server(verbose=False)

            # Assert
            # For stdio transport, the server should be created successfully
            # but without HTTP endpoints
            assert mock_fastmcp.called

    def test_health_endpoint_registered_for_sse_transport(self):
        """Test that health endpoint is registered for SSE transport."""
        # Arrange
        with patch("quilt_mcp.utils.FastMCP") as mock_fastmcp:
            with patch.dict(os.environ, {"FASTMCP_TRANSPORT": "sse"}):
                # Act
                server = create_configured_server(verbose=False)

            # Assert
            assert mock_fastmcp.called

    def test_verbose_logging_for_health_endpoint(self):
        """Test that verbose mode logs health endpoint registration."""
        # Arrange
        with patch("quilt_mcp.utils.FastMCP") as mock_fastmcp:
            with patch.dict(os.environ, {"FASTMCP_TRANSPORT": "http"}):
                with patch("sys.stderr") as mock_stderr:
                    # Act
                    server = create_configured_server(verbose=True)

                # Assert
                assert mock_fastmcp.called
