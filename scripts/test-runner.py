#!/usr/bin/env python3
"""
Test Runner TUI - Orchestrates all test phases with single-line progress updates.

Runs 5 phases of testing with hierarchical progress tracking:
1. Lint (ruff format, ruff check, mypy)
2. Coverage (unit, functional, e2e tests + analysis + validation)
3. Docker (check, build)
4. Script Tests (pytest scripts/tests + MCP server tests + MCP stateless)
5. MCPB Validate (check-tools, build, validate, UVX test)

Usage:
    python scripts/test-runner.py [--verbose] [--no-tui] [--phase PHASE [PHASE ...]]

Options:
    --verbose: Show full output (disables TUI)
    --no-tui: Disable TUI (show all output)
    --phase: Run specific phases only (by number 1-5 or name)

Examples:
    python scripts/test-runner.py --phase 1              # Run only lint
    python scripts/test-runner.py --phase lint docker   # Run lint and docker
    python scripts/test-runner.py --phase 1 3 5          # Run phases 1, 3, and 5
"""

import argparse
import csv
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from rich.live import Live


# Check if we should use TUI before importing rich
def should_use_tui() -> bool:
    """Determine if TUI should be enabled."""
    if not sys.stdout.isatty():
        return False
    if os.environ.get("CI") == "true":
        return False
    if "--verbose" in sys.argv or "--no-tui" in sys.argv:
        return False
    return True


USE_TUI = should_use_tui()

if USE_TUI:
    from rich.console import Console
    from rich.live import Live
    from rich.text import Text

    console = Console()
else:
    console = None  # type: ignore


# ANSI escape code regex for stripping color codes
ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_ESCAPE.sub('', text)


def read_coverage_summary(csv_path: str = "build/test-results/coverage-analysis.csv") -> Optional[float]:
    """Read overall coverage percentage from coverage analysis CSV.

    Returns:
        Combined coverage percentage from SUMMARY row, or None if not available
    """
    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('file') == 'SUMMARY':
                    # Extract combined_pct_covered column
                    combined_str = row.get('combined_pct_covered', '0')
                    return float(combined_str)
    except (FileNotFoundError, ValueError, KeyError):
        pass
    return None


@dataclass
class TestFailure:
    """Details of a test failure."""

    phase: str
    test_path: str
    line: Optional[int] = None


@dataclass
class PhaseStats:
    """Statistics for a phase."""

    name: str
    subtasks: list[str]
    subtask_test_counts: list[int] = field(default_factory=list)  # Expected test counts per subtask
    subtask_start_counts: list[int] = field(default_factory=list)  # Actual test count at start of each subtask
    current_subtask_idx: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0
    failures: list[TestFailure] = field(default_factory=list)
    error_lines: list[tuple[int, str]] = field(default_factory=list)  # (subtask_idx, error_line)
    completed: bool = False
    command_failed: bool = False  # Track if the phase command failed (non-zero exit)
    coverage_pct: Optional[float] = None  # Overall coverage percentage


