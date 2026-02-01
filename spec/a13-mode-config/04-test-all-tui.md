# Test Runner TUI Design

## Problem

`make test-all` runs 975+ tests producing hundreds of lines of output. This makes it hard to:

- Monitor progress during long test runs (several minutes)
- Quickly identify failures
- Determine if errors are actionable vs transient

## Actual Execution Order (from make output)

Based on the dependencies in `test-all: lint test-catalog test-scripts mcpb-validate`:

**Phase 1: lint** → Runs first (no dependencies)

- ruff format
- ruff check --fix
- mypy type checking

**Phase 2: coverage** → Triggered by test-scripts dependency chain

- Runs test-unit → generates coverage-unit.xml
- Runs test-integration → generates coverage-integration.xml
- Runs test-e2e → generates coverage-e2e.xml
- Generates coverage-analysis.csv from 3 coverage files
- Validates coverage thresholds

**Phase 3: docker-build** → Triggered by test-scripts dependency

- docker-check (verify docker available)
- docker build quilt-mcp:test image

**Phase 4: test-scripts** → Explicit dependency of test-all

- pytest scripts/tests/ (24 tests: coverage_analysis, scripts validation)
- MCP integration tests via test_mcp.py --docker (39 tool/resource tests)

**Phase 5: mcpb-validate** → Explicit dependency of test-all

- check-tools (verify npx, uv, mcpb installed)
- mcpb (build MCPB package from build/mcpb/)
- mcpb validate (validate manifest, structure, content, UVX execution, prerequisites)

