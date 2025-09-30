"""Tests for health check endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from quilt_mcp.health import health_check_handler


class TestHealthCheckEndpoint:
    """Test health check endpoint functionality."""

    @pytest.mark.asyncio
    async def test_basic_health_check_returns_ok_status(self):
        """Test that basic health check returns OK status."""
        # Arrange
        mock_request = MagicMock(spec=Request)

        # Act
        response = await health_check_handler(mock_request)

        # Assert
        assert isinstance(response, JSONResponse)
        assert response.status_code == 200

        # Parse response body
        body = json.loads(response.body.decode())
        assert body["status"] == "ok"
        assert "timestamp" in body

        # Verify timestamp format
        timestamp = datetime.fromisoformat(body["timestamp"])
        assert timestamp.tzinfo is not None  # Should have timezone info

    @pytest.mark.asyncio
    async def test_health_check_includes_server_info(self):
        """Test that health check includes basic server information."""
        # Arrange
        mock_request = MagicMock(spec=Request)

        # Act
        response = await health_check_handler(mock_request)

        # Assert
        body = json.loads(response.body.decode())
        assert "server" in body
        assert body["server"]["name"] == "quilt-mcp-server"
        assert "version" in body["server"]
        assert "transport" in body["server"]

    @pytest.mark.asyncio
    async def test_health_check_handles_errors_gracefully(self):
        """Test that health check handles internal errors gracefully."""
        # Arrange
        mock_request = MagicMock(spec=Request)

        # Mock an internal error during health check
        with patch("quilt_mcp.health.get_server_info", side_effect=Exception("Internal error")):
            # Act
            response = await health_check_handler(mock_request)

            # Assert
            assert response.status_code == 503
            body = json.loads(response.body.decode())
            assert body["status"] == "unhealthy"
            assert "error" in body
            assert "timestamp" in body

    @pytest.mark.asyncio
    async def test_health_check_response_headers(self):
        """Test that health check response includes proper headers."""
        # Arrange
        mock_request = MagicMock(spec=Request)

        # Act
        response = await health_check_handler(mock_request)

        # Assert
        assert response.headers["Content-Type"] == "application/json"
        assert "Cache-Control" in response.headers
        # Health checks should not be cached
        assert "no-cache" in response.headers["Cache-Control"]
