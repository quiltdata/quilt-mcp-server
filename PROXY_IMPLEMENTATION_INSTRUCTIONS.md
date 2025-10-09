# MCP Proxy Implementation Instructions for Codex

**Goal:** Enable the Quilt MCP server to route tool calls to remote MCP servers (BioContextAI, Benchling) while maintaining a single connection from the frontend.

**Repository:** `/Users/simonkohnstamm/Documents/Quilt/quilt-mcp-server`  
**Estimated Time:** 1-2 days for MVP, 5-7 days for full implementation  
**Priority:** HIGH - Enables actual usage of BioContextAI and Benchling tools

---

## 📋 Overview

### Current Architecture
```
Frontend → Quilt MCP Server → Quilt Native Tools
```

### Target Architecture
```
Frontend → Quilt MCP Server ─┬─→ Quilt Native Tools
                              ├─→ BioContextAI MCP (remote)
                              └─→ Benchling MCP (same-domain)
```

### Key Concept: Namespace Routing
- Frontend sends: `biocontext__search_pubmed`
- Backend parses: `biocontext` (server) + `search_pubmed` (tool)
- Backend routes to BioContextAI
- Backend returns results to frontend

---

## 🎯 Phase 1: MVP Implementation (1-2 days)

### Goal
Enable tool calls to **Benchling MCP only** with hardcoded configuration.

### Why Benchling First?
1. ✅ **Same domain** (`demo.quiltdata.com/benchling/mcp`) - no CORS
2. ✅ **Already deployed** - backend is running
3. ✅ **Auth configured** - secrets in AWS Secrets Manager
4. ✅ **Simpler** - fewer edge cases to handle

---

## 📁 File Structure

Create these new files in the repository:

```
/Users/simonkohnstamm/Documents/Quilt/quilt-mcp-server/
└── src/
    └── quilt_mcp/
        ├── proxy/
        │   ├── __init__.py
        │   ├── client.py        # Base remote MCP client
        │   ├── router.py        # Tool routing logic
        │   └── aggregator.py    # Tool list aggregation
        └── config/
            └── remote_servers.py # Server configuration
```

---

## 🔧 Implementation Steps

### Step 1: Create Remote MCP Client

**File:** `src/quilt_mcp/proxy/client.py`

**Purpose:** HTTP client for communicating with remote MCP servers

**Requirements:**
1. Support both **JSON** and **SSE** (Server-Sent Events) response formats
2. Handle MCP protocol 2024-11-05
3. Support `initialize` and `tools/list` methods
4. Support `tools/call` for executing tools
5. Include proper headers (Content-Type, mcp-protocol-version)
6. Handle errors gracefully with detailed logging

**Key Features:**
```python
class RemoteMCPClient:
    """HTTP client for remote MCP servers."""
    
    def __init__(self, endpoint: str, server_id: str):
        self.endpoint = endpoint
        self.server_id = server_id
        self.session = httpx.AsyncClient(timeout=30.0)
        
    async def initialize(self) -> dict:
        """Initialize connection to remote server."""
        # POST to endpoint with initialize method
        # Return server info
        
    async def list_tools(self) -> list[dict]:
        """Fetch tools from remote server."""
        # POST to endpoint with tools/list method
        # Parse SSE or JSON response
        # Return list of tools
        
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool on the remote server."""
        # POST to endpoint with tools/call method
        # Include tool name and arguments
        # Return result
        
    def _parse_response(self, text: str) -> dict:
        """Parse SSE or JSON response."""
        if "event:" in text or text.startswith("data:"):
            # SSE format - extract data: lines
            lines = text.split('\n')
            data_lines = [
                line.strip()[5:].strip() 
                for line in lines 
                if line.strip().startswith('data:')
            ]
            if data_lines:
                return json.loads(data_lines[0])
        else:
            # Regular JSON
            return json.loads(text)
```

**Dependencies:**
- Already in `pyproject.toml`: `httpx>=0.27.0`

**Testing:**
```python
# Test with Benchling
client = RemoteMCPClient(
    endpoint="https://demo.quiltdata.com/benchling/mcp",
    server_id="benchling"
)
await client.initialize()
tools = await client.list_tools()
print(f"Found {len(tools)} tools")
```