@dataclass
class TestRunnerState:
    """State tracking for the entire test run."""

    start_time: float = field(default_factory=time.time)
    last_progress_time: float = field(default_factory=time.time)
    current_phase: int = 0
    phases: list[PhaseStats] = field(default_factory=list)
    selected_phases: set[int] = field(default_factory=set)  # Indices of phases to run (empty = all)
    total_passed: int = 0
    total_failed: int = 0
    all_failures: list[TestFailure] = field(default_factory=list)

    def elapsed_time(self) -> str:
        """Get formatted elapsed time."""
        elapsed = int(time.time() - self.start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        return f"{minutes}m {seconds}s"

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

    def current_phase_stats(self) -> Optional[PhaseStats]:
        """Get current phase statistics."""
        if 0 <= self.current_phase < len(self.phases):
            return self.phases[self.current_phase]
        return None

    def format_progress_string(self, phase: PhaseStats) -> str:
        """Format progress string for active subtask."""
        if phase.tests_total == 0:
            return ""

        # If we have per-subtask counts, show progress within current subtask
        if (
            phase.subtask_test_counts
            and phase.current_subtask_idx < len(phase.subtask_test_counts)
            and phase.current_subtask_idx < len(phase.subtask_start_counts)
        ):
            # Tests done at start of current subtask
            subtask_start = phase.subtask_start_counts[phase.current_subtask_idx]
            # Tests done in current subtask
            current_subtask_done = (phase.tests_passed + phase.tests_failed) - subtask_start
            # Expected total for current subtask
            current_subtask_total = phase.subtask_test_counts[phase.current_subtask_idx]

            # Only show test progress if subtask has measurable tests
            if current_subtask_total > 0:
                parts = [f"Test {current_subtask_done}/{current_subtask_total}"]
            else:
                parts = []  # No test progress for subtasks without test counts
        else:
            # Fallback: show cumulative across all phases
            prior_tests = sum(p.tests_passed + p.tests_failed for p in self.phases[: self.current_phase])
            current_test_num = prior_tests + phase.tests_passed + phase.tests_failed
            total_tests = sum(p.tests_total for p in self.phases)
            parts = [f"Test {current_test_num}/{total_tests}"]

        # Use hourglass for in-progress passing tests (not checkmark which implies done)
        if self.total_passed > 0:
            parts.append(f"⏳ {self.total_passed}")
        if self.total_failed > 0:
            parts.append(f"❌ {self.total_failed}")

        return " | ".join(parts)

    def format_status_line(self) -> str:
        """Format multi-line hierarchical status for TUI using tree structure."""
        lines = []
        phase = self.current_phase_stats()

        # Calculate phase number within selected phases
        selected_list = sorted(self.selected_phases) if self.selected_phases else list(range(len(self.phases)))
        if self.current_phase in selected_list:
            phase_num = selected_list.index(self.current_phase) + 1
        else:
            phase_num = self.current_phase + 1
        total_phases = len(selected_list)

        # ANSI codes
        DIM = "\033[2m"
        RESET = "\033[0m"

        # Section 1: RUNNING header with timers on same line
        if phase:
            elapsed = self.elapsed_time()
            lap = self.lap_time()
            lines.append(f"🔄 RUNNING: Phase {phase_num}/{total_phases} - {phase.name} ⏱️  {elapsed} | 🔄 {lap}")

            # Section 2: Tree structure for subtasks
            if phase.subtasks:
                letters = "abcdefghijklmnopqrstuvwxyz"
                for i, subtask in enumerate(phase.subtasks):
                    # Tree symbol: ├─ for middle items, └─ for last
                    tree_symbol = "└─" if i == len(phase.subtasks) - 1 else "├─"
                    letter = letters[i]

                    if i == phase.current_subtask_idx:
                        # Active subtask with full progress
                        progress = self.format_progress_string(phase)
                        if progress:
                            lines.append(f"  {tree_symbol} {letter}. {subtask} [ACTIVE] {progress}")
                        else:
                            lines.append(f"  {tree_symbol} {letter}. {subtask} [ACTIVE]")
                    elif i < phase.current_subtask_idx:
                        # Completed subtask (dimmed)
                        lines.append(f"{DIM}  {tree_symbol} {letter}. {subtask} ✅{RESET}")
                    else:
                        # Pending subtask
                        lines.append(f"  {tree_symbol} {letter}. {subtask}")

        # Section 3: Blank separator
        lines.append("")

        # Section 4: PENDING (forward-looking) - only show selected phases
        selected_set = self.selected_phases if self.selected_phases else set(range(len(self.phases)))
        pending = [p.name for i, p in enumerate(self.phases) if i > self.current_phase and i in selected_set]
        if pending:
            lines.append(f"💤 PENDING: {' | '.join(pending)}")

        # Section 5: COMPLETED (past) - dimmed, only show selected phases
        completed = [p.name for i, p in enumerate(self.phases) if i < self.current_phase and i in selected_set]
        if completed:
            lines.append(f"{DIM}✅ COMPLETED: {' | '.join(completed)}{RESET}")

        # Section 6: All errors and skipped tests grouped by phase and subtask (expanding list at bottom)
        has_errors = any(phase.error_lines for phase in self.phases)

        if has_errors:
            lines.append("")
            lines.append("🔍 ERRORS & SKIPPED:")
            for phase in self.phases:
                if phase.error_lines:
                    # Group errors by subtask
                    errors_by_subtask: dict[int, list[str]] = {}
                    for subtask_idx, error_line in phase.error_lines:
                        if subtask_idx not in errors_by_subtask:
                            errors_by_subtask[subtask_idx] = []
                        errors_by_subtask[subtask_idx].append(error_line)

                    # Display errors grouped by subtask
                    for subtask_idx in sorted(errors_by_subtask.keys()):
                        subtask_name = phase.subtasks[subtask_idx] if subtask_idx < len(phase.subtasks) else "unknown"
                        lines.append(f"  [{phase.name} → {subtask_name}]")
                        for error_line in errors_by_subtask[subtask_idx]:
                            lines.append(f"    {error_line}")

        return "\n".join(lines)


def collect_test_count(pytest_args: list[str]) -> int:
    """Run pytest --collect-only to count tests."""
    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "--collect-only", "-q"] + pytest_args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Parse output like "1146 tests collected in 0.31s"
        match = re.search(r'(\d+) tests? collected', result.stdout)
        if match:
            return int(match.group(1))
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass
    return 0


