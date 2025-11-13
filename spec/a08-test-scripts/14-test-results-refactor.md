# Test Results Refactor: Fix Missing Output Bug

## The Bug

When tests fail, `print_detailed_summary()` silently fails to show failure details because result dictionaries are missing required keys (`failed_tests`, `passed_tests`, `skipped_tests`).

Example:
```
📊 Resource Test Results: 18 passed, 6 failed, 0 skipped (out of 24 total)

================================================================================
📊 OVERALL TEST SUMMARY
================================================================================
   Tools: ✅ PASSED
   Resources: ❌ FAILED
   Overall: ❌ SOME TESTS FAILED
================================================================================
```

**Missing**: The actual list of which 6 resources failed and why!

## Root Cause

`run_resources_test()` sometimes returns incomplete dictionaries:
- Line 318: `return False, {}`  (empty dict)
- Line 458: `return False, {"total": X, "passed": 0, "failed": X, "skipped": 0}`  (missing list keys)

`print_detailed_summary()` expects:
```python
if resources_results['failed_tests']:  # KeyError or empty list!
```

## Solution: Refactor with Result Tracking Classes

### Architecture

```
TestResults (generic tracker)
    ↓ has-a
MCPTester (base: transport + results tracking)
    ↓ inherits
ToolsTester (adds: side-effects tracking)
ResourcesTester (adds: skip tracking)
```

### 1. Create TestResults Class

**Purpose**: Guarantee consistent result structure for ALL test outcomes

**State**:
- `total`, `passed`, `failed`, `skipped` - counters
- `passed_tests`, `failed_tests`, `skipped_tests` - lists of test details

**Methods**:
- `__init__()` - initialize counters and lists to 0/[]
- `record_pass(test_info: dict)` - increment total+passed, append to passed_tests
- `record_failure(test_info: dict)` - increment total+failed, append to failed_tests
- `record_skip(test_info: dict)` - increment total+skipped, append to skipped_tests
- `is_success() -> bool` - return failed == 0
- `to_dict() -> dict` - ALWAYS returns ALL keys: total, passed, failed, skipped, passed_tests, failed_tests, skipped_tests

**Note**: Both ToolsTester and ResourcesTester use skip tracking:

- **Tools**: Skip when specific_tool not in config, or tools with side-effects that aren't tested
- **Resources**: Skip when URI variables contain "CONFIGURE_" placeholders

**Important**: test_info dicts must capture both input AND output:

- **Pass**: Include input (arguments/uri), output (result/content), and metadata
- **Fail**: Include input (arguments/uri), partial output if any, error, error_type
- **Skip**: Include input (what was skipped), reason for skip

### 2. Refactor MCPTester

**Current**: Monolithic class with transport + protocol methods

**New**: Base class with integrated result tracking

**Changes**:
- Add `self.results = TestResults()` in `__init__()`
- Keep all existing transport methods (HTTP/stdio)
- Keep all existing protocol methods (initialize, list_tools, call_tool, etc.)
- Remove test orchestration logic (that goes to subclasses)

### 3. Create ToolsTester Subclass

**Inherits from**: MCPTester

**Additional state**:
- `self.config` - test configuration
- `self.all_side_effects` - set of tools with side effects
- `self.tested_side_effects` - set of tested side-effect tools

**Methods**:
- `run_test(tool_name: str, test_config: dict)` - run single tool test, record result
- `run_all_tests(specific_tool: str = None)` - iterate and run all configured tools
- `to_dict() -> dict` - call `self.results.to_dict()`, add `untested_side_effects`

### 4. Create ResourcesTester Subclass

**Inherits from**: MCPTester

**Additional state**:
- `self.config` - test configuration
- `self.skipped` - count of skipped resources
- `self.skipped_tests` - list of skipped resource details
- `self.available_uris` - set of available resource URIs
- `self.available_templates` - set of available resource templates

**Methods**:
- `_initialize_resources() -> bool` - query server for available resources, return success/failure
- `run_test(uri_pattern: str, test_config: dict)` - run single resource test, record result
- `_validate_content(content: dict, validation: dict)` - helper for content validation
- `run_all_tests(specific_resource: str = None)` - initialize then iterate all resources
- `to_dict() -> dict` - call `self.results.to_dict()`, add `skipped` and `skipped_tests`

### 5. Add Static Test Suite Runner

**Location**: MCPTester class

**Signature**:
```python
@staticmethod
def run_test_suite(
    endpoint: str = None,
    stdin_fd: int = None,
    stdout_fd: int = None,
    transport: str = "http",
    verbose: bool = False,
    config: dict = None,
    run_tools: bool = False,
    run_resources: bool = False,
    specific_tool: str = None,
    specific_resource: str = None,
    process: Optional[subprocess.Popen] = None
) -> bool:
```

**Logic**:
1. If `run_tools`: create ToolsTester, initialize, run_all_tests, get dict
2. If `run_resources`: create ResourcesTester, initialize, run_all_tests, get dict
3. **Call `print_detailed_summary(tools_results, resources_results)` internally**
4. Return boolean success status (True if no failures)

**Critical Design Decision**: This method MUST print the detailed summary itself. This ensures:

- Summary is ALWAYS printed when tests run (impossible to forget)
- Single point of responsibility (run tests + report results)
- Callers just get simple boolean success status
- No code duplication between CLI and programmatic usage

### 6. Simplify main()

**Changes**:
- Keep argument parsing (unchanged)
- Keep list operations (create temporary MCPTester, list tools/resources)
- Replace test execution with: `success = MCPTester.run_test_suite(...)`
- **Remove** `print_detailed_summary()` call (now handled inside run_test_suite)
- Exit with: `sys.exit(0 if success else 1)`

### 7. Remove Old Functions

**Delete**:
- `run_tools_test(tester, config, specific_tool)` - logic moves to ToolsTester
- `run_resources_test(tester, config, specific_resource)` - logic moves to ResourcesTester

**Keep**:
- `load_test_config(config_path)` - still needed
- `print_detailed_summary(tools_results, resources_results)` - still needed (but now gets consistent dicts)

## Benefits

1. **Fixes the bug**: `to_dict()` always returns complete structure
2. **Cleaner separation**: Transport vs testing logic
3. **Easier to extend**: Add new test types by subclassing MCPTester
4. **Better error handling**: Early failures properly recorded in results
5. **Type safety**: Methods enforce correct result structure

## Implementation Notes

- Each tester instance tracks its own results via `self.results`
- Subclasses call `self.results.record_pass()` and `self.results.record_failure()`
- `to_dict()` methods ensure EVERY dict has required keys
- Static `run_test_suite()` handles orchestration
- No changes to `print_detailed_summary()` required - it just works now

## Migration Checklist

- [ ] Create TestResults class with all methods
- [ ] Refactor MCPTester to add self.results, keep transport/protocol only
- [ ] Create ToolsTester subclass with test logic from run_tools_test()
- [ ] Create ResourcesTester subclass with test logic from run_resources_test()
- [ ] Add static run_test_suite() method to MCPTester
- [ ] Update main() to use run_test_suite()
- [ ] Delete run_tools_test() and run_resources_test() functions
- [ ] Test that detailed summary now shows all failures
