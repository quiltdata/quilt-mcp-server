"""Unit tests for quilt_mcp.testing.validators module.

Tests validation logic, failure analysis, search validation, and coverage checks.
"""

import json
import pytest
from typing import Any, Dict, List

from quilt_mcp.testing.validators import (
    ResourceFailureType,
    SearchValidator,
    analyze_failure_patterns,
    classify_resource_failure,
    validate_loop_coverage,
    validate_test_coverage,
)


class TestResourceFailureType:
    """Test ResourceFailureType enum."""

    def test_enum_values(self):
        """Test that all enum values are defined."""
        assert ResourceFailureType.TEMPLATE_NOT_REGISTERED.value == "template_not_registered"
        assert ResourceFailureType.URI_NOT_FOUND.value == "uri_not_found"
        assert ResourceFailureType.CONTENT_VALIDATION.value == "content_validation"
        assert ResourceFailureType.SERVER_ERROR.value == "server_error"
        assert ResourceFailureType.CONFIG_ERROR.value == "config_error"


class TestClassifyResourceFailure:
    """Test classify_resource_failure function."""

    def test_classify_template_not_registered(self):
        """Test classification of template not registered errors."""
        test_info = {"name": "bucket://catalog", "error": "Template not found in server resourceTemplates: bucket"}
        result = classify_resource_failure(test_info)
        assert result == ResourceFailureType.TEMPLATE_NOT_REGISTERED

    def test_classify_uri_not_found(self):
        """Test classification of URI not found errors."""
        test_info = {"name": "invalid://uri", "error": "Resource not found in server resources: invalid://uri"}
        result = classify_resource_failure(test_info)
        assert result == ResourceFailureType.URI_NOT_FOUND

    def test_classify_content_validation(self):
        """Test classification of content validation errors."""
        test_info = {"name": "test_resource", "error": "Content validation failed: missing required field"}
        result = classify_resource_failure(test_info)
        assert result == ResourceFailureType.CONTENT_VALIDATION

    def test_classify_config_error(self):
        """Test classification of configuration errors."""
        test_info = {"name": "test_resource", "error": "Configuration issue", "error_type": "ConfigurationError"}
        result = classify_resource_failure(test_info)
        assert result == ResourceFailureType.CONFIG_ERROR

    def test_classify_server_error(self):
        """Test classification of generic server errors."""
        test_info = {"name": "test_resource", "error": "Internal server error: unexpected exception"}
        result = classify_resource_failure(test_info)
        assert result == ResourceFailureType.SERVER_ERROR

    def test_classify_with_empty_error(self):
        """Test classification with empty error message."""
        test_info = {"name": "test_resource", "error": ""}
        result = classify_resource_failure(test_info)
        assert result == ResourceFailureType.SERVER_ERROR


class TestAnalyzeFailurePatterns:
    """Test analyze_failure_patterns function."""

    def test_analyze_empty_failures(self):
        """Test analysis with no failures."""
        result = analyze_failure_patterns([])
        assert result["severity"] == "info"
        assert result["recommendations"] == []

    def test_analyze_all_template_not_registered(self):
        """Test analysis when all failures are template not registered."""
        failed_tests = [
            {"name": "bucket", "error": "Template not found in server resourceTemplates"},
            {"name": "package", "error": "Template not found in server resourceTemplates"},
            {"name": "user", "error": "Template not found in server resourceTemplates"},
        ]
        result = analyze_failure_patterns(failed_tests)

        assert result["dominant_pattern"] == ResourceFailureType.TEMPLATE_NOT_REGISTERED
        assert result["pattern_count"] == 3
        assert result["total_failures"] == 3
        assert result["severity"] == "warning"
        assert len(result["recommendations"]) == 4
        assert "✅ Static resources all work" in result["recommendations"][0]

    def test_analyze_partial_template_not_registered(self):
        """Test analysis when some failures are template not registered."""
        failed_tests = [
            {"name": "bucket", "error": "Template not found in server resourceTemplates"},
            {"name": "package", "error": "Internal server error"},
        ]
        result = analyze_failure_patterns(failed_tests)

        assert result["dominant_pattern"] == ResourceFailureType.TEMPLATE_NOT_REGISTERED
        assert result["pattern_count"] == 1
        assert result["total_failures"] == 2
        assert result["severity"] == "warning"

    def test_analyze_server_errors(self):
        """Test analysis when failures are server errors."""
        failed_tests = [
            {"name": "test1", "error": "Internal server error"},
            {"name": "test2", "error": "Unexpected exception"},
        ]
        result = analyze_failure_patterns(failed_tests)

        assert result["dominant_pattern"] == ResourceFailureType.SERVER_ERROR
        assert result["pattern_count"] == 2
        assert result["total_failures"] == 2
        assert result["severity"] == "critical"
        assert "❌ Server errors detected" in result["recommendations"][0]


