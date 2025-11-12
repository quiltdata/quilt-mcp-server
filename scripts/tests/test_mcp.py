#!/usr/bin/env python3
"""
Comprehensive MCP server testing script.

This script:
1. Generates test configuration using mcp-list.py
2. Launches MCP server in Docker container
3. Runs tool tests via stdio transport with configurable test selection
4. Cleans up Docker container on exit

By default, only runs idempotent (read-only) tests.

Note: This script does NOT use mcp-test.py (that's a separate HTTP-based manual testing tool).
This script implements its own stdio-based testing via run_tests_stdio().
"""

import argparse
import asyncio
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("❌ PyYAML is required. Install with: uv pip install pyyaml")
    sys.exit(1)

# Script paths
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_DIR = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
MCP_LIST_SCRIPT = SCRIPTS_DIR / "mcp-list.py"
MCP_TEST_SCRIPT = SCRIPTS_DIR / "mcp-test.py"
TEST_CONFIG_PATH = SCRIPT_DIR / "mcp-test.yaml"

# Docker settings
DEFAULT_IMAGE = "quiltdata/quilt-mcp-server:latest"
DEFAULT_PORT = 8765


class DockerMCPServer:
    """Manages Docker container lifecycle for MCP server testing (stdio transport)."""

    def __init__(self, image: str = DEFAULT_IMAGE, port: int = DEFAULT_PORT):
        self.image = image
        self.port = port  # Not used in stdio mode, kept for compatibility
        self.container_name = f"mcp-test-{uuid.uuid4().hex[:8]}"
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        """Start MCP server in Docker container with stdio transport."""
        print(f"🚀 Starting MCP server in Docker (stdio transport)...")
        print(f"   Image: {self.image}")
        print(f"   Container: {self.container_name}")

        try:
            # Check if image exists, pull if not
            result = subprocess.run(
                ["docker", "image", "inspect", self.image],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"📥 Pulling Docker image: {self.image}")
                subprocess.run(["docker", "pull", self.image], check=True)

            # Build docker run command with AWS credentials
            # Use stdio transport for testing - simpler and no session issues
            aws_creds_path = Path.home() / ".aws"
            docker_cmd = [
                "docker", "run", "-i",  # Interactive for stdio
                "--name", self.container_name,
            ]

            # Mount AWS credentials if they exist
            if aws_creds_path.exists():
                docker_cmd.extend([
                    "-v", f"{aws_creds_path}:/root/.aws:ro",  # Read-only mount
                ])

            # Add environment variables from test config or environment
            # Priority: environment variable > test config > defaults
            aws_region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            aws_profile = os.getenv("AWS_PROFILE", "default")

            docker_cmd.extend([
                "-e", f"AWS_REGION={aws_region}",
                "-e", f"AWS_PROFILE={aws_profile}",
                "-e", "FASTMCP_TRANSPORT=stdio",  # Use stdio instead of HTTP
            ])

            docker_cmd.extend([
                self.image,
                "quilt-mcp", "--skip-banner"  # Run with stdio transport
            ])

            # Start container as interactive process
            self.process = subprocess.Popen(
                docker_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )

            # Wait a moment for startup
            time.sleep(2)

            # Check if process is still running
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                print(f"❌ Container exited immediately")
                print(f"   stderr: {stderr}")
                return False

            print(f"✅ Container started with stdio transport")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to start container: {e}")
            print(f"   stdout: {e.stdout}")
            print(f"   stderr: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False

    def stop(self):
        """Stop and remove Docker container."""
        if not self.process:
            return

        print(f"\n🛑 Stopping container {self.container_name}...")
        try:
            # Terminate the process
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("⚠️  Timeout, force killing...")
                self.process.kill()
                self.process.wait()

            # Remove the container
            subprocess.run(
                ["docker", "rm", "-f", self.container_name],
                capture_output=True,
                timeout=10
            )
            print("✅ Container cleaned up")
        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")
            subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True)

    def logs(self, tail: int = 50):
        """Print container logs."""
        if not self.process:
            return

        print(f"\n📋 Container stderr output:")
        if self.process.stderr:
            try:
                stderr_lines = self.process.stderr.readlines()
                for line in stderr_lines[-tail:]:
                    print(line.rstrip())
            except Exception as e:
                print(f"Could not read stderr: {e}")


