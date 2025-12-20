#!/usr/bin/env python3
"""
MCP Protocol Diagnostic Tool

This script tests the MCP protocol step-by-step to identify where tool calls fail.
It provides detailed logging and captures full request/response cycles.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


class MCPProtocolDiagnostic:
    """Diagnostic tool for MCP protocol debugging."""

    def __init__(self, image: str = "quilt-mcp:test", verbose: bool = True):
        self.image = image
        self.verbose = verbose
        self.process = None
        self.request_id = 1

    def log(self, message: str, level: str = "INFO"):
        """Log message to stderr (to avoid JSON-RPC interference)."""
        prefix = {
            "INFO": "ℹ️ ",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "DEBUG": "🔍",
            "REQUEST": "📤",
            "RESPONSE": "📥",
        }.get(level, "  ")
        print(f"{prefix} {message}", file=sys.stderr)

    def start_server(self) -> bool:
        """Start MCP server via Docker with stdio transport."""
        self.log("Starting MCP server in Docker...", "INFO")
        self.log(f"   Image: {self.image}", "INFO")

        try:
            # Check if image exists
            result = subprocess.run(
                ["docker", "image", "inspect", self.image],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                self.log(f"Image {self.image} not found. Build it first with 'make docker'", "ERROR")
                return False

            # Build docker command
            docker_cmd = [
                "docker", "run", "-i",
                "--name", f"mcp-diagnostic-{int(time.time())}",
                "-e", "FASTMCP_TRANSPORT=stdio",
                self.image,
                "quilt-mcp", "--skip-banner"
            ]

            # Start container as interactive process
            self.process = subprocess.Popen(
                docker_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )

            # Wait for startup
            time.sleep(2)

            # Check if process is still running
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                self.log("Container exited immediately", "ERROR")
                self.log(f"   stderr: {stderr}", "DEBUG")
                return False

            self.log("MCP server started successfully", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"Failed to start server: {e}", "ERROR")
            return False

    def send_request(self, method: str, params: dict) -> dict:
        """Send JSON-RPC request and get response."""
        if not self.process:
            return {"error": "Server not running"}

        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params
        }
        self.request_id += 1

        try:
            # Log request
            if self.verbose:
                self.log(f"Method: {method}", "REQUEST")
                self.log(f"Params: {json.dumps(params, indent=2)}", "DEBUG")

            # Send request
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json)
            self.process.stdin.flush()

            # Read response
            response_line = self.process.stdout.readline()
            if not response_line:
                self.log("No response from server", "ERROR")
                return {"error": "No response"}

            response = json.loads(response_line.strip())

            # Log response
            if self.verbose:
                if "error" in response:
                    self.log(f"Error: {json.dumps(response['error'], indent=2)}", "RESPONSE")
                elif "result" in response:
                    # Truncate large results for readability
                    result = response["result"]
                    if isinstance(result, dict):
                        result_summary = {k: (f"<{len(v)} items>" if isinstance(v, list) else v)
                                        for k, v in list(result.items())[:5]}
                        self.log(f"Result: {json.dumps(result_summary, indent=2)}", "RESPONSE")
                    else:
                        self.log(f"Result: {str(result)[:200]}", "RESPONSE")

            return response

        except Exception as e:
            self.log(f"Communication error: {e}", "ERROR")
            return {"error": str(e)}

    def test_initialize(self) -> bool:
        """Test initialize protocol."""
        self.log("\n=== Test 1: Initialize ===", "INFO")

        response = self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "diagnostic", "version": "1.0"}
        })

        if "error" in response:
            self.log(f"Initialize FAILED: {response['error']}", "ERROR")
            return False

        if "result" in response:
            result = response["result"]
            self.log("Initialize PASSED", "SUCCESS")
            if "capabilities" in result:
                self.log(f"   Server capabilities: {list(result['capabilities'].keys())}", "INFO")
            return True

        return False

    def test_tools_list(self) -> bool:
        """Test tools/list method."""
        self.log("\n=== Test 2: Tools List ===", "INFO")

        response = self.send_request("tools/list", {})

        if "error" in response:
            self.log(f"tools/list FAILED: {response['error']}", "ERROR")
            return False

        if "result" in response and "tools" in response["result"]:
            tools = response["result"]["tools"]
            self.log(f"tools/list PASSED: Found {len(tools)} tools", "SUCCESS")

            # Show sample tools
            if tools:
                sample_tools = [tool["name"] for tool in tools[:5]]
                self.log(f"   Sample tools: {sample_tools}", "INFO")

            return True

        self.log("tools/list FAILED: No tools in response", "ERROR")
        return False

    def test_tool_call_no_args(self) -> bool:
        """Test tools/call with a tool that takes no arguments."""
        self.log("\n=== Test 3: Tool Call (No Arguments) ===", "INFO")

        # Try calling auth_status which should work with minimal args
        response = self.send_request("tools/call", {
            "name": "auth_status",
            "arguments": {}
        })

        if "error" in response:
            self.log(f"tools/call (no args) FAILED: {response['error']}", "ERROR")
            self.log(f"   Error code: {response['error'].get('code')}", "DEBUG")
            self.log(f"   Error message: {response['error'].get('message')}", "DEBUG")
            self.log(f"   Error data: {response['error'].get('data')}", "DEBUG")
            return False

        if "result" in response:
            self.log("tools/call (no args) PASSED", "SUCCESS")
            return True

        return False

    def test_tool_call_with_args(self) -> bool:
        """Test tools/call with arguments."""
        self.log("\n=== Test 4: Tool Call (With Arguments) ===", "INFO")

        # Try calling catalog_configure with arguments
        response = self.send_request("tools/call", {
            "name": "catalog_configure",
            "arguments": {
                "catalog_url": "s3://quilt-ernest-staging"
            }
        })

        if "error" in response:
            self.log(f"tools/call (with args) FAILED: {response['error']}", "ERROR")
            self.log(f"   Error code: {response['error'].get('code')}", "DEBUG")
            self.log(f"   Error message: {response['error'].get('message')}", "DEBUG")
            self.log(f"   Error data: {response['error'].get('data')}", "DEBUG")
            return False

        if "result" in response:
            self.log("tools/call (with args) PASSED", "SUCCESS")
            return True

        return False

    def test_alternate_formats(self) -> bool:
        """Test alternate parameter formats to identify what works."""
        self.log("\n=== Test 5: Alternate Formats ===", "INFO")

        # Test 1: Flat params (no nesting)
        self.log("   Test 5a: Flat params (no 'arguments' key)", "INFO")
        response = self.send_request("tools/call", {
            "name": "auth_status"
        })

        if "result" in response:
            self.log("      Format 5a PASSED: Flat params work!", "SUCCESS")
            return True
        else:
            self.log(f"      Format 5a FAILED: {response.get('error', {}).get('message')}", "ERROR")

        # Test 2: Different nesting
        self.log("   Test 5b: Arguments as 'input' key", "INFO")
        response = self.send_request("tools/call", {
            "name": "auth_status",
            "input": {}
        })

        if "result" in response:
            self.log("      Format 5b PASSED: 'input' key works!", "SUCCESS")
            return True
        else:
            self.log(f"      Format 5b FAILED: {response.get('error', {}).get('message')}", "ERROR")

        return False

    def cleanup(self):
        """Clean up server process."""
        if self.process:
            self.log("\nCleaning up server process...", "INFO")
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.log("Server stopped", "SUCCESS")

    def run_diagnostics(self) -> dict:
        """Run full diagnostic suite."""
        self.log("=" * 70, "INFO")
        self.log("MCP PROTOCOL DIAGNOSTICS", "INFO")
        self.log("=" * 70, "INFO")

        if not self.start_server():
            return {"error": "Failed to start server"}

        try:
            results = {
                "initialize": self.test_initialize(),
                "tools_list": self.test_tools_list(),
                "tool_call_no_args": self.test_tool_call_no_args(),
                "tool_call_with_args": self.test_tool_call_with_args(),
                "alternate_formats": self.test_alternate_formats(),
            }

            # Summary
            self.log("\n" + "=" * 70, "INFO")
            self.log("DIAGNOSTIC SUMMARY", "INFO")
            self.log("=" * 70, "INFO")

            passed = sum(1 for v in results.values() if v)
            total = len(results)

            for test_name, result in results.items():
                status = "✅ PASS" if result else "❌ FAIL"
                self.log(f"   {test_name}: {status}", "INFO")

            self.log(f"\nTotal: {passed}/{total} tests passed", "INFO")

            return results

        finally:
            self.cleanup()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MCP Protocol Diagnostic Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run diagnostics with default image
  python scripts/diagnose-mcp-protocol.py

  # Use custom Docker image
  python scripts/diagnose-mcp-protocol.py --image quiltdata/quilt-mcp-server:latest

  # Quiet mode (less verbose)
  python scripts/diagnose-mcp-protocol.py --quiet
        """
    )

    parser.add_argument(
        "--image",
        default="quilt-mcp:test",
        help="Docker image to test (default: quilt-mcp:test)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce verbosity"
    )

    args = parser.parse_args()

    diagnostic = MCPProtocolDiagnostic(
        image=args.image,
        verbose=not args.quiet
    )

    results = diagnostic.run_diagnostics()

    # Exit with error if any test failed
    if "error" in results:
        sys.exit(1)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
