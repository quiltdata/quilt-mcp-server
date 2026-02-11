# Configuration System Overview

## Update (Deployment Mode)

Primary configuration now uses `deployment_mode` (`--deployment` / `QUILT_DEPLOYMENT`) with presets:
- `remote` => platform + http + multiuser
- `local` => platform + stdio + multiuser (default)
- `legacy` => quilt3 + stdio + single-user

Precedence is:
1. `--deployment`
2. `QUILT_DEPLOYMENT`
3. explicit overrides (`--backend`, `FASTMCP_TRANSPORT`)
4. `QUILT_MULTIUSER_MODE` (legacy)
5. default `local`

## Quick Reference: Defaults

| Parameter | Default Value | Set In |
| --------- | ------------- | ------ |
| **Backend** | `platform` | [config.py](../../src/quilt_mcp/config.py) `_select_backend()` (line 82) |
| **Transport** | `stdio` (always) | [config.py](../../src/quilt_mcp/config.py) `default_transport` (line 147), overridden by `FASTMCP_TRANSPORT` env var |
| **Multiuser** | Derived from backend: `True` (platform) / `False` (quilt3) | [config.py](../../src/quilt_mcp/config.py) `is_multiuser` property (line 101) |

## Docker vs CLI Deployments

**Docker containers and direct CLI invocations use identical configuration logic.** Both deployment methods:

- Use the same `uvx quilt-mcp` command
- Read from the same configuration sources (CLI flags, environment variables, defaults)
- Apply the same precedence rules
- Support the same three standard configurations (Remote, Local, Legacy)

The **only difference** is how environment variables are provided:

- **Docker:** `docker run -e QUILT_CATALOG_URL=...`
- **CLI:** `export QUILT_CATALOG_URL=...` or inline `QUILT_CATALOG_URL=... uvx quilt-mcp`

All configuration behavior documented below applies equally to both deployment methods.

---

## Deployment Parameters

The quilt-mcp server has three key deployment parameters:

### 1. Backend (`backend`)

**What it controls:** Which backend implementation to use

**Values:**

- `quilt3` - Local development backend (uses quilt3 Python library + local AWS session)
- `platform` - Production backend (uses GraphQL API + JWT authentication)

**How it's set (precedence order):**

1. `--backend` CLI flag (highest priority)

   ```bash
   uvx quilt-mcp --backend platform
   uvx quilt-mcp --backend quilt3
   ```

2. `QUILT_MULTIUSER_MODE` environment variable (legacy, backward compatibility)

   ```bash
   QUILT_MULTIUSER_MODE=true   # → platform backend
   QUILT_MULTIUSER_MODE=false  # → quilt3 backend
   ```

3. **Default: `platform`** (as of A21 spec implementation)

**Where it's implemented:**

- CLI parsing: [src/quilt_mcp/main.py](../../src/quilt_mcp/main.py) - `argparse` setup
- Config logic: [src/quilt_mcp/config.py](../../src/quilt_mcp/config.py) - `ModeConfig._select_backend()`
- Backend selection: `ModeConfig.backend_type` property (returns internal "quilt3" or "graphql")

### 2. Transport (`transport`)

**What it controls:** Communication protocol between client and server

**Values:**

- `stdio` - Standard input/output (for IDE integrations, single process)
- `http` - HTTP server (for multi-client deployments, container environments)

**How it's set (precedence order):**

1. `FASTMCP_TRANSPORT` environment variable (explicit override)

   ```bash
   FASTMCP_TRANSPORT=http   # Force HTTP (e.g., Docker deployments)
   FASTMCP_TRANSPORT=stdio  # Force stdio (default behavior)
   ```

2. **Default: `stdio`** (MCP protocol standard for CLI tools)
   - Docker deployments set `FASTMCP_TRANSPORT=http` explicitly in Dockerfile
   - Local CLI usage gets `stdio` by default

**Where it's implemented:**

