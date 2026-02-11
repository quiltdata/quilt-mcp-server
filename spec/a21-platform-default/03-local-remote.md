# Local vs Remote Default Configuration

## Update (Deployment Presets)

This behavior is now represented as deployment presets:
- `--deployment remote` => platform + http
- `--deployment local` => platform + stdio (default)
- `--deployment legacy` => quilt3 + stdio

Docker sets `QUILT_DEPLOYMENT=remote` and continues to set `FASTMCP_TRANSPORT=http` for compatibility.

## Context

After implementing the platform backend as the default ([01-uvx-backend.md](./01-uvx-backend.md)), we identified that the transport default needs adjustment to better serve the two primary deployment contexts:

1. **Docker (Remote)** - Containerized HTTP server for multi-client production deployments
2. **Dev/CLI (Local)** - Terminal-based stdio for IDE integrations and local MCP clients

Currently, both contexts default to `http` transport when using the platform backend, which is incorrect for local CLI usage where `stdio` is the MCP protocol standard.

## Problem Statement

**Current behavior:**

- `uvx quilt-mcp` → platform backend + http transport
- Docker deployment → platform backend + http transport ✓ (correct)
- Local CLI usage → platform backend + http transport ✗ (should be stdio)

**Desired behavior:**

- Docker deployment → platform backend + http transport ✓
- Local CLI usage → platform backend + stdio transport ✓
- Legacy mode (`--backend quilt3`) → quilt3 backend + stdio transport ✓

## Solution: Change Default Transport to Stdio

### Design Decision

**Change the `default_transport` property to always return `stdio`**, letting Docker's explicit `FASTMCP_TRANSPORT=http` environment variable override it.

**Rationale:**

1. **Stdio is the MCP standard** - The Model Context Protocol specifies stdio as the default transport for CLI tools
2. **Docker already overrides** - Dockerfile explicitly sets `FASTMCP_TRANSPORT=http` (line 40)
3. **Precedence system works** - `os.environ.setdefault()` in main.py ensures explicit env vars win
4. **Minimal change** - One line modification to fix the default
5. **Zero breaking changes** - Docker unaffected, CLI users get correct default
6. **Aligns with semantics** - Transport choice is about invocation context (CLI vs container), not backend type

### Alternatives Considered

**Option B: Add --transport CLI flag**

- ❌ More complexity for users
- ❌ Requires remembering flag
- ❌ Not self-documenting

**Option C: Add --mode preset flag** (e.g., `--mode local|remote|legacy`)

- ❌ New abstraction layer
- ❌ Duplicates backend selection
- ❌ Over-engineering

**Option D: Add QUILT_DEPLOYMENT_MODE env var**

- ❌ Another environment variable
- ❌ Not discoverable from CLI
- ❌ Mixes deployment and backend concerns

**Why Option A wins:**

- ✅ Zero new flags or environment variables
- ✅ Follows existing precedence patterns
- ✅ Correct default for most users
- ✅ Explicit override for production deployments

## Implementation

### Core Change

**File:** [src/quilt_mcp/config.py](../../src/quilt_mcp/config.py)

**Before (lines 147-149):**

```python
@property
def default_transport(self) -> Literal["stdio", "http"]:
    """Default transport protocol based on deployment mode."""
    return "http" if self.backend_type == "graphql" else "stdio"
```

**After:**

```python
@property
def default_transport(self) -> Literal["stdio", "http"]:
    """Default transport protocol for MCP server.

    Returns stdio by default (MCP protocol standard for CLI tools).
    Docker deployments override to http via FASTMCP_TRANSPORT environment variable.
    """
    return "stdio"
```

### Transport Precedence System

The transport selection follows this precedence (highest to lowest):

1. **Explicit `FASTMCP_TRANSPORT` environment variable** (set by Docker, user override, or orchestration)
2. **Default from `mode_config.default_transport`** (now always "stdio")

This precedence is implemented in [main.py](../../src/quilt_mcp/main.py) lines 128-131:

```python
# Set transport protocol based on deployment mode
os.environ.setdefault("FASTMCP_TRANSPORT", mode_config.default_transport)
```

The `setdefault()` ensures explicit environment variables always win.

### Docker Configuration

**File:** [Dockerfile](../../Dockerfile)

Docker explicitly sets transport to http (line 40), which overrides the default:

```dockerfile
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    FASTMCP_TRANSPORT=http \
    FASTMCP_HOST=0.0.0.0 \
    FASTMCP_PORT=8000
```

**Result:** Docker deployments continue using http transport unchanged.

## Updated Configuration Matrix

After this change, the three standard configurations work as intended:

| Configuration | Backend | Transport | How Set | Use Case |
| ------------- | ------- | --------- | ------- | -------- |
| **Remote** | platform | http | Docker sets `FASTMCP_TRANSPORT=http` | Production HTTP server |
| **Local** | platform | stdio | Default (no override needed) | IDE with platform features |
| **Legacy** | quilt3 | stdio | `--backend quilt3` | Local dev/testing |

### Usage Examples

**Docker deployment (Remote):**

```bash
# Dockerfile sets FASTMCP_TRANSPORT=http automatically
docker run -e QUILT_CATALOG_URL=https://example.com \
           -e QUILT_REGISTRY_URL=https://registry.example.com \
           quilt-mcp:latest
# Result: platform backend + http transport
```

**Local CLI with Claude Desktop (Local):**

