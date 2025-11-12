# Unified MCP Test Client: Consolidating test_mcp.py and mcp-test.py

**Date:** 2025-11-12
**Status:** 📋 PROPOSAL
**Related:** [06-resource-testing-extension.md](./06-resource-testing-extension.md), [06a-corrected-architecture.md](./06a-corrected-architecture.md)

## Executive Summary

This proposal consolidates `test_mcp.py` and `mcp-test.py` into a single unified test client that supports both stdio and HTTP transports. This eliminates significant code duplication (~300+ lines), provides a consistent testing interface, and simplifies resource testing implementation by requiring changes in only one place.

## Problem Statement

### Current Duplication Analysis

**Duplicated Functionality (744 total lines across 2 files):**

1. **Test Configuration Loading** (~15 lines each)
   - Both read `mcp-test.yaml`
   - Both parse YAML structure
   - Both filter test_tools section

2. **MCP Protocol Initialization** (~40 lines each)
   - Both send `initialize` request
   - Both handle initialize response
   - Both need `notifications/initialized` (though only stdio has it)

3. **Tool Testing Logic** (~130 lines each)
   - Both iterate through test_tools
   - Both call tools with arguments
   - Both validate responses
   - Both report success/failure
   - Both provide verbose output

4. **Test Result Reporting** (~20 lines each)
   - Both count successes/failures
   - Both print formatted results
   - Both return pass/fail boolean

5. **CLI Argument Parsing** (~80 lines each)
   - Both have verbose flag
   - Both have config path option
   - Both have test filtering options
   - Different but overlapping arguments

**Unique Functionality:**

- **test_mcp.py only:** Docker container management (~115 lines)
- **mcp-test.py only:** HTTP request handling (~60 lines)
- **test_mcp.py only:** Stdio I/O handling (~50 lines)

### Maintenance Burden

**Current State:**
- Bug fixes must be applied twice (e.g., `notifications/initialized` fix)
- Feature additions must be implemented twice (e.g., resource testing)
- Test output formats diverge over time
- Configuration format changes require two updates

**Example:** Adding resource testing requires:
- ~200 lines in `test_mcp.py` (stdio implementation)
- ~200 lines in `mcp-test.py` (HTTP implementation)
- Total: ~400 lines of largely duplicated code

## Proposal: Unified Test Client

### Design Principles

1. **Transport Abstraction**
   - Common interface for stdio and HTTP
   - Transport-specific implementation hidden
   - Same test logic works for both

2. **Single Source of Truth**
   - One test execution engine
   - One configuration parser
   - One result reporter

3. **Backward Compatibility**
   - Keep same CLI for CI/CD (`make test-scripts` still works)
   - Maintain same output format
   - Preserve existing behavior

4. **Clear Separation**
   - Docker management: separate, optional
   - Transport layer: pluggable
   - Test logic: shared

### Unified Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Unified MCP Test Client                        │
│                     (mcp-test.py ENHANCED)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
          ┌─────▼─────┐          ┌─────▼─────┐
          │  Transport │          │  Transport │
          │   Layer    │          │   Layer   │
          │  (Stdio)   │          │  (HTTP)   │
          └─────┬─────┘          └─────┬─────┘
                │                       │
                │                       │
          ┌─────▼──────────────────────▼─────┐
          │     Shared Test Engine            │
          │  - Configuration loading          │
          │  - MCP protocol initialization    │
          │  - Tool testing                   │
          │  - Resource testing (NEW)         │
          │  - Result reporting               │
          └───────────────────────────────────┘
                            │
                  ┌─────────┴─────────┐
                  │                   │
            ┌─────▼─────┐      ┌─────▼─────┐
            │  Docker   │      │   Direct  │
            │  Manager  │      │  Connect  │
            │ (Optional)│      │ (Default) │
            └───────────┘      └───────────┘
```

### Transport Abstraction Layer

**Common Interface:**
```python
class MCPTransport(ABC):
    """Abstract base class for MCP transport implementations."""

    @abstractmethod
    def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC request and return response."""
        pass

    @abstractmethod
    def send_notification(self, notification: Dict[str, Any]) -> None:
        """Send JSON-RPC notification (no response expected)."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close transport connection."""
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        """Check if transport is still active."""
        pass
