# Test Runner Improvements - Follow-on Spec

**Status:** Proposed improvements based on implementation feedback
**Date:** 2026-01-31
**Parent:** [04-test-all-tui.md](04-test-all-tui.md)

## Problem Summary

The current test-runner.py implementation has three issues:

1. **Confusing test counts** - Mixes per-phase and cumulative counts (e.g., "Test 231/975 | ✅ 295 passed")
2. **Poor visual hierarchy** - Active phase buried in middle of status line
3. **Test duplication** - Phase 2 and Phase 6 run the same 975 tests twice (~2min overhead)

## Coverage Redundancy Analysis

### Current Behavior (test-runner.py lines 450-483)

**Phase 2:** `make coverage`

- Runs `test-unit` → generates `coverage-unit.xml` (unit/ tests)
- Runs `test-integration` → generates `coverage-integration.xml` (integration/ tests)
- Runs `test-e2e` → generates `coverage-e2e.xml` (e2e/ tests)
- Generates `coverage-analysis.csv` from 3 XML files
- Validates coverage thresholds
- **Total: 975 tests**

**Phase 6:** `pytest tests/ --cov=quilt_mcp`

- Runs ALL tests in tests/ directory (unit + integration + e2e)
- Generates `coverage-all.xml`
- **Total: 975 tests (DUPLICATE)**

### Why Phase 6 Exists

Looking at make.dev:25-31, `test-all` originally called test-runner.py which orchestrates ALL phases. The final pytest command in Phase 6 was meant to be "all remaining tests", but since Phase 2 already runs all tests with coverage, Phase 6 duplicates them.

### Coverage Calculation Mechanism

Coverage is calculated **during test execution** by pytest-cov:

- pytest-cov instruments Python code at runtime
- Tracks which lines execute during each test
- Writes coverage data to XML files after tests complete
- `scripts/coverage_analysis.py` merges the 3 XML files into CSV

**Key insight:** Coverage data comes FROM the test runs themselves, not a separate analysis phase.

### Redundancy Confirmation

```bash
# Phase 2 runs these commands:
uv run pytest tests/unit/ --cov=quilt_mcp --cov-report=xml:build/test-results/coverage-unit.xml
uv run pytest tests/integration/ --cov=quilt_mcp --cov-report=xml:build/test-results/coverage-integration.xml
uv run pytest tests/e2e/ --cov=quilt_mcp --cov-report=xml:build/test-results/coverage-e2e.xml

# Phase 6 runs this command (duplicating all above):
uv run pytest tests/ --cov=quilt_mcp --cov-report=xml:build/test-results/coverage-all.xml
```

Both phases run **identical test code** with **identical coverage instrumentation**. The only difference is splitting by directory vs running all at once.

## Proposed Solutions

### Solution 1: Eliminate Phase 6 (Recommended)

**Change:** Remove Phase 6 entirely. Phase 2 already runs all tests with coverage.

**Benefits:**

- Eliminates ~2 minutes of duplicate test execution
- Cleaner: one phase runs tests, generates coverage, validates thresholds
- No loss of functionality: Phase 2 generates all coverage data needed

**Implementation:**

1. Remove Phase 6 from `init_phases()` (test-runner.py:177-210)
2. Remove Phase 6 command from `phases_cmds` (test-runner.py:450-483)
3. Update all "6 phases" messaging to "5 phases"
4. Keep Phase 2 as-is (already complete)

**Trade-offs:**

- None. Phase 6 provides zero additional value.

### Solution 2: Keep Phase 6 for Debugging (Not Recommended)

**Rationale:** Some might argue Phase 6 provides "fresh" output without coverage overhead.

**Counter-argument:**

- Coverage overhead is negligible (~5% runtime)
- Can run `make test-unit` or `pytest tests/` directly for debugging
- test-all shouldn't optimize for debugging workflows
- 2-minute waste on every full test run is unacceptable

### Solution 3: Consolidate Coverage as Post-Processing (Rejected)

