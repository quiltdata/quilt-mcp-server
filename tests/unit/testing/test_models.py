"""Unit tests for MCP test infrastructure data models.

Tests cover:
- TestResults: Recording and aggregating test outcomes
- DiscoveryResult: Tool discovery result structure
- DiscoveredDataRegistry: Data registry for test generation
"""

import pytest
from datetime import datetime

from quilt_mcp.testing.models import (
    TestResults,
    DiscoveryResult,
    DiscoveredDataRegistry,
)


class TestTestResults:
    """Test suite for TestResults class."""

    def test_initial_state(self):
        """Verify initial state has all counters at zero."""
        results = TestResults()

        assert results.total == 0
        assert results.passed == 0
        assert results.failed == 0
        assert results.skipped == 0
        assert results.passed_tests == []
        assert results.failed_tests == []
        assert results.skipped_tests == []

    def test_record_pass(self):
        """Verify recording a successful test increments counters."""
        results = TestResults()
        test_info = {"tool": "bucket_list", "status": "passed"}

        results.record_pass(test_info)

        assert results.total == 1
        assert results.passed == 1
        assert results.failed == 0
        assert results.skipped == 0
        assert test_info in results.passed_tests
        assert len(results.passed_tests) == 1

    def test_record_failure(self):
        """Verify recording a failed test increments counters."""
        results = TestResults()
        test_info = {"tool": "bucket_create", "error": "Permission denied"}

        results.record_failure(test_info)

        assert results.total == 1
        assert results.passed == 0
        assert results.failed == 1
        assert results.skipped == 0
        assert test_info in results.failed_tests
        assert len(results.failed_tests) == 1

    def test_record_skip(self):
        """Verify recording a skipped test increments counters."""
        results = TestResults()
        test_info = {"tool": "admin_only_tool", "reason": "Missing permissions"}

        results.record_skip(test_info)

        assert results.total == 1
        assert results.passed == 0
        assert results.failed == 0
        assert results.skipped == 1
        assert test_info in results.skipped_tests
        assert len(results.skipped_tests) == 1

    def test_multiple_outcomes(self):
        """Verify multiple test outcomes are tracked correctly."""
        results = TestResults()

        results.record_pass({"tool": "tool1"})
        results.record_pass({"tool": "tool2"})
        results.record_failure({"tool": "tool3"})
        results.record_skip({"tool": "tool4"})

        assert results.total == 4
        assert results.passed == 2
        assert results.failed == 1
        assert results.skipped == 1

    def test_is_success_with_no_failures(self):
        """Verify is_success returns True when no failures."""
        results = TestResults()

        results.record_pass({"tool": "tool1"})
        results.record_pass({"tool": "tool2"})
        results.record_skip({"tool": "tool3"})

        assert results.is_success() is True

    def test_is_success_with_failures(self):
        """Verify is_success returns False when there are failures."""
        results = TestResults()

        results.record_pass({"tool": "tool1"})
        results.record_failure({"tool": "tool2"})

        assert results.is_success() is False

    def test_is_success_with_only_skipped(self):
        """Verify is_success returns True when only skipped tests."""
        results = TestResults()

        results.record_skip({"tool": "tool1"})
        results.record_skip({"tool": "tool2"})

        assert results.is_success() is True

    def test_to_dict_contains_all_keys(self):
        """Verify to_dict() always returns complete structure."""
        results = TestResults()
        result_dict = results.to_dict()

        # Verify all required keys are present
        required_keys = {"total", "passed", "failed", "skipped", "passed_tests", "failed_tests", "skipped_tests"}
        assert set(result_dict.keys()) == required_keys

    def test_to_dict_with_empty_results(self):
        """Verify to_dict() works with no test results."""
        results = TestResults()
        result_dict = results.to_dict()

        assert result_dict["total"] == 0
        assert result_dict["passed"] == 0
        assert result_dict["failed"] == 0
        assert result_dict["skipped"] == 0
        assert result_dict["passed_tests"] == []
        assert result_dict["failed_tests"] == []
        assert result_dict["skipped_tests"] == []

    def test_to_dict_with_populated_results(self):
        """Verify to_dict() accurately reflects recorded tests."""
        results = TestResults()

        pass_info = {"tool": "pass_tool"}
        fail_info = {"tool": "fail_tool"}
        skip_info = {"tool": "skip_tool"}

        results.record_pass(pass_info)
        results.record_failure(fail_info)
        results.record_skip(skip_info)

        result_dict = results.to_dict()

        assert result_dict["total"] == 3
        assert result_dict["passed"] == 1
        assert result_dict["failed"] == 1
        assert result_dict["skipped"] == 1
        assert pass_info in result_dict["passed_tests"]
        assert fail_info in result_dict["failed_tests"]
        assert skip_info in result_dict["skipped_tests"]

    def test_test_info_immutability(self):
        """Verify that test_info dicts are stored by reference correctly."""
        results = TestResults()
        test_info = {"tool": "test_tool", "data": "test_data"}

        results.record_pass(test_info)

        # Modify original dict
        test_info["data"] = "modified_data"

        # Verify stored reference reflects change (Python dict behavior)
        assert results.passed_tests[0]["data"] == "modified_data"