class TestSearchValidator:
    """Test SearchValidator class."""

    def test_validator_initialization(self):
        """Test validator initialization."""
        config = {"type": "search", "min_results": 1}
        env_vars = {"TEST_BUCKET": "my-bucket"}
        validator = SearchValidator(config, env_vars)

        assert validator.config == config
        assert validator.env_vars == env_vars

    def test_validate_unknown_type(self):
        """Test validation with unknown type (should skip)."""
        config = {"type": "unknown"}
        validator = SearchValidator(config, {})

        result = {"some": "data"}
        is_valid, error = validator.validate(result)

        assert is_valid is True
        assert error is None

    def test_validate_search_direct_dict_format(self):
        """Test validation with direct dict format."""
        config = {"type": "search", "min_results": 1}
        validator = SearchValidator(config, {})

        result = {
            "success": True,
            "results": [
                {"name": "file1.json", "logical_key": "data/file1.json"},
                {"name": "file2.csv", "logical_key": "data/file2.csv"},
            ],
        }
        is_valid, error = validator.validate(result)

        assert is_valid is True
        assert error is None

    def test_validate_search_mcp_wrapped_format(self):
        """Test validation with MCP-wrapped format."""
        config = {"type": "search", "min_results": 1}
        validator = SearchValidator(config, {})

        search_data = {"success": True, "results": [{"name": "file1.json", "logical_key": "data/file1.json"}]}
        result = {"content": [{"type": "text", "text": json.dumps(search_data)}]}
        is_valid, error = validator.validate(result)

        assert is_valid is True
        assert error is None

    def test_validate_search_no_results_found(self):
        """Test validation when no results found in response."""
        config = {"type": "search"}
        validator = SearchValidator(config, {})

        result = {"some": "data"}  # No "results" key
        is_valid, error = validator.validate(result)

        assert is_valid is False
        assert "No search results found" in error

    def test_validate_search_min_results_not_met(self):
        """Test validation when minimum results not met."""
        config = {"type": "search", "min_results": 5}
        validator = SearchValidator(config, {})

        result = {
            "results": [
                {"name": "file1.json"},
                {"name": "file2.json"},
            ]
        }
        is_valid, error = validator.validate(result)

        assert is_valid is False
        assert "Expected at least 5 results, got 2" in error

    def test_validate_search_must_contain_substring(self):
        """Test validation with must_contain substring matching."""
        config = {
            "type": "search",
            "must_contain": [
                {"field": "name", "value": ".json", "match_type": "substring", "description": "Must find JSON file"}
            ],
        }
        validator = SearchValidator(config, {})

        result = {
            "results": [
                {"name": "file1.json", "size": 1024},
                {"name": "file2.csv", "size": 2048},
            ]
        }
        is_valid, error = validator.validate(result)

        assert is_valid is True
        assert error is None

    def test_validate_search_must_contain_not_found(self):
        """Test validation when must_contain pattern not found."""
        config = {
            "type": "search",
            "must_contain": [
                {
                    "field": "name",
                    "value": ".parquet",
                    "match_type": "substring",
                    "description": "Must find Parquet file",
                }
            ],
        }
        validator = SearchValidator(config, {})

        result = {
            "results": [
                {"name": "file1.json"},
                {"name": "file2.csv"},
            ]
        }
        is_valid, error = validator.validate(result)

        assert is_valid is False
        assert "Must find Parquet file" in error
        assert ".parquet" in error
        assert "name" in error

    def test_validate_search_must_contain_exact(self):
        """Test validation with must_contain exact matching."""
        config = {"type": "search", "must_contain": [{"field": "name", "value": "README.md", "match_type": "exact"}]}
        validator = SearchValidator(config, {})

        result = {
            "results": [
                {"name": "README.md"},
                {"name": "readme.md"},
            ]
        }
        is_valid, error = validator.validate(result)

        assert is_valid is True
        assert error is None

    def test_validate_search_must_contain_regex(self):
        """Test validation with must_contain regex matching."""
        config = {
            "type": "search",
            "must_contain": [{"field": "name", "value": r"file\d+\.json", "match_type": "regex"}],
        }
        validator = SearchValidator(config, {})

        result = {
            "results": [
                {"name": "file1.json"},
                {"name": "data.csv"},
            ]
        }
        is_valid, error = validator.validate(result)

        assert is_valid is True
        assert error is None

    def test_validate_search_result_shape_valid(self):
        """Test validation with result shape - all required fields present."""
        config = {"type": "search", "result_shape": {"required_fields": ["name", "logical_key", "size"]}}
        validator = SearchValidator(config, {})

        result = {
            "results": [
                {"name": "file1.json", "logical_key": "data/file1.json", "size": 1024},
                {"name": "file2.json", "logical_key": "data/file2.json", "size": 2048},
            ]
        }
        is_valid, error = validator.validate(result)

        assert is_valid is True
        assert error is None

    def test_validate_search_result_shape_missing_fields(self):
        """Test validation with result shape - missing required fields."""
        config = {"type": "search", "result_shape": {"required_fields": ["name", "logical_key", "size"]}}
        validator = SearchValidator(config, {})

        result = {
            "results": [
                {"name": "file1.json", "logical_key": "data/file1.json"},  # Missing 'size'
            ]
        }
        is_valid, error = validator.validate(result)

        assert is_valid is False
        assert "missing required fields" in error
        assert "size" in error

    def test_validate_search_empty_results_with_shape(self):
        """Test validation with empty results and result shape (should pass)."""
        config = {"type": "search", "result_shape": {"required_fields": ["name", "logical_key"]}}
        validator = SearchValidator(config, {})

        result = {"results": []}
        is_valid, error = validator.validate(result)

        assert is_valid is True
        assert error is None


