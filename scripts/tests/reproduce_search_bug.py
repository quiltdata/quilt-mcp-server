#!/usr/bin/env python3
"""
Minimal standalone script to reproduce search_catalog bug in stateless mode.

Reproduces the regression identified in spec/a11-client-testing/19-test-comparison-analysis.md:
- search_catalog works in stdio mode (test-mcp-docker)
- search_catalog returns 0 results in HTTP+JWT stateless mode (test-mcp-stateless)

KEY INSIGHT: Uses a Platform JWT directly as Bearer token.
No AWS role wrapping, no catalog token wrapping.

Usage:
    # Provide Platform JWT via environment
    export MCP_JWT_TOKEN=eyJhbGciOi...

    # Build image and run
    make docker-build
    uv run python scripts/tests/reproduce_search_bug.py
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

# Add tests dir to path for jwt_helpers
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / 'tests'))

# Configuration
CONTAINER_NAME = "mcp-search-bug-repro"
DOCKER_IMAGE = "quilt-mcp:test"
PORT = 8003
MCP_ENDPOINT = f"http://localhost:{PORT}/mcp"

# Test cases from mcp-test.yaml that fail in stateless mode
TEST_CASES = [
    {
        "name": "search_catalog.global.no_bucket",
        "tool": "search_catalog",
        "arguments": {"query": "README.md", "limit": 10, "scope": "global", "bucket": ""},
        "expected_min_results": 1
    },
    {
        "name": "search_catalog.file.no_bucket",
        "tool": "search_catalog",
        "arguments": {"query": "README.md", "limit": 10, "scope": "file", "bucket": ""},
        "expected_min_results": 1
    },
    {
        "name": "search_catalog.package.no_bucket",
        "tool": "search_catalog",
        "arguments": {"query": "raw/test", "limit": 10, "scope": "package", "bucket": ""},
        "expected_min_results": 1
    }
]


def start_simple_http_container():
    """Start MCP container with HTTP transport (NO JWT wrapping)."""
    print("\n" + "=" * 80)
    print("STEP 1: Starting HTTP Container (NO JWT wrapping)")
    print("=" * 80)

    # Check if image exists
    result = subprocess.run(["docker", "image", "inspect", DOCKER_IMAGE], capture_output=True)
    if result.returncode != 0:
        print(f"❌ Docker image not found: {DOCKER_IMAGE}")
        print("   Build with: make docker-build")
        return False

    # Stop existing container if running
    subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True)
    subprocess.run(["docker", "rm", CONTAINER_NAME], capture_output=True)

    # Start simple HTTP container (NO MCP_REQUIRE_JWT, NO role ARN)
    print(f"Starting container on port {PORT}...")
    docker_cmd = [
        "docker", "run", "-d", "--name", CONTAINER_NAME,
        "-e", "FASTMCP_TRANSPORT=http",
        "-e", "FASTMCP_HOST=0.0.0.0",
        "-e", "FASTMCP_PORT=8000",
        "-e", "LOG_LEVEL=DEBUG",
        "-p", f"{PORT}:8000",
        DOCKER_IMAGE
    ]

    result = subprocess.run(docker_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Failed to start container: {result.stderr}")
        return False

    time.sleep(3)

    # Verify running
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    if CONTAINER_NAME not in result.stdout:
        print("❌ Container failed to start")
        subprocess.run(["docker", "logs", CONTAINER_NAME])
        return False

    print(f"✅ Container started: {MCP_ENDPOINT}")
    return True


def parse_sse_response(response_text):
    """Parse Server-Sent Events (SSE) response and extract JSON data."""
    # SSE format: "event: message\ndata: {json}\n\n"
    for line in response_text.split('\n'):
        if line.startswith('data: '):
            json_str = line[6:]  # Remove "data: " prefix
            return json.loads(json_str)
    raise ValueError(f"No data line found in SSE response: {response_text[:200]}")


def extract_platform_jwt():
    """Extract platform JWT from environment."""
    print("\n" + "=" * 80)
    print("STEP 2: Loading Platform JWT from environment")
    print("=" * 80)

    jwt_token = os.getenv("MCP_JWT_TOKEN")
    if not jwt_token:
        print("❌ MCP_JWT_TOKEN not set")
        print("   Export MCP_JWT_TOKEN with a valid Platform JWT")
        return None

    print(f"✅ Found MCP_JWT_TOKEN")
    print(f"   Token: {jwt_token[:20]}...{jwt_token[-10:]}")
    return jwt_token


def initialize_mcp_session(jwt_token):
    """Initialize MCP session with Platform JWT as Bearer token."""
    print("\n" + "=" * 80)
    print("STEP 3: Initializing MCP Session with Catalog JWT")
    print("=" * 80)

    session = requests.Session()
    session.headers.update({
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {jwt_token}'
    })

    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "search-bug-repro", "version": "1.0.0"}
        }
    }

    try:
        response = session.post(MCP_ENDPOINT, json=init_request, timeout=10)
        response.raise_for_status()

        # Parse SSE response
        result = parse_sse_response(response.text)

        if "error" in result:
            print(f"❌ Initialization failed: {result['error']}")
            return None

        # Extract session ID from response headers
        session_id = response.headers.get('mcp-session-id')
        if session_id:
            session.headers.update({'mcp-session-id': session_id})
            print(f"✅ MCP session initialized (session ID: {session_id[:16]}...)")
        else:
            print("✅ MCP session initialized")

        print(f"   Server: {result.get('result', {}).get('serverInfo', {}).get('name', 'unknown')}")

        # Send initialized notification
        session.post(MCP_ENDPOINT, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=10)
        return session

    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        if 'response' in locals():
            print(f"   Response text: {response.text[:500]}")
        return None


def run_search_tests(session):
    """Run search_catalog tests."""
    print("\n" + "=" * 80)
    print("STEP 4: Running Search Tests")
    print("=" * 80)

    results = []
    request_id = 10

    for test_case in TEST_CASES:
        print(f"\n--- Test: {test_case['name']} ---")
        print(f"Query: {test_case['arguments']['query']}, Scope: {test_case['arguments']['scope']}")

        tool_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": test_case['tool'], "arguments": test_case['arguments']}
        }
        request_id += 1

        try:
            response = session.post(MCP_ENDPOINT, json=tool_request, timeout=15)
            response.raise_for_status()

            # Parse SSE response
            result = parse_sse_response(response.text)

            if "error" in result:
                print(f"❌ Error: {result['error']}")
                results.append({"test": test_case['name'], "passed": False, "error": result['error']})
                continue

            # Extract search results
            tool_result = result.get("result", {})
            content = tool_result.get("content", [])

            if content and len(content) > 0:
                search_data = json.loads(content[0].get("text", "{}"))
            else:
                search_data = tool_result

            result_count = len(search_data.get("results", []))
            expected_min = test_case['expected_min_results']

            print(f"Results: {result_count} (expected ≥{expected_min})")

            if result_count >= expected_min:
                print(f"✅ PASSED")
                results.append({"test": test_case['name'], "passed": True, "result_count": result_count})
            else:
                print(f"❌ FAILED - BUG REPRODUCED: Got {result_count} results")
                # Print the actual response for debugging
                if result_count == 0:
                    print(f"   Full response: {json.dumps(search_data, indent=2)[:500]}")
                results.append({
                    "test": test_case['name'],
                    "passed": False,
                    "result_count": result_count,
                    "expected_min": expected_min
                })

        except Exception as e:
            print(f"❌ Exception: {e}")
            if 'response' in locals():
                print(f"   Response text: {response.text[:500]}")
            results.append({"test": test_case['name'], "passed": False, "error": str(e)})

    return results


def print_summary(results):
    """Print test summary."""
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results if r['passed'])
    failed = sum(1 for r in results if not r['passed'])

    print(f"\nTotal: {len(results)} | ✅ Passed: {passed} | ❌ Failed: {failed}")

    if failed > 0:
        print("\n⚠️  BUG CONFIRMED: search_catalog returns 0 results in HTTP mode")
        print("\nFailed tests:")
        for r in results:
            if not r['passed']:
                print(f"  - {r['test']}: got {r.get('result_count', '?')} results, expected ≥{r.get('expected_min', 1)}")
    else:
        print("\n✅ All tests passed - bug may be fixed!")

    return failed == 0


def stop_container():
    """Stop and remove container."""
    print("\n" + "=" * 80)
    print("CLEANUP")
    print("=" * 80)
    subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True)
    subprocess.run(["docker", "rm", CONTAINER_NAME], capture_output=True)
    print("✅ Container stopped")


def main():
    """Main test flow."""
    print("=" * 80)
    print("SEARCH_CATALOG BUG REPRODUCTION")
    print("=" * 80)
    print("\nReproduces: search works in stdio, fails in HTTP+JWT mode\n")

    try:
        if not start_simple_http_container():
            return 1

        jwt_token = extract_platform_jwt()
        if not jwt_token:
            stop_container()
            return 1

        session = initialize_mcp_session(jwt_token)
        if not session:
            stop_container()
            return 1

        results = run_search_tests(session)
        success = print_summary(results)

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
        return 1
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        stop_container()


if __name__ == "__main__":
    sys.exit(main())
