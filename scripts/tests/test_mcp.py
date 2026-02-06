#!/usr/bin/env python3
"""
Comprehensive MCP server testing script.

This script:
1. Generates test configuration using mcp-test-setup.py
2. Launches MCP server (Docker container or local process)
3. Runs tool/resource tests via stdio transport (delegates to mcp-test.py)
4. Cleans up server on exit

By default, only runs idempotent (read-only) tests.

Architecture:
- This script manages server lifecycle (Docker/Local)
- mcp-test.py handles all test execution logic (single source of truth)
- Test logic is NOT duplicated here
"""

import argparse
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional, Union

try:
    import yaml
except ImportError:
    print("❌ PyYAML is required. Install with: uv pip install pyyaml")
    sys.exit(1)

# Script paths
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_DIR = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
MCP_TEST_SETUP_SCRIPT = SCRIPTS_DIR / "mcp-test-setup.py"
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
            # Check if image exists locally
            result = subprocess.run(
                ["docker", "image", "inspect", self.image],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                # Only pull if image looks like a registry image (contains registry domain)
                # Local test images like "quilt-mcp:test" should be built first with make docker-build
                # Registry images have format: registry.domain/path/image:tag
                is_registry_image = (
                    "/" in self.image.split(":")[0] or  # Has registry/path before tag
                    self.image.startswith(("docker.io/", "ghcr.io/", "public.ecr.aws/"))
                )
                if is_registry_image:
                    print(f"📥 Pulling Docker image: {self.image}")
                    subprocess.run(["docker", "pull", self.image], check=True)
                else:
                    print(f"❌ Local image not found: {self.image}")
                    print(f"   For local testing, build the image first with: make docker-build")
                    return False

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
    """Generate test configuration using mcp-test-setup.py."""
    print("🔧 Generating test configuration...")

    try:
        result = subprocess.run(
            [sys.executable, str(MCP_TEST_SETUP_SCRIPT)],
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


def filter_tests_by_idempotence(config_path: Path, idempotent_only: bool) -> tuple[list[str], dict]:
    """Filter test tools based on effect classification.

    Returns:
        Tuple of (filtered_tool_names, stats_dict) where stats_dict contains:
        - total_tools: total number of tools in config
        - total_resources: total number of resources in config
        - selected_tools: number of tools selected
        - effect_counts: dict of effect type -> count of selected tools
    """
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    test_tools = config.get('test_tools', {})
    test_resources = config.get('test_resources', {})
    filtered = []
    effect_counts = {}

    for tool_name, tool_config in test_tools.items():
        effect = tool_config.get('effect', 'none')

        # Count by effect type
        effect_counts[effect] = effect_counts.get(effect, 0) + 1

        # Filter: idempotent_only means only 'none' effect
        if idempotent_only and effect == 'none':
            filtered.append(tool_name)
        elif not idempotent_only:
            filtered.append(tool_name)

    stats = {
        'total_tools': len(test_tools),
        'total_resources': len(test_resources),
        'selected_tools': len(filtered),
        'effect_counts': effect_counts
    }

    return filtered, stats


def run_tests_stdio(
    server: Union[DockerMCPServer, LocalMCPServer],
    config_path: Path,
    tools: Optional[list[str]] = None,
    verbose: bool = False
) -> bool:
    """DEPRECATED: Use run_unified_tests() instead.

    This function is kept for backwards compatibility but should not be used
    for new code. It calls run_test_suite separately for tools only.
    """
    return run_unified_tests(
        server=server,
        config_path=config_path,
        tools=tools,
        resources=None,
        run_tools=True,
        run_resources=False,
        verbose=verbose
    )


def run_unified_tests(
    server: Union[DockerMCPServer, LocalMCPServer],
    config_path: Path,
    tools: Optional[list[str]] = None,
    resources: Optional[list[str]] = None,
    run_tools: bool = True,
    run_resources: bool = True,
    verbose: bool = False,
    selection_stats: Optional[dict] = None
) -> bool:
    """Run BOTH tool and resource tests with ONE call to mcp-test.py.

    This function calls MCPTester.run_test_suite() ONCE with both run_tools and
    run_resources flags, which prints ONE unified summary covering both test types.

    Args:
        server: Running Docker/Local MCP server instance
        config_path: Path to test configuration YAML
        tools: Optional list of tool names to test (None = all tools in config)
        resources: Optional list of resource URIs to test (None = all resources)
        run_tools: Whether to run tool tests
        run_resources: Whether to run resource tests
        verbose: Enable verbose test output
        selection_stats: Optional test selection statistics for summary

    Returns:
        True if all tests passed, False otherwise
    """
    print(f"\n🧪 Running MCP tests (stdio via mcp-test.py)...")
    print(f"   Config: {config_path}")
    if run_tools and tools:
        print(f"   Testing {len(tools)} specific tools")
    if run_resources and resources:
        print(f"   Testing {len(resources)} specific resources")

    if not server.process or server.process.poll() is not None:
        print("❌ Server process not running")
        return False

    try:
        # Import mcp-test as a module to use its functionality directly
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            from mcp_test import MCPTester, load_test_config
        except ImportError as e:
            # Handle module name with dash by trying alternative import
            import importlib.util
            spec = importlib.util.spec_from_file_location("mcp_test", MCP_TEST_SCRIPT)
            if spec and spec.loader:
                mcp_test = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mcp_test)
                MCPTester = mcp_test.MCPTester
                load_test_config = mcp_test.load_test_config
            else:
                print(f"❌ Failed to import mcp-test.py: {e}")
                return False

        # Load test configuration
        config = load_test_config(config_path)

        # Filter tools if specific ones requested
        specific_tool = None
        if tools:
            if len(tools) == 1:
                specific_tool = tools[0]
            else:
                test_tools = config.get("test_tools", {})
                config["test_tools"] = {k: v for k, v in test_tools.items() if k in tools}

        # Filter resources if specific ones requested
        specific_resource = None
        if resources:
            if len(resources) == 1:
                specific_resource = resources[0]
            else:
                test_resources = config.get("test_resources", {})
                config["test_resources"] = {k: v for k, v in test_resources.items() if k in resources}

        # ONE call runs BOTH tools and resources, prints ONE unified summary
        success = MCPTester.run_test_suite(
            process=server.process,
            transport="stdio",
            verbose=verbose,
            config=config,
            run_tools=run_tools,
            run_resources=run_resources,
            specific_tool=specific_tool,
            specific_resource=specific_resource,
            selection_stats=selection_stats
        )

        return success

    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False
    finally:
        # Clean up sys.path
        if str(SCRIPTS_DIR) in sys.path:
            sys.path.remove(str(SCRIPTS_DIR))


def run_resource_tests_stdio(
    server: Union[DockerMCPServer, LocalMCPServer],
    config_path: Path,
    resources: Optional[list[str]] = None,
    verbose: bool = False,
    skip_init: bool = False
) -> bool:
    """DEPRECATED: Use run_unified_tests() instead.

    This function is kept for backwards compatibility but should not be used
    for new code. It calls run_test_suite separately for resources only.
    """
    return run_unified_tests(
        server=server,
        config_path=config_path,
        tools=None,
        resources=resources,
        run_tools=False,
        run_resources=True,
        verbose=verbose
    )


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
    parser.add_argument(
        "--resources-only",
        action="store_true",
        help="Run only resource tests (skip tool tests)"
    )
    parser.add_argument(
        "--skip-resources",
        action="store_true",
        help="Skip resource tests (run only tool tests)"
    )
    parser.add_argument(
        "--resource",
        metavar="URI",
        help="Test specific resource by URI"
    )

    args = parser.parse_args()

    # Determine mode
    mode = determine_server_mode(args)

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
        tools, stats = filter_tests_by_idempotence(TEST_CONFIG_PATH, idempotent_only=False)
    else:
        mode_desc = "local" if mode == "local" else "Docker"
        print(f"🧪 Running MCP server integration tests ({mode_desc} mode, idempotent only)...")
        tools, stats = filter_tests_by_idempotence(TEST_CONFIG_PATH, idempotent_only=True)

    # Display detailed selection statistics
    print(f"📋 Selected {stats['selected_tools']}/{stats['total_tools']} tools for testing")
    if args.all:
        # Show breakdown by effect type when running all tests
        effect_summary = ", ".join(f"{effect}: {count}" for effect, count in sorted(stats['effect_counts'].items()))
        print(f"   Effect breakdown: {effect_summary}")
    else:
        # Show what was filtered out when running idempotent only
        filtered_out = stats['total_tools'] - stats['selected_tools']
        if filtered_out > 0:
            non_none_effects = {k: v for k, v in stats['effect_counts'].items() if k != 'none'}
            skipped_summary = ", ".join(f"{effect}: {count}" for effect, count in sorted(non_none_effects.items()))
            print(f"   Skipped {filtered_out} non-idempotent tools ({skipped_summary})")
    print(f"   Resources: {stats['total_resources']} configured for testing")

    # Start server based on mode
    server = None
    if mode == "local":
        server = LocalMCPServer(python_path=args.python)
        if not server.start():
            sys.exit(1)
    else:  # docker
        server = DockerMCPServer(image=args.image, port=args.port)
        if not server.start():
            sys.exit(1)

    try:
        # Run BOTH tool and resource tests with ONE call to run_test_suite
        if not server:
            print("❌ No server available for testing")
            sys.exit(1)

        # Single call runs BOTH tools and resources, prints ONE unified summary
        success = run_unified_tests(
            server=server,
            config_path=TEST_CONFIG_PATH,
            tools=tools if not args.resources_only else None,
            resources=[args.resource] if args.resource else None,
            run_tools=not args.resources_only,
            run_resources=not args.skip_resources,
            verbose=args.verbose,
            selection_stats=stats  # Pass selection stats for intelligent summary
        )

        # Show logs if requested
        if args.logs:
            server.logs()

        sys.exit(0 if success else 1)

    finally:
        # Clean up server
        if server and not args.keep_container:
            server.stop()
        elif server:
            if mode == "local":
                print(f"\n💡 Server kept running: {server.server_id}")
                print(f"   PID: {server.process.pid}")
                print(f"   Note: Server is using stdio, cannot connect externally")
            else:
                print(f"\n💡 Container kept running: {server.container_name}")
                print(f"   Note: Container is using stdio, cannot connect externally")


if __name__ == "__main__":
    main()