---

### Step 2: Create Tool Router

**File:** `src/quilt_mcp/proxy/router.py`

**Purpose:** Route tool calls to the correct backend (Quilt vs remote)

**Requirements:**
1. Parse tool names for namespace prefix
2. Route namespaced tools to remote clients
3. Route unprefixed tools to Quilt native handlers
4. Handle errors and provide fallback messages

**Key Features:**
```python
class ToolRouter:
    """Routes tool calls to appropriate backend."""
    
    def __init__(self):
        self.remote_clients: dict[str, RemoteMCPClient] = {}
        self._initialize_clients()
        
    def _initialize_clients(self):
        """Initialize remote MCP clients."""
        # For MVP: Hardcode Benchling
        self.remote_clients["benchling"] = RemoteMCPClient(
            endpoint="https://demo.quiltdata.com/benchling/mcp",
            server_id="benchling"
        )
        
    def parse_tool_name(self, tool_name: str) -> tuple[str | None, str]:
        """
        Parse tool name into (server_id, tool_name).
        
        Examples:
          - "benchling__get_entries" → ("benchling", "get_entries")
          - "search_buckets" → (None, "search_buckets")
        """
        if "__" in tool_name:
            parts = tool_name.split("__", 1)
            if len(parts) == 2 and parts[0] in self.remote_clients:
                return parts[0], parts[1]
        return None, tool_name
        
    async def route_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """
        Route tool call to appropriate backend.
        
        Returns:
          - Tool result dict
          - Raises exception on error
        """
        server_id, actual_tool_name = self.parse_tool_name(tool_name)
        
        if server_id:
            # Route to remote server
            client = self.remote_clients[server_id]
            return await client.call_tool(actual_tool_name, arguments)
        else:
            # Route to Quilt native tools
            # (handled by existing tool handlers)
            return None  # Signal to use native handler
```

**Integration Point:**
- Hook into existing tool execution flow
- Before calling native tools, check if router can handle it
- If router returns `None`, proceed with native handler

---

### Step 3: Create Tool Aggregator

**File:** `src/quilt_mcp/proxy/aggregator.py`

**Purpose:** Combine tools from Quilt native + remote servers

**Requirements:**
1. Fetch tools from all configured remote servers
2. Add namespace prefix to remote tool names
3. Update descriptions to show origin
4. Handle failures gracefully (continue if one server fails)
5. Cache tool lists for performance

**Key Features:**
```python
class ToolAggregator:
    """Aggregates tools from multiple MCP servers."""
    
    def __init__(self, router: ToolRouter):
        self.router = router
        self._cached_tools: list[dict] | None = None
        self._cache_ttl = 300  # 5 minutes
        
    async def get_all_tools(self, native_tools: list[dict]) -> list[dict]:
        """
        Aggregate tools from all sources.
        
        Args:
          native_tools: List of Quilt native tools
          
        Returns:
          Combined list with namespaced remote tools
        """
        tools = list(native_tools)  # Copy native tools
        
        # Fetch from each remote server
        for server_id, client in self.router.remote_clients.items():
            try:
                remote_tools = await client.list_tools()
                
                # Add namespace prefix
                for tool in remote_tools:
                    tool['name'] = f"{server_id}__{tool['name']}"
                    tool['description'] = f"[{client.server_id.title()}] {tool['description']}"
                    
                tools.extend(remote_tools)
                
            except Exception as e:
                # Log but don't fail entirely
                print(f"⚠️ Failed to load tools from {server_id}: {e}")
                
        return tools
```

**Integration Point:**
- Modify the `tools/list` handler to use aggregator
- Call `await aggregator.get_all_tools(native_tools)`
- Return combined list to frontend

---

### Step 4: Server Configuration

**File:** `src/quilt_mcp/config/remote_servers.py`

**Purpose:** Configuration for remote MCP servers

