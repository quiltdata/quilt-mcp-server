#!/usr/bin/env python3
"""
Coverage Analysis Script

Parses XML coverage reports from multiple test suites and generates
comparative analysis in CSV format.

Input Files:
- build/test-results/coverage-unit.xml
- build/test-results/coverage-integration.xml
- build/test-results/coverage-e2e.xml

Output:
- build/test-results/coverage-analysis.csv

CSV Columns:
- file: Source file path
- unit_coverage: Unit test coverage percentage
- integration_coverage: Integration test coverage percentage
- e2e_coverage: E2E test coverage percentage
- combined_coverage: Overall coverage percentage
- lines_total: Total lines in file
- lines_covered: Lines covered by any test
- coverage_gaps: Lines only covered by specific test types

Error Handling:
- Missing XML files: Log warning and continue with available files
- Malformed XML: Skip invalid files and report parsing errors
- Empty coverage data: Generate CSV with zero values but maintain file structure
- Write failures: Exit with error code 1 and clear error message
"""

import csv
import logging
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Set, Tuple, Optional


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class CoverageData:
    """Represents coverage data for a single file."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.unit_lines: Set[int] = set()
        self.integration_lines: Set[int] = set()
        self.e2e_lines: Set[int] = set()
        self.total_lines = 0

    def add_coverage(self, suite_type: str, covered_lines: Set[int], total_lines: int):
        """Add coverage data for a specific test suite."""
        self.total_lines = max(self.total_lines, total_lines)

        if suite_type == "unit":
            self.unit_lines = covered_lines
        elif suite_type == "integration":
            self.integration_lines = covered_lines
        elif suite_type == "e2e":
            self.e2e_lines = covered_lines

    def get_coverage_percentages(self) -> Tuple[float, float, float, float]:
        """Calculate coverage percentages for each suite and combined."""
        if self.total_lines == 0:
            return 0.0, 0.0, 0.0, 0.0

        unit_pct = len(self.unit_lines) / self.total_lines * 100
        integration_pct = len(self.integration_lines) / self.total_lines * 100
        e2e_pct = len(self.e2e_lines) / self.total_lines * 100

        combined_lines = self.unit_lines | self.integration_lines | self.e2e_lines
        combined_pct = len(combined_lines) / self.total_lines * 100

        return unit_pct, integration_pct, e2e_pct, combined_pct

    def get_coverage_gaps(self) -> str:
        """Identify coverage gaps between test suites."""
        gaps = []

        unit_only = self.unit_lines - self.integration_lines - self.e2e_lines
        if unit_only:
            gaps.append(f"unit-only:{len(unit_only)}")

        integration_only = self.integration_lines - self.unit_lines - self.e2e_lines
        if integration_only:
            gaps.append(f"integration-only:{len(integration_only)}")

        e2e_only = self.e2e_lines - self.unit_lines - self.integration_lines
        if e2e_only:
            gaps.append(f"e2e-only:{len(e2e_only)}")

        return ";".join(gaps) if gaps else "none"


def parse_coverage_xml(xml_file: Path) -> Dict[str, Tuple[Set[int], int]]:
    """Parse a coverage XML file and extract file coverage data.

    Args:
        xml_file: Path to the coverage XML file

    Returns:
        Dict mapping file paths to (covered_lines_set, total_lines)
    """
    if not xml_file.exists():
        logger.warning(f"Coverage file not found: {xml_file}")
        return {}

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        coverage_data = {}

        # Navigate XML structure: coverage -> packages -> package -> classes -> class
        for package in root.findall(".//package"):
            for class_elem in package.findall(".//class"):
                filename = class_elem.get("filename", "")
                if not filename:
                    continue

                # Extract line coverage
                covered_lines = set()
                total_lines = 0

                for line in class_elem.findall(".//line"):
                    line_num = int(line.get("number", "0"))
                    hits = int(line.get("hits", "0"))

                    total_lines = max(total_lines, line_num)
                    if hits > 0:
                        covered_lines.add(line_num)

                coverage_data[filename] = (covered_lines, total_lines)

        logger.info(f"Parsed {len(coverage_data)} files from {xml_file}")
        return coverage_data

    except ET.ParseError as e:
        logger.error(f"Failed to parse XML file {xml_file}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error parsing {xml_file}: {e}")
        return {}


def generate_coverage_analysis() -> None:
    """Generate comprehensive coverage analysis CSV."""
    # Define input and output paths
    test_results_dir = Path("build/test-results")
    output_csv = test_results_dir / "coverage-analysis.csv"

    # Ensure output directory exists
    test_results_dir.mkdir(parents=True, exist_ok=True)

    # Define coverage XML files
    coverage_files = {
        "unit": test_results_dir / "coverage-unit.xml",
        "integration": test_results_dir / "coverage-integration.xml",
        "e2e": test_results_dir / "coverage-e2e.xml",
    }

    # Parse all coverage files
    all_coverage_data: Dict[str, Dict[str, Tuple[Set[int], int]]] = {}
    all_files: Set[str] = set()

    for suite_type, xml_file in coverage_files.items():
        coverage_data = parse_coverage_xml(xml_file)
        all_coverage_data[suite_type] = coverage_data
        all_files.update(coverage_data.keys())

    if not all_files:
        logger.warning("No coverage data found in any XML files")
        # Create empty CSV file to maintain workflow compatibility
        with open(output_csv, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'file', 'unit_coverage', 'integration_coverage', 'e2e_coverage',
                'combined_coverage', 'lines_total', 'lines_covered', 'coverage_gaps'
            ])
        return

    # Build comprehensive coverage analysis
    file_coverage_map: Dict[str, CoverageData] = {}

    for file_path in all_files:
        coverage = CoverageData(file_path)

        for suite_type in ["unit", "integration", "e2e"]:
            if file_path in all_coverage_data[suite_type]:
                covered_lines, total_lines = all_coverage_data[suite_type][file_path]
                coverage.add_coverage(suite_type, covered_lines, total_lines)

        file_coverage_map[file_path] = coverage

    # Generate CSV output
    try:
        with open(output_csv, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow([
                'file', 'unit_coverage', 'integration_coverage', 'e2e_coverage',
                'combined_coverage', 'lines_total', 'lines_covered', 'coverage_gaps'
            ])

            # Write data rows
            for file_path in sorted(file_coverage_map.keys()):
                coverage = file_coverage_map[file_path]
                unit_pct, integration_pct, e2e_pct, combined_pct = coverage.get_coverage_percentages()

                combined_lines = coverage.unit_lines | coverage.integration_lines | coverage.e2e_lines

                writer.writerow([
                    file_path,
                    f"{unit_pct:.1f}",
                    f"{integration_pct:.1f}",
                    f"{e2e_pct:.1f}",
                    f"{combined_pct:.1f}",
                    coverage.total_lines,
                    len(combined_lines),
                    coverage.get_coverage_gaps()
                ])

        logger.info(f"Coverage analysis CSV generated: {output_csv}")
        logger.info(f"Analyzed {len(file_coverage_map)} files across {len(coverage_files)} test suites")

    except IOError as e:
        logger.error(f"Failed to write CSV file {output_csv}: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    logger.info("Starting coverage analysis...")
    generate_coverage_analysis()
    logger.info("Coverage analysis completed successfully")


if __name__ == "__main__":
    main()