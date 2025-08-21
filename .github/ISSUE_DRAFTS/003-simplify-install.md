Title: Simplify installation and implementation (single-command setup, fewer prereqs)

Labels: enhancement, developer-experience, docs

Summary

Installation spans `uv`, Makefiles across 4 phases, `.env` editing, Docker, and AWS CLI. For local usage and contributors, we can streamline to a single `uvx` or `make bootstrap` path, auto-detect more defaults, and provide a lean "local only" mode that does not require AWS until needed.

Motivation / Problem

- New contributors need to understand 4 phases before running locally.
- Manual `.env` editing is error prone; some variables can be auto-derived.
- No single-command bootstrap for running tests, linting, and the local MCP server.

Proposed Approach

- Add `make bootstrap` that installs uv, syncs dependencies (test+lint), and validates environment.
- Provide `uvx`-based entrypoint (`uvx quilt-mcp`) that runs the local server with sensible defaults.
- Make `.env` optional for local-only mode; default to mocked AWS (localstack) unless `AWS_PROFILE` is configured.
- Add a `scripts/install.sh` to check prereqs and install missing tools (uv, docker) with guidance.
- Publish a small `pipx`/`uvx` install snippet in `README.md`.

Acceptance Criteria

- `make bootstrap` sets up a dev environment and prints next steps.
- Running `uvx quilt-mcp` starts the local MCP server without extra flags when AWS is not required.
- `.env` fields auto-derived where possible; errors clearly reported by `make check-env`.
- Updated `README.md` with a concise Quick Start and Troubleshooting.

Proposed Tasks

- [ ] Add `make bootstrap` target and `scripts/install.sh`
- [ ] Add optional localstack support and doc section; guard integration tests with markers
- [ ] Update `README.md` to highlight `uvx` and simplified steps
- [ ] Add smoke test instruction using `curl` and MCP inspector

References

- Files: `Makefile`, `scripts/check-env.sh`, `pyproject.toml` (`project.scripts`)

