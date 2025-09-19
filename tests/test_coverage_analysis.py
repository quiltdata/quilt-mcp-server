"""Tests for coverage analysis script."""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
import pytest
import csv
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def create_sample_coverage_xml(filename: str, file_coverage_data: dict) -> str:
    """Create a sample coverage XML file for testing.

    Args:
        filename: Name of the XML file to create
        file_coverage_data: Dict mapping file paths to (lines_covered, lines_total)

    Returns:
        Path to the created XML file
    """
    root = ET.Element("coverage")
    root.set("version", "5.5")

    packages = ET.SubElement(root, "packages")
    package = ET.SubElement(packages, "package", name="quilt_mcp")
    classes = ET.SubElement(package, "classes")

    for file_path, (lines_covered, lines_total) in file_coverage_data.items():
        class_elem = ET.SubElement(classes, "class",
                                 filename=file_path,
                                 name=file_path.replace("/", ".").replace(".py", ""))

        lines = ET.SubElement(class_elem, "lines")

        # Create line elements - covered lines have hits > 0
        for line_num in range(1, lines_total + 1):
            hits = "1" if line_num <= lines_covered else "0"
            ET.SubElement(lines, "line", number=str(line_num), hits=hits)

    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)
    return filename


class TestCoverageAnalysis:
    """Test the coverage analysis functionality."""

    def test_parse_coverage_xml_valid_file(self):
        """Test parsing a valid coverage XML file."""
        from scripts.coverage_analysis import parse_coverage_xml

        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            sample_data = {
                "src/quilt_mcp/tools/auth.py": (85, 100),
                "src/quilt_mcp/tools/buckets.py": (72, 100),
            }
            create_sample_coverage_xml(f.name, sample_data)

            try:
                result = parse_coverage_xml(Path(f.name))

                assert len(result) == 2
                assert "src/quilt_mcp/tools/auth.py" in result
                assert "src/quilt_mcp/tools/buckets.py" in result

                # Check auth.py coverage
                auth_covered, auth_total = result["src/quilt_mcp/tools/auth.py"]
                assert len(auth_covered) == 85
                assert auth_total == 100

                # Check buckets.py coverage
                buckets_covered, buckets_total = result["src/quilt_mcp/tools/buckets.py"]
                assert len(buckets_covered) == 72
                assert buckets_total == 100

            finally:
                os.unlink(f.name)

    def test_parse_coverage_xml_missing_file(self):
        """Test handling of missing XML files."""
        from scripts.coverage_analysis import parse_coverage_xml

        result = parse_coverage_xml(Path("/nonexistent/file.xml"))
        assert result == {}

    def test_parse_coverage_xml_malformed_file(self):
        """Test handling of malformed XML files."""
        from scripts.coverage_analysis import parse_coverage_xml

        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write("invalid xml content")
            f.flush()

            try:
                result = parse_coverage_xml(Path(f.name))
                assert result == {}
            finally:
                os.unlink(f.name)

    def test_coverage_data_class(self):
        """Test the CoverageData class functionality."""
        from scripts.coverage_analysis import CoverageData

        coverage = CoverageData("src/test.py")

        # Add coverage for different suites
        coverage.add_coverage("unit", {1, 2, 3, 4, 5}, 10)
        coverage.add_coverage("integration", {3, 4, 5, 6, 7}, 10)
        coverage.add_coverage("e2e", {5, 6, 7, 8, 9}, 10)

        # Test coverage percentages
        unit_pct, integration_pct, e2e_pct, combined_pct = coverage.get_coverage_percentages()

        assert unit_pct == 50.0  # 5 out of 10 lines
        assert integration_pct == 50.0  # 5 out of 10 lines
        assert e2e_pct == 50.0  # 5 out of 10 lines
        assert combined_pct == 90.0  # 9 unique lines out of 10

        # Test coverage gaps
        gaps = coverage.get_coverage_gaps()
        assert "unit-only:2" in gaps  # lines 1,2
        assert "e2e-only:2" in gaps  # lines 8,9
        # No integration-only lines in this test data (lines 6,7 are shared with e2e)

    def test_generate_coverage_csv_complete_data(self):
        """Test CSV generation with complete coverage data."""
        from scripts.coverage_analysis import generate_coverage_analysis

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test directory structure
            test_results_dir = Path(temp_dir) / "build" / "test-results"
            test_results_dir.mkdir(parents=True)

            # Create sample coverage XML files
            unit_data = {
                "src/quilt_mcp/tools/auth.py": (85, 100),
                "src/quilt_mcp/tools/buckets.py": (72, 100),
            }
            integration_data = {
                "src/quilt_mcp/tools/auth.py": (45, 100),
                "src/quilt_mcp/tools/buckets.py": (89, 100),
            }
            e2e_data = {
                "src/quilt_mcp/tools/auth.py": (12, 100),
                "src/quilt_mcp/tools/buckets.py": (34, 100),
            }

            unit_file = str(test_results_dir / "coverage-unit.xml")
            integration_file = str(test_results_dir / "coverage-integration.xml")
            e2e_file = str(test_results_dir / "coverage-e2e.xml")

            create_sample_coverage_xml(unit_file, unit_data)
            create_sample_coverage_xml(integration_file, integration_data)
            create_sample_coverage_xml(e2e_file, e2e_data)

            # Change to temp directory and run analysis
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                generate_coverage_analysis()

                # Verify CSV was created
                csv_file = test_results_dir / "coverage-analysis.csv"
                assert csv_file.exists()

                # Verify CSV content
                with open(csv_file, 'r') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)

                assert len(rows) == 2

                # Check auth.py row
                auth_row = next(r for r in rows if r['file'] == 'src/quilt_mcp/tools/auth.py')
                assert auth_row['unit_coverage'] == '85.0'
                assert auth_row['integration_coverage'] == '45.0'
                assert auth_row['e2e_coverage'] == '12.0'
                assert auth_row['lines_total'] == '100'

                # Check buckets.py row
                buckets_row = next(r for r in rows if r['file'] == 'src/quilt_mcp/tools/buckets.py')
                assert buckets_row['unit_coverage'] == '72.0'
                assert buckets_row['integration_coverage'] == '89.0'
                assert buckets_row['e2e_coverage'] == '34.0'
                assert buckets_row['lines_total'] == '100'

            finally:
                os.chdir(original_dir)

    def test_generate_coverage_csv_empty_data(self):
        """Test CSV generation with no coverage data."""
        from scripts.coverage_analysis import generate_coverage_analysis

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test directory structure (but no XML files)
            test_results_dir = Path(temp_dir) / "build" / "test-results"
            test_results_dir.mkdir(parents=True)

            # Change to temp directory and run analysis
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                generate_coverage_analysis()

                # Verify empty CSV was created
                csv_file = test_results_dir / "coverage-analysis.csv"
                assert csv_file.exists()

                # Verify CSV has header only
                with open(csv_file, 'r') as f:
                    content = f.read()
                    lines = content.strip().split('\n')
                    assert len(lines) == 1  # Header only
                    assert lines[0].startswith('file,unit_coverage')

            finally:
                os.chdir(original_dir)


