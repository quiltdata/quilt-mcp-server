# Test Coverage Validation - Implementation Summary

## What Changed

Added automatic validation to [scripts/mcp-test.py](../../scripts/mcp-test.py) that **ERRORS immediately** if it discovers tools on the MCP server that aren't covered by the test configuration.

## The Problem This Solves

**Before**: Silent config drift
```bash
# Developer adds new tool
vim src/quilt_mcp/tools/new_feature.py

# Forgets to regenerate config
# Tests pass ✅ (but new tool is never tested!)
# Tool deploys to production with ZERO validation 😱
```

**After**: Immediate error with fix
```bash
# Developer adds new tool
vim src/quilt_mcp/tools/new_feature.py

# Forgets to regenerate config
# Tests ERROR ❌ immediately:

❌ ERROR: 1 tool(s) on server are NOT covered by test config!

Uncovered tools:
  • new_feature_tool

🔧 Action Required:
   1. Run: uv run scripts/mcp-list.py
   2. This regenerates scripts/tests/mcp-test.yaml
   3. Re-run this test
```

## Implementation Details

### New Function

**[scripts/mcp-test.py:390-442](../../scripts/mcp-test.py:390-442)** - `validate_test_coverage()`

- Compares server tools vs. config tools
- Handles variants correctly (`search_catalog.file.no_bucket`)
- Raises descriptive `ValueError` with remediation steps

### Integration Point

**[scripts/mcp-test.py:820-828](../../scripts/mcp-test.py:820-828)** - Added to `run_test_suite()`

```python
if run_tools:
    tester.initialize()

    # NEW: Validate coverage before running tests
    if not specific_tool:
        server_tools = tester.list_tools()
        config_tools = config.get('test_tools', {})
        validate_test_coverage(server_tools, config_tools)

    tester.run_all_tests(specific_tool=specific_tool)
```

## Testing

### Unit Tests

**[tests/unit/test_mcp_test_coverage.py](../../tests/unit/test_mcp_test_coverage.py)** - 8 test cases

```bash
uv run pytest tests/unit/test_mcp_test_coverage.py -v
```

All tests pass ✅:
1. ✅ All tools covered (success)
2. ✅ Tool variants covered (handles `tool` field)
3. ✅ Uncovered tool raises error
4. ✅ Multiple uncovered tools all listed
5. ✅ Empty server tools (edge case)
6. ✅ Extra config tools allowed (deprecated tools OK)
7. ✅ Mixed variants and regular tools
8. ✅ Error message has helpful instructions

### Interactive Demo

**[scripts/demo_coverage_validation.py](../../scripts/demo_coverage_validation.py)**

```bash
uv run python scripts/demo_coverage_validation.py
```

Shows three scenarios:
1. ✅ Success: All tools covered
2. 🔀 Variants: Multiple test cases for same tool
3. ❌ Failure: Uncovered tools with full error output

## Key Features

1. **Variant Support**: Correctly handles tool variants like `search_catalog.file.no_bucket`
2. **Actionable Errors**: Provides exact command to fix: `uv run scripts/mcp-list.py`
3. **Smart Skipping**: Skips validation when testing specific tool (`--test-tool`)
4. **Backward Compatible**: Allows extra config entries (deprecated tools)

## Impact

### CI/CD Protection

Prevents untested tools from reaching production:

```yaml
# .github/workflows/test.yml
- name: Run MCP tests
  run: |
    uv run scripts/mcp-test.py http://localhost:8000/mcp \
      --tools-test --resources-test
    # Will ERROR if config is outdated ✅
```

### Developer Workflow

Forces config to stay synchronized:

```bash
# 1. Add new tool
vim src/quilt_mcp/tools/my_new_tool.py

# 2. Regenerate config (validation will enforce this)
uv run scripts/mcp-list.py

# 3. Run tests (now passes)
uv run scripts/mcp-test.py http://localhost:8000/mcp --tools-test

# 4. Commit code AND updated config
git add src/quilt_mcp/tools/my_new_tool.py scripts/tests/mcp-test.yaml
git commit -m "feat: add my_new_tool with test coverage"
```

## Files Changed

1. **[scripts/mcp-test.py](../../scripts/mcp-test.py)**
   - Added `validate_test_coverage()` (53 lines)
   - Integrated into `run_test_suite()` (7 lines)

2. **[tests/unit/test_mcp_test_coverage.py](../../tests/unit/test_mcp_test_coverage.py)**
   - New unit tests (191 lines, 8 test cases)

3. **[scripts/demo_coverage_validation.py](../../scripts/demo_coverage_validation.py)**
   - Interactive demonstration (228 lines)

4. **[spec/a18-valid-jwts/20-test-coverage-validation.md](20-test-coverage-validation.md)**
   - Full specification document

## Error Message Example

```
================================================================================
❌ ERROR: 2 tool(s) on server are NOT covered by test config!
================================================================================

Uncovered tools:
  • new_visualization_tool
  • new_admin_tool

📋 Coverage Summary:
   Server has: 5 tools
   Config has: 3 tool configs (including variants)
   Missing:    2 tools

🔧 Action Required:
   1. Run: uv run scripts/mcp-list.py
   2. This regenerates scripts/tests/mcp-test.yaml with ALL server tools
   3. Re-run this test

💡 Why This Matters:
   • New tools were added to server but not to test config
   • Running mcp-list.py ensures test coverage stays synchronized
   • This prevents capabilities from going untested
   • Config drift detection is critical for CI/CD reliability
================================================================================
```

## Quick Reference

### Run Validation Demo
```bash
uv run python scripts/demo_coverage_validation.py
```

### Run Unit Tests
```bash
uv run pytest tests/unit/test_mcp_test_coverage.py -v
```

### Fix Coverage Errors
```bash
uv run scripts/mcp-list.py  # Regenerates config with all tools
```

## Conclusion

**Key Benefit**: Makes it **impossible** to deploy untested tools to production ✅

The validation ensures test coverage automatically stays synchronized with server capabilities, preventing the most common cause of config drift in CI/CD pipelines.