```

**Stdio Implementation:**
```python
class StdioTransport(MCPTransport):
    """Stdio transport for MCP communication."""

    def __init__(self, process: subprocess.Popen):
        self.process = process

    def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request via stdin, read response from stdout."""
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        response = self.process.stdout.readline()
        return json.loads(response)

    def send_notification(self, notification: Dict[str, Any]) -> None:
        """Send notification via stdin (no response)."""
        self.process.stdin.write(json.dumps(notification) + "\n")
        self.process.stdin.flush()

    def close(self) -> None:
        """Terminate process."""
        self.process.terminate()
        self.process.wait(timeout=10)

    def is_alive(self) -> bool:
        """Check if process is running."""
        return self.process.poll() is None
```

**HTTP Implementation:**
```python
class HTTPTransport(MCPTransport):
    """HTTP transport for MCP communication."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream'
        })

    def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send request via HTTP POST."""
        response = self.session.post(
            self.endpoint,
            json=request,
            timeout=10
        )
        response.raise_for_status()

        # Handle SSE format if needed
        content_type = response.headers.get('content-type', '')
        if 'text/event-stream' in content_type:
            return self._parse_sse(response.text)
        else:
            return response.json()

    def send_notification(self, notification: Dict[str, Any]) -> None:
        """Send notification via HTTP POST (no response expected)."""
        # For HTTP, notifications are sent same as requests
        # Server may not respond, so we ignore response
        try:
            self.session.post(self.endpoint, json=notification, timeout=1)
        except:
            pass  # Notifications don't require response

    def close(self) -> None:
        """Close HTTP session."""
        self.session.close()

    def is_alive(self) -> bool:
        """Check if endpoint is reachable."""
        try:
            response = self.session.get(self.endpoint, timeout=1)
            return True
        except:
            return False

    def _parse_sse(self, text: str) -> Dict[str, Any]:
        """Parse Server-Sent Events format."""
        lines = text.strip().split('\n')
        for line in lines:
            if line.startswith('data: '):
                return json.loads(line[6:])
        raise Exception("No data field in SSE response")
```

### Unified Test Client

**Core Class:**
```python
class MCPTestClient:
    """Unified MCP test client supporting multiple transports."""

    def __init__(
        self,
        transport: MCPTransport,
        config_path: Path,
        verbose: bool = False
    ):
        self.transport = transport
        self.config_path = config_path
        self.verbose = verbose
        self.request_id = 1
        self.initialized = False

    def initialize(self) -> bool:
        """Initialize MCP session (works for any transport)."""
        self._log("Initializing MCP session...")

        init_request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-test", "version": "1.0"}
            }
        }
        self.request_id += 1

        try:
            result = self.transport.send_request(init_request)

            if "error" in result:
                self._log(f"Initialize failed: {result['error']}", "ERROR")
                return False

            # Send notifications/initialized (required by protocol)
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            self.transport.send_notification(initialized_notification)
            time.sleep(0.5)  # Give server time to process

            self.initialized = True
            self._log("✅ Session initialized", "INFO")
            return True

        except Exception as e:
            self._log(f"Initialize error: {e}", "ERROR")
            return False

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        if not self.initialized:
            raise Exception("Not initialized")

        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/list",
            "params": {}
        }
        self.request_id += 1

        result = self.transport.send_request(request)
        return result.get("result", {}).get("tools", [])

    def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Call a tool."""
        if not self.initialized:
            raise Exception("Not initialized")

        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/call",
            "params": {"name": name}
        }
        if arguments:
            request["params"]["arguments"] = arguments

        self.request_id += 1
        return self.transport.send_request(request)

    def list_resources(self) -> List[Dict[str, Any]]:
        """List available resources."""
        if not self.initialized:
            raise Exception("Not initialized")

        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "resources/list",
            "params": {}
        }
        self.request_id += 1

        result = self.transport.send_request(request)
        return result.get("result", {}).get("resources", [])

    def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource."""
        if not self.initialized:
            raise Exception("Not initialized")

        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "resources/read",
            "params": {"uri": uri}
        }
        self.request_id += 1

        return self.transport.send_request(request)

    def run_tool_tests(
        self,
        specific_tools: Optional[List[str]] = None
    ) -> bool:
        """Run tool tests (works for any transport)."""
        config = self._load_config()
        test_tools = config.get("test_tools", {})

        if specific_tools:
            test_tools = {
                k: v for k, v in test_tools.items()
                if k in specific_tools
            }

        success_count = 0
        fail_count = 0

        print(f"\n🧪 Running tool tests ({len(test_tools)} tools)...")

        for tool_name, test_config in test_tools.items():
            try:
                start_time = time.time()
                test_args = test_config.get("arguments", {})

                result = self.call_tool(tool_name, test_args)
                elapsed = time.time() - start_time

                if "error" in result:
                    fail_count += 1
                    error_msg = result["error"].get("message", "Unknown")
                    print(f"  ❌ {tool_name}: {error_msg} ({elapsed:.2f}s)")
                else:
                    success_count += 1
                    print(f"  ✅ {tool_name} ({elapsed:.2f}s)")

            except Exception as e:
                fail_count += 1
                print(f"  ❌ {tool_name}: {e}")

        print(f"\n📊 Tool Test Results: {success_count}/{len(test_tools)} passed")
        return fail_count == 0

    def run_resource_tests(
        self,
        specific_resources: Optional[List[str]] = None
    ) -> bool:
        """Run resource tests (works for any transport)."""
        config = self._load_config()
        test_resources = config.get("test_resources", {})

        if specific_resources:
            test_resources = {
                k: v for k, v in test_resources.items()
                if k in specific_resources
            }

        if not test_resources:
            print("⚠️  No resources configured for testing")
            return True

        # List available resources
        available = self.list_resources()
        available_uris = {r["uri"] for r in available}

        success_count = 0
        fail_count = 0

        print(f"\n🗂️  Running resource tests ({len(test_resources)} resources)...")

        for uri_pattern, test_config in test_resources.items():
            try:
                start_time = time.time()

                # Substitute URI variables
                uri = self._substitute_uri_variables(uri_pattern, test_config)

                if uri not in available_uris:
                    fail_count += 1
                    print(f"  ❌ {uri}: Not found on server")
                    continue

                result = self.read_resource(uri)
                elapsed = time.time() - start_time

                if "error" in result:
                    fail_count += 1
                    error_msg = result["error"].get("message", "Unknown")
                    print(f"  ❌ {uri}: {error_msg} ({elapsed:.2f}s)")
                else:
                    # Validate content
                    if self._validate_resource_content(result, test_config):
                        success_count += 1
                        print(f"  ✅ {uri} ({elapsed:.2f}s)")
                    else:
                        fail_count += 1
                        print(f"  ❌ {uri}: Content validation failed ({elapsed:.2f}s)")

            except Exception as e:
                fail_count += 1
                print(f"  ❌ {uri_pattern}: {e}")

        print(f"\n📊 Resource Test Results: {success_count}/{len(test_resources)} passed")
        return fail_count == 0

    def _load_config(self) -> Dict[str, Any]:
        """Load test configuration."""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _substitute_uri_variables(
        self,
        uri_pattern: str,
        test_config: Dict[str, Any]
    ) -> str:
        """Substitute variables in URI pattern."""
        uri = uri_pattern
        uri_vars = test_config.get("uri_variables", {})
        for var_name, var_value in uri_vars.items():
            uri = uri.replace(f"{{{var_name}}}", var_value)
        return uri

    def _validate_resource_content(
        self,
        result: Dict[str, Any],
        test_config: Dict[str, Any]
    ) -> bool:
        """Validate resource content against test config."""
        # Implementation similar to spec in 06-resource-testing-extension.md
        # Check MIME type, content type, schema, etc.
        return True  # Simplified for this spec

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log message."""
        if level == "DEBUG" and not self.verbose:
            return
        print(f"{message}")

    def close(self) -> None:
        """Close transport connection."""
        self.transport.close()
