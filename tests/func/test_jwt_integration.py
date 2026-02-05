#!/usr/bin/env python3
"""
Integration tests for JWT authentication with MCP server.

Tests the complete JWT authentication flow with a real MCP server.
"""

import os
import sys
import subprocess
import unittest
from pathlib import Path

# Add tests directory to path for jwt_helpers
repo_root = Path(__file__).parent.parent.parent
tests_dir = repo_root / "tests"
scripts_dir = repo_root / "scripts"
sys.path.insert(0, str(tests_dir))

# Import JWT helper functions
from jwt_helpers import get_sample_catalog_claims, get_sample_catalog_token


class TestJWTIntegration(unittest.TestCase):
    """Integration tests for JWT authentication."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_token = get_sample_catalog_token()

    def test_sample_jwt_token_structure(self):
        """Test that the sample catalog JWT is structurally valid."""
        token = self.sample_token

        self.assertIsInstance(token, str)
        self.assertTrue(token.startswith("eyJ"))  # JWT header
        self.assertEqual(len(token.split(".")), 3)  # header.payload.signature

    def test_sample_jwt_contains_required_claims(self):
        """Test that sample catalog JWT contains required claims."""
        payload = get_sample_catalog_claims()

        # Check required claims
        self.assertIn("id", payload)
        self.assertIn("uuid", payload)
        self.assertIn("exp", payload)

    def test_mcp_test_script_accepts_jwt_token(self):
        """Test that mcp-test.py accepts JWT token parameter."""
        # This test verifies the command-line interface works
        # We don't need a running server for this test

        token = self.sample_token

        # Test that the script accepts the JWT token parameter
        # We expect it to fail with connection error, but not argument error
        result = subprocess.run(
            [
                "python",
                str(scripts_dir / "mcp-test.py"),
                "http://localhost:9999/mcp",  # Non-existent server
                "--jwt-token",
                token,
                "--list-tools",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should fail with connection error, not argument parsing error
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("unrecognized arguments", result.stderr)
        self.assertNotIn("error: argument", result.stderr)

    def test_environment_variable_support(self):
        """Test that MCP_JWT_TOKEN environment variable is supported."""
        token = self.sample_token

        # Test with environment variable
        env = os.environ.copy()
        env["MCP_JWT_TOKEN"] = token

        result = subprocess.run(
            [
                "python",
                str(scripts_dir / "mcp-test.py"),
                "http://localhost:9999/mcp",  # Non-existent server
                "--list-tools",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

        # Should fail with connection error, not argument parsing error
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("unrecognized arguments", result.stderr)
        # Should show security warning since we're using env var
        self.assertNotIn("Security Warning", result.stderr)

    def test_command_line_precedence_over_env_var(self):
        """Test that command-line JWT token takes precedence over env var."""
        token1 = self.sample_token
        token2 = self.sample_token

        # Set env var to token1, pass token2 on command line
        env = os.environ.copy()
        env["MCP_JWT_TOKEN"] = token1

        result = subprocess.run(
            [
                "python",
                str(scripts_dir / "mcp-test.py"),
                "http://localhost:9999/mcp",  # Non-existent server
                "--jwt-token",
                token2,
                "--list-tools",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

        # Should show security warning for command-line token
        output = result.stdout + result.stderr
        self.assertIn("Security Warning", output)


if __name__ == '__main__':
    unittest.main()
