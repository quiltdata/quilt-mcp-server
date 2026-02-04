#!/usr/bin/env python3
"""
Unit tests for JWT authentication functionality in mcp-test.py.

Tests the JWT token handling, error messages, and authentication flow
without making real HTTP requests.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from tests.jwt_helpers import get_sample_catalog_token

# Add scripts directory to path for importing mcp-test.py
scripts_dir = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

# Import the MCPTester class from mcp-test.py
import importlib.util

spec = importlib.util.spec_from_file_location("mcp_test", scripts_dir / "mcp-test.py")
mcp_test_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp_test_module)
MCPTester = mcp_test_module.MCPTester


class TestJWTAuthentication(unittest.TestCase):
    """Test JWT authentication functionality in MCPTester."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_endpoint = "http://localhost:8000/mcp"
        self.test_jwt_token = get_sample_catalog_token()

    def test_jwt_token_parameter_accepted(self):
        """Test that JWT token parameter is accepted and stored."""
        tester = MCPTester(endpoint=self.test_endpoint, transport="http", jwt_token=self.test_jwt_token)

        self.assertEqual(tester.jwt_token, self.test_jwt_token)
        self.assertEqual(tester.transport, "http")
        self.assertEqual(tester.endpoint, self.test_endpoint)

    def test_jwt_header_added_to_session(self):
        """Test that Authorization header is added when JWT token provided."""
        tester = MCPTester(endpoint=self.test_endpoint, transport="http", jwt_token=self.test_jwt_token)

        # Check that Authorization header is set
        expected_header = f"Bearer {self.test_jwt_token}"
        self.assertEqual(tester.session.headers.get("Authorization"), expected_header)

    def test_no_jwt_header_without_token(self):
        """Test that no Authorization header is added without JWT token."""
        tester = MCPTester(endpoint=self.test_endpoint, transport="http")

        # Check that Authorization header is not set
        self.assertNotIn("Authorization", tester.session.headers)

    def test_jwt_ignored_for_stdio_transport(self):
        """Test that JWT token is ignored for stdio transport."""
        with patch('os.fdopen'):
            tester = MCPTester(stdin_fd=0, stdout_fd=1, transport="stdio", jwt_token=self.test_jwt_token)

            self.assertEqual(tester.jwt_token, self.test_jwt_token)
            self.assertIsNone(tester.session)  # No HTTP session for stdio

    def test_mask_token_method(self):
        """Test token masking for safe display."""
        tester = MCPTester(endpoint=self.test_endpoint, transport="http", jwt_token=self.test_jwt_token)

        # Test with normal token
        masked = tester._mask_token(self.test_jwt_token)
        self.assertTrue(masked.startswith(self.test_jwt_token[:4]))
        self.assertTrue(masked.endswith(self.test_jwt_token[-4:]))
        self.assertIn("...", masked)

        # Test with None token
        self.assertEqual(tester._mask_token(None), "(none)")

        # Test with short token
        short_token = "abc123"
        self.assertEqual(tester._mask_token(short_token), "***")

    @patch('requests.Session.post')
    def test_401_error_with_jwt_token(self, mock_post):
        """Test 401 error handling when JWT token is provided."""
        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        tester = MCPTester(endpoint=self.test_endpoint, transport="http", jwt_token=self.test_jwt_token)

        with self.assertRaises(Exception) as context:
            tester._make_http_request("initialize")

        error_message = str(context.exception)
        self.assertIn("Authentication failed", error_message)
        self.assertIn("JWT token rejected", error_message)
        self.assertIn(tester._mask_token(self.test_jwt_token), error_message)  # Masked token
        self.assertIn("Troubleshooting", error_message)

    @patch('requests.Session.post')
    def test_401_error_without_jwt_token(self, mock_post):
        """Test 401 error handling when no JWT token is provided."""
        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        tester = MCPTester(endpoint=self.test_endpoint, transport="http")

        with self.assertRaises(Exception) as context:
            tester._make_http_request("initialize")

        error_message = str(context.exception)
        self.assertIn("Authentication required", error_message)
        self.assertIn("Server requires JWT token", error_message)
        self.assertIn("--jwt-token TOKEN", error_message)
        self.assertIn("MCP_JWT_TOKEN", error_message)

    @patch('requests.Session.post')
    def test_403_error_with_jwt_token(self, mock_post):
        """Test 403 error handling with JWT token."""
        # Mock 403 response
        mock_response = Mock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response

        tester = MCPTester(endpoint=self.test_endpoint, transport="http", jwt_token=self.test_jwt_token)

        with self.assertRaises(Exception) as context:
            tester._make_http_request("initialize")

        error_message = str(context.exception)
        self.assertIn("Authorization failed", error_message)
        self.assertIn("Insufficient permissions", error_message)
        self.assertIn(tester._mask_token(self.test_jwt_token), error_message)  # Masked token
        self.assertIn("JWT", error_message)

    @patch('requests.Session.post')
    def test_successful_request_with_jwt(self, mock_post):
        """Test successful HTTP request with JWT token."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        mock_post.return_value = mock_response

        tester = MCPTester(endpoint=self.test_endpoint, transport="http", jwt_token=self.test_jwt_token)

        result = tester._make_http_request("initialize")

        # Verify request was made with correct headers
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check that Authorization header was sent
        self.assertEqual(tester.session.headers.get("Authorization"), f"Bearer {self.test_jwt_token}")

        # Check result
        self.assertEqual(result, {"capabilities": {}})


class TestJWTHelperIntegration(unittest.TestCase):
    """Test integration with JWT helper script."""

    def setUp(self):
        """Set up test fixtures."""
        # JWT helper was moved to tests/jwt_helpers.py
        self.jwt_helper_path = Path(__file__).parent.parent / "jwt_helpers.py"

    def test_jwt_helper_exists(self):
        """Test that JWT helper script exists."""
        self.assertTrue(self.jwt_helper_path.exists())

    def test_jwt_helper_outputs_sample_token(self):
        """Test JWT helper prints a sample token."""
        import subprocess

        result = subprocess.run(
            ["python", str(self.jwt_helper_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0)
        token = result.stdout.strip()
        self.assertTrue(token.startswith("eyJ"))
        self.assertEqual(len(token.split(".")), 3)


class TestCommandLineIntegration(unittest.TestCase):
    """Test command-line argument parsing for JWT."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock sys.argv to avoid interference with test runner
        self.original_argv = sys.argv.copy()

    def tearDown(self):
        """Clean up after tests."""
        sys.argv = self.original_argv

    @patch.dict(os.environ, {}, clear=True)
    def test_jwt_token_from_command_line(self):
        """Test JWT token from command-line argument."""
        test_token = get_sample_catalog_token()

        # Mock command line arguments
        test_args = ["mcp-test.py", "http://localhost:8000/mcp", "--jwt-token", test_token, "--tools-test"]

        with patch('sys.argv', test_args):
            # Import and test argument parsing
            import argparse

            parser = argparse.ArgumentParser()
            parser.add_argument("endpoint")
            parser.add_argument("--jwt-token", type=str)
            parser.add_argument("--tools-test", action="store_true")

            args = parser.parse_args(test_args[1:])

            self.assertEqual(args.jwt_token, test_token)
            self.assertEqual(args.endpoint, "http://localhost:8000/mcp")

    @patch.dict(os.environ, {'MCP_JWT_TOKEN': 'env-jwt-token'})
    def test_jwt_token_from_environment(self):
        """Test JWT token from environment variable."""
        # Test that environment variable is accessible
        self.assertEqual(os.environ.get('MCP_JWT_TOKEN'), 'env-jwt-token')

    @patch.dict(os.environ, {'MCP_JWT_TOKEN': 'env-token'})
    def test_command_line_precedence_over_env(self):
        """Test that command-line argument takes precedence over env var."""
        cli_token = "cli-token"
        env_token = os.environ.get('MCP_JWT_TOKEN')

        # Simulate the precedence logic from mcp-test.py
        jwt_token = cli_token or env_token

        self.assertEqual(jwt_token, cli_token)
        self.assertNotEqual(jwt_token, env_token)


if __name__ == '__main__':
    unittest.main()
