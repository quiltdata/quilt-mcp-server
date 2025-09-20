<!-- markdownlint-disable MD013 MD025 -->
# I RASP DECO – 04 Phases

# Inputs

- Requirements: `spec/2025-09-20-uv-package/01-requirements.md`
- Analysis: `spec/2025-09-20-uv-package/02-analysis.md`
- Specifications: `spec/2025-09-20-uv-package/03-specifications.md`

# Phase Breakdown

## Phase 1 – Introduce uv Packaging via release.sh

- **Goal**: Establish reproducible uv build flow exposed through `bin/release.sh` and a make target, without requiring publish credentials.
- **Deliverables**:
  - Extend `bin/release.sh` with command `python-dist` to build wheel and sdist artifacts using uv, writing results to `dist/`.
  - Create a make target (`make python-dist`) that delegates to the new release.sh entry point, mirroring how `make dxt` wraps DXT packaging.
  - Regression run confirming DXT packaging targets still function.
- **Validation**:
  - Running the make target from a clean workspace produces expected artifacts without needing credentials.
  - `make dxt` succeeds post-change.

## Phase 2 – Developer Documentation & Dry Run Support

- **Goal**: Enable developers to configure `.env` for TestPyPI and exercise dry-run publishes using a future publish command.
- **Deliverables**:
  - Documentation update (e.g., CLAUDE.md section) outlining required `.env` keys and dry-run workflow using `bin/release.sh python-publish` (once implemented).
  - Optional helper target or script for TestPyPI publish dry run, implemented through `release.sh` to maintain parity.
  - Verified dry-run procedure producing artifacts or simulated publish output.
- **Validation**:
  - Documentation passes lint/IDE diagnostics.
  - Dry run executed using `.env` credentials with expected result/logs.

## Phase 3 – GitHub Trusted Publishing Integration

- **Goal**: Automate production publishing via GitHub Actions using Trusted Publishing on tag push, delegating to `release.sh` so DXT and Python artifacts are handled together.
- **Deliverables**:
  - Workflow YAML that invokes the release entry point (`release.sh release` or equivalent) which now runs DXT packaging, `python-dist`, and `python-publish` in sequence under Trusted Publishing.
  - Release documentation noting tag-driven publish process, credential separation, and dual-artifact output.
  - Safeguards ensuring combined flow still preserves legacy DXT behaviour for other callers.
- **Validation**:
  - Workflow dry run or manual approval confirming Trusted Publishing handshake and dist publishing.
  - Tag-triggered build completes without manual secrets while producing both DXT and Python artifacts.

# Cross-Phase Considerations

1. Ensure environment validation logic lives in the publish path, keeping local build command credential-free while CI and publish flows remain consistent.
2. Each phase should run the existing test suite to maintain safety net coverage.
3. Communicate rollout plan so maintainers know the release script now emits both DXT and Python artifacts while standalone targets remain available for focused workflows.
4. Track external dependencies (GitHub settings) as risks if they cannot be completed within the repo.
