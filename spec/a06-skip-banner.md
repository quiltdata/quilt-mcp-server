# ADR a06: Skip Banner CLI Flag

## Status

Accepted

## Context

When running multiple MCP servers together (e.g., Benchling MCP + Quilt MCP in a Pydantic AI agent), the FastMCP library's ASCII art banner written to stdout during initialization breaks the JSON-RPC protocol handshake over stdio transport. This causes `BrokenResourceError` in clients attempting to communicate with the server.

MCP servers using stdio transport communicate via JSON-RPC over stdin/stdout. Any non-JSON output (such as a startup banner) corrupts the protocol, causing initialization failures.

The FastMCP library's `mcp.run()` method accepts a `show_banner` parameter that defaults to `True`. While this is appropriate for single-server development scenarios, it becomes problematic in multi-server production deployments.

## Decision

We will add a `--skip-banner` CLI flag and `MCP_SKIP_BANNER` environment variable to allow users to disable the banner when needed, while maintaining the default behavior of showing the banner for backward compatibility.

### Design Principles

1. **Consistent Terminology**: Use `skip_banner` throughout the codebase (CLI, env var, function parameters)
2. **Safe Default**: Default to `skip_banner=False` (show banner) to maintain existing behavior
3. **Single Conversion Point**: Convert `skip_banner` to `show_banner` only at the FastMCP API boundary
4. **User Control**: Support both CLI flag and environment variable with CLI taking precedence

### Implementation

#### Terminology Mapping

| Layer | Term | Type | Default | Purpose |
|-------|------|------|---------|---------|
| CLI flag | `--skip-banner` | boolean flag | False (not set) | User-facing control |
| Environment | `MCP_SKIP_BANNER` | string "true"/"false" | "false" | Configuration control |
| Internal code | `skip_banner` | bool | False | Python parameter |
| FastMCP API | `show_banner` | bool | True | Library API call |

#### Precedence Rules

1. CLI flag `--skip-banner` (if set) → `skip_banner=True`
2. Else: `MCP_SKIP_BANNER` env var (if set and "true") → `skip_banner=True`
3. Else: Default → `skip_banner=False`

#### Code Changes

1. **main.py**: Add argparse with `--skip-banner` flag, read `MCP_SKIP_BANNER` env var, pass `skip_banner` to `run_server()`
2. **utils.py**: Update `run_server(skip_banner: bool = False)` signature, convert to `show_banner=not skip_banner` when calling `mcp.run()`

### Usage Examples

```bash
# Default: show banner (existing behavior)
uvx quilt-mcp

# Skip banner via CLI flag (multi-server scenario)
uvx quilt-mcp --skip-banner

# Skip banner via environment variable
MCP_SKIP_BANNER=true uvx quilt-mcp

# In MCP client configuration (Claude Desktop, Pydantic AI)
{
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["quilt-mcp", "--skip-banner"]
    }
  }
}
```

## Consequences

### Positive

- **Fixes multi-server compatibility**: Resolves `BrokenResourceError` when using multiple MCP servers
- **Backward compatible**: Default behavior unchanged (banner shows)
- **Consistent terminology**: Single term (`skip_banner`) throughout codebase
- **Flexible control**: Users can choose CLI flag or environment variable
- **Clean design**: Single conversion point to FastMCP's `show_banner` API

### Negative

- **Additional complexity**: Adds CLI argument parsing to previously simple entry point
- **Testing surface**: Requires testing CLI flag, env var, and precedence rules
- **Documentation**: Needs updates to README and deployment guides

### Neutral

- **Alternative naming**: Could have used `--hide-banner`, `--no-banner`, or `--quiet`, but `--skip-banner` provides clearest intent with consistent positive action verb
- **Environment variable**: `MCP_SKIP_BANNER` aligns with existing `MCP_*` convention (e.g., `MCP_SERVER_NAME`)

## Implementation Notes

### Affected Files

- `spec/a06-skip-banner.md` (this ADR)
- `src/quilt_mcp/main.py` (add argparse and flag handling)
- `src/quilt_mcp/utils.py` (update `run_server()` signature)
- `README.md` (document new flag)

### Testing Requirements

- Default behavior: banner displays
- CLI flag: `--skip-banner` suppresses banner
- Environment variable: `MCP_SKIP_BANNER=true` suppresses banner
- Precedence: CLI flag overrides environment variable
- Both transports: stdio and SSE/HTTP modes
- Integration: Test with actual MCP client (Claude Desktop or Pydantic AI)

## References

- Issue: User report of `BrokenResourceError` in Pydantic AI multi-server setup
- FastMCP SDK: `mcp.run(show_banner: bool = True)` API
- MCP Protocol: stdio transport uses stdin/stdout for JSON-RPC
- Related: [FastMCP Server API Documentation](https://github.com/jlowin/fastmcp)

## Date

2025-11-10
