#!/usr/bin/env python3
"""
Test the MCP protocol with proper initialization sequence.

According to MCP spec, after receiving initialize response, the client MUST
send a notifications/initialized notification before calling tools.

This test verifies if that's the missing piece.
"""

import json
import subprocess
import sys
import time


def main():
    """Test with proper MCP initialization sequence."""
    print("🧪 Testing MCP Protocol with notifications/initialized", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    # Start Docker container
    print("\n📦 Starting Docker container...", file=sys.stderr)
    docker_cmd = [
        "docker",
        "run",
        "-i",
        "--rm",
        "-e",
        "FASTMCP_TRANSPORT=stdio",
        "quilt-mcp:test",
        "quilt-mcp",
        "--skip-banner",
    ]

    try:
        process = subprocess.Popen(
            docker_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
        )
    except Exception as e:
        print(f"❌ Failed to start container: {e}", file=sys.stderr)
        return 1

    time.sleep(2)

    if process.poll() is not None:
        stderr = process.stderr.read()
        print(f"❌ Container exited: {stderr}", file=sys.stderr)
        return 1

    print("✅ Container started", file=sys.stderr)

    try:
        # Step 1: Initialize
        print("\n📤 Step 1: Sending initialize request", file=sys.stderr)
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "protocol-test", "version": "1.0"},
            },
        }

        print(f"   → {json.dumps(init_request)}", file=sys.stderr)
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()

        response_line = process.stdout.readline()
        print(f"   ← {response_line.strip()}", file=sys.stderr)
        response = json.loads(response_line)

        if "error" in response:
            print(f"❌ Initialize failed: {response['error']}", file=sys.stderr)
            return 1

        print("✅ Initialize succeeded", file=sys.stderr)

        # Step 2: Send notifications/initialized (THIS IS THE KEY!)
        print("\n📤 Step 2: Sending notifications/initialized notification", file=sys.stderr)
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            # NOTE: No "id" field - this is a notification, not a request
        }

        print(f"   → {json.dumps(initialized_notification)}", file=sys.stderr)
        process.stdin.write(json.dumps(initialized_notification) + "\n")
        process.stdin.flush()

        # Notifications don't get responses, but give server a moment to process
        time.sleep(0.5)
        print("✅ Notification sent (no response expected)", file=sys.stderr)

        # Step 3: Now try tools/call
        print("\n📤 Step 3: Calling tool (after initialization complete)", file=sys.stderr)
        call_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "catalog_configure", "arguments": {"catalog_url": "s3://quilt-ernest-staging"}},
        }

        print(f"   → {json.dumps(call_request, indent=2)}", file=sys.stderr)
        process.stdin.write(json.dumps(call_request) + "\n")
        process.stdin.flush()

        response_line = process.stdout.readline()
        print(f"   ← {response_line.strip()[:200]}", file=sys.stderr)
        response = json.loads(response_line)

        if "error" in response:
            print(f"\n❌ Tool call still failed: {json.dumps(response['error'], indent=2)}", file=sys.stderr)
            print("\n⚠️  The notifications/initialized was NOT the issue.", file=sys.stderr)
            print("    Need to investigate further...", file=sys.stderr)
            return 1
        else:
            print(f"\n✅ SUCCESS! Tool call worked after notifications/initialized!", file=sys.stderr)
            print("\n🎯 FOUND THE ISSUE:", file=sys.stderr)
            print("    The test suite was missing the notifications/initialized", file=sys.stderr)
            print("    notification required by the MCP protocol.", file=sys.stderr)
            print("\n📋 Fix required:", file=sys.stderr)
            print("    Update scripts/tests/test_mcp.py to send notifications/initialized", file=sys.stderr)
            print("    after receiving initialize response and before calling tools.", file=sys.stderr)
            return 0

    except Exception as e:
        print(f"❌ Test failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        return 1
    finally:
        print("\n🛑 Stopping container...", file=sys.stderr)
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    sys.exit(main())
