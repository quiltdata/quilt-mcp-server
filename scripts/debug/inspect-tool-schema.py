#!/usr/bin/env python3
"""
Inspect tool schemas from tools/list to understand expected parameter format.

This will show us what the MCP server is advertising as the schema for each tool,
which should tell us how to format the tools/call request.
"""

import json
import subprocess
import sys
import time


def main():
    """Inspect tool schemas."""
    print("🔍 Inspecting Tool Schemas from MCP Server", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    # Start Docker container
    print("\n📦 Starting Docker container...", file=sys.stderr)
    docker_cmd = [
        "docker", "run", "-i",
        "--rm",
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

    time.sleep(2)

    if process.poll() is not None:
        stderr = process.stderr.read()
        print(f"❌ Container exited: {stderr}", file=sys.stderr)
        return 1

    print("✅ Container started", file=sys.stderr)

    try:
        # Initialize
        print("\n📤 Initializing...", file=sys.stderr)
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "schema-inspector", "version": "1.0"}
            }
        }

        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        response_line = process.stdout.readline()
        response = json.loads(response_line)

        if "error" in response:
            print(f"❌ Initialize failed: {response['error']}", file=sys.stderr)
            return 1

        print("✅ Initialized", file=sys.stderr)

        # Get tools list
        print("\n📤 Getting tools/list...", file=sys.stderr)
        list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        process.stdin.write(json.dumps(list_request) + "\n")
        process.stdin.flush()
        response_line = process.stdout.readline()
        response = json.loads(response_line)

        if "error" in response:
            print(f"❌ tools/list failed: {response['error']}", file=sys.stderr)
            return 1

        tools = response.get("result", {}).get("tools", [])
        print(f"✅ Found {len(tools)} tools", file=sys.stderr)

        # Find a few key tools and inspect their schemas
        key_tools = ["catalog_configure", "auth_status", "bucket_object_fetch"]

        print("\n" + "=" * 70, file=sys.stderr)
        print("TOOL SCHEMAS", file=sys.stderr)
        print("=" * 70, file=sys.stderr)

        for tool in tools:
            if tool["name"] in key_tools:
                print(f"\n📋 Tool: {tool['name']}", file=sys.stderr)
                print(f"   Description: {tool.get('description', 'N/A')[:80]}", file=sys.stderr)

                input_schema = tool.get("inputSchema", {})
                print(f"\n   Input Schema:", file=sys.stderr)
                print(json.dumps(input_schema, indent=6), file=sys.stderr)

                # Check if it has properties
                properties = input_schema.get("properties", {})
                required = input_schema.get("required", [])

                if properties:
                    print(f"\n   Properties ({len(properties)} total):", file=sys.stderr)
                    for prop_name, prop_schema in list(properties.items())[:3]:  # Show first 3
                        prop_type = prop_schema.get("type", "unknown")
                        is_required = "✓" if prop_name in required else " "
                        print(f"      [{is_required}] {prop_name}: {prop_type}", file=sys.stderr)
                        if "description" in prop_schema:
                            print(f"          {prop_schema['description'][:60]}", file=sys.stderr)

                print("\n   " + "-" * 66, file=sys.stderr)

        # Now let's also check the MCP specification format
        print("\n" + "=" * 70, file=sys.stderr)
        print("MCP PROTOCOL INVESTIGATION", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("\nBased on the schemas above, the tools/call request should match", file=sys.stderr)
        print("the inputSchema structure. Let me test different formats...\n", file=sys.stderr)

        # Test with catalog_configure
        test_tool = None
        for tool in tools:
            if tool["name"] == "catalog_configure":
                test_tool = tool
                break

        if not test_tool:
            print("❌ Could not find catalog_configure tool", file=sys.stderr)
            return 1

        schema = test_tool.get("inputSchema", {})
        properties = schema.get("properties", {})

        print(f"🧪 Testing catalog_configure", file=sys.stderr)
        print(f"   Expected properties: {list(properties.keys())}", file=sys.stderr)

        # Format 1: Standard MCP format with arguments
        print("\n📤 Format 1: Standard (arguments object)", file=sys.stderr)
        call_request_1 = {
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

        print(f"   Request: {json.dumps(call_request_1['params'], indent=6)}", file=sys.stderr)
        process.stdin.write(json.dumps(call_request_1) + "\n")
        process.stdin.flush()
        response_line = process.stdout.readline()
        response = json.loads(response_line)

        if "error" in response:
            print(f"   ❌ FAILED: {response['error']['message']}", file=sys.stderr)
        else:
            print(f"   ✅ SUCCESS!", file=sys.stderr)
            return 0

        # Format 2: Flat params
        print("\n📤 Format 2: Flat (tool args at params level)", file=sys.stderr)
        call_request_2 = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "catalog_configure",
                "catalog_url": "s3://quilt-ernest-staging"
            }
        }

        print(f"   Request: {json.dumps(call_request_2['params'], indent=6)}", file=sys.stderr)
        process.stdin.write(json.dumps(call_request_2) + "\n")
        process.stdin.flush()
        response_line = process.stdout.readline()
        response = json.loads(response_line)

        if "error" in response:
            print(f"   ❌ FAILED: {response['error']['message']}", file=sys.stderr)
        else:
            print(f"   ✅ SUCCESS!", file=sys.stderr)
            return 0

        # Format 3: Different key name
        print("\n📤 Format 3: With 'input' key", file=sys.stderr)
        call_request_3 = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "catalog_configure",
                "input": {
                    "catalog_url": "s3://quilt-ernest-staging"
                }
            }
        }

        print(f"   Request: {json.dumps(call_request_3['params'], indent=6)}", file=sys.stderr)
        process.stdin.write(json.dumps(call_request_3) + "\n")
        process.stdin.flush()
        response_line = process.stdout.readline()
        response = json.loads(response_line)

        if "error" in response:
            print(f"   ❌ FAILED: {response['error']['message']}", file=sys.stderr)
        else:
            print(f"   ✅ SUCCESS!", file=sys.stderr)
            return 0

        print("\n❌ All formats failed! This requires deeper investigation.", file=sys.stderr)
        print("\nPossible causes:", file=sys.stderr)
        print("1. FastMCP version mismatch or bug", file=sys.stderr)
        print("2. Protocol version incompatibility", file=sys.stderr)
        print("3. Server-side validation issue", file=sys.stderr)
        print("4. Missing required initialization step", file=sys.stderr)

        return 1

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
