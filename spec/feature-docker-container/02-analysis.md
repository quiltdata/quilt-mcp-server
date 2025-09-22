<!-- markdownlint-disable MD013 -->
# Analysis — Dockerized Quilt MCP Server

## 1. Current Architecture & Execution Model

1. **CLI Entry Point**: `quilt_mcp.main:main` (see `src/quilt_mcp/main.py`) launches the server and explicitly forces `FASTMCP_TRANSPORT=stdio` before calling `run_server()`.
2. **Server Bootstrap**: `run_server()` in `src/quilt_mcp/utils.py` builds a `FastMCP` instance, registers all tools, derives the transport from `FASTMCP_TRANSPORT`, and defaults to `stdio` when unset or invalid.
3. **Configuration Surface**: Runtime configuration today is `.env`-style variables (see `env.example`), Makefile `make run`, and scripts that assume stdio transport.
4. **Release & Packaging**: Current release pipeline focuses on Python packages and MCP Bundles (DXT/MCPB). `make deploy`, `scripts/release.sh`, and `.github/workflows/push.yml` do not build or publish container images.
5. **Testing**: Tests live under `tests/` with unit, integration, and e2e suites run via `make test`. No container-focused tests exist; transport coverage centers on stdio with limited validation for alternative transports via monkeypatched env vars.

## 2. Existing Tooling & Automation

1. **Make Targets**: `make.dev` and `Makefile` orchestrate local runs, linting, coverage, etc. There are no Docker-related targets or scripts.
2. **Versioning**: Releases rely on tags and `pyproject` versioning; `scripts/release.sh` and `scripts/version.py` drive version sync. A Docker workflow must align with these conventions.
3. **AWS Integration**: Deployment scripts assume AWS credentials for CDK/Terraform; no precedent for container publishing, though the repo already depends on AWS for infrastructure provisioning.

## 3. Constraints & Risks

1. **Transport Mode Conflict**: The CLI overrides the transport to `stdio`, which conflicts with the requirement to serve via HTTP inside the container.
2. **Environment Variables**: The server depends on credentials and service endpoints (S3, Elasticsearch, etc.). Container runtime must surface these safely without baking secrets.
3. **Dependency Footprint**: Image must install Python dependencies declared in `pyproject.toml` (and likely optional extras). Build should be deterministic and cache friendly.
4. **Release Alignment**: Publishing to ECR must fit the existing release cadence without breaking current DXT workflows. Need to ensure CI/CD updates remain under acceptable runtime limits.
5. **Testing in Container**: Ensuring tests run inside the image (or against a running container) may increase CI time; we must decide on scope to keep pipelines practical.

## 4. Gaps Relative to Requirements

1. **No Dockerfile**: Repository lacks container definition or guidance for building/running via Docker.
2. **No ECR Publishing**: Workflows/scripts do not authenticate to ECR or push images.
3. **Missing HTTP-first Behaviour**: Primary entrypoint enforces stdio transport, so HTTP functionality requires manual overrides and is untested.
4. **Documentation Gap**: README/docs do not cover container usage, exposing friction for new researchers.
5. **Health/Port Exposure**: There is no formalized HTTP port management or health check endpoint configuration documented for container orchestration.

## 5. Opportunities & Considerations

1. **Transport Abstraction**: Introduce a CLI flag or environment-driven transport choice that defaults differently when running in Docker vs. local CLI usage.
2. **Build Tooling**: Reuse `uv` for deterministic dependency installation during image build (matching local tooling).
3. **CI Validation**: Add a GitHub Actions job or make target that builds the container and confirms startup and HTTP responsiveness using existing tests or smoke probes.
4. **Release Automation**: Extend release scripts to tag images with version + `latest`, authenticate to AWS ECR, and push.
5. **Documentation Updates**: Provide concise instructions and troubleshooting tips in `docs/user/INSTALLATION.md` or similar, keeping CLAUDE.md updated per repository guidelines.