**Phase 6: pytest tests/** → Final command in test-all target

- All tests in tests/ directory (975 tests across e2e/, integration/, unit/)

**Note:** `test-catalog` appears to be a no-op target (nothing to be done)

**Total:** 6 phases, ~1045 work items, ~3-5 minutes runtime

## Requirements

### Core Display Format

**Single-line status with hierarchical context:**

```
[Phase 1/6: Lint → mypy] [Task 3/3 | ⏱️ 0m 15s]
```

```
[Phase 2/6: Coverage → integration] [Test 142/975 | ✅ 141 passed | ⏱️ 1m 23s]
```

```
[Phase 4/6: Script Tests → MCP] [Test 12/39 | ✅ 11 passed | ⏱️ 2m 15s]
```

```
[Phase 6/6: Main Tests → unit] [Test 789/975 | ✅ 787 passed | ❌ 2 failed | ⏱️ 3m 45s]
```

**Display Components:**

1. `[Phase X/6: Name]` - Current phase out of 6 total
2. `→ subtask` - Current subtask within phase (linting tool, test directory, etc.)
3. `[Task/Test N/Total]` - Progress within current phase (or cumulative for pytest)
4. `✅ N passed` - Cumulative pass count across ALL phases
5. `❌ N failed` - Cumulative failure count across ALL phases
6. `⏱️ Mm Ss` - Total elapsed time since start

Updates in-place at 2-4 Hz refresh rate.

### What to Track Per Phase

**Phase 1: Lint (3 subtasks)**

- Track: ruff format → ruff check → mypy
- Parse: "Running ruff", "Running mypy" output
- No test counts, just task completion

**Phase 2: Coverage (5 subtasks = 3 test runs + 1 analysis + 1 validation)**

- Track: unit → integration → e2e → analysis → validation
- Parse pytest output during each test run (cumulative test counts)
- Track: 975 total tests across 3 directories

**Phase 3: Docker (2 subtasks)**

- Track: docker-check → docker-build
- Parse: "Docker available", "Building Docker image", "Successfully built"
- No test counts

**Phase 4: Script Tests (2 subtasks = 24 pytest + 39 MCP tests)**

- Track: pytest scripts/tests → MCP integration tests
- Parse pytest output for scripts/tests (24 tests)
- Parse MCP test_mcp.py output for tool/resource tests (39 tests)

**Phase 5: MCPB Validate (4 subtasks)**

- Track: check-tools → mcpb build → mcpb validate → UVX test
- Parse: "All required tools found", "Built dist/*.mcpb", validation steps
- No test counts

**Phase 6: Main Tests (975 tests across 3 directories)**

- Track: current directory (e2e → integration → unit)
- Parse pytest verbose output with directory context
- Cumulative test count: 975 total

### Cumulative Tracking

Track across ALL phases:

- Total tests run (from Phase 2 coverage + Phase 4 scripts + Phase 4 MCP + Phase 6 main)
- Total pass count
- Total fail count
- Failed test details (phase, path, line)
- Elapsed time from start

### Error Reporting

After all phases complete, print hierarchical summary:

**If all passed:**

```
✅ All phases completed successfully in 3m 42s

Phase 1: Lint                     ✅ 3/3 tasks
Phase 2: Coverage                 ✅ 975/975 tests (unit + integration + e2e)
Phase 3: Docker                   ✅ 2/2 tasks
Phase 4: Script Tests             ✅ 63/63 tests (24 scripts + 39 MCP)
Phase 5: MCPB Validate            ✅ 4/4 tasks
Phase 6: Main Tests               ✅ 975/975 tests
         → e2e                    ✅ 60/60
         → integration            ✅ 200/200
         → unit                   ✅ 715/715

Total: 2013 tests passed, 0 failed
```

**If failures exist:**

```
❌ Test suite failed: 2 failures (2011 passed) in 3m 45s

Phase 2: Coverage - ❌ 1 failed
  tests/integration/test_packages.py::test_create_package - line 156

Phase 4: Script Tests - ❌ 1 failed
  scripts/tests/test_coverage_analysis.py::test_threshold_validation - line 42

Total: 2011 passed, 2 failed

Run with --verbose for full output
```

Show:

- Which phase each failure occurred in
- Full test path with file:line reference
- Total pass/fail across all phases

### Integration Points

1. **make test-all**: Replace final pytest invocation with wrapper script
2. **Script orchestrates**: Run all dependencies (lint, coverage, docker, scripts, mcpb) then pytest
3. **Passthrough flags**: Support `--verbose` to show full output (disable TUI)
4. **Exit codes**: Preserve standard exit codes (0=pass, 1=failures, 2=errors)
5. **CI compatibility**: Auto-detect non-TTY and disable TUI

### Implementation Strategy

**Phase Detection:**

Track which subprocess is running by monitoring:

1. Command invocations (make lint, make coverage, docker build, etc.)
2. Output parsing to detect phase transitions
3. Pytest directory detection from test paths

**Parsing Strategy per Phase:**

1. **Lint**: Match "Running ruff format", "Running ruff check", "Running mypy"
2. **Coverage**:
   - Match "Running unit/integration/e2e tests"
   - Parse pytest output (test names, PASSED/FAILED)
   - Match "Generating coverage analysis", "Validating coverage thresholds"
3. **Docker**: Match "Docker available", "Building Docker image", "Successfully built"
4. **Script Tests**:
   - Parse pytest output for scripts/tests/
   - Parse test_mcp.py output matching "Testing tool:" and resource test patterns
5. **MCPB Validate**: Match validation step output
6. **Main Tests**: Parse pytest verbose output with directory extraction

**State Tracking:**

- Current phase number (1-6)
- Current subtask within phase
- Tests completed in current phase
- Cumulative pass/fail/skip counts
- Start timestamp for elapsed time
- Failed test details (phase, path, line)

### Technical Details

**Dependencies:**

- Add `rich>=13.0.0` to test dependency group in pyproject.toml

**CLI Interface:**

```bash
uv run python scripts/test-runner.py [--verbose] [--no-tui]
```

**Environment Detection:**

- If `sys.stdout.isatty() == False`, disable TUI automatically
- If `CI=true` environment variable, disable TUI
- If `--verbose` flag, disable TUI and pass through to subprocess

### Non-Requirements

- No full-screen TUI (single line only)
- No interactive controls (not curses-based)
- No colors in CI/non-TTY environments
- No scrolling history buffer
- No parallel execution (phases are sequential)

### Success Metrics

1. Shows hierarchical phase progress (X/6 phases, current subtask)
2. Shows cumulative test counts across all phases
3. Failures immediately visible without scrolling
4. Failed tests show file:line for quick navigation
5. Works identically in CI with TUI auto-disabled
6. Agents can quickly determine: "Are there errors? Where?"
