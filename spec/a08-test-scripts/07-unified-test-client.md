# Unified MCP Test Client: Transport Abstraction for mcp-test.py

**Date:** 2025-11-12
**Status:** 📋 PROPOSAL
**Related:** [06-resource-testing-extension.md](./06-resource-testing-extension.md), [06a-corrected-architecture.md](./06a-corrected-architecture.md)

## Executive Summary

Add stdio transport support to `mcp-test.py` through a transport abstraction layer.
This centralizes all test logic in one place, preventing test drift between HTTP and
stdio transports. `test_mcp.py` becomes a simple Docker orchestrator that launches
containers and delegates to `mcp-test.py`.

## Problem: Test Drift

**Current State:**

- `mcp-test.py`: Tests via HTTP, reads mcp-test.yaml, validates results
- `test_mcp.py`: Tests via stdio, reads mcp-test.yaml, validates results (different implementation)

**Critical Issue:** Test logic exists in two places

- Configuration parsing: 2 implementations → drift over time
- Tool validation: 2 implementations → different behavior
- Result reporting: 2 implementations → inconsistent output

**Adding resource testing would require:**

- ~200 lines in `mcp-test.py` (HTTP)
- ~200 lines in `test_mcp.py` (stdio)
- Two places to fix bugs, two places to add features

## Solution: Transport Abstraction

**New Architecture:**

```
┌─────────────────────────────────────┐
│  test_mcp.py (Docker orchestrator)  │
│  - Build/launch container           │
│  - Call mcp-test.py --transport     │
└─────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│    mcp-test.py (unified test logic) │
│    ┌───────────────────────────┐   │
│    │  MCPTestClient            │   │
│    │  - Read mcp-test.yaml     │   │
│    │  - Run tool tests         │   │
│    │  - Run resource tests     │   │
│    │  - Report results         │   │
│    └───────────────────────────┘   │
│              │                      │
│    ┌─────────┴─────────┐           │
│    │                   │           │
│  ┌─▼──────┐      ┌─────▼───┐      │
│  │ Stdio  │      │  HTTP   │      │
│  │Transport│     │Transport│      │
│  └────────┘      └─────────┘      │
└─────────────────────────────────────┘
```

**Key Principle:** Test logic exists once, transport is just I/O

## Implementation

### 1. Transport Abstraction Layer

```python
class MCPTransport(ABC):
    """Abstract base class for MCP transport."""

    @abstractmethod
    def send_request(self, request: Dict) -> Dict:
        """Send JSON-RPC request, return response."""
        pass

    @abstractmethod
    def send_notification(self, notification: Dict) -> None:
        """Send notification (no response expected)."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close connection."""
        pass
```

### 2. Stdio Transport

```python
class StdioTransport(MCPTransport):
    """Stdio transport via subprocess."""

    def __init__(self, process: subprocess.Popen):
        self.process = process

    def send_request(self, request: Dict) -> Dict:
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        response = self.process.stdout.readline()
        return json.loads(response)

    def send_notification(self, notification: Dict) -> None:
        self.process.stdin.write(json.dumps(notification) + "\n")
        self.process.stdin.flush()

    def close(self) -> None:
        self.process.terminate()
        self.process.wait(timeout=10)
```

### 3. HTTP Transport (existing)

```python
class HTTPTransport(MCPTransport):
    """HTTP transport via requests."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.session = requests.Session()

    def send_request(self, request: Dict) -> Dict:
        response = self.session.post(self.endpoint, json=request, timeout=10)
        response.raise_for_status()
        return response.json()

    def send_notification(self, notification: Dict) -> None:
        try:
            self.session.post(self.endpoint, json=notification, timeout=1)
        except:
            pass  # Notifications don't require response

    def close(self) -> None:
        self.session.close()
```

### 4. Unified Test Client

```python
class MCPTestClient:
    """Unified test client - works with any transport."""

    def __init__(self, transport: MCPTransport, config_path: Path):
        self.transport = transport
        self.config_path = config_path
        self.request_id = 1

    def initialize(self) -> bool:
        """Initialize MCP session."""
        request = {
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
        result = self.transport.send_request(request)

        if "error" not in result:
            # Send initialized notification
            self.transport.send_notification({
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            })
            time.sleep(0.5)
            return True
        return False

    def call_tool(self, name: str, arguments: Dict = None) -> Dict:
        """Call a tool (works for any transport)."""
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

    def run_tool_tests(self, specific_tools: List[str] = None) -> bool:
        """Run tool tests - SINGLE IMPLEMENTATION."""
        config = yaml.safe_load(self.config_path.read_text())
        test_tools = config.get("test_tools", {})

        if specific_tools:
            test_tools = {k: v for k, v in test_tools.items() if k in specific_tools}

        success_count = 0
        fail_count = 0

        print(f"\n🧪 Running tool tests ({len(test_tools)} tools)...")

        for tool_name, test_config in test_tools.items():
            try:
                result = self.call_tool(tool_name, test_config.get("arguments", {}))

                if "error" in result:
                    fail_count += 1
                    print(f"  ❌ {tool_name}: {result['error'].get('message')}")
                else:
                    success_count += 1
                    print(f"  ✅ {tool_name}")
            except Exception as e:
                fail_count += 1
                print(f"  ❌ {tool_name}: {e}")

        print(f"\n📊 Results: {success_count}/{len(test_tools)} passed")
        return fail_count == 0

    def run_resource_tests(self) -> bool:
        """Run resource tests - SINGLE IMPLEMENTATION."""
        # Similar to run_tool_tests but for resources
        # Implementation details from 06-resource-testing-extension.md
        pass
```