**Idea:** Run tests once without coverage in Phase 2, then calculate coverage in Phase 6.

**Why this fails:**

- Coverage requires runtime instrumentation (pytest-cov)
- Can't retroactively calculate coverage from test results
- Would require trace/profile data saved during tests, essentially coverage anyway

---

## Proposed Changes

### Change 1: Eliminate Phase 6

**Before (6 phases):**

1. Lint (3 subtasks)
2. Coverage (5 subtasks) - runs 975 tests
3. Docker (2 subtasks)
4. Script Tests (2 subtasks) - runs 63 tests
5. MCPB Validate (3 subtasks)
6. Main Tests (3 subtasks) - runs 975 tests **← DUPLICATE**

**After (5 phases):**

1. Lint (3 subtasks)
2. Coverage (5 subtasks) - runs 975 tests ✅
3. Docker (2 subtasks)
4. Script Tests (2 subtasks) - runs 63 tests ✅
5. MCPB Validate (3 subtasks)

**Total tests: 1038** (was 2013 counting duplicates)

### Change 2: Fix Count Inconsistency

**Problem:** Mixing per-phase and cumulative counts creates nonsensical displays.

**Current (broken):**

```
Phase 6/6: Main Tests → integration [Test 231/975 | ✅ 295 passed] | ⏱️  7m 18s
         per-phase count ^^^  ^^^        ^^^ cumulative count
```

Why 295 > 231? Because 295 includes 64 tests from earlier phases.

**Solution: All Cumulative (Recommended)**

```
Phase 4/5: Script Tests → MCP [Test 1026/1038 | ✅ 1026 passed] | ⏱️  4m 32s
                               ^^^^^ all tests  ^^^^^ all passed
```

**Benefits:**

- Clear progress: "X of Y total tests complete"
- Pass count always ≤ current count (no confusion)
- Shows overall test suite progress, not just current phase

**Alternative: All Per-Phase (Not Recommended)**

```
Phase 4/5: Script Tests → MCP [Test 12/63 | ✅ 12 passed] | ⏱️  4m 32s
                               ^^^ this phase only
```

**Why not:** Loses sight of overall progress. User can't tell if "12 passed" means "almost done" or "just started".

**Implementation:**

```python
# In format_status_line() (line 157-165):
progress = ""
if phase.tests_total > 0:
    # Calculate cumulative position across ALL phases
    prior_tests = sum(p.tests_passed + p.tests_failed for p in state.phases[:state.current_phase])
    current_test_num = prior_tests + phase.tests_passed + phase.tests_failed
    total_tests = sum(p.tests_total for p in state.phases)

    progress = f"[Test {current_test_num}/{total_tests}"
    if state.total_passed > 0:
        progress += f" | ✅ {state.total_passed} passed"
    if state.total_failed > 0:
        progress += f" | ❌ {state.total_failed} failed"
    progress += "]"
```

### Change 3: Human-Optimized Display Layout

**Problem:** Current display buries active phase in middle of line.

**Current:**

```
1.✅ Lint  2.✅ Coverage  3.✅ Docker  4.✅ Script Tests  5.✅ MCPB  [6.⏳ Main Tests]
```

User must scan entire line to find active phase.

**Proposed: "Done | *RUNNING* | Pending" Layout**

```
[4.⏳ Script Tests] | ✅ Lint, Coverage, Docker | 💤 MCPB
      ACTIVE       |      COMPLETED (3)       | PENDING (1)
```

**Benefits:**

- Active phase immediately visible (left side)
- Completed count at a glance
- Pending phases shown but de-emphasized
- Better use of horizontal space

**Multi-line variant (for complex scenarios):**

```
Line 1: Phase 4/5: [Script Tests] | ✅ 3 done | 💤 1 pending
Line 2: Script Tests: [b. MCP] | ✅ a. pytest scripts
Line 3: MCP tests [Test 1026/1038 | ✅ 1026 passed] | ⏱️  4m 32s
```

