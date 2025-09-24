# Health Check Endpoints Analysis

**Issue Reference**: GitHub Issue #197 - Add Health Checks to MCP Server
**Branch**: `197-add-health-checks`
**Status**: Architecture Analysis

## Current Codebase Architecture

### 1. FastMCP Server Implementation

**Primary Components:**
- **Server Factory**: `create_mcp_server()` in `src/quilt_mcp/utils.py` creates base `FastMCP("quilt-mcp-server")` instance
- **Tool Registration**: `register_tools()` auto-discovers and registers tool modules as MCP tools using `mcp.tool(func)` decorator pattern
- **Server Bootstrap**: `create_configured_server()` combines server creation with tool registration
- **Runtime Entry**: `run_server()` handles transport configuration and server execution

**Transport Configuration:**
- Environment variable driven: `FASTMCP_TRANSPORT` (default: "stdio")
- Supported modes: `["stdio", "http", "sse", "streamable-http"]`
- Invalid transport values fall back to "stdio"
- Main entry point (`src/quilt_mcp/main.py`) explicitly sets `FASTMCP_TRANSPORT=stdio` for MCPB compatibility
- Docker containers override to `FASTMCP_TRANSPORT=http` via Dockerfile environment

**Current Server Run Pattern:**
```python
mcp = create_configured_server()
transport = os.environ.get("FASTMCP_TRANSPORT", "stdio")
mcp.run(transport=transport)
```

### 2. Existing Health Check Infrastructure

**Core Health Check Function:**
- **Location**: `src/quilt_mcp/tools/error_recovery.py`
- **Function**: `health_check_with_recovery()` - comprehensive health assessment
- **Coverage**: Authentication, permissions, Athena connectivity, package operations
- **Return Format**: Structured JSON with overall health status and component details

**Health Check Components:**
1. **Authentication Status**: Uses `auth.auth_status()` to verify Quilt login state
2. **Permissions Discovery**: Tests `permissions.aws_permissions_discover()` for S3 access
3. **Athena Connectivity**: Validates `athena_glue.athena_workgroups_list()` functionality
4. **Package Operations**: Checks `packages.packages_list()` basic functionality

**Error Recovery Framework:**
- **Batch Operations**: `batch_operation_with_recovery()` executes multiple checks with individual fallbacks
- **Safe Operations**: `safe_operation()` wrapper with comprehensive error handling and timing
- **Recovery Suggestions**: Context-aware recommendations based on operation type and error patterns
- **Fallback Support**: Primary/fallback function patterns with metadata tracking

**Status Classification:**
- **Healthy**: All components functioning normally
- **Degraded**: Some components failing but core functionality intact
- **Unhealthy**: Multiple critical issues detected

### 3. HTTP Transport and Container Support

**Docker Configuration:**
- **Base Image**: `ghcr.io/astral-sh/uv:python3.11-bookworm-slim`
- **Transport Override**: `FASTMCP_TRANSPORT=http` set in Dockerfile
- **Network Config**: `FASTMCP_HOST=0.0.0.0`, `FASTMCP_PORT=8000`
- **Exposed Port**: Container exposes port 8000

**FastMCP HTTP Transport:**
- **MCP Endpoint**: Server exposes MCP protocol at `/mcp` path when using HTTP transport
- **Current Test**: `tests/integration/test_docker_container.py` validates container serves HTTP at `/mcp`
- **Expected Responses**: HTTP 200, 302, 307, or 406 status codes for MCP endpoint

**Routing Limitations:**
- **No Custom Routes**: Current FastMCP implementation only provides MCP protocol endpoint
- **No REST API**: No mechanism discovered for adding custom HTTP endpoints alongside MCP protocol
- **Transport Isolation**: HTTP transport mode only serves MCP protocol, not general web server

### 4. Current Testing Patterns

**Integration Test Structure:**
- **Docker Tests**: `test_docker_container.py` builds image and validates HTTP readiness
- **Health Check Tests**: `test_error_recovery.py` validates health check logic and error scenarios
- **Transport Testing**: Limited to stdio transport with monkeypatched environment variables

**Test Coverage Gaps:**
- **HTTP Health Endpoints**: No tests for HTTP-accessible health endpoints
- **Cross-Transport Testing**: Health checks not validated across all transport modes
- **Container Health Probes**: No tests for Docker health check integration

## Existing Patterns and Conventions

### 1. Tool Registration Pattern

**Auto-Discovery Mechanism:**
```python
# All public functions in tool modules automatically become MCP tools
functions = inspect.getmembers(module, predicate=make_predicate(module))
for name, func in functions:
    mcp.tool(func)  # FastMCP decorator registration
```

**Tool Module Structure:**
- Public functions (no leading underscore) automatically registered
- Type hints used for parameter validation
- Standardized return format with `success`, `error`, `timestamp` fields

### 2. Error Handling and Response Formatting

**Standardized Error Response:**
```python
{
    "success": False,
    "error": "Error message",
    "timestamp": "ISO 8601 timestamp",
    "recovery_suggestions": ["suggestion1", "suggestion2"]
}
```

**Safe Operation Pattern:**
- Execution timing measurement
- Comprehensive exception handling
- Fallback value support
- Recovery recommendation generation

### 3. Environment Configuration

**Configuration Sources:**
- Environment variables (`.env` file support)
- Runtime environment variable overrides
- Container environment configuration
- Makefile target environment setup

