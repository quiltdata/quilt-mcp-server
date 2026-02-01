#!/usr/bin/env python3
"""
Test Runner TUI - Orchestrates all test phases with single-line progress updates.

Runs 5 phases of testing with hierarchical progress tracking:
1. Lint (ruff format, ruff check, mypy)
2. Coverage (unit, integration, e2e tests + analysis + validation)
3. Docker (check, build)
4. Script Tests (pytest scripts/tests + MCP integration tests)
5. MCPB Validate (check-tools, build, validate, UVX test)

Usage:
    python scripts/test-runner.py [--verbose] [--no-tui]

Options:
    --verbose: Show full output (disables TUI)
    --no-tui: Disable TUI (show all output)
"""

import argparse
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
    current_subtask_idx: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0
    failures: list[TestFailure] = field(default_factory=list)
    completed: bool = False


@dataclass
class TestRunnerState:
    """State tracking for the entire test run."""

    start_time: float = field(default_factory=time.time)
    last_progress_time: float = field(default_factory=time.time)
    current_phase: int = 0
    phases: list[PhaseStats] = field(default_factory=list)
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

    def format_status_line(self) -> str:
        """Format three-line hierarchical status for TUI."""
        lines = []

        # Line 1: Active phase | Completed | Pending
        phase = self.current_phase_stats()
        phase_num = self.current_phase + 1
        total_phases = len(self.phases)

        active = f"[{phase_num}.⏳ {phase.name}]" if phase else ""

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

        lines.append(f"Phase {phase_num}/{total_phases}: {phase_line}")

        # Line 2: Current phase subtasks
        if phase and phase.subtasks:
            subtask_parts = []
            letters = "abcdefghijklmnopqrstuvwxyz"
            for i, subtask in enumerate(phase.subtasks):
                if i == phase.current_subtask_idx:
                    subtask_parts.append(f"[{letters[i]}. {subtask}]")
                elif i < phase.current_subtask_idx:
                    subtask_parts.append(f"✅ {letters[i]}. {subtask}")
                else:
                    subtask_parts.append(f"{letters[i]}. {subtask}")

            lines.append(f"{phase.name}: {' | '.join(subtask_parts)}")
        elif phase:
            lines.append(f"{phase.name}")

        # Line 3: Current subtask details with cumulative progress and timers
        if phase:
            letters = "abcdefghijklmnopqrstuvwxyz"
            current_letter = (
                letters[phase.current_subtask_idx] if phase.current_subtask_idx < len(phase.subtasks) else ""
            )
            current_subtask = (
                phase.subtasks[phase.current_subtask_idx] if phase.current_subtask_idx < len(phase.subtasks) else ""
            )

            progress = ""
            if phase.tests_total > 0:
                # Calculate cumulative position across ALL phases
                prior_tests = sum(p.tests_passed + p.tests_failed for p in self.phases[:self.current_phase])
                current_test_num = prior_tests + phase.tests_passed + phase.tests_failed
                total_tests = sum(p.tests_total for p in self.phases)

                progress = f"[Test {current_test_num}/{total_tests}"
                if self.total_passed > 0:
                    progress += f" | ✅ {self.total_passed} passed"
                if self.total_failed > 0:
                    progress += f" | ❌ {self.total_failed} failed"
                progress += "]"

            lap = self.lap_time()
            if current_subtask:
                lines.append(f"{current_subtask} {progress} | ⏱️  {self.elapsed_time()} | 🔄 {lap}")
            else:
                lines.append(f"⏱️  {self.elapsed_time()} | 🔄 {lap}")
        else:
            lines.append(f"⏱️  {self.elapsed_time()}")

        return "\n".join(lines)


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
            # Extract test path
            match = re.search(r"(tests/[^:]+)::", line)
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
        elif "integration" in line.lower() and "test" in line.lower():
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
        elif "mcp" in line.lower() and "integration" in line.lower():
            phase.current_subtask_idx = 1

    # MCPB Validate phase
    elif phase.name == "MCPB Validate":
        if "check-tools" in line or "checking" in line.lower():
            phase.current_subtask_idx = 0
        elif "mcpb build" in line or "building" in line.lower():
            phase.current_subtask_idx = 1
        elif "mcpb validate" in line or "validating" in line.lower():
            phase.current_subtask_idx = 2

    # Reset lap timer if subtask changed
    if phase.current_subtask_idx != old_subtask_idx:
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

        if not USE_TUI:
            print(line, flush=True)
        else:
            # Parse line for state updates
            parse_subtask_transition(line, state)
            parse_pytest_output(line, state)

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

    # Show phase overview
    phase_line = []
    for i, phase in enumerate(state.phases, 1):
        if phase.completed and phase.tests_failed == 0:
            phase_line.append(f"{i}.✅ {phase.name}")
        elif phase.tests_failed > 0:
            phase_line.append(f"{i}.❌ {phase.name}")
        else:
            phase_line.append(f"{i}.💤 {phase.name}")

    print("  ".join(phase_line))
    print()

    if exit_code == 0 and state.total_failed == 0:
        print(f"✅ All phases completed successfully in {state.elapsed_time()}\n")

        for i, phase in enumerate(state.phases, 1):
            if phase.tests_total > 0:
                print(f"  Phase {i}: {phase.name:20} ✅ {phase.tests_passed}/{phase.tests_total} tests")
                if phase.subtasks:
                    for subtask in phase.subtasks:
                        print(f"           → {subtask:15} ✅")
            else:
                tasks = len(phase.subtasks)
                print(f"  Phase {i}: {phase.name:20} ✅ {tasks}/{tasks} tasks")

        print(f"\n  Total: {state.total_passed} tests passed, 0 failed")
    else:
        print(f"❌ Test suite failed in {state.elapsed_time()}\n")

        if state.all_failures:
            for phase in state.phases:
                if phase.failures:
                    print(f"  {phase.name} - ❌ {len(phase.failures)} failed:")
                    for failure in phase.failures:
                        line_info = f":{failure.line}" if failure.line else ""
                        print(f"    • {failure.test_path}{line_info}")
                    print()

        print(f"  Total: {state.total_passed} passed, {state.total_failed} failed")
        print("\n  Run with --verbose for full output")