**Implementation:**

```python
def format_status_line(self) -> str:
    """Format three-line hierarchical status for TUI."""
    lines = []

    # Line 1: Active phase | Completed | Pending
    phase = self.current_phase_stats()
    active = f"[{self.current_phase + 1}.⏳ {phase.name}]" if phase else ""

    completed = []
    pending = []
    for i, p in enumerate(self.phases):
        if i < self.current_phase:
            completed.append(p.name)
        elif i > self.current_phase:
            pending.append(p.name)

    completed_str = f"✅ {', '.join(completed)}" if completed else ""
    pending_str = f"💤 {', '.join(pending)}" if pending else ""

    status_parts = [active, completed_str, pending_str]
    phase_line = " | ".join(p for p in status_parts if p)

    phase_num = self.current_phase + 1
    total_phases = len(self.phases)
    lines.append(f"Phase {phase_num}/{total_phases}: {phase_line}")

    # Line 2: Subtasks (unchanged)
    # ... existing subtask logic ...

    # Line 3: Progress with cumulative counts
    # ... use cumulative counting from Change 2 ...

    return "\n".join(lines)
```

### Change 4: Add Lap Timer for Hung Detection

**Problem:** Long-running tests can appear hung. Users can't tell if a test is:

- Making progress slowly
- Actually hung/deadlocked
- Waiting on external resource

**Solution:** Show time since last progress update (lap timer).

**Display:**

```
Phase 2/5: [2.⏳ Coverage] | ✅ Lint | 💤 Docker, Script Tests, MCPB
Coverage: [a. unit] | b. integration | c. e2e | d. analysis | e. validation
unit tests [Test 142/1038 | ✅ 142 passed] | ⏱️  1m 23s | 🔄 5s
                                                  ^total     ^lap
```

**Behavior:**

- Lap timer resets on ANY progress event:
  - Test completion (PASSED/FAILED)
  - Subtask transition
  - Phase transition
- Color coding (optional):
  - Green: < 10s (normal)
  - Yellow: 10-30s (slow test)
  - Red: > 30s (possibly hung)

**Implementation:**

```python
@dataclass
class TestRunnerState:
    start_time: float = field(default_factory=time.time)
    last_progress_time: float = field(default_factory=time.time)  # NEW
    # ... existing fields ...

    def reset_lap_timer(self) -> None:
        """Reset lap timer on any progress event."""
        self.last_progress_time = time.time()

    def lap_time(self) -> str:
        """Get formatted lap time since last progress."""
        elapsed = int(time.time() - self.last_progress_time)
        if elapsed < 60:
            return f"{elapsed}s"
        else:
            minutes = elapsed // 60
            seconds = elapsed % 60
            return f"{minutes}m {seconds}s"

    def format_status_line(self) -> str:
        # ... existing line 1 & 2 logic ...

        # Line 3: Progress with cumulative counts AND lap timer
        if phase:
            # ... existing progress logic ...
            if current_subtask:
                lap = self.lap_time()
                lines.append(
                    f"{phase_num}.{current_letter} {current_subtask} {progress} | "
                    f"⏱️  {self.elapsed_time()} | 🔄 {lap}"
                )
```

**Reset lap timer on:**

```python
def parse_pytest_output(line: str, state: TestRunnerState) -> None:
    # ... existing parsing ...
    if " PASSED" in line:
        phase.tests_passed += 1
        state.total_passed += 1
        state.reset_lap_timer()  # NEW
    elif "FAILED" in line:
        phase.tests_failed += 1
        state.total_failed += 1
        state.reset_lap_timer()  # NEW

def parse_subtask_transition(line: str, state: TestRunnerState) -> None:
    # ... existing parsing ...
    if <detected_transition>:
        phase.current_subtask_idx = new_idx
        state.reset_lap_timer()  # NEW
```

**Use case:**

- User sees "🔄 45s" and knows: "This test is slow but still running"
- User sees "🔄 3m 12s" and knows: "Something is probably hung, kill it"
- CI logs show lap times, helping diagnose flaky tests

