<!-- markdownlint-disable MD013 MD025 -->
# Phase 3 Design – Trusted Publishing & Combined Release Flow

## Objectives
- Keep `bin/release.sh python-dist` and `python-publish` focused on local workflows while delegating CI publishing to the PyPA GitHub Action.
- Ensure GitHub Actions builds Python distributions via the release script, publishes them with the PyPA action, and then produces DXT bundles so both artifact families remain in sync.
- Maintain existing tagging commands and DXT tooling without introducing bespoke publish orchestration in bash.

## Scope & Constraints
- Continue to treat DXT packaging as a first-class deliverable; Python builds must not skip or replace existing bundle generation.
- `python-dist` and `python-publish` remain reusable standalone commands; the combined release flow composes them but does not duplicate logic.
- CI must rely on Trusted Publishing (OIDC) without storing TestPyPI or PyPI credentials; local dry runs still require `.env` secrets.
- Maintain `DRY_RUN` semantics across the orchestrated release path so tests and previews avoid mutating state.
- Avoid introducing dependencies outside approved toolchain (bash, make, uv, existing Node tooling for DXT).

## Implementation Outline
1. **Release Script Updates**
   - Keep `python_dist` focused on building wheels/sdists and ensure it remains idempotent for CI re-use.
   - Retain `python_publish` for local/TestPyPI validation; no new CI-specific subcommands are introduced.

2. **GitHub Actions Integration**
   - Update `.github/actions/create-release` to: (a) call `./bin/release.sh python-dist`, (b) invoke `pypa/gh-action-pypi-publish` with supplied credentials, and (c) run `make dxt`, `make dxt-validate`, and `make release-zip` afterward.
   - Allow workflows to pass repository-specific endpoints (TestPyPI vs PyPI) and tokens via inputs.
   - Continue uploading Python artifacts and DXT bundles for traceability.

3. **Workflow Adjustments**
   - Production tags (`push.yml`) supply the real PyPI token; dev tags (`pr.yml`) point to TestPyPI.
   - Maintain required permissions (contents/id-token) for future Trusted Publishing migration while relying on tokens today.

4. **Documentation & Developer Workflow**
   - Document that CI handles PyPI publishing via the PyPA action while developers can still run `./bin/release.sh python-publish` for manual tests.
   - Clarify the order of operations (build dist → PyPA publish → DXT build/validate → release asset upload).

## Open Decisions
- Whether to eventually swap token-based auth for OIDC/Trusted Publishing once GitHub + PyPI support matures for the project.
- How to manage version increments for TestPyPI dry runs to avoid collisions.

## Testing Matrix
| Scenario | Context | DRY_RUN | Expected Outcome |
| --- | --- | --- | --- |
| Local dry run | Developer machine | 1 | `python-dist` logs uv build command without executing; `python-publish` dry run masks credentials |
| Missing dist artifacts | Local | 0 | `python-publish` fails fast with actionable error |
| CI release run | GitHub Actions | 0 | `python-dist` builds, PyPA action publishes, DXT build validates, release artifacts uploaded |
| Standalone commands | Developer machine | 0 | `python-dist` / `python-publish` usable independently |
