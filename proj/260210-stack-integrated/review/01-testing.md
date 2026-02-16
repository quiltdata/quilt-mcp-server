# 01 - Code Coverage & Testing

**Date:** 2026-02-16  
**Reviewer:** Codex

## Commands Executed

- `make coverage`
- `uv run pytest --collect-only -m "not slow" | grep -E "(SKIPPED|XFAIL)" || true`
- `cat scripts/tests/coverage_required.yaml`
- `uv run python` ad-hoc analysis against `build/test-results/coverage-analysis.csv`
- `rg` scans across `tests/` for skip/xfail and mocking patterns

## Actual Coverage

- Combined project coverage (quality gate metric): **86.0%** (required: 55.0%)
- Unit coverage summary: **82.8%**
- Functional coverage summary: **28.5%**
- E2E coverage summary: **27.4%**

### Critical Paths Coverage (combined)

- `backends`: **82.1%** (1515/1845) ❌ below 90%
- `tools`: **89.7%** (2323/2591) ❌ below 90%
- `auth`: **88.9%** (56/63) ❌ below 90%

## Skipped/XFail Inventory

- `uv run pytest --collect-only ... | grep ...` returned no `SKIPPED`/`XFAIL` markers in output, but static scan shows runtime `pytest.skip(...)` usage in fixtures and e2e flows.
- One explicit decorator skip found:
  - `tests/e2e/backend/integration/test_cleanup_fixtures.py:72` (`@pytest.mark.skip(...)`)
- No `@pytest.mark.xfail` or `pytest.xfail(...)` found via `rg` scan.

## Integration Test Mocking Inventory

- `tests/func/` contains mock usage (`Mock/patch/monkeypatch`): **90** matches.
- `tests/e2e/` contains mock usage: **4** matches.
- Assessment: integration tests are mixed; functional tests still contain substantial mocking.

## E2E Local/Remote Mode Coverage

- E2E harness indicates dual-backend intent (`TEST_BACKEND_MODE=${TEST_BACKEND_MODE:-both}` in `make.dev`).
- Environment-gated skips are present for platform/remote auth and backend readiness in e2e fixtures.
- Assessment: local+remote paths exist, but execution in this run was not re-validated end-to-end due environment gating.

## Critical Gaps Identified

1. Critical-path coverage target (>=90%) is not met for backends/tools/auth.
2. Skip-heavy e2e/fixture behavior can mask environment regressions when prerequisites are absent.
3. Functional tests use extensive mocking in permission-related flows.

## Pass/Fail Status

- Overall coverage >=80%: ✅ Pass
- Critical paths >=90%: ❌ Fail
- No skipped tests in production paths: ⚠️ Warning (runtime/environment skips present)
- No xfail masking failures: ✅ Pass (none found)
- Integration tests minimal mocking: ⚠️ Warning
- E2E local+remote coverage: ⚠️ Warning (structure exists; runtime depends on env)
- CI/CD all tests pass: 🔍 Not verified in this section

**Section Result:** ⚠️ **Warning**
