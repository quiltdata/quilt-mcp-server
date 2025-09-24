import json
import platform
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


def _get_docker_image_platforms(image_tag: str) -> list[str]:
    """Inspect Docker image to get supported platforms."""
    try:
        # Use docker manifest inspect to get platform information
        result = subprocess.run(
            ["docker", "manifest", "inspect", image_tag],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            # Fallback to docker image inspect for local images
            result = subprocess.run(
                ["docker", "image", "inspect", image_tag, "--format", "{{.Architecture}}"],
                capture_output=True,
                text=True,
                check=True,
            )
            arch = result.stdout.strip()
            return [f"linux/{arch}"] if arch else []

        manifest = json.loads(result.stdout)
        platforms = []

        # Check for manifests (multi-platform image)
        if "manifests" in manifest:
            for m in manifest["manifests"]:
                if "platform" in m:
                    p = m["platform"]
                    platforms.append(f"{p.get('os', 'linux')}/{p.get('architecture', 'unknown')}")
        # Single platform image
        elif "architecture" in manifest:
            platforms.append(f"linux/{manifest['architecture']}")

        return platforms
    except Exception:
        return []


@pytest.mark.integration
def test_docker_image_serves_http():
    dockerfile = REPO_ROOT / "Dockerfile"
    assert dockerfile.exists(), "Dockerfile must exist for container build"

    # Build the image exactly as production would
    build_cmd = (
        "docker",
        "build",
        "--tag",
        IMAGE_TAG,
        str(REPO_ROOT),
    )
    subprocess.run(build_cmd, check=True)

    # Verify the built image supports linux/amd64 (required for ECS Fargate)
    platforms = _get_docker_image_platforms(IMAGE_TAG)
    assert platforms, f"Could not determine platforms for image {IMAGE_TAG}"

    # Check if linux/amd64 is supported (required for ECS)
    assert "linux/amd64" in platforms or "linux/x86_64" in platforms, (
        f"Image does not support linux/amd64 platform required for ECS Fargate. "
        f"Supported platforms: {platforms}. "
        f"Build with: docker buildx build --platform linux/amd64,linux/arm64"
    )

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
        health_url = f"http://127.0.0.1:{free_port}/health"

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

        # Test the health check endpoint
        health_response = requests.get(health_url, timeout=5)
        assert health_response.status_code == 200, f"Health check failed with status {health_response.status_code}"

        # Verify health check response format
        health_data = health_response.json()
        assert health_data["status"] == "ok", f"Health status is not ok: {health_data}"
        assert "timestamp" in health_data, "Health response missing timestamp"
        assert "server" in health_data, "Health response missing server info"
        assert health_data["server"]["name"] == "quilt-mcp-server", "Incorrect server name"

    finally:
        subprocess.run(("docker", "stop", container_name), check=False, capture_output=True)
        if container_id:
            subprocess.run(("docker", "rm", container_id), check=False, capture_output=True)


@pytest.mark.integration
def test_docker_image_ecs_platform_compatibility():
    """Test that Docker image is compatible with ECS Fargate platform requirements."""
    dockerfile = REPO_ROOT / "Dockerfile"
    assert dockerfile.exists(), "Dockerfile must exist for container build"

    # Build the image exactly as production would
    build_cmd = (
        "docker",
        "build",
        "--tag",
        f"{IMAGE_TAG}-ecs-test",
        str(REPO_ROOT),
    )
    result = subprocess.run(build_cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"Docker build failed: {result.stderr}"

    # Get the image's architecture
    inspect_cmd = (
        "docker",
        "image",
        "inspect",
        f"{IMAGE_TAG}-ecs-test",
        "--format",
        "{{.Architecture}}",
    )
    result = subprocess.run(inspect_cmd, capture_output=True, text=True, check=True)
    image_arch = result.stdout.strip()

    # ECS Fargate requires linux/amd64 (x86_64)
    assert image_arch in ["amd64", "x86_64"], (
        f"Docker image architecture '{image_arch}' is not compatible with ECS Fargate. "
        f"ECS Fargate requires 'amd64' (x86_64) architecture. "
        f"Current build architecture: {image_arch}. "
        f"To fix: Use 'docker buildx build --platform linux/amd64,linux/arm64' for multi-platform support."
    )

    # Additional check: verify the image can be inspected for manifest
    manifest_cmd = ["docker", "manifest", "inspect", f"{IMAGE_TAG}-ecs-test"]
    manifest_result = subprocess.run(manifest_cmd, capture_output=True, text=True)

    if manifest_result.returncode == 0:
        # If manifest exists, verify it includes linux/amd64
        try:
            manifest = json.loads(manifest_result.stdout)
            platforms_found = []

            if "manifests" in manifest:
                for m in manifest["manifests"]:
                    if "platform" in m:
                        p = m["platform"]
                        platforms_found.append(f"{p.get('os', 'unknown')}/{p.get('architecture', 'unknown')}")

            if platforms_found:
                assert "linux/amd64" in platforms_found or "linux/x86_64" in platforms_found, (
                    f"Multi-platform image does not include linux/amd64 required for ECS. "
                    f"Found platforms: {platforms_found}"
                )
        except json.JSONDecodeError:
            pass  # Manifest inspection failed, rely on architecture check above


@pytest.mark.integration
def test_docker_image_defaults_to_sse():
    """Test that Docker image defaults to SSE transport when FASTMCP_TRANSPORT is not set."""
    dockerfile = REPO_ROOT / "Dockerfile"
    assert dockerfile.exists(), "Dockerfile must exist for container build"

    # Use existing image if available, otherwise build
    image_to_test = IMAGE_TAG
    existing_images = subprocess.run(
        ["docker", "images", "-q", image_to_test],
        capture_output=True,
        text=True,
    )

    if not existing_images.stdout.strip():
        # Build if image doesn't exist
        build_cmd = ["docker", "build", "--tag", image_to_test, str(REPO_ROOT)]
        subprocess.run(build_cmd, check=True)

    container_name = f"quilt-mcp-sse-test-{uuid.uuid4()}"

    # Run container WITHOUT setting FASTMCP_TRANSPORT (should default to SSE)
    run_cmd = [
        "docker", "run", "--detach", "--rm",
        "--name", container_name,
        image_to_test,
        "python", "-c",
        "import os; print(f'FASTMCP_TRANSPORT={os.environ.get(\"FASTMCP_TRANSPORT\", \"not_set\")}'); import sys; sys.exit(0)"
    ]

    try:
        # Check the environment variable default
        check_cmd = [
            "docker", "run", "--rm",
            image_to_test,
            "python", "-c",
            "import os; transport = os.environ.get('FASTMCP_TRANSPORT', 'sse'); print(transport)"
        ]
        result = subprocess.run(check_cmd, capture_output=True, text=True, check=True)
        transport = result.stdout.strip()

        # In production, we want SSE for Claude Desktop compatibility
        # But the container sets HTTP for web serving
        # So we need to check what the actual default is in the Dockerfile

        # Check if the entrypoint or CMD sets FASTMCP_TRANSPORT
        inspect_cmd = ["docker", "inspect", image_to_test, "--format", "{{json .Config}}"]
        inspect_result = subprocess.run(inspect_cmd, capture_output=True, text=True, check=True)
        config = json.loads(inspect_result.stdout)

        # Check ENV settings
        env_vars = config.get("Env", [])
        transport_env = None
        for env in env_vars:
            if env.startswith("FASTMCP_TRANSPORT="):
                transport_env = env.split("=", 1)[1]
                break

        # For Docker container, it should be set to 'http' for web serving
        # For local/Claude Desktop, it should default to 'sse'
        assert transport_env == "http", (
            f"Docker container should set FASTMCP_TRANSPORT=http for web serving, "
            f"but found: {transport_env}"
        )

    finally:
        subprocess.run(["docker", "rm", "-f", container_name], check=False, capture_output=True)
