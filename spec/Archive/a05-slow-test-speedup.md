<!-- markdownlint-disable MD013 -->
# Slow Test Speedup Opportunities

## Scope

- `tests/integration/test_athena_glue.py`
- `tests/integration/test_athena_integration.py`
- `tests/e2e/test_package_management.py`

All tests listed above are marked with `pytest.mark.slow` and must continue to execute real AWS network calls. This document captures options for reducing runtime by reusing setup work and trimming duplicated effort without sacrificing integration coverage.

## Current Pain Points

- Multiple top-level tool functions create a fresh `AthenaQueryService`, forcing redundant STS credentials checks, workgroup discovery, and SQLAlchemy engine creation.
- Slow classes reissue identical AWS requests within the same test class, even when a shared response would cover every assertion branch.
- `TestAthenaPerformance` spawns threads that each bootstrap a new service instance, multiplying setup costs before the actual query runs.
- `create_package_enhanced` auto-detects a registry during the E2E migration test, triggering a full permission discovery crawl through `bucket_recommendations_get`.
- Guard helpers (for example `skip_if_no_aws_credentials`) do not fully skip when credentials are absent, so pytest still pays connection penalties on failure paths.

## Proposed Optimizations

1. **Cached Athena Service Fixture**
   - Introduce a `@pytest.fixture(scope="session")` that returns a cached `AthenaQueryService` (potentially via `functools.lru_cache`).
   - Update slow tests that currently call the module-level helpers to accept an injected service so only the first call per session performs the expensive bootstrap while later calls reuse the live connection.

2. **Response-Sharing Fixtures**
   - For each integration class, add class-scoped fixtures that make the initial live AWS call (e.g., `athena_databases_list`) and memoize the response dictionary.
   - Rewrite individual tests to, where appropriate, consume the shared fixture instead of calling the network function repeatedly. Assertions still exercise the real payload but avoid duplicate requests.

3. **Threaded Performance Tests**
   - When testing concurrency, seed threads with the shared service fixture rather than constructing new services inside each thread.
   - Maintain the real AWS workload by allowing each thread to issue its own query through the shared engine.

4. **E2E Registry Detection**
   - Pass an explicit `registry` argument in `TestPackageManagementMigration` or pre-seed the permission discovery cache through a fixture so that only one real discovery call occurs.

5. **Helper Reliability**
   - Restore `pytest.skip` in `skip_if_no_aws_credentials` to ensure environments without credentials bypass the AWS calls instead of repeatedly attempting and printing errors.

## Validation Plan

- Measure baseline durations with `UV_CACHE_DIR=.uv_cache uv run pytest tests/integration tests/e2e/test_package_management.py --maxfail=1 --durations=10`.
- Implement fixtures and caching, then rerun the same command to verify time improvements while confirming AWS calls still occur (inspect CloudTrail or log count of executed queries).
- Confirm no test moves off the network path by temporarily injecting telemetry (e.g., counting calls to `AthenaQueryService.execute_query`).

## Risks & Mitigations

- **Risk:** Cached service masks credential expiration between tests.
  - *Mitigation:* Keep TTL-based cache (already present in service) and document manual cache invalidation for long-running suites.
- **Risk:** Sharing responses could hide flakiness caused by multiple network invocations.
  - *Mitigation:* Leave at least one test per behaviour that re-issues the call to detect intermittent failures; rely on session-level fixture to keep total count low.
- **Risk:** Pre-seeding registry recommendations might diverge from production behaviour.
  - *Mitigation:* Use real discovery once per run and cache the result, rather than stubbing or mocking the response.

## Open Questions

- Should the Athena service cache live inside the production module (`athena_glue`) to aid interactive users, or stay test-only?
- Is it acceptable to log AWS query IDs during tests for telemetry (helps ensure calls remain real)?
- Do we need a utility for clearing cached services between suites to prevent cross-test leakage when new credentials are supplied mid-run?