- Default determination: [src/quilt_mcp/config.py](../../src/quilt_mcp/config.py) - `ModeConfig.default_transport` property
- Applied to environment: [src/quilt_mcp/main.py](../../src/quilt_mcp/main.py) - `os.environ.setdefault("FASTMCP_TRANSPORT", ...)`
- Used by FastMCP framework: FastMCP reads `FASTMCP_TRANSPORT` to determine protocol

### 3. Multiuser (`multiuser`)

**What it controls:** Whether the deployment supports multiple users (derived, not directly set)

**Values:**

- `True` (multi-user) - Platform backend, JWT authentication required, supports multiple users
- `False` (single-user) - Quilt3 backend, uses local AWS credentials, single user only

**How it's determined:**

- **Derived from backend parameter:**
  - `backend = platform` → `multiuser = True`
  - `backend = quilt3` → `multiuser = False`
- This is a computed property, not a direct parameter

**Where it's implemented:**

- Property: [src/quilt_mcp/config.py](../../src/quilt_mcp/config.py) - `ModeConfig.is_multiuser` property
- Auth requirements: `ModeConfig.requires_jwt` property (True when multiuser)
- Usage: Backend initialization, auth checks, validation logic

---

## Standard Configurations

Three standard deployment configurations combine these parameters:

### Configuration 1: Remote (Production)

**Use case:** Production deployment serving multiple users via HTTP

| Parameter | Value | Source |
| --------- | ----- | ------ |
| `backend` | `platform` | Default or explicit `--backend platform` |
| `transport` | `http` | Docker Dockerfile sets `FASTMCP_TRANSPORT=http` |
| `multiuser` | `True` | Derived from platform backend |

**Example deployment:**

```bash
# Docker container with environment variables (Dockerfile sets FASTMCP_TRANSPORT=http)
export QUILT_CATALOG_URL="https://example.com"
export QUILT_REGISTRY_URL="https://registry.example.com"
export MCP_JWT_SECRET="..."
uvx quilt-mcp  # Uses platform backend (default) + http transport (Docker env)
```

**Characteristics:**

- Requires JWT authentication
- Runs as HTTP server (can handle multiple clients)
- Uses GraphQL API for all operations
- Suitable for container/cloud deployments

### Configuration 2: Local (IDE with Platform)

**Use case:** Local IDE integration using platform backend features

| Parameter | Value | Source |
| --------- | ----- | ------ |
| `backend` | `platform` | Default or explicit `--backend platform` |
| `transport` | `stdio` | Default (MCP protocol standard) |
| `multiuser` | `True` | Derived from platform backend |

**Example deployment:**

```bash
# Claude Desktop config or IDE integration
export QUILT_CATALOG_URL="https://example.com"
export QUILT_REGISTRY_URL="https://registry.example.com"
# JWT discovered from: quilt3 session, MCP_JWT_SECRET, or runtime context
uvx quilt-mcp  # Uses platform backend (default) + stdio transport (default)
```

**Characteristics:**

- Requires JWT authentication (from quilt3 login or env var)
- Uses stdio for single-user IDE integration
- Uses GraphQL API for all operations
- Suitable for IDE plugins (Claude Desktop, VS Code, etc.)

### Configuration 3: Legacy (Local Development)

**Use case:** Legacy local development with quilt3 library

| Parameter | Value | Source |
| --------- | ----- | ------ |
| `backend` | `quilt3` | Explicit `--backend quilt3` |
| `transport` | `stdio` | Default (MCP protocol standard) |
| `multiuser` | `False` | Derived from quilt3 backend |

**Example deployment:**

```bash
# Local development without JWT
uvx quilt-mcp --backend quilt3
# Or legacy environment variable:
# QUILT_MULTIUSER_MODE=false uvx quilt-mcp
```

**Characteristics:**

- No JWT required (uses local AWS credentials)
- Uses stdio for single-user interaction
- Uses quilt3 Python library directly
- Suitable for local development and testing

---

## Configuration Matrix

