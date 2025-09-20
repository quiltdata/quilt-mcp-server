<!-- markdownlint-disable MD013 MD025 -->
# Phase 3 Episodes – Trusted Publishing Rollout

## Episode 1 – Spec-Driven Tests for Combined Release Flow
- Add pytest coverage that executes `./bin/release.sh ci-release --dry-run` (name TBD) and asserts ordered logging for DXT build, Python dist build, and publish preview.
- Extend tests ensuring failure propagation when `python-publish` preconditions are unmet (e.g., missing credentials in non-dry-run mode).
- Capture fixtures for Trusted Publishing env simulation (OIDC tokens mocked via env vars).

## Episode 2 – Implement Release Script Orchestration
- Introduce helper that composes `make dxt`, `make dxt-validate`, `python_dist`, and `python_publish` with shared `DRY_RUN` handling.
- Add new subcommand wiring (plus optional flag for `release --with-artifacts`) while keeping legacy behaviour untouched.
- Ensure summary output surfaces both artifact families.

## Episode 3 – Update GitHub Actions Pipeline
- Modify `.github/actions/create-release` to call the new release script subcommand.
- Configure workflow permissions and environment for Trusted Publishing (OIDC token, `UV_PUBLISH_TOKEN` or equivalent).
- Upload Python artifacts (or log PyPI URLs) alongside existing DXT assets.

## Episode 4 – Documentation Refresh
- Update release sections in CLAUDE.md (and any workflow docs) to explain the unified release script usage.
- Document dry-run expectations and how CI now leverages `release.sh` for both artifact families.

## Episode 5 – Verification & Hardening
- Run `make test` and targeted smoke tests for the new release command in dry-run mode.
- Perform end-to-end rehearsal (manual or scripted) to confirm dual artifact generation and publishing succeed under DRY_RUN=0 with test credentials.
- Record lessons learned in CLAUDE.md per repository guidelines.
