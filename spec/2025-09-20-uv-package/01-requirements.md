<!-- markdownlint-disable MD013 MD025 -->
# I RASP DECO – 01 Requirements

# Issue Reference

- GitHub Issue: [#73 chore: uv package](https://github.com/quiltdata/quilt-mcp-server/issues/73)
- Problem Statement: Packaging must migrate to a uv-driven workflow surfaced through make targets while separating local TestPyPI credentials from CI Trusted Publishing.

# User Stories

1. As a release engineer, I want a reproducible uv command that builds the `quilt-mcp-server` package so that releases are consistent across environments.
2. As a developer, I want make targets that wrap uv packaging so that `.env` variables load automatically during local runs.
3. As a maintainer, I want preflight checks for required uv environment variables so that packaging fails fast when configuration is incomplete.
4. As a developer, I want guidance for populating local `.env` TestPyPI credentials so that I can perform dry-run publishes safely.
5. As a release engineer, I want CI releases to use GitHub Trusted Publishing on tag pushes so that production credentials are never stored in repository secrets.

# Acceptance Criteria

1. Repository exposes documented or scripted uv command(s) that build wheel and sdist artifacts for `quilt-mcp-server`.
2. Make target(s) wrap the uv packaging workflow and automatically source `.env` values.
3. Packaging workflow stops with descriptive errors when required uv environment variables are missing.
4. Developer documentation references `.env` entries for TestPyPI credentials used in local dry runs.
5. CI release process leverages GitHub Trusted Publishing on tag push without requiring TestPyPI credentials.
6. Existing DXT release flow remains operational with either compatibility or a described migration path once uv packaging is introduced.

# Success Metrics

- 100% of local packaging runs succeed via make targets after `.env` is populated.
- CI workflow publishes artifacts through Trusted Publishing on tag push without manual secrets.
- At least one local dry-run publish to TestPyPI completes using the documented procedure.

# High-Level Approach (Non-Technical)

- Define uv-based packaging commands as the authoritative Python packaging entry point.
- Surface commands via make targets that reuse `.env` sourcing and align local/CI behavior.
- Introduce environment validation before packaging begins.
- Document credential expectations for TestPyPI and Trusted Publishing.

# Open Questions

1. Which uv subcommands (`uv build`, `uv publish`) should be considered canonical for this repo?
2. Which environment variables must be present (e.g., `UV_PUBLISH_USERNAME`, `UV_PUBLISH_PASSWORD`, token-based alternatives)?
3. Does the repository already have GitHub Trusted Publishing configured, or will workflow updates be required?
4. Are there existing packaging scripts or make targets that should be deprecated to avoid duplication?
5. Should TestPyPI dry runs include automated verification of uploaded artifacts?