def init_phases() -> list[PhaseStats]:
    """Initialize all test phases with dynamic test counts."""
    print("📊 Collecting test counts...")

    # Collect per-subtask test counts
    unit_count = collect_test_count(["tests/unit"])
    func_count = collect_test_count(["tests/func"])
    e2e_count = collect_test_count(["tests/e2e"])
    coverage_count = unit_count + func_count + e2e_count

    scripts_count = collect_test_count(["scripts/tests/"])

    print(f"   Unit: {unit_count} | Functional: {func_count} | E2E: {e2e_count}")
    print(f"   Scripts: {scripts_count}")

    return [
        PhaseStats(
            name="Lint",
            subtasks=["ruff format", "ruff check", "mypy"],
            tests_total=0,
        ),
        PhaseStats(
            name="Coverage",
            subtasks=["unit", "functional", "e2e", "analysis", "validation"],
            subtask_test_counts=[unit_count, func_count, e2e_count, 0, 0],
            tests_total=coverage_count,
        ),
        PhaseStats(
            name="Docker",
            subtasks=["docker-check", "docker-build"],
            tests_total=0,
        ),
        PhaseStats(
            name="Script Tests",
            subtasks=["pytest scripts", "mcp-test"],
            subtask_test_counts=[scripts_count, 0],  # Only pytest scripts reports test counts
            tests_total=scripts_count,  # Just pytest scripts count (MCP tests reported differently)
        ),
        PhaseStats(
            name="MCPB Validate",
            subtasks=["check-tools", "mcpb build", "mcpb validate"],
            tests_total=0,
        ),
    ]


def parse_pytest_output(line: str, state: TestRunnerState) -> None:
    """Parse pytest output for test results."""
    phase = state.current_phase_stats()
    if not phase:
        return

    # Match test results: PASSED, FAILED, SKIPPED
    if " PASSED" in line or "::test_" in line:
        if "PASSED" in line:
            phase.tests_passed += 1
            state.total_passed += 1
            state.reset_lap_timer()
        elif "FAILED" in line:
            phase.tests_failed += 1
            state.total_failed += 1
            state.reset_lap_timer()
            # Extract full test path including function name
            # Match patterns like: tests/unit/test_file.py::TestClass::test_method FAILED
            match = re.search(r"(tests/[^:]+::[^\s]+)", line)
            if match:
                test_path = match.group(1)
                line_match = re.search(r"line (\d+)", line)
                line_num = int(line_match.group(1)) if line_match else None
                failure = TestFailure(phase=phase.name, test_path=test_path, line=line_num)
                phase.failures.append(failure)
                state.all_failures.append(failure)

    # Match pytest summary line
    match = re.search(r"(\d+) passed", line)
    if match:
        passed = int(match.group(1))
        # Update if we got summary
        if passed > phase.tests_passed:
            phase.tests_passed = passed
            state.total_passed = sum(p.tests_passed for p in state.phases)
            state.reset_lap_timer()

    match = re.search(r"(\d+) failed", line)
    if match:
        failed = int(match.group(1))
        if failed > phase.tests_failed:
            phase.tests_failed = failed
            state.total_failed = sum(p.tests_failed for p in state.phases)
            state.reset_lap_timer()


