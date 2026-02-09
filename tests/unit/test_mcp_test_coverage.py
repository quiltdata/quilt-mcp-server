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


class TestToolsTesterWriteEffectSkipping:
    """Test suite for write-effect tool skipping in ToolsTester.run_all_tests()."""

    def test_write_effect_tools_are_skipped(self):
        """Verify write-effect tools are not tested in standalone mode."""
        from unittest.mock import MagicMock, patch

        config = {
            "test_tools": {
                "bucket_objects_list": {"effect": "none", "category": "optional-arg"},
                "admin_user_create": {"effect": "create", "category": "write-effect"},
                "package_update": {"effect": "update", "category": "write-effect"},
                "admin_role_remove": {"effect": "remove", "category": "write-effect"},
            }
        }

        # Create ToolsTester instance (MCPTester parent requires endpoint for HTTP transport)
        tester = mcp_test.ToolsTester(config=config, endpoint="http://test:8080", transport="http")

        # Mock the call_tool method to return success
        tester.call_tool = MagicMock(return_value={"content": [{"type": "text", "text": "success"}], "isError": False})

        # Run all tests
        with patch('builtins.print'):  # Suppress output
            tester.run_all_tests()

        # Only non-write tools should be tested (1 tool: bucket_objects_list)
        # Write-effect tools should be skipped (3 tools)
        assert len(tester.results.skipped_tests) == 3
        assert tester.results.skipped == 3

        # Verify skip reasons contain write-effect information
        skip_reasons = [s["reason"] for s in tester.results.skipped_tests]
        assert all("write-effect" in reason.lower() for reason in skip_reasons)

        # Verify skipped tool names
        skipped_names = {s["name"] for s in tester.results.skipped_tests}
        assert skipped_names == {"admin_user_create", "package_update", "admin_role_remove"}

    def test_effect_types_correctly_classified(self):
        """Test that different effect types are correctly classified for skipping."""
        from unittest.mock import MagicMock, patch

        config = {
            "test_tools": {
                "tool_none": {"effect": "none", "category": "read-only"},
                "tool_create": {"effect": "create", "category": "write-effect"},
                "tool_update": {"effect": "update", "category": "write-effect"},
                "tool_remove": {"effect": "remove", "category": "write-effect"},
                "tool_configure": {"effect": "configure", "category": "config"},
            }
        }

        tester = mcp_test.ToolsTester(config=config, endpoint="http://test:8080", transport="http")
        tester.call_tool = MagicMock(return_value={"content": [{"type": "text", "text": "success"}], "isError": False})

        with patch('builtins.print'):
            tester.run_all_tests()

        # create/update/remove should be skipped (3 tools)
        assert tester.results.skipped == 3

        # none and configure should be tested (2 tools)
        # They may pass or fail, but they should be attempted
        assert tester.results.total >= 2

        # Verify the right tools were skipped
        skipped_names = {s["name"] for s in tester.results.skipped_tests}
        assert skipped_names == {"tool_create", "tool_update", "tool_remove"}

    def test_category_based_skipping(self):
        """Test that category='write-effect' triggers skipping even without explicit effect."""
        from unittest.mock import MagicMock, patch

        config = {
            "test_tools": {
                "normal_tool": {"effect": "none", "category": "optional-arg"},
                "write_tool_by_category": {"category": "write-effect"},  # No explicit effect field
            }
        }

        tester = mcp_test.ToolsTester(config=config, endpoint="http://test:8080", transport="http")
        tester.call_tool = MagicMock(return_value={"content": [{"type": "text", "text": "success"}], "isError": False})

        with patch('builtins.print'):
            tester.run_all_tests()

        # Tool with category='write-effect' should be skipped
        assert tester.results.skipped == 1
        skipped_names = {s["name"] for s in tester.results.skipped_tests}
        assert skipped_names == {"write_tool_by_category"}

    def test_specific_tool_runs_despite_write_effect(self):
        """Test that specific tool request runs even if it has write effects."""
        from unittest.mock import MagicMock, patch

        config = {
            "test_tools": {
                "bucket_objects_list": {"effect": "none", "category": "read-only"},
                "admin_user_create": {"effect": "create", "category": "write-effect"},
            }
        }

        tester = mcp_test.ToolsTester(config=config, endpoint="http://test:8080", transport="http")
        tester.call_tool = MagicMock(return_value={"content": [{"type": "text", "text": "success"}], "isError": False})

        # Request specific write-effect tool
        with patch('builtins.print'):
            tester.run_all_tests(specific_tool="admin_user_create")

        # Should not be skipped when explicitly requested
        assert tester.results.skipped == 0
        # Should be tested (may pass or fail)
        assert tester.results.total == 1

    def test_missing_effect_classification_defaults_to_test(self):
        """Test that tools without effect/category fields are tested (conservative default)."""
        from unittest.mock import MagicMock, patch

        config = {
            "test_tools": {
                "tool_with_no_classification": {},  # No effect or category
            }
        }

        tester = mcp_test.ToolsTester(config=config, endpoint="http://test:8080", transport="http")
        tester.call_tool = MagicMock(return_value={"content": [{"type": "text", "text": "success"}], "isError": False})

        with patch('builtins.print'):
            tester.run_all_tests()

        # Should not be skipped (conservative default: test it)
        assert tester.results.skipped == 0
        assert tester.results.total >= 1
