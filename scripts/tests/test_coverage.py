#!/usr/bin/env python3
"""
Coverage Threshold Validation Tests

Runs coverage_analysis.py and validates that coverage meets minimum thresholds
defined in coverage_required.yaml.

Usage:
    pytest scripts/tests/test_coverage.py
    python scripts/tests/test_coverage.py

Exit Codes:
    0 - All coverage thresholds met
    1 - Coverage thresholds not met or analysis failed
"""

import csv
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pytest
import yaml


# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TEST_RESULTS_DIR = PROJECT_ROOT / "build" / "test-results"
COVERAGE_ANALYSIS_SCRIPT = SCRIPTS_DIR / "coverage_analysis.py"
COVERAGE_REQUIRED_YAML = SCRIPTS_DIR / "tests" / "coverage_required.yaml"
COVERAGE_CSV = TEST_RESULTS_DIR / "coverage-analysis.csv"


class CoverageThresholds:
    """Container for coverage threshold configuration."""

    def __init__(self, config: dict):
        self.summary = config.get("summary", {})
        self.files = config.get("files") or {}
        self.strict = config.get("strict", False)
        self.exempt_files = config.get("exempt_files") or []

    def get_file_thresholds(self, file_path: str) -> Dict[str, float]:
        """Get thresholds for a specific file, falling back to summary defaults."""
        if file_path in self.files:
            return self.files[file_path]
        return self.summary

    def is_exempt(self, file_path: str) -> bool:
        """Check if a file is exempt from coverage requirements."""
        from fnmatch import fnmatch
        return any(fnmatch(file_path, pattern) for pattern in self.exempt_files)