def parse_subtask_transition(line: str, state: TestRunnerState) -> None:
    """Detect subtask transitions in output."""
    phase = state.current_phase_stats()
    if not phase:
        return

    old_subtask_idx = phase.current_subtask_idx

    # Lint phase transitions
    if phase.name == "Lint":
        if "Running ruff format" in line or "ruff format" in line:
            phase.current_subtask_idx = 0
        elif "Running ruff check" in line or "ruff check" in line:
            phase.current_subtask_idx = 1
        elif "Running mypy" in line or "mypy" in line:
            phase.current_subtask_idx = 2

    # Coverage phase transitions
    elif phase.name == "Coverage":
        if "unit" in line.lower() and "test" in line.lower():
            phase.current_subtask_idx = 0
        elif ("functional" in line.lower() or "func" in line.lower()) and "test" in line.lower():
            phase.current_subtask_idx = 1
        elif "e2e" in line.lower() or "end-to-end" in line.lower():
            phase.current_subtask_idx = 2
        elif "coverage analysis" in line.lower():
            phase.current_subtask_idx = 3
        elif "validating" in line.lower() and "coverage" in line.lower():
            phase.current_subtask_idx = 4

    # Docker phase transitions
    elif phase.name == "Docker":
        if "docker" in line.lower() and "available" in line.lower():
            phase.current_subtask_idx = 0
        elif "building docker" in line.lower() or "docker build" in line.lower():
            phase.current_subtask_idx = 1

    # Script Tests phase
    elif phase.name == "Script Tests":
        if "pytest scripts" in line.lower():
            phase.current_subtask_idx = 0
        elif "mcp-test" in line.lower() or ("mcp" in line.lower() and "test" in line.lower()):
            phase.current_subtask_idx = 1

    # MCPB Validate phase
    elif phase.name == "MCPB Validate":
        if "check-tools" in line or "checking" in line.lower():
            phase.current_subtask_idx = 0
        elif "mcpb build" in line or "building" in line.lower():
            phase.current_subtask_idx = 1
        elif "mcpb validate" in line or "validating" in line.lower():
            phase.current_subtask_idx = 2

    # Record test count at start of new subtask if subtask changed
    if phase.current_subtask_idx != old_subtask_idx:
        # Ensure subtask_start_counts list is large enough
        while len(phase.subtask_start_counts) <= phase.current_subtask_idx:
            phase.subtask_start_counts.append(0)
        # Record current test count at start of this subtask
        phase.subtask_start_counts[phase.current_subtask_idx] = phase.tests_passed + phase.tests_failed
        state.reset_lap_timer()


def run_command(cmd: list[str], state: TestRunnerState, live: Optional["Live"] = None) -> int:
    """Run a command and update state from output."""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    assert process.stdout is not None

    # Start background thread to refresh display periodically
    stop_refresh = threading.Event()
    refresh_thread = None

    def refresh_display() -> None:
        """Background thread to update display every 0.5 seconds."""
        while not stop_refresh.is_set():
            if live and USE_TUI:
                try:
                    status_line = state.format_status_line()
                    live.update(Text(status_line))
                except Exception:
                    pass  # Ignore errors during shutdown
            time.sleep(0.5)

    if USE_TUI and live:
        refresh_thread = threading.Thread(target=refresh_display, daemon=True)
        refresh_thread.start()

    # Process output
    for line in iter(process.stdout.readline, ""):
        line = line.rstrip()

        # Always parse output for statistics tracking (regardless of TUI mode)
        parse_subtask_transition(line, state)
        parse_pytest_output(line, state)

        # Capture error-related lines
        phase = state.current_phase_stats()
        if phase:
            # Strip ANSI color codes for reliable pattern matching
            line_clean = strip_ansi(line)

            # Check for pytest status indicators first (these take precedence)
            is_passing_test = " PASSED " in line_clean or line_clean.endswith(" PASSED") or "PASSED [" in line_clean
            is_skipped_test = " SKIPPED " in line_clean or line_clean.endswith(" SKIPPED") or "SKIPPED [" in line_clean

            # Flag as notable if:
            # - Contains error keywords AND is not a passing test, OR
            # - Is a skipped test (important to see what's being skipped)
            error_keywords = [
                "FAILED",
                "ERROR",
                "Error",
                "Traceback",
                "AssertionError",
                "Exception",
                "make: ***",  # Make errors
                "bash: ",
                "sh: ",  # Shell errors
                "command not found",  # Command errors
                "No rule to make",  # Make target missing
                "fatal:",  # Git and other fatal errors
            ]
            has_error_keyword = any(keyword in line_clean for keyword in error_keywords)
            is_notable = (has_error_keyword and not is_passing_test) or is_skipped_test

            if is_notable:
                # Add to error list with subtask info (no limit - show all errors and skipped tests)
                phase.error_lines.append((phase.current_subtask_idx, line))

        # Display output (only in non-TUI mode)
        if not USE_TUI:
            print(line, flush=True)

    process.wait()

    # Stop refresh thread
    if refresh_thread:
        stop_refresh.set()
        refresh_thread.join(timeout=1.0)

    return process.returncode


