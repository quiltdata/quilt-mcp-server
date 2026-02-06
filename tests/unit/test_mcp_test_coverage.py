"""Unit tests for test coverage validation in mcp-test.py.

Tests the validate_test_coverage() function that ensures all server tools
are covered by the test configuration.
"""

import importlib.util
import pytest
from pathlib import Path

# Load mcp-test.py module dynamically (can't use regular import due to hyphen)
scripts_dir = Path(__file__).parent.parent.parent / "scripts"
mcp_test_path = scripts_dir / "mcp-test.py"

spec = importlib.util.spec_from_file_location("mcp_test", mcp_test_path)
assert spec and spec.loader, "Failed to load mcp-test.py module spec"

mcp_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp_test)

# Import the function we need
validate_test_coverage = mcp_test.validate_test_coverage


class TestValidateTestCoverage:
    """Test suite for validate_test_coverage() function."""

    def test_all_tools_covered_success(self):
        """Test passes when all server tools are in config."""
        server_tools = [{"name": "bucket_objects_list"}, {"name": "package_browse"}, {"name": "search_catalog"}]

        config_tools = {
            "bucket_objects_list": {"effect": "none", "arguments": {}},
            "package_browse": {"effect": "none", "arguments": {}},
            "search_catalog": {"effect": "none", "arguments": {}},
        }

        # Should not raise
        validate_test_coverage(server_tools, config_tools)

    def test_tool_variants_covered_success(self):
        """Test passes when tool variants properly reference base tool."""
        server_tools = [{"name": "search_catalog"}, {"name": "bucket_objects_list"}]

        # Config has variants of search_catalog
        config_tools = {
            "search_catalog.file.no_bucket": {
                "tool": "search_catalog",  # References actual tool
                "effect": "none",
                "arguments": {"scope": "file"},
            },
            "search_catalog.package.with_bucket": {
                "tool": "search_catalog",
                "effect": "none",
                "arguments": {"scope": "package", "bucket": "test"},
            },
            "bucket_objects_list": {"effect": "none", "arguments": {}},
        }

        # Should not raise - variants correctly map to base tool
        validate_test_coverage(server_tools, config_tools)

    def test_uncovered_tool_raises_error(self):
        """Test raises ValueError when server has tool not in config."""
        server_tools = [
            {"name": "bucket_objects_list"},
            {"name": "package_browse"},
            {"name": "new_tool_not_in_config"},  # Missing from config!
        ]

        config_tools = {
            "bucket_objects_list": {"effect": "none"},
            "package_browse": {"effect": "none"},
            # "new_tool_not_in_config" is missing!
        }

        with pytest.raises(ValueError) as exc_info:
            validate_test_coverage(server_tools, config_tools)

        error_msg = str(exc_info.value)
        assert "new_tool_not_in_config" in error_msg
        assert "uv run scripts/mcp-test-setup.py" in error_msg
        assert "NOT covered by test config" in error_msg

    def test_multiple_uncovered_tools_all_listed(self):
        """Test error message lists all uncovered tools."""
        server_tools = [
            {"name": "tool_a"},
            {"name": "tool_b"},
            {"name": "tool_c"},
            {"name": "uncovered_1"},
            {"name": "uncovered_2"},
        ]

        config_tools = {"tool_a": {}, "tool_b": {}, "tool_c": {}}

        with pytest.raises(ValueError) as exc_info:
            validate_test_coverage(server_tools, config_tools)

        error_msg = str(exc_info.value)
        assert "uncovered_1" in error_msg
        assert "uncovered_2" in error_msg
        assert "2 tool(s) on server are NOT covered" in error_msg

    def test_empty_server_tools_success(self):
        """Test passes when server has no tools (edge case)."""
        server_tools = []
        config_tools = {}

        # Should not raise
        validate_test_coverage(server_tools, config_tools)

    def test_extra_config_tools_allowed(self):
        """Test allows config to have more tools than server (deprecated tools)."""
        server_tools = [{"name": "active_tool"}]

        config_tools = {
            "active_tool": {"effect": "none"},
            "deprecated_tool": {"effect": "none"},  # Not on server anymore
            "old_tool": {"effect": "none"},
        }

        # Should not raise - extra config entries are allowed
        # (tools may be removed from server but still in config)
        validate_test_coverage(server_tools, config_tools)

    def test_mixed_variants_and_regular_tools(self):
        """Test correctly handles mix of regular tools and variants."""
        server_tools = [{"name": "simple_tool"}, {"name": "search_catalog"}, {"name": "another_tool"}]

        config_tools = {
            "simple_tool": {"effect": "none"},
            "search_catalog.variant_1": {"tool": "search_catalog", "effect": "none"},
            "search_catalog.variant_2": {"tool": "search_catalog", "effect": "none"},
            "another_tool": {"effect": "none"},
        }

        # Should not raise
        validate_test_coverage(server_tools, config_tools)

    def test_error_message_has_helpful_instructions(self):
        """Test error message includes actionable remediation steps."""
        server_tools = [{"name": "uncovered_tool"}]
        config_tools = {}

        with pytest.raises(ValueError) as exc_info:
            validate_test_coverage(server_tools, config_tools)

        error_msg = str(exc_info.value)

        # Check for key components of helpful error message
        assert "uv run scripts/mcp-test-setup.py" in error_msg
        assert "Action Required" in error_msg
        assert "Why This Matters" in error_msg
        assert "Coverage Summary" in error_msg
        assert "regenerates scripts/tests/mcp-test.yaml" in error_msg