def generate_test_config() -> bool:
    """Generate test configuration using mcp-list.py."""
    print("🔧 Generating test configuration...")

    try:
        result = subprocess.run(
            [sys.executable, str(MCP_LIST_SCRIPT)],
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate test config: {e}")
        print(f"   stdout: {e.stdout}")
        print(f"   stderr: {e.stderr}")
        return False


def filter_tests_by_idempotence(config_path: Path, idempotent_only: bool) -> list[str]:
    """Filter test tools based on idempotence flag."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    test_tools = config.get('test_tools', {})
    filtered = []

    for tool_name, tool_config in test_tools.items():
        is_idempotent = tool_config.get('idempotent', True)
        if idempotent_only and is_idempotent:
            filtered.append(tool_name)
        elif not idempotent_only:
            filtered.append(tool_name)

    return filtered


def run_tests_stdio(
    server: DockerMCPServer,
    config_path: Path,
    tools: Optional[list[str]] = None,
    verbose: bool = False
) -> bool:
    """Run MCP tests using stdio transport."""
    import json

    print(f"\n🧪 Running MCP tests (stdio)...")
    print(f"   Config: {config_path}")

    if tools:
        print(f"   Testing {len(tools)} tools")

    if not server.process or server.process.poll() is not None:
        print("❌ Server process not running")
        return False

    try:
        # Load test configuration
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        test_tools = config.get("test_tools", {})
        if tools:
            test_tools = {k: v for k, v in test_tools.items() if k in tools}

        # Send initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        }

        server.process.stdin.write(json.dumps(init_request) + "\n")
        server.process.stdin.flush()
        response = server.process.stdout.readline()

        if verbose:
            print(f"Initialize: {response[:100]}")

        if not response or "error" in response:
            print(f"❌ Initialize failed: {response}")
            return False

        # ✅ FIX: Send notifications/initialized notification (required by MCP protocol)
        # This notification must be sent after receiving initialize response
        # and before making any tool calls. Without it, the server remains in
        # "initializing" state and rejects tool calls with error -32602.
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
            # Note: No "id" field - this is a notification, not a request
        }

        server.process.stdin.write(json.dumps(initialized_notification) + "\n")
        server.process.stdin.flush()

        # Give server a moment to process notification (no response expected)
        time.sleep(0.5)

        if verbose:
            print("Sent notifications/initialized")

        # Test each tool
        success_count = 0
        fail_count = 0
        request_id = 2

        for tool_name, test_config in test_tools.items():
            try:
                start_time = time.time()
                test_args = test_config.get("arguments", {})

                # Call the tool
                tool_request = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": test_args
                    }
                }

                if verbose:
                    print(f"\nRequest: {json.dumps(tool_request, indent=2)}")

                server.process.stdin.write(json.dumps(tool_request) + "\n")
                server.process.stdin.flush()
                response = server.process.stdout.readline()
                elapsed = time.time() - start_time

                if verbose:
                    print(f"Response: {response[:200]}")

                if not response:
                    fail_count += 1
                    print(f"  ❌ {tool_name}: No response ({elapsed:.2f}s)")
                    continue

                result = json.loads(response)
                if "error" in result:
                    fail_count += 1
                    print(f"  ❌ {tool_name}: {result['error'].get('message', 'Unknown error')} ({elapsed:.2f}s)")
                    if verbose:
                        print(f"     {result}")
                else:
                    success_count += 1
                    print(f"  ✅ {tool_name} ({elapsed:.2f}s)")

                    # Show tool result content in verbose mode
                    if verbose and "result" in result:
                        tool_result = result["result"]
                        if "content" in tool_result:
                            content = tool_result["content"]
                            if isinstance(content, list) and len(content) > 0:
                                # Show first content item
                                first_item = content[0]
                                if isinstance(first_item, dict) and "text" in first_item:
                                    # Truncate long text responses
                                    text = first_item["text"]
                                    if len(text) > 500:
                                        print(f"     Result: {text[:500]}...")
                                    else:
                                        print(f"     Result: {text}")
                                else:
                                    print(f"     Result: {json.dumps(first_item, indent=6)[:500]}")
                            elif isinstance(content, str):
                                print(f"     Result: {content[:500]}")

                request_id += 1

            except Exception as e:
                fail_count += 1
                print(f"  ❌ {tool_name}: {e}")
                if verbose:
                    import traceback
                    print(f"     {traceback.format_exc()}")

        print(f"\n📊 Test Results: {success_count}/{len(test_tools)} passed")
        return fail_count == 0

    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        if verbose:
            import traceback
            print(traceback.format_exc())
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Comprehensive MCP server testing with Docker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run via make (automatically runs as part of test-scripts)
  make test-scripts

  # Run directly - idempotent (read-only) tests only (default)
  python scripts/tests/test_mcp.py

  # Run all tests including write operations
  python scripts/tests/test_mcp.py --all

  # Use custom Docker image
  python scripts/tests/test_mcp.py --image quiltdata/quilt-mcp-server:dev

  # Verbose output
  python scripts/tests/test_mcp.py -v

  # Skip Docker, test existing server
  python scripts/tests/test_mcp.py --no-docker --endpoint http://localhost:8000/mcp
        """
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tests including non-idempotent (write) operations"
    )
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Skip Docker container launch, use existing server"
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="MCP endpoint URL (default: http://localhost:{port}/mcp)"
    )
    parser.add_argument(
        "--image",
        default=DEFAULT_IMAGE,
        help=f"Docker image to use (default: {DEFAULT_IMAGE})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to expose Docker container on (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--no-generate",
        action="store_true",
        help="Skip test config generation (use existing)"
    )
    parser.add_argument(
        "--keep-container",
        action="store_true",
        help="Keep Docker container running after tests"
    )
    parser.add_argument(
        "--logs",
        action="store_true",
        help="Show container logs after tests"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Generate test configuration
    if not args.no_generate:
        if not generate_test_config():
            sys.exit(1)
    elif not TEST_CONFIG_PATH.exists():
        print(f"❌ Test config not found: {TEST_CONFIG_PATH}")
        print("   Run without --no-generate to generate it")
        sys.exit(1)

    # Filter tests based on idempotence
    if args.all:
        print("🔓 Running ALL tests (including write operations)")
        tools = filter_tests_by_idempotence(TEST_CONFIG_PATH, idempotent_only=False)
    else:
        print("===🧪 Running MCP server integration tests (idempotent only)...")
        tools = filter_tests_by_idempotence(TEST_CONFIG_PATH, idempotent_only=True)

    print(f"📋 Selected {len(tools)} tools for testing")

    # Start Docker container if needed
    server = None
    if not args.no_docker:
        server = DockerMCPServer(image=args.image, port=args.port)
        if not server.start():
            sys.exit(1)

    try:
        # Run tests using stdio transport
        if server:
            success = run_tests_stdio(server, TEST_CONFIG_PATH, tools, args.verbose)
        else:
            print("❌ No server available for testing")
            success = False

        # Show logs if requested
        if args.logs and server:
            server.logs()

        sys.exit(0 if success else 1)

    finally:
        # Clean up Docker container
        if server and not args.keep_container:
            server.stop()
        elif server and args.keep_container:
            print(f"\n💡 Container kept running: {server.container_name}")
            print(f"   Note: Container is using stdio, cannot connect externally")


if __name__ == "__main__":
    main()