class TestDiscoveryResult:
    """Test suite for DiscoveryResult dataclass."""

    def test_minimal_passed_result(self):
        """Verify minimal successful discovery result."""
        result = DiscoveryResult(tool_name="bucket_list", status="PASSED", duration_ms=150.5)

        assert result.tool_name == "bucket_list"
        assert result.status == "PASSED"
        assert result.duration_ms == 150.5
        assert result.response is None
        assert result.discovered_data == {}
        assert result.error is None
        assert result.error_category is None

    def test_passed_result_with_data(self):
        """Verify successful result with response and discovered data."""
        response_data = {"keys": ["file1.json", "file2.csv"]}
        discovered = {"s3_keys": ["key1", "key2"]}

        result = DiscoveryResult(
            tool_name="bucket_objects_list",
            status="PASSED",
            duration_ms=250.0,
            response=response_data,
            discovered_data=discovered,
        )

        assert result.response == response_data
        assert result.discovered_data == discovered
        assert result.success is True

    def test_failed_result(self):
        """Verify failed discovery result with error details."""
        result = DiscoveryResult(
            tool_name="admin_tool",
            status="FAILED",
            duration_ms=50.0,
            error="Access denied",
            error_category="access_denied",
        )

        assert result.status == "FAILED"
        assert result.error == "Access denied"
        assert result.error_category == "access_denied"
        assert result.success is False

    def test_skipped_result(self):
        """Verify skipped discovery result."""
        result = DiscoveryResult(tool_name="optional_tool", status="SKIPPED", duration_ms=0.0)

        assert result.status == "SKIPPED"
        assert result.success is False

    def test_timestamp_auto_generation(self):
        """Verify timestamp is automatically generated."""
        result = DiscoveryResult(tool_name="test_tool", status="PASSED", duration_ms=100.0)

        # Verify timestamp exists and is ISO format
        assert result.timestamp is not None
        # Should be parseable as datetime
        datetime.fromisoformat(result.timestamp)

    def test_success_property(self):
        """Verify success property correctly reflects status."""
        passed = DiscoveryResult("tool1", "PASSED", 100.0)
        failed = DiscoveryResult("tool2", "FAILED", 100.0)
        skipped = DiscoveryResult("tool3", "SKIPPED", 0.0)

        assert passed.success is True
        assert failed.success is False
        assert skipped.success is False

    def test_default_factory_for_discovered_data(self):
        """Verify discovered_data uses default factory correctly."""
        result1 = DiscoveryResult("tool1", "PASSED", 100.0)
        result2 = DiscoveryResult("tool2", "PASSED", 100.0)

        # Add data to one result
        result1.discovered_data["test"] = "data"

        # Verify other result's data is independent
        assert "test" not in result2.discovered_data
        assert result2.discovered_data == {}

    def test_error_categories(self):
        """Verify various error categories can be recorded."""
        categories = ["access_denied", "timeout", "validation_error", "network_error"]

        for category in categories:
            result = DiscoveryResult(
                tool_name="test_tool", status="FAILED", duration_ms=100.0, error_category=category
            )
            assert result.error_category == category


