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


class LocalMCPServer:
    """Manages local MCP server process lifecycle for testing."""

    def __init__(self, python_path: Optional[str] = None):
        """Initialize local server configuration.

        Args:
            python_path: Path to Python executable (default: uv's Python)
        """
        self.python_path = python_path or sys.executable
        self.process: Optional[subprocess.Popen] = None
        self.server_id = f"local-{uuid.uuid4().hex[:8]}"

    def start(self) -> bool:
        """Start MCP server as local subprocess with stdio transport.

        Returns:
            True if server started successfully, False otherwise
        """
        print(f"🚀 Starting local MCP server...")
        print(f"   Python: {self.python_path}")
        print(f"   Server ID: {self.server_id}")

        try:
            # Build environment with necessary variables
            env = os.environ.copy()
            env["FASTMCP_TRANSPORT"] = "stdio"

            # Optional: inherit AWS credentials from environment
            # (already present in env if user is configured)

            # Start server process using uv
            cmd = [
                "uv", "run",
                "python", "src/main.py",
                "--skip-banner"
            ]

            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                cwd=REPO_ROOT,  # Run from repo root
                env=env
            )

            # Brief wait for startup
            time.sleep(0.5)  # Much faster than Docker's 2s

            # Check if process is still running
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                print(f"❌ Server exited immediately")
                print(f"   stderr: {stderr}")
                return False

            print(f"✅ Server started (PID: {self.process.pid})")
            return True

        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False

    def stop(self):
        """Stop local server process."""
        if not self.process:
            return

        print(f"\n🛑 Stopping server {self.server_id}...")
        try:
            # Send SIGTERM for graceful shutdown
            self.process.terminate()
            try:
                # Wait for graceful shutdown (shorter timeout than Docker)
                self.process.wait(timeout=3)
                print("✅ Server stopped gracefully")
            except subprocess.TimeoutExpired:
                print("⚠️  Timeout, force killing...")
                self.process.kill()
                self.process.wait()
                print("✅ Server force-stopped")
        except Exception as e:
            print(f"⚠️  Error during cleanup: {e}")
            if self.process:
                try:
                    self.process.kill()
                except:
                    pass

    def logs(self, tail: int = 50):
        """Print server stderr output."""
        if not self.process or not self.process.stderr:
            return

        print(f"\n📋 Server stderr output:")
        try:
            stderr_lines = self.process.stderr.readlines()
            for line in stderr_lines[-tail:]:
                print(line.rstrip())
        except Exception as e:
            print(f"Could not read stderr: {e}")


