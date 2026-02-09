"""Pytest configuration for end-to-end tests.

## Purpose

E2E tests validate functional correctness of the MCP protocol:
- Package operations (list, browse, push)
- Search functionality
- Visualization generation
- Multi-step workflows
- MCP protocol correctness

## Architecture: Backend-Agnostic

E2E tests are **completely backend-agnostic**:
- Tests use the `container_url` fixture (HTTP endpoint only)
- Tests don't know or care what backend is running inside the container
- Tests validate MCP protocol behavior over HTTP
- No `backend_mode` parametrization (removed in this spec)

## What E2E Tests DON'T Test

E2E tests do NOT test:
- JWT authentication (that's a stateless deployment constraint → tests/stateless/)
- Container security constraints (→ tests/stateless/)
- Read-only filesystem enforcement (→ tests/stateless/)
- Backend-specific implementations (→ tests/func/)

## Shared Infrastructure

E2E tests share Docker fixtures from tests/conftest.py:
- `docker_client`, `docker_image_name`, `build_docker_image`
- `stateless_container`, `container_url`

See: spec/a18-valid-jwts/08-test-organization.md
"""

import pytest

pytestmark = pytest.mark.usefixtures(
    "test_env",
    "clean_auth",
    "cached_athena_service_constructor",
    # "backend_mode" REMOVED - e2e tests are backend-agnostic!
    "requires_catalog",
    "test_bucket",
    "test_registry",
)