class TestDiscoveredDataRegistry:
    """Test suite for DiscoveredDataRegistry class."""

    def test_initial_state(self):
        """Verify initial state has all lists empty."""
        registry = DiscoveredDataRegistry()

        assert registry.s3_keys == []
        assert registry.package_names == []
        assert registry.tables == []
        assert registry.catalog_resources == []

    def test_add_s3_keys(self):
        """Verify S3 keys can be added to registry."""
        registry = DiscoveredDataRegistry()
        keys = ["path/to/file1.json", "path/to/file2.csv"]

        registry.add_s3_keys(keys)

        assert registry.s3_keys == keys
        assert len(registry.s3_keys) == 2

    def test_add_s3_keys_multiple_times(self):
        """Verify S3 keys accumulate across multiple additions."""
        registry = DiscoveredDataRegistry()

        registry.add_s3_keys(["key1", "key2"])
        registry.add_s3_keys(["key3", "key4"])

        assert registry.s3_keys == ["key1", "key2", "key3", "key4"]

    def test_add_package_names(self):
        """Verify package names can be added to registry."""
        registry = DiscoveredDataRegistry()
        packages = ["my-package", "test-package"]

        registry.add_package_names(packages)

        assert registry.package_names == packages
        assert len(registry.package_names) == 2

    def test_add_package_names_multiple_times(self):
        """Verify package names accumulate across multiple additions."""
        registry = DiscoveredDataRegistry()

        registry.add_package_names(["package1"])
        registry.add_package_names(["package2", "package3"])

        assert registry.package_names == ["package1", "package2", "package3"]

    def test_add_tables(self):
        """Verify tables can be added to registry."""
        registry = DiscoveredDataRegistry()
        tables = [{"database": "db1", "name": "table1"}, {"database": "db2", "name": "table2"}]

        registry.add_tables(tables)

        assert registry.tables == tables
        assert len(registry.tables) == 2

    def test_add_tables_multiple_times(self):
        """Verify tables accumulate across multiple additions."""
        registry = DiscoveredDataRegistry()

        registry.add_tables([{"database": "db1", "name": "table1"}])
        registry.add_tables([{"database": "db2", "name": "table2"}])

        assert len(registry.tables) == 2

    def test_add_catalog_resource(self):
        """Verify catalog resources can be added to registry."""
        registry = DiscoveredDataRegistry()

        registry.add_catalog_resource(uri="s3://bucket/package", resource_type="package")

        assert len(registry.catalog_resources) == 1
        assert registry.catalog_resources[0]["uri"] == "s3://bucket/package"
        assert registry.catalog_resources[0]["type"] == "package"

    def test_add_catalog_resource_multiple_times(self):
        """Verify catalog resources accumulate."""
        registry = DiscoveredDataRegistry()

        registry.add_catalog_resource("uri1", "type1")
        registry.add_catalog_resource("uri2", "type2")

        assert len(registry.catalog_resources) == 2

    def test_to_dict_with_empty_registry(self):
        """Verify to_dict() works with empty registry."""
        registry = DiscoveredDataRegistry()
        result = registry.to_dict()

        assert result == {
            "s3_keys": [],
            "package_names": [],
            "tables": [],
            "catalog_resources": [],
        }

    def test_to_dict_with_populated_registry(self):
        """Verify to_dict() returns all data types."""
        registry = DiscoveredDataRegistry()

        registry.add_s3_keys(["key1", "key2"])
        registry.add_package_names(["package1"])
        registry.add_tables([{"database": "db1", "name": "table1"}])
        registry.add_catalog_resource("uri1", "type1")

        result = registry.to_dict()

        assert result["s3_keys"] == ["key1", "key2"]
        assert result["package_names"] == ["package1"]
        assert result["tables"] == [{"database": "db1", "name": "table1"}]
        assert result["catalog_resources"] == [{"uri": "uri1", "type": "type1"}]

    def test_to_dict_limits_to_first_10_items(self):
        """Verify to_dict() limits each category to first 10 items."""
        registry = DiscoveredDataRegistry()

        # Add 15 items of each type
        registry.add_s3_keys([f"key{i}" for i in range(15)])
        registry.add_package_names([f"package{i}" for i in range(15)])
        registry.add_tables([{"name": f"table{i}"} for i in range(15)])
        for i in range(15):
            registry.add_catalog_resource(f"uri{i}", f"type{i}")

        result = registry.to_dict()

        # Verify each is limited to 10
        assert len(result["s3_keys"]) == 10
        assert len(result["package_names"]) == 10
        assert len(result["tables"]) == 10
        assert len(result["catalog_resources"]) == 10

        # Verify it's the first 10
        assert result["s3_keys"] == [f"key{i}" for i in range(10)]
        assert result["package_names"] == [f"package{i}" for i in range(10)]

    def test_to_dict_preserves_original_data(self):
        """Verify to_dict() doesn't modify the original data."""
        registry = DiscoveredDataRegistry()

        original_keys = ["key1", "key2", "key3"]
        registry.add_s3_keys(original_keys)

        result = registry.to_dict()

        # Modify the returned dict
        result["s3_keys"].append("key4")

        # Verify original registry is unchanged
        assert registry.s3_keys == original_keys
        assert len(registry.s3_keys) == 3

    def test_mixed_operations(self):
        """Verify registry works correctly with mixed operations."""
        registry = DiscoveredDataRegistry()

        # Add data in various orders
        registry.add_package_names(["pkg1"])
        registry.add_s3_keys(["key1"])
        registry.add_catalog_resource("uri1", "type1")
        registry.add_tables([{"name": "table1"}])
        registry.add_package_names(["pkg2"])
        registry.add_s3_keys(["key2"])

        # Verify all data is retained in order
        assert registry.s3_keys == ["key1", "key2"]
        assert registry.package_names == ["pkg1", "pkg2"]
        assert len(registry.tables) == 1
        assert len(registry.catalog_resources) == 1


