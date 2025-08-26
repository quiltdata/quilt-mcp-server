"""BDD Tests for UV Package Publishing functionality.

This module contains behavior-driven tests for UV-based PyPI package publishing,
including local TestPyPI publishing and environment validation.

Tests follow TDD principles and will initially fail until implementation is complete.
"""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from subprocess import CompletedProcess


class TestUVPublishingBehavior(unittest.TestCase):
    """Test UV publishing behavior through Make targets."""

    def setUp(self):
        """Set up test environment."""
        self.project_root = Path(__file__).parent.parent
        self.original_cwd = os.getcwd()
        os.chdir(self.project_root)

    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)

    def test_make_help_includes_publishing_targets(self):
        """
        Scenario: Publishing targets appear in make help
        Given I am in the project root directory
        When I run "make help"
        Then the output should contain publishing commands
        And the output should contain target descriptions
        """
        # This test will fail until make targets are implemented
        result = subprocess.run(
            ["make", "help"], 
            capture_output=True, 
            text=True,
            cwd=self.project_root
        )
        
        # Verify make help includes publishing targets
        help_output = result.stdout
        self.assertIn("Publishing Commands:", help_output, 
                     "make help should include Publishing Commands section")
        self.assertIn("make publish-test", help_output,
                     "make help should list publish-test target")
        self.assertIn("make check-publish-env", help_output,
                     "make help should list check-publish-env target")
        self.assertIn("Publish package to TestPyPI", help_output,
                     "make help should describe publish-test target")
        self.assertIn("Validate publishing environment", help_output,
                     "make help should describe check-publish-env target")

    def test_make_publish_test_fails_without_credentials(self):
        """
        Scenario: Attempt publishing without TestPyPI credentials
        Given TestPyPI credentials are missing from .env
        When I run "make publish-test"
        Then I should see error about missing credentials
        And the command should exit with code 1
        And no UV publish command should be executed
        """
        # Create temporary .env without TestPyPI credentials
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("# No TestPyPI credentials\n")
            f.write("LOG_LEVEL=INFO\n")
            temp_env_file = f.name
        
        try:
            # This test will fail until make target is implemented
            result = subprocess.run(
                ["make", "publish-test"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                env={**os.environ, "ENV_FILE": temp_env_file}
            )
            
            # Should fail with clear error message
            self.assertNotEqual(result.returncode, 0,
                              "publish-test should fail without credentials")
            self.assertIn("TestPyPI credentials not configured", result.stderr,
                         "Should show missing credentials error")
            self.assertIn("Please add TESTPYPI_TOKEN to .env", result.stderr,
                         "Should provide setup guidance")
            
        finally:
            os.unlink(temp_env_file)

    def test_make_check_publish_env_validates_missing_variables(self):
        """
        Scenario: Validate environment with missing variables
        Given my .env file is missing TestPyPI configuration
        When I run "make check-publish-env"
        Then I should see missing required environment variables
        And I should see specific error messages
        And the command should exit with code 1
        """
        # Create temporary .env without publishing variables
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("# Missing publishing configuration\n")
            f.write("LOG_LEVEL=INFO\n")
            temp_env_file = f.name
        
        try:
            # This test will fail until make target is implemented
            result = subprocess.run(
                ["make", "check-publish-env"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                env={**os.environ, "ENV_FILE": temp_env_file}
            )
            
            # Should fail and report missing variables
            self.assertNotEqual(result.returncode, 0,
                              "check-publish-env should fail with missing variables")
            output = result.stdout + result.stderr
            self.assertIn("Missing required environment variables", output,
                         "Should report missing variables")
            self.assertIn("TESTPYPI_TOKEN", output,
                         "Should list missing TESTPYPI_TOKEN")
            
        finally:
            os.unlink(temp_env_file)

    def test_make_check_publish_env_validates_complete_configuration(self):
        """
        Scenario: Validate complete TestPyPI environment configuration
        Given I have complete TestPyPI configuration in .env
        When I run "make check-publish-env"
        Then I should see configuration valid message
        And the command should exit with code 0
        """
        # Create temporary .env with complete configuration
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("TESTPYPI_TOKEN=pypi-test-token-here\n")
            f.write("LOG_LEVEL=INFO\n")
            temp_env_file = f.name
        
        try:
            # This test will fail until make target is implemented
            result = subprocess.run(
                ["make", "check-publish-env"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                env={**os.environ, "ENV_FILE": temp_env_file}
            )
            
            # Should succeed with validation confirmation
            self.assertEqual(result.returncode, 0,
                           "check-publish-env should succeed with valid config")
            output = result.stdout + result.stderr
            self.assertIn("TestPyPI configuration valid", output,
                         "Should confirm valid configuration")
            self.assertIn("UV publishing environment ready", output,
                         "Should confirm environment ready")
            
        finally:
            os.unlink(temp_env_file)


class TestUVPublishingEnvironmentValidation(unittest.TestCase):
    """Test environment variable validation logic."""

    def test_validate_testpypi_environment_missing_token(self):
        """Test validation fails when TESTPYPI_TOKEN is missing."""
        # This will fail until validation function is implemented
        from quilt_mcp.publishing import validate_testpypi_environment
        
        # Test with missing token
        env_vars = {"LOG_LEVEL": "INFO"}
        result = validate_testpypi_environment(env_vars)
        
        self.assertFalse(result.is_valid,
                        "Validation should fail without TESTPYPI_TOKEN")
        self.assertIn("TESTPYPI_TOKEN", result.missing_variables,
                     "Should identify missing TESTPYPI_TOKEN")
        self.assertIn("credentials not configured", result.error_message,
                     "Should provide clear error message")

    def test_validate_testpypi_environment_valid_configuration(self):
        """Test validation succeeds with complete configuration."""
        # This will fail until validation function is implemented
        from quilt_mcp.publishing import validate_testpypi_environment
        
        # Test with complete configuration
        env_vars = {
            "TESTPYPI_TOKEN": "pypi-test-token",
            "LOG_LEVEL": "INFO"
        }
        result = validate_testpypi_environment(env_vars)
        
        self.assertTrue(result.is_valid,
                       "Validation should succeed with complete config")
        self.assertEqual(len(result.missing_variables), 0,
                        "Should have no missing variables")
        self.assertIn("valid", result.success_message.lower(),
                     "Should provide success confirmation")


class TestUVPublishingIntegration(unittest.TestCase):
    """Integration tests for UV publishing with real commands."""

    def setUp(self):
        """Set up integration test environment."""
        self.project_root = Path(__file__).parent.parent
        self.original_cwd = os.getcwd()
        os.chdir(self.project_root)

    def tearDown(self):
        """Clean up integration test environment."""
        os.chdir(self.original_cwd)

    @patch('subprocess.run')
    def test_uv_build_command_execution(self, mock_run):
        """Test UV build command is executed correctly."""
        # This will fail until build function is implemented
        from quilt_mcp.publishing import build_package
        
        # Mock successful UV build
        mock_run.return_value = CompletedProcess(
            args=['uv', 'build'], 
            returncode=0,
            stdout="Building wheel for quilt-mcp-server\nBuilding source distribution\n",
            stderr=""
        )
        
        result = build_package()
        
        # Verify UV build was called correctly
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]  # First positional argument
        self.assertEqual(args[0], "uv", "Should call UV command")
        self.assertEqual(args[1], "build", "Should call build subcommand")
        
        # Verify result indicates success
        self.assertTrue(result.success, "Build should report success")
        self.assertIn("Building wheel", result.output, "Should capture build output")

    @patch('subprocess.run')
    def test_uv_publish_command_with_testpypi_config(self, mock_run):
        """Test UV publish command uses TestPyPI configuration."""
        # This will fail until publish function is implemented
        from quilt_mcp.publishing import publish_to_testpypi
        
        # Mock successful UV publish
        mock_run.return_value = CompletedProcess(
            args=['uv', 'publish'], 
            returncode=0,
            stdout="Uploading quilt_mcp_server-0.4.1.tar.gz\nUploaded to TestPyPI\n",
            stderr=""
        )
        
        config = {
            "TESTPYPI_TOKEN": "pypi-test-token",
            "UV_PUBLISH_URL": "https://test.pypi.org/legacy/"
        }
        
        result = publish_to_testpypi(config)
        
        # Verify UV publish was called with correct parameters
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]  # First positional argument
        self.assertEqual(args[0], "uv", "Should call UV command")
        self.assertEqual(args[1], "publish", "Should call publish subcommand")
        
        # Check environment variables were set correctly
        env = mock_run.call_args[1].get('env', {})
        self.assertIn("UV_PUBLISH_TOKEN", env, "Should set UV_PUBLISH_TOKEN")
        self.assertEqual(env["UV_PUBLISH_TOKEN"], "pypi-test-token",
                        "Should use provided token")
        
        # Verify result indicates success
        self.assertTrue(result.success, "Publish should report success")
        self.assertIn("Uploaded to TestPyPI", result.output, "Should capture publish output")

    def test_generate_test_version_creates_unique_version(self):
        """Test version generation creates unique versions for testing."""
        # This will fail until version function is implemented
        from quilt_mcp.publishing import generate_test_version
        
        version1 = generate_test_version()
        time.sleep(0.1)  # Ensure different timestamp
        version2 = generate_test_version()
        
        # Should generate unique versions
        self.assertNotEqual(version1, version2, "Should generate unique versions")
        self.assertTrue(version1.startswith("0.4.1-test-"), 
                       "Should follow test version format")
        self.assertTrue(version2.startswith("0.4.1-test-"), 
                       "Should follow test version format")
        
        # Should contain timestamp
        self.assertRegex(version1, r'0\.4\.1-test-\d+', "Should include timestamp")
        self.assertRegex(version2, r'0\.4\.1-test-\d+', "Should include timestamp")


if __name__ == "__main__":
    unittest.main()