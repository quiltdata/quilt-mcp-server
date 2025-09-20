<!-- markdownlint-disable MD013 MD025 -->
# Phase 3 Design – Trusted Publishing & Combined Release Flow

## Objectives
- Extend `bin/release.sh` so the production release path builds DXT artifacts, builds Python distributions, and publishes them via `uv publish` in a single orchestrated command.
- Ensure GitHub Actions Trusted Publishing jobs reuse the same release script entry point, eliminating divergence between local dry runs and CI execution.
- Keep existing tagging commands and DXT tooling functional while layering Python packaging on top.

## Scope & Constraints
- Continue to treat DXT packaging as a first-class deliverable; Python builds must not skip or replace existing bundle generation.
- `python-dist` and `python-publish` remain reusable standalone commands; the combined release flow composes them but does not duplicate logic.
- CI must rely on Trusted Publishing (OIDC) without storing TestPyPI or PyPI credentials; local dry runs still require `.env` secrets.
- Maintain `DRY_RUN` semantics across the orchestrated release path so tests and previews avoid mutating state.
- Avoid introducing dependencies outside approved toolchain (bash, make, uv, existing Node tooling for DXT).

## Implementation Outline
1. **Release Script Orchestration**
   - Add a helper (e.g., `run_release_artifacts`) that sequentially invokes:
     1. `make dxt` and `make dxt-validate` (or equivalent shell helpers) to preserve existing bundle workflow.
     2. `python_dist` function to build wheel and sdist artifacts into `dist/`.
     3. `python_publish` function to publish previously built artifacts.
   - Introduce a new subcommand (placeholder name: `ci-release`) that calls the helper and exits on failure; expose `--dry-run` passthrough.
   - Update user-facing `release` command to optionally call the helper when invoked with a flag (e.g., `release --with-artifacts`) so maintainers can execute the combined flow locally before tagging.
   - Ensure `DIST_DIR` and DXT directories coexist without clobbering; surface summary output listing both DXT and Python artifacts.

2. **Environment Handling**
   - Extend `python_publish` to detect Trusted Publishing context: prefer `UV_PUBLISH_TOKEN` or fall back to GitHub-provided token/oidc integration if present.
   - Continue to require credentials locally; log actionable guidance when running in CI without required env (expected to be handled by workflow secrets/permissions).

3. **GitHub Actions Integration**
   - Update `.github/actions/create-release/action.yml` (or equivalent workflow step) to call `./bin/release.sh ci-release` instead of raw make targets, ensuring DXT + Python releases occur together.
   - Provide environment configuration in the workflow step (e.g., `UV_PUBLISH_TOKEN`, `PYPI_PUBLISH_URL`, OIDC permissions) and upload Python artifacts alongside DXT bundles where appropriate.
   - Record outputs (e.g., distribution paths or package URLs) for release notes if needed.

4. **Documentation & Developer Workflow**
   - Refresh release documentation to explain the combined flow, noting that `release.sh` orchestrates both artifact families.
   - Highlight dry-run usage (`DRY_RUN=1 ./bin/release.sh ci-release`) for developers verifying the pipeline without pushing tags.

## Open Decisions
- Exact naming for the new subcommand (`ci-release`, `release-artifacts`, etc.) and whether it should be callable from make (`make release-python`?).
- Where to surface Python artifact uploads in GitHub Releases (attach wheels/sdists or rely solely on PyPI links).
- Whether to gate `python_publish` within CI behind a conditional to allow tag-only dry runs (e.g., skip publish on non-production tags).

## Testing Matrix
| Scenario | Context | DRY_RUN | Expected Outcome |
| --- | --- | --- | --- |
| Local dry run | Developer machine | 1 | Logs sequential DXT build, dist build, publish command without executing heavy steps |
| Missing dist artifacts | CI or local | 0 | Combined command fails after `python_dist` if artifacts absent, surfacing actionable error |
| Trusted Publishing run | GitHub Actions | 0 | Generates DXT + Python artifacts, publishes via uv, exits success |
| Standalone commands | Developer machine | 0 | `python-dist` / `python-publish` still function independently |
| Legacy release tag | Developer machine | 0 | `release.sh release` without flag behaves as today (tag only) |
