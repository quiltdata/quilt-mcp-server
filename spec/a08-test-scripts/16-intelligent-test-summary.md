# Intelligent Test Summary Design

## Problem: Current Summary is Confusing and Incomplete

### Current Issues

1. **Contradictory Information**

   ```
   🔧 Tools Tests:
      Total: 17
      ✅ Passed: 17
      ❌ Failed: 0    ← Says 0 failures

   BUT earlier output said:
      📋 Selected 17/48 tools for testing
      Skipped 31 non-idempotent tools
   ```

   **Problem**: "Failed: 0" is technically correct but misleading - we didn't test 31 tools at all!

2. **Missing Context in Final Summary**

   ```
   ================================================================================
      Tools: ✅ PASSED
      Resources: ❌ FAILED
      Overall: ❌ SOME TESTS FAILED
   ================================================================================
   ```

   **Problem**: No summary of what was tested vs skipped. Reader has to scroll up to find:
   - How many tools were selected vs total
   - Which tool categories were skipped
   - Resource template vs static breakdown

3. **Separation of Selection Info from Final Summary**

   ```
   [Beginning of output]
   📋 Selected 17/48 tools for testing
      Skipped 31 non-idempotent tools (configure: 6, create: 15, remove: 5, update: 5)
      Resources: 24 configured for testing

   [150 lines of test output]

   [End of output]
   ================================================================================
   📊 OVERALL TEST SUMMARY
   ================================================================================
   [no mention of selection stats]
   ```

   **Problem**: Key context is separated from results by hundreds of lines

4. **Unclear What "Failed" Means for Resources**

   ```
   Failed Resources (7):
   • permissions://buckets/{bucket}/access
     Error: Template not found in server resourceTemplates
   ```

   **Problem**: Is this a test failure or expected for a resource template that needs registration?

---

## Solution: Contextual, Hierarchical Summary

### Design Principles

