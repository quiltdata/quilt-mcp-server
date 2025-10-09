# MCP Proxy Implementation - Codex Summary

**Location:** `/Users/simonkohnstamm/Documents/Quilt/quilt-mcp-server`  
**Task:** Enable remote MCP server support via proxy architecture  
**Priority:** HIGH  
**Estimated Time:** 1-2 days for MVP

---

## 📋 What to Tell Codex

```
I need you to implement an MCP proxy layer in the Quilt MCP server that allows it 
to route tool calls to remote MCP servers (specifically Benchling and BioContextAI) 
while maintaining a single connection from the frontend.

Please read these implementation guides:
1. PROXY_IMPLEMENTATION_INSTRUCTIONS.md - Full detailed instructions
2. PROXY_QUICK_START.md - Quick reference for MVP implementation

The goal is to enable "namespace routing" where tools prefixed with server names 
(like "benchling__get_entries") get routed to the appropriate remote server.

Start with Benchling only (MVP) since it's on the same domain and has no CORS issues.
```

---

## 📍 Key Files to Read First

1. **PROXY_IMPLEMENTATION_INSTRUCTIONS.md**
   - Complete implementation guide
   - All requirements and details
   - Testing procedures
   - Deployment steps

2. **PROXY_QUICK_START.md**
   - Simplified 3-step approach
   - Code examples
   - Quick testing commands

3. **src/main.py**
   - Entry point for server
   - Understand server structure

4. **pyproject.toml**
   - Dependencies (httpx already available)
   - Current version: 0.6.72

---

## 🎯 Success Criteria

Implementation is complete when:

1. ✅ `tools/list` returns Benchling tools with `benchling__` prefix
2. ✅ Can call `benchling__get_projects` and get results
3. ✅ Can call `benchling__get_entries` and get results
4. ✅ Native Quilt tools still work (no regression)
5. ✅ Error messages are clear and helpful
6. ✅ Code is tested locally before deployment

---

## 🚀 Deployment Checklist

After implementation:

- [ ] All tests pass
- [ ] Manual testing confirms functionality
- [ ] Version bumped to 0.6.73 in pyproject.toml
- [ ] Docker image built
- [ ] Image pushed to ECR
- [ ] ECS task definition updated
- [ ] Service redeployed
- [ ] Frontend tested end-to-end

---

## 💡 Architecture Summary

```
Before:
Frontend → Quilt MCP → Quilt Tools

After:
Frontend → Quilt MCP ┬→ Quilt Tools (native)
                     ├→ Benchling Tools (benchling__*)
                     └→ BioContext Tools (biocontext__*)
```

**Key Concepts:**
- **Namespace prefixing**: `benchling__get_entries`
- **Routing**: Parse prefix, route to correct client
- **Aggregation**: Combine all tools in one list
- **Transparency**: Frontend sees single MCP server

---

## 🔗 Related Documents

- **MCP_PROXY_ARCHITECTURE.md** (in /deployment-notes) - High-level design
- **BENCHLING_MCP_ADDED.md** (in /deployment-notes) - Benchling setup
- **MCP_TOOLS_LISTING_DEPLOYED.md** (in /deployment-notes) - Current status

---

## 📞 Questions?

If Codex has questions about:
- **Server structure**: Check `src/main.py` and look for FastMCP usage
- **Tool handlers**: Search for `@mcp.tool()` decorators
- **Authentication**: Benchling auth is handled by backend (secrets configured)
- **Testing**: Use `scripts/mcp-test.py` for manual testing

---

## ⚡ TL;DR for Codex

**Create 3 files:**
1. `src/quilt_mcp/proxy/client.py` - HTTP client for remote servers
2. `src/quilt_mcp/proxy/router.py` - Routing logic
3. `src/quilt_mcp/proxy/aggregator.py` - Tool aggregation

**Modify 2 handlers:**
1. `tools/list` - Add remote tools with namespace prefix
2. `tools/call` - Route namespaced tools to remote clients

**Test thoroughly:**
1. List tools shows `benchling__*` tools
2. Calling `benchling__get_projects` works
3. Native tools still work

**Deploy:**
1. Bump version to 0.6.73
2. Build, push, deploy to ECS

That's it! 🎉

