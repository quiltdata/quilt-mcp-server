<!-- markdownlint-disable MD013 -->
# Requirements — Dockerized Quilt MCP Server

## Issue Reference

- GitHub: [#188 – Implement Docker Container for Quilt MCP](https://github.com/quiltdata/quilt-mcp-server/issues/188)
- Priority: Critical, blocks local adoption

## Problem Statement

Researchers need an officially supported Docker image for the Quilt MCP server that speaks HTTP so they can run the latest build locally without manual environment setup. The current repository lacks a standardized container distribution channel, making onboarding and updates difficult.

## User Stories

1. **As a bioinformatics researcher**, I want to run the Quilt MCP server from a Docker image so that I can work with a fully configured local instance without managing Python dependencies.
2. **As a DevOps engineer**, I want an authenticated remote registry (ECR) that publishes the latest Quilt MCP server image so that teams can pull trusted builds into controlled environments.
3. **As a developer on the Quilt MCP project**, I want automated validation that the container exposes the HTTP MCP endpoint and runs the existing test suite so that we can trust releases and avoid regressions.

## Acceptance Criteria

1. A Docker image definition exists in-repo that builds the Quilt MCP server with all required runtime dependencies.
2. Image startup launches the MCP server using HTTP transport on a configurable port (default 8000) and reads configuration from documented environment variables.
3. Containerized server passes the existing automated test suite (or a representative subset) when invoked through repository tooling.
4. Release workflow publishes the image to a designated AWS ECR registry/tag so that authenticated users can pull the latest build.
5. Repository documentation includes instructions for building, running, and pulling the container, including environment variables and any prerequisites.
6. Published image metadata (tag naming, versioning) stays aligned with repository release strategy.

## Success Metrics

- Pulling `docker pull <documented ECR URI>` retrieves a functional image.
- `docker run` example in docs exposes the MCP HTTP endpoint and responds to a health probe.
- CI reports green for container build and runtime verification steps.
- 100% of acceptance criteria validated by automated or documented manual tests.

## Constraints & Assumptions

- Container must use HTTP transport (no websockets/grpc) per MCP spec.
- Solution should reuse existing Makefile or scripts where possible to fit established workflows.
- Assume AWS credentials are available when publishing to ECR; local builds must not require AWS access.
- Publishing cadence should match current release process (likely on tagged releases).

## Open Questions

1. What is the canonical AWS ECR repository URI and region for publishing the Quilt MCP image?
2. Should the container expose additional diagnostics endpoints (healthz/metrics) beyond MCP HTTP?
3. Are there size constraints or base image preferences (e.g. slim Python, distroless) we must follow?
4. Do we need multi-architecture builds (amd64 + arm64) out of the gate?
5. How should credentials or configuration for downstream services (S3, Elasticsearch, etc.) be injected at runtime?