def print_summary(state: TestRunnerState, exit_code: int) -> None:
    """Print final summary of test run."""
    if USE_TUI:
        print("\n")  # Extra newline after TUI

    # Determine which phases to show
    selected_set = state.selected_phases if state.selected_phases else set(range(len(state.phases)))

    # Count phases passed/failed
    phases_passed = sum(
        1
        for i, p in enumerate(state.phases)
        if i in selected_set and p.completed and p.tests_failed == 0 and not p.command_failed
    )
    phases_total = len(selected_set)

    # Check if any selected phase had command failures
    any_command_failures = any(p.command_failed for i, p in enumerate(state.phases) if i in selected_set)

    # Header: Phase count summary
    if exit_code == 0 and state.total_failed == 0 and not any_command_failures:
        print(f"✅ {phases_passed}/{phases_total} Phases passed\n")
    else:
        print(f"❌ {phases_passed}/{phases_total} Phases passed\n")

    # Hierarchical breakdown of each phase
    for i, phase in enumerate(state.phases):
        if i not in selected_set:
            continue

        display_num = i + 1
        phase_failed = phase.tests_failed > 0 or phase.command_failed

        # Phase header
        if phase.tests_total > 0:
            status = "❌" if phase_failed else "✅"
            header = f"  Phase {display_num}: {phase.name:20} {status} {phase.tests_passed}/{phase.tests_total} tests"
            # Add coverage percentage for Coverage phase
            if phase.name == "Coverage" and phase.coverage_pct is not None:
                header += f" | 📊 {phase.coverage_pct:.1f}% coverage"
            print(header)
        else:
            tasks = len(phase.subtasks)
            status = "❌" if phase_failed else "✅"
            print(f"  Phase {display_num}: {phase.name:20} {status} {tasks}/{tasks} tasks")

        # Subtask breakdown
        if phase.subtasks:
            # Group errors by subtask for easy lookup
            errors_by_subtask: dict[int, list[str]] = {}
            for subtask_idx, error_line in phase.error_lines:
                if subtask_idx not in errors_by_subtask:
                    errors_by_subtask[subtask_idx] = []
                errors_by_subtask[subtask_idx].append(error_line)

            for subtask_idx, subtask in enumerate(phase.subtasks):
                has_errors = subtask_idx in errors_by_subtask
                status = "❌" if has_errors else "✅"
                print(f"           → {subtask:15} {status}")

                # Show errors indented under the failing subtask
                if has_errors:
                    for error_line in errors_by_subtask[subtask_idx]:
                        print(f"             {error_line}")

        # Show test failures (from pytest)
        if phase.failures:
            for failure in phase.failures:
                line_info = f":{failure.line}" if failure.line else ""
                print(f"             • {failure.test_path}{line_info}")

        print()  # Blank line between phases

    # Footer: Total summary
    total_passed = sum(p.tests_passed for i, p in enumerate(state.phases) if i in selected_set)
    total_failed = sum(p.tests_failed for i, p in enumerate(state.phases) if i in selected_set)
    total_tasks = sum(len(p.subtasks) for i, p in enumerate(state.phases) if i in selected_set and p.tests_total == 0)

    summary_parts = []
    if total_passed > 0:
        summary_parts.append(f"{total_passed} tests passed")
    if total_failed > 0:
        summary_parts.append(f"{total_failed} failed")
    if total_tasks > 0:
        summary_parts.append(f"{total_tasks} tasks completed")

    if summary_parts:
        print(f"  Total: {', '.join(summary_parts)}")
    else:
        print(f"  Total: All phases completed")

    if exit_code != 0 and not USE_TUI:
        print("\n  Run with --verbose for full command output")


def run_phase(phase_idx: int, cmd: list[str], state: TestRunnerState, live: Optional["Live"] = None) -> int:
    """Run a single test phase."""
    state.current_phase = phase_idx
    phase = state.phases[phase_idx]

    # Initialize subtask_start_counts for first subtask
    if not phase.subtask_start_counts:
        phase.subtask_start_counts = [0]  # First subtask starts at 0

    if not USE_TUI:
        print(f"\n{'=' * 80}")
        print(f"Phase {phase_idx + 1}/5: {phase.name}")
        print(f"{'=' * 80}\n")

    # Reset lap timer at start of new phase
    state.reset_lap_timer()
    exit_code = run_command(cmd, state, live)
    phase.completed = True

    # Track command failure
    if exit_code != 0:
        phase.command_failed = True

    # Read coverage summary for Coverage phase
    if phase.name == "Coverage":
        phase.coverage_pct = read_coverage_summary()

    return exit_code


