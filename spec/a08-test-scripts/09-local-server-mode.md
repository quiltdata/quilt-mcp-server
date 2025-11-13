# Local Server Mode for test_mcp.py

**Date:** 2025-11-12
**Status:** 📝 Proposed
**Related:** [08-test-mcp-bugs.md](./08-test-mcp-bugs.md), [07-unified-test-client.md](./07-unified-test-client.md)

## Overview

The current `test_mcp.py` implementation exclusively uses Docker containers to run the MCP server for testing. While Docker provides isolation and reproducibility, it adds overhead (image pulls, container lifecycle management, cleanup timeouts) and makes debugging more difficult.

This proposal adds **local server mode** as the **default** testing approach, while keeping Docker as an optional fallback for integration testing scenarios.

## Current Implementation

### Docker-Only Mode

**Location:** [scripts/tests/test_mcp.py:46-133](../../scripts/tests/test_mcp.py#L46-L133)

```python
class DockerMCPServer:
    """Manages Docker container lifecycle for MCP server testing (stdio transport)."""

    def start(self) -> bool:
        """Start MCP server in Docker container with stdio transport."""
        # Pull image if needed
        # Mount AWS credentials
        # Start container with -i flag for stdio
        # Wait 2 seconds for startup
        self.process = subprocess.Popen(docker_cmd, stdin=PIPE, stdout=PIPE, ...)

    def stop(self):
        """Stop and remove Docker container."""
        # Terminate process
        # Wait with 10s timeout → force kill if needed
        # Remove container with docker rm -f
```

## Proposed Implementation

### Architecture Overview

```graph
┌─────────────────────────────────────────────────────────┐
│                    test_mcp.py                          │
│                                                         │
│  ┌──────────────┐      ┌─────────────┐                │
│  │ Detect Mode  │──┬──>│ Local       │ (default)      │
│  │  --local     │  │   │ Start uv    │                │
│  │  --docker    │  │   └─────────────┘                │
│  │  (auto)      │  │                                   │
│  └──────────────┘  │   ┌─────────────┐                │
│                    └──>│ Docker      │ (optional)     │
│                        │ Start ctnr  │                │
│                        └─────────────┘                │
│                                                         │
│  ┌────────────────────────────────────────────┐       │
│  │   Unified stdio Testing Interface          │       │
│  │   (works with both local & Docker)         │       │
│  └────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### New LocalMCPServer Class

**Location:** [scripts/tests/test_mcp.py](../../scripts/tests/test_mcp.py) (new class)

```python
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
```

### Mode Detection Logic

**Location:** [scripts/tests/test_mcp.py:main()](../../scripts/tests/test_mcp.py) (updated)

```python
def determine_server_mode(args) -> Literal["local", "docker"]:
    """Determine which server mode to use based on arguments and environment.

    Priority:
    1. Explicit --docker flag → docker
    2. Explicit --local flag → local
    3. Environment variable QUILT_MCP_TEST_MODE → mode
    4. Default → local
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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(...)

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

    # ... other args ...

    args = parser.parse_args()

    # Determine mode
    mode = determine_server_mode(args)

    # Generate test configuration
    if not args.no_generate:
        if not generate_test_config():
            sys.exit(1)

    # Filter tests
    if args.all:
        print("🔓 Running ALL tests (including write operations)")
        tools = filter_tests_by_idempotence(TEST_CONFIG_PATH, idempotent_only=False)
    else:
        print(f"🧪 Running MCP server integration tests ({'local' if mode == 'local' else 'Docker'} mode, idempotent only)...")
        tools = filter_tests_by_idempotence(TEST_CONFIG_PATH, idempotent_only=True)

    print(f"📋 Selected {len(tools)} tools for testing")

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
        # Run tests using stdio transport (works with both modes)
        success = run_tests_stdio(server, TEST_CONFIG_PATH, tools, args.verbose)

        # Show logs if requested
        if args.logs and server:
            server.logs()

        sys.exit(0 if success else 1)

    finally:
        # Clean up server
        if server and not args.keep_container:  # keep_container works for both modes
            server.stop()
        elif server:
            print(f"\n💡 Server kept running: {server.server_id}")
            if mode == "local":
                print(f"   PID: {server.process.pid}")
                print(f"   Note: Server is using stdio, cannot connect externally")
```

## Updated CLI Interface

### Local Mode (Default)

```bash
# Run with local server (default)
python scripts/tests/test_mcp.py

# Explicit local mode
python scripts/tests/test_mcp.py --local

# Keep server running after tests (for debugging)
python scripts/tests/test_mcp.py --local --keep-container

# Show server logs
python scripts/tests/test_mcp.py --local --logs

# Verbose output
python scripts/tests/test_mcp.py --local -v
```

### Docker Mode (Explicit)

```bash
# Use Docker mode
python scripts/tests/test_mcp.py --docker

# Custom Docker image
python scripts/tests/test_mcp.py --docker --image quiltdata/quilt-mcp-server:dev

# Docker with verbose output
python scripts/tests/test_mcp.py --docker -v --logs
```

### Environment Variable Override

```bash
# Set default mode via environment
export QUILT_MCP_TEST_MODE=docker
python scripts/tests/test_mcp.py  # Uses Docker

export QUILT_MCP_TEST_MODE=local
python scripts/tests/test_mcp.py  # Uses local (same as default)
```

## Makefile Integration

**Location:** [Makefile](../../Makefile) (update)

```makefile
# Default - uses local server
test-mcp:
 uv run python scripts/tests/test_mcp.py

# Explicit modes
test-mcp-local:
 uv run python scripts/tests/test_mcp.py --local -v

test-mcp-docker:
 uv run python scripts/tests/test_mcp.py --docker -v

## Testing the Implementation

### Unit Tests for Server Classes

```python
# tests/test_server_modes.py

def test_local_server_starts_and_stops():
    """Test that local server can start and stop cleanly."""
    server = LocalMCPServer()
    assert server.start()
    assert server.process is not None
    assert server.process.poll() is None  # Still running

    server.stop()
    time.sleep(0.5)
    assert server.process.poll() is not None  # Exited

def test_docker_server_starts_and_stops():
    """Test that Docker server can start and stop cleanly."""
    server = DockerMCPServer()
    assert server.start()
    assert server.process is not None

    server.stop()
    # Verify container removed
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name={server.container_name}"],
        capture_output=True, text=True
    )
    assert server.container_name not in result.stdout

def test_mode_detection_priority():
    """Test that mode detection follows priority rules."""
    # Explicit --docker wins
    args = argparse.Namespace(docker=True, local=False)
    assert determine_server_mode(args) == "docker"

    # Explicit --local wins
    args = argparse.Namespace(docker=False, local=True)
    assert determine_server_mode(args) == "local"

    # Default is local
    args = argparse.Namespace(docker=False, local=False)
    assert determine_server_mode(args) == "local"
```

### Integration Tests

```bash
# Test that both modes pass the same test suite
make test-scripts-local   # Should pass
make test-scripts-docker  # Should pass

# Verify idempotent tests work in both modes
python scripts/tests/test_mcp.py --local
python scripts/tests/test_mcp.py --docker

# Compare results (should be identical)
```

## Migration Plan

### Phase 1: Add Local Mode (This Spec)

1. Implement `LocalMCPServer` class
2. Add mode detection logic
3. Update CLI arguments
4. Update Makefile targets
5. Keep Docker as available option

**Timeline:** 1 day

### Phase 2: Update Documentation

1. Update README with new default behavior
2. Add troubleshooting guide for local mode
3. Document when to use Docker mode
4. Add CI/CD examples

**Timeline:** 1 day

### Phase 3: Validate in CI

1. Run both modes in CI
2. Compare test results
3. Ensure Docker mode still works for releases
4. Document any differences found

**Timeline:** Ongoing

## Compatibility

### Backwards Compatibility

✅ **Fully backwards compatible:**

- `--docker` flag preserves old behavior
- `--no-docker` removed (replaced by `--local` which is now default)
- All existing Docker arguments still work
- Environment variables still respected
- Same test framework (stdio transport)

### Breaking Changes

⚠️ **Minor breaking changes:**

- Default mode changes from Docker → Local
  - **Impact:** Low - most developers prefer local
  - **Migration:** Use `--docker` or `QUILT_MCP_TEST_MODE=docker`

- `--no-docker` flag removed
  - **Impact:** Low - flag wasn't useful (had no alternative)
  - **Migration:** Use `--local` instead (now default)

## Performance Comparison

### Expected Timings

| Operation | Docker Mode | Local Mode | Improvement |
|-----------|-------------|------------|-------------|
| Image pull (cold) | 30-120s | 0s | ∞ |
| Image check (warm) | 1-2s | 0s | 100% |
| Server startup | 2s | 0.5s | 75% |
| Server shutdown | 10s (timeout) | 0-3s | 70-100% |
| **Total overhead** | **13-134s** | **0.5-3.5s** | **~95%** |
| Test execution | ~30s | ~30s | 0% |
| **Total test time** | **43-164s** | **30-34s** | **30-80%** |

### Real-World Scenarios

**Cold start (first run):**

- Docker: ~120s (image pull) + 13s (overhead) + 30s (tests) = **163s**
- Local: 0.5s (overhead) + 30s (tests) = **30.5s** ✅ **5.3x faster**

**Warm start (typical):**

- Docker: 13s (overhead) + 30s (tests) = **43s**
- Local: 0.5s (overhead) + 30s (tests) = **30.5s** ✅ **1.4x faster**

**Iteration (code change → test):**

- Docker: Rebuild image (60s) + 13s + 30s = **103s**
- Local: 0.5s + 30s = **30.5s** ✅ **3.4x faster**


## Success Criteria

✅ **Implementation is successful if:**

1. Local mode works for all idempotent tests
2. Docker mode still passes (backwards compatibility)
3. Test execution time reduced by ≥30% (warm start)
4. Documentation updated with new default
5. CI passes with both modes
6. Developer feedback is positive

## References

- [Current test_mcp.py](../../scripts/tests/test_mcp.py)
- [Main server entry point](../../src/main.py)
- [FastMCP run_server](../../src/quilt_mcp/utils.py#L529)
- [pyproject.toml scripts](../../pyproject.toml#L54)
- [Bug #9: Container Cleanup Timeout](./08-test-mcp-bugs.md#bug-9-container-cleanup-timeout-warning)
