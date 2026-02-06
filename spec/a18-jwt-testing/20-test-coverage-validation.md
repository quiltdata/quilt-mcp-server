# Test Coverage Validation for mcp-test.py

**Status**: ✅ Implemented
**Date**: 2026-02-05
**Related**: [01-base-failures.md](01-base-failures.md)

## Problem

When new tools are added to the MCP server, there was no automatic check to ensure the test configuration (`scripts/tests/mcp-test.yaml`) was updated to include them. This created a risk of:

1. **Silent coverage gaps**: New tools deployed without any test coverage
2. **Config drift**: Server capabilities and test suite becoming desynchronized
3. **CI/CD blind spots**: Tests passing while missing critical functionality

**Real-world scenario**:
```bash
# Developer adds new tool to src/quilt_mcp/tools/
# Forgets to run: uv run scripts/mcp-list.py
# Tests run and pass, but new tool is never tested
# Tool gets deployed to production with zero validation ❌
```

## Solution

Added **automatic coverage validation** to `mcp-test.py` that errors immediately if it discovers tools on the server that aren't in the test configuration.

### Implementation

**New function**: `validate_test_coverage()` ([scripts/mcp-test.py:390-442](scripts/mcp-test.py:390-442))

```python
def validate_test_coverage(
    server_tools: List[Dict[str, Any]],
    config_tools: Dict[str, Any]
) -> None:
    """Validate that all server tools are covered by test config.

    Raises ValueError with actionable remediation if gaps exist.
    """
    # Extract tool names from server
    server_tool_names = {tool['name'] for tool in server_tools}

    # Extract base tool names from config (handles variants)
    config_tool_names = set()
    for config_key, config_value in config_tools.items():
        if isinstance(config_value, dict) and 'tool' in config_value:
            # Variant - use the "tool" field
            config_tool_names.add(config_value['tool'])
        else:
            # Regular tool - use the key itself
            config_tool_names.add(config_key)

    # Find uncovered tools
    uncovered = server_tool_names - config_tool_names

    if uncovered:
        raise ValueError(f"""
❌ ERROR: {len(uncovered)} tool(s) NOT covered by test config!

Uncovered tools:
{chr(10).join(f"  • {tool}" for tool in sorted(uncovered))}

🔧 Action Required:
   1. Run: uv run scripts/mcp-list.py
   2. This regenerates scripts/tests/mcp-test.yaml
   3. Re-run this test
        """)
```

**Integration point**: `MCPTester.run_test_suite()` ([scripts/mcp-test.py:811-828](scripts/mcp-test.py:811-828))

```python
if run_tools:
    tester = ToolsTester(...)
    tester.initialize()

    # CRITICAL: Validate coverage before running tests
    if not specific_tool:  # Skip when testing specific tool
        server_tools = tester.list_tools()
        config_tools = config.get('test_tools', {})
        validate_test_coverage(server_tools, config_tools)

    tester.run_all_tests(specific_tool=specific_tool)
```

## Key Features

### 1. Variant Support

Handles tool variants correctly (e.g., `search_catalog.file.no_bucket`):

```yaml
test_tools:
  search_catalog.file.no_bucket:
    tool: search_catalog  # Maps to actual tool
    arguments: {scope: file}
```

The validator extracts the base tool name from the `tool` field.

### 2. Actionable Error Messages

Error output includes:
- ✅ List of uncovered tools
- ✅ Coverage summary statistics
- ✅ Exact command to fix: `uv run scripts/mcp-list.py`
- ✅ Explanation of why this matters

### 3. Smart Behavior

- **Skips validation** when testing specific tool (`--test-tool bucket_objects_list`)
- **Allows extra config entries** (deprecated tools removed from server but still in config)
- **Works with variants** (multiple test cases for same tool)

## Testing

Created comprehensive unit tests ([tests/unit/test_mcp_test_coverage.py](../../tests/unit/test_mcp_test_coverage.py)):

```bash
uv run pytest tests/unit/test_mcp_test_coverage.py -v
```

**8 test cases**:
1. ✅ All tools covered (success)
2. ✅ Tool variants covered (success)
3. ✅ Uncovered tool raises error
4. ✅ Multiple uncovered tools all listed
5. ✅ Empty server tools (edge case)
6. ✅ Extra config tools allowed
7. ✅ Mixed variants and regular tools
8. ✅ Error message has helpful instructions