**MVP Version (Hardcoded):**
```python
"""Remote MCP server configuration."""

from dataclasses import dataclass


@dataclass
class RemoteServerConfig:
    """Configuration for a remote MCP server."""
    id: str
    name: str
    endpoint: str
    auth_type: str = "none"  # "none", "api-key", "oauth"
    enabled: bool = True


# MVP: Hardcoded Benchling only
REMOTE_SERVERS = [
    RemoteServerConfig(
        id="benchling",
        name="Benchling",
        endpoint="https://demo.quiltdata.com/benchling/mcp",
        auth_type="api-key",  # Handled by backend
        enabled=True,
    ),
]
```

**Future Version (Configurable):**
```python
import os
import json

def load_remote_servers() -> list[RemoteServerConfig]:
    """Load remote servers from environment or config file."""
    config_json = os.getenv("MCP_REMOTE_SERVERS")
    if config_json:
        configs = json.loads(config_json)
        return [RemoteServerConfig(**cfg) for cfg in configs]
    return REMOTE_SERVERS  # Fallback to hardcoded
```

---

### Step 5: Integration with Main Server

**File to Modify:** `src/quilt_mcp/utils.py` or wherever `run_server()` is defined

**Changes Needed:**

1. **Initialize proxy components:**
```python
from quilt_mcp.proxy.router import ToolRouter
from quilt_mcp.proxy.aggregator import ToolAggregator

# In run_server() or server initialization:
router = ToolRouter()
aggregator = ToolAggregator(router)
```

2. **Modify tools/list handler:**
```python
# Find the current tools/list implementation
# Wrap it with aggregation:

async def list_tools_handler():
    # Get native Quilt tools (existing logic)
    native_tools = await get_native_tools()
    
    # Aggregate with remote tools
    all_tools = await aggregator.get_all_tools(native_tools)
    
    return all_tools
```

3. **Modify tools/call handler:**
```python
# Find the current tools/call implementation
# Add routing logic:

async def call_tool_handler(tool_name: str, arguments: dict):
    # Try routing first
    result = await router.route_tool_call(tool_name, arguments)
    
    if result is None:
        # Not a remote tool, use native handler
        result = await call_native_tool(tool_name, arguments)
        
    return result
```

---

## 🧪 Testing

### Local Testing

1. **Test Remote Client:**
```bash
cd /Users/simonkohnstamm/Documents/Quilt/quilt-mcp-server
python -m pytest tests/proxy/test_client.py -v
```

2. **Test Router:**
```bash
python -m pytest tests/proxy/test_router.py -v
```

3. **Test End-to-End:**
```bash
# Start local server
uv run src/main.py

# In another terminal, test with mcp-test.py
python scripts/mcp-test.py
```

### Manual Testing

1. **List Tools:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

Expected: Should see both Quilt tools and `benchling__*` tools

2. **Call Benchling Tool:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "benchling__get_projects",
      "arguments": {"limit": 10}
    }
  }'
```

Expected: Should return Benchling projects

---

## 🚀 Deployment

### Update Dependencies

**File:** `pyproject.toml`

Already has `httpx>=0.27.0` ✅

### Build and Deploy

```bash
# 1. Update version
# Edit pyproject.toml: version = "0.6.73"

# 2. Build Docker image
cd /Users/simonkohnstamm/Documents/Quilt/quilt-mcp-server
docker build -t quiltdata/quilt-mcp:0.6.73 .

# 3. Tag and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 850787717197.dkr.ecr.us-east-1.amazonaws.com
docker tag quiltdata/quilt-mcp:0.6.73 850787717197.dkr.ecr.us-east-1.amazonaws.com/quiltdata/quilt-mcp:0.6.73
docker push 850787717197.dkr.ecr.us-east-1.amazonaws.com/quiltdata/quilt-mcp:0.6.73

# 4. Update ECS task definition
# Edit task-definition-final.json to use new image
aws ecs register-task-definition --cli-input-json file://task-definition-final.json --region us-east-1

