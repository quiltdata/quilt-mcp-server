<!-- markdownlint-disable MD013 -->
# Phases — Dockerized Quilt MCP Server

## Phase 1 — Container Fundamentals
- Create Dockerfile and supporting scripts/targets to build and run the Quilt MCP server with HTTP transport.
- Add automated smoke tests validating container startup and HTTP availability.

## Phase 2 — Publishing Automation
- Extend CI/release workflows to build, tag, and push images to AWS ECR.
- Ensure version alignment with repository releases and add documentation for pulling images.

## Phase 3 — Documentation & Developer Experience
- Update user/developer docs with container usage instructions.
- Capture learnings in CLAUDE.md and confirm tooling (`make`, scripts) support developers working with the container.

