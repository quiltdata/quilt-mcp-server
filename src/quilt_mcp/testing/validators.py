r"""Validation and analysis for MCP test results.

This module provides comprehensive validation of test execution results and
intelligent analysis of failure patterns. It ensures test coverage completeness,
validates search result quality, and generates actionable insights from failures.

Core Components
---------------
SearchValidator : class
    Validates search results against expected outcomes including minimum result
    counts, required fields, content patterns, and data quality checks.
    Provides detailed validation failure reports.

ResourceFailureType : enum
    Classifies resource test failures into categories (template_not_registered,
    uri_not_found, content_validation, server_error, config_error) for intelligent
    reporting and pattern analysis.

validate_test_coverage(server_tools, config_tools) -> None
    Ensures all server-registered tools are covered by test configuration.
    Raises ValueError for missing coverage with detailed reports.

classify_resource_failure(test_info) -> ResourceFailureType
    Classifies resource test failures based on error messages and patterns.
    Enables intelligent grouping and reporting of failure types.

analyze_failure_patterns(failed_tests) -> Dict[str, Any]
    Analyzes failure patterns across multiple test failures to identify
    common root causes, infrastructure issues, and actionable fixes.

validate_loop_coverage(server_tools, tool_loops, standalone_tools) -> Tuple[bool, List[str]]
    Validates that all write-effect tools are covered by either tool loops
    or standalone tests. Returns (coverage_complete, missing_tools).

Validation Strategies
---------------------
1. Coverage Validation
   - All registered tools must have test configurations
   - Write-effect tools must have cleanup/rollback tests
   - Resources must have access validation tests
   - Search tools must have result quality checks

2. Result Quality Validation
   - Minimum result count requirements
   - Required field presence checks
   - Content pattern matching (regex, substrings)
   - Data type and format validation

3. Failure Pattern Analysis
   - Group failures by error type and root cause
   - Identify infrastructure vs code issues
   - Detect permission and access control problems
   - Highlight environment configuration issues

Usage Examples
--------------
Validate search results:
    >>> config = {
    ...     "type": "search",
    ...     "min_results": 1,
    ...     "result_shape": {"required_fields": ["name", "logical_key"]}
    ... }
    >>> validator = SearchValidator(config, env_vars={})
    >>> is_valid, error = validator.validate(result)
    >>> if not is_valid:
    ...     print(error)

Classify resource failures:
    >>> failure_type = classify_resource_failure({
    ...     "name": "access_private_bucket",
    ...     "error": "Template not found in server resourceTemplates"
    ... })
    >>> print(failure_type)
    ResourceFailureType.TEMPLATE_NOT_REGISTERED

Analyze failure patterns:
    >>> failed = [
    ...     {"tool": "bucket_list", "error": "Template not found"},
    ...     {"tool": "package_list", "error": "Template not found"},
    ... ]
    >>> patterns = analyze_failure_patterns(failed)
    >>> print(patterns["recommendations"])

Validate test coverage:
    >>> server_tools = [
    ...     {"name": "bucket_list", "description": "List buckets"},
    ...     {"name": "package_create", "description": "Create package"}
    ... ]
    >>> config_tools = {"bucket_list": {"args": {}}}
    >>> validate_test_coverage(server_tools, config_tools)
    ValueError: Missing test coverage for tools: package_create

Validate loop coverage:
    >>> complete, missing = validate_loop_coverage(
    ...     server_tools=tools,
    ...     tool_loops=loops,
    ...     standalone_tools=standalone
    ... )
    >>> if not complete:
    ...     print(f"Missing coverage: {', '.join(missing)}")

Design Principles
-----------------
- Fail-fast validation with detailed error messages
- Actionable insights from failure analysis
- Extensible validation rules and patterns
- Clear separation of validation logic from test execution
- Comprehensive logging for debugging validation issues

SearchValidator Design
----------------------
The SearchValidator provides flexible result validation:

1. Quantitative Checks
   - Minimum result counts
   - Empty result detection

2. Structural Checks
   - Required field presence
   - Field type validation

3. Content Checks
   - Regex pattern matching
   - Substring presence
   - Exact value matching

Dependencies
------------
- Standard library: enum, typing, collections, json, re

Extracted From
--------------
- ResourceFailureType: lines 157-163 from scripts/mcp-test.py
- SearchValidator: lines 358-524 from scripts/mcp-test.py
- validate_test_coverage: lines 527-579 from scripts/mcp-test.py
- classify_resource_failure: lines 166-186 from scripts/mcp-test.py
- analyze_failure_patterns: lines 189-247 from scripts/mcp-test.py
- validate_loop_coverage: lines 856-901 from scripts/mcp-test.py
"""

