"""Test Scenario 2: JWT Authentication.

Verify JWT-only authentication works correctly in stateless mode.
"""

import httpx
import pytest
from docker.models.containers import Container


def test_jwt_required_environment_variable(stateless_container: Container):
    """Verify container has MCP_REQUIRE_JWT enabled."""
    stateless_container.reload()
    env_vars = stateless_container.attrs["Config"]["Env"]

    # Parse environment variables
    env_dict = {}
    for env_var in env_vars:
        if "=" in env_var:
            key, value = env_var.split("=", 1)
            env_dict[key] = value

    assert "MCP_REQUIRE_JWT" in env_dict, (
        "❌ FAIL: MCP_REQUIRE_JWT environment variable not set\n"
        "Stateless mode requires JWT-only authentication\n"
        "Fix: Add environment variable MCP_REQUIRE_JWT=true"
    )

    assert env_dict["MCP_REQUIRE_JWT"].lower() == "true", (
        f"❌ FAIL: MCP_REQUIRE_JWT should be 'true'\n"
        f"Actual: MCP_REQUIRE_JWT={env_dict['MCP_REQUIRE_JWT']}\n"
        "Fix: Set MCP_REQUIRE_JWT=true to enforce JWT authentication"
    )

    print("✅ JWT authentication is required")


def test_request_without_jwt_fails_clearly(container_url: str):
    """Verify requests without JWT are rejected with clear error message."""
    try:
        # Attempt to call MCP endpoint without JWT
        # MCP protocol over HTTP uses JSON-RPC 2.0 format at /mcp endpoint
        response = httpx.post(
            f"{container_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            },
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )

        # Should get an error response
        # We'll be lenient about the exact status code (401, 403, or even 400)
        # as long as there's a clear error message

        if response.status_code == 200:
            pytest.fail(
                "❌ FAIL: Server accepted request without JWT token\n"
                "Expected: Authentication error (401/403)\n"
                "Actual: 200 OK (success)\n"
                "\n"
                "Stateless mode MUST enforce JWT authentication:\n"
                "  1. Set MCP_REQUIRE_JWT=true in environment\n"
                "  2. Reject requests without Authorization header\n"
                "  3. Return clear error: 'JWT token required'\n"
                "\n"
                "Security risk: Without JWT enforcement, the server may fall back\n"
                "to local credentials, violating stateless deployment constraints."
            )

        # Check if error message is clear
        response_text = response.text.lower()

        has_jwt_mention = any(keyword in response_text for keyword in ["jwt", "token", "authorization", "auth"])

        if not has_jwt_mention:
            pytest.fail(
                f"❌ FAIL: Error message doesn't mention JWT/authentication\n"
                f"Status: {response.status_code}\n"
                f"Response: {response.text[:200]}\n"
                "\n"
                "Error messages should clearly state:\n"
                "  - 'JWT token required'\n"
                "  - 'Authorization header missing'\n"
                "  - 'Bearer token not provided'\n"
                "\n"
                "Clear error messages help developers debug authentication issues."
            )

        print(f"✅ Request without JWT rejected: {response.status_code}")

    except httpx.RequestError as e:
        pytest.fail(
            f"❌ FAIL: Network error when testing JWT requirement\n"
            f"Error: {e}\n"
            "Server should respond with auth error, not crash"
        )


def test_request_with_malformed_jwt_fails_clearly(container_url: str):
    """Verify requests with malformed JWT are rejected with clear error."""
    try:
        # Send request with invalid JWT to MCP endpoint
        # MCP protocol over HTTP uses JSON-RPC 2.0 format at /mcp endpoint
        response = httpx.post(
            f"{container_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer not-a-valid-jwt-token",
            },
            timeout=10.0,
        )

        # Should get an error (not 200)
        if response.status_code == 200:
            pytest.fail(
                "❌ FAIL: Server accepted malformed JWT token\n"
                "Expected: Authentication error (401/403)\n"
                "Actual: 200 OK (success)\n"
                "\n"
                "Security issue: Server must validate JWT tokens:\n"
                "  1. Parse JWT structure (header.payload.signature)\n"
                "  2. Verify signature with public key\n"
                "  3. Check expiration time\n"
                "  4. Validate required claims\n"
                "\n"
                "Accepting invalid tokens defeats JWT security."
            )

        # Check for clear error message
        response_text = response.text.lower()

        has_validation_mention = any(
            keyword in response_text for keyword in ["invalid", "malformed", "token", "jwt", "signature"]
        )

        if not has_validation_mention:
            pytest.fail(
                f"❌ FAIL: Error doesn't explain JWT validation failure\n"
                f"Status: {response.status_code}\n"
                f"Response: {response.text[:200]}\n"
                "\n"
                "Error should mention:\n"
                "  - 'Invalid JWT token'\n"
                "  - 'Token signature invalid'\n"
                "  - 'Malformed authorization header'\n"
            )

        print(f"✅ Malformed JWT rejected: {response.status_code}")

    except httpx.RequestError as e:
        pytest.fail(
            f"❌ FAIL: Network error when testing JWT validation\n"
            f"Error: {e}\n"
            "Server should validate JWT and return error, not crash"
        )


def test_no_fallback_to_local_credentials(stateless_container: Container):
    """Verify container doesn't try to use ~/.quilt/ credentials."""
    from .conftest import get_container_filesystem_writes

    # Check for any attempts to read/write credential files
    writes = get_container_filesystem_writes(stateless_container)

    # Look for credential-related paths
    credential_paths = [
        path
        for path in writes
        if any(cred_marker in path.lower() for cred_marker in [".quilt", ".aws", "credentials", ".config"])
    ]

    if credential_paths:
        pytest.fail(
            "❌ FAIL: Container attempted to access local credential files\n"
            "\n"
            "Detected credential file access:\n" + "\n".join(f"  - {path}" for path in credential_paths) + "\n\n"
            "Stateless mode MUST NOT use local credentials:\n"
            "  ✗ No ~/.quilt/ directory access\n"
            "  ✗ No ~/.aws/credentials access\n"
            "  ✓ Only JWT tokens for authentication\n"
            "\n"
            "Recommendations:\n"
            "  1. Set MCP_REQUIRE_JWT=true to disable credential file access\n"
            "  2. Configure HOME=/tmp to redirect home directory\n"
            "  3. Remove any code that reads ~/.quilt/ or ~/.aws/\n"
        )

    print("✅ No local credential access detected")


@pytest.mark.skip(reason="Requires valid JWT token from auth server - implement when auth integration ready")
def test_request_with_valid_jwt_succeeds(container_url: str):
    """Verify requests with valid JWT tokens work correctly.

    NOTE: This test is skipped because it requires:
    - Real JWT token from dev auth server
    - Token generation/refresh mechanism
    - Test user account with permissions

    Implement this test when JWT authentication integration is ready.
    """
    # TODO: Implement when JWT auth infrastructure is available
    #
    # Steps:
    # 1. Generate or retrieve valid JWT token for test user
    # 2. Make request with Authorization: Bearer <token>
    # 3. Verify request succeeds (200 OK)
    # 4. Verify token claims are respected (user permissions, etc.)
    pass
