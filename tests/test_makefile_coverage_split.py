"""Tests for the coverage-split Makefile target."""

import subprocess
import tempfile
from pathlib import Path


def test_coverage_split_target_exists():
    """Test that the coverage-split target exists in make.dev."""
    makefile_path = Path(__file__).parent.parent / "make.dev"
    content = makefile_path.read_text()
    
    # The target should exist
    assert "coverage-split:" in content, "coverage-split target not found in make.dev"


def test_coverage_split_target_runs_unit_and_integration_tests():
    """Test that coverage-split target runs both unit and integration tests with coverage."""
    # Test that the target exists and can be invoked (dry-run style check)  
    makefile_path = Path(__file__).parent.parent / "make.dev"
    content = makefile_path.read_text()
    
    # Verify the target structure includes the expected pytest commands
    coverage_split_section = content.split("coverage-split:")[1].split("\n\n")[0] if "coverage-split:" in content else ""
    
    # Should run pytest for both unit and integration tests
    assert "pytest tests/" in coverage_split_section, "coverage-split should run pytest on tests/"
    assert "--cov=quilt_mcp" in coverage_split_section, "coverage-split should include coverage reporting"


def test_coverage_split_creates_expected_output_files():
    """Test that coverage-split creates the expected output files in build/test-results/."""
    # This is more of an integration test - we'll verify the target structure
    # without running the full test suite (which could be slow)
    
    makefile_path = Path(__file__).parent.parent / "make.dev"
    content = makefile_path.read_text()
    
    # Check that the target mentions the expected output files
    coverage_split_section = content.split("coverage-split:")[1].split("\n\n")[0] if "coverage-split:" in content else ""
    
    # Should create build/test-results directory
    assert "build/test-results" in coverage_split_section, "coverage-split should create build/test-results directory"
    
    # Should generate coverage XML files
    expected_files = ["coverage-unit.xml", "coverage-integration.xml", "coverage-summary.md"]
    for expected_file in expected_files:
        assert expected_file in coverage_split_section, f"coverage-split should generate {expected_file}"


def test_coverage_split_uses_correct_test_markers():
    """Test that coverage-split uses the correct test markers for unit/integration classification."""
    makefile_path = Path(__file__).parent.parent / "make.dev"
    content = makefile_path.read_text()
    
    coverage_split_section = content.split("coverage-split:")[1].split("\n\n")[0] if "coverage-split:" in content else ""
    
    # Should use "not aws and not search" for unit tests
    assert "not aws and not search" in coverage_split_section, "Unit tests should exclude aws and search markers"
    
    # Should use "aws or search" for integration tests  
    assert "aws or search" in coverage_split_section, "Integration tests should include aws or search markers"