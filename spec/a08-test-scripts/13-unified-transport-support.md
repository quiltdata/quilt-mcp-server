# Unified Transport Support for MCP Test Scripts

**Status**: Proposed
**Created**: 2025-01-12
**Spec ID**: a08-13

## Problem Statement

We currently have two test scripts with significant duplication:

1. **[mcp-test.py](../../scripts/mcp-test.py)** (700 lines)
   - HTTP transport only
   - Direct JSON-RPC testing via `requests` library
   - Used for manual testing with standalone endpoint URLs
   - Has comprehensive test infrastructure (test config loading, validation, detailed reporting)

2. **[test_mcp.py](../../scripts/tests/test_mcp.py)** (1,239 lines)
   - stdio transport only
   - Direct stdio JSON-RPC via subprocess pipes
   - Used for automated integration tests with Docker/local servers
   - **Duplicates** most of mcp-test.py's test logic (400+ lines)

### Current Issues

1. **Code Duplication**: Both scripts implement:
   - Test config loading and filtering
   - Tool/resource test execution
   - Result validation and error handling
   - Detailed failure reporting
   - Progress tracking and statistics

2. **Maintenance Burden**: Changes to test logic must be made in two places

3. **Feature Gaps**:
   - mcp-test.py only supports HTTP
   - test_mcp.py only supports stdio
   - Neither supports both transports for flexible testing

4. **Architecture Mismatch**:
   - mcp-test.py is a standalone CLI tool
   - test_mcp.py is a test runner that should orchestrate, not duplicate

## Proposed Solution

Refactor to a clean separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│ scripts/mcp-test.py                                      │
│ - Unified transport CLI tool                             │
│ - Supports BOTH stdio AND HTTP                           │
│ - All test execution logic                               │
│ - Exit codes for CI integration                          │
└─────────────────────────────────────────────────────────┘
                            ▲
                            │ subprocess.run()
                            │