class TestModelIntegration:
    """Integration tests across multiple models."""

    def test_discovery_result_to_registry_workflow(self):
        """Verify workflow from discovery results to registry."""
        # Create discovery result with discovered data
        result = DiscoveryResult(
            tool_name="bucket_objects_list",
            status="PASSED",
            duration_ms=200.0,
            discovered_data={"s3_keys": ["file1.json", "file2.csv"], "packages": ["my-package"]},
        )

        # Populate registry from discovery result
        registry = DiscoveredDataRegistry()
        if result.success and "s3_keys" in result.discovered_data:
            registry.add_s3_keys(result.discovered_data["s3_keys"])
        if result.success and "packages" in result.discovered_data:
            registry.add_package_names(result.discovered_data["packages"])

        # Verify registry is populated
        assert registry.s3_keys == ["file1.json", "file2.csv"]
        assert registry.package_names == ["my-package"]

    def test_test_results_with_discovery_info(self):
        """Verify TestResults can store discovery result info."""
        results = TestResults()

        # Create a discovery result
        discovery = DiscoveryResult(tool_name="test_tool", status="PASSED", duration_ms=150.0)

        # Record in test results
        test_info = {"tool": discovery.tool_name, "status": discovery.status, "duration_ms": discovery.duration_ms}
        results.record_pass(test_info)

        # Verify data is preserved
        assert results.passed == 1
        assert results.passed_tests[0]["tool"] == "test_tool"
        assert results.passed_tests[0]["duration_ms"] == 150.0
