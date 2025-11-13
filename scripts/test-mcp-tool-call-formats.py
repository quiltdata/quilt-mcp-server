#!/usr/bin/env python3
"""
Minimal MCP test to isolate the protocol issue.

This script sends the absolute minimum messages needed to test tool calling.
"""

import json
import subprocess
import sys
import time


def main():
    """Run minimal MCP test."""
    print("🧪 Minimal MCP Protocol Test", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    # Start Docker container
    print("\n📦 Starting Docker container...", file=sys.stderr)
    docker_cmd = [
        "docker", "run", "-i",
        "--rm",  # Auto-remove when done
        "-e", "FASTMCP_TRANSPORT=stdio",
        "quilt-mcp:test",
        "quilt-mcp", "--skip-banner"
    ]

    try:
        process = subprocess.Popen(
            docker_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    except Exception as e:
        print(f"❌ Failed to start container: {e}", file=sys.stderr)
        return 1

    # Wait for startup
    time.sleep(2)

    if process.poll() is not None:
        stderr = process.stderr.read()
        print(f"❌ Container exited: {stderr}", file=sys.stderr)
        return 1

    print("✅ Container started", file=sys.stderr)

    try:
        # Test 1: Initialize
        print("\n📤 Test 1: Initialize", file=sys.stderr)
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "minimal-test", "version": "1.0"}
            }
        }

        print(f"Request: {json.dumps(init_request)}", file=sys.stderr)
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()

        response_line = process.stdout.readline()
        print(f"Response: {response_line.strip()}", file=sys.stderr)

        response = json.loads(response_line)
        if "error" in response:
            print(f"❌ Initialize failed: {response['error']}", file=sys.stderr)
            return 1

        print("✅ Initialize succeeded", file=sys.stderr)

        # Test 2: Tools list
        print("\n📤 Test 2: Tools List", file=sys.stderr)
        list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        print(f"Request: {json.dumps(list_request)}", file=sys.stderr)
        process.stdin.write(json.dumps(list_request) + "\n")
        process.stdin.flush()

        response_line = process.stdout.readline()
        response = json.loads(response_line)

        if "error" in response:
            print(f"❌ tools/list failed: {response['error']}", file=sys.stderr)
            return 1

        tools = response.get("result", {}).get("tools", [])
        print(f"✅ tools/list succeeded: {len(tools)} tools", file=sys.stderr)

        if tools:
            tool_names = [t["name"] for t in tools[:3]]
            print(f"   First 3 tools: {tool_names}", file=sys.stderr)

        # Test 3: Call a tool (standard format)
        print("\n📤 Test 3: Tool Call (Standard Format)", file=sys.stderr)

        # Use catalog_configure as it's a simple tool
        call_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "catalog_configure",
                "arguments": {
                    "catalog_url": "s3://quilt-ernest-staging"
                }
            }
        }

        print(f"Request: {json.dumps(call_request, indent=2)}", file=sys.stderr)
        process.stdin.write(json.dumps(call_request) + "\n")
        process.stdin.flush()

        response_line = process.stdout.readline()
        print(f"Response: {response_line.strip()}", file=sys.stderr)

        response = json.loads(response_line)

        if "error" in response:
            print(f"❌ tools/call failed: {json.dumps(response['error'], indent=2)}", file=sys.stderr)
            print("\n🔍 This is the key error we need to understand!", file=sys.stderr)

            # Test alternate format
            print("\n📤 Test 4: Tool Call (Alternate Format - No 'arguments' key)", file=sys.stderr)
            alt_request = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "catalog_configure",
                    "catalog_url": "s3://quilt-ernest-staging"  # Flat params
                }
            }

            print(f"Request: {json.dumps(alt_request, indent=2)}", file=sys.stderr)
            process.stdin.write(json.dumps(alt_request) + "\n")
            process.stdin.flush()

            response_line = process.stdout.readline()
            print(f"Response: {response_line.strip()}", file=sys.stderr)

            response = json.loads(response_line)
            if "error" in response:
                print(f"❌ Alternate format also failed: {response['error']['message']}", file=sys.stderr)
            else:
                print("✅ Alternate format WORKED! Found the issue!", file=sys.stderr)
                return 0

            return 1
        else:
            print("✅ tools/call succeeded with standard format", file=sys.stderr)
            return 0

    except Exception as e:
        print(f"❌ Test failed with exception: {e}", file=sys.stderr)
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
        print("✅ Container stopped", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
