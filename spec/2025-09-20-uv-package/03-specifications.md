<!-- markdownlint-disable MD013 MD025 -->
# I RASP DECO – 03 Specifications

# Inputs

- Requirements: `spec/2025-09-20-uv-package/01-requirements.md`
- Analysis: `spec/2025-09-20-uv-package/02-analysis.md`

# Desired End State

1. **Authoritative uv Packaging Pipeline**
   - Wheel and sdist builds are produced through uv (`uv build` or equivalent) with reproducible output in `dist/`.
   - `bin/release.sh` orchestrates the uv packaging so the release script remains the single entry point, mirroring the existing DXT flow.
2. **Make Target Coverage**
   - A make target (parallel to `make dxt`) delegates to `bin/release.sh` to invoke the uv packaging path while inheriting `.env` sourcing.
3. **Separated Build vs Publish Flows**
   - `bin/release.sh python-dist` performs local artifact builds without credential requirements.
   - A future `bin/release.sh python-publish` command will enforce credential validation before pushing to PyPI/TestPyPI.
4. **Developer Guidance for `.env`**
   - Approved documentation clearly lists TestPyPI credential keys, usage patterns, and where to store them locally.
5. **Trusted Publishing in CI**
   - GitHub Actions workflow builds artifacts and publishes through Trusted Publishing on tag push without storing static credentials, calling into the same `release.sh` logic so command parity is maintained.
6. **DXT Workflow Continuity**
   - Newly introduced packaging flow coexists with existing DXT targets and communicates when each path should be used. DXT-specific commands in `release.sh` remain functional.

# Success Criteria

- Running the packaging make target produces wheel and sdist artifacts via `release.sh` and uv in a clean workspace, regardless of publish credentials.
- Publish command (when added) fails fast with actionable errors if required credentials are missing.
- Documentation update is merged that references `.env` keys and provides TestPyPI dry-run guidance.
- CI tag push triggers a Trusted Publishing workflow that completes without manual secrets while delegating to `release.sh`.
- DXT packaging commands execute successfully after changes.

# Architectural & Design Principles

1. Define environment variable requirements within the future publish path so enforcement is consistent across local and CI usage.
2. Ensure local and CI commands call the same `release.sh` entry points to minimize environment-specific drift.
3. Maintain separation of artifact directories to avoid cross-contamination between DXT and Python package outputs.
4. Prefer additive changes that introduce minimal risk to existing release automation.
5. Keep credential handling secure by avoiding persistent secrets in repo or CI secrets; rely on `.env` locally and OIDC in CI.

# Integration Points & Interfaces

- **bin/release.sh**: central location for new uv packaging logic and eventual publish validation (`python-dist` vs `python-publish`).
- **Makefile / make.deploy**: include new target that invokes the release script similar to `make dxt` exposure.
- **GitHub Actions**: workflow YAML defining Trusted Publishing job triggered by tags, calling `release.sh` entry point.
- **Documentation**: existing CLAUDE.md or release guide to store developer guidance per repository rules.

# Validation Gates

1. Local packaging dry run from clean checkout via `make python-dist` (no credentials required).
2. Automated test suite (`make test`) to confirm no regressions.
3. CI workflow dry run or manual approval demonstrating Trusted Publishing handshake (subject to GitHub settings).
4. Documentation linting/IDE diagnostics clean.

# Risks & Unknowns

1. Trusted Publishing requires repository-level configuration that may not be manageable purely within code.
2. uv publish semantics for Trusted Publishing may need additional flags; fallback tooling might be necessary.
3. Coordinating version increments for TestPyPI dry runs could require automation to avoid collisions.
4. Additional tooling (e.g., twine) might still be necessary if uv lacks features; must budget for contingency.