# 5. Deploy to ECS
aws ecs update-service --cluster <cluster-name> --service <service-name> --task-definition <task-def-name>:<revision> --force-new-deployment --region us-east-1
```

---

## 📊 Success Criteria

### MVP is complete when:
1. ✅ `tools/list` returns Benchling tools with `benchling__` prefix
2. ✅ Can call Benchling tools: `benchling__get_projects`, `benchling__get_entries`, etc.
3. ✅ Results are returned correctly to frontend
4. ✅ Native Quilt tools still work normally
5. ✅ Error handling provides useful messages
6. ✅ Console logs show routing decisions

### Testing Checklist:
- [ ] List tools shows both Quilt and Benchling tools
- [ ] Benchling tools have `benchling__` prefix
- [ ] Can call `benchling__get_projects` successfully
- [ ] Can call `benchling__get_entries` successfully  
- [ ] Native tools like `search_buckets` still work
- [ ] Error messages are helpful when Benchling is down
- [ ] Performance is acceptable (<2s for tool calls)

---

## 🔮 Phase 2: Full Implementation (Next Steps)

After MVP works, expand to:

### 1. Add BioContextAI Support
```python
REMOTE_SERVERS = [
    RemoteServerConfig(
        id="benchling",
        endpoint="https://demo.quiltdata.com/benchling/mcp",
        enabled=True,
    ),
    RemoteServerConfig(
        id="biocontext",
        endpoint="https://mcp.biocontext.ai/mcp",
        enabled=True,
    ),
]
```

### 2. Make Configuration Dynamic
- Read from environment variable: `MCP_REMOTE_SERVERS`
- Support JSON configuration
- Allow runtime enable/disable

### 3. Add Error Handling
- Retry failed calls (3 attempts)
- Circuit breaker for failing servers
- Graceful degradation
- Detailed error logging

### 4. Add Caching
- Cache tool lists (5-minute TTL)
- Cache common query results
- Respect server rate limits

### 5. Add Monitoring
- Log all remote calls
- Track latency metrics
- Monitor success/failure rates
- Alert on high error rates

---

## 📝 Code Locations Reference

### Files to Create:
- `src/quilt_mcp/proxy/__init__.py`
- `src/quilt_mcp/proxy/client.py`
- `src/quilt_mcp/proxy/router.py`
- `src/quilt_mcp/proxy/aggregator.py`
- `src/quilt_mcp/config/remote_servers.py`

### Files to Modify:
- `src/quilt_mcp/utils.py` (or main server file)
  - Import and initialize proxy components
  - Modify `tools/list` handler
  - Modify `tools/call` handler

### Test Files to Create:
- `tests/proxy/test_client.py`
- `tests/proxy/test_router.py`
- `tests/proxy/test_aggregator.py`
- `tests/integration/test_proxy_e2e.py`

---

## 🐛 Common Issues & Solutions

### Issue 1: SSE Parsing Fails
**Symptom:** `SyntaxError: Unexpected token 'e'`  
**Solution:** Ensure `_parse_response()` checks for `event:` prefix and extracts `data:` lines correctly

### Issue 2: Tool Not Found
**Symptom:** "Unknown tool: benchling__get_projects"  
**Solution:** Verify tool aggregation is working and namespace prefix is added correctly

### Issue 3: Connection Timeout
**Symptom:** `httpx.TimeoutException`  
**Solution:** Increase timeout in `httpx.AsyncClient(timeout=60.0)` or check network connectivity

### Issue 4: Authentication Error
**Symptom:** `HTTP 401: Unauthorized`  
**Solution:** Verify Benchling backend has access to secrets and is passing credentials correctly

---

## 💬 Questions for Implementation

1. **Where is the current `tools/list` handler?**
   - Look for FastMCP decorators or route definitions
   - Search for `@mcp.tool()` or similar decorators

2. **Where is the current `tools/call` handler?**
   - Same location as `tools/list`
   - May be implicit in FastMCP framework

3. **How are native tools defined?**
   - Look for tool decorator usage
   - Check `src/quilt_mcp/tools/` directory

4. **What's the logging setup?**
   - Use existing logger for consistency
   - Add structured logging for proxy operations

---

## 🎊 Expected Outcome

After implementation:

1. **Frontend stays unchanged** - single MCP connection
2. **Backend routes calls** - transparent to frontend
3. **Users can use Benchling tools** - full functionality
4. **Foundation for more servers** - easy to add BioContextAI next

**Example User Experience:**
```
User: "Get my recent Benchling notebook entries"
Assistant: [Calls benchling__get_entries]
Backend: [Routes to Benchling MCP]
Result: Returns list of entries
```

Success! 🚀

