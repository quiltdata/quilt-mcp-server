"""
Unit tests for QuiltRoleMiddleware functionality.

These tests verify that the middleware correctly processes headers and triggers
role assumption without making real AWS calls.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from fastmcp import FastMCP
from starlette.testclient import TestClient

from quilt_mcp.utils import build_http_app


class TestQuiltRoleMiddleware:
    """Test QuiltRoleMiddleware functionality."""

    def setup_method(self):
        """Set up test environment."""
        # Clear any existing environment variables
        if "QUILT_USER_ROLE_ARN" in os.environ:
            del os.environ["QUILT_USER_ROLE_ARN"]
        if "QUILT_USER_ID" in os.environ:
            del os.environ["QUILT_USER_ID"]

    def teardown_method(self):
        """Clean up after tests."""
        # Clear environment variables
        if "QUILT_USER_ROLE_ARN" in os.environ:
            del os.environ["QUILT_USER_ROLE_ARN"]
        if "QUILT_USER_ID" in os.environ:
            del os.environ["QUILT_USER_ID"]

    @patch('quilt_mcp.services.auth_service.get_auth_service')
    def test_middleware_detects_quilt_headers(self, mock_get_auth_service):
        """Test that middleware detects X-Quilt-User-Role and X-Quilt-User-Id headers."""
        # Mock the auth service
        mock_auth_service = MagicMock()
        mock_auth_service.auto_attempt_role_assumption.return_value = True
        mock_get_auth_service.return_value = mock_auth_service

        # Create a minimal MCP server for testing
        mcp = FastMCP("test-server")
        
        # Add a simple tool to test with
        @mcp.tool()
        def test_tool() -> str:
            """Simple test tool."""
            return "test-response"
        
        # Build the HTTP app with middleware
        app = build_http_app(mcp, transport="http")
        
        # Test with headers
        test_role_arn = "arn:aws:iam::123456789012:role/TestRole"
        test_user_id = "test-user-123"
        
        with TestClient(app) as client:
            response = client.get(
                "/healthz",
                headers={
                    "X-Quilt-User-Role": test_role_arn,
                    "X-Quilt-User-Id": test_user_id
                }
            )
            
            # Verify the request succeeded
            assert response.status_code == 200
            
            # Verify environment variables were set
            assert os.environ.get("QUILT_USER_ROLE_ARN") == test_role_arn
            assert os.environ.get("QUILT_USER_ID") == test_user_id
            
            # Verify auto_attempt_role_assumption was called
            mock_auth_service.auto_attempt_role_assumption.assert_called_once()

    @patch('quilt_mcp.services.auth_service.get_auth_service')
    def test_middleware_ignores_requests_without_headers(self, mock_get_auth_service):
        """Test that middleware doesn't interfere with requests without Quilt headers."""
        # Mock the auth service
        mock_auth_service = MagicMock()
        mock_get_auth_service.return_value = mock_auth_service

        mcp = FastMCP("test-server")
        
        @mcp.tool()
        def test_tool() -> str:
            return "test-response"
        
        app = build_http_app(mcp, transport="http")
        
        with TestClient(app) as client:
            response = client.get("/healthz")
            
            # Verify the request succeeded
            assert response.status_code == 200
            
            # Verify environment variables were not set
            assert os.environ.get("QUILT_USER_ROLE_ARN") is None
            assert os.environ.get("QUILT_USER_ID") is None
            
            # Verify auto_attempt_role_assumption was not called
            mock_auth_service.auto_attempt_role_assumption.assert_not_called()

    @patch('quilt_mcp.services.auth_service.get_auth_service')
    def test_middleware_handles_auth_service_exception(self, mock_get_auth_service):
        """Test that middleware handles exceptions from auth service gracefully."""
        # Mock the auth service to raise an exception
        mock_auth_service = MagicMock()
        mock_auth_service.auto_attempt_role_assumption.side_effect = Exception("Test exception")
        mock_get_auth_service.return_value = mock_auth_service

        mcp = FastMCP("test-server")
        
        @mcp.tool()
        def test_tool() -> str:
            return "test-response"
        
        app = build_http_app(mcp, transport="http")
        
        with TestClient(app) as client:
            response = client.get(
                "/healthz",
                headers={
                    "X-Quilt-User-Role": "arn:aws:iam::123456789012:role/TestRole",
                    "X-Quilt-User-Id": "test-user-123"
                }
            )
            
            # Verify the request still succeeded despite the exception
            assert response.status_code == 200
            
            # Verify environment variables were still set
            assert os.environ.get("QUILT_USER_ROLE_ARN") == "arn:aws:iam::123456789012:role/TestRole"
            assert os.environ.get("QUILT_USER_ID") == "test-user-123"

    @patch('quilt_mcp.services.auth_service.get_auth_service')
    def test_middleware_handles_partial_headers(self, mock_get_auth_service):
        """Test that middleware handles partial header information correctly."""
        # Mock the auth service
        mock_auth_service = MagicMock()
        mock_auth_service.auto_attempt_role_assumption.return_value = True
        mock_get_auth_service.return_value = mock_auth_service

        mcp = FastMCP("test-server")
        
        @mcp.tool()
        def test_tool() -> str:
            return "test-response"
        
        app = build_http_app(mcp, transport="http")
        
        # Test with only role header
        with TestClient(app) as client:
            response = client.get(
                "/healthz",
                headers={
                    "X-Quilt-User-Role": "arn:aws:iam::123456789012:role/TestRole"
                }
            )
            
            # Verify the request succeeded
            assert response.status_code == 200
            
            # Verify only role was set
            assert os.environ.get("QUILT_USER_ROLE_ARN") == "arn:aws:iam::123456789012:role/TestRole"
            assert os.environ.get("QUILT_USER_ID") is None
            
            # Verify auto_attempt_role_assumption was called
            mock_auth_service.auto_attempt_role_assumption.assert_called_once()

        # Clear environment and test with only user ID header
        if "QUILT_USER_ROLE_ARN" in os.environ:
            del os.environ["QUILT_USER_ROLE_ARN"]
        
        with TestClient(app) as client:
            response = client.get(
                "/healthz",
                headers={
                    "X-Quilt-User-Id": "test-user-123"
                }
            )
            
            # Verify the request succeeded
            assert response.status_code == 200
            
            # Verify only user ID was set
            assert os.environ.get("QUILT_USER_ROLE_ARN") is None
            assert os.environ.get("QUILT_USER_ID") == "test-user-123"
            
            # Verify auto_attempt_role_assumption was not called (no role header)
            assert mock_auth_service.auto_attempt_role_assumption.call_count == 1  # Only from previous call

    @patch('quilt_mcp.services.auth_service.get_auth_service')
    def test_middleware_preserves_request_flow(self, mock_get_auth_service):
        """Test that middleware doesn't interfere with normal request processing."""
        # Mock the auth service
        mock_auth_service = MagicMock()
        mock_auth_service.auto_attempt_role_assumption.return_value = True
        mock_get_auth_service.return_value = mock_auth_service

        mcp = FastMCP("test-server")
        
        @mcp.tool()
        def test_tool() -> str:
            return "test-response"
        
        app = build_http_app(mcp, transport="http")
        
        with TestClient(app) as client:
            # Test multiple requests to ensure middleware doesn't interfere
            for i in range(3):
                response = client.get(
                    "/healthz",
                    headers={
                        "X-Quilt-User-Role": f"arn:aws:iam::123456789012:role/TestRole{i}",
                        "X-Quilt-User-Id": f"test-user-{i}"
                    }
            )
            
            # Verify all requests succeeded
            assert response.status_code == 200
            
            # Verify the latest environment variables
            assert os.environ.get("QUILT_USER_ROLE_ARN") == "arn:aws:iam::123456789012:role/TestRole2"
            assert os.environ.get("QUILT_USER_ID") == "test-user-2"
            
            # Verify auto_attempt_role_assumption was called for each request
            assert mock_auth_service.auto_attempt_role_assumption.call_count == i + 1

    def test_middleware_works_without_auth_service(self):
        """Test that middleware works even if auth service is not available."""
        # Mock get_auth_service to raise an exception
        with patch('quilt_mcp.services.auth_service.get_auth_service', side_effect=Exception("Auth service unavailable")):
            mcp = FastMCP("test-server")
            
            @mcp.tool()
            def test_tool() -> str:
                return "test-response"
            
            app = build_http_app(mcp, transport="http")
            
            with TestClient(app) as client:
                response = client.get(
                    "/healthz",
                    headers={
                        "X-Quilt-User-Role": "arn:aws:iam::123456789012:role/TestRole",
                        "X-Quilt-User-Id": "test-user-123"
                    }
            )
            
            # Verify the request still succeeded despite auth service being unavailable
            assert response.status_code == 200
            
            # Verify environment variables were still set
            assert os.environ.get("QUILT_USER_ROLE_ARN") == "arn:aws:iam::123456789012:role/TestRole"
            assert os.environ.get("QUILT_USER_ID") == "test-user-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
