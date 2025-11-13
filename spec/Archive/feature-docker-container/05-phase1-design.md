<!-- markdownlint-disable MD013 -->
# Phase 1 Design — Container Fundamentals

## Objectives

1. Produce a Docker image that runs the Quilt MCP server using HTTP transport.
2. Ensure TDD coverage for HTTP startup behaviour and container smoke validation.

## Key Tasks

1. Design Dockerfile layering strategy (base image, dependency install, source copy, runtime command).
2. Introduce entrypoint/launch script that defaults `FASTMCP_TRANSPORT` to `http` while respecting overrides.
3. Add Make targets (e.g., `make docker-build`, `make docker-run`, `make docker-test`) to streamline developer workflows.
4. Create automated smoke test that builds the image and verifies HTTP endpoint availability (likely via pytest fixture invoking `docker run`).
5. Update CI to run the smoke test in pull requests (or at least ensure local automation is reproducible).

## Dependencies & Inputs

- Existing MCP server scripts (`src/quilt_mcp/main.py`, `src/quilt_mcp/utils.py`).
- `pyproject.toml` for dependency management.
- `Makefile` / `make.dev` for integrating new targets.

## Acceptance

- Docker image starts successfully with HTTP transport confirmed in logs or health probe.
- New tests fail before implementation and pass after minimal code changes.
