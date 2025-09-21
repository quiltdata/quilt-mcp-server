#!/usr/bin/env python3
"""
Test that all scripts in the scripts/ directory can be executed without errors.

This test ensures that all Python scripts maintain basic functionality and
can be called without immediate syntax or import errors.
"""

import subprocess
import sys
from pathlib import Path
import pytest


class TestScripts:
    """Test suite for scripts execution."""

    def test_version_script(self):
        """Test that version.py runs with get-version command."""
        script_path = Path("scripts/version.py")
        result = subprocess.run(
            [sys.executable, str(script_path), "get-version"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should succeed and return a version string
        assert result.returncode == 0
        assert result.stdout.strip()  # Should have version output

    def test_mcp_test_script_help(self):
        """Test that mcp-test.py shows help without errors."""
        script_path = Path("scripts/mcp-test.py")
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should succeed and show help
        assert result.returncode == 0
        assert "Modern MCP endpoint testing tool" in result.stdout

    def test_coverage_analysis_script(self):
        """Test that coverage_analysis.py runs without errors."""
        script_path = Path("scripts/coverage_analysis.py")
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should succeed (creates empty CSV if no coverage files found)
        assert result.returncode == 0

    def test_mcp_list_script(self):
        """Test that mcp-list.py runs without errors."""
        script_path = Path("scripts/mcp-list.py")
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Should succeed and generate output files
        assert result.returncode == 0
        assert "Canonical tool listings generated!" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__])