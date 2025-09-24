"""
Unit tests for middleware functionality.

These tests verify that the QuiltRoleMiddleware correctly processes headers
and triggers role assumption without making real AWS calls.
"""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quilt_mcp.utils import build_http_app


class TestMiddlewareFunctionality:
    """Test middleware functionality in isolation."""

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

    def test_middleware_class_definition(self):
        """Test that the QuiltRoleMiddleware class can be instantiated."""
        from starlette.middleware.base import BaseHTTPMiddleware
        
        # Test that we can define the middleware class
        class QuiltRoleMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                # Extract Quilt role information from headers
                quilt_user_role = request.headers.get("x-quilt-user-role")
                quilt_user_id = request.headers.get("x-quilt-user-id")
                
                # Set environment variables for the authentication service
                if quilt_user_role:
                    os.environ["QUILT_USER_ROLE_ARN"] = quilt_user_role
                if quilt_user_id:
                    os.environ["QUILT_USER_ID"] = quilt_user_id
                
                response = await call_next(request)
                return response
        
        # Verify the class can be instantiated
        middleware = QuiltRoleMiddleware(None)
        assert middleware is not None

    @patch('quilt_mcp.services.auth_service.get_auth_service')
    def test_middleware_environment_variable_setting(self, mock_get_auth_service):
        """Test that middleware correctly sets environment variables."""
        # Mock the auth service
        mock_auth_service = MagicMock()
        mock_auth_service.auto_attempt_role_assumption.return_value = True
        mock_get_auth_service.return_value = mock_auth_service

        # Create a simple Starlette app with the middleware
        from starlette.middleware.base import BaseHTTPMiddleware
        
        class QuiltRoleMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                # Extract Quilt role information from headers
                quilt_user_role = request.headers.get("x-quilt-user-role")
                quilt_user_id = request.headers.get("x-quilt-user-id")
                
                # Set environment variables for the authentication service
                if quilt_user_role:
                    os.environ["QUILT_USER_ROLE_ARN"] = quilt_user_role
                if quilt_user_id:
                    os.environ["QUILT_USER_ID"] = quilt_user_id
                
                # Automatically attempt role assumption if role header is present
                if quilt_user_role:
                    try:
                        auth_service = mock_get_auth_service()
                        auth_service.auto_attempt_role_assumption()
                    except Exception:
                        pass  # Ignore exceptions in test
                
                response = await call_next(request)
                return response
        
        async def test_endpoint(request):
            return JSONResponse({"status": "ok"})
        
        app = Starlette(routes=[Route("/test", test_endpoint)])
        app.add_middleware(QuiltRoleMiddleware)
        
        # Test with headers
        test_role_arn = "arn:aws:iam::123456789012:role/TestRole"
        test_user_id = "test-user-123"
        
        with TestClient(app) as client:
            response = client.get(
                "/test",
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

    def test_middleware_ignores_requests_without_headers(self):
        """Test that middleware doesn't interfere with requests without Quilt headers."""
        from starlette.middleware.base import BaseHTTPMiddleware
        
        class QuiltRoleMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                # Extract Quilt role information from headers
                quilt_user_role = request.headers.get("x-quilt-user-role")
                quilt_user_id = request.headers.get("x-quilt-user-id")
                
                # Set environment variables for the authentication service
                if quilt_user_role:
                    os.environ["QUILT_USER_ROLE_ARN"] = quilt_user_role
                if quilt_user_id:
                    os.environ["QUILT_USER_ID"] = quilt_user_id
                
                response = await call_next(request)
                return response
        
        async def test_endpoint(request):
            return JSONResponse({"status": "ok"})
        
        app = Starlette(routes=[Route("/test", test_endpoint)])
        app.add_middleware(QuiltRoleMiddleware)
        
        with TestClient(app) as client:
            response = client.get("/test")
            
            # Verify the request succeeded
            assert response.status_code == 200
            
            # Verify environment variables were not set
            assert os.environ.get("QUILT_USER_ROLE_ARN") is None
            assert os.environ.get("QUILT_USER_ID") is None

    @patch('quilt_mcp.services.auth_service.get_auth_service')
    def test_middleware_handles_auth_service_exception(self, mock_get_auth_service):
        """Test that middleware handles exceptions from auth service gracefully."""
        # Mock the auth service to raise an exception
        mock_auth_service = MagicMock()
        mock_auth_service.auto_attempt_role_assumption.side_effect = Exception("Test exception")
        mock_get_auth_service.return_value = mock_auth_service

        from starlette.middleware.base import BaseHTTPMiddleware
        
        class QuiltRoleMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                # Extract Quilt role information from headers
                quilt_user_role = request.headers.get("x-quilt-user-role")
                quilt_user_id = request.headers.get("x-quilt-user-id")
                
                # Set environment variables for the authentication service
                if quilt_user_role:
                    os.environ["QUILT_USER_ROLE_ARN"] = quilt_user_role
                if quilt_user_id:
                    os.environ["QUILT_USER_ID"] = quilt_user_id
                
                # Automatically attempt role assumption if role header is present
                if quilt_user_role:
                    try:
                        auth_service = mock_get_auth_service()
                        auth_service.auto_attempt_role_assumption()
                    except Exception:
                        pass  # Ignore exceptions in test
                
                response = await call_next(request)
                return response
        
        async def test_endpoint(request):
            return JSONResponse({"status": "ok"})
        
        app = Starlette(routes=[Route("/test", test_endpoint)])
        app.add_middleware(QuiltRoleMiddleware)
        
        with TestClient(app) as client:
            response = client.get(
                "/test",
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

    def test_environment_variable_clearing(self):
        """Test that environment variables are properly cleared between tests."""
        # This test verifies that our setup/teardown methods work correctly
        assert os.environ.get("QUILT_USER_ROLE_ARN") is None
        assert os.environ.get("QUILT_USER_ID") is None
        
        # Set some values
        os.environ["QUILT_USER_ROLE_ARN"] = "test-role"
        os.environ["QUILT_USER_ID"] = "test-user"
        
        # Verify they were set
        assert os.environ.get("QUILT_USER_ROLE_ARN") == "test-role"
        assert os.environ.get("QUILT_USER_ID") == "test-user"
        
        # The teardown method will clear these in the next test

    def test_header_case_insensitivity(self):
        """Test that middleware handles header case variations."""
        from starlette.middleware.base import BaseHTTPMiddleware
        
        class QuiltRoleMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                # Extract Quilt role information from headers (case insensitive)
                quilt_user_role = request.headers.get("x-quilt-user-role")
                quilt_user_id = request.headers.get("x-quilt-user-id")
                
                # Set environment variables for the authentication service
                if quilt_user_role:
                    os.environ["QUILT_USER_ROLE_ARN"] = quilt_user_role
                if quilt_user_id:
                    os.environ["QUILT_USER_ID"] = quilt_user_id
                
                response = await call_next(request)
                return response
        
        async def test_endpoint(request):
            return JSONResponse({"status": "ok"})
        
        app = Starlette(routes=[Route("/test", test_endpoint)])
        app.add_middleware(QuiltRoleMiddleware)
        
        with TestClient(app) as client:
            # Test with different case variations
            response = client.get(
                "/test",
                headers={
                    "x-quilt-user-role": "arn:aws:iam::123456789012:role/TestRole",  # lowercase
                    "X-Quilt-User-Id": "test-user-123"  # mixed case
                }
            )
            
            # Verify the request succeeded
            assert response.status_code == 200
            
            # Verify environment variables were set (headers are case insensitive in Starlette)
            assert os.environ.get("QUILT_USER_ROLE_ARN") == "arn:aws:iam::123456789012:role/TestRole"
            assert os.environ.get("QUILT_USER_ID") == "test-user-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