class TestValidateTestCoverage:
    """Test validate_test_coverage function."""

    def test_validate_coverage_complete(self):
        """Test validation with complete coverage."""
        server_tools = [
            {"name": "bucket_list", "description": "List buckets"},
            {"name": "package_list", "description": "List packages"},
        ]
        config_tools = {
            "bucket_list": {"args": {}},
            "package_list": {"args": {}},
        }

        # Should not raise
        validate_test_coverage(server_tools, config_tools)

    def test_validate_coverage_with_variants(self):
        """Test validation with tool variants."""
        server_tools = [
            {"name": "search_catalog", "description": "Search catalog"},
        ]
        config_tools = {
            "search_catalog.basic": {"tool": "search_catalog", "args": {"query": "test"}},
            "search_catalog.advanced": {"tool": "search_catalog", "args": {"query": "test", "limit": 10}},
        }

        # Should not raise (variants cover the base tool)
        validate_test_coverage(server_tools, config_tools)

    def test_validate_coverage_missing_tools(self):
        """Test validation with missing tool coverage."""
        server_tools = [
            {"name": "bucket_list", "description": "List buckets"},
            {"name": "package_create", "description": "Create package"},
            {"name": "user_add", "description": "Add user"},
        ]
        config_tools = {
            "bucket_list": {"args": {}},
        }

        with pytest.raises(ValueError) as exc_info:
            validate_test_coverage(server_tools, config_tools)

        error_msg = str(exc_info.value)
        assert "2 tool(s) on server are NOT covered" in error_msg
        assert "package_create" in error_msg
        assert "user_add" in error_msg
        assert "uv run scripts/mcp-test-setup.py" in error_msg

    def test_validate_coverage_empty_config(self):
        """Test validation with empty config."""
        server_tools = [
            {"name": "bucket_list", "description": "List buckets"},
        ]
        config_tools = {}

        with pytest.raises(ValueError) as exc_info:
            validate_test_coverage(server_tools, config_tools)

        error_msg = str(exc_info.value)
        assert "1 tool(s) on server are NOT covered" in error_msg
        assert "bucket_list" in error_msg


