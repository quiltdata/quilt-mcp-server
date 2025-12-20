<!-- markdownlint-disable MD013 MD025 -->
# I RASP DECO – 02 Analysis

# Source Inputs

- Based on `spec/2025-09-20-uv-package/01-requirements.md`
- Focused on GitHub Issue [#73 chore: uv package](https://github.com/quiltdata/quilt-mcp-server/issues/73)

# Current Architecture & Workflow

1. `make.deploy` targets focus on DXT packaging using `npx @anthropic-ai/dxt`, not on Python packaging for PyPI/TestPyPI.
2. `uv` is already the dependency manager for tests and linting (`uv sync`, `uv run`) and for staging dependencies during DXT builds (`uv pip install --target …`).
3. `pyproject.toml` uses `setuptools.build_meta` with `wheel`, supporting traditional Python packaging but lacking uv command integration.
4. Top-level `Makefile` performs `sinclude .env`, so new make targets automatically inherit environment variables when `.env` exists.
5. Release automation (`bin/release.sh`, `make release*`) handles version bumps and DXT artifacts; no PyPI/TestPyPI publishing flow exists.
6. Existing documentation centers on DXT workflows; there is no guidance for uv packaging or TestPyPI credentials.

# Constraints & Limitations

1. New packaging commands must coexist with current DXT targets without breaking release expectations.
2. Required credentials are undefined; enforcing environment checks without clarity risks false failures.
3. GitHub Trusted Publishing requires repository settings and workflow updates that may extend beyond code changes.
4. Directory layout must separate Python artifacts (`dist/`) from DXT outputs to avoid clobbering.
5. Developers may lack TestPyPI credentials; guidance must differentiate local dry runs from production releases.

# Technical Debt & Opportunities

1. Absence of dedicated Python packaging targets presents an opportunity to add uv build/publish commands.
2. No environment validation exists for packaging flows; when a publish command is added it must validate credentials without burdening local builds.
3. Documentation does not mention `.env` usage for credentials—gap to fill for developer experience.
4. Release scripts assume manual tagging; aligning them with Trusted Publishing may expose automation debt.

# Gap Analysis vs Requirements

1. **UV Packaging Command (Req 1)** – Missing entirely.
2. **Make Targets (Req 2)** – Missing.
3. **Separated Build/Publish (Req 3)** – Need distinct commands so local builds run credential-free while publish enforces validation.
4. **Local `.env` Guidance (Req 4)** – Missing.
5. **Trusted Publishing in CI (Req 5)** – Missing.
6. **Backward Compatibility (Req 6)** – Requires careful design to avoid DXT regressions.

# Architectural Considerations & Challenges

1. Decide whether uv packaging targets live in `make.dev`, `make.deploy`, or a new include to keep structure clear.
2. Determine canonical environment variable names for uv publish workflows to ensure consistency between local runs and CI.
3. Ensure packaging commands produce artifacts in isolated directories and clean up intermediate files.
4. Trusted Publishing may call for new GitHub Actions workflows and repository permissions outside code control.
5. Need strategy for versioning during TestPyPI dry runs to avoid conflicts (e.g., using pre-release suffixes).