def run_phase(phase_idx: int, cmd: list[str], state: TestRunnerState, live: Optional["Live"] = None) -> int:
    """Run a single test phase."""
    state.current_phase = phase_idx
    phase = state.phases[phase_idx]

    if not USE_TUI:
        print(f"\n{'=' * 80}")
        print(f"Phase {phase_idx + 1}/5: {phase.name}")
        print(f"{'=' * 80}\n")

    # Reset lap timer at start of new phase
    state.reset_lap_timer()
    exit_code = run_command(cmd, state, live)
    phase.completed = True
    return exit_code


def main() -> int:
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(description="Run all test phases with TUI")
    parser.add_argument("--verbose", action="store_true", help="Show full output")
    parser.add_argument("--no-tui", action="store_true", help="Disable TUI")
    args = parser.parse_args()

    # Initialize state
    state = TestRunnerState(phases=init_phases())

    # Prepare commands for each phase
    # Note: We call make targets directly to leverage existing build system
    # Some targets have dependencies that will run automatically
    base_make = ["make", "-s"]  # Silent make to reduce noise

    # Build results directory path
    results_dir = "build/test-results"
    os.makedirs(results_dir, exist_ok=True)

    phases_cmds = [
        (0, base_make + ["lint"]),
        (1, base_make + ["coverage"]),  # Runs unit + integration + e2e + analysis + validation
        (2, base_make + ["docker-build"]),  # Includes docker-check as dependency
        # Phase 4: Run test-scripts components - pytest scripts + MCP tests
        (
            3,
            [
                "bash",
                "-c",
                'export PYTHONPATH="src" && '
                'uv run python -m pytest scripts/tests/ -v && '
                'echo "\\n===🧪 Running MCP server integration tests (idempotent only)..." && '
                'uv run python scripts/tests/test_mcp.py --docker --image quilt-mcp:test',
            ],
        ),
        (4, base_make + ["mcpb-validate"]),
    ]

    exit_code = 0

    if USE_TUI:
        # Run with TUI
        with Live(Text("Starting test run..."), console=console, refresh_per_second=2) as live:
            for phase_idx, cmd in phases_cmds:
                code = run_phase(phase_idx, cmd, state, live)
                if code != 0 and exit_code == 0:
                    exit_code = code
                    # Continue running remaining phases to collect all failures

            # Show final status
            live.update(Text(f"✅ Test run completed in {state.elapsed_time()}"))
    else:
        # Run without TUI
        for phase_idx, cmd in phases_cmds:
            code = run_phase(phase_idx, cmd, state, None)
            if code != 0 and exit_code == 0:
                exit_code = code

    # Print summary
    print_summary(state, exit_code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