class TestValidateLoopCoverage:
    """Test validate_loop_coverage function."""

    def test_validate_loop_coverage_complete(self):
        """Test validation with complete coverage."""
        server_tools = [
            {"name": "bucket_create", "description": "Create bucket"},
            {"name": "bucket_delete", "description": "Delete bucket"},
            {"name": "package_list", "description": "List packages"},
        ]
        tool_loops = {
            "bucket_lifecycle": {
                "steps": [
                    {"tool": "bucket_create", "args": {"name": "test-bucket"}},
                    {"tool": "bucket_delete", "args": {"name": "test-bucket"}},
                ]
            }
        }
        standalone_tools = {
            "package_list": {"args": {}},
        }

        is_complete, uncovered = validate_loop_coverage(server_tools, tool_loops, standalone_tools)

        assert is_complete is True
        assert uncovered == []

    def test_validate_loop_coverage_missing_tools(self):
        """Test validation with missing tool coverage."""
        server_tools = [
            {"name": "bucket_create", "description": "Create bucket"},
            {"name": "bucket_delete", "description": "Delete bucket"},
            {"name": "package_create", "description": "Create package"},
            {"name": "user_add", "description": "Add user"},
        ]
        tool_loops = {
            "bucket_lifecycle": {
                "steps": [
                    {"tool": "bucket_create", "args": {"name": "test-bucket"}},
                ]
            }
        }
        standalone_tools = {}

        is_complete, uncovered = validate_loop_coverage(server_tools, tool_loops, standalone_tools)

        assert is_complete is False
        assert set(uncovered) == {"bucket_delete", "package_create", "user_add"}

    def test_validate_loop_coverage_with_variants(self):
        """Test validation with standalone tool variants."""
        server_tools = [
            {"name": "search_catalog", "description": "Search catalog"},
        ]
        tool_loops = {}
        standalone_tools = {
            "search_catalog.basic": {"tool": "search_catalog", "args": {"query": "test"}},
        }

        is_complete, uncovered = validate_loop_coverage(server_tools, tool_loops, standalone_tools)

        assert is_complete is True
        assert uncovered == []

    def test_validate_loop_coverage_empty_config(self):
        """Test validation with empty loops and standalone tools."""
        server_tools = [
            {"name": "bucket_list", "description": "List buckets"},
        ]
        tool_loops = {}
        standalone_tools = {}

        is_complete, uncovered = validate_loop_coverage(server_tools, tool_loops, standalone_tools)

        assert is_complete is False
        assert uncovered == ["bucket_list"]

    def test_validate_loop_coverage_sorted_output(self):
        """Test that uncovered tools are returned in sorted order."""
        server_tools = [
            {"name": "zebra_tool", "description": "Zebra"},
            {"name": "alpha_tool", "description": "Alpha"},
            {"name": "beta_tool", "description": "Beta"},
        ]
        tool_loops = {}
        standalone_tools = {}

        is_complete, uncovered = validate_loop_coverage(server_tools, tool_loops, standalone_tools)

        assert is_complete is False
        assert uncovered == ["alpha_tool", "beta_tool", "zebra_tool"]
