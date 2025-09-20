<!-- markdownlint-disable MD013 -->
# Analysis — Issue #166 "improve coverage"

## Source References

- Requirements: `spec/2025-09-19-improve-coverage/01-requirements.md`
- Repository structure and tooling: `make.dev`, `Makefile`, `pyproject.toml`
- Test suites: `tests/unit`, `tests/integration`, `tests/e2e`, `scripts/test`

## Current Architecture & Test Landscape

1. **Language & Tooling**: Python project managed via `uv`. Pytest drives all automated tests with coverage via `--cov=quilt_mcp`. Ruff manages formatting, linting, and type checking.
2. **Test Suite Segmentation**:
   - `tests/unit/`: Fast, mocked tests covering modules like `auth`, `governance`, `visualization`, etc.
   - `tests/integration/`: Exercises AWS services (Athena, S3), permissions, and MCP server flows. Utilizes pytest markers (`aws`, `integration`).
   - `tests/e2e/`: Covers broader workflows (package management, search, migrations) mirroring real user journeys. Includes CLI-style scenarios and data fixture usage.
   - `scripts/test/`: Validates helper scripts such as coverage analysis utilities.
3. **Coverage Automation**:
   - `make.dev` orchestrates coverage via `make coverage`, running unit/integration/e2e suites sequentially and generating XML reports under `build/test-results/`.
   - HTML coverage reports generated with `make coverage-html` (output in `htmlcov/`).
   - `scripts/coverage_analysis.py` parses coverage artifacts for additional reporting.
4. **CI Integration**: `make.dev test-ci` enforces coverage through `--cov=quilt_mcp --cov-report=xml`. `coverage` target includes `--cov-fail-under=85`, establishing the current global threshold.
5. **Project Layout**:
   - Source code centered in `src/quilt_mcp/` with modular domains (auth, visualization, governance, etc.).
   - Deployment utilities live in `src/deploy/` and `scripts/`.
   - Extensive fixtures under `tests/fixtures/` supporting deterministic inputs for integration/E2E tests.

## Idioms & Conventions

1. **Behavior-Driven Tests**: Test names and docstrings focus on user-visible behavior (e.g., `test_quilt_tools.py`, `test_package_management.py`).
2. **Functional Style Helpers**: Test factories implemented as pure functions with optional overrides (`tests/fixtures/factories.py`, `tests/helpers.py`).
3. **Immutable Data Patterns**: Many modules favor dataclasses or typed dictionaries with minimal mutation.
4. **Coverage Validation Scripts**: Custom coverage parsing ensures reporting consistency (see `scripts/coverage_analysis.py`).
5. **Prefactoring Discipline**: Existing specs (e.g., `spec/141-fix-makefiles`) highlight iterative doc + implementation workflow; coverage expectations documented in `CLAUDE.md` and repository guides.

## Current Constraints & Limitations

1. **Baseline Coverage Unknown**: No persisted snapshot of current unit/integration/E2E coverage percentages; `htmlcov/` may be stale/out of sync.
2. **Integration/E2E Stability**: Some tests require AWS credentials or large fixtures; execution cost/time may hinder frequent runs locally.
3. **Coverage Aggregation**: While XML reports are generated per suite, there is no aggregated dashboard combining them (only script-based console output).
4. **CI Gate**: Single global `--cov-fail-under=85` does not distinguish between unit, integration, and E2E targets, limiting fine-grained enforcement.
5. **E2E Coverage Definition**: Current implementation of `tests/e2e/test_coverage.py` appears minimal, suggesting lack of clarity on measuring "coverage" for workflow tests beyond line coverage.
6. **Tooling Dependencies**: `uv sync --group test` required before running tests; missing dependencies or environment drift can slow iteration.

## Technical Debt & Opportunities

1. **Coverage Strategy Fragmentation**: Each suite writes its own coverage XML, but there is no automated merge or reporting pipeline; manual inspection required.
2. **Missing Guardrails**: Integration and E2E targets (50%, doubling) lack enforcement mechanisms; coverage gates only applied to total coverage.
3. **Limited Observability**: No mention of uploading coverage artifacts to external services (Codecov, Allure) for historical tracking.
4. **Fixture Bloat Risk**: Large fixture directories may slow coverage generation; opportunities exist for factory simplification or targeted sampling.
5. **Script Coverage Gaps**: `scripts/test` suite not integrated into coverage threshold check, potentially omitting critical logic from metrics.
6. **Flakiness Potential**: AWS-dependent tests might be flaky, complicating coverage increase efforts unless mocked alternatives or recorded responses are used.

## Gap Analysis vs Requirements

1. **Unit Coverage 85% Target**: Current enforcement already at 85%, but actual percentage may hover near threshold; need confirmed baseline and additional behavior tests to create buffer.
2. **Integration Coverage 50% Target**: No distinct threshold now; integration suite likely below 50% given complexity and environmental constraints.
3. **E2E Coverage Doubling**: Without defined metric, cannot measure doubling; likely requires establishing baseline metric (line coverage, scenario count, or instrumentation) and automation to track deltas.
4. **Reporting & Visibility**: Requirements call for reproducible reports and PR-level visibility; currently manual commands without gating per-suite metrics or PR comment bots.
5. **Stakeholder Confidence**: Documentation emphasizes coverage goals but lacks dashboards or CI annotations aligning with release manager expectations.

## Risks

1. **Performance/Time**: Increasing coverage, especially in integration/E2E tests, may significantly extend CI durations unless parallelization or selective execution is implemented.
2. **Complex Infrastructure**: Additional coverage instrumentation for E2E may demand environment setup (e.g., browser drivers, mock services) increasing maintenance overhead.
3. **Data Management**: Doubling E2E coverage may require new fixtures or datasets that must be curated and maintained.
4. **CI Fallback**: Tightening gates without addressing flakiness could block deployments.
5. **Knowledge Continuity**: Coverage tooling knowledge concentrated in scripts; documentation updates needed to onboard contributors.
