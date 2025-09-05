# Spec: Complete Ruff Lint Configuration and Code Quality Improvements

**Issue**: #105 (inferred from current branch: 105-standard-lint)

## Overview

This specification outlines the complete migration to ruff as the sole linting and formatting tool, replacing the previous multi-tool setup (black, mypy, ruff, yamllint). The initial configuration has been applied, reducing lint errors from 4400 to 20 remaining issues that require manual fixes.

## Current State

### Completed ✅

- Configured external `ruff.toml` with comprehensive rule set (119-character line length)
- Updated `pyproject.toml` to use only ruff with external configuration
- Applied automatic fixes reducing errors from 4400 to 20
- Reformatted 111 files to match new standards
- All 415 tests continue to pass

### Remaining Issues (20 errors)

The following code quality issues require manual fixes:

#### 1. Security Warnings (6 errors)

- **S112**: `try-except-continue` without logging exceptions
  - `app/quilt_mcp/aws/athena_service.py:153`
- **S307**: Use of `eval()` function (security risk)
  - `app/quilt_mcp/optimization/autonomous.py:227`
- **S602**: `subprocess` with `shell=True`
  - `tests/test_readme.py:125`

#### 2. Error Handling (10 errors)

**E722**: Bare `except` clauses should specify exception types

- `app/quilt_mcp/search/backends/graphql.py:270`
- `app/quilt_mcp/search/tools/search_suggest.py:151`
- `app/quilt_mcp/telemetry/collector.py:200`
- `app/quilt_mcp/telemetry/privacy.py:87`
- `app/quilt_mcp/telemetry/privacy.py:166`
- `app/quilt_mcp/telemetry/transport.py:108`
- `app/quilt_mcp/telemetry/transport.py:231`
- `app/quilt_mcp/telemetry/transport.py:334`
- `tests/fixtures/interactive_mcp_test.py:150`
- `tests/fixtures/llm_mcp_test.py:209`

#### 3. Missing Imports (4 errors)

**F821**: Undefined names

- `sys` not imported in `app/quilt_mcp/visualization/engine.py` (multiple locations)
- `with_fallback` undefined in `app/quilt_mcp/tools/error_recovery.py:214`

## Implementation Plan

### Phase 1: Security and Import Fixes

**Priority: High** - These affect code reliability and security

1. **Add missing imports**

   ```python
   # Add to visualization/engine.py
   import sys
   
   # Fix error_recovery.py decorator issue
   ```

2. **Replace eval() usage**

   ```python
   # Replace in optimization/autonomous.py:227
   # Use ast.literal_eval or safer evaluation method
   ```

3. **Add exception logging**

   ```python
   # Replace in athena_service.py:153
   except Exception as e:
       logger.warning(f"Cannot access workgroup {name}: {e}")
       continue
   ```

### Phase 2: Error Handling Improvements

**Priority: Medium** - Improve debugging and error diagnosis

1. **Replace bare except clauses**

   ```python
   # Example transformation
   try:
       risky_operation()
   except:  # ❌ Bare except
       pass
   
   # Should become:
   try:
       risky_operation()
   except (SpecificError, AnotherError) as e:  # ✅ Specific exceptions
       logger.debug(f"Expected error: {e}")  # Add logging
   ```

2. **Add appropriate exception types** for each bare except:
   - JSON parsing errors → `json.JSONDecodeError`
   - Network errors → `requests.RequestException`
   - File operations → `IOError`, `OSError`

### Phase 3: Test-Specific Fixes

**Priority: Low** - Test infrastructure improvements

1. **Subprocess security** (`tests/test_readme.py:125`)
   - Consider using `subprocess.run()` without `shell=True`
   - Or add security justification comment and suppress warning

## Acceptance Criteria

### Must Have ✅

- [x] Ruff configuration replaces all previous lint tools
- [x] All automatic formatting applied (4032+ fixes)
- [x] All tests continue to pass (415 tests)
- [ ] All F821 (undefined name) errors resolved
- [ ] All S307 (eval usage) security issues resolved
- [ ] S112 exception logging added where appropriate

### Should Have 📋

- [ ] All E722 bare except clauses specify exception types
- [ ] Security warnings reviewed and addressed or suppressed with justification
- [ ] Code quality score improved from current 53% coverage baseline

### Could Have 💡

- [ ] Type annotations modernized (UP007: Union → | syntax)
- [ ] Additional security improvements beyond minimum requirements

## Technical Notes

### Ruff Configuration

```toml
# ruff.toml (external config)
line-length = 119
select = ["E", "W", "F", "I", "UP", "B", "C4", "S"]
ignore = [
  "E501",  # line-too-long (handled by line-length)
  "S101",  # assert usage (acceptable in tests)
  # ... other justified ignores
]
```

### Testing Strategy

- Run `uv run ruff check .` after each fix to verify progress
- Ensure `make coverage` continues to pass all 415 tests
- Monitor that fixes don't introduce new issues

## Risk Assessment

**Low Risk** - Changes are primarily code quality improvements:

- Formatting changes are automated and reversible
- Manual fixes are isolated and well-defined
- All tests pass, indicating no functional regressions
- External configuration allows easy rollback if needed

## Timeline

**Estimated effort**: 2-4 hours for complete implementation

- Phase 1 (Security/Imports): 1 hour
- Phase 2 (Error Handling): 2-3 hours  
- Phase 3 (Test Fixes): 30 minutes

## Success Metrics

1. **Error Reduction**: From 20 remaining to 0 critical errors
2. **Code Quality**: Improved maintainability and debugging capabilities
3. **Security**: Eliminated eval() usage and improved exception handling
4. **Consistency**: Single tool (ruff) for all linting and formatting
