<!-- markdownlint-disable MD013 -->
# Phase 1 Episodes — Container Fundamentals

## Episode 1 — Define Container Tests (Red)
- Add pytest module that expects a Docker image/tag and asserts HTTP readiness.
- Mark test appropriately (e.g., `@pytest.mark.integration` if needed) and ensure it fails due to missing image/behaviour.

## Episode 2 — Implement Dockerfile & Entrypoint (Green)
- Create Dockerfile, entrypoint script, and supporting configuration to satisfy the failing tests.
- Ensure Docker build installs dependencies using repository-approved tooling.

## Episode 3 — Integrate Developer Tooling (Refactor)
- Add Make targets/scripts that wrap build/run/test commands.
- Refactor as needed to keep code clean, ensuring all tests remain green.

