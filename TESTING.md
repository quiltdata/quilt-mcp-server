# Testing Guide

## Structure

Tests are organized by directory. Test type is determined by location, not markers.

```
tests/
├── unit/     # Single-module tests, no network
├── func/     # Mocked multi-module tests
├── e2e/      # End-to-end workflows with real services
├── fixtures/ # Shared test data and helpers
```

## Markers (Minimal)

Only two markers are used:

- `platform`: requires platform authentication
- `slow`: takes longer than ~1s

## Common Commands

```
make test              # unit tests only
make test-catalog      # verify quiltx config matches .env
make test-func         # func tests (mocked)
make test-e2e          # e2e tests
make test-all          # all test phases (unit + func + e2e + scripts)
make test-ci           # CI-optimized (unit + func, skip slow/platform)
```

## Requirements-Based Skips

Some tests depend on external capabilities and will skip automatically when unavailable:

- Admin tests: require catalog admin privileges
- Search tests: require search backend availability
- Docker tests: require Docker CLI/runtime
- Catalog tests: require quilt3 authentication

## Notes

- Functional tests (`tests/func/`) use mocked backends and placeholder bucket fixtures.
- End-to-end tests (`tests/e2e/`) require real services and environment configuration
  (e.g., `PLATFORM_TEST_ENABLED`, `QUILT_CATALOG_URL`, `QUILT_REGISTRY_URL`, `QUILT_TEST_BUCKET`).