```

### Docker Manager (Separate, Optional)

```python
class DockerMCPServer:
    """Manages Docker container for stdio transport (unchanged from test_mcp.py)."""
    # Keep existing implementation (~115 lines)
    # This is the only Docker-specific code
    pass
```

### Unified CLI

```python
def main():
    """Unified CLI supporting both transports."""
    parser = argparse.ArgumentParser(
        description="Unified MCP testing client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Stdio transport with Docker (primary CI/CD usage)
  python mcp-test.py --transport stdio --docker
  python mcp-test.py --transport stdio --docker --all

  # Stdio transport to existing process (advanced)
  python mcp-test.py --transport stdio --stdio-cmd "quilt-mcp --skip-banner"

  # HTTP transport to external server
  python mcp-test.py --transport http --endpoint http://localhost:8765/mcp
  python mcp-test.py http://localhost:8765/mcp  # Shortcut

  # Test specific components
  python mcp-test.py --docker --tools-only
  python mcp-test.py --docker --resources-only
  python mcp-test.py --docker --test-tool catalog_configure
  python mcp-test.py --docker --test-resource "quilt://status"
        """
    )

    # Transport selection
    parser.add_argument(
        "endpoint",
        nargs="?",
        help="MCP endpoint URL (shortcut for --transport http --endpoint URL)"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=None,
        help="Transport type (auto-detected if endpoint provided)"
    )

    # Stdio transport options
    stdio_group = parser.add_argument_group("stdio transport options")
    stdio_group.add_argument(
        "--docker",
        action="store_true",
        help="Launch MCP server in Docker container (stdio only)"
    )
    stdio_group.add_argument(
        "--image",
        default="quiltdata/quilt-mcp-server:latest",
        help="Docker image to use"
    )
    stdio_group.add_argument(
        "--stdio-cmd",
        help="Command to launch stdio MCP server (alternative to --docker)"
    )

    # HTTP transport options
    http_group = parser.add_argument_group("http transport options")
    http_group.add_argument(
        "--endpoint",
        help="MCP endpoint URL for HTTP transport"
    )

    # Test selection
    test_group = parser.add_argument_group("test selection")
    test_group.add_argument(
        "--all",
        action="store_true",
        help="Run all tests including non-idempotent (write) operations"
    )
    test_group.add_argument(
        "--tools-only",
        action="store_true",
        help="Run only tool tests"
    )
    test_group.add_argument(
        "--resources-only",
        action="store_true",
        help="Run only resource tests"
    )
    test_group.add_argument(
        "--test-tool",
        metavar="TOOL_NAME",
        help="Test specific tool"
    )
    test_group.add_argument(
        "--test-resource",
        metavar="RESOURCE_URI",
        help="Test specific resource"
    )
    test_group.add_argument(
        "--list-tools",
        action="store_true",
        help="List available tools and exit"
    )
    test_group.add_argument(
        "--list-resources",
        action="store_true",
        help="List available resources and exit"
    )

    # Configuration
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "tests" / "mcp-test.yaml",
        help="Path to test configuration file"
    )
    parser.add_argument(
        "--no-generate",
        action="store_true",
        help="Skip test config generation"
    )

    # Output options
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--logs",
        action="store_true",
        help="Show container logs (Docker only)"
    )
    parser.add_argument(
        "--keep-container",
        action="store_true",
        help="Keep Docker container running after tests"
    )

    args = parser.parse_args()

    # Determine transport
    if args.endpoint and not args.transport:
        transport_type = "http"
        endpoint = args.endpoint
    elif args.transport == "http":
        if not args.endpoint:
            parser.error("--endpoint required for http transport")
        transport_type = "http"
        endpoint = args.endpoint
    else:
        transport_type = "stdio"
        endpoint = None

    # Generate config if needed
    if not args.no_generate:
        generate_test_config()

    # Create transport
    transport = None
    docker_server = None

    try:
        if transport_type == "stdio":
            if args.docker:
                # Launch Docker container
                docker_server = DockerMCPServer(image=args.image)
                if not docker_server.start():
                    sys.exit(1)
                transport = StdioTransport(docker_server.process)
            elif args.stdio_cmd:
                # Launch custom command
                process = subprocess.Popen(
                    args.stdio_cmd.split(),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                transport = StdioTransport(process)
            else:
                parser.error("stdio transport requires --docker or --stdio-cmd")
        else:
            # HTTP transport
            transport = HTTPTransport(endpoint)

        # Create test client
        client = MCPTestClient(transport, args.config, args.verbose)

        # Initialize
        if not client.initialize():
            print("❌ Failed to initialize MCP session")
            sys.exit(1)

        # List tools/resources if requested
        if args.list_tools:
            tools = client.list_tools()
            print(f"\n📋 Available Tools ({len(tools)}):")
            for tool in tools:
                print(f"  • {tool.get('name')}: {tool.get('description', 'No description')}")
            return

        if args.list_resources:
            resources = client.list_resources()
            print(f"\n📋 Available Resources ({len(resources)}):")
            for resource in resources:
                print(f"  • {resource.get('uri')}: {resource.get('description', 'No description')}")
            return

        # Run tests
        tool_success = True
        resource_success = True

        if not args.resources_only:
            if args.test_tool:
                tool_success = client.run_tool_tests([args.test_tool])
            else:
                # Filter by idempotence if needed
                tools = filter_tests_by_idempotence(args.config, not args.all)
                tool_success = client.run_tool_tests(tools)

        if not args.tools_only:
            if args.test_resource:
                resource_success = client.run_resource_tests([args.test_resource])
            else:
                resource_success = client.run_resource_tests()

        # Show logs if requested
        if args.logs and docker_server:
            docker_server.logs()

        success = tool_success and resource_success
        sys.exit(0 if success else 1)

    finally:
        # Cleanup
        if transport:
            transport.close()
        if docker_server and not args.keep_container:
            docker_server.stop()
        elif docker_server and args.keep_container:
            print(f"💡 Container kept running: {docker_server.container_name}")


if __name__ == "__main__":
    main()
```

## Migration Plan

### Phase 1: Create Unified Client (Week 1)

**Tasks:**
1. Create `MCPTransport` abstract base class
2. Implement `StdioTransport` (extract from test_mcp.py)
3. Implement `HTTPTransport` (extract from mcp-test.py)
4. Create `MCPTestClient` with shared test logic
5. Keep `DockerMCPServer` as-is (move to unified file)

**Deliverable:** New unified `mcp-test.py` with both transports

### Phase 2: Add Resource Testing (Week 1)

**Tasks:**
1. Add `list_resources()` to `MCPTestClient`
2. Add `read_resource()` to `MCPTestClient`
3. Add `run_resource_tests()` to `MCPTestClient`
4. Update `mcp-list.py` to generate `test_resources` config
5. Test resource functionality on both transports

**Deliverable:** Resource testing working on both transports

### Phase 3: Backward Compatibility (Week 2)

**Tasks:**
1. Update `test_mcp.py` to be thin wrapper around unified client
2. Ensure `make test-scripts` still works
3. Test CI/CD integration
4. Verify all existing tests pass

**Deliverable:** Backward-compatible integration

### Phase 4: Deprecation (Week 2)

**Tasks:**
1. Mark old `test_mcp.py` as deprecated (but keep functional)
2. Update documentation to use unified client
3. Create migration guide
4. Update CI/CD to use unified client directly

**Deliverable:** Migration complete, old file deprecated

### Phase 5: Cleanup (Week 3+)

**Tasks:**
1. Remove old `test_mcp.py` after transition period
2. Clean up any remaining duplication
3. Final documentation updates

**Deliverable:** Single unified test client

## Benefits

### Development Velocity

**Before (Separate Files):**
- Add resource testing: ~400 lines across 2 files
- Bug fix: Apply to 2 files, test 2 implementations
- Feature: Implement twice

**After (Unified):**
- Add resource testing: ~200 lines in 1 file
- Bug fix: Apply once, works for both transports
- Feature: Implement once

**Time Savings:** ~50% reduction in implementation time

### Code Quality

**Metrics:**
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total LOC | 744 | ~550 | 26% reduction |
| Test logic duplication | ~300 lines | 0 | 100% elimination |
| Files to maintain | 2 | 1 | 50% reduction |
| Transport implementations | Embedded | Abstracted | Better separation |

### Maintainability

**Single Source of Truth:**
- One place to fix bugs
- One place to add features
- One place to update protocol
- One place to improve output

**Consistency:**
- Same test output format
- Same error messages
- Same CLI patterns
- Same behavior across transports

### Testability

**Easier to Test:**
- Mock transport layer
- Test logic independently
- Test transports independently
- Clear separation of concerns

## Risks and Mitigation

### Risk 1: Breaking CI/CD

**Impact:** High (blocks releases)
**Probability:** Medium

**Mitigation:**
- Keep old `test_mcp.py` as wrapper during transition
- Test thoroughly before switching CI/CD
- Have rollback plan
- Run both old and new in parallel temporarily

### Risk 2: Stdio/HTTP Behavior Divergence

**Impact:** Medium (inconsistent testing)
**Probability:** Low

**Mitigation:**
- Comprehensive transport interface tests
- Protocol compliance tests
- Cross-transport validation tests
- Transport abstraction review

### Risk 3: Complex Refactoring

**Impact:** Medium (delays timeline)
**Probability:** Medium

**Mitigation:**
- Phased approach (create new, keep old)
- Extensive testing at each phase
- Clear rollback points
- Gradual migration

### Risk 4: Docker Management Complexity

**Impact:** Low (Docker still works)
**Probability:** Low

**Mitigation:**
- Keep Docker code mostly unchanged
- Docker is just one way to get stdio transport
- Test Docker integration thoroughly

## Alternatives Considered

### Alternative 1: Keep Separate, Extract Shared Library

**Approach:** Create shared library, keep two CLI tools

**Pros:**
- Less risky
- Keeps existing files
- Gradual extraction

**Cons:**
- Still two files to maintain
- Still two CLIs to document
- Still some duplication
- More complex dependency

**Decision:** ❌ Rejected - Doesn't fully solve duplication

### Alternative 2: Rewrite from Scratch

**Approach:** Build new test framework from ground up

**Pros:**
- Clean slate
- Modern design
- No legacy baggage

**Cons:**
- Very high risk
- Long timeline
- Loses tested code
- Feature parity difficult

**Decision:** ❌ Rejected - Too risky, unnecessary

### Alternative 3: Status Quo

**Approach:** Keep separate files, duplicate resource testing

**Pros:**
- Zero risk
- Known quantity
- No migration needed

**Cons:**
- Technical debt grows
- Maintenance burden increases
- ~400 lines of duplicate code
- Bug fixes applied twice

**Decision:** ❌ Rejected - Maintenance burden too high

## Success Criteria

### Quantitative

- [ ] **LOC Reduction:** 25%+ reduction in total lines
- [ ] **Duplication:** 0 duplicated test logic lines
- [ ] **Coverage:** 100% transport abstraction test coverage
- [ ] **Performance:** No regression in test execution time
- [ ] **Compatibility:** 100% backward compatibility with existing CI/CD

### Qualitative

- [ ] **Simplicity:** Single CLI easier to understand and use
- [ ] **Maintainability:** Future features require single implementation
- [ ] **Reliability:** Transport abstraction makes testing more robust
- [ ] **Documentation:** Clear, unified documentation
- [ ] **Developer Experience:** Easier to add new features

## Conclusion

Consolidating `test_mcp.py` and `mcp-test.py` into a unified client with transport abstraction:

1. **Eliminates ~300 lines of duplication**
2. **Simplifies resource testing implementation** (200 lines instead of 400)
3. **Improves maintainability** (one place for bug fixes and features)
4. **Provides clean architecture** (transport abstraction, separation of concerns)
5. **Maintains backward compatibility** (via wrapper or direct CLI compatibility)

**Recommendation:** Proceed with unified client implementation as the foundation for resource testing.

---

**Status:** 📋 PROPOSAL
**Next Step:** Decide: Implement unified client first, or add resource testing to separate files?
**Author:** Claude Code
**Date:** 2025-11-12