**Transport Selection Logic:**
- Environment variable precedence
- Validation with fallback to safe defaults
- Container-specific overrides

## Constraints and Limitations

### 1. FastMCP Framework Constraints

**Limited HTTP Customization:**
- **MCP Protocol Only**: FastMCP HTTP transport serves MCP protocol at fixed `/mcp` path
- **No Custom Routes**: No documented mechanism for adding additional HTTP endpoints
- **Transport Isolation**: Cannot serve both MCP protocol and REST API simultaneously

**Transport Mode Limitations:**
- **Binary Transport Selection**: Must choose single transport mode at startup
- **No Mixed Mode**: Cannot serve multiple transports simultaneously
- **Cross-Transport Compatibility**: Health functionality must work across all transport modes

### 2. Container Environment Variables

**Required Container Configuration:**
- `FASTMCP_TRANSPORT=http` - Enables HTTP transport
- `FASTMCP_HOST=0.0.0.0` - Binds to all interfaces
- `FASTMCP_PORT=8000` - Sets HTTP port

**Port Configuration:**
- Fixed port 8000 exposed in Dockerfile
- No dynamic port allocation
- Container orchestration must handle port mapping

### 3. Authentication and Security

**No HTTP Authentication:**
- Current MCP tools require Quilt authentication
- Health endpoints should not require authentication per requirements
- Need to differentiate authenticated MCP tools from public health endpoints

## Technical Debt and Challenges

### 1. Missing HTTP Health Endpoint

**Current Gap:**
- `health_check_with_recovery()` function exists but not exposed via HTTP
- Docker container serves HTTP but only provides `/mcp` MCP protocol endpoint
- Container orchestration systems cannot access health status via HTTP

**Integration Challenge:**
- Need to expose health functionality outside MCP protocol
- Must work when `FASTMCP_TRANSPORT=http` is set
- Should not interfere with existing MCP tool operation

### 2. Error Recovery Module Disabled

**Current Status:**
- `error_recovery` module commented out in `utils.py` tool registration
- Comment indicates "Callable parameter issues" preventing registration
- Health check function exists but not accessible as MCP tool

**Impact:**
- Rich health check functionality already implemented but inaccessible
- Need to resolve registration issues or create alternative access method

### 3. Docker Test Expectations vs Reality

**Test Assumptions:**
- `test_docker_container.py` expects `/mcp` endpoint to respond
- Tests validate MCP protocol availability
- No tests for `/health` endpoints that don't exist yet

**Missing Health Probe Support:**
- Docker containers typically need `/health` endpoint for orchestration
- Current tests validate MCP availability, not service health
- No integration between container health checks and internal health assessment

### 4. Cross-Transport Health Access

**Stdio Transport Challenge:**
- Health checks must work in stdio transport mode (Claude Desktop)
- Cannot use HTTP endpoints when transport is stdio
- Need consistent health check access across all transport modes

**Transport-Specific Behavior:**
- HTTP transport could serve health endpoints
- stdio transport needs health via MCP tools
- SSE transport behavior unclear for custom endpoints

## Gaps Between Current State and Requirements

### 1. HTTP Endpoint Gap

**Required Endpoints Missing:**
- `/health` - General health status
- `/health/simple` - Minimal response for load balancers
- `/health/detailed` - Comprehensive diagnostics
- `/readiness` - Kubernetes-style readiness probe
- `/liveness` - Kubernetes-style liveness probe

**Current State:**
- Only `/mcp` endpoint exists for MCP protocol
- No mechanism identified for adding custom HTTP routes

### 2. FastMCP Integration Unknown

**Documentation Gap:**
- No clear guidance on adding custom HTTP routes to FastMCP server
- FastMCP README shows basic HTTP transport but not custom endpoints
- Need to investigate FastMCP source code or request documentation

**Architectural Questions:**
- Can FastMCP serve both MCP protocol and REST endpoints?
- Does FastMCP provide route decoration or middleware support?
- How to access underlying HTTP server framework?

### 3. Error Recovery Registration Issue

**Blocking Issue:**
- Existing health check function cannot be registered as MCP tool
- "Callable parameter issues" prevent module loading
- Need to resolve or work around registration problem

### 4. Container Orchestration Support

**Missing Integration:**
- No Docker HEALTHCHECK directive in Dockerfile
- No container-native health probe endpoints
- Gap between internal health assessment and container orchestration needs

### 5. Performance and Resource Overhead

**Unknown Performance Impact:**
- Current health checks may be too heavyweight for frequent load balancer probes
- No benchmarking of health check execution time
- Need lightweight variants for high-frequency health checks

### 6. Authentication Bypass Requirements

**Security Considerations:**
- Health endpoints must not require Quilt authentication
- Need to ensure health endpoints don't expose sensitive information
- Balance between useful diagnostics and security

## Next Steps for Design Phase

1. **Investigate FastMCP Custom Routes**: Research FastMCP source code or documentation for HTTP route customization
2. **Resolve Error Recovery Registration**: Fix "Callable parameter issues" preventing health check tool registration
3. **Define Transport-Specific Behavior**: Determine how health checks work across stdio, HTTP, and SSE transports
4. **Design Endpoint Architecture**: Plan health endpoint structure that integrates with existing health check framework
5. **Security Model**: Define authentication requirements and information exposure policies for health endpoints