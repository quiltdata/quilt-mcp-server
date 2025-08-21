Title: Strengthen unit tests and CI/CD (lint/type/coverage/matrix/caching)

Labels: enhancement, ci, testing, quality

Summary

Current tests are extensive under `app/tests`, but CI is minimal: single Python version (3.11), no lint/type checks, and no coverage gating. This issue proposes hardening tests and CI/CD with matrix builds, caching, static analysis, and clear coverage thresholds. Also proposes safer AWS access via OIDC and required checks.

Motivation / Problem

- CI uses only Python 3.11 whereas `pyproject.toml` requires Python >=3.12, causing mismatch.
- No ruff/black/mypy jobs; code quality regressions can slip in.
- No coverage upload or minimum enforced in CI.
- AWS credentials via long-lived secrets instead of GitHub OIDC role, increasing risk.
- No build caches for uv/pip and docker layers, increasing CI time.

Proposed Approach

- Update test workflow to a matrix: Python 3.12 and 3.11 (if 3.11 must be supported), or align strictly to 3.12.
- Add separate jobs for: lint (ruff + black --check), type (mypy), tests (pytest + coverage), and packaging smoke.
- Cache uv and pip artifacts; enable Docker buildx cache in deploy workflow.
- Add coverage threshold gate (e.g., 85% line) and upload to Codecov or store as artifact.
- Switch deploy workflow to GitHub OIDC (no static keys) with a role ARN; use environments with required reviewers for production.

Acceptance Criteria

- CI test matrix runs for Python 3.12 (and optionally 3.11); green on main and PRs.
- Lint and type-check jobs added and required.
- Coverage threshold enforced (>=85%); report shown in PR summary.
- Caching reduces CI time by at least 30% versus baseline (documented in PR description).
- Deploy workflow authenticates to AWS via OIDC role (assume-role with web identity), not long-lived keys.
- Required status checks configured in repo settings for: lint, type, tests, coverage.

Proposed Tasks

- [ ] Align `test.yml` Python version to 3.12 and/or enable a matrix
- [ ] Add lint/type jobs using `uv run ruff`, `uv run black --check`, and `uv run mypy`
- [ ] Add coverage report upload using Codecov or GitHub artifacts; enforce threshold
- [ ] Add uv cache steps and docker build cache to `deploy.yml`
- [ ] Replace `aws-actions/configure-aws-credentials` secrets usage with OIDC and role-to-assume
- [ ] Add environment protection rules for deploy (staging/prod) with approvals
- [ ] Document local test commands in `README.md` and ensure `make test-ci` runs all checks

References

- Workflows: `.github/workflows/test.yml`, `deploy.yml`, `dxt.yml`
- Project config: `pyproject.toml` (ruff/black/mypy settings already present)

Risks / Mitigations

- Risk: Stricter lint/type may fail current code. Mitigation: Introduce in warn-only mode for initial PR, then flip to required.
- Risk: OIDC setup requires AWS IAM changes. Mitigation: Provide Terraform/CDK snippet and docs in PR.