def determine_server_mode(args) -> str:
    """Determine which server mode to use based on arguments and environment.

    Priority:
    1. Explicit --docker flag → docker
    2. Explicit --local flag → local
    3. Environment variable QUILT_MCP_TEST_MODE → mode
    4. Default → local

    Returns:
        "local" or "docker"
    """
    if args.docker:
        return "docker"
    if args.local:
        return "local"

    # Check environment variable
    env_mode = os.environ.get("QUILT_MCP_TEST_MODE", "local").lower()
    if env_mode in ["docker", "local"]:
        return env_mode

    # Default to local
    return "local"


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
        skip_count = 0
        request_id = 2

        # Store discovered test data from search
        discovered_data = {
            'package_name': None,
            's3_uri': None,
            'bucket': None,
            'prefix': None
        }

        for tool_name, test_config in test_tools.items():
            try:
                start_time = time.time()
                test_args = test_config.get("arguments", {}).copy()

                # Use discovered data to populate test arguments dynamically
                if tool_name == 'search_catalog':
                    # Search runs first to discover data
                    pass
                elif discovered_data['package_name']:
                    # Use discovered data if available
                    if 'package_name' in test_args and test_args.get('package_name') == 'DISCOVER':
                        test_args['package_name'] = discovered_data['package_name']
                    if 's3_uri' in test_args and test_args.get('s3_uri') == 'DISCOVER':
                        test_args['s3_uri'] = discovered_data['s3_uri']
                    if 'bucket' in test_args and test_args.get('bucket') == 'DISCOVER':
                        test_args['bucket'] = discovered_data['bucket']
                    if 'prefix' in test_args and test_args.get('prefix') == 'DISCOVER':
                        test_args['prefix'] = discovered_data['prefix']

                # Skip tests with unresolved CONFIGURE_ placeholders
                if any(isinstance(v, str) and v.startswith('CONFIGURE_') for v in test_args.values()):
                    skip_count += 1
                    print(f"  ⏭️  {tool_name}: Skipped (needs configuration)")
                    continue

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

                # Check for JSON-RPC level errors
                if "error" in result:
                    fail_count += 1
                    print(f"  ❌ {tool_name}: {result['error'].get('message', 'Unknown error')} ({elapsed:.2f}s)")
                    if verbose:
                        print(f"     {result}")
                    continue

                # Extract tool result content
                tool_result_text = None
                tool_result_data = None
                is_error = False

                if "result" in result:
                    tool_result = result["result"]

                    # Check for isError flag
                    if tool_result.get("isError"):
                        is_error = True

                    if "content" in tool_result:
                        content = tool_result["content"]
                        if isinstance(content, list) and len(content) > 0:
                            first_item = content[0]
                            if isinstance(first_item, dict) and "text" in first_item:
                                tool_result_text = first_item["text"]
                                # Try to parse as JSON to check for status/error fields
                                try:
                                    tool_result_data = json.loads(tool_result_text)
                                except:
                                    pass
                        elif isinstance(content, str):
                            tool_result_text = content
                            try:
                                tool_result_data = json.loads(content)
                            except:
                                pass

                # Check tool result for error conditions
                test_failed = False
                test_skipped = False
                failure_reason = None

                if is_error:
                    test_failed = True
                    failure_reason = tool_result_text or "Tool marked as error"
                elif tool_result_data:
                    # Check for authorization failures (should skip, not fail)
                    error_msg = tool_result_data.get("error", "")
                    if "Unauthorized" in error_msg or "Access denied" in error_msg or "Forbidden" in error_msg:
                        test_skipped = True
                        failure_reason = "Authorization required"
                    # Check various error patterns
                    elif tool_result_data.get("status") == "error":
                        test_failed = True
                        failure_reason = tool_result_data.get("error") or tool_result_data.get("message") or "Status: error"
                    elif tool_result_data.get("success") is False:
                        test_failed = True
                        failure_reason = tool_result_data.get("error") or "success: false"
                    elif "error" in tool_result_data and tool_result_data["error"]:
                        test_failed = True
                        failure_reason = tool_result_data["error"]
                    elif "Input validation error" in (tool_result_text or ""):
                        test_failed = True
                        failure_reason = tool_result_text

                # Extract test data from successful search results
                if not test_failed and not test_skipped and tool_name == 'search_catalog' and tool_result_data:
                    if tool_result_data.get("success") and tool_result_data.get("results"):
                        results = tool_result_data["results"]
                        if len(results) > 0:
                            first_result = results[0]
                            # Try to extract package info
                            if first_result.get("package_name"):
                                discovered_data['package_name'] = first_result["package_name"]
                            # Try to extract S3 URI
                            if first_result.get("s3_uri"):
                                discovered_data['s3_uri'] = first_result["s3_uri"]
                                # Parse bucket from S3 URI
                                if discovered_data['s3_uri'].startswith('s3://'):
                                    parts = discovered_data['s3_uri'][5:].split('/', 1)
                                    discovered_data['bucket'] = parts[0]
                                    if len(parts) > 1:
                                        discovered_data['prefix'] = parts[1].rsplit('/', 1)[0]

                if test_skipped:
                    skip_count += 1
                    print(f"  ⏭️  {tool_name}: {failure_reason} ({elapsed:.2f}s)")
                elif test_failed:
                    fail_count += 1
                    # Truncate long error messages
                    if len(failure_reason) > 200:
                        failure_reason = failure_reason[:200] + "..."
                    print(f"  ❌ {tool_name}: {failure_reason} ({elapsed:.2f}s)")
                    if verbose and tool_result_text:
                        if len(tool_result_text) > 500:
                            print(f"     Result: {tool_result_text[:500]}...")
                        else:
                            print(f"     Result: {tool_result_text}")
                else:
                    success_count += 1
                    print(f"  ✅ {tool_name} ({elapsed:.2f}s)")

                    # Show tool result content in verbose mode
                    if verbose and tool_result_text:
                        if len(tool_result_text) > 500:
                            print(f"     Result: {tool_result_text[:500]}...")
                        else:
                            print(f"     Result: {tool_result_text}")

                request_id += 1

            except Exception as e:
                fail_count += 1
                print(f"  ❌ {tool_name}: {e}")
                if verbose:
                    import traceback
                    print(f"     {traceback.format_exc()}")

        print(f"\n📊 Test Results: {success_count} passed, {fail_count} failed, {skip_count} skipped (out of {len(test_tools)} total)")
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

    # Server mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--local",
        action="store_true",
        default=False,  # Don't set default here
        help="Run tests against local server (default)"
    )
    mode_group.add_argument(
        "--docker",
        action="store_true",
        help="Run tests against Docker container"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all tests including non-idempotent (write) operations"
    )

    # Docker-specific options
    parser.add_argument(
        "--image",
        default=DEFAULT_IMAGE,
        help=f"Docker image to use (default: {DEFAULT_IMAGE}, only used with --docker)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port for Docker container (default: {DEFAULT_PORT}, only used with --docker)"
    )

    # Local-specific options
    parser.add_argument(
        "--python",
        default=None,
        help="Python executable path for local mode (default: uv's Python)"
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
