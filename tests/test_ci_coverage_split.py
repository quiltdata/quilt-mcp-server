"""Tests for CI workflow coverage-tools integration."""

from pathlib import Path


def test_ci_workflow_uses_coverage_split():
    """Test that CI workflow uses coverage-tools instead of single coverage."""
    ci_file = Path(__file__).parent.parent / ".github/workflows/ci.yml"
    content = ci_file.read_text()
    
    # Should use make coverage-tools
    assert "make coverage-tools" in content, "CI should use 'make coverage-tools' command"


def test_ci_workflow_uploads_split_coverage_artifacts():
    """Test that CI workflow uploads the split coverage artifacts."""
    ci_file = Path(__file__).parent.parent / ".github/workflows/ci.yml"
    content = ci_file.read_text()
    
    # Should upload build/test-results/ which contains our coverage files
    assert "build/test-results/" in content, "CI should upload build/test-results/ containing coverage files"
    
    # The existing artifact upload should include our new files automatically
    upload_section = content.split("Upload test results")[1].split("steps:")[0] if "Upload test results" in content else ""
    assert "build/test-results/" in upload_section, "Upload test results step should include build/test-results/"


def test_ci_workflow_does_not_use_old_coverage_command():
    """Test that CI workflow removes the old single coverage command."""
    ci_file = Path(__file__).parent.parent / ".github/workflows/ci.yml"
    content = ci_file.read_text()
    
    # Should not have the old --cov=quilt_mcp --cov-report=xml:src/coverage.xml command
    # We'll look for this pattern to ensure it's been replaced
    lines = content.split('\n')
    
    coverage_lines = [line for line in lines if "--cov=quilt_mcp" in line and "make coverage-tools" not in line]
    
    # We should not find any old coverage command lines (outside of make coverage-tools)
    assert len(coverage_lines) == 0, f"Found old coverage commands that should be replaced: {coverage_lines}"