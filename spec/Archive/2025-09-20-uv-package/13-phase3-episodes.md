<!-- markdownlint-disable MD013 MD025 -->
# Phase 3 Episodes – Trusted Publishing Rollout

## Episode 1 – Spec-Driven Tests for Packaging Commands
- Extend pytest coverage around `python-dist` and `python-publish` to ensure dry-run behaviour, credential validation, and make delegation continue to work without combined release helpers.
- Remove expectations tied to the previous orchestration command so the safety net reflects the PyPA-action workflow.

## Episode 2 – Release Script Cleanup
- Delete the unused release orchestration helper/subcommand while keeping `python-dist`/`python-publish` intact for local flows.
- Ensure usage/help text and make targets align with the streamlined command set.

## Episode 3 – Update GitHub Actions Pipeline
- Modify `.github/actions/create-release` to run `python-dist`, invoke `pypa/gh-action-pypi-publish`, then build/validate DXT bundles and package release assets.
- Pass repository-specific URLs/tokens from workflows (`push.yml`, `pr.yml`) and keep artifact uploads intact.

## Episode 4 – Documentation Refresh
- Update release sections in CLAUDE.md (and any workflow docs) to explain that CI handles PyPI publishing via the PyPA action while developers rely on `python-publish` for manual tests.
- Document the new CI ordering (build dist → publish → build DXT) and required secrets.

## Episode 5 – Verification & Hardening
- Run `make test` / `make test-unit` and targeted smoke tests for `python-dist` + `python-publish` dry runs.
- Perform end-to-end rehearsal (manual or scripted) confirming CI ordering works with real TestPyPI credentials, then document findings in CLAUDE.md per repository guidelines.