class CoverageReport:
    """Represents parsed coverage analysis results."""

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.files: Dict[str, Dict[str, str]] = {}
        self.summary: Dict[str, str] = {}
        self._parse_csv()

    def _parse_csv(self):
        """Parse the coverage CSV file."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Coverage CSV not found: {self.csv_path}")

        with open(self.csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                file_path = row['file']
                if file_path == 'SUMMARY':
                    self.summary = row
                else:
                    self.files[file_path] = row

    def get_file_coverage(self, file_path: str) -> Dict[str, float]:
        """Get coverage percentages for a specific file."""
        if file_path not in self.files:
            return {}

        row = self.files[file_path]
        return {
            'unit_pct_covered': float(row['unit_pct_covered']),
            'integration_pct_covered': float(row['integration_pct_covered']),
            'e2e_pct_covered': float(row['e2e_pct_covered']),
            'combined_pct_covered': float(row['combined_pct_covered']),
        }

    def get_summary_coverage(self) -> Dict[str, float]:
        """Get summary coverage percentages."""
        if not self.summary:
            return {}

        return {
            'unit_pct_covered': float(self.summary['unit_pct_covered']),
            'integration_pct_covered': float(self.summary['integration_pct_covered']),
            'e2e_pct_covered': float(self.summary['e2e_pct_covered']),
            'combined_pct_covered': float(self.summary['combined_pct_covered']),
        }


def run_coverage_analysis() -> bool:
    """Run the coverage analysis script.

    Returns:
        True if analysis completed successfully, False otherwise
    """
    try:
        result = subprocess.run(
            [sys.executable, str(COVERAGE_ANALYSIS_SCRIPT)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            print(f"Coverage analysis failed with exit code {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        print("Coverage analysis timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"Failed to run coverage analysis: {e}")
        return False


def load_thresholds() -> CoverageThresholds:
    """Load coverage thresholds from YAML configuration."""
    if not COVERAGE_REQUIRED_YAML.exists():
        raise FileNotFoundError(
            f"Coverage thresholds config not found: {COVERAGE_REQUIRED_YAML}"
        )

    with open(COVERAGE_REQUIRED_YAML, 'r') as f:
        config = yaml.safe_load(f)

    return CoverageThresholds(config)


def validate_coverage(
    report: CoverageReport,
    thresholds: CoverageThresholds
) -> Tuple[bool, List[str]]:
    """Validate coverage against thresholds.

    Args:
        report: Parsed coverage report
        thresholds: Coverage threshold configuration

    Returns:
        Tuple of (all_passed, error_messages)
    """
    errors = []
    all_passed = True

    # Validate summary coverage
    summary_coverage = report.get_summary_coverage()
    summary_thresholds = thresholds.summary

    if summary_coverage:
        for metric, threshold in summary_thresholds.items():
            actual = summary_coverage.get(metric, 0.0)
            if actual < threshold:
                all_passed = False
                errors.append(
                    f"SUMMARY {metric}: {actual:.1f}% < {threshold:.1f}% (required)"
                )

    # Validate per-file coverage
    for file_path, coverage_data in report.files.items():
        # Skip exempt files
        if thresholds.is_exempt(file_path):
            continue

        file_thresholds = thresholds.get_file_thresholds(file_path)
        file_coverage = report.get_file_coverage(file_path)

        for metric, threshold in file_thresholds.items():
            actual = file_coverage.get(metric, 0.0)
            if actual < threshold:
                all_passed = False
                errors.append(
                    f"{file_path} {metric}: {actual:.1f}% < {threshold:.1f}% (required)"
                )

    return all_passed, errors


class TestCoverageThresholds:
    """Test suite for coverage threshold validation."""

    @pytest.fixture(scope="class")
    def coverage_report(self):
        """Generate and load coverage report."""
        # Run coverage analysis
        success = run_coverage_analysis()
        assert success, "Coverage analysis script failed"

        # Load the generated report
        report = CoverageReport(COVERAGE_CSV)
        return report

    @pytest.fixture(scope="class")
    def thresholds(self):
        """Load coverage thresholds."""
        return load_thresholds()

    def test_coverage_analysis_runs(self, coverage_report):
        """Test that coverage analysis script runs successfully."""
        assert coverage_report is not None
        assert COVERAGE_CSV.exists(), f"Coverage CSV not generated: {COVERAGE_CSV}"

    def test_summary_coverage_meets_thresholds(self, coverage_report, thresholds):
        """Test that summary coverage meets minimum thresholds."""
        summary_coverage = coverage_report.get_summary_coverage()
        assert summary_coverage, "No summary coverage data found"

        errors = []
        for metric, threshold in thresholds.summary.items():
            actual = summary_coverage.get(metric, 0.0)
            if actual < threshold:
                errors.append(
                    f"{metric}: {actual:.1f}% < {threshold:.1f}% (required)"
                )

        assert not errors, "Summary coverage thresholds not met:\n" + "\n".join(errors)

    def test_file_coverage_meets_thresholds(self, coverage_report, thresholds):
        """Test that per-file coverage meets minimum thresholds."""
        errors = []

        for file_path in coverage_report.files.keys():
            # Skip exempt files
            if thresholds.is_exempt(file_path):
                continue

            file_thresholds = thresholds.get_file_thresholds(file_path)
            file_coverage = coverage_report.get_file_coverage(file_path)

            for metric, threshold in file_thresholds.items():
                actual = file_coverage.get(metric, 0.0)
                if actual < threshold:
                    errors.append(
                        f"{file_path} {metric}: {actual:.1f}% < {threshold:.1f}%"
                    )

        assert not errors, "File coverage thresholds not met:\n" + "\n".join(errors)

    def test_no_missing_coverage_files(self, coverage_report, thresholds):
        """Test that all explicitly listed files in thresholds have coverage data."""
        if not thresholds.strict:
            pytest.skip("Strict mode disabled, skipping missing file check")

        missing_files = []
        for file_path in thresholds.files.keys():
            if file_path not in coverage_report.files and file_path != "SUMMARY":
                missing_files.append(file_path)

        assert not missing_files, (
            f"Files listed in coverage_required.yaml but not found in report:\n"
            + "\n".join(missing_files)
        )


def main():
    """Main entry point for standalone execution."""
    print("=" * 70)
    print("Coverage Threshold Validation")
    print("=" * 70)

    # Run coverage analysis
    print("\n1. Running coverage analysis...")
    if not run_coverage_analysis():
        print("❌ Coverage analysis failed")
        return 1

    print("✅ Coverage analysis completed")

    # Load thresholds
    print("\n2. Loading coverage thresholds...")
    try:
        thresholds = load_thresholds()
        print(f"✅ Loaded thresholds from {COVERAGE_REQUIRED_YAML}")
    except Exception as e:
        print(f"❌ Failed to load thresholds: {e}")
        return 1

    # Load coverage report
    print("\n3. Loading coverage report...")
    try:
        report = CoverageReport(COVERAGE_CSV)
        print(f"✅ Loaded coverage data for {len(report.files)} files")
    except Exception as e:
        print(f"❌ Failed to load coverage report: {e}")
        return 1

    # Validate coverage
    print("\n4. Validating coverage thresholds...")
    all_passed, errors = validate_coverage(report, thresholds)

    if all_passed:
        print("✅ All coverage thresholds met!")
        print("\nSummary Coverage:")
        summary = report.get_summary_coverage()
        for metric, value in summary.items():
            threshold = thresholds.summary.get(metric, 0.0)
            status = "✅" if value >= threshold else "❌"
            print(f"  {status} {metric}: {value:.1f}% (required: {threshold:.1f}%)")
        return 0
    else:
        print("❌ Coverage thresholds not met!\n")
        print("Failures:")
        for error in errors:
            print(f"  ❌ {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