1. **Show What Was Run**: Always distinguish "not tested" from "tested and failed"
2. **Provide Context**: Final summary repeats key selection statistics
3. **Explain Outcomes**: Differentiate failure types (server error, config error, expected missing)
4. **Hierarchical Detail**: Three levels of detail based on verbosity
5. **Visual Clarity**: Only show failure counts when >0; avoid red X for zero failures
6. **Consistent Formatting**: Same format for tools and resources (don't repeat "0 skipped" for resources)

---

## Proposed Output Format

### Level 1: Always Show (Default)

```
================================================================================
📊 TEST SUITE SUMMARY
================================================================================

🔧 TOOLS (17/48 tested, 31 skipped)
   Selection: Idempotent only (configure: 6, create: 15, remove: 5, update: 5 skipped)
   Results: ✅ 17 passed

🗂️  RESOURCES (24/24 tested)
   Type Breakdown: 17 static URIs, 7 templates
   Results: ✅ 17 passed, ❌ 7 failed

   ⚠️  Failed Resources (7 template validation errors):
      • 7 templates not registered with server (expected - registration required)
        - permissions://buckets/{bucket}/access
        - admin://users/{name}
        - athena://databases/{database}/tables
        - athena://databases/{database}/tables/{table}/schema
        - metadata://templates/{name}
        - workflow://workflows/{id}
        - tabulator://buckets/{bucket}/tables

   📋 Analysis:
      These templates exist in test config but weren't registered by server.
      This may be expected if:
      - Templates are dynamically registered based on runtime config
      - Features require additional setup (auth, buckets, etc.)

      To investigate:
      1. Check server logs for registration warnings
      2. Run with --verbose to see full server capabilities
      3. Verify feature flags and environment variables

================================================================================
   Overall Status: ⚠️  PARTIAL PASS
   - All tested tools passed
   - Some resource templates not available on server
   - Core functionality verified
================================================================================

💡 To test skipped tools: python scripts/tests/test_mcp.py --all
💡 To see full details: python scripts/tests/test_mcp.py --verbose
```

### Level 2: Verbose Mode (--verbose)

Shows actual test inputs and outputs for all failures.

```
================================================================================
📊 TEST SUITE SUMMARY (VERBOSE)
================================================================================

🔧 TOOLS (17/48 tested, 31 skipped)
   Selection: Idempotent only (configure: 6, create: 15, remove: 5, update: 5 skipped)
   Results: ✅ 17 passed

🗂️  RESOURCES (24/24 tested)
   Type Breakdown: 17 static URIs, 7 templates
   Results: ✅ 17 passed, ❌ 7 failed

   ❌ Failed Resources (7):

   1. permissions://buckets/{bucket}/access
      Input Variables:
         {
           "bucket": "quilt-ernest-staging"
         }
      Resolved URI: permissions://buckets/quilt-ernest-staging/access

      Expected Output:
         - Resource found in server's resourceTemplates
         - Response contains permission data

      Actual Output:
         Error: Template not found in server resourceTemplates

         Server advertised templates (7):
         - config://{key}
         - docs://{section}
         - system://{component}
         [... 4 more ...]

         Note: permissions://* templates NOT in list

      Root Cause: Server didn't register permissions templates
      Severity: ⚠️ Warning (likely feature-gated)

   2. admin://users/{name}
      Input Variables:
         {
           "name": "test_user"
         }
      Resolved URI: admin://users/test_user

      Expected Output:
         - Resource found in server's resourceTemplates
         - Response contains user data

      Actual Output:
         Error: Template not found in server resourceTemplates

         Server advertised templates (7):
         - config://{key}
         - docs://{section}
         - system://{component}
         [... 4 more ...]

         Note: admin://* templates NOT in list

      Root Cause: Server didn't register admin templates
      Severity: ⚠️ Warning (likely feature-gated)

   [... remaining 5 failures with same format ...]

   📋 Pattern Analysis:
      All 7 failures: Same root cause (template registration)
      Impact: ✅ Core functionality verified, ⚠️ Optional features unavailable

================================================================================
   Overall Status: ⚠️  PARTIAL PASS
   - Core functionality verified (17/17 tools, 17/17 static resources)
   - 7 optional templates not registered (expected - feature-gated)
================================================================================
```

### Level 3: Debug Mode (--debug or on failure)

Adds per-test details:

```
🗂️  RESOURCES (24 tested, 0 skipped)
   Results: ✅ 17 passed, ❌ 7 failed, ⏭️ 0 skipped

   ✅ Passed Resources (17):
      Static URIs (17/17):
      • config://catalog ✅ (text/plain, 245 bytes)
      • docs://quick-start ✅ (text/markdown, 3.2KB)
      • system://info ✅ (application/json, valid schema)
      [... remaining 14 ...]

   ❌ Failed Resources (7):
      Template Validation Errors (7/7):

      • permissions://buckets/{bucket}/access
        Test Input: {bucket: "quilt-ernest-staging"}
        Expected: Template registered, URI resolves to permission data
        Actual: Template not in server's resourceTemplates array
        Root Cause: Server didn't register this template (likely feature-gated)

      • admin://users/{name}
        Test Input: {name: "test_user"}
        Expected: Template registered, URI resolves to user data
        Actual: Template not in server's resourceTemplates array
        Root Cause: Server didn't register this template (likely feature-gated)

      [... remaining 5 with same pattern ...]

   📊 Failure Pattern Analysis:
      All 7 failures are the same issue: Template registration

      Root Cause Hypothesis:
      1. These templates may require server-side configuration
      2. Features might be gated behind environment variables
      3. Dynamic registration may occur after first use

      Recommended Actions:
      1. ✅ Static resources all work - core MCP protocol OK
      2. 🔍 Check server logs for template registration messages
      3. 🔧 Review feature flags in config (SSO_ENABLED, ADMIN_API_ENABLED, etc.)
      4. 📖 Consult docs for template activation requirements
```

---

## Formatting Rules

### Results Line Format

**Rule**: Only show counts when they're non-zero

```python
def format_results_line(passed: int, failed: int, skipped: int = 0) -> str:
    """Format results line with conditional display of counts.

    Examples:
        ✅ 17 passed                    # No failures
        ✅ 12 passed, ❌ 5 failed       # Some failures
        ✅ 10 passed, ⏭️ 2 skipped     # Some skipped
        ✅ 10 passed, ❌ 3 failed, ⏭️ 2 skipped  # All three
    """
    parts = [f"✅ {passed} passed"]

    if failed > 0:
        parts.append(f"❌ {failed} failed")

    if skipped > 0:
        parts.append(f"⏭️ {skipped} skipped")

    return "Results: " + ", ".join(parts)
```

### Tools vs Resources Format

**Consistent Structure**:

```text
🔧 TOOLS (selected/total tested, N skipped)
   Selection: [reason for filtering]
   Results: [formatted counts]

🗂️  RESOURCES (selected/total tested)
   Type Breakdown: [static vs templates]
   Results: [formatted counts]
```

**Key Points**:

- Tools always show "skipped" in header because test selection is policy-based
- Resources show "X/Y tested" format (no separate skipped, all resources run if configured)
- Both use same `format_results_line()` function for consistency

---

## Implementation Changes

### 1. Enhance `print_detailed_summary()` Signature

```python
def print_detailed_summary(
    tools_results: Optional[Dict[str, Any]] = None,
    resources_results: Optional[Dict[str, Any]] = None,
    selection_stats: Optional[Dict[str, Any]] = None,  # NEW
    server_info: Optional[Dict[str, Any]] = None,       # NEW
    verbose: bool = False                                # NEW
) -> None:
    """Print intelligent test summary with context.

    Args:
        tools_results: Tool test results from ToolsTester.to_dict()
        resources_results: Resource test results from ResourcesTester.to_dict()
        selection_stats: Stats from filter_tests_by_idempotence()
        server_info: Server capabilities from initialize()
        verbose: Include detailed configuration and analysis
    """
```

### 2. Pass Selection Stats Through Call Chain

```python
# In test_mcp.py main()
selection_stats = {
    'total_tools': 48,
    'selected_tools': 17,
    'effect_counts': {'none': 17, 'configure': 6, 'create': 15, 'remove': 5, 'update': 5},
    'total_resources': 24,
    'skipped_tools': 31
}

# In run_unified_tests()
success = MCPTester.run_test_suite(
    ...,
    selection_stats=selection_stats  # Pass through
)
```

### 3. Add Failure Classification

```python
class ResourceFailureType(enum.Enum):
    """Classify resource test failures for better reporting."""
    TEMPLATE_NOT_REGISTERED = "template_not_registered"
    URI_NOT_FOUND = "uri_not_found"
    CONTENT_VALIDATION = "content_validation"
    SERVER_ERROR = "server_error"
    CONFIG_ERROR = "config_error"

def classify_resource_failure(test_info: dict) -> ResourceFailureType:
    """Classify resource failure for intelligent reporting."""
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
```

### 4. Add Pattern Analysis

```python
def analyze_failure_patterns(failed_tests: List[Dict]) -> Dict[str, Any]:
    """Analyze failure patterns to provide actionable insights.

    Returns:
        {
            'dominant_pattern': ResourceFailureType,
            'pattern_count': int,
            'total_failures': int,
            'recommendations': List[str],
            'severity': 'critical' | 'warning' | 'info'
        }
    """
    if not failed_tests:
        return {'severity': 'info', 'recommendations': []}

    # Classify all failures
    classifications = [classify_resource_failure(t) for t in failed_tests]

    # Find dominant pattern
    from collections import Counter
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
                "📖 Consult docs for template activation requirements"
            ]
        else:
            severity = 'warning'
            recommendations = [
                "Some templates not registered - may need configuration",
                "Compare working vs failing templates for patterns"
            ]
    elif dominant[0] == ResourceFailureType.SERVER_ERROR:
        severity = 'critical'
        recommendations = [
            "❌ Server errors detected - check server logs",
            "🐛 May indicate bugs in resource handlers",
            "🔧 Verify server is properly configured"
        ]

    return {
        'dominant_pattern': dominant[0],
        'pattern_count': dominant[1],
        'total_failures': len(failed_tests),
        'recommendations': recommendations,
        'severity': severity
    }
```

### 5. Update Overall Status Logic

```python
def determine_overall_status(tools_results, resources_results, analysis):
    """Determine overall test status with nuance."""
    tools_ok = not tools_results or tools_results['failed'] == 0
    resources_ok = not resources_results or resources_results['failed'] == 0

    if tools_ok and resources_ok:
        return "✅ ALL TESTS PASSED"

    if not tools_ok:
        return "❌ CRITICAL FAILURE"  # Tool failures are always critical

    # Tools passed, some resources failed - check pattern
    if analysis['severity'] == 'warning':
        return "⚠️  PARTIAL PASS"
    else:
        return "❌ FAILURE"
```

---

## Output Examples

### Example 1: Default Mode, Template Issues (Current Scenario)

```
================================================================================
📊 TEST SUITE SUMMARY
================================================================================

🔧 TOOLS (17/48 tested, 31 skipped)
   Selection: Idempotent only (31 non-idempotent skipped)
   Results: ✅ 17 passed

🗂️  RESOURCES (24/24 tested)
   Type Breakdown: 17 static URIs, 7 templates
   Results: ✅ 17 passed, ❌ 7 failed

   ⚠️  All 7 failures: Template registration issues
      Templates not registered by server:
      - permissions://buckets/{bucket}/access
      - admin://users/{name}
      - athena://databases/{database}/tables
      - athena://databases/{database}/tables/{table}/schema
      - metadata://templates/{name}
      - workflow://workflows/{id}
      - tabulator://buckets/{bucket}/tables

   📋 Likely Causes:
      • Features require activation (env vars, feature flags)
      • Dynamic registration based on runtime config
      • Expected behavior for optional features

   📊 Impact Assessment:
      ✅ Core MCP protocol working (all static resources pass)
      ✅ All idempotent tools working
      ⚠️  Some advanced features unavailable

================================================================================
   Overall Status: ⚠️  PARTIAL PASS
   - Core functionality verified (17/17 tools, 17/17 static resources)
   - 7 optional templates not registered (may be expected)
   - No critical failures detected
================================================================================

💡 Next Steps:
   • Review server logs for feature initialization messages
   • Check environment variables for feature flags
   • Run with --all to test write operations
   • Run with --verbose for detailed analysis
```

### Example 2: All Tests Pass

```
================================================================================
📊 TEST SUITE SUMMARY
================================================================================

🔧 TOOLS (17/48 tested, 31 skipped)
   Selection: Idempotent only
   Results: ✅ 17 passed

🗂️  RESOURCES (24/24 tested)
   Results: ✅ 24 passed

================================================================================
   Overall Status: ✅ ALL TESTS PASSED
   - 17 idempotent tools verified
   - 24 resources verified (17 static, 7 templates)
   - No failures detected
================================================================================

💡 Run with --all to test write operations
```

### Example 3: Critical Tool Failures

```
================================================================================
📊 TEST SUITE SUMMARY
================================================================================

🔧 TOOLS (17/48 tested, 31 skipped)
   Results: ✅ 12 passed, ❌ 5 failed

   ❌ Failed Tools (5):
      • bucket_objects_list: Connection timeout
      • bucket_object_info: Connection timeout
      • search_catalog: Connection timeout
      • package_browse: Connection timeout
      • athena_query_execute: Connection timeout

   📋 Failure Pattern Analysis:
      All 5 failures: Connection timeout
      Root Cause: Cannot reach AWS services

   📊 Recommended Actions:
      1. ❌ Check network connectivity
      2. 🔑 Verify AWS credentials are configured
      3. 🌐 Check if running behind VPN/proxy
      4. 🔧 Review security groups and network ACLs

================================================================================
   Overall Status: ❌ CRITICAL FAILURE
   - 5/17 core tools failing with connection issues
   - Server operational but cannot reach dependencies
   - Immediate action required
================================================================================
```

---

## Benefits

1. **No More Contradictions**: Clear distinction between "not tested" and "tested and failed"
2. **Context Preserved**: Final summary includes selection stats, no need to scroll
3. **Actionable Insights**: Pattern analysis suggests concrete next steps
4. **Appropriate Severity**: Distinguishes critical vs warning vs expected failures
5. **Progressive Detail**: Three verbosity levels for different use cases
6. **Pattern Recognition**: Automatic identification of common failure modes

---

## Implementation Priority

1. **Phase 1** (Critical): Add selection stats to final summary
2. **Phase 2** (High): Implement failure classification and pattern analysis
3. **Phase 3** (Medium): Add verbose mode with detailed breakdown
4. **Phase 4** (Low): Add debug mode with per-test details

---

## Migration Path

Existing code structure stays the same:

- `TestResults` class already ensures complete result dictionaries ✅
- `print_detailed_summary()` is already the centralized output function ✅
- Just need to enhance `print_detailed_summary()` with new features

Changes required:

1. Add `selection_stats` parameter to call chain
2. Add failure classification function
3. Add pattern analysis function
4. Update summary formatting in `print_detailed_summary()`
5. Add verbosity level support

All changes are **additive** - no breaking changes to existing tests or callers.