### 5. Updated mcp-test.py CLI

```python
def main():
    parser = argparse.ArgumentParser(description="MCP test client")

    # Transport selection
    parser.add_argument("endpoint", nargs="?", help="HTTP endpoint (shortcut)")
    parser.add_argument("--transport", choices=["stdio", "http"])

    # Stdio options
    parser.add_argument("--stdio-process", help="Subprocess handle for stdio")

    # HTTP options
    parser.add_argument("--endpoint", help="HTTP endpoint URL")

    # Test selection
    parser.add_argument("--tools-only", action="store_true")
    parser.add_argument("--resources-only", action="store_true")
    parser.add_argument("--test-tool", help="Test specific tool")

    # Config
    parser.add_argument("--config", type=Path, default=Path("tests/mcp-test.yaml"))

    args = parser.parse_args()

    # Determine transport
    if args.endpoint or args.transport == "http":
        endpoint = args.endpoint or args.endpoint
        transport = HTTPTransport(endpoint)
    elif args.stdio_process:
        # For use by test_mcp.py
        process = ... # Get process handle from test_mcp.py
        transport = StdioTransport(process)
    else:
        parser.error("Specify either HTTP endpoint or stdio process")

    # Run tests with unified client
    client = MCPTestClient(transport, args.config)

    if not client.initialize():
        sys.exit(1)

    success = True
    if not args.resources_only:
        success &= client.run_tool_tests()
    if not args.tools_only:
        success &= client.run_resource_tests()

    transport.close()
    sys.exit(0 if success else 1)
```

### 6. Simplified test_mcp.py

```python
class DockerMCPServer:
    """Manages Docker container (unchanged)."""

    def start(self) -> subprocess.Popen:
        """Build/start container, return process."""
        # Existing Docker management code (~115 lines)
        pass

    def stop(self):
        """Stop container."""
        pass

def main():
    parser = argparse.ArgumentParser(description="Docker-based MCP testing")
    parser.add_argument("--image", default="quiltdata/quilt-mcp-server:latest")
    parser.add_argument("--logs", action="store_true")
    # ... other Docker-specific options

    args = parser.parse_args()

    # Start Docker container
    docker = DockerMCPServer(image=args.image)
    process = docker.start()

    try:
        # Delegate to mcp-test.py for actual testing
        result = subprocess.run([
            "python", "mcp-test.py",
            "--transport", "stdio",
            "--stdio-process", str(process.pid),  # Or pass via stdin/stdout
            # Pass through test selection args
        ])
        sys.exit(result.returncode)
    finally:
        if args.logs:
            docker.logs()
        docker.stop()
```

## Benefits

### Single Source of Truth

- ✅ One place to read mcp-test.yaml
- ✅ One place to validate tools
- ✅ One place to validate resources
- ✅ One place to report results
- ✅ Zero test drift between transports

### Reduced Maintenance

- Adding resource testing: ~200 lines (once) instead of ~400 lines (twice)
- Bug fixes: Apply once, works for both transports
- Output format: Consistent across all transports

### Clear Separation

- `mcp-test.py`: Test logic (transport-agnostic)
- `test_mcp.py`: Docker orchestration only
- Transport layer: Just I/O, no logic

## Migration Plan

### Phase 1: Add Transport Abstraction

1. Create `MCPTransport` abstract class in mcp-test.py
2. Refactor existing HTTP code to `HTTPTransport`
3. Add `StdioTransport` class
4. Test both transports work

### Phase 2: Add Resource Testing

1. Add `list_resources()` to `MCPTestClient`
2. Add `read_resource()` to `MCPTestClient`
3. Add `run_resource_tests()` to `MCPTestClient`
4. Works automatically for both transports

### Phase 3: Simplify test_mcp.py

1. Remove duplicated test logic from test_mcp.py
2. Keep only Docker management
3. Call mcp-test.py for actual testing
4. Verify CI/CD still works

## Success Criteria

- [ ] All test logic exists once in mcp-test.py
- [ ] Both stdio and HTTP transports use same test logic
- [ ] Resource testing works on both transports
- [ ] CI/CD unchanged (make test-scripts still works)
- [ ] Zero test drift risk

## Conclusion

**Core Insight:** Transport is just I/O. Test logic must be centralized.

**Implementation:**

- mcp-test.py: Unified test logic + transport abstraction
- test_mcp.py: Docker orchestrator only

**Result:** Single implementation, consistent behavior, no drift

---

**Status:** 📋 PROPOSAL
**Next Step:** Implement transport abstraction in mcp-test.py
**Author:** Claude Code
**Date:** 2025-11-12
