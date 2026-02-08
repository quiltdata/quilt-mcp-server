# MCP Test CLI Status

## Analysis Overview

Looking at [scripts/mcp-test.py](../../scripts/mcp-test.py), I can see the CLI argument definitions in the
`main()` function (lines 2117-2228).

## Current CLI Options

### Transport & Connection

- `endpoint` - Positional argument for HTTP endpoint URL
- `--http` / `--stdio` - Transport mode selection (mutually exclusive)
- `--stdin-fd` / `--stdout-fd` - File descriptors for stdio transport

### Authentication

- `--jwt-token` - Explicit JWT token
- `--jwt` - Use generated test JWT token
- Also checks `MCP_JWT_TOKEN` environment variable

### Test Execution

- `-t` / `--tools-test` - Run all tool tests
- `-T` / `--test-tool TOOL_NAME` - Test specific tool
- `-r` / `--resources-test` - Run all resource tests
- `-R` / `--test-resource RESOURCE_URI` - Test specific resource
- `--loop LOOP_NAME` - Run specific tool loop
- `--loops-test` - Run all tool loops

### Filtering & Validation

- `--idempotent-only` - Run only read-only tools
- `--validate-coverage` - Validate test coverage

### Discovery

- `--list-tools` - List available tools
- `--list-resources` - List available resources

### Configuration

- `--config` - Path to test config YAML (default: `scripts/tests/mcp-test.yaml`)
- `-v` / `--verbose` - Verbose output

## Issues Found

### 1. Missing `--all` flag (Critical)

Line 2111 references a non-existent option:

```python
print(f"   • Run with --all to test write operations")
```

But there's no `--all` argument defined. This should either:

- Add the `--all` flag to disable `--idempotent-only` filtering, OR
- Remove the reference from the output

### 2. Inconsistent `--idempotent-only` documentation

Line 2226 help text says:

```python
help="Run only idempotent (read-only) tools with effect='none' (matches test-mcp behavior)"
```

But line 1842 shows it actually includes **two** effect types:

```python
is_idempotent = effect in ['none', 'none-context-required']
```

The help text should mention both effect types or explain that it includes read-only operations regardless of context requirements.

### 3. Potential obsolete context reference

The code still references `'none-context-required'` as an effect type (line 1842), but based on the spec file name
[21-delete-implicit-context.md](21-delete-implicit-context.md), implicit context was removed. This might be:

- A leftover from the old system that should be cleaned up, OR
- A legitimate effect classification that's still needed