# BDD-style test to verify the expected behavior
def test_coverage_analysis_workflow():
    """Behavior test: Complete coverage analysis workflow."""
    from scripts.coverage_analysis import generate_coverage_analysis

    with tempfile.TemporaryDirectory() as temp_dir:
        # Given: Multiple coverage XML files exist with different coverage data
        test_results_dir = Path(temp_dir) / "build" / "test-results"
        test_results_dir.mkdir(parents=True)

        unit_data = {"src/test.py": (8, 10)}
        integration_data = {"src/test.py": (6, 10)}
        e2e_data = {"src/test.py": (4, 10)}

        create_sample_coverage_xml(str(test_results_dir / "coverage-unit.xml"), unit_data)
        create_sample_coverage_xml(str(test_results_dir / "coverage-integration.xml"), integration_data)
        create_sample_coverage_xml(str(test_results_dir / "coverage-e2e.xml"), e2e_data)

        # When: Coverage analysis is run
        original_dir = os.getcwd()
        try:
            os.chdir(temp_dir)
            generate_coverage_analysis()

            # Then: A CSV file is generated with file-level coverage analysis
            csv_file = test_results_dir / "coverage-analysis.csv"
            assert csv_file.exists()

            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            row = rows[0]

            # And: Coverage gaps are identified and reported
            assert row['file'] == 'src/test.py'
            assert row['unit_coverage'] == '80.0'
            assert row['integration_coverage'] == '60.0'
            assert row['e2e_coverage'] == '40.0'
            assert 'unit-only' in row['coverage_gaps'] or row['coverage_gaps'] == 'none'

        finally:
            os.chdir(original_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])