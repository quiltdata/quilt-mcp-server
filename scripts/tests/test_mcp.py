#!/usr/bin/env python3
"""
Comprehensive MCP server testing script.

This script:
1. Generates test configuration using mcp-list.py
2. Launches MCP server in Docker container
3. Runs mcp-test.py with configurable test selection
4. Cleans up Docker container on exit

By default, only runs idempotent (read-only) tests.
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
    """Manages Docker container lifecycle for MCP server testing."""

    def __init__(self, image: str = DEFAULT_IMAGE, port: int = DEFAULT_PORT):
        self.image = image
        self.port = port
        self.container_name = f"mcp-test-{uuid.uuid4().hex[:8]}"
        self.container_id: Optional[str] = None

    def start(self) -> bool:
        """Start MCP server in Docker container."""
        print(f"🚀 Starting MCP server in Docker...")
        print(f"   Image: {self.image}")
        print(f"   Port: {self.port}")
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
            # Best practice: Mount ~/.aws directory as read-only volume
            # This supports AWS profiles, SSO, MFA, and credential rotation
            aws_creds_path = Path.home() / ".aws"
            docker_cmd = [
                "docker", "run", "-d",
                "--name", self.container_name,
                "-p", f"{self.port}:8000",
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
            ])

            docker_cmd.extend([
                "-e", "QUILT_MCP_DEBUG=true",
                self.image
            ])

            # Start container
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                check=True
            )

            self.container_id = result.stdout.strip()
            print(f"✅ Container started: {self.container_id[:12]}")

            # Wait for server to be ready
            print("⏳ Waiting for server to be ready...")
            return self._wait_for_ready()

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to start container: {e}")
            print(f"   stdout: {e.stdout}")
            print(f"   stderr: {e.stderr}")
            return False

    def _wait_for_ready(self, timeout: int = 30) -> bool:
        """Wait for MCP server to respond to health checks."""
        import requests

        endpoint = f"http://localhost:{self.port}/health"
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(endpoint, timeout=2)
                if response.status_code == 200:
                    print(f"✅ Server ready at http://localhost:{self.port}")
                    return True
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                pass

            time.sleep(1)
            print(".", end="", flush=True)

        print("\n❌ Server failed to become ready within timeout")
        return False

    def stop(self):
        """Stop and remove Docker container."""
        if not self.container_id:
            return

        print(f"\n🛑 Stopping container {self.container_name}...")
        try:
            subprocess.run(
                ["docker", "stop", self.container_name],
                capture_output=True,
                timeout=10
            )
            subprocess.run(
                ["docker", "rm", self.container_name],
                capture_output=True,
                timeout=10
            )
            print("✅ Container cleaned up")
        except subprocess.TimeoutExpired:
            print("⚠️  Timeout stopping container, force removing...")
            subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True)

    def logs(self, tail: int = 50):
        """Print container logs."""
        if not self.container_id:
            return

        print(f"\n📋 Container logs (last {tail} lines):")
        subprocess.run(["docker", "logs", "--tail", str(tail), self.container_name])


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


def run_tests(
    endpoint: str,
    config_path: Path,
    tools: Optional[list[str]] = None,
    verbose: bool = False
) -> bool:
    """Run mcp-test.py with specified configuration."""
    print(f"\n🧪 Running MCP tests...")
    print(f"   Endpoint: {endpoint}")
    print(f"   Config: {config_path}")

    if tools:
        print(f"   Testing {len(tools)} tools")
        if verbose:
            print(f"   Tools: {', '.join(tools[:5])}" + ("..." if len(tools) > 5 else ""))

    cmd = [
        sys.executable,
        str(MCP_TEST_SCRIPT),
        endpoint,
        "--config", str(config_path),
        "-t"  # Run tools test
    ]

    if verbose:
        cmd.append("-v")

    # Run each tool individually for better progress tracking
    if tools:
        success_count = 0
        fail_count = 0

        for tool in tools:
            tool_cmd = cmd + ["-T", tool]
            try:
                result = subprocess.run(
                    tool_cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    success_count += 1
                    print(f"  ✅ {tool}")
                else:
                    fail_count += 1
                    print(f"  ❌ {tool}")
                    if verbose:
                        print(f"     {result.stderr}")
            except subprocess.TimeoutExpired:
                fail_count += 1
                print(f"  ⏱️  {tool} (timeout)")

        print(f"\n📊 Test Results: {success_count}/{len(tools)} passed")
        return fail_count == 0
    else:
        # Run all tests at once
        try:
            result = subprocess.run(cmd, check=True)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            print(f"❌ Tests failed: {e}")
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
  python scripts/tests/test_mcp.py --no-docker --endpoint http://localhost:8000/mcp/
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
        help="MCP endpoint URL (default: http://localhost:{port}/mcp/)"
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
        print("🔒 Running IDEMPOTENT tests only (read-only operations)")
        tools = filter_tests_by_idempotence(TEST_CONFIG_PATH, idempotent_only=True)

    print(f"📋 Selected {len(tools)} tools for testing")

    # Start Docker container if needed
    server = None
    if not args.no_docker:
        server = DockerMCPServer(image=args.image, port=args.port)
        if not server.start():
            sys.exit(1)

    # Determine endpoint
    endpoint = args.endpoint or f"http://localhost:{args.port}/mcp/"

    try:
        # Run tests
        success = run_tests(endpoint, TEST_CONFIG_PATH, tools, args.verbose)

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
            print(f"   Stop with: docker stop {server.container_name}")


if __name__ == "__main__":
    main()
