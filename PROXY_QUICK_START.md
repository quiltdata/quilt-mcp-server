# MCP Proxy - Quick Start Guide

**For:** Codex AI implementing the proxy  
**Time:** 1-2 days for MVP  
**Goal:** Enable Benchling tool usage from frontend

---

## 🎯 Three-Step Implementation

### Step 1: Create Remote Client (2-3 hours)
**File:** `src/quilt_mcp/proxy/client.py`

```python
import httpx
import json

class RemoteMCPClient:
    def __init__(self, endpoint: str, server_id: str):
        self.endpoint = endpoint
        self.server_id = server_id
        self.session = httpx.AsyncClient(timeout=30.0)
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        response = await self.session.post(
            self.endpoint,
            json={
                "jsonrpc": "2.0",
                "id": "tool-call",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments}
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
        )
        text = await response.text()
        return self._parse_response(text)
    
    def _parse_response(self, text: str) -> dict:
        if "event:" in text or text.startswith("data:"):
            # SSE format
            lines = [l.strip()[5:].strip() for l in text.split('\n') if l.strip().startswith('data:')]
            return json.loads(lines[0]) if lines else {}
        return json.loads(text)
```

### Step 2: Add Routing Logic (1-2 hours)
**File:** Modify existing tool call handler

```python
# Add at top of file
benchling_client = RemoteMCPClient(
    endpoint="https://demo.quiltdata.com/benchling/mcp",
    server_id="benchling"
)

# In tools/call handler:
async def handle_tool_call(tool_name: str, arguments: dict):
    # Check if it's a Benchling tool
    if tool_name.startswith("benchling__"):
        actual_name = tool_name.replace("benchling__", "")
        result = await benchling_client.call_tool(actual_name, arguments)
        return result["result"]
    
    # Otherwise, use native tools
    return await call_native_tool(tool_name, arguments)
```

### Step 3: Add to Tool List (1 hour)
**File:** Modify tools/list handler

```python
async def handle_tools_list():
    # Get native tools
    native_tools = await get_native_tools()
    
    # Get Benchling tools
    benchling_tools_response = await benchling_client.call_tool("list_tools", {})
    benchling_tools = benchling_tools_response.get("result", {}).get("tools", [])
    
    # Add namespace prefix
    for tool in benchling_tools:
        tool["name"] = f"benchling__{tool['name']}"
        tool["description"] = f"[Benchling] {tool['description']}"
    
    return native_tools + benchling_tools
```

---

## 🧪 Testing

```bash
# 1. Start server locally
cd /Users/simonkohnstamm/Documents/Quilt/quilt-mcp-server
uv run src/main.py

# 2. Test tool list
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# Should see benchling__ tools

# 3. Test tool call
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{
      "name":"benchling__get_projects",
      "arguments":{"limit":10}
    }
  }'
```

---

## 📍 Where to Find Things

### Main Server Entry
- Start: `src/main.py`
- Calls: `quilt_mcp.utils.run_server()`

### Tool Handlers
Search for: `@mcp.tool()` or `@server.tool()`

### Dependencies
- Already has `httpx` ✅
- Check: `pyproject.toml` line 29

---

## ⚡ Quick Deploy

```bash
# 1. Update version
sed -i '' 's/version = "0.6.72"/version = "0.6.73"/' pyproject.toml

# 2. Build & Push
make deploy  # or manual docker build/push

# 3. Update ECS
aws ecs update-service \
  --cluster <cluster> \
  --service <service> \
  --force-new-deployment
```

---

## 🎯 Success = Frontend Can Use Benchling

When working:
1. Frontend calls: `benchling__get_entries`
2. Backend routes to Benchling
3. Results appear in frontend
4. Native tools still work

**That's it!** 🚀

