"""Output formatting for MCP test results.

This module formats test results and generates detailed summaries with
intelligent analysis, pattern detection, and actionable recommendations.

Core Functions
--------------
format_results_line(passed, failed, skipped) -> str
    Format a concise results summary line with conditional display of counts.
    Omits zero-count categories for cleaner output.

print_detailed_summary(tools_results, resources_results, loops_results, ...) -> None
    Print comprehensive test summary with intelligent pattern analysis,
    failure categorization, and actionable recommendations for fixes.

Summary Components
------------------
1. Overall Statistics
   - Total tests run across all categories
   - Pass/fail/skip counts and percentages
   - Execution time and performance metrics

2. Category Breakdown
   - Tools: Individual tool test results
   - Resources: Resource access test results
   - Loops: Multi-step loop execution results

3. Failure Analysis
   - Grouped by failure type and pattern
   - Common error messages highlighted
   - Infrastructure vs code issues identified

4. Actionable Recommendations
   - Specific fixes for detected issues
   - Configuration changes suggested
   - Permission and access control guidance

5. Context Information
   - Test selection statistics
   - Server version and capabilities
   - Environment configuration used

Output Formatting
-----------------
The detailed summary uses structured formatting:

1. Section Headers
   - Clear visual separation
   - Hierarchical organization
   - Consistent styling

2. Color Coding (Terminal)
   - Green: Passed tests
   - Red: Failed tests
   - Yellow: Skipped tests
   - Blue: Informational

3. Indentation
   - 2-space indents for hierarchy
   - Aligned values for readability
   - Consistent spacing

4. Conditional Display
   - Hide empty sections
   - Show relevant context only
   - Verbose mode for details

Usage Examples
--------------
Format simple results line:
    >>> line = format_results_line(passed=25, failed=3, skipped=2)
    >>> print(line)
    Passed: 25, Failed: 3, Skipped: 2

    >>> line = format_results_line(passed=30, failed=0, skipped=0)
    >>> print(line)
    Passed: 30

Print detailed summary:
    >>> print_detailed_summary(
    ...     tools_results={
    ...         "passed": 20,
    ...         "failed": 2,
    ...         "failed_tests": [
    ...             {"name": "bucket_create", "error": "Access Denied"},
    ...             {"name": "package_create", "error": "Access Denied"}
    ...         ]
    ...     },
    ...     resources_results={"passed": 5, "failed": 0},
    ...     loops_results={"passed": 3, "failed": 0},
    ...     selection_stats={
    ...         "tools": {"total": 22, "selected": 22},
    ...         "resources": {"total": 5, "selected": 5}
    ...     },
    ...     server_info={"version": "0.1.0", "capabilities": ["search"]},
    ...     verbose=True
    ... )

    # Output:
    # ================================================================================
    # TEST SUMMARY
    # ================================================================================
    #
    # Overall Results: Passed: 28, Failed: 2 (93.3% pass rate)
    #
    # Tools: Passed: 20, Failed: 2
    # Resources: Passed: 5
    # Loops: Passed: 3
    #
    # --------------------------------------------------------------------------------
    # FAILURE ANALYSIS
    # --------------------------------------------------------------------------------
    #
    # Access Denied Errors (2 failures):
    #   - bucket_create: Access Denied
    #   - package_create: Access Denied
    #
    # Recommended Actions:
    #   1. Check IAM permissions for S3 bucket creation
    #   2. Verify AWS credentials have required policies
    #   3. Review CloudFormation stack permissions
    # ...

Print with pattern analysis:
    >>> print_detailed_summary(
    ...     tools_results={
    ...         "failed_tests": [
    ...             {"name": "tool1", "error": "NoCredentialsError"},
    ...             {"name": "tool2", "error": "NoCredentialsError"},
    ...             {"name": "tool3", "error": "Timeout after 30s"}
    ...         ]
    ...     },
    ...     verbose=True
    ... )

    # Output includes:
    # - Grouped by error pattern
    # - Infrastructure issue detection
    # - Specific recommendations

Format minimal output:
    >>> print_detailed_summary(
    ...     tools_results={"passed": 30, "failed": 0},
    ...     verbose=False
    ... )

    # Output:
    # All tests passed! (30 passed)

Design Principles
-----------------
- Clear visual hierarchy
- Actionable insights, not just data
- Conditional detail based on verbose flag
- Pattern detection for common issues
- Structured formatting for readability
- Infrastructure vs code issue distinction

Pattern Analysis
----------------
The summary detects and highlights:

1. Permission Issues
   - Access Denied errors
   - NoCredentialsError
   - Insufficient permissions

2. Configuration Issues
   - Missing environment variables
   - Invalid URLs or parameters
   - Timeout configuration

3. Infrastructure Issues
   - Network connectivity
   - Service availability
   - Resource not found

4. Code Issues
   - Schema validation failures
   - Unexpected response types
   - Logic errors

Verbosity Levels
----------------
Normal Mode:
- Summary statistics
- Failed test names
- Basic error messages

Verbose Mode:
- Full error details
- Stack traces
- Pattern analysis
- Recommendations
- Selection statistics
- Server information

Dependencies
------------
- validators.py: Uses analyze_failure_patterns()
- typing: Type hints
- Standard library: No external dependencies

Extracted From
--------------
- format_results_line: lines 250-279 from scripts/mcp-test.py
- print_detailed_summary: lines 1984-2307 from scripts/mcp-test.py
"""

