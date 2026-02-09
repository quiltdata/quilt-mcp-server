"""Pytest configuration and fixtures for stateless deployment tests.

## Purpose

These tests validate stateless deployment constraints:
- Read-only filesystem enforcement
- Security constraints (no-new-privileges, cap-drop)
- Resource limits (memory, CPU)
- JWT-only authentication (multiuser/platform mode)
- No persistent state

## Architecture

Most Docker fixtures are in tests/conftest.py and shared with e2e tests.
This module contains only stateless-specific fixtures like writable_container
for negative testing.

## Important: JWT Tests Belong Here

JWT authentication is a **stateless deployment constraint**, not a universal
feature. JWT tests belong in tests/stateless/ because:

1. JWT is platform/multiuser mode only (not used in quilt3 local mode)
2. stateless_container fixture sets QUILT_MULTIUSER_MODE=true
3. These tests validate deployment constraints, not backend functionality

See: spec/a18-valid-jwts/08-test-organization.md
"""

import time
from typing import Generator, Optional
import pytest
import docker
from docker.models.containers import Container

# Import shared fixtures from parent conftest
# These are available to all tests in this directory
# Note: docker_client and build_docker_image are used as fixture parameters below,
# so they're not imported here (pytest discovers them automatically)
from tests.conftest import (
    docker_image_name,
    stateless_container,
    container_url,
    make_test_jwt,
    get_container_filesystem_writes,
)

pytestmark = pytest.mark.usefixtures("requires_docker")


# ============================================================================
# Stateless-Specific Fixtures
# ============================================================================


@pytest.fixture
def writable_container(
    docker_client,
    build_docker_image: str,
) -> Generator[Container, None, None]:
    """
    Start a container WITHOUT stateless constraints (for negative testing).

    This container has a writable filesystem and should be detected by tests.
    """
    container: Optional[Container] = None

    try:
        container = docker_client.containers.run(
            image=build_docker_image,
            detach=True,
            remove=False,
            read_only=False,  # ❌ Writable filesystem (VIOLATION)
            environment={
                "QUILT_MULTIUSER_MODE": "false",  # ❌ Local mode in stateless test (VIOLATION)
                "FASTMCP_TRANSPORT": "http",
                "FASTMCP_HOST": "0.0.0.0",  # noqa: S104
                "FASTMCP_PORT": "8000",
            },
            ports={"8000/tcp": None},
        )

        time.sleep(3)
        container.reload()

        yield container

    finally:
        if container:
            try:
                container.stop(timeout=5)
                container.remove(force=True)
            except Exception:
                pass
