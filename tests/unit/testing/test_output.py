"""Unit tests for quilt_mcp.testing.output module.

Tests output formatting functions and detailed summary generation.
"""

import io
import sys
from typing import Any, Dict
from unittest.mock import patch

import pytest

from quilt_mcp.testing.output import format_results_line, print_detailed_summary
from quilt_mcp.testing.validators import ResourceFailureType


class TestFormatResultsLine:
    """Test format_results_line() function."""

    def test_passed_only(self):
        """Test formatting with only passed tests."""
        result = format_results_line(17, 0, 0)
        assert result == "   ✅ 17 passed"

    def test_passed_and_failed(self):
        """Test formatting with passed and failed tests."""
        result = format_results_line(12, 5, 0)
        assert result == "   ✅ 12 passed, ❌ 5 failed"

    def test_passed_and_skipped(self):
        """Test formatting with passed and skipped tests."""
        result = format_results_line(10, 0, 2)
        assert result == "   ✅ 10 passed, ⏭️ 2 skipped"

    def test_all_categories(self):
        """Test formatting with all categories present."""
        result = format_results_line(15, 3, 2)
        assert result == "   ✅ 15 passed, ❌ 3 failed, ⏭️ 2 skipped"

    def test_zero_passed(self):
        """Test formatting with zero passed tests."""
        result = format_results_line(0, 5, 0)
        assert result == "   ✅ 0 passed, ❌ 5 failed"

    def test_default_skipped(self):
        """Test that skipped defaults to 0 when not provided."""
        result = format_results_line(10, 2)
        assert result == "   ✅ 10 passed, ❌ 2 failed"

    def test_single_test_passed(self):
        """Test formatting with single passed test."""
        result = format_results_line(1, 0, 0)
        assert result == "   ✅ 1 passed"

    def test_single_test_failed(self):
        """Test formatting with single failed test."""
        result = format_results_line(0, 1, 0)
        assert result == "   ✅ 0 passed, ❌ 1 failed"


