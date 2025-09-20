<!-- markdownlint-disable MD013 -->
# Phases — Issue #166 "improve coverage"

## Phase Overview

Coverage improvements will be delivered across three implementation phases, each culminating in a reviewable PR that targets specific coverage gaps while respecting TDD and prefactoring requirements.

### Phase 1 — Baseline & Guardrails

**Goal**: Establish accurate coverage baselines, define E2E coverage metric, and implement automated gates.

- Capture current coverage metrics via scripted run (`make coverage`) and persist results as baseline artifacts.
- Document how E2E coverage is quantified (line coverage vs scenario count) and incorporate instrumentation if needed.
- Enhance CI configuration to enforce per-suite thresholds (unit ≥85%, integration ≥50%, E2E ≥ baseline × 2 once achieved) with clear failure messaging.
- Update documentation (CLAUDE.md, developer guides) to reflect commands and gating policy.

### Phase 2 — Integration Coverage Expansion

**Goal**: Raise integration coverage to ≥50% through behavior-driven tests covering critical service interactions.

- Prefactor integration fixtures/utilities to simplify adding new scenarios.
- Add behavior tests focusing on high-risk workflows (S3 package operations, permissions, governance checks) driven by user stories.
- Ensure new tests are hermetic (mocked AWS interactions where possible) to maintain stability.
- Validate coverage increase and adjust instrumentation if gaps remain.

### Phase 3 — E2E Coverage Amplification & Unit Buffer

**Goal**: Double E2E coverage metric and establish ≥90% actual unit coverage for resilience.

- Identify under-tested user journeys (search, package lifecycle, governance enforcement) and add E2E scenarios via existing runner patterns.
- Strengthen unit suites for core modules affected by new E2E flows to reinforce coverage buffer.
- Confirm combined suite performance remains acceptable; optimize test runtime if necessary.
- Finalize reporting automation (e.g., PR comments summarizing coverage deltas) and ensure gates stay green.

## Phase Sequencing & Dependencies

1. **Phase 1** is prerequisite for all subsequent phases because it defines metrics and enforcement.
2. **Phase 2** depends on baseline data and gating from Phase 1 to measure progress accurately.
3. **Phase 3** leverages tooling and reporting established earlier to validate doubled coverage.

## Review & Integration Strategy

- After each phase, run `make coverage` and `make lint`, update CLAUDE.md with learnings, and push commits.
- Each phase yields independent PRs merged sequentially into the implementation branch (`impl/improve-coverage`) aligned with the spec history.
- PR reviews focus on behavior verification, coverage deltas, and test reliability.
