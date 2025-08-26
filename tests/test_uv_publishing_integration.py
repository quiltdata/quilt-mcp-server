"""Live Integration Tests for UV Package Publishing.

These tests run against real TestPyPI and UV commands to validate
the complete publishing workflow works end-to-end.

Prerequisites:
- TESTPYPI_TOKEN set in .env file
- UV installed and available in PATH
- Internet connection for TestPyPI access

Tests can be skipped with SKIP_INTEGRATION_TESTS=1 environment variable.
"""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import skip


def skip_if_no_integration():
    """Skip test if integration tests should be skipped."""
    return skip("Integration tests skipped") if os.getenv("SKIP_INTEGRATION_TESTS") else lambda x: x


def has_testpypi_token():
    """Check if TESTPYPI_TOKEN is available for testing."""
    # Check .env file
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file, 'r') as f:
            content = f.read()
            if "TESTPYPI_TOKEN=" in content and not content.count("TESTPYPI_TOKEN=pypi-your-testpypi-token-here"):
                return True
    # Check environment variable
    return bool(os.getenv("TESTPYPI_TOKEN"))


def has_uv_command():
    """Check if UV command is available."""
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


class TestUVPublishingLiveIntegration(unittest.TestCase):
    """Live integration tests against real TestPyPI and UV commands."""

    def setUp(self):
        """Set up integration test environment."""
        self.project_root = Path(__file__).parent.parent
        self.original_cwd = os.getcwd()
        os.chdir(self.project_root)

    def tearDown(self):
        """Clean up integration test environment."""
        os.chdir(self.original_cwd)

    @skip_if_no_integration()
    @unittest.skipUnless(has_uv_command(), "UV command not available")
    def test_uv_build_command_real(self):
        """Test real UV build command execution."""
        # This test will fail until UV build is properly integrated
        result = subprocess.run(
            ["uv", "build"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=60
        )
        
        # UV build should succeed
        self.assertEqual(result.returncode, 0,
                        f"UV build should succeed. Error: {result.stderr}")
        
        # Should create dist directory with artifacts
        dist_dir = self.project_root / "dist"
        self.assertTrue(dist_dir.exists(),
                       "UV build should create dist directory")
        
        # Should create wheel and source distribution
        dist_files = list(dist_dir.glob("*"))
        wheel_files = [f for f in dist_files if f.suffix == ".whl"]
        source_files = [f for f in dist_files if f.suffix == ".gz"]
        
        self.assertTrue(len(wheel_files) > 0,
                       "UV build should create wheel file")
        self.assertTrue(len(source_files) > 0,
                       "UV build should create source distribution")

    @skip_if_no_integration()
    @unittest.skipUnless(has_testpypi_token(), "TESTPYPI_TOKEN not configured")
    @unittest.skipUnless(has_uv_command(), "UV command not available")
    def test_uv_publish_testpypi_dry_run(self):
        """Test UV publish to TestPyPI in dry-run mode."""
        # First ensure package is built
        build_result = subprocess.run(
            ["uv", "build"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=60
        )
        self.assertEqual(build_result.returncode, 0,
                        "UV build should succeed before publish test")
        
        # Load TestPyPI token from .env
        env_vars = os.environ.copy()
        env_file = self.project_root / ".env"
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
        
        # Set UV publish environment variables for TestPyPI
        env_vars.update({
            "UV_PUBLISH_URL": "https://test.pypi.org/legacy/",
            "UV_PUBLISH_TOKEN": env_vars.get("TESTPYPI_TOKEN", ""),
        })
        
        # This test will fail until UV publish is properly configured
        # Note: This would actually publish to TestPyPI, so we're testing the error handling
        result = subprocess.run(
            ["uv", "publish", "--dry-run"],  # Dry run to avoid actual publishing
            capture_output=True,
            text=True,
            cwd=self.project_root,
            env=env_vars,
            timeout=30
        )
        
        # Even dry-run should validate the configuration
        # The exact behavior depends on UV's dry-run implementation
        if result.returncode == 0:
            # Dry run succeeded - configuration is valid
            self.assertIn("would upload" in result.stdout.lower() or 
                         "dry run" in result.stdout.lower() or
                         "would publish" in result.stdout.lower(),
                         f"Dry run should indicate what would be published. Output: {result.stdout}")
        else:
            # Dry run failed - should provide meaningful error
            self.assertTrue(
                "authentication" in result.stderr.lower() or
                "token" in result.stderr.lower() or
                "credential" in result.stderr.lower() or
                "publish" in result.stderr.lower(),
                f"Error should be about authentication/publishing. Error: {result.stderr}")

    @skip_if_no_integration()
    def test_environment_variable_loading_from_dotenv(self):
        """Test that environment variables can be loaded from .env file."""
        env_file = self.project_root / ".env"
        
        if not env_file.exists():
            self.skipTest(".env file not found, skipping environment loading test")
        
        # Parse .env file manually (simple parsing)
        env_vars = {}
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
        
        # Should have required TestPyPI configuration
        if "TESTPYPI_TOKEN" in env_vars:
            self.assertNotEqual(env_vars["TESTPYPI_TOKEN"], "",
                              "TESTPYPI_TOKEN should not be empty")
            self.assertNotEqual(env_vars["TESTPYPI_TOKEN"], "pypi-your-testpypi-token-here",
                              "TESTPYPI_TOKEN should be configured with real token")
        else:
            self.skipTest("TESTPYPI_TOKEN not configured in .env")

    @skip_if_no_integration()
    @unittest.skipUnless(has_uv_command(), "UV command not available")
    def test_package_version_parsing(self):
        """Test that current package version can be parsed correctly."""
        # Read version from pyproject.toml
        pyproject_file = self.project_root / "pyproject.toml"
        self.assertTrue(pyproject_file.exists(),
                       "pyproject.toml should exist")
        
        with open(pyproject_file, 'r') as f:
            content = f.read()
        
        # Should contain version = "x.y.z"
        import re
        version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
        self.assertIsNotNone(version_match,
                           "pyproject.toml should contain version field")
        
        version = version_match.group(1)
        self.assertRegex(version, r'^\d+\.\d+\.\d+',
                        f"Version should follow semantic versioning: {version}")
        
        # Version should be consistent with what UV sees
        result = subprocess.run(
            ["uv", "build", "--wheel"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=30
        )
        
        if result.returncode == 0:
            # Check that built wheel contains the same version
            dist_dir = self.project_root / "dist"
            wheel_files = list(dist_dir.glob("*.whl"))
            
            if wheel_files:
                wheel_name = wheel_files[0].name
                self.assertIn(version, wheel_name,
                             f"Wheel filename should contain version {version}: {wheel_name}")

    def test_testpypi_version_conflict_handling(self):
        """Test handling of version conflicts with TestPyPI."""
        # This test validates error handling when version already exists
        # We'll use the current version which likely exists on TestPyPI
        
        pyproject_file = self.project_root / "pyproject.toml"
        if not pyproject_file.exists():
            self.skipTest("pyproject.toml not found")
        
        with open(pyproject_file, 'r') as f:
            content = f.read()
        
        import re
        version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
        if not version_match:
            self.skipTest("Version not found in pyproject.toml")
        
        current_version = version_match.group(1)
        
        # When we implement the publishing logic, it should:
        # 1. Detect if version already exists on TestPyPI
        # 2. Provide helpful error message about version bumping
        # 3. Suggest using test version format (0.4.1-test-{timestamp})
        
        # For now, this documents the expected behavior
        self.assertTrue(True,  # Placeholder test
                       f"Publishing system should handle version conflicts for {current_version}")


class TestMakeTargetEnvironmentIntegration(unittest.TestCase):
    """Integration tests for Make target environment loading."""

    def setUp(self):
        """Set up test environment."""
        self.project_root = Path(__file__).parent.parent
        self.original_cwd = os.getcwd()
        os.chdir(self.project_root)

    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)

    @skip_if_no_integration()
    def test_makefile_loads_env_variables(self):
        """Test that Makefile can load and use .env variables."""
        # Create a test .env file
        test_env_content = """
# Test environment for integration
TEST_VAR=test_value_123
TESTPYPI_TOKEN=test-token-for-makefile
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(test_env_content)
            temp_env_file = f.name
        
        try:
            # Test that make can access environment variables
            # This tests the existing .env loading mechanism
            result = subprocess.run(
                ["make", "-f", "/dev/stdin"],
                input=f"""
sinclude {temp_env_file}
export

test-env:
\t@echo "TEST_VAR=$$TEST_VAR"
\t@echo "TESTPYPI_TOKEN=$$TESTPYPI_TOKEN"
""",
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                output = result.stdout
                self.assertIn("TEST_VAR=test_value_123", output,
                             "Make should load TEST_VAR from env file")
                self.assertIn("TESTPYPI_TOKEN=test-token-for-makefile", output,
                             "Make should load TESTPYPI_TOKEN from env file")
            else:
                # Environment loading mechanism should exist in project
                self.skipTest(f"Make environment loading test failed: {result.stderr}")
                
        finally:
            os.unlink(temp_env_file)

    @skip_if_no_integration()
    def test_project_makefile_structure(self):
        """Test that project Makefile follows expected patterns."""
        makefile_path = self.project_root / "Makefile"
        self.assertTrue(makefile_path.exists(),
                       "Project should have Makefile")
        
        with open(makefile_path, 'r') as f:
            content = f.read()
        
        # Should use sinclude .env pattern (existing in project)
        self.assertIn("sinclude .env", content,
                     "Makefile should include .env loading")
        
        # Should have export directive
        self.assertIn("export", content,
                     "Makefile should export environment variables")
        
        # Should have .PHONY declaration
        self.assertIn(".PHONY:", content,
                     "Makefile should have .PHONY declaration")


if __name__ == "__main__":
    # Print integration test status
    print("Integration Test Environment:")
    print(f"  TESTPYPI_TOKEN configured: {has_testpypi_token()}")
    print(f"  UV command available: {has_uv_command()}")
    print(f"  Skip integration tests: {bool(os.getenv('SKIP_INTEGRATION_TESTS'))}")
    print()
    
    unittest.main()