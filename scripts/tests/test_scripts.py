#!/usr/bin/env python3
"""
Test suite for scripts directory.

Ensures Python scripts in scripts/ can be imported and basic functionality works.
"""

import sys
import subprocess
import pytest
from pathlib import Path

# Add scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))


class TestScriptImports:
    """Test that scripts can be imported without errors."""

    def test_version_script_import(self):
        """Test version.py can be imported."""
        import version
        assert hasattr(version, 'get_version')
        assert hasattr(version, 'main')

    def test_coverage_analysis_import(self):
        """Test coverage_analysis.py can be imported."""
        import coverage_analysis
        # Basic smoke test - check it has expected attributes
        assert hasattr(coverage_analysis, '__name__')

    def test_mcp_test_import(self):
        """Test mcp-test.py can be imported."""
        # Import with hyphen name requires importlib
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mcp_test", SCRIPTS_DIR / "mcp-test.py"
        )
        mcp_test = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mcp_test)
        assert hasattr(mcp_test, 'MCPTester')

    def test_mcp_list_import(self):
        """Test mcp-list.py can be imported."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mcp_list", SCRIPTS_DIR / "mcp-list.py"
        )
        mcp_list = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mcp_list)
        # Check it has expected functionality
        assert hasattr(mcp_list, 'main')


class TestScriptExecution:
    """Test that scripts can execute basic commands without crashing."""

    def test_version_script_help(self):
        """Test version.py shows help when called incorrectly."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "version.py")],
            capture_output=True,
            text=True
        )
        # Should exit with error code but not crash
        assert result.returncode != 0
        assert "Usage:" in result.stderr

    def test_mcp_test_help(self):
        """Test mcp-test.py shows help."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "mcp-test.py"), "--help"],
            capture_output=True,
            text=True
        )
        # Should exit successfully and show help
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "MCP endpoint" in result.stdout

    def test_mcp_list_help(self):
        """Test mcp-list.py shows help."""
        build_dir = (SCRIPTS_DIR.parent / "build")
        build_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "mcp-list.py"), "--help"],
            capture_output=True,
            text=True
        )
        # Should exit successfully and show help
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "MCP" in result.stdout

    def test_docker_unified_script(self):
        """Ensure docker.py generates expected tags and functions correctly."""
        script = SCRIPTS_DIR / "docker.py"
        assert script.exists(), "docker.py must exist"

        # Test tags command (replaces docker_image.py functionality)
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "tags",
                "--registry",
                "123456789012.dkr.ecr.us-east-1.amazonaws.com",
                "--version",
                "1.2.3",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        output = result.stdout.strip().splitlines()
        assert "123456789012.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:1.2.3" in output
        assert "123456789012.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:latest" in output

        # Test JSON output format
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "tags",
                "--registry",
                "test.registry.com",
                "--version",
                "2.0.0",
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        import json
        data = json.loads(result.stdout)
        assert data["registry"] == "test.registry.com"
        assert data["image"] == "quilt-mcp-server"
        assert "2.0.0" in data["tags"]
        assert "latest" in data["tags"]

        # Test --no-latest flag
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "tags",
                "--registry",
                "test.registry.com",
                "--version",
                "3.0.0",
                "--no-latest",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        output = result.stdout.strip().splitlines()
        assert "test.registry.com/quilt-mcp-server:3.0.0" in output
        assert "test.registry.com/quilt-mcp-server:latest" not in output

    def test_docker_script_help(self):
        """Test docker.py shows help properly."""
        script = SCRIPTS_DIR / "docker.py"
        assert script.exists(), "docker.py must exist"

        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Docker build and deployment" in result.stdout
        assert "tags" in result.stdout
        assert "build" in result.stdout
        assert "push" in result.stdout
        assert "info" in result.stdout

    def test_docker_info_command(self):
        """Test docker.py info command for getting image URIs."""
        script = SCRIPTS_DIR / "docker.py"
        assert script.exists(), "docker.py must exist"

        # Test text output
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "info",
                "--registry",
                "123456789012.dkr.ecr.us-east-1.amazonaws.com",
                "--version",
                "1.2.3",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.strip() == "123456789012.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:1.2.3"

        # Test GitHub Actions output format
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "info",
                "--registry",
                "test.registry.com",
                "--version",
                "2.0.0",
                "--output",
                "github",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.stdout.strip() == "image-uri=test.registry.com/quilt-mcp-server:2.0.0"

    def test_docker_image_legacy_compatibility(self):
        """Ensure legacy docker_image.py still works if it exists."""
        legacy_script = SCRIPTS_DIR / "docker_image.py"
        if legacy_script.exists():
            result = subprocess.run(
                [
                    sys.executable,
                    str(legacy_script),
                    "--registry",
                    "123456789012.dkr.ecr.us-east-1.amazonaws.com",
                    "--version",
                    "1.2.3",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            output = result.stdout.strip().splitlines()
            assert "123456789012.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:1.2.3" in output
            assert "123456789012.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:latest" in output

    def test_post_release_status_import(self):
        """Test post_release_status.py can be imported."""
        import post_release_status
        assert hasattr(post_release_status, 'generate_release_comment')
        assert hasattr(post_release_status, 'find_pr_for_tag')
        assert hasattr(post_release_status, 'post_comment_to_pr')
        assert hasattr(post_release_status, 'main')

    def test_post_release_status_help(self):
        """Test post_release_status.py shows help."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "post_release_status.py"), "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Post release status to GitHub releases and PRs" in result.stdout

    def test_post_release_status_dry_run(self):
        """Test post_release_status.py dry run mode."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "post_release_status.py"),
                "--version", "1.2.3",
                "--release-url", "https://github.com/owner/repo/releases/v1.2.3",
                "--pypi-url", "https://pypi.org/project/quilt-mcp-server/1.2.3/",
                "--docker-image", "123.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:1.2.3",
                "--dry-run"
            ],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "DRY RUN - Comment Body" in result.stdout
        assert "## 🚀 Release Status for v1.2.3" in result.stdout
        assert "https://github.com/owner/repo/releases/v1.2.3" in result.stdout
        assert "docker pull 123.dkr.ecr.us-east-1.amazonaws.com/quilt-mcp-server:1.2.3" in result.stdout
        assert "pip install quilt-mcp-server==1.2.3" in result.stdout

    def test_post_release_status_dev_version(self):
        """Test post_release_status.py with dev version."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "post_release_status.py"),
                "--version", "1.2.3-dev-20250101120000",
                "--release-url", "https://github.com/owner/repo/releases/v1.2.3-dev",
                "--pypi-url", "https://test.pypi.org/project/quilt-mcp-server/1.2.3-dev/",
                "--is-production", "false",
                "--dry-run"
            ],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Install from TestPyPI" in result.stdout
        assert "pip install -i https://test.pypi.org/simple/" in result.stdout


class TestScriptSyntax:
    """Test that all Python scripts have valid syntax."""

    @pytest.mark.parametrize("script_name", [
        "version.py",
        "coverage_analysis.py",
        "mcp-test.py",
        "mcp-list.py",
        "docker.py",
        "post_release_status.py"
    ])
    def test_script_syntax(self, script_name):
        """Test script has valid Python syntax."""
        script_path = SCRIPTS_DIR / script_name
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(script_path)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Syntax error in {script_name}: {result.stderr}"