import json
from typing import Any, Dict, Optional

from .validators import analyze_failure_patterns, ResourceFailureType


def format_results_line(passed: int, failed: int, skipped: int = 0) -> str:
    """Format results line with conditional display of counts.

    Only shows counts when they're non-zero to avoid cluttered output.

    Args:
        passed: Number of passed tests
        failed: Number of failed tests
        skipped: Number of skipped tests

    Returns:
        Formatted results string

    Examples:
        >>> format_results_line(17, 0, 0)
        'Results: ✅ 17 passed'
        >>> format_results_line(12, 5, 0)
        'Results: ✅ 12 passed, ❌ 5 failed'
        >>> format_results_line(10, 0, 2)
        'Results: ✅ 10 passed, ⏭️ 2 skipped'
    """
    parts = [f"✅ {passed} passed"]

    if failed > 0:
        parts.append(f"❌ {failed} failed")

    if skipped > 0:
        parts.append(f"⏭️ {skipped} skipped")

    return "   " + ", ".join(parts)


def print_detailed_summary(
    tools_results: Optional[Dict[str, Any]] = None,
    resources_results: Optional[Dict[str, Any]] = None,
    loops_results: Optional[Dict[str, Any]] = None,
    selection_stats: Optional[Dict[str, Any]] = None,
    server_info: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
    config: Optional[Dict[str, Any]] = None,
) -> None:
    """Print intelligent test summary with context and pattern analysis.

    Args:
        tools_results: Tool test results from ToolsTester.to_dict()
        resources_results: Resource test results from ResourcesTester.to_dict()
        loops_results: Tool loops results from ToolLoopExecutor
        selection_stats: Stats from filter_tests_by_idempotence() including:
            - total_tools: total number of tools in config
            - total_resources: total number of resources in config
            - selected_tools: number of tools selected for testing
            - effect_counts: dict of effect type -> count
        server_info: Server capabilities from initialize() (optional)
        verbose: Include detailed configuration and analysis (optional)
        config: Test configuration (needed to determine tools in loops)
    """
    print("\n" + "=" * 80)
    print("📊 TEST SUITE SUMMARY")
    print("=" * 80)

    # Tools summary
    if tools_results:
        total_tools = (
            selection_stats.get('total_tools', tools_results['total']) if selection_stats else tools_results['total']
        )
        selected_tools = tools_results['total']
        non_selected = total_tools - selected_tools

        # Header with selection context
        if non_selected > 0 and selection_stats and config:
            # Analyze which non-selected tools are in loops vs truly skipped
            test_tools = config.get('test_tools', {})
            tool_loops = config.get('tool_loops', {})

            # Get tools used in loops
            tools_in_loops = set()
            for loop_name, loop_config in tool_loops.items():
                for step in loop_config.get('steps', []):
                    tool = step.get('tool')
                    if tool:
                        tools_in_loops.add(tool)

            # Categorize non-selected tools by effect and whether they're in loops
            effect_counts = selection_stats.get('effect_counts', {})
            non_none_effects = {k: v for k, v in effect_counts.items() if k not in {'none', 'none-context-required'}}

            # Count tools in loops vs truly skipped
            in_loops_by_effect = {}
            skipped_by_effect = {}
            for tool_name, tool_config in test_tools.items():
                effect = tool_config.get('effect', 'none')
                if effect in non_none_effects:
                    if tool_name in tools_in_loops:
                        in_loops_by_effect[effect] = in_loops_by_effect.get(effect, 0) + 1
                    else:
                        skipped_by_effect[effect] = skipped_by_effect.get(effect, 0) + 1

            tools_in_loops_count = sum(in_loops_by_effect.values())
            truly_skipped_count = sum(skipped_by_effect.values())

            # Print header with accurate counts
            header_parts = [f"{selected_tools}/{total_tools} tested"]
            if tools_in_loops_count > 0:
                header_parts.append(f"{tools_in_loops_count} in loops")
            if truly_skipped_count > 0:
                header_parts.append(f"{truly_skipped_count} skipped")
            print(f"\n🔧 TOOLS ({', '.join(header_parts)})")

            # Show details
            print("   Selection: Idempotent only")
            if tools_in_loops_count > 0:
                loops_summary = ", ".join(f"{effect}: {count}" for effect, count in sorted(in_loops_by_effect.items()))
                print(f"   DEFERRED TO LOOPS: {loops_summary}")
            if truly_skipped_count > 0:
                skipped_summary = ", ".join(
                    f"{effect}: {count}" for effect, count in sorted(skipped_by_effect.items())
                )
                print(f"   SKIPPED: {skipped_summary}")
        elif non_selected > 0:
            # Fallback if config not available (preserve old behavior)
            print(f"\n🔧 TOOLS (Tested {selected_tools}/{total_tools} tested, {non_selected} skipped)")
            if selection_stats:
                effect_counts = selection_stats.get('effect_counts', {})
                non_none_effects = {k: v for k, v in effect_counts.items() if k != 'none'}
                if non_none_effects:
                    skipped_summary = ", ".join(
                        f"{effect}: {count}" for effect, count in sorted(non_none_effects.items())
                    )
                    print(f"   Selection: Idempotent only (SKIPPED: {skipped_summary})")
        else:
            print(f"\n🔧 TOOLS ({selected_tools}/{total_tools} tested)")

        # Results line with conditional display
        print(format_results_line(tools_results['passed'], tools_results['failed']))

        # Show failures if any
        if tools_results['failed'] > 0 and tools_results['failed_tests']:
            print(f"\n   ❌ Failed Tools ({len(tools_results['failed_tests'])}):")
            for test in tools_results['failed_tests']:
                print(f"\n      • {test['name']}")
                print(f"        Tool: {test['actual_tool']}")
                if test['arguments']:
                    print(f"        Input: {json.dumps(test['arguments'], indent=9)}")

                # Format error message with proper indentation for multi-line errors
                error_msg = test['error']
                if '\n' in error_msg:
                    # Multi-line error (e.g., validation errors) - indent each line
                    lines = error_msg.split('\n')
                    print(f"        Error: {lines[0]}")
                    for line in lines[1:]:
                        print(f"               {line}")
                else:
                    # Single-line error
                    print(f"        Error: {error_msg}")

                print(f"        Error Type: {test['error_type']}")

        if tools_results.get('untested_side_effects'):
            print(f"\n   ⚠️  Untested Tools with Side Effects ({len(tools_results['untested_side_effects'])}):")
            for tool in tools_results['untested_side_effects']:
                print(f"      • {tool}")

    # Tool Loops summary
    if loops_results:
        # Count unique loops that passed/failed (not individual steps)
        # A loop passes if ALL its steps passed; fails if ANY step failed
        unique_failed_loops = set(test.get('loop') for test in loops_results.get('failed_tests', []))
        unique_passed_loops = set(test.get('loop') for test in loops_results.get('passed_tests', []))
        # Remove loops from passed set if they're also in failed set (partial failures)
        unique_passed_loops = unique_passed_loops - unique_failed_loops

        loops_passed_count = len(unique_passed_loops)
        loops_failed_count = len(unique_failed_loops)
        total_step_failures = len(loops_results.get('failed_tests', []))

        print("\n🔄 TOOL LOOPS")
        print(format_results_line(loops_passed_count, loops_failed_count))

        # Show failures if any
        if loops_failed_count > 0:
            # Group failures by loop for cleaner display
            failures_by_loop = {}
            for test in loops_results['failed_tests']:
                loop_name = test.get('loop', 'unknown')
                if loop_name not in failures_by_loop:
                    failures_by_loop[loop_name] = []
                failures_by_loop[loop_name].append(test)

            print(f"\n   ❌ Failed Loops ({loops_failed_count} loops, {total_step_failures} step failures):")
            for loop_name, failures in sorted(failures_by_loop.items()):
                # Show first failure for this loop (most relevant)
                first_failure = failures[0]
                step_num = first_failure.get('step', '?')
                tool_name = first_failure.get('tool', 'unknown')
                error = first_failure.get('error', 'Unknown error')
                is_cleanup = first_failure.get('is_cleanup', False)

                print(f"\n      • Loop: {loop_name}")
                if len(failures) > 1:
                    print(f"        {len(failures)} step failures in this loop")
                print(f"        First failure at step {step_num}: {tool_name}")
                if is_cleanup:
                    print("        (cleanup step failure)")
                print(f"        Error: {error}")

    # Resources summary
    if resources_results:
        total_resources = (
            selection_stats.get('total_resources', resources_results['total'])
            if selection_stats
            else resources_results['total']
        )

        # Header - resources always test all configured
        print(f"\n🗂️  RESOURCES ({total_resources}/{total_resources} tested)")

        # Count static vs template resources based on failure patterns
        static_count = 0
        template_count = 0
        for test in resources_results.get('passed_tests', []):
            if test.get('uri_variables'):
                template_count += 1
            else:
                static_count += 1
        for test in resources_results.get('failed_tests', []):
            if test.get('uri_variables') or '{' in test.get('uri', ''):
                template_count += 1
            else:
                static_count += 1

        if static_count > 0 or template_count > 0:
            print(f"   Type Breakdown: {static_count} static URIs, {template_count} templates")

        # Results line with conditional display
        print(
            format_results_line(
                resources_results['passed'], resources_results['failed'], resources_results.get('skipped', 0)
            )
        )

        # Analyze failure patterns if there are failures
        if resources_results['failed'] > 0 and resources_results['failed_tests']:
            analysis = analyze_failure_patterns(resources_results['failed_tests'])

            # Show concise failure summary based on pattern
            if analysis['dominant_pattern'] == ResourceFailureType.TEMPLATE_NOT_REGISTERED:
                if analysis['pattern_count'] == analysis['total_failures']:
                    # All failures are template registration
                    print(f"\n   ⚠️  All {analysis['total_failures']} failures: Template registration issues")
                    print("      Templates not registered by server:")
                    for test in resources_results['failed_tests']:
                        print(f"      - {test['uri']}")

                    print("\n   📋 Likely Causes:")
                    print("      • Features require activation (env vars, feature flags)")
                    print("      • Dynamic registration based on runtime config")
                    print("      • Expected behavior for optional features")

                    print("\n   📊 Impact Assessment:")
                    if static_count > 0:
                        print("      ✅ Core MCP protocol working (all static resources pass)")
                    if tools_results and tools_results['failed'] == 0:
                        print("      ✅ All idempotent tools working")
                    print("      ⚠️  Some advanced features unavailable")
                else:
                    # Mixed failure types
                    print(f"\n   ❌ Failed Resources ({len(resources_results['failed_tests'])}):")
                    for test in resources_results['failed_tests']:
                        print(f"\n      • {test['uri']}")
                        if test.get('resolved_uri') != test['uri']:
                            print(f"        Resolved URI: {test['resolved_uri']}")
                        if test.get('uri_variables'):
                            print(f"        Variables: {json.dumps(test['uri_variables'], indent=9)}")
                        print(f"        Error: {test['error']}")
                        if 'error_type' in test:
                            print(f"        Error Type: {test['error_type']}")
            else:
                # Non-template failures - show detailed list
                print(f"\n   ❌ Failed Resources ({len(resources_results['failed_tests'])}):")
                for test in resources_results['failed_tests']:
                    print(f"\n      • {test['uri']}")
                    if test.get('resolved_uri') != test['uri']:
                        print(f"        Resolved URI: {test['resolved_uri']}")
                    if test.get('uri_variables'):
                        print(f"        Variables: {json.dumps(test['uri_variables'], indent=9)}")
                    print(f"        Error: {test['error']}")
                    if 'error_type' in test:
                        print(f"        Error Type: {test['error_type']}")

        if resources_results.get('skipped', 0) > 0 and resources_results['skipped_tests']:
            print(f"\n   Skipped Resources ({len(resources_results['skipped_tests'])}):")
            for test in resources_results['skipped_tests']:
                print(f"\n      • {test['uri']}")
                print(f"        Reason: {test['reason']}")
                if test.get('config_needed'):
                    print(f"        Configuration Needed: {test['config_needed']}")

    # Overall status with intelligent assessment
    print("\n" + "=" * 80)
    tools_ok = not tools_results or tools_results['failed'] == 0
    resources_ok = not resources_results or resources_results['failed'] == 0
    loops_ok = not loops_results or loops_results['failed'] == 0

    # Analyze severity for nuanced status
    severity = 'info'
    if resources_results and resources_results['failed'] > 0:
        analysis = analyze_failure_patterns(resources_results.get('failed_tests', []))
        severity = analysis.get('severity', 'warning')

    # Determine overall status
    if tools_ok and resources_ok and loops_ok:
        overall_status = "✅ ALL TESTS PASSED"
        detail_lines = []
        if tools_results:
            detail_lines.append(f"- {tools_results['passed']} idempotent tools verified")
        if loops_results:
            detail_lines.append(f"- {loops_results['passed']} tool loops executed successfully")
        if resources_results:
            detail_lines.append(f"- {resources_results['passed']} resources verified")
        detail_lines.append("- No failures detected")
    elif not tools_ok or not loops_ok:
        overall_status = "❌ CRITICAL FAILURE"
        detail_lines = []
        if tools_results and not tools_ok:
            detail_lines.append(f"- {tools_results['failed']}/{tools_results['total']} core tools failing")
        if loops_results and not loops_ok:
            detail_lines.append(f"- {loops_results['failed']} tool loops failing")
        detail_lines.append("- Immediate action required")
    elif severity == 'warning':
        overall_status = "⚠️  PARTIAL PASS"
        detail_lines = []
        if tools_results:
            detail_lines.append(
                f"- Core functionality verified ({tools_results['passed']}/{tools_results['total']} tools)"
            )
        if loops_results:
            detail_lines.append(f"- Write operations verified ({loops_results['passed']} loops)")
        if resources_results:
            passed_static = sum(1 for t in resources_results.get('passed_tests', []) if not t.get('uri_variables'))
            if passed_static > 0:
                detail_lines.append(f"- {passed_static} static resources verified")
            detail_lines.append(f"- {resources_results['failed']} optional templates not registered (may be expected)")
        detail_lines.append("- No critical failures detected")
    else:
        overall_status = "❌ FAILURE"
        detail_lines = [
            f"- {resources_results['failed']} resource tests failed",
            "- Review failures and address issues",
        ]

    print(f"   Overall Status: {overall_status}")
    for line in detail_lines:
        print(f"   {line}")
    print("=" * 80)

    # Show next steps if applicable
    if severity == 'warning' and resources_results and resources_results['failed'] > 0:
        analysis = analyze_failure_patterns(resources_results.get('failed_tests', []))
        if analysis.get('recommendations'):
            print("\n💡 Next Steps:")
            for rec in analysis['recommendations']:
                print(f"   • {rec}")
            if selection_stats and selection_stats.get('total_tools', 0) > selection_stats.get('selected_tools', 0):
                print("   • Run with --all to test write operations")
            if not verbose:
                print("   • Run with --verbose for detailed analysis")
            print()


__all__ = [
    "format_results_line",
    "print_detailed_summary",
]
