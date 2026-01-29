"""Test Scenario 4: No Persistent State.

Verify container is truly stateless - no data carries over between restarts.
"""

import time
import httpx
import pytest
import docker
from docker.models.containers import Container


def test_no_state_persists_across_restarts(
    docker_client: docker.DockerClient,
    build_docker_image: str,
):
    """Verify second container run behaves identically to first run.

    This test:
    1. Starts a container with stateless constraints
    2. Makes requests that might create cached data
    3. Stops and removes the container
    4. Starts a new container with same config
    5. Verifies behavior is identical (no warm-start effects)
    """

    def create_and_test_container() -> dict:
        """Create container, make requests, return metrics."""
        container = None
        try:
            container = docker_client.containers.run(
                image=build_docker_image,
                detach=True,
                remove=False,
                read_only=True,
                tmpfs={"/tmp": "size=100M", "/app/.cache": "size=50M"},  # noqa: S108
                environment={
                    "MCP_REQUIRE_JWT": "true",
                    "MCP_JWT_SECRET": "test-secret-key-for-stateless-testing-only",
                    "QUILT_DISABLE_CACHE": "true",
                    "HOME": "/tmp",  # noqa: S108
                    "FASTMCP_TRANSPORT": "http",
                    "FASTMCP_HOST": "0.0.0.0",  # noqa: S104
                    "FASTMCP_PORT": "8000",
                },
                ports={"8000/tcp": None},
            )

            time.sleep(3)
            container.reload()

            # Get container URL
            ports = container.ports

            if "8000/tcp" not in ports or not ports["8000/tcp"]:
                pytest.fail(
                    f"❌ FAIL: Container port 8000/tcp not exposed\n"
                    f"Available ports: {list(ports.keys())}\n"
                    f"Container status: {container.status}\n"
                    "Check if container started properly"
                )

            host_port = ports["8000/tcp"][0]["HostPort"]
            url = f"http://localhost:{host_port}"

            # Make test requests
            start_time = time.time()
            response = httpx.get(f"{url}/", timeout=10.0)
            response_time = time.time() - start_time

            # Get filesystem state
            from .conftest import get_container_filesystem_writes

            writes = get_container_filesystem_writes(container)

            return {
                "status_code": response.status_code,
                "response_time": response_time,
                "filesystem_writes": len(writes),
                "container_id": container.short_id,
            }

        finally:
            if container:
                container.stop(timeout=5)
                container.remove(force=True)

    # First run
    print("\n📊 First container run...")
    first_run = create_and_test_container()
    print(f"   Status: {first_run['status_code']}")
    print(f"   Response time: {first_run['response_time']:.3f}s")
    print(f"   Filesystem writes: {first_run['filesystem_writes']}")

    # Second run
    print("\n📊 Second container run (fresh start)...")
    second_run = create_and_test_container()
    print(f"   Status: {second_run['status_code']}")
    print(f"   Response time: {second_run['response_time']:.3f}s")
    print(f"   Filesystem writes: {second_run['filesystem_writes']}")

    # Verify behavior is consistent
    assert first_run["status_code"] == second_run["status_code"], (
        "❌ FAIL: Container behavior changed between runs\n"
        f"First run: {first_run['status_code']}\n"
        f"Second run: {second_run['status_code']}\n"
        "\n"
        "Stateless containers must behave identically on each restart.\n"
        "Different behavior suggests state is being persisted."
    )

    # Check for warm-start effects (significantly faster second run)
    time_ratio = second_run["response_time"] / first_run["response_time"]

    # Allow up to 50% faster (some variation is normal)
    # But if second run is >2x faster, that suggests caching
    if time_ratio < 0.5:
        pytest.fail(
            f"❌ FAIL: Second run suspiciously faster (warm-start effect)\n"
            f"First run: {first_run['response_time']:.3f}s\n"
            f"Second run: {second_run['response_time']:.3f}s\n"
            f"Speedup: {1 / time_ratio:.1f}x faster\n"
            "\n"
            "Possible causes:\n"
            "  1. Data cached in persistent storage (not tmpfs)\n"
            "  2. Docker layer caching\n"
            "  3. Application-level caching not disabled\n"
            "\n"
            "Verify:\n"
            "  - QUILT_DISABLE_CACHE=true is set\n"
            "  - No volume mounts persist between runs\n"
            "  - Application doesn't use external cache (Redis, etc.)\n"
        )

    # Filesystem writes should be similar
    write_diff = abs(first_run["filesystem_writes"] - second_run["filesystem_writes"])

    if write_diff > 5:  # Allow small variance
        pytest.fail(
            f"❌ FAIL: Filesystem writes differ significantly between runs\n"
            f"First run: {first_run['filesystem_writes']} writes\n"
            f"Second run: {second_run['filesystem_writes']} writes\n"
            f"Difference: {write_diff} writes\n"
            "\n"
            "This suggests the application writes different data on first vs. later runs,\n"
            "which may indicate state is being checked/loaded from persistent storage.\n"
        )

    print("\n✅ Container behavior is consistent across restarts (truly stateless)")


def test_tmpfs_contents_cleared_on_restart(
    docker_client: docker.DockerClient,
    build_docker_image: str,
):
    """Verify tmpfs contents don't persist between container instances."""

    def check_tmpfs_marker() -> bool:
        """Create a marker file in tmpfs and check if it persists."""
        container = None
        try:
            container = docker_client.containers.run(
                image=build_docker_image,
                detach=True,
                remove=False,
                read_only=True,
                tmpfs={"/tmp": "size=100M"},  # noqa: S108
                environment={"FASTMCP_TRANSPORT": "http"},
            )

            time.sleep(2)

            # Try to create a marker file in tmpfs
            exec_result = container.exec_run("sh -c 'echo test > /tmp/marker.txt && cat /tmp/marker.txt'")

            marker_created = exec_result.exit_code == 0

            return marker_created

        finally:
            if container:
                container.stop(timeout=5)
                container.remove(force=True)

    # First container: create marker
    print("\n📝 Creating marker file in tmpfs...")
    first_run = check_tmpfs_marker()

    assert first_run, "Should be able to write to tmpfs"

    # Second container: marker should NOT exist
    print("📝 Checking if marker persists in new container...")

    container = None
    try:
        container = docker_client.containers.run(
            image=build_docker_image,
            detach=True,
            remove=False,
            read_only=True,
            tmpfs={"/tmp": "size=100M"},  # noqa: S108
            environment={"FASTMCP_TRANSPORT": "http"},
        )

        time.sleep(2)

        # Check if marker still exists
        exec_result = container.exec_run("cat /tmp/marker.txt")
        marker_persisted = exec_result.exit_code == 0

        if marker_persisted:
            pytest.fail(
                "❌ FAIL: File in tmpfs persisted between container restarts\n"
                "\n"
                "Found /tmp/marker.txt in second container, but tmpfs should be ephemeral.\n"
                "\n"
                "Possible causes:\n"
                "  1. /tmp is not actually mounted as tmpfs\n"
                "  2. Volume is being mounted instead of tmpfs\n"
                "  3. Container is being restarted instead of recreated\n"
                "\n"
                "Verify Docker configuration:\n"
                "  - Using --tmpfs /tmp:size=100M (not -v /tmp)\n"
                "  - Container is fully removed between runs\n"
                "  - No persistent volumes attached\n"
            )

        print("✅ tmpfs contents cleared between restarts (ephemeral)")

    finally:
        if container:
            container.stop(timeout=5)
            container.remove(force=True)
