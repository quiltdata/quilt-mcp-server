# MCP Configuration Exposure

## Overview

This document specifies how the Quilt MCP server exposes its configuration and capabilities to MCP clients, following Model Context Protocol standards and best practices.

## Problem Statement

MCP clients (Claude Desktop, VS Code extensions, etc.) need visibility into:

1. **Server identity**: What server they're connected to and its version
2. **Backend configuration**: Which backend (quilt3 vs platform) is active
3. **Deployment mode**: Single-user vs multi-user operation
4. **Authentication requirements**: Whether JWT is required
5. **Runtime capabilities**: What features are available in the current configuration

Without this visibility, clients cannot:
- Provide context-appropriate suggestions to users
- Debug configuration issues
- Adapt their behavior to server capabilities
- Display meaningful server information in UIs

## MCP Protocol Standards

The Model Context Protocol provides three mechanisms for exposing configuration:

### 1. Server Initialization Metadata (Static)

During the MCP handshake, servers send `ServerInfo` in the `initialize` response:

```typescript
interface ServerInfo {
  name: string;           // Server identifier
  version: string;        // Version string
  protocolVersion: string; // MCP protocol version
}
```

**Use case**: Static information that identifies the server and its capabilities.

**MCP Spec Reference**: [Architecture - Basic Protocol](https://modelcontextprotocol.io/specification/2025-11-25/architecture)

### 2. Resources (Dynamic Data)

MCP Resources expose data that clients can read. Resources can be:
- **Static**: Fixed content defined at server startup
- **Dynamic**: Content computed on-demand

```typescript
interface Resource {
  uri: string;           // Unique identifier (e.g., "config://server")
  name: string;          // Human-readable name
  description?: string;  // Optional description
  mimeType?: string;     // Content type
}
```

**Use case**: Configuration data that clients may need to query, especially if it can change or is complex.

**MCP Spec Reference**: [Server Features - Resources](https://modelcontextprotocol.io/specification/2025-11-25/server)

### 3. Tools (Interactive)

MCP Tools are functions that clients can invoke. Tools are appropriate when:
- The operation is an action (not just data retrieval)
- Parameters are needed
- Side effects occur

**Use case**: Not ideal for pure configuration exposure, but useful for configuration-related actions (e.g., `catalog_configure`).

## Current Implementation

### FastMCP Initialization

**File**: [src/quilt_mcp/utils/common.py:239](../../src/quilt_mcp/utils/common.py#L239)

```python
def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server instance."""
    return FastMCP("quilt-mcp-server")
```

**Status**: Minimal implementation, only provides server name.

### Existing Configuration Tools

**File**: [src/quilt_mcp/tools/catalog.py](../../src/quilt_mcp/tools/catalog.py)

The `catalog_info()` tool already returns catalog-specific configuration:

```python
def catalog_info() -> dict:
    """Retrieve catalog metadata - Quilt authentication introspection workflows"""
    return {
        "catalog_name": "...",
        "is_authenticated": bool,
        "navigator_url": "...",
        "registry_url": "...",
        "region": "...",
        "tabulator_data_catalog": "...",
        "search_backend_status": {...},
        "detection_method": "...",
        "status": "success",
    }
```

**Status**: Well-designed for catalog metadata, but doesn't expose server/backend configuration.

## Proposed Solution

### Approach: Multi-Layered Configuration Exposure

Use all three MCP mechanisms, each for its appropriate purpose:

#### Layer 1: Enhanced Server Initialization (Static Identity)

**Purpose**: Help clients identify the server and its version at connection time.

**Implementation**: Enhance FastMCP initialization with backend info in the version string:

```python
def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server instance."""
    from quilt_mcp import __version__
    from quilt_mcp.config import get_mode_config

    mode_config = get_mode_config()

    # Include backend in version string for client visibility
    version_string = f"{__version__} ({mode_config.backend_name})"

    # Provide clear instructions about server mode
    mode_description = "multi-user" if mode_config.is_multiuser else "single-user"
    instructions = (
        f"Quilt data access server using {mode_config.backend_name} backend "
        f"in {mode_description} mode. "
        f"Provides secure access to Quilt packages, S3 buckets, and data visualization."
    )

    return FastMCP(
        name="quilt-mcp-server",
        version=version_string,
        instructions=instructions,
    )
```

**Benefits**:
- Visible in client UIs (Claude Desktop shows server name/version)
- No client action required (sent during handshake)
- Helps with debugging ("Which backend am I connected to?")

**Example output**:
- Name: `quilt-mcp-server`
- Version: `0.5.6 (platform)`
- Instructions: `Quilt data access server using platform backend in multi-user mode...`

#### Layer 2: Configuration Resource (Dynamic Details)

**Purpose**: Provide detailed, queryable configuration that clients can access on-demand.

**Implementation**: Create a new MCP resource at `config://server`:

**File**: New file `src/quilt_mcp/resources/server_config.py`

```python
"""MCP resource for server configuration exposure."""

from __future__ import annotations

import os
from typing import Any, Dict

from quilt_mcp import __version__
from quilt_mcp.config import get_mode_config


def get_server_config() -> Dict[str, Any]:
    """Get comprehensive server configuration.

    Returns:
        Dictionary containing server configuration including:
        - Backend information (name, type, selection source)
        - Deployment mode (multiuser, JWT requirements)
        - Transport configuration
        - Version information
        - Feature flags
    """
    mode_config = get_mode_config()

    return {
        "version": __version__,
        "backend": {
            "name": mode_config.backend_name,  # "quilt3" or "platform"
            "type": mode_config.backend_type,  # "quilt3" or "graphql"
            "selection_source": mode_config.backend_selection_source,
            "description": _get_backend_description(mode_config.backend_name),
        },
        "deployment": {
            "multiuser": mode_config.is_multiuser,
            "requires_jwt": mode_config.requires_jwt,
            "transport": os.environ.get("FASTMCP_TRANSPORT", mode_config.default_transport),
            "mode": "production" if mode_config.is_multiuser else "development",
        },
        "capabilities": {
            "graphql_api": mode_config.backend_type == "graphql",
            "quilt3_library": mode_config.backend_type == "quilt3",
            "jwt_auth": mode_config.requires_jwt,
            "aws_credentials": not mode_config.requires_jwt,
        },
        "urls": _get_configured_urls(),
    }


def _get_backend_description(backend_name: str) -> str:
    """Get human-readable backend description."""
    descriptions = {
        "platform": "Production backend using GraphQL API with JWT authentication",
        "quilt3": "Local development backend using quilt3 Python library with AWS credentials",
    }
    return descriptions.get(backend_name, "Unknown backend")


def _get_configured_urls() -> Dict[str, str | None]:
    """Get configured catalog/registry URLs if available."""
    return {
        "catalog_url": os.environ.get("QUILT_CATALOG_URL"),
        "registry_url": os.environ.get("QUILT_REGISTRY_URL"),
    }
```

**Registration in server initialization**:

**File**: `src/quilt_mcp/utils/common.py` (modify `run_server` function)

```python
def run_server(skip_banner: bool = False) -> None:
    """Start the MCP server with all registered tools and resources."""
    from quilt_mcp.resources.server_config import get_server_config

    # ... existing code ...

    # Register server configuration resource
    @mcp.resource("config://server")
    def server_config_resource():
        """Server configuration and capabilities.

        Exposes comprehensive server configuration including backend type,
        deployment mode, authentication requirements, and feature capabilities.
        Use this to understand the server's operational context.
        """
        import json
        return json.dumps(get_server_config(), indent=2)

    # ... rest of run_server ...
```

**Benefits**:
- Clients can query configuration when needed
- Provides detailed, structured data
- Easy to extend with new configuration fields
- Follows MCP resource pattern
- Machine-readable (JSON format)

**Example client usage**:
```python
# Client requests config://server resource
response = {
    "version": "0.5.6",
    "backend": {
        "name": "platform",
        "type": "graphql",
        "selection_source": "default",
        "description": "Production backend using GraphQL API with JWT authentication"
    },
    "deployment": {
        "multiuser": true,
        "requires_jwt": true,
        "transport": "stdio",
        "mode": "production"
    },
    "capabilities": {
        "graphql_api": true,
        "quilt3_library": false,
        "jwt_auth": true,
        "aws_credentials": false
    },
    "urls": {
        "catalog_url": "https://example.quiltdata.com",
        "registry_url": "https://registry.example.quiltdata.com"
    }
}
```

#### Layer 3: Keep Existing catalog_info Tool (Catalog-Specific)

**Purpose**: Maintain separation of concerns - catalog information vs server configuration.

**File**: [src/quilt_mcp/tools/catalog.py:365-385](../../src/quilt_mcp/tools/catalog.py#L365-L385)

**Status**: Keep as-is. This tool is well-scoped for catalog/authentication metadata.

**Rationale**:
- `catalog_info()`: Catalog-specific metadata (authentication, URLs, region)
- `config://server`: Server-wide configuration (backend, deployment, capabilities)
- Clear separation makes both more maintainable

## Implementation Plan

### Phase 1: Server Initialization Enhancement (Immediate)

**Files to modify**:
1. [src/quilt_mcp/utils/common.py:237-239](../../src/quilt_mcp/utils/common.py#L237-L239)

**Changes**:
```python
def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server instance."""
    from quilt_mcp import __version__
    from quilt_mcp.config import get_mode_config

    mode_config = get_mode_config()
    version_string = f"{__version__} ({mode_config.backend_name})"
    mode_description = "multi-user" if mode_config.is_multiuser else "single-user"

    return FastMCP(
        name="quilt-mcp-server",
        version=version_string,
        instructions=(
            f"Quilt data access server using {mode_config.backend_name} backend "
            f"in {mode_description} mode. "
            f"Provides secure access to Quilt packages, S3 buckets, and data visualization."
        ),
    )
```

**Testing**:
- Start server and verify initialization output
- Check client UI shows enhanced version string
- Verify instructions appear in client documentation

### Phase 2: Configuration Resource (Follow-up)

**Files to create**:
1. `src/quilt_mcp/resources/server_config.py` (new file, see Layer 2 implementation above)
2. `tests/unit/resources/test_server_config.py` (unit tests)

**Files to modify**:
1. `src/quilt_mcp/utils/common.py` - Register resource in `run_server()`
2. `src/quilt_mcp/__init__.py` - Export if needed

**Testing**:
- Unit test `get_server_config()` with both backend modes
- Integration test resource registration
- E2E test client can fetch `config://server`
- Verify JSON format and field presence

### Phase 3: Documentation (Concurrent)

**Files to update**:
1. `README.md` - Document configuration exposure features
2. `docs/user-guide.md` - Add troubleshooting section using config resource
3. This spec document - Add implementation status section

## Alternatives Considered

### Alternative 1: Add Backend Info to catalog_info Tool

**Approach**: Extend existing `catalog_info()` to include backend configuration.

**Pros**:
- Single source of truth for all configuration
- No new files needed
- Clients already know about catalog_info

**Cons**:
- Mixes concerns (catalog metadata vs server configuration)
- Tool invocation required (not available at connection time)
- Returns dict, not structured Resource
- Harder to maintain as it grows

**Decision**: ❌ **Rejected** - Violates separation of concerns principle.

### Alternative 2: Configuration Tool Instead of Resource

**Approach**: Create `server_config()` tool instead of resource.

**Pros**:
- Consistent with existing tool pattern
- Easy to implement

**Cons**:
- Tools are for actions, not data exposure
- Client must invoke tool (not passive reading)
- Doesn't follow MCP resource pattern for data
- Cannot be cached by clients

**Decision**: ❌ **Rejected** - Resources are more appropriate for static/semi-static data.

### Alternative 3: Environment Variable Inspection

**Approach**: Let clients inspect environment variables directly.

**Pros**:
- No server-side code needed
- Direct access to configuration source

**Cons**:
- Security risk (exposes all env vars)
- Not standardized (clients need custom logic)
- Doesn't follow MCP patterns
- Cannot compute derived values

**Decision**: ❌ **Rejected** - Security and standardization concerns.

## FastMCP Implementation Details

### FastMCP Version: 2.14.4

**Supported Parameters** (as of Feb 2026):

```python
FastMCP(
    name: str = "FastMCP",           # Server identifier
    version: str | None = None,      # Version string (defaults to FastMCP version)
    instructions: str | None = None, # Server description for clients
    website_url: str | None = None,  # URL for more information (v2.13.0+)
    icons: list[Icon] | None = None, # Visual icons for UIs (v2.13.0+)
    # ... other parameters for tools, auth, lifespan, etc.
)
```

**Source**: [FastMCP Server Documentation](https://gofastmcp.com/servers/server)

### Icon Support (Future Enhancement)

FastMCP 2.13.0+ supports icons for visual identification:

```python
from fastmcp import Icon

icons = [
    Icon(
        uri="https://quiltdata.com/icon.png",
        mimeType="image/png",
    )
]

FastMCP(name="quilt-mcp-server", icons=icons)
```

**Recommendation**: Consider adding Quilt logo icons in a future enhancement.

## References

### MCP Specification
- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Architecture](https://modelcontextprotocol.io/specification/2025-11-25/architecture)
- [MCP Server Features](https://modelcontextprotocol.io/specification/2025-11-25/server)

### FastMCP Documentation
- [FastMCP Server Documentation](https://gofastmcp.com/servers/server)
- [FastMCP GitHub Repository](https://github.com/jlowin/fastmcp)
- [Building MCP Server with FastMCP Tutorial](https://www.datacamp.com/tutorial/building-mcp-server-client-fastmcp)

### Related Specifications
- [01-uvx-backend.md](./01-uvx-backend.md) - Backend selection and CLI flags
- [02-configuration-overview.md](./02-configuration-overview.md) - Configuration system overview
- [03-local-remote.md](./03-local-remote.md) - Local vs remote deployment modes

## Implementation Status

- [x] Research MCP configuration exposure mechanisms
- [x] Document proposed solution
- [ ] Phase 1: Enhance server initialization (immediate)
- [ ] Phase 2: Implement configuration resource (follow-up)
- [ ] Phase 3: Update documentation (concurrent)
- [ ] Add unit tests for server configuration
- [ ] Add E2E tests for resource access
- [ ] Update user guide with troubleshooting section

## Questions for Review

1. Should we include environment variable values in the resource, or just indicate whether they're set?
   - **Security consideration**: Full URLs might contain sensitive info
   - **Debugging value**: Knowing the actual URLs helps troubleshooting

2. Should the resource be dynamic (computed on each request) or static (computed at startup)?
   - **Current proposal**: Dynamic (allows detecting config changes without restart)
   - **Performance**: Negligible overhead for configuration lookup

3. Should we add a `server_capabilities()` tool for interactive capability checking?
   - **Example**: "Does this server support GraphQL queries?"
   - **Current proposal**: No - capabilities are static and better exposed via resource

4. Should we add website_url and icons to FastMCP initialization?
   - **website_url**: Could point to quilt-mcp-server GitHub or docs
   - **icons**: Would need Quilt logo assets

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-10 | Use multi-layered approach (initialization + resource) | Follows MCP best practices; separates static identity from dynamic details |
| 2026-02-10 | Keep catalog_info separate from server config | Maintains separation of concerns; catalog metadata ≠ server configuration |
| 2026-02-10 | Use Resource pattern instead of Tool for config | Resources are designed for data exposure; tools are for actions |
| 2026-02-10 | Include backend in version string | High visibility in client UIs; helps with support/debugging |

---

**Author**: Claude (Sonnet 4.5)
**Date**: 2026-02-10
**Status**: Proposed
**Related Issues**: A21 Platform Default Implementation
