"""Pytest configuration and fixtures for stateless deployment tests."""

import os
import subprocess
import time
from typing import Generator, Optional
import pytest
import docker
from docker.models.containers import Container


@pytest.fixture(scope="session")
def docker_client() -> docker.DockerClient:
    """Provide Docker client for container management."""
    return docker.from_env()


@pytest.fixture(scope="session")
def docker_image_name() -> str:
    """Get the Docker image name to test."""
    return os.getenv("TEST_DOCKER_IMAGE", "quilt-mcp-server:test")


@pytest.fixture(scope="session")
def build_docker_image(docker_client: docker.DockerClient, docker_image_name: str) -> str:
    """Build the Docker image for testing."""
    print(f"\n🔨 Building Docker image: {docker_image_name}")

    # Get project root (3 levels up from this file)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Build image
    image, build_logs = docker_client.images.build(
        path=project_root,
        tag=docker_image_name,
        rm=True,
        forcerm=True,
    )

    # Print build summary
    print(f"✅ Built image: {image.short_id}")
    return docker_image_name


@pytest.fixture
def stateless_container(
    docker_client: docker.DockerClient,
    build_docker_image: str,
) -> Generator[Container, None, None]:
    """
    Start a container with stateless deployment constraints.

    This fixture creates a container with:
    - Read-only root filesystem
    - Tmpfs mounts for temporary storage
    - Security constraints (no-new-privileges, cap-drop=ALL)
    - Resource limits (512M memory, 1.0 CPU)
    - JWT-only authentication mode
    """
    container: Optional[Container] = None

    try:
        # Container configuration matching production constraints
        container = docker_client.containers.run(
            image=build_docker_image,
            detach=True,
            remove=False,  # Don't auto-remove so we can inspect it
            read_only=True,  # Read-only root filesystem
            security_opt=["no-new-privileges:true"],  # Prevent privilege escalation
            cap_drop=["ALL"],  # Drop all capabilities
            tmpfs={
                "/tmp": "size=100M,mode=1777",  # noqa: S108
                "/app/.cache": "size=50M,mode=700",
                "/run": "size=10M,mode=755",
            },
            mem_limit="512m",  # Memory limit
            memswap_limit="512m",  # No swap
            cpu_quota=100000,  # 1.0 CPU (100000/100000)
            cpu_period=100000,
            environment={
                "MCP_REQUIRE_JWT": "true",  # Force JWT-only auth
                "QUILT_DISABLE_CACHE": "true",  # Disable caching
                "HOME": "/tmp",  # Redirect home directory  # noqa: S108
                "LOG_LEVEL": "DEBUG",  # Verbose logging
                "QUILT_MCP_STATELESS_MODE": "true",  # Enable stateless mode checks
                "FASTMCP_TRANSPORT": "http",
                "FASTMCP_HOST": "0.0.0.0",  # noqa: S104
                "FASTMCP_PORT": "8000",
            },
            ports={"8000/tcp": None},  # Random host port
        )

        # Wait for container to be healthy
        print(f"🚀 Started container: {container.short_id}")
        time.sleep(3)  # Give it time to start

        # Reload container to get latest status
        container.reload()

        if container.status != "running":
            logs = container.logs().decode("utf-8")
            raise RuntimeError(f"Container failed to start: {logs}")

        print(f"✅ Container running: {container.short_id}")

        yield container

    finally:
        if container:
            try:
                print(f"\n🧹 Cleaning up container: {container.short_id}")
                container.stop(timeout=5)
                container.remove(force=True)
                print("✅ Container cleaned up")
            except Exception as e:
                print(f"⚠️  Error cleaning up container: {e}")


@pytest.fixture
def writable_container(
    docker_client: docker.DockerClient,
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
                "MCP_REQUIRE_JWT": "false",  # ❌ Allow local credentials (VIOLATION)
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


@pytest.fixture
def container_url(stateless_container: Container) -> str:
    """Get the HTTP URL for the container's MCP server."""
    stateless_container.reload()
    ports = stateless_container.ports

    if "8000/tcp" not in ports or not ports["8000/tcp"]:
        raise RuntimeError("Container port 8000 not exposed")

    host_port = ports["8000/tcp"][0]["HostPort"]
    return f"http://localhost:{host_port}"


def get_container_filesystem_writes(container: Container) -> list[str]:
    """
    Get list of files written outside tmpfs directories.

    Uses `docker diff` to detect filesystem changes.
    """
    result = subprocess.run(
        ["docker", "diff", container.id],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return []

    # Parse docker diff output (format: "A /path/to/file" or "C /path/to/file")
    changes = []
    tmpfs_paths = {"/tmp", "/app/.cache", "/run"}  # noqa: S108

    for line in result.stdout.strip().split("\n"):
        if not line:
            continue

        parts = line.split(None, 1)
        if len(parts) != 2:
            continue

        change_type, path = parts

        # Ignore changes in tmpfs directories
        if any(path.startswith(tmpfs_path) for tmpfs_path in tmpfs_paths):
            continue

        changes.append(path)

    return changes
