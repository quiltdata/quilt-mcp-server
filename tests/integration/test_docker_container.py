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


@pytest.mark.integration
def test_container_has_curl():
    """Verify curl is installed (required for ECS health checks)."""
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

    container_name = f"quilt-mcp-curl-test-{uuid.uuid4()}"

    run_cmd = (
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        container_name,
        IMAGE_TAG,
    )
    run_result = subprocess.run(run_cmd, check=True, text=True, capture_output=True)
    container_id = run_result.stdout.strip()

    try:
        # Check if curl is installed
        result = subprocess.run(
            ["docker", "exec", container_id, "which", "curl"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"curl not found in container: {result.stderr}"
        assert "/usr/bin/curl" in result.stdout, f"curl path unexpected: {result.stdout}"

        # Verify curl version works
        result = subprocess.run(
            ["docker", "exec", container_id, "curl", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"curl --version failed: {result.stderr}"
        assert "curl" in result.stdout.lower(), f"curl version output unexpected: {result.stdout}"

    finally:
        subprocess.run(("docker", "stop", container_name), check=False, capture_output=True)
        if container_id:
            subprocess.run(("docker", "rm", container_id), check=False, capture_output=True)


@pytest.mark.integration
def test_internal_health_check_localhost():
    """Test the EXACT health check command that ECS uses from inside the container."""
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
    container_name = f"quilt-mcp-health-test-{uuid.uuid4()}"

    # Run with EXACT same env vars as ECS deployment
    run_cmd = (
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        container_name,
        "-e",
        "FASTMCP_HOST=0.0.0.0",
        "-e",
        "FASTMCP_PORT=80",
        "-e",
        "FASTMCP_TRANSPORT=http",
        "-p",
        f"{free_port}:80",
        IMAGE_TAG,
    )
    run_result = subprocess.run(run_cmd, check=True, text=True, capture_output=True)
    container_id = run_result.stdout.strip()

    try:
        # Wait for container to be ready (check from outside first)
        deadline = time.time() + DEFAULT_TIMEOUT
        last_exception = None
        external_url = f"http://127.0.0.1:{free_port}/health"

        while time.time() < deadline:
            try:
                response = requests.get(external_url, timeout=5)
                if response.status_code == 200:
                    break
            except Exception as exc:
                last_exception = exc
                time.sleep(2)
        else:
            pytest.fail(f"Container never became ready (external check): {last_exception}")

        # Now test the EXACT command ECS runs inside the container
        # This is the command from ECS task definition health check
        health_check_cmd = [
            "docker",
            "exec",
            container_id,
            "/bin/sh",
            "-c",
            "curl -v -f --max-time 8 http://localhost:80/health 2>&1 || (echo 'HEALTH CHECK FAILED'; exit 1)",
        ]

        result = subprocess.run(health_check_cmd, capture_output=True, text=True, timeout=15)

        # Debug output if it fails
        if result.returncode != 0:
            print("\n=== Health Check Failed ===")
            print(f"Return code: {result.returncode}")
            print(f"STDOUT:\n{result.stdout}")
            print(f"STDERR:\n{result.stderr}")

            # Additional debugging
            ps_result = subprocess.run(
                ["docker", "exec", container_id, "ps", "aux"],
                capture_output=True,
                text=True,
            )
            print(f"\n=== Container Processes ===\n{ps_result.stdout}")

            netstat_result = subprocess.run(
                ["docker", "exec", container_id, "netstat", "-tln"],
                capture_output=True,
                text=True,
            )
            print(f"\n=== Listening Ports ===\n{netstat_result.stdout}")

        assert result.returncode == 0, f"Internal health check failed: {result.stderr}\n{result.stdout}"
        assert "200 OK" in result.stdout or "200 OK" in result.stderr, (
            f"Health check didn't return 200 OK: {result.stdout}\n{result.stderr}"
        )

    finally:
        subprocess.run(("docker", "stop", container_name), check=False, capture_output=True)
        if container_id:
            subprocess.run(("docker", "rm", container_id), check=False, capture_output=True)


@pytest.mark.integration
def test_internal_health_check_all_routes():
    """Test all health check routes from inside the container."""
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
    container_name = f"quilt-mcp-routes-test-{uuid.uuid4()}"

    run_cmd = (
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        container_name,
        "-e",
        "FASTMCP_HOST=0.0.0.0",
        "-e",
        "FASTMCP_PORT=80",
        "-e",
        "FASTMCP_TRANSPORT=http",
        "-p",
        f"{free_port}:80",
        IMAGE_TAG,
    )
    run_result = subprocess.run(run_cmd, check=True, text=True, capture_output=True)
    container_id = run_result.stdout.strip()

    try:
        # Wait for container to be ready
        deadline = time.time() + DEFAULT_TIMEOUT
        last_exception = None
        external_url = f"http://127.0.0.1:{free_port}/health"

        while time.time() < deadline:
            try:
                response = requests.get(external_url, timeout=5)
                if response.status_code == 200:
                    break
            except Exception as exc:
                last_exception = exc
                time.sleep(2)
        else:
            pytest.fail(f"Container never became ready: {last_exception}")

        # Test all health check routes from inside the container
        health_routes = ["/health", "/healthz", "/"]

        for route in health_routes:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_id,
                    "curl",
                    "-f",
                    "--max-time",
                    "5",
                    f"http://localhost:80{route}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert result.returncode == 0, (
                f"Internal health check failed for {route}: {result.stderr}\n{result.stdout}"
            )

            # Verify it's valid JSON with expected structure
            import json

            try:
                health_data = json.loads(result.stdout)
                assert health_data["status"] == "ok", f"Health status not ok at {route}: {health_data}"
                assert "timestamp" in health_data, f"Missing timestamp at {route}"
                assert health_data["route"] == route, f"Route mismatch at {route}: {health_data}"
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON response from {route}: {result.stdout}\nError: {e}")

    finally:
        subprocess.run(("docker", "stop", container_name), check=False, capture_output=True)
        if container_id:
            subprocess.run(("docker", "rm", container_id), check=False, capture_output=True)


@pytest.mark.integration
@pytest.mark.skip(reason="Requires MCP server with known protocol bug")
def test_mcp_protocol_compliance():
    """Test MCP JSON-RPC 2.0 protocol compliance over HTTP transport with SSE.

    This test validates that:
    1. The MCP server properly implements JSON-RPC 2.0 over HTTP
    2. SSE (Server-Sent Events) is used for streaming responses
    3. The initialize and tools/list methods work correctly
    4. Response format matches MCP specification
    """
    import json
    import re

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
    container_name = f"quilt-mcp-protocol-test-{uuid.uuid4()}"

    run_cmd = (
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        container_name,
        "-e",
        "FASTMCP_HOST=0.0.0.0",
        "-e",
        "FASTMCP_PORT=80",
        "-e",
        "FASTMCP_TRANSPORT=http",
        "-p",
        f"{free_port}:80",
        IMAGE_TAG,
    )
    run_result = subprocess.run(run_cmd, check=True, text=True, capture_output=True)
    container_id = run_result.stdout.strip()

    def parse_sse_response(text: str) -> dict:
        """Parse SSE response and extract JSON-RPC message."""
        # SSE format: "data: {json}\n\n"
        for line in text.split("\n"):
            if line.startswith("data: "):
                json_str = line[6:]  # Remove "data: " prefix
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"No valid JSON-RPC message found in SSE response: {text}")

    try:
        # Wait for container to be ready
        deadline = time.time() + DEFAULT_TIMEOUT
        last_exception = None
        health_url = f"http://127.0.0.1:{free_port}/health"

        while time.time() < deadline:
            try:
                response = requests.get(health_url, timeout=5)
                if response.status_code == 200:
                    break
            except Exception as exc:
                last_exception = exc
                time.sleep(2)
        else:
            pytest.fail(f"Container never became ready: {last_exception}")

        # Test MCP protocol endpoint
        mcp_url = f"http://127.0.0.1:{free_port}/mcp"

        # Use a requests.Session to maintain state (cookies, etc.) across requests
        # This is required for MCP session management
        session = requests.Session()
        session.headers.update({
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        })

        # Test 1: Initialize session (required before tools/list)
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        init_response = session.post(mcp_url, json=init_request, timeout=10)
        assert init_response.status_code == 200, (
            f"MCP initialize failed with status {init_response.status_code}: {init_response.text}"
        )

        # Parse SSE response
        content_type = init_response.headers.get("Content-Type", "")
        assert "text/event-stream" in content_type, (
            f"Expected SSE response (text/event-stream), got: {content_type}"
        )

        # Extract session ID from response headers and add to session headers for subsequent requests
        mcp_session_id = init_response.headers.get("mcp-session-id")
        assert mcp_session_id is not None, (
            f"Expected mcp-session-id header in initialize response. "
            f"Headers: {dict(init_response.headers)}"
        )
        session.headers.update({"mcp-session-id": mcp_session_id})

        init_data = parse_sse_response(init_response.text)
        assert "jsonrpc" in init_data, "Initialize response missing jsonrpc field"
        assert init_data["jsonrpc"] == "2.0", f"Invalid jsonrpc version: {init_data.get('jsonrpc')}"
        assert "id" in init_data, "Initialize response missing id field"
        assert init_data["id"] == 1, f"Initialize response id mismatch: expected 1, got {init_data.get('id')}"
        assert "result" in init_data, f"Initialize response missing result field: {init_data}"
        assert "error" not in init_data, f"Initialize failed with error: {init_data.get('error')}"

        # Test 2: Test tools/list method call
        # This should work after a successful initialize, but currently fails with:
        # "MCP error -32602: Invalid request parameters"
        # Same error that MCP Inspector sees!
        tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        tools_response = session.post(mcp_url, json=tools_request, timeout=10)
        assert tools_response.status_code == 200, (
            f"MCP protocol should return HTTP 200 (JSON-RPC errors go in body), got {tools_response.status_code}"
        )

        # Parse SSE response
        tools_data = parse_sse_response(tools_response.text)
        assert "jsonrpc" in tools_data, "tools/list response missing jsonrpc field"
        assert tools_data["jsonrpc"] == "2.0", f"Invalid jsonrpc version: {tools_data.get('jsonrpc')}"
        assert "id" in tools_data, "tools/list response missing id field"
        assert tools_data["id"] == 2, f"tools/list response id mismatch: expected 2, got {tools_data.get('id')}"

        # THIS IS WHERE THE BUG MANIFESTS:
        # Server returns error instead of result
        assert "result" in tools_data, (
            f"tools/list should return result, but got error: {tools_data.get('error')}\n"
            f"This is the same error MCP Inspector sees!\n"
            f"Full response: {tools_data}"
        )
        assert "error" not in tools_data, f"tools/list failed with error: {tools_data.get('error')}"

        # Validate tools/list result structure
        result = tools_data["result"]
        assert "tools" in result, f"tools/list result missing 'tools' field: {result}"
        assert isinstance(result["tools"], list), f"tools/list 'tools' must be a list: {type(result['tools'])}"

        # Verify at least some tools are available
        tools = result["tools"]
        assert len(tools) > 0, "Expected at least one tool to be available"

        # Validate tool structure (check first tool as sample)
        first_tool = tools[0]
        assert "name" in first_tool, f"Tool missing 'name' field: {first_tool}"
        assert "description" in first_tool, f"Tool missing 'description' field: {first_tool}"
        assert "inputSchema" in first_tool, f"Tool missing 'inputSchema' field: {first_tool}"

    finally:
        subprocess.run(("docker", "stop", container_name), check=False, capture_output=True)
        if container_id:
            subprocess.run(("docker", "rm", container_id), check=False, capture_output=True)