### Change 5: Update Test Count Constants

After eliminating Phase 6, update hardcoded test counts:

```python
def init_phases() -> list[PhaseStats]:
    """Initialize all test phases."""
    return [
        PhaseStats(
            name="Lint",
            subtasks=["ruff format", "ruff check", "mypy"],
            tests_total=0,
        ),
        PhaseStats(
            name="Coverage",
            subtasks=["unit", "integration", "e2e", "analysis", "validation"],
            tests_total=975,  # All main tests
        ),
        PhaseStats(
            name="Docker",
            subtasks=["docker-check", "docker-build"],
            tests_total=0,
        ),
        PhaseStats(
            name="Script Tests",
            subtasks=["pytest scripts", "MCP integration"],
            tests_total=63,  # 24 scripts + 39 MCP
        ),
        PhaseStats(
            name="MCPB Validate",
            subtasks=["check-tools", "mcpb build", "mcpb validate"],
            tests_total=0,
        ),
        # Phase 6 removed
    ]
```

**Total test count: 975 + 63 = 1038 tests**

---

## Example Output (After Changes)

### During Execution

**Phase 1: Lint**

```
Phase 1/5: [1.⏳ Lint] | 💤 Coverage, Docker, Script Tests, MCPB
Lint: [a. ruff format] | b. ruff check | c. mypy
ruff format | ⏱️  0m 3s | 🔄 1s
```

**Phase 2: Coverage (unit tests)**

```
Phase 2/5: [2.⏳ Coverage] | ✅ Lint | 💤 Docker, Script Tests, MCPB
Coverage: [a. unit] | b. integration | c. e2e | d. analysis | e. validation
unit tests [Test 142/1038 | ✅ 142 passed] | ⏱️  1m 23s | 🔄 2s
```

**Phase 4: Script Tests (MCP integration)**

```
Phase 4/5: [4.⏳ Script Tests] | ✅ Lint, Coverage, Docker | 💤 MCPB
Script Tests: ✅ a. pytest scripts | [b. MCP]
MCP integration [Test 1026/1038 | ✅ 1026 passed] | ⏱️  4m 32s | 🔄 8s
```

**Phase 5: MCPB Validate (final phase)**

```
Phase 5/5: [5.⏳ MCPB] | ✅ Lint, Coverage, Docker, Script Tests
MCPB: ✅ a. check-tools | [b. mcpb build] | c. mcpb validate
mcpb build | ⏱️  4m 58s | 🔄 14s
```

### Success Summary

```
✅ All phases completed successfully in 4m 58s

Phase 1: Lint                     ✅ 3/3 tasks
         → ruff format            ✅
         → ruff check             ✅
         → mypy                   ✅

Phase 2: Coverage                 ✅ 975/975 tests
         → unit                   ✅ 715/715
         → integration            ✅ 200/200
         → e2e                    ✅ 60/60
         → analysis               ✅
         → validation             ✅

Phase 3: Docker                   ✅ 2/2 tasks
         → docker-check           ✅
         → docker-build           ✅

Phase 4: Script Tests             ✅ 63/63 tests
         → pytest scripts         ✅ 24/24
         → MCP integration        ✅ 39/39

Phase 5: MCPB Validate            ✅ 3/3 tasks
         → check-tools            ✅
         → mcpb build             ✅
         → mcpb validate          ✅

Total: 1038 tests passed, 0 failed | 5/5 phases | ⏱️  4m 58s
```

### Failure Summary

```
❌ Test suite failed in 5m 12s

Phase 2: Coverage - ❌ 2 failed
  tests/integration/test_packages.py::test_create_package:156
  tests/unit/test_backend.py::test_bucket_list:89

Phase 4: Script Tests - ❌ 1 failed
  scripts/tests/test_coverage_analysis.py::test_threshold_validation:42

Phases: [2.❌ Coverage]  [4.❌ Script Tests] | ✅ Lint, Docker | 💤 MCPB

Total: 1035 passed, 3 failed | 4/5 phases (stopped at MCPB) | ⏱️  5m 12s

Run with --verbose for full output
```