def parse_phase_selection(phase_arg: list[str], available_phases: list[PhaseStats]) -> set[int]:
    """Parse phase selection from command line arguments.

    Args:
        phase_arg: List of phase identifiers (numbers 1-5 or names)
        available_phases: List of available phase stats

    Returns:
        Set of 0-based phase indices to run
    """
    if not phase_arg:
        # Run all phases
        return set(range(len(available_phases)))

    # Map phase names to indices (case-insensitive)
    name_to_idx = {p.name.lower().replace(" ", "-"): i for i, p in enumerate(available_phases)}
    name_to_idx.update({p.name.lower(): i for i, p in enumerate(available_phases)})

    selected = set()
    for item in phase_arg:
        item_lower = item.lower()
        # Try as number (1-indexed)
        if item.isdigit():
            idx = int(item) - 1  # Convert to 0-based
            if 0 <= idx < len(available_phases):
                selected.add(idx)
            else:
                print(f"Warning: Phase number {item} out of range (1-{len(available_phases)}), ignoring")
        # Try as name
        elif item_lower in name_to_idx:
            selected.add(name_to_idx[item_lower])
        else:
            print(f"Warning: Unknown phase '{item}', ignoring")
            print(f"  Valid options: 1-{len(available_phases)} or {', '.join(p.name for p in available_phases)}")

    return selected if selected else set(range(len(available_phases)))


def main() -> int:
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(
        description="Run all test phases with TUI",
        epilog="Phase names: lint, coverage, docker, script-tests (or 'script tests'), mcpb-validate",
    )
    parser.add_argument("--verbose", action="store_true", help="Show full output")
    parser.add_argument("--no-tui", action="store_true", help="Disable TUI")
    parser.add_argument(
        "--phase",
        nargs="+",
        metavar="PHASE",
        help="Run specific phases only (by number 1-5 or name, e.g., --phase 1 3 or --phase lint coverage)",
    )
    args = parser.parse_args()

    # Initialize state
    all_phases = init_phases()

    # Parse phase selection
    selected_phase_indices = parse_phase_selection(args.phase or [], all_phases)

    # Initialize state with selected phases
    state = TestRunnerState(phases=all_phases, selected_phases=selected_phase_indices)

    # Prepare commands for each phase
    # Note: We call make targets directly to leverage existing build system
    # Some targets have dependencies that will run automatically
    base_make = ["make", "-s"]  # Silent make to reduce noise

    # Build results directory path
    results_dir = "build/test-results"
    os.makedirs(results_dir, exist_ok=True)

    all_phases_cmds = [
        (0, base_make + ["lint"]),
        (1, base_make + ["coverage"]),  # Runs unit + functional + e2e + analysis + validation
        (2, base_make + ["docker-build"]),  # Includes docker-check as dependency
        # Phase 4: Run test-scripts components - pytest scripts + MCP tests
        (
            3,
            [
                "bash",
                "-c",
                'export PYTHONPATH="src" && uv run python -m pytest scripts/tests/ -v && make -s mcp-test',
            ],
        ),
        (4, base_make + ["mcpb-validate"]),
    ]

    # Filter phases based on selection
    phases_cmds = [(idx, cmd) for idx, cmd in all_phases_cmds if idx in selected_phase_indices]

    if not phases_cmds:
        print("Error: No valid phases selected")
        return 1

    # Show which phases will run
    if args.phase:
        phase_names = [all_phases[idx].name for idx, _ in phases_cmds]
        print(f"📋 Running phases: {', '.join(phase_names)}\n")

    exit_code = 0

    if USE_TUI:
        # Run with TUI
        with Live(Text("Starting test run..."), console=console, refresh_per_second=2) as live:
            for phase_idx, cmd in phases_cmds:
                code = run_phase(phase_idx, cmd, state, live)
                if code != 0 and exit_code == 0:
                    exit_code = code
                    # Continue running remaining phases to collect all failures

            # Show final status with all errors visible
            final_status = state.format_status_line()
            live.update(Text(final_status))
    else:
        # Run without TUI
        for phase_idx, cmd in phases_cmds:
            code = run_phase(phase_idx, cmd, state, None)
            if code != 0 and exit_code == 0:
                exit_code = code

        # Print summary only in non-TUI mode
        print_summary(state, exit_code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
