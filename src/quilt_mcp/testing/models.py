"""Data models for MCP test infrastructure.

This module provides pure data containers with no external dependencies.
These models are used throughout the testing infrastructure to maintain
consistent structure and type safety.

Core Models
-----------
TestResults : class
    Tracks test execution results with consistent structure for tools,
    resources, and loops. Provides JSON serialization and summary statistics.

DiscoveryResult : dataclass
    Captures the result of tool discovery and validation, including
    execution time, success status, and any discovered data samples.

DiscoveredDataRegistry : class
    Registry for discovered data during test generation, including S3 keys,
    package names, table names, and other infrastructure resources.

Design Principles
-----------------
- Pure data containers with no business logic
- Immutable where possible (use dataclasses with frozen=True)
- Complete type hints for all fields
- JSON serialization support for reporting
- Clear documentation of field semantics

Usage Examples
--------------
Track test results across multiple categories:
    >>> results = TestResults()
    >>> results.record_pass({"tool": "bucket_list", "status": "passed"})
    >>> results.record_failure({"tool": "bucket_create", "error": "Permission denied"})
    >>> summary = results.to_dict()

Register discovered data for test generation:
    >>> registry = DiscoveredDataRegistry()
    >>> registry.add_s3_keys(["path/to/file.json"])
    >>> registry.add_package_names(["my-package"])
    >>> test_data = registry.to_dict()

Capture discovery execution results:
    >>> result = DiscoveryResult(
    ...     tool_name="bucket_list",
    ...     status="PASSED",
    ...     duration_ms=150.5,
    ...     discovered_data={"keys": ["file1.json", "file2.csv"]}
    ... )

Extracted From
--------------
- TestResults: lines 282-356 from scripts/mcp-test.py
- DiscoveryResult: lines 108-130 from scripts/mcp-test-setup.py
- DiscoveredDataRegistry: lines 132-165 from scripts/mcp-test-setup.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


class TestResults:
    """Tracks test results with consistent structure for all outcomes.

    Ensures that result dictionaries ALWAYS contain all required keys,
    fixing the bug where incomplete dictionaries cause print_detailed_summary() to fail.

    Attributes:
        total: Total number of tests executed
        passed: Number of tests that passed
        failed: Number of tests that failed
        skipped: Number of tests that were skipped
        passed_tests: List of test info dicts for passed tests
        failed_tests: List of test info dicts for failed tests
        skipped_tests: List of test info dicts for skipped tests

    Methods:
        record_pass: Record a successful test execution
        record_failure: Record a failed test execution
        record_skip: Record a skipped test
        is_success: Check if all tests passed (no failures)
        to_dict: Export results as complete dictionary structure
    """

    def __init__(self) -> None:
        """Initialize counters and lists to empty state."""
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.passed_tests: List[Dict[str, Any]] = []
        self.failed_tests: List[Dict[str, Any]] = []
        self.skipped_tests: List[Dict[str, Any]] = []

    def record_pass(self, test_info: Dict[str, Any]) -> None:
        """Record a successful test.

        Args:
            test_info: Dict with test details (input, output, metadata)
        """
        self.total += 1
        self.passed += 1
        self.passed_tests.append(test_info)

    def record_failure(self, test_info: Dict[str, Any]) -> None:
        """Record a failed test.

        Args:
            test_info: Dict with test details (input, partial output, error)
        """
        self.total += 1
        self.failed += 1
        self.failed_tests.append(test_info)

    def record_skip(self, test_info: Dict[str, Any]) -> None:
        """Record a skipped test.

        Args:
            test_info: Dict with test details (what was skipped, reason)
        """
        self.total += 1
        self.skipped += 1
        self.skipped_tests.append(test_info)

    def is_success(self) -> bool:
        """Check if all tests passed (no failures).

        Returns:
            True if no failures, False otherwise
        """
        return self.failed == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary with ALL required keys.

        This method guarantees that the returned dictionary always has
        the complete structure expected by print_detailed_summary().

        Returns:
            Dict with keys: total, passed, failed, skipped,
                           passed_tests, failed_tests, skipped_tests
        """
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "skipped_tests": self.skipped_tests,
        }


@dataclass
class DiscoveryResult:
    """Result of attempting to discover/validate a tool.

    This dataclass captures all information about tool discovery attempts,
    including execution status, timing, and any data discovered during execution.

    Attributes:
        tool_name: Name of the tool being discovered
        status: Execution status ('PASSED', 'FAILED', or 'SKIPPED')
        duration_ms: Execution time in milliseconds
        response: Tool response data (if successful)
        discovered_data: Data samples found during execution (S3 keys, packages, etc.)
        error: Error message (if failed)
        error_category: Classification of error (access_denied, timeout, etc.)
        timestamp: ISO format timestamp of discovery attempt

    Properties:
        success: Backward-compatible boolean check (status == 'PASSED')
    """

    tool_name: str
    status: Literal['PASSED', 'FAILED', 'SKIPPED']
    duration_ms: float

    # Successful execution (status='PASSED')
    response: Optional[Dict[str, Any]] = None
    discovered_data: Dict[str, Any] = field(default_factory=dict)

    # Failed execution (status='FAILED')
    error: Optional[str] = None
    error_category: Optional[str] = None  # access_denied, timeout, validation_error, etc.

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def success(self) -> bool:
        """Backward compatibility: success = (status == 'PASSED')"""
        return self.status == 'PASSED'


class DiscoveredDataRegistry:
    """Registry for data discovered during tool execution.

    This class maintains collections of infrastructure resources discovered
    during test setup, which can be used to generate realistic test cases.

    Attributes:
        s3_keys: List of discovered S3 object keys
        package_names: List of discovered Quilt package names
        tables: List of discovered table metadata dicts
        catalog_resources: List of discovered catalog resource dicts

    Methods:
        add_s3_keys: Register newly discovered S3 keys
        add_package_names: Register newly discovered package names
        add_tables: Register newly discovered tables
        add_catalog_resource: Register a catalog resource with its URI and type
        to_dict: Export registry as dictionary (limited to first 10 items per category)
    """

    def __init__(self) -> None:
        self.s3_keys: List[str] = []
        self.package_names: List[str] = []
        self.tables: List[Dict[str, str]] = []
        self.catalog_resources: List[Dict[str, str]] = []

    def add_s3_keys(self, keys: List[str]) -> None:
        """Add discovered S3 keys."""
        self.s3_keys.extend(keys)

    def add_package_names(self, names: List[str]) -> None:
        """Add discovered package names."""
        self.package_names.extend(names)

    def add_tables(self, tables: List[Dict[str, str]]) -> None:
        """Add discovered tables."""
        self.tables.extend(tables)

    def add_catalog_resource(self, uri: str, resource_type: str) -> None:
        """Add discovered catalog resource."""
        self.catalog_resources.append({"uri": uri, "type": resource_type})

    def to_dict(self) -> Dict[str, Any]:
        """Export registry as dictionary."""
        return {
            "s3_keys": self.s3_keys[:10],  # Limit to first 10
            "package_names": self.package_names[:10],
            "tables": self.tables[:10],
            "catalog_resources": self.catalog_resources[:10],
        }


__all__ = [
    "TestResults",
    "DiscoveryResult",
    "DiscoveredDataRegistry",
]
