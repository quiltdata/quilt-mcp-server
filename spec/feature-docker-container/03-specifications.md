<!-- markdownlint-disable MD013 -->
# Specifications — Dockerized Quilt MCP Server

## 1. Desired End State

1. Repository contains an officially supported Docker image definition that packages the Quilt MCP server and its runtime dependencies.
2. Image entrypoint starts the MCP server with HTTP transport enabled, binding to a configurable host/port (default `0.0.0.0:8000`).
3. Automated workflows build, test, and publish the image to the Quilt AWS ECR registry during release events, aligning with existing version semantics.
4. Documentation teaches users how to build locally, run the container, configure runtime credentials, and pull from ECR.

## 2. Architectural Goals

1. **Deterministic Builds**: Use locked dependency installs (e.g., `uv sync --frozen`) to ensure reproducible image layers.
2. **Configurable Runtime**: Expose configuration solely through environment variables / mounted files, with defaults that match local developer expectations.
3. **Transport Flexibility**: Preserve stdio transport for existing CLI workflows while allowing HTTP transport when explicitly requested (e.g., via env var).
4. **Security Alignment**: Avoid embedding secrets; instruct users to supply credentials via environment variables or AWS IAM roles when deploying.
5. **Observability**: Provide basic readiness/health logging so operators can validate container startup.

## 3. Success Criteria

1. `docker build -t quilt-mcp:dev .` succeeds using repository tooling.
2. Running `docker run --rm -p 8000:8000 quilt-mcp:dev` starts the server and logs that HTTP transport is active.
3. Automation (Make target or CI job) executes the containerized server against a smoke test confirming HTTP availability.
4. Published image tags follow `<version>` and `latest` scheme and are available in the designated ECR repository.
5. Documentation changes reviewed and validated; CLAUDE.md updated with new learnings.

## 4. Integration Points & Contracts

1. **Entrypoint Script**: Docker `CMD`/`ENTRYPOINT` must call a Python wrapper that honours `FASTMCP_TRANSPORT=http` by default while deferring to user override.
2. **Make/CI**: Introduce tasks such as `make docker-build` and `make docker-test` (names TBD) integrated into existing pipelines without disrupting current jobs.
3. **Release Automation**: Extend `scripts/release.sh` or GitHub Actions workflows to authenticate with AWS ECR and push images using repository secrets.
4. **Documentation**: Update `docs/user/INSTALLATION.md` (and possibly README) with container usage instructions, ensuring version-controlled examples reference canonical commands.

## 5. Quality Gates

1. TDD-required automated tests cover HTTP startup path and container smoke validation.
2. Linting (`make lint`) and tests (`make test` or targeted subset) pass locally and in CI with the new assets.
3. Docker image passes a scripted health check verifying HTTP responsiveness before publish.
4. Spec documents reviewed and approved before implementation branch.
5. CLAUDE.md documents any caveats that future contributors need when working on containerization.

## 6. Risks & Mitigations

1. **Transport Regression**: Ensure stdio behaviour remains default for CLI by gating HTTP defaults to container-specific paths; add regression tests.
2. **CI Runtime**: Container build may increase CI time; use caching or base images to mitigate.
3. **AWS Credentials**: Publishing requires credentials; ensure workflow uses existing secrets and optionally provide dry-run fallback for local testing.
4. **Dependency Mismatch**: Keep container dependency install in sync with `uv` configuration to avoid drift; consider invoking `uv export` or `uv pip sync` using lockfile.
