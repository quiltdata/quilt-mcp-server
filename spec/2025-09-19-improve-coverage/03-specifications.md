<!-- markdownlint-disable MD013 -->
# Specifications — Issue #166 "improve coverage"

## Vision & Scope
Deliver a measurable, automated coverage program that meets or exceeds the issue-mandated thresholds (unit ≥85%, integration ≥50%, E2E coverage doubled) while preserving the repository's TDD-first philosophy and keeping the CI pipeline reliable.

## Behavioral Outcomes
1. **Coverage Targets Enforced**
   - Unit suite maintains ≥85% line coverage with a 5% buffer (i.e., actual ≥90%) to prevent regressions.
   - Integration suite reports ≥50% coverage using the same measurement methodology as unit tests.
   - E2E suite doubles its existing coverage metric (baseline captured before implementation; success = baseline × 2 or higher).
2. **Automated Gates**
   - CI fails if any suite's coverage slips below its threshold.
   - Local developers receive the same failure signal using a single documented command.
3. **Transparent Reporting**
   - Coverage reports (XML + HTML) stored in predictable locations (`build/test-results`, `htmlcov`) with timestamped artifacts.
   - PRs display coverage summaries for each suite (unit/integration/E2E) and the combined total.
4. **Incremental Safety**
   - Tests validating new coverage remain behavior-focused, avoiding white-box assertions.
   - Additional tests do not introduce flakiness; nightly/CI runs remain stable.
5. **Documentation & Onboarding**
   - CLAUDE.md and developer docs reference updated commands, thresholds, and troubleshooting steps.

## Engineering Constraints
1. Retain existing tooling stack (`pytest`, `coverage.py`, `uv`, `make.dev`) without introducing external SaaS dependencies.
2. Ensure make targets remain idempotent and runnable in sandboxed CI environments.
3. Avoid altering historical specs or unrelated modules beyond what coverage improvements require.
4. Preserve deterministic test data by extending existing factories/fixtures rather than creating ad-hoc datasets.
5. Maintain compatibility with restricted network environments (no online downloads during test execution).

## Success Criteria
1. All acceptance criteria from requirements satisfied (coverage thresholds, reproducible outputs, CI gating).
2. Coverage deltas visible in PR checks (text summary or artifact link) with clear pass/fail signals.
3. No increase in flaky test rate over two consecutive CI runs after rollout.
4. Documentation updates merged alongside implementation to prevent knowledge gaps.

## Non-Goals
1. Replacing the current coverage tooling or switching to alternate test frameworks.
2. Delivering performance optimizations beyond what is needed to keep CI within acceptable limits.
3. Building dashboards outside the repository (e.g., hosted coverage services).
4. Addressing unrelated refactors unless required to enable coverage improvements.

## Open Decisions
1. **E2E Coverage Metric Definition**: Determine whether to track Python line coverage, scenario completion counts, or a custom metric (e.g., "critical user flows executed").
2. **Coverage Baseline Capture**: Decide on the source of truth for current coverage figures (latest `make coverage` run, CI artifact, etc.).
3. **PR Reporting Mechanism**: Choose between extending existing scripts, adding CI job steps, or embedding summary output in GitHub Actions logs.
4. **Test Execution Strategy**: Determine if suites should be parallelized or filtered to keep runtime acceptable after adding coverage tests.