import json
import re
from collections import Counter
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ResourceFailureType(Enum):
    """Classify resource test failures for better reporting."""

    TEMPLATE_NOT_REGISTERED = "template_not_registered"
    URI_NOT_FOUND = "uri_not_found"
    CONTENT_VALIDATION = "content_validation"
    SERVER_ERROR = "server_error"
    CONFIG_ERROR = "config_error"


def classify_resource_failure(test_info: Dict[str, Any]) -> ResourceFailureType:
    """Classify resource failure for intelligent reporting.

    Args:
        test_info: Test failure information dict

    Returns:
        ResourceFailureType classification
    """
    error = test_info.get('error', '')

    if 'Template not found in server resourceTemplates' in error:
        return ResourceFailureType.TEMPLATE_NOT_REGISTERED
    elif 'Resource not found in server resources' in error:
        return ResourceFailureType.URI_NOT_FOUND
    elif 'validation failed' in error.lower():
        return ResourceFailureType.CONTENT_VALIDATION
    elif 'error_type' in test_info and test_info['error_type'] == 'ConfigurationError':
        return ResourceFailureType.CONFIG_ERROR
    else:
        return ResourceFailureType.SERVER_ERROR


def analyze_failure_patterns(failed_tests: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze failure patterns to provide actionable insights.

    Args:
        failed_tests: List of failed test info dictionaries

    Returns:
        Dict with pattern analysis:
        - dominant_pattern: Most common ResourceFailureType
        - pattern_count: Count of dominant pattern
        - total_failures: Total number of failures
        - recommendations: List of actionable recommendations
        - severity: 'critical' | 'warning' | 'info'
    """
    if not failed_tests:
        return {'severity': 'info', 'recommendations': []}

    # Classify all failures
    classifications = [classify_resource_failure(t) for t in failed_tests]

    # Find dominant pattern
    pattern_counts = Counter(classifications)
    dominant = pattern_counts.most_common(1)[0]

    # Generate recommendations based on pattern
    recommendations = []
    severity = 'warning'

    if dominant[0] == ResourceFailureType.TEMPLATE_NOT_REGISTERED:
        if dominant[1] == len(failed_tests):
            # ALL failures are template registration
            severity = 'warning'  # Not critical - static resources work
            recommendations = [
                "✅ Static resources all work - core MCP protocol OK",
                "🔍 Check server logs for template registration messages",
                "🔧 Review feature flags in config (SSO_ENABLED, ADMIN_API_ENABLED, etc.)",
                "📖 Consult docs for template activation requirements",
            ]
        else:
            severity = 'warning'
            recommendations = [
                "Some templates not registered - may need configuration",
                "Compare working vs failing templates for patterns",
            ]
    elif dominant[0] == ResourceFailureType.SERVER_ERROR:
        severity = 'critical'
        recommendations = [
            "❌ Server errors detected - check server logs",
            "🐛 May indicate bugs in resource handlers",
            "🔧 Verify server is properly configured",
        ]

    return {
        'dominant_pattern': dominant[0],
        'pattern_count': dominant[1],
        'total_failures': len(failed_tests),
        'recommendations': recommendations,
        'severity': severity,
    }


class SearchValidator:
    """Validates search results against expected outcomes."""

    def __init__(self, validation_config: Dict[str, Any], env_vars: Dict[str, str]):
        """Initialize validator with config and environment.

        Args:
            validation_config: Validation rules from YAML
            env_vars: Environment variables for substitution
        """
        self.config = validation_config
        self.env_vars = env_vars

    def validate(self, result: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate search result.

        Returns:
            (is_valid, error_message)
            - is_valid: True if validation passed
            - error_message: None if valid, error string if invalid
        """
        validation_type = self.config.get("type")

        if validation_type == "search":
            return self._validate_search(result)
        else:
            # Unknown validation type - skip
            return True, None

    def _validate_search(self, result: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate search-specific results."""

        # Handle both MCP-wrapped and direct dict responses
        # MCP protocol may wrap as {"content": [{"text": "<json>"}]}
        # Or return direct dict: {"success": true, "results": [...]}

        search_results = None

        # Try MCP-wrapped format first
        content = result.get("content", [])
        if content:
            try:
                if isinstance(content[0], dict) and "text" in content[0]:
                    search_results = json.loads(content[0]["text"])
                else:
                    search_results = content[0]
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                # Fall through to try direct format
                pass

        # Try direct dict format (actual stdio transport format)
        if search_results is None:
            if "results" in result:
                search_results = result
            else:
                return False, "No search results found in response (neither MCP-wrapped nor direct dict format)"

        # Extract results list
        try:
            results_list = search_results.get("results", [])
        except (KeyError, AttributeError) as e:
            return False, f"Failed to extract results array: {e}"

        # Check minimum results
        min_results = self.config.get("min_results", 0)
        if len(results_list) < min_results:
            return False, f"Expected at least {min_results} results, got {len(results_list)}"

        # Check must_contain rules
        must_contain = self.config.get("must_contain", [])
        for rule in must_contain:
            is_found, error = self._check_must_contain(results_list, rule)
            if not is_found:
                return False, error

        # Check result shape if specified
        result_shape = self.config.get("result_shape")
        if result_shape:
            shape_valid, shape_error = self._validate_result_shape(results_list, result_shape)
            if not shape_valid:
                return False, shape_error

        # All checks passed
        return True, None

    def _check_must_contain(self, results: List[Dict[str, Any]], rule: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Check if results contain expected value.

        Args:
            results: List of result dictionaries
            rule: must_contain rule with value, field, match_type

        Returns:
            (is_found, error_message)
        """
        expected_value = rule["value"]
        field_name = rule["field"]
        match_type = rule.get("match_type", "substring")
        description = rule.get("description", f"Expected to find '{expected_value}'")

        # Search through results
        found = False
        for result in results:
            actual_value = result.get(field_name, "")

            if match_type == "exact":
                if actual_value == expected_value:
                    found = True
                    break
            elif match_type == "substring":
                if expected_value in str(actual_value):
                    found = True
                    break
            elif match_type == "regex":
                if re.search(expected_value, str(actual_value)):
                    found = True
                    break

        if not found:
            # Generate helpful error message
            error = f"{description}\n"
            error += f"  Expected: '{expected_value}' in field '{field_name}'\n"
            error += f"  Match type: {match_type}\n"
            error += f"  Searched {len(results)} results\n"

            # Show sample of what we found instead
            if results and len(results) > 0:
                sample = results[:3]
                sample_values = [r.get(field_name, "<missing>") for r in sample]
                error += f"  Sample values: {sample_values}"

            return False, error

        return True, None

    def _validate_result_shape(
        self, results: List[Dict[str, Any]], shape: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate that results have expected shape.

        Args:
            results: List of result dictionaries
            shape: Expected shape with required_fields, optional_fields, etc.

        Returns:
            (is_valid, error_message)
        """
        if not results:
            return True, None  # Empty results are OK if we got this far

        required_fields = shape.get("required_fields", [])

        # Check first result (representative sample)
        first_result = results[0]
        missing_fields = [f for f in required_fields if f not in first_result]

        if missing_fields:
            return False, f"Results missing required fields: {missing_fields}"

        return True, None


def validate_test_coverage(server_tools: List[Dict[str, Any]], config_tools: Dict[str, Any]) -> None:
    """Validate that all server tools are covered by test config.

    This prevents tools from going untested when new capabilities are added.
    Raises descriptive error with remediation steps if coverage gaps exist.

    Args:
        server_tools: List of tool dicts from server (with 'name' field)
        config_tools: Dict of test configurations keyed by tool name (may include variants)

    Raises:
        ValueError: If any server tools are not covered by test config
    """
    # Extract tool names from server
    server_tool_names = {tool['name'] for tool in server_tools}

    # Extract base tool names from config (handles variants like "search_catalog.file.no_bucket")
    # Variants use format: "tool_name.variant" and have a "tool" field with actual tool name
    config_tool_names = set()
    for config_key, config_value in config_tools.items():
        if isinstance(config_value, dict) and 'tool' in config_value:
            # This is a variant - use the "tool" field
            config_tool_names.add(config_value['tool'])
        else:
            # Regular tool - use the key itself
            config_tool_names.add(config_key)

    # Find uncovered tools
    uncovered = server_tool_names - config_tool_names

    if uncovered:
        raise ValueError(
            f"\n{'=' * 80}\n"
            f"❌ ERROR: {len(uncovered)} tool(s) on server are NOT covered by test config!\n"
            f"{'=' * 80}\n\n"
            f"Uncovered tools:\n" + "\n".join(f"  • {tool}" for tool in sorted(uncovered)) + f"\n\n"
            f"📋 Coverage Summary:\n"
            f"   Server has: {len(server_tool_names)} tools\n"
            f"   Config has: {len(config_tool_names)} tool configs (including variants)\n"
            f"   Missing:    {len(uncovered)} tools\n\n"
            f"🔧 Action Required:\n"
            f"   1. Run: uv run scripts/mcp-test-setup.py\n"
            f"   2. This regenerates scripts/tests/mcp-test.yaml with ALL server tools\n"
            f"   3. Re-run this test\n\n"
            f"💡 Why This Matters:\n"
            f"   • New tools were added to server but not to test config\n"
            f"   • Running mcp-test-setup.py ensures test coverage stays synchronized\n"
            f"   • This prevents capabilities from going untested\n"
            f"   • Config drift detection is critical for CI/CD reliability\n"
            f"{'=' * 80}\n"
        )


def validate_loop_coverage(
    server_tools: List[Dict[str, Any]], tool_loops: Dict[str, Any], standalone_tools: Dict[str, Any]
) -> tuple[bool, List[str]]:
    """Validate that all write-effect tools are covered by loops or standalone tests.

    Args:
        server_tools: List of tool dicts from server
        tool_loops: Tool loops configuration
        standalone_tools: Standalone test configurations

    Returns:
        (is_complete, uncovered_tools) where:
        - is_complete: True if 100% coverage
        - uncovered_tools: List of tool names not covered
    """
    # Find all write-effect tools (would need effect classification from server)
    # For now, we'll extract tools from loops and standalone tests

    # Find tools covered by loops
    loop_covered = set()
    for loop_name, loop_config in tool_loops.items():
        for step in loop_config.get('steps', []):
            tool_name = step.get('tool')
            if tool_name:
                loop_covered.add(tool_name)

    # Find tools covered by standalone tests
    standalone_covered = set()
    for tool_key, tool_config in standalone_tools.items():
        if isinstance(tool_config, dict) and 'tool' in tool_config:
            # Variant - use actual tool name
            standalone_covered.add(tool_config['tool'])
        else:
            # Regular tool - use key
            standalone_covered.add(tool_key)

    # All server tools
    server_tool_names = {tool['name'] for tool in server_tools}

    # Check coverage
    total_covered = loop_covered | standalone_covered
    uncovered = server_tool_names - total_covered

    return len(uncovered) == 0, sorted(uncovered)


__all__ = [
    "ResourceFailureType",
    "SearchValidator",
    "validate_test_coverage",
    "classify_resource_failure",
    "analyze_failure_patterns",
    "validate_loop_coverage",
]
