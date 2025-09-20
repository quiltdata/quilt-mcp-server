<!-- markdownlint-disable MD013 MD025 -->
# I RASP DECO – 04 Phases

# Inputs

- Requirements: `spec/2025-09-20-uv-package/01-requirements.md`
- Analysis: `spec/2025-09-20-uv-package/02-analysis.md`
- Specifications: `spec/2025-09-20-uv-package/03-specifications.md`

# Phase Breakdown

## Phase 1 – Introduce uv Packaging via release.sh

- **Goal**: Establish reproducible uv build flow exposed through `bin/release.sh` and a make target.
- **Deliverables**:
  - Extend `bin/release.sh` with commands to build wheel and sdist artifacts using uv, writing results to `dist/`.
  - Add environment preflight checks inside `release.sh` for required variables with clear messaging.
  - Create a make target (e.g., `make package-uv`) that delegates to the new release.sh entry point, mirroring how `make dxt` wraps DXT packaging.
  - Regression run confirming DXT packaging targets still function.
- **Validation**:
  - Running the make target from a clean workspace produces expected artifacts.
  - Invoking the release script without credentials exits with descriptive failure.
  - `make dxt` succeeds post-change.

## Phase 2 – Developer Documentation & Dry Run Support

- **Goal**: Enable developers to configure `.env` for TestPyPI and exercise dry-run publishes using the release script target.
- **Deliverables**:
  - Documentation update (e.g., CLAUDE.md section) outlining required `.env` keys and dry-run workflow that calls the release.sh-backed make target.
  - Optional helper target or script for TestPyPI publish dry run, implemented through `release.sh` to maintain parity.
  - Verified dry-run procedure producing artifacts or simulated publish output.
- **Validation**:
  - Documentation passes lint/IDE diagnostics.
  - Dry run executed using `.env` credentials with expected result/logs.

## Phase 3 – GitHub Trusted Publishing Integration

- **Goal**: Automate production publishing via GitHub Actions using Trusted Publishing on tag push, delegating to `release.sh`.
- **Deliverables**:
  - Workflow YAML that calls `release.sh` to build/publish via uv under Trusted Publishing.
  - Release documentation noting tag-driven publish process and credential separation.
  - Safeguards ensuring DXT workflow remains unaffected (separate jobs or conditionals).
- **Validation**:
  - Workflow dry run or manual approval confirming Trusted Publishing handshake.
  - Tag-triggered build completes without manual secrets.

# Cross-Phase Considerations

1. Reuse environment validation logic defined in `release.sh` across local scripts, make targets, and CI to keep rules consistent.
2. Each phase should run the existing test suite to maintain safety net coverage.
3. Communicate rollout plan so maintainers know when to use DXT vs uv packaging.
4. Track external dependencies (GitHub settings) as risks if they cannot be completed within the repo.