class TestPrintDetailedSummary:
    """Test print_detailed_summary() function."""

    @pytest.fixture
    def capture_output(self):
        """Fixture to capture stdout."""
        captured_output = io.StringIO()
        return captured_output

    def _capture_print(self, *args, **kwargs):
        """Helper to capture print_detailed_summary output."""
        captured_output = io.StringIO()
        with patch('sys.stdout', new=captured_output):
            print_detailed_summary(*args, **kwargs)
        return captured_output.getvalue()

    def test_all_tests_passed(self):
        """Test summary when all tests pass."""
        tools_results = {'total': 20, 'passed': 20, 'failed': 0, 'failed_tests': [], 'passed_tests': []}
        resources_results = {'total': 5, 'passed': 5, 'failed': 0, 'failed_tests': [], 'passed_tests': []}
        loops_results = {
            'passed': 3,
            'failed': 0,
            'failed_tests': [],
            'passed_tests': [{'loop': 'loop1'}, {'loop': 'loop2'}, {'loop': 'loop3'}],
        }

        output = self._capture_print(
            tools_results=tools_results, resources_results=resources_results, loops_results=loops_results
        )

        assert "📊 TEST SUITE SUMMARY" in output
        assert "✅ ALL TESTS PASSED" in output
        assert "20 idempotent tools verified" in output
        assert "3 tool loops executed successfully" in output
        assert "5 resources verified" in output
        assert "No failures detected" in output

    def test_tools_with_failures(self):
        """Test summary with tool failures."""
        tools_results = {
            'total': 20,
            'passed': 18,
            'failed': 2,
            'failed_tests': [
                {
                    'name': 'test_bucket_create',
                    'actual_tool': 'bucket_create',
                    'arguments': {'bucket_name': 'test-bucket'},
                    'error': 'Access Denied',
                    'error_type': 'PermissionError',
                },
                {
                    'name': 'test_package_create',
                    'actual_tool': 'package_create',
                    'arguments': {'name': 'test-pkg'},
                    'error': 'Access Denied',
                    'error_type': 'PermissionError',
                },
            ],
            'passed_tests': [],
        }

        output = self._capture_print(tools_results=tools_results)

        assert "❌ Failed Tools (2)" in output
        assert "test_bucket_create" in output
        assert "bucket_create" in output
        assert "Access Denied" in output
        assert "PermissionError" in output
        assert "❌ CRITICAL FAILURE" in output

    def test_multiline_error_formatting(self):
        """Test that multi-line errors are properly indented."""
        tools_results = {
            'total': 1,
            'passed': 0,
            'failed': 1,
            'failed_tests': [
                {
                    'name': 'test_validation',
                    'actual_tool': 'some_tool',
                    'arguments': {},
                    'error': 'Validation failed:\n  - Field x is required\n  - Field y is invalid',
                    'error_type': 'ValidationError',
                }
            ],
            'passed_tests': [],
        }

        output = self._capture_print(tools_results=tools_results)

        # Check that indentation is applied
        assert "Error: Validation failed:" in output
        assert "- Field x is required" in output
        assert "- Field y is invalid" in output

    def test_resources_with_template_failures(self):
        """Test summary with resource template registration failures."""
        resources_results = {
            'total': 5,
            'passed': 3,
            'failed': 2,
            'failed_tests': [
                {
                    'uri': 'quilt+s3://bucket/{package_name}',
                    'resolved_uri': 'quilt+s3://bucket/{package_name}',
                    'error': "Template not found in server resourceTemplates for URI 'quilt+s3://bucket/{package_name}'",
                    'error_type': 'ResourceNotFoundError',
                    'uri_variables': {},
                },
                {
                    'uri': 'quilt+s3://bucket/{key}',
                    'resolved_uri': 'quilt+s3://bucket/{key}',
                    'error': "Template not found in server resourceTemplates for URI 'quilt+s3://bucket/{key}'",
                    'error_type': 'ResourceNotFoundError',
                    'uri_variables': {},
                },
            ],
            'passed_tests': [
                {'uri': 'quilt+s3://bucket/file1'},
                {'uri': 'quilt+s3://bucket/file2'},
                {'uri': 'quilt+s3://bucket/file3'},
            ],
            'skipped': 0,
            'skipped_tests': [],
        }

        output = self._capture_print(resources_results=resources_results)

        assert "⚠️  All 2 failures: Template registration issues" in output
        assert "Templates not registered by server:" in output
        assert "📋 Likely Causes:" in output
        assert "Features require activation" in output
        assert "📊 Impact Assessment:" in output
        assert "⚠️  PARTIAL PASS" in output

    def test_loops_with_failures(self):
        """Test summary with loop failures."""
        loops_results = {
            'passed': 2,
            'failed': 1,
            'failed_tests': [
                {
                    'loop': 'user_lifecycle',
                    'step': 2,
                    'tool': 'user_update',
                    'error': 'User not found',
                    'is_cleanup': False,
                },
                {
                    'loop': 'user_lifecycle',
                    'step': 3,
                    'tool': 'user_delete',
                    'error': 'Skipped due to prior failure',
                    'is_cleanup': True,
                },
            ],
            'passed_tests': [{'loop': 'package_lifecycle'}, {'loop': 'bucket_lifecycle'}],
        }

        output = self._capture_print(loops_results=loops_results)

        assert "🔄 TOOL LOOPS" in output
        assert "❌ Failed Loops (1 loops, 2 step failures)" in output
        assert "Loop: user_lifecycle" in output
        assert "2 step failures in this loop" in output
        assert "First failure at step 2: user_update" in output
        assert "Error: User not found" in output

    def test_selection_stats_with_config(self):
        """Test summary with selection stats and config showing tools in loops."""
        tools_results = {'total': 15, 'passed': 15, 'failed': 0, 'failed_tests': [], 'passed_tests': []}
        selection_stats = {
            'total_tools': 20,
            'selected_tools': 15,
            'effect_counts': {'none': 15, 'create': 3, 'update': 2},
        }
        config = {
            'test_tools': {'tool1': {'effect': 'none'}, 'tool2': {'effect': 'create'}, 'tool3': {'effect': 'update'}},
            'tool_loops': {'loop1': {'steps': [{'tool': 'tool2'}, {'tool': 'tool3'}]}},
        }

        output = self._capture_print(tools_results=tools_results, selection_stats=selection_stats, config=config)

        assert "15/20 tested" in output
        assert "in loops" in output
        assert "DEFERRED TO LOOPS:" in output

    def test_skipped_resources(self):
        """Test summary with skipped resources."""
        resources_results = {
            'total': 5,
            'passed': 3,
            'failed': 0,
            'skipped': 2,
            'failed_tests': [],
            'passed_tests': [
                {'uri': 'quilt+s3://bucket/file1'},
                {'uri': 'quilt+s3://bucket/file2'},
                {'uri': 'quilt+s3://bucket/file3'},
            ],
            'skipped_tests': [
                {'uri': 'athena://table', 'reason': 'Missing configuration', 'config_needed': 'ATHENA_DATABASE'},
                {'uri': 'catalog://entry', 'reason': 'Feature not enabled', 'config_needed': 'CATALOG_URL'},
            ],
        }

        output = self._capture_print(resources_results=resources_results)

        assert "⏭️ 2 skipped" in output
        assert "Skipped Resources (2)" in output
        assert "athena://table" in output
        assert "Missing configuration" in output
        assert "ATHENA_DATABASE" in output

    def test_no_results(self):
        """Test summary with no results provided."""
        output = self._capture_print()

        assert "📊 TEST SUITE SUMMARY" in output
        assert "=" * 80 in output
        # Should complete without error

    def test_untested_side_effects(self):
        """Test display of untested tools with side effects."""
        tools_results = {
            'total': 20,
            'passed': 20,
            'failed': 0,
            'failed_tests': [],
            'passed_tests': [],
            'untested_side_effects': ['bucket_delete', 'package_delete'],
        }

        output = self._capture_print(tools_results=tools_results)

        assert "⚠️  Untested Tools with Side Effects (2)" in output
        assert "bucket_delete" in output
        assert "package_delete" in output

    def test_static_vs_template_resources(self):
        """Test resource type breakdown display."""
        resources_results = {
            'total': 7,
            'passed': 7,
            'failed': 0,
            'failed_tests': [],
            'passed_tests': [
                {'uri': 'quilt+s3://bucket/file1'},
                {'uri': 'quilt+s3://bucket/file2'},
                {'uri': 'quilt+s3://bucket/file3'},
                {'uri': 'quilt+s3://bucket/{key}', 'uri_variables': {'key': 'test'}},
                {'uri': 'athena://{database}/{table}', 'uri_variables': {'database': 'db', 'table': 't'}},
            ],
            'skipped': 0,
            'skipped_tests': [],
        }

        output = self._capture_print(resources_results=resources_results)

        assert "Type Breakdown:" in output
        assert "static URIs" in output
        assert "templates" in output

    def test_next_steps_recommendations(self):
        """Test that next steps are shown for partial passes."""
        resources_results = {
            'total': 5,
            'passed': 3,
            'failed': 2,
            'failed_tests': [
                {
                    'uri': 'quilt+s3://bucket/{package_name}',
                    'resolved_uri': 'quilt+s3://bucket/{package_name}',
                    'error': "Template not found in server resourceTemplates for URI 'quilt+s3://bucket/{package_name}'",
                    'error_type': 'ResourceNotFoundError',
                },
                {
                    'uri': 'quilt+s3://bucket/{key}',
                    'resolved_uri': 'quilt+s3://bucket/{key}',
                    'error': "Template not found in server resourceTemplates for URI 'quilt+s3://bucket/{key}'",
                    'error_type': 'ResourceNotFoundError',
                },
            ],
            'passed_tests': [
                {'uri': 'quilt+s3://bucket/file1'},
                {'uri': 'quilt+s3://bucket/file2'},
                {'uri': 'quilt+s3://bucket/file3'},
            ],
            'skipped': 0,
            'skipped_tests': [],
        }
        selection_stats = {'total_tools': 20, 'selected_tools': 15}

        output = self._capture_print(
            resources_results=resources_results, selection_stats=selection_stats, verbose=False
        )

        assert "💡 Next Steps:" in output
        assert "Run with --all to test write operations" in output
        assert "Run with --verbose for detailed analysis" in output

    def test_critical_failure_status(self):
        """Test critical failure status for tool failures."""
        tools_results = {
            'total': 20,
            'passed': 15,
            'failed': 5,
            'failed_tests': [
                {
                    'name': f'test_tool_{i}',
                    'actual_tool': f'tool_{i}',
                    'arguments': {},
                    'error': 'Error occurred',
                    'error_type': 'Error',
                }
                for i in range(5)
            ],
            'passed_tests': [],
        }

        output = self._capture_print(tools_results=tools_results)

        assert "❌ CRITICAL FAILURE" in output
        assert "5/20 core tools failing" in output
        assert "Immediate action required" in output

    def test_verbose_mode_differences(self):
        """Test that verbose mode provides additional details."""
        tools_results = {'total': 1, 'passed': 1, 'failed': 0, 'failed_tests': [], 'passed_tests': []}

        # Normal mode
        output_normal = self._capture_print(tools_results=tools_results, verbose=False)

        # Verbose mode
        output_verbose = self._capture_print(tools_results=tools_results, verbose=True)

        # Both should contain the summary
        assert "📊 TEST SUITE SUMMARY" in output_normal
        assert "📊 TEST SUITE SUMMARY" in output_verbose

    def test_mixed_resource_failures(self):
        """Test resources with mixed failure types (not all template errors)."""
        resources_results = {
            'total': 5,
            'passed': 2,
            'failed': 3,
            'failed_tests': [
                {
                    'uri': 'quilt+s3://bucket/{key}',
                    'resolved_uri': 'quilt+s3://bucket/{key}',
                    'error': "No resource template found",
                    'error_type': 'ResourceNotFoundError',
                },
                {
                    'uri': 'quilt+s3://bucket/missing',
                    'resolved_uri': 'quilt+s3://bucket/missing',
                    'error': 'File not found',
                    'error_type': 'FileNotFoundError',
                },
                {
                    'uri': 'athena://db/table',
                    'resolved_uri': 'athena://db/table',
                    'error': 'Query timeout',
                    'error_type': 'TimeoutError',
                },
            ],
            'passed_tests': [{'uri': 'quilt+s3://bucket/file1'}, {'uri': 'quilt+s3://bucket/file2'}],
            'skipped': 0,
            'skipped_tests': [],
        }

        output = self._capture_print(resources_results=resources_results)

        # Should show detailed list for mixed failures
        assert "❌ Failed Resources (3)" in output
        assert "File not found" in output
        assert "Query timeout" in output

    def test_empty_loops_results(self):
        """Test handling of empty loops results."""
        loops_results = {'passed': 0, 'failed': 0, 'failed_tests': [], 'passed_tests': []}

        output = self._capture_print(loops_results=loops_results)

        # Should not crash and should show loops section
        assert "🔄 TOOL LOOPS" in output

    def test_cleanup_failure_indication(self):
        """Test that cleanup failures are properly indicated."""
        loops_results = {
            'passed': 0,
            'failed': 1,
            'failed_tests': [
                {'loop': 'test_loop', 'step': 5, 'tool': 'cleanup_tool', 'error': 'Cleanup failed', 'is_cleanup': True}
            ],
            'passed_tests': [],
        }

        output = self._capture_print(loops_results=loops_results)

        assert "(cleanup step failure)" in output
        assert "cleanup_tool" in output


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