| Configuration | Backend | Transport | Multiuser | Auth Required | Use Case |
| ------------- | ------- | --------- | --------- | ------------- | -------- |
| **Remote** | platform | http | True | Yes (JWT) | Production HTTP server |
| **Local** | platform | stdio | True | Yes (JWT) | IDE with platform features |
| **Legacy** | quilt3 | stdio | False | No (AWS creds) | Local dev/testing |

---

## Configuration Code Paths

### Backend Selection Flow

```text
CLI arg --backend
    ↓ (if not provided)
Env var QUILT_MULTIUSER_MODE
    ↓ (if not set)
Default: "platform"
    ↓
ModeConfig._normalize_backend()
    ↓
backend_type: "quilt3" | "graphql"
```

**Files involved:**

1. [src/quilt_mcp/main.py](../../src/quilt_mcp/main.py):85-100 - CLI argument parsing
2. [src/quilt_mcp/config.py](../../src/quilt_mcp/config.py):52-63 - `ModeConfig.__init__()`
3. [src/quilt_mcp/config.py](../../src/quilt_mcp/config.py):82-99 - `ModeConfig._select_backend()`
4. [src/quilt_mcp/config.py](../../src/quilt_mcp/config.py):72-80 - `ModeConfig._normalize_backend()`

### Transport Selection Flow

```text
Env var FASTMCP_TRANSPORT
    ↓ (if not set)
mode_config.default_transport
    ↓
"stdio" (always - MCP protocol standard)
    ↓
Set as env default in main.py (setdefault)
    ↓
FastMCP framework reads FASTMCP_TRANSPORT
```

**Files involved:**

1. [src/quilt_mcp/config.py](../../src/quilt_mcp/config.py):147-149 - `ModeConfig.default_transport` property
2. [src/quilt_mcp/main.py](../../src/quilt_mcp/main.py):128-131 - Apply transport default

### Multiuser Derivation Flow

```text
backend_type
    ↓
is_multiuser = (backend_type == "graphql")
    ↓
requires_jwt = is_multiuser
    ↓
Backend validation and auth checks
```

**Files involved:**

1. [src/quilt_mcp/config.py](../../src/quilt_mcp/config.py):101-104 - `ModeConfig.is_multiuser` property
2. [src/quilt_mcp/config.py](../../src/quilt_mcp/config.py):127-129 - `ModeConfig.requires_jwt` property
3. [src/quilt_mcp/config.py](../../src/quilt_mcp/config.py):151-178 - Validation logic

---

## Key Implementation Details

### Backend Type Normalization

User-facing names are normalized to internal types:

| User Input | Internal Type | Backend Implementation |
| ---------- | ------------- | ---------------------- |
| `"platform"` | `"graphql"` | Platform backend with GraphQL API |
| `"quilt3"` | `"quilt3"` | Quilt3 backend with quilt3 library |

This happens in `ModeConfig._normalize_backend()`.

### Default Transport Logic

Transport always defaults to stdio (MCP protocol standard):

```python
@property
def default_transport(self) -> Literal["stdio", "http"]:
    """Default transport protocol for MCP server.

    Returns stdio by default (MCP protocol standard for CLI tools).
    Docker deployments override to http via FASTMCP_TRANSPORT environment variable.
    """
    return "stdio"
```

This default can be overridden by explicitly setting `FASTMCP_TRANSPORT` before calling `uvx quilt-mcp` (which Docker does automatically).

### Configuration Singleton

The `ModeConfig` class is a singleton managed by:

- `get_mode_config(backend_override)` - Get or create singleton
- `reset_mode_config()` - Clear singleton (tests only)
- `create_test_mode_config(multiuser_mode)` - Create test instance without affecting singleton
- `set_test_mode_config(multiuser_mode)` - Set test instance as singleton

---

## Related Specifications

- [01-uvx-backend.md](./01-uvx-backend.md) - Detailed spec for adding `--backend` CLI flag and changing default to platform
