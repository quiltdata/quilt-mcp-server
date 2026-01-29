"""Test Scenario 1: Basic Tool Execution.

Verify all tools work with read-only filesystem and stateless constraints.
"""

import httpx
import pytest
from docker.models.containers import Container


def test_container_starts_with_stateless_constraints(stateless_container: Container):
    """Verify container starts successfully with all stateless constraints."""
    stateless_container.reload()

    assert stateless_container.status == "running", f"Container should be running but is: {stateless_container.status}"

    # Verify container has expected configuration
    config = stateless_container.attrs["HostConfig"]

    # Check read-only filesystem
    assert config["ReadonlyRootfs"] is True, (
        "❌ FAIL: Container filesystem is NOT read-only\n"
        "Expected: ReadonlyRootfs=true\n"
        f"Actual: ReadonlyRootfs={config['ReadonlyRootfs']}\n"
        "Fix: Add --read-only flag to docker run command"
    )

    # Check security options
    security_opt = config.get("SecurityOpt", [])
    assert "no-new-privileges:true" in security_opt, (
        "❌ FAIL: Container allows privilege escalation\n"
        "Expected: SecurityOpt contains 'no-new-privileges:true'\n"
        f"Actual: SecurityOpt={security_opt}\n"
        "Fix: Add --security-opt=no-new-privileges:true to docker run command"
    )

    # Check capabilities dropped
    cap_drop = config.get("CapDrop", [])
    assert "ALL" in cap_drop or "all" in cap_drop, (
        "❌ FAIL: Container has unnecessary capabilities\n"
        "Expected: CapDrop contains 'ALL'\n"
        f"Actual: CapDrop={cap_drop}\n"
        "Fix: Add --cap-drop=ALL to docker run command"
    )

    # Check memory limit
    memory_limit = config.get("Memory", 0)
    expected_memory = 512 * 1024 * 1024  # 512MB in bytes
    assert memory_limit == expected_memory, (
        f"❌ FAIL: Container memory limit is incorrect\n"
        f"Expected: {expected_memory} bytes (512MB)\n"
        f"Actual: {memory_limit} bytes\n"
        "Fix: Add --memory=512m to docker run command"
    )

    print("✅ Container has correct stateless constraints")


def test_mcp_server_responds(container_url: str):
    """Verify MCP server responds to health check."""
    try:
        response = httpx.get(f"{container_url}/", timeout=10.0)

        assert response.status_code == 200, (
            f"❌ FAIL: MCP server returned unexpected status code\n"
            f"Expected: 200 OK\n"
            f"Actual: {response.status_code}\n"
            f"Response: {response.text}\n"
            "Check container logs for startup errors"
        )

        print(f"✅ MCP server responding: {response.status_code}")

    except httpx.ConnectError as e:
        pytest.fail(
            f"❌ FAIL: Cannot connect to MCP server at {container_url}\n"
            f"Error: {e}\n"
            "Possible causes:\n"
            "  1. Container failed to start MCP server\n"
            "  2. Port mapping is incorrect\n"
            "  3. Server crashed on startup\n"
            "Check container logs with: docker logs <container_id>"
        )
    except httpx.TimeoutException:
        pytest.fail(
            f"❌ FAIL: MCP server at {container_url} timed out\n"
            "Server is running but not responding\n"
            "Check container logs for errors"
        )


def test_tools_list_endpoint(container_url: str):
    """Verify tools/list endpoint works in stateless mode."""
    try:
        # MCP protocol: list available tools
        response = httpx.post(
            f"{container_url}/mcp/v1/tools/list",
            json={"method": "tools/list", "params": {}},
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )

        # Server might return 404 if endpoint structure is different
        # Let's check what endpoints are available
        if response.status_code == 404:
            # Try root to see server info
            root_response = httpx.get(f"{container_url}/", timeout=5.0)
            pytest.fail(
                f"❌ FAIL: tools/list endpoint not found\n"
                f"Tried: {container_url}/mcp/v1/tools/list\n"
                f"Status: {response.status_code}\n"
                f"Server root response: {root_response.text[:500]}\n"
                "Verify MCP protocol endpoint structure"
            )

        assert response.status_code == 200, (
            f"❌ FAIL: tools/list returned error\n"
            f"Expected: 200 OK\n"
            f"Actual: {response.status_code}\n"
            f"Response: {response.text[:500]}\n"
            "Check if MCP server is properly initialized"
        )

        data = response.json()

        # Should return a list of tools
        assert "tools" in data or "result" in data, (
            f"❌ FAIL: tools/list response missing 'tools' or 'result' field\n"
            f"Response: {data}\n"
            "MCP protocol response should contain tools list"
        )

        print("✅ tools/list endpoint working")

    except Exception as e:
        pytest.fail(
            f"❌ FAIL: Error calling tools/list endpoint\n"
            f"Error: {type(e).__name__}: {e}\n"
            "Check MCP server implementation"
        )


def test_no_filesystem_writes_outside_tmpfs(stateless_container: Container):
    """Verify container doesn't write outside tmpfs directories."""
    from .conftest import get_container_filesystem_writes

    # Get filesystem changes
    writes = get_container_filesystem_writes(stateless_container)

    # Filter out acceptable changes
    # Some base image changes are OK (e.g., /etc/hosts, /etc/resolv.conf)
    acceptable_writes = {
        "/etc/hostname",
        "/etc/hosts",
        "/etc/resolv.conf",
        "/.dockerenv",
    }

    unexpected_writes = [path for path in writes if path not in acceptable_writes]

    if unexpected_writes:
        # Create detailed error message
        error_lines = [
            "❌ FAIL: Container wrote files outside tmpfs directories",
            "",
            "Unexpected file changes:",
        ]

        for path in unexpected_writes[:10]:  # Show first 10
            error_lines.append(f"  - {path}")

        if len(unexpected_writes) > 10:
            error_lines.append(f"  ... and {len(unexpected_writes) - 10} more")

        error_lines.extend(
            [
                "",
                "Stateless deployment requires:",
                "  ✓ Only tmpfs directories can be written: /tmp, /app/.cache, /run",
                "  ✗ Root filesystem must remain read-only",
                "",
                "Recommendations:",
                "  1. Check if application is trying to write config/cache files",
                "  2. Set HOME=/tmp to redirect user files to tmpfs",
                "  3. Configure applications to use /tmp for temporary storage",
                "  4. Review container logs for 'Read-only file system' errors",
            ]
        )

        pytest.fail("\n".join(error_lines))

    print("✅ No unexpected filesystem writes detected")


def test_container_continues_running_after_requests(
    stateless_container: Container,
    container_url: str,
):
    """Verify container stays healthy after making several requests."""
    # Make multiple requests
    for i in range(5):
        try:
            response = httpx.get(f"{container_url}/", timeout=5.0)
            assert response.status_code == 200
        except Exception as e:
            pytest.fail(
                f"❌ FAIL: Container became unhealthy after {i} requests\n"
                f"Error: {e}\n"
                "Container may be crashing or hanging"
            )

    # Verify still running
    stateless_container.reload()
    assert stateless_container.status == "running", (
        f"❌ FAIL: Container stopped after handling requests\n"
        f"Status: {stateless_container.status}\n"
        "Check container logs for crashes or errors"
    )

    print("✅ Container stable after multiple requests")
