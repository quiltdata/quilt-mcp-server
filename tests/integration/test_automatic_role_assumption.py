"""
Integration tests for automatic role assumption functionality.

These tests verify that the QuiltRoleMiddleware correctly detects headers
and triggers automatic role assumption in the AuthenticationService.
"""
import os
import pytest
import boto3
from unittest.mock import patch, MagicMock
from fastmcp import FastMCP
from starlette.testclient import TestClient

from quilt_mcp.utils import build_http_app, create_configured_server
from quilt_mcp.services.auth_service import get_auth_service


class TestAutomaticRoleAssumption:
    """Test automatic role assumption via middleware."""

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

    def test_middleware_detects_quilt_headers(self):
        """Test that middleware detects X-Quilt-User-Role and X-Quilt-User-Id headers."""
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

    def test_middleware_ignores_requests_without_headers(self):
        """Test that middleware doesn't interfere with requests without Quilt headers."""
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

    @patch('quilt_mcp.services.auth_service.boto3.client')
    def test_automatic_role_assumption_triggered(self, mock_boto3_client):
        """Test that automatic role assumption is triggered when headers are present."""
        # Mock STS client and assume_role response
        mock_sts_client = MagicMock()
        mock_boto3_client.return_value = mock_sts_client
        
        # Mock successful assume_role response
        mock_assume_role_response = {
            'Credentials': {
                'AccessKeyId': 'ASIA1234567890',
                'SecretAccessKey': 'secret123',
                'SessionToken': 'token123',
                'Expiration': '2024-01-01T00:00:00Z'
            },
            'AssumedRoleUser': {
                'AssumedRoleId': 'AROA1234567890:test-session',
                'Arn': 'arn:aws:sts::123456789012:assumed-role/TestRole/test-session'
            }
        }
        mock_sts_client.assume_role.return_value = mock_assume_role_response
        
        # Mock get_caller_identity for role validation
        mock_get_caller_identity = {
            'UserId': 'AROA1234567890:test-session',
            'Account': '123456789012',
            'Arn': 'arn:aws:sts::123456789012:assumed-role/TestRole/test-session'
        }
        mock_sts_client.get_caller_identity.return_value = mock_get_caller_identity
        
        mcp = FastMCP("test-server")
        
        @mcp.tool()
        def test_tool() -> str:
            return "test-response"
        
        app = build_http_app(mcp, transport="http")
        
        test_role_arn = "arn:aws:iam::123456789012:role/TestRole"
        
        with TestClient(app) as client:
            response = client.get(
                "/healthz",
                headers={
                    "X-Quilt-User-Role": test_role_arn,
                    "X-Quilt-User-Id": "test-user-123"
                }
            )
            
            # Verify the request succeeded
            assert response.status_code == 200
            
            # Verify assume_role was called with correct parameters
            mock_sts_client.assume_role.assert_called_once()
            call_args = mock_sts_client.assume_role.call_args
            
            assert call_args[1]['RoleArn'] == test_role_arn
            assert 'RoleSessionName' in call_args[1]
            assert call_args[1]['DurationSeconds'] == 3600

    def test_auth_service_auto_assumption_method(self):
        """Test the auto_attempt_role_assumption method directly."""
        from quilt_mcp.services.auth_service import AuthenticationService
        
        # Create auth service instance
        auth_service = AuthenticationService()
        
        # Set up environment variable
        test_role_arn = "arn:aws:iam::123456789012:role/TestRole"
        os.environ["QUILT_USER_ROLE_ARN"] = test_role_arn
        
        # Mock the assume_quilt_user_role method
        with patch.object(auth_service, 'assume_quilt_user_role', return_value=True) as mock_assume:
            result = auth_service.auto_attempt_role_assumption()
            
            # Verify the method was called
            mock_assume.assert_called_once_with(test_role_arn)
            assert result is True

    def test_auth_service_auto_assumption_no_role(self):
        """Test auto_attempt_role_assumption when no role is set."""
        from quilt_mcp.services.auth_service import AuthenticationService
        
        auth_service = AuthenticationService()
        
        # Ensure no role is set
        if "QUILT_USER_ROLE_ARN" in os.environ:
            del os.environ["QUILT_USER_ROLE_ARN"]
        
        with patch.object(auth_service, 'assume_quilt_user_role') as mock_assume:
            result = auth_service.auto_attempt_role_assumption()
            
            # Verify assume_quilt_user_role was not called
            mock_assume.assert_not_called()
            assert result is True

    def test_auth_service_auto_assumption_same_role(self):
        """Test auto_attempt_role_assumption when same role is already assumed."""
        from quilt_mcp.services.auth_service import AuthenticationService
        
        auth_service = AuthenticationService()
        test_role_arn = "arn:aws:iam::123456789012:role/TestRole"
        
        # Set environment variable and mark role as already assumed
        os.environ["QUILT_USER_ROLE_ARN"] = test_role_arn
        auth_service._assumed_role_arn = test_role_arn
        
        with patch.object(auth_service, 'assume_quilt_user_role') as mock_assume:
            result = auth_service.auto_attempt_role_assumption()
            
            # Verify assume_quilt_user_role was not called (already assumed)
            mock_assume.assert_not_called()
            assert result is True

    def test_get_boto3_session_triggers_auto_assumption(self):
        """Test that get_boto3_session triggers automatic role assumption."""
        from quilt_mcp.services.auth_service import AuthenticationService
        
        auth_service = AuthenticationService()
        test_role_arn = "arn:aws:iam::123456789012:role/TestRole"
        os.environ["QUILT_USER_ROLE_ARN"] = test_role_arn
        
        # Mock the auto_attempt_role_assumption method
        with patch.object(auth_service, 'auto_attempt_role_assumption') as mock_auto:
            # Mock the session
            mock_session = MagicMock()
            auth_service._boto3_session = mock_session
            
            result = auth_service.get_boto3_session()
            
            # Verify auto_attempt_role_assumption was called
            mock_auto.assert_called_once()
            assert result == mock_session

    def test_middleware_order_does_not_interfere_with_cors(self):
        """Test that the QuiltRoleMiddleware doesn't interfere with CORS functionality."""
        mcp = FastMCP("test-server")
        
        @mcp.tool()
        def test_tool() -> str:
            return "test-response"
        
        app = build_http_app(mcp, transport="http")
        
        with TestClient(app) as client:
            # Test CORS preflight request
            response = client.options(
                "/healthz",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "x-quilt-user-role"
                }
            )
            
            # Verify CORS headers are present
            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
            assert "access-control-allow-headers" in response.headers

    def test_health_endpoint_with_quilt_headers(self):
        """Test that the health endpoint works correctly with Quilt headers."""
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
            
            # Verify health endpoint responds correctly
            assert response.status_code == 200
            health_data = response.json()
            assert "status" in health_data
            assert "uptime_seconds" in health_data
            assert "transport" in health_data
            assert health_data["transport"] == "http"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