---

## Implementation Plan

### Phase 1: Remove Phase 6 Redundancy

1. Update `init_phases()` to remove Phase 6
2. Update `phases_cmds` to remove Phase 6 command
3. Update all "6 phases" → "5 phases" in messages
4. Update test count totals (2013 → 1038)
5. Test: `uv run python scripts/test-runner.py`

### Phase 2: Fix Count Display

1. Update `format_status_line()` to use cumulative counts
2. Add helper method `calculate_cumulative_position()`
3. Update progress string to show "Test X/Y_total"
4. Test: Verify counts make sense at each phase transition

### Phase 3: Improve Display Layout

1. Update `format_status_line()` Line 1 to use "Active | Done | Pending"
2. Shorten completed phase names (comma-separated)
3. De-emphasize pending phases (💤 prefix)
4. Test: Verify layout is scannable at each phase

### Phase 4: Add Lap Timer

1. Add `last_progress_time` field to `TestRunnerState`
2. Add `reset_lap_timer()` and `lap_time()` methods
3. Call `reset_lap_timer()` in `parse_pytest_output()` and `parse_subtask_transition()`
4. Update Line 3 of `format_status_line()` to include lap timer
5. Test: Verify lap timer resets on test completion and subtask transitions

### Phase 5: Update Documentation

1. Update [04-test-all-tui.md](04-test-all-tui.md) with new phase count
2. Update make.dev comments about test-runner.py
3. Add note about coverage redundancy removal

---

## Success Metrics

1. **Performance:** Test suite completes ~2 minutes faster (no Phase 6 duplication)
2. **Clarity:** Test counts always consistent (cumulative ≤ current, never >)
3. **Scannability:** Active phase immediately visible (left side of display)
4. **Accuracy:** Total test count matches actual tests (1038, not 2013)
5. **Hung detection:** Lap timer shows time since last progress (identifies hung tests)
6. **Maintainability:** No duplicate test execution to maintain

---

## Rejected Alternatives

### Keep Phase 6 for "Fresh" Output

**Argument:** Phase 6 provides clean pytest output without coverage noise.

**Rejection:**

- Users debugging failures can run `make test-unit` directly
- test-all optimizes for CI/validation, not debugging
- 2-minute overhead unacceptable for marginal debugging convenience
- Coverage overhead is negligible (~5%)

### Run Tests Once in Phase 6, Remove Phase 2

**Argument:** Simplify by only running tests once in Phase 6.

**Rejection:**

- Coverage generation requires test execution (pytest-cov instruments during tests)
- Phase 2 split by directory provides better granularity (unit vs integration vs e2e coverage)
- Coverage analysis/validation happens in Phase 2 - moving to Phase 6 would delay validation until end
- Phase 4 (Script Tests) depends on Phase 2 coverage data (make.dev:90)

### Parallel Phase Execution

**Argument:** Run independent phases in parallel (e.g., Phase 1 Lint + Phase 3 Docker).

**Rejection:**

- Phases have dependencies (Phase 4 needs Phase 2 coverage + Phase 3 docker)
- Terminal output would interleave (breaks TUI single-line design)
- Debugging failures would be harder (can't isolate phase output)
- Minimal performance gain (most time is in Phase 2 tests)

---

## Notes

- **Coverage File Usage:** After Phase 6 removal, only coverage-{unit,integration,e2e}.xml and coverage-analysis.csv exist. No coverage-all.xml needed.
- **Test Count Accuracy:** Current counts (975, 63) are estimates from spec. Actual counts may vary as tests are added/removed. Test runner parses pytest output for actual counts at runtime.
- **Display Width:** "Active | Done | Pending" layout assumes ~120 char terminal width. May wrap on narrow terminals (acceptable - priority is TUI mode in normal terminals).