All tests pass ✅

## Demonstration

Created demo script showing three scenarios:

```bash
uv run python scripts/demo_coverage_validation.py
```

**Output shows**:
1. ✅ Success case: All tools covered
2. 🔀 Variant case: Multiple configs for same tool
3. ❌ Failure case: New tools not in config (with full error details)

## Impact

### Before

```bash
# Add new tool to server
vim src/quilt_mcp/tools/new_feature.py

# Forget to regenerate config
# Run tests - PASS ✅ (false positive!)
uv run scripts/mcp-test.py http://localhost:8000/mcp --tools-test

# Deploy to production with zero test coverage 😱
```

### After

```bash
# Add new tool to server
vim src/quilt_mcp/tools/new_feature.py

# Forget to regenerate config
# Run tests - ERROR ❌ (caught immediately!)
uv run scripts/mcp-test.py http://localhost:8000/mcp --tools-test

# Error message:
# ❌ ERROR: 1 tool(s) NOT covered by test config!
# Uncovered tools:
#   • new_feature_tool
#
# 🔧 Action Required:
#    1. Run: uv run scripts/mcp-list.py

# Fix the issue
uv run scripts/mcp-list.py  # Regenerates config

# Now tests can run with full coverage ✅
```

## Workflow Integration

### Development Workflow

```bash
# 1. Add new tool
vim src/quilt_mcp/tools/my_new_tool.py

# 2. Regenerate test config
uv run scripts/mcp-list.py

# 3. Run tests (validation passes)
uv run scripts/mcp-test.py http://localhost:8000/mcp --tools-test

# 4. Commit both code AND updated config
git add src/quilt_mcp/tools/my_new_tool.py
git add scripts/tests/mcp-test.yaml  # Updated by mcp-list.py
git commit -m "feat: add my_new_tool with test coverage"
```

### CI/CD Integration

The validation ensures CI/CD catches config drift:

```yaml
# .github/workflows/test.yml
- name: Run MCP tests
  run: |
    uv run scripts/mcp-test.py http://localhost:8000/mcp \
      --tools-test --resources-test
    # Will ERROR if config is outdated ✅
```

## Design Decisions

### Why Error Instead of Warning?

**Decision**: Use `ValueError` (hard error) instead of warning

**Rationale**:
- Config drift is a **critical issue**, not a soft problem
- Warnings are easy to ignore in CI/CD logs
- Forces developers to keep config synchronized
- Prevents silent deployment of untested features

### Why Skip Validation for Specific Tool Tests?

**Decision**: Skip validation when `--test-tool` is used

**Rationale**:
- Developer testing specific tool during development
- Validation would be noise in this workflow
- Full validation runs in CI/CD anyway

### Why Allow Extra Config Entries?

**Decision**: Don't error if config has more tools than server

**Rationale**:
- Tools may be deprecated/removed from server
- Config can lag behind safely (opposite direction is the problem)
- Allows gradual cleanup of old test cases

## Files Changed

1. **[scripts/mcp-test.py](../../scripts/mcp-test.py)**
   - Added `validate_test_coverage()` function (53 lines)
   - Integrated validation into `run_test_suite()` (7 lines)

2. **[tests/unit/test_mcp_test_coverage.py](../../tests/unit/test_mcp_test_coverage.py)**
   - New test file with 8 comprehensive test cases (191 lines)

3. **[scripts/demo_coverage_validation.py](../../scripts/demo_coverage_validation.py)**
   - Interactive demonstration of validation (228 lines)

## Related Issues

This addresses the root cause identified in [01-base-failures.md](01-base-failures.md):
- Tools added to server but missing from test config
- CI/CD passes without validating new capabilities
- Silent drift between code and test coverage

## Future Enhancements

1. **Resource coverage validation**: Extend to resources (same pattern)
2. **Coverage metrics**: Report % of tools with tests vs. without
3. **Variant recommendations**: Suggest variants for parameterized tools
4. **Auto-fix mode**: `--auto-update-config` to regenerate on the fly

## Conclusion

Test coverage validation ensures the test suite stays synchronized with server capabilities. This prevents the most common cause of config drift: adding new tools without updating test configuration.

**Key benefit**: Makes it **impossible** to deploy untested tools to production ✅
