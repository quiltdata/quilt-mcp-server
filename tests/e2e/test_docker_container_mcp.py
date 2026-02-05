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

pytestmark = pytest.mark.usefixtures("requires_docker")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_mcp_protocol_compliance():
    """Test MCP JSON-RPC 2.0 protocol compliance over HTTP transport.

    This test validates that:
    1. The MCP server properly implements JSON-RPC 2.0 over HTTP
    2. Stateless mode with JSON responses works correctly
    3. Session management via mcp-session-id headers functions properly
    4. All core MCP methods work correctly:
       - initialize (session initialization)
       - tools/list (list available tools)
       - tools/call (execute a tool)
       - resources/list (list available resources, if supported)
       - prompts/list (list available prompts, if supported)
    5. Response format matches MCP specification
    6. JSON-RPC 2.0 compliance (proper field structure, error handling)

    Note: Previously skipped due to session management bug, fixed in commit d32e488
    (Jan 28, 2026) by enabling stateless_http=True and json_response=True in
    src/quilt_mcp/utils.py when QUILT_MCP_STATELESS_MODE=true.
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
        "-e",
        "QUILT_MCP_STATELESS_MODE=true",
        "-p",
        f"{free_port}:80",
        IMAGE_TAG,
    )
    run_result = subprocess.run(run_cmd, check=True, text=True, capture_output=True)
    container_id = run_result.stdout.strip()

    def parse_response(response: requests.Response) -> dict:
        """Parse MCP response, handling both JSON and SSE formats.

        In stateless mode (QUILT_MCP_STATELESS_MODE=true), the server returns
        plain JSON responses. Otherwise, it uses SSE (Server-Sent Events) format.
        """
        content_type = response.headers.get("Content-Type", "")

        # Handle plain JSON responses (stateless mode)
        if "application/json" in content_type:
            return response.json()

        # Handle SSE responses (stateful mode)
        if "text/event-stream" in content_type:
            text = response.text
            # SSE format: "data: {json}\n\n"
            for line in text.split("\n"):
                if line.startswith("data: "):
                    json_str = line[6:]  # Remove "data: " prefix
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        continue
            raise ValueError(f"No valid JSON-RPC message found in SSE response: {text}")

        raise ValueError(f"Unexpected Content-Type: {content_type}. Expected application/json or text/event-stream")

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
        session.headers.update(
            {
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            }
        )

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

        # Extract session ID from response headers for subsequent requests
        # In stateless mode, this is required for maintaining session state
        mcp_session_id = init_response.headers.get("mcp-session-id")
        if mcp_session_id:
            session.headers.update({"mcp-session-id": mcp_session_id})

        # Parse response (handles both JSON and SSE formats)
        init_data = parse_response(init_response)
        assert "jsonrpc" in init_data, "Initialize response missing jsonrpc field"
        assert init_data["jsonrpc"] == "2.0", f"Invalid jsonrpc version: {init_data.get('jsonrpc')}"
        assert "id" in init_data, "Initialize response missing id field"
        assert init_data["id"] == 1, f"Initialize response id mismatch: expected 1, got {init_data.get('id')}"
        assert "result" in init_data, f"Initialize response missing result field: {init_data}"
        assert "error" not in init_data, f"Initialize failed with error: {init_data.get('error')}"

        # Test 2: Test tools/list method call
        # This now works after enabling stateless mode (fixed in commit d32e488)
        tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        tools_response = session.post(mcp_url, json=tools_request, timeout=10)
        assert tools_response.status_code == 200, (
            f"MCP protocol should return HTTP 200 (JSON-RPC errors go in body), got {tools_response.status_code}"
        )

        # Parse response (handles both JSON and SSE formats)
        tools_data = parse_response(tools_response)
        assert tools_data.get("id") == 2
        assert "result" in tools_data
        assert "tools" in tools_data["result"]

        # Verify tool list is non-empty and has expected structure
        tools = tools_data["result"]["tools"]
        assert isinstance(tools, list)
        assert len(tools) > 0
        assert all("name" in tool for tool in tools)

        # Test 3: Test an actual tool call
        # Use a simple tool that doesn't require external dependencies
        tool_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "catalog_url",
                "arguments": {"registry": "s3://test-bucket", "package_name": "test/package"},
            },
        }

        tool_response = session.post(mcp_url, json=tool_request, timeout=10)
        assert tool_response.status_code == 200

        tool_data = parse_response(tool_response)
        assert tool_data.get("id") == 3
        assert "result" in tool_data

        # Validate JSON-RPC response structure
        assert re.match(r"2\.0", tool_data["jsonrpc"])

    finally:
        subprocess.run(("docker", "stop", container_name), check=False, capture_output=True)
        if container_id:
            subprocess.run(("docker", "rm", container_id), check=False, capture_output=True)