```bash
# No override needed - stdio is now the default
export QUILT_CATALOG_URL="https://example.com"
export QUILT_REGISTRY_URL="https://registry.example.com"
uvx quilt-mcp
# Result: platform backend + stdio transport
```

**Local development with quilt3 (Legacy):**

```bash
uvx quilt-mcp --backend quilt3
# Result: quilt3 backend + stdio transport
```

**Manual http override (if needed):**

```bash
# Explicit override for testing or special cases
FASTMCP_TRANSPORT=http uvx quilt-mcp
# Result: platform backend + http transport
```

## Backward Compatibility

### Impact Analysis

**No breaking changes for:**

- ✅ Docker deployments - Explicit `FASTMCP_TRANSPORT=http` in Dockerfile
- ✅ MCP clients expecting stdio - Now get correct default
- ✅ Legacy mode users - Behavior unchanged
- ✅ Tests - Backend parametrization independent of transport

**Requires migration for:**

- ⚠️ CLI users manually expecting http transport without explicit configuration
  - **Likelihood:** Very low - http transport without containerization is unusual
  - **Mitigation:** Set `FASTMCP_TRANSPORT=http` environment variable
  - **Detection:** Would have required manual `QUILT_CATALOG_URL` + `QUILT_REGISTRY_URL` setup anyway

### Migration Guide

If you were running `uvx quilt-mcp` expecting http transport (without Docker):

**Before:**

```bash
uvx quilt-mcp  # Got http (old default)
```

**After:**

```bash
FASTMCP_TRANSPORT=http uvx quilt-mcp  # Explicit http
# Or add to .env file:
echo "FASTMCP_TRANSPORT=http" >> .env
uvx quilt-mcp
```

## Verification

### Unit Tests

```bash
# Test config defaults
uv run pytest tests/unit/test_config.py::test_default_transport -v

# Expected behavior:
# - ModeConfig.default_transport returns "stdio" for all backends
```

### Integration Tests

```bash
# Test Docker deployment
make docker-build
docker run --rm \
  -e QUILT_CATALOG_URL=test \
  -e QUILT_REGISTRY_URL=test \
  quilt-mcp:latest \
  python -c "import os; assert os.environ['FASTMCP_TRANSPORT'] == 'http'"
# Expected: http (Docker's explicit setting)

# Test CLI default
python -c "from quilt_mcp.config import get_mode_config; \
           assert get_mode_config().default_transport == 'stdio'"
# Expected: stdio

# Test full suite
make test-all
```

### Manual Verification

**Test Local (stdio):**

```bash
# Start server
uvx quilt-mcp

# In another terminal, verify stdio mode
# (should respond to MCP protocol messages on stdin/stdout)
```

**Test Docker (http):**

```bash
# Start container
docker run -d -p 8000:8000 \
  -e QUILT_CATALOG_URL=https://example.com \
  -e QUILT_REGISTRY_URL=https://registry.example.com \
  quilt-mcp:latest

# Verify http endpoint
curl http://localhost:8000/health
# Expected: 200 OK
```

**Test Legacy (quilt3 + stdio):**

```bash
uvx quilt-mcp --backend quilt3
# Should start in stdio mode with quilt3 backend
```

## Documentation Updates

### README.md

Update the quickstart section to clarify transport behavior:

```markdown
### Quick Start

**For local development with Claude Desktop:**

```bash
# Defaults to platform backend with stdio transport (MCP standard)
export QUILT_CATALOG_URL="https://your-catalog.example.com"
export QUILT_REGISTRY_URL="https://registry.example.com"
uvx quilt-mcp
```

**For Docker deployment:**

```bash
# Dockerfile sets http transport automatically
docker run -e QUILT_CATALOG_URL=https://example.com \
           -e QUILT_REGISTRY_URL=https://registry.example.com \
           quilt-mcp:latest
```

**For legacy local mode (no JWT required):**

```bash
uvx quilt-mcp --backend quilt3
```

```

### Configuration Documentation

Update [02-configuration-overview.md](./02-configuration-overview.md) to reflect the new transport default:

**Line 8 (Quick Reference table):**
```markdown
| **Transport** | `stdio` (always) | [config.py](../../src/quilt_mcp/config.py) `default_transport` (line 147), overridden by `FASTMCP_TRANSPORT` env var |
```

**Lines 58-66 (Transport section):**

```markdown
**How it's set (precedence order):**

1. `FASTMCP_TRANSPORT` environment variable (explicit override)

   ```bash
   FASTMCP_TRANSPORT=http   # Force HTTP (e.g., Docker)
   FASTMCP_TRANSPORT=stdio  # Force stdio (default)
   ```

1. **Default: `stdio`** (MCP protocol standard for CLI tools)
   - Docker deployments set `FASTMCP_TRANSPORT=http` explicitly
   - Local CLI usage gets stdio by default

```

## Benefits

1. **MCP Protocol Compliance** - Stdio is the standard transport for MCP servers
2. **Better User Experience** - CLI users get the right default without flags
3. **Clear Separation** - Transport choice is about invocation context, not backend type
4. **Zero Complexity** - No new flags, env vars, or abstractions
5. **Maintainable** - Simple logic, easy to understand and debug
6. **Future-Proof** - Easier to add new transports (sse, websocket) later

## Related Specifications

- [01-uvx-backend.md](./01-uvx-backend.md) - Backend default change to platform
- [02-configuration-overview.md](./02-configuration-overview.md) - Complete configuration system
