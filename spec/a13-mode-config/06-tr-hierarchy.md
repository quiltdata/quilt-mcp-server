# Test Runner TUI: Hierarchical Display Design

**Status:** Approved
**Date:** 2026-01-31

## Problem

The current test runner TUI display compresses all phase information into a single line, making it difficult to distinguish at a glance:

- What's actively running now
- What's already completed
- What's still pending

Current format:

```
Phase 2/5: [2.⏳ Coverage] | ✅ Lint | 💤 Docker, Script Tests, MCPB Validate
```

## Solution: Tree Structure Layout

Use a multi-line hierarchical display with clear visual sections and tree symbols (├─ └─) to show subtask relationships.

### Visual Design

```
🔄 RUNNING: Phase 2/5 - Coverage ⏱️  1m 23s | 🔄 12s
  ├─ a. unit ✅                          (dimmed)
  ├─ b. integration ✅                   (dimmed)
  └─ c. e2e [ACTIVE] Test 450/975 | ⏳ 420 | ❌ 2

💤 PENDING: Docker | Script Tests | MCPB Validate
✅ COMPLETED: Lint                       (dimmed)


❌ FAILURES:
❌ Coverage: tests/unit/test_foo.py::test_bar:42
❌ Coverage: tests/unit/test_bar.py::test_baz:108
```

**Notes:**
- Completed subtasks and phases are displayed using ANSI dim styling (`\033[2m`) to de-emphasize past work
- Active progress uses ⏳ (hourglass) for passing tests to indicate "in progress", not ✅ which implies complete
- ❌ is used for failed tests even during active runs since failures are definitive
- ALL failures are displayed in real-time as they occur (not just recent 3)

### Benefits

1. **Clear visual hierarchy** - Tree symbols (├─ └─) show subtask relationships
2. **Obvious section headers** - 🔄 RUNNING, ✅ COMPLETED, 💤 PENDING are instantly recognizable
3. **Active task highlighted** - [ACTIVE] marker shows exactly what's running
4. **Breathing room** - Blank line separators between sections improve readability
5. **Real-time failure log** - Recent failures visible without waiting for final summary

## Display Structure

### Section 1: RUNNING Phase Header

```
🔄 RUNNING: Phase {num}/{total} - {phase_name}
```

### Section 2: Subtask Tree

- Uses tree box-drawing characters:
  - `├─` for all subtasks except the last
  - `└─` for the last subtask
- Three states for each subtask:
  - Completed: `├─ a. unit ✅`
  - Active: `└─ c. e2e [ACTIVE] Test 450/975 | ✅ 420 | ❌ 2`
  - Pending: `├─ d. analysis`

### Section 3: Blank Separator

Empty line for visual breathing room

### Section 4: Completed Phases

```
✅ COMPLETED: {phase1}, {phase2}, ...
```

### Section 5: Pending Phases

```
💤 PENDING: {phase3}, {phase4}, ...
```

### Section 6: Blank Separator

Empty line for visual breathing room

### Section 7: Timers

```
⏱️  {elapsed_time} | 🔄 {lap_time}
```

### Section 8: All Failures (if any)

```
(blank line)
❌ {phase}: {test_path}:{line}
❌ {phase}: {test_path}:{line}
...
```

Shows ALL failures as they occur in real-time

## Implementation Notes

### Tree Symbol Logic

```python
tree_symbol = "└─" if i == len(phase.subtasks) - 1 else "├─"
```

### Subtask Status Logic

- `i < current_subtask_idx` → Completed: `├─ {letter}. {name} ✅`
- `i == current_subtask_idx` → Active: `├─ {letter}. {name} [ACTIVE] {progress}`
- `i > current_subtask_idx` → Pending: `├─ {letter}. {name}`

### Progress Format (Active Subtask Only)

```
[ACTIVE] Test {current}/{total} | ✅ {passed} | ❌ {failed}
```

Only the active subtask shows detailed test progress. Completed subtasks just show ✅, pending subtasks show nothing.

## Comparison: Before vs After

### Before (3 lines, compressed)

```
Phase 2/5: [2.⏳ Coverage] | ✅ Lint | 💤 Docker, Script Tests, MCPB Validate
Coverage: ✅ a. unit | ✅ b. integration | [c. e2e] | d. analysis | e. validation
e2e tests [Test 450/975 | ✅ 420 | ❌ 2] | ⏱️  1m 23s | 🔄 12s
```

### After (8-10 lines, clear hierarchy)

```
🔄 RUNNING: Phase 2/5 - Coverage
  ├─ a. unit ✅
  ├─ b. integration ✅
  ├─ c. e2e [ACTIVE] Test 450/975 | ✅ 420 | ❌ 2
  ├─ d. analysis
  └─ e. validation

✅ COMPLETED: Lint
💤 PENDING: Docker, Script Tests, MCPB Validate

⏱️  1m 23s | 🔄 12s

❌ Coverage: tests/unit/test_elasticsearch_backend.py::test_connect_with_api_key:142
```

## Trade-offs

### Advantages

- **Instant comprehension** - At-a-glance understanding of test progress
- **Better failure visibility** - Errors appear immediately, not just at end
- **Professional appearance** - Tree structure looks polished
- **Reduced cognitive load** - Clear sections reduce mental parsing

### Disadvantages

- **More vertical space** - Takes ~8-10 lines vs 3-4 lines
- **Terminal scrolling** - On small terminals, may push previous output off screen
- **Slightly more code** - More complex formatting logic

## Design Alternatives Considered

1. **Box Around Current Phase** - Too busy with ╔═╗║╚═╝ characters
2. **Heavy Separators** - Too tall with ━━━━━ lines
3. **Compact Box** - Lost too much detail
4. **Minimal Hierarchy** - No tree symbols, harder to see relationships

**Selected: Tree Structure** - Best balance of clarity and compactness

## Implementation Location

**File:** `scripts/test-runner.py`
**Method:** `format_status_line()` (lines 121-206)

**New Helper:** `format_progress_string()` - Builds the progress portion for active subtasks

## Testing Checklist

- [ ] Tree structure renders correctly with ├─ and └─
- [ ] Active phase shows [ACTIVE] marker
- [ ] Completed phases show ✅
- [ ] Pending phases appear in correct section
- [ ] Progress updates in real-time
- [ ] Recent failures appear at bottom
- [ ] Layout works correctly across all 5 phases
- [ ] Intentional test failure shows in recent failures
- [ ] Timers update correctly (elapsed and lap)
- [ ] No visual glitches or rendering issues

## Future Enhancements

1. **Color coding** - Use ANSI colors for success/failure (green/red)
2. **Expandable details** - Show/hide failure details on demand
3. **Progress bars** - Visual progress bar for each phase
4. **Estimated time** - Show ETA for current phase
5. **Configurable verbosity** - Different detail levels via CLI flag
