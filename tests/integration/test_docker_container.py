import socket
import subprocess
import time
import uuid
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_TAG = "quilt-mcp:test"
DEFAULT_TIMEOUT = 60


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.integration
def test_docker_image_serves_http():
    dockerfile = REPO_ROOT / "Dockerfile"
    assert dockerfile.exists(), "Dockerfile must exist for container build"

    build_cmd = (
        "docker",
        "build",
        "--platform",
        "linux/amd64",
        "--tag",
        IMAGE_TAG,
        str(REPO_ROOT),
    )
    subprocess.run(build_cmd, check=True)

    free_port = _find_free_port()
    container_name = f"quilt-mcp-test-{uuid.uuid4()}"

    run_cmd = (
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        container_name,
        "-p",
        f"{free_port}:8000",
        IMAGE_TAG,
    )
    run_result = subprocess.run(run_cmd, check=True, text=True, capture_output=True)
    container_id = run_result.stdout.strip()

    try:
        deadline = time.time() + DEFAULT_TIMEOUT
        last_exception = None
        mcp_url = f"http://127.0.0.1:{free_port}/mcp"

        # Wait for container to be ready
        while time.time() < deadline:
            try:
                response = requests.get(mcp_url, timeout=5)
                assert response.status_code in {200, 302, 307, 406}
                break
            except Exception as exc:
                last_exception = exc
                time.sleep(2)
        else:
            pytest.fail(f"Container never became ready: {last_exception}")

        # Test all health check endpoint variations
        # Note: /mcp/* paths are reserved by FastMCP for protocol endpoints
        health_endpoints = [
            (f"http://127.0.0.1:{free_port}/health", "/health"),
            (f"http://127.0.0.1:{free_port}/healthz", "/healthz"),
            (f"http://127.0.0.1:{free_port}/", "/"),
        ]

        for endpoint_url, expected_route in health_endpoints:
            health_response = requests.get(endpoint_url, timeout=5)
            assert health_response.status_code == 200, (
                f"Health check at {expected_route} failed with status {health_response.status_code}"
            )

            # Verify health check response format
            health_data = health_response.json()
            assert health_data["status"] == "ok", f"Health status at {expected_route} is not ok: {health_data}"
            assert "timestamp" in health_data, f"Health response at {expected_route} missing timestamp"
            assert "route" in health_data, f"Health response at {expected_route} missing route info"
            assert health_data["route"] == expected_route, (
                f"Health response route mismatch: expected {expected_route}, got {health_data.get('route')}"
            )
            assert "server" in health_data, f"Health response at {expected_route} missing server info"
            assert health_data["server"]["name"] == "quilt-mcp-server", f"Incorrect server name at {expected_route}"

    finally:
        subprocess.run(("docker", "stop", container_name), check=False, capture_output=True)
        if container_id:
            subprocess.run(("docker", "rm", container_id), check=False, capture_output=True)