┌─────────────────────────────────────────────────────────┐
│ scripts/tests/test_mcp.py                                │
│ - Test orchestrator                                      │
│ - Server lifecycle management (Docker/Local)             │
│ - Calls mcp-test.py via subprocess                       │
│ - NO duplication of test logic                           │
└─────────────────────────────────────────────────────────┘
```

## Design

### 1. Enhanced mcp-test.py

Add stdio transport support alongside existing HTTP:

```python
class MCPTester:
    """Unified MCP testing client supporting stdio and HTTP transports."""

    def __init__(self, endpoint: str = None, process: subprocess.Popen = None,
                 verbose: bool = False, transport: str = "http"):
        """Initialize tester.

        Args:
            endpoint: HTTP endpoint URL (for HTTP transport)
            process: Running subprocess with stdio pipes (for stdio transport)
            verbose: Enable verbose output
            transport: "http" or "stdio"
        """
        self.transport = transport
        self.verbose = verbose
        self.request_id = 1

        if transport == "http":
            if not endpoint:
                raise ValueError("endpoint required for HTTP transport")
            self.endpoint = endpoint
            self.session = requests.Session()
            self.session.headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            })
        elif transport == "stdio":
            if not process:
                raise ValueError("process required for stdio transport")
            self.process = process
        else:
            raise ValueError(f"Unsupported transport: {transport}")

    def _make_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Make JSON-RPC request using configured transport."""
        if self.transport == "http":
            return self._make_http_request(method, params)
        else:
            return self._make_stdio_request(method, params)

    def _make_http_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Execute via HTTP (existing implementation)."""
        # ... existing HTTP code ...

    def _make_stdio_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Execute via stdio pipes."""
        request_data = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }
        if params:
            request_data["params"] = params

        self.request_id += 1

        # Write request to stdin
        self.process.stdin.write(json.dumps(request_data) + "\n")
        self.process.stdin.flush()

        # Read response from stdout
        response_line = self.process.stdout.readline()
        if not response_line:
            raise Exception("No response from server")

        result = json.loads(response_line)

        if "error" in result:
            raise Exception(f"JSON-RPC error: {result['error']}")

        return result.get("result", {})
```

#### CLI Interface

```bash
# HTTP transport (current behavior)
mcp-test.py http://localhost:8000/mcp --tools-test

# stdio transport (NEW)
mcp-test.py --stdio --process-id 12345 --tools-test

# stdio with subprocess spawn (NEW)
mcp-test.py --stdio --command "docker run -i mcp-server" --tools-test
```

#### Arguments

```python
parser.add_argument(
    "endpoint",
    nargs="?",  # Optional for stdio mode
    help="MCP endpoint URL (required for HTTP transport)"
)

# Transport mode
transport_group = parser.add_mutually_exclusive_group()
transport_group.add_argument(
    "--http",
    action="store_true",
    default=True,  # Default to HTTP for backward compatibility
    help="Use HTTP transport (default)"
)
transport_group.add_argument(
    "--stdio",
    action="store_true",
    help="Use stdio transport (stdin/stdout)"
)

# stdio-specific options
parser.add_argument(
    "--process-id",
    type=int,
    help="PID of running MCP server for stdio (use existing process)"
)
parser.add_argument(
    "--command",
    help="Command to spawn MCP server subprocess for stdio"
)
parser.add_argument(
    "--stdin-fd",
    type=int,
    help="File descriptor for stdin (advanced, for test orchestration)"
)
parser.add_argument(
    "--stdout-fd",
    type=int,
    help="File descriptor for stdout (advanced, for test orchestration)"
)
```

### 2. Simplified test_mcp.py

Remove all duplicated test logic, delegate to mcp-test.py:

```python
def run_tests_stdio(
    server: Union[DockerMCPServer, LocalMCPServer],
    config_path: Path,
    tools: Optional[list[str]] = None,
    verbose: bool = False
) -> bool:
    """Run MCP tests by calling mcp-test.py with stdio transport.

    This function now delegates ALL test execution to mcp-test.py,
    eliminating code duplication.
    """
    print(f"\n🧪 Running MCP tests (stdio via mcp-test.py)...")

    # Build command to invoke mcp-test.py with stdio transport
    cmd = [
        sys.executable,
        str(MCP_TEST_SCRIPT),
        "--stdio",
        "--stdin-fd", str(server.process.stdin.fileno()),
        "--stdout-fd", str(server.process.stdout.fileno()),
        "--config", str(config_path),
        "--tools-test"
    ]

    if tools:
        for tool in tools:
            cmd.extend(["--test-tool", tool])

    if verbose:
        cmd.append("--verbose")

    # Run mcp-test.py and capture result
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Print output
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Return success based on exit code
    return result.returncode == 0


def run_resource_tests_stdio(
    server: Union[DockerMCPServer, LocalMCPServer],
    config_path: Path,
    resources: Optional[list[str]] = None,
    verbose: bool = False,
    skip_init: bool = False
) -> bool:
    """Run resource tests by calling mcp-test.py with stdio transport."""
    print(f"\n🗂️  Running resource tests (stdio via mcp-test.py)...")

    cmd = [
        sys.executable,
        str(MCP_TEST_SCRIPT),
        "--stdio",
        "--stdin-fd", str(server.process.stdin.fileno()),
        "--stdout-fd", str(server.process.stdout.fileno()),
        "--config", str(config_path),
        "--resources-test"
    ]

    if resources:
        for resource in resources:
            cmd.extend(["--test-resource", resource])

    if verbose:
        cmd.append("--verbose")

    if skip_init:
        cmd.append("--skip-init")

    result = subprocess.run(cmd, capture_output=True, text=True)

    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode == 0
```

### 3. Migration Path

#### Phase 1: Add stdio support to mcp-test.py
- [ ] Add transport abstraction layer (`_make_http_request`, `_make_stdio_request`)
- [ ] Add CLI arguments for stdio mode
- [ ] Add file descriptor passing support
- [ ] Test stdio transport independently

#### Phase 2: Refactor test_mcp.py to use mcp-test.py
- [ ] Replace `run_tests_stdio()` implementation with subprocess call
- [ ] Replace `run_resource_tests_stdio()` implementation with subprocess call
- [ ] Remove all duplicated test logic (400+ lines)
- [ ] Update error handling to parse mcp-test.py output

#### Phase 3: Testing & Documentation
- [ ] Verify both transports work correctly
- [ ] Update test suite to cover both transports
- [ ] Update documentation
- [ ] Update CI pipeline if needed

## Implementation Details

### File Descriptor Passing

For subprocess communication, we use file descriptor passing:

```python
# test_mcp.py spawns server and gets stdio pipes
server_process = subprocess.Popen(
    ["docker", "run", "-i", "mcp-server"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

# Get raw file descriptor numbers
stdin_fd = server_process.stdin.fileno()
stdout_fd = server_process.stdout.fileno()

# Pass to mcp-test.py as arguments
subprocess.run([
    "python", "mcp-test.py",
    "--stdio",
    "--stdin-fd", str(stdin_fd),
    "--stdout-fd", str(stdout_fd),
    "--tools-test"
])
```

### Session Initialization

stdio transport requires MCP handshake:

```python
def initialize(self) -> Dict[str, Any]:
    """Initialize MCP session (both transports)."""
    result = self._make_request("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "mcp-test", "version": "1.0"}
    })

    # stdio requires notifications/initialized after initialize
    if self.transport == "stdio":
        self._send_notification("notifications/initialized")

    return result

def _send_notification(self, method: str, params: Optional[Dict] = None):
    """Send JSON-RPC notification (no response expected)."""
    if self.transport == "stdio":
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params:
            notification["params"] = params

        self.process.stdin.write(json.dumps(notification) + "\n")
        self.process.stdin.flush()
        time.sleep(0.1)  # Brief pause for server processing
```

## Benefits

1. **Single Source of Truth**: All test logic in one place (mcp-test.py)
2. **DRY**: Remove 400+ lines of duplicated code
3. **Flexibility**: Support both transports from same tool
4. **Maintainability**: Changes only need to be made once
5. **Testability**: Can test both transports with same test suite
6. **Separation of Concerns**:
   - mcp-test.py = test execution
   - test_mcp.py = server orchestration

## Backward Compatibility

- Existing HTTP usage of mcp-test.py unchanged
- test_mcp.py CLI interface unchanged
- Make test targets unchanged
- CI pipeline unchanged (just calls same scripts)

## Alternatives Considered

### Alternative 1: Python library approach
Create a shared library imported by both scripts:

```python
# mcp_test_lib.py
class MCPTestRunner:
    def run_tool_tests(...)
    def run_resource_tests(...)
```

**Rejected**: Adds unnecessary abstraction layer. mcp-test.py is already a complete CLI tool; better to reuse it directly.

### Alternative 2: Keep duplication
Accept duplication as "cost of simplicity."

**Rejected**: 400+ lines of duplication is too high a maintenance cost. Test logic changes frequently as MCP spec evolves.

### Alternative 3: Make test_mcp.py import mcp-test.py functions
```python
from mcp_test import MCPTester, run_tools_test
```

**Rejected**: Creates tight coupling between scripts. Subprocess invocation is cleaner separation of concerns.

## Success Criteria

- [ ] mcp-test.py supports both HTTP and stdio transports
- [ ] test_mcp.py < 800 lines (down from 1,239)
- [ ] All existing tests pass with refactored code
- [ ] No behavioral changes to end users
- [ ] CI pipeline continues working
- [ ] Code coverage maintained or improved

## Related Specs

- [01-test-mcp.md](01-test-mcp.md) - Original mcp-test.py design
- [03-stdio-transport-approach.md](03-stdio-transport-approach.md) - stdio transport decision
- [09-local-server-mode.md](09-local-server-mode.md) - Local server testing

## References

- [MCP Specification - Transport Layer](https://spec.modelcontextprotocol.io/specification/architecture/#transports)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- Selected code: [scripts/mcp-test.py:312-325](../../scripts/mcp-test.py#L312-L325)
