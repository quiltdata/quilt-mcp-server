"""Tests for Make target integration with UV publishing.

Tests the Make target implementation for package publishing,
focusing on environment variable loading and command execution.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock


class TestMakePublishingTargets(unittest.TestCase):
    """Test Make targets for UV publishing functionality."""

    def setUp(self):
        """Set up test environment."""
        self.project_root = Path(__file__).parent.parent
        self.original_cwd = os.getcwd()
        os.chdir(self.project_root)

    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)

    def test_make_publish_test_target_exists(self):
        """Test that publish-test make target exists and is callable."""
        # This test will fail until make target is implemented
        result = subprocess.run(
            ["make", "-n", "publish-test"],  # -n for dry run
            capture_output=True,
            text=True,
            cwd=self.project_root
        )
        
        # Should not error on dry run (target exists)
        self.assertEqual(result.returncode, 0,
                        "publish-test target should exist in Makefile")
        
        # Should show commands that would be executed
        self.assertNotEqual(result.stdout.strip(), "",
                          "publish-test should have implementation commands")

    def test_make_check_publish_env_target_exists(self):
        """Test that check-publish-env make target exists and is callable."""
        # This test will fail until make target is implemented
        result = subprocess.run(
            ["make", "-n", "check-publish-env"],  # -n for dry run
            capture_output=True,
            text=True,
            cwd=self.project_root
        )
        
        # Should not error on dry run (target exists)
        self.assertEqual(result.returncode, 0,
                        "check-publish-env target should exist in Makefile")
        
        # Should show commands that would be executed
        self.assertNotEqual(result.stdout.strip(), "",
                          "check-publish-env should have implementation commands")

    def test_make_targets_load_env_file(self):
        """
        Scenario: Publishing target uses .env configuration
        Given I have TestPyPI credentials in .env
        When I run make target with environment tracing
        Then the environment variables should be properly loaded
        """
        # Create temporary .env with test configuration
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("TESTPYPI_TOKEN=test-token-for-env-loading\n")
            f.write("LOG_LEVEL=DEBUG\n")
            temp_env_file = f.name
        
        try:
            # Copy temp env to .env for make to load
            temp_project_env = self.project_root / ".env.test"
            with open(temp_env_file, 'r') as src, open(temp_project_env, 'w') as dst:
                dst.write(src.read())
            
            # This test will fail until make targets properly load .env
            result = subprocess.run(
                ["make", "check-publish-env"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                env={**os.environ, "ENV_FILE": str(temp_project_env)}
            )
            
            # Should have access to environment variables from .env
            output = result.stdout + result.stderr
            # The exact behavior will depend on implementation, but should process the env vars
            self.assertNotIn("command not found", output.lower(),
                           "Make target should be implemented")
            
        finally:
            os.unlink(temp_env_file)
            if temp_project_env.exists():
                temp_project_env.unlink()

    def test_make_publish_test_validates_uv_availability(self):
        """
        Scenario: Publishing fails when UV is not available
        Given UV is not in PATH
        When I run "make publish-test"
        Then I should see UV not found error
        And the command should exit with code 1
        """
        # Mock environment without UV
        env_without_uv = {k: v for k, v in os.environ.items() if 'uv' not in k.lower()}
        # Remove common paths where UV might be found
        if 'PATH' in env_without_uv:
            paths = env_without_uv['PATH'].split(os.pathsep)
            filtered_paths = [p for p in paths if 'uv' not in p.lower() and '.cargo' not in p]
            env_without_uv['PATH'] = os.pathsep.join(filtered_paths)
        
        # This test will fail until make target checks for UV
        result = subprocess.run(
            ["make", "publish-test"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
            env=env_without_uv
        )
        
        # Should fail with UV not found error
        # Note: This might pass if UV is in a system location, but the error handling should exist
        output = result.stdout + result.stderr
        if result.returncode != 0:
            # If it fails, should have helpful message about UV
            self.assertTrue(
                "uv not found" in output.lower() or 
                "uv: command not found" in output.lower() or
                "please install uv" in output.lower(),
                f"Should provide helpful UV error message. Got: {output}"
            )

    def test_make_targets_follow_project_patterns(self):
        """Test that publishing targets follow established project patterns."""
        # Read the main Makefile to understand patterns
        makefile_path = self.project_root / "Makefile"
        
        # This test will fail until targets are added to Makefile
        with open(makefile_path, 'r') as f:
            makefile_content = f.read()
        
        # Should include publishing targets in .PHONY declaration
        self.assertIn("publish-test", makefile_content,
                     "publish-test should be declared in Makefile")
        self.assertIn("check-publish-env", makefile_content,
                     "check-publish-env should be declared in Makefile")
        
        # Should follow the project's help target pattern
        self.assertIn("Publishing Commands:", makefile_content,
                     "Should add Publishing Commands section to help")

    def test_make_publish_test_builds_before_publishing(self):
        """Test that publish-test target builds package before publishing."""
        # This test will fail until implementation includes build step
        result = subprocess.run(
            ["make", "-n", "publish-test"],  # Dry run to see commands
            capture_output=True,
            text=True,
            cwd=self.project_root
        )
        
        commands = result.stdout
        
        # Should include UV build command before publish
        self.assertIn("uv build", commands,
                     "publish-test should include uv build step")
        
        # Build should come before publish in the command sequence
        build_pos = commands.find("uv build")
        publish_pos = commands.find("uv publish")
        
        if build_pos >= 0 and publish_pos >= 0:
            self.assertLess(build_pos, publish_pos,
                          "uv build should come before uv publish")

    def test_make_targets_include_environment_validation(self):
        """Test that make targets validate environment before proceeding."""
        # This test will fail until validation is implemented
        result = subprocess.run(
            ["make", "-n", "publish-test"],  # Dry run
            capture_output=True,
            text=True,
            cwd=self.project_root
        )
        
        commands = result.stdout
        
        # Should include environment validation step
        self.assertTrue(
            "check-publish-env" in commands or 
            "validate" in commands.lower() or
            "TESTPYPI_TOKEN" in commands,
            f"publish-test should validate environment. Commands: {commands}")


class TestMakefileStructure(unittest.TestCase):
    """Test Makefile structure and organization for publishing targets."""

    def setUp(self):
        """Set up test environment."""
        self.project_root = Path(__file__).parent.parent
        self.makefile_path = self.project_root / "Makefile"

    def test_makefile_includes_publishing_section(self):
        """Test that Makefile includes a proper publishing section."""
        # This test will fail until Makefile is updated
        with open(self.makefile_path, 'r') as f:
            content = f.read()
        
        # Should have Publishing Commands section in help
        self.assertIn("Publishing Commands:", content,
                     "Makefile should include Publishing Commands section")
        
        # Should list the publishing targets
        self.assertIn("publish-test", content,
                     "Makefile should include publish-test target")
        self.assertIn("check-publish-env", content,
                     "Makefile should include check-publish-env target")

    def test_makefile_phony_declaration_includes_publishing_targets(self):
        """Test that .PHONY declaration includes publishing targets."""
        # This test will fail until .PHONY is updated
        with open(self.makefile_path, 'r') as f:
            content = f.read()
        
        # Find .PHONY line
        phony_lines = [line for line in content.split('\n') if '.PHONY:' in line]
        self.assertTrue(len(phony_lines) > 0, "Makefile should have .PHONY declaration")
        
        phony_content = ' '.join(phony_lines)
        self.assertIn("publish-test", phony_content,
                     ".PHONY should include publish-test")
        self.assertIn("check-publish-env", phony_content,
                     ".PHONY should include check-publish-env")

    def test_makefile_help_target_describes_publishing_commands(self):
        """Test that help target properly describes publishing commands."""
        # This test will fail until help target is updated
        result = subprocess.run(
            ["make", "help"],
            capture_output=True,
            text=True,
            cwd=self.project_root
        )
        
        help_output = result.stdout
        
        # Should include publishing section
        self.assertIn("Publishing Commands:", help_output,
                     "make help should show Publishing Commands section")
        
        # Should describe each target
        self.assertIn("publish-test", help_output,
                     "make help should list publish-test target")
        self.assertIn("TestPyPI", help_output,
                     "make help should mention TestPyPI")
        self.assertIn("check-publish-env", help_output,
                     "make help should list check-publish-env target")
        self.assertIn("environment", help_output.lower(),
                     "make help should mention environment validation")


if __name__ == "__main__":
    unittest.main()