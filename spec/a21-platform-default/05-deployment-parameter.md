# Deployment Mode Specification

## Overview

Introduce a `deployment_mode` parameter that **controls** backend, transport, and multiuser mode through high-level modes,
simplifying configuration and improving reporting clarity.

## Problem

Users must understand three interrelated parameters:

- **Backend**: quilt3 vs platform
- **Transport**: stdio vs http
- **Multiuser**: derived from backend

This creates confusion:

- "Should I use `--backend platform` or set `FASTMCP_TRANSPORT=http`?"
- "Which combination is right for my IDE?"
- Configuration reporting shows low-level parameters instead of deployment intent

## Solution: Deployment Parameter

Add a single `--deployment` parameter with three presets that control all configuration:

| Deployment | Backend | Transport | Multiuser | Use Case |
|------------|---------|-----------|-----------|----------|
| **remote** | platform | http | True | Production container (multi-client HTTP server) |
| **local** | platform | stdio | True | IDE integration (Claude Desktop, VS Code) |
| **legacy** | quilt3 | stdio | False | Legacy local dev (quilt3 library + AWS creds) |

## Design Principles

1. **Mode controls parameters** - `deployment_mode` is authoritative, sets backend + transport
2. **Override remains possible** - Explicit backend/transport flags override mode
3. **Clear defaults** - `deployment_mode=local` is default (stdio + platform)
4. **Discoverable** - `--help` shows modes with descriptions
5. **Backward compatible** - Existing flags continue working
6. **Report deployment** - Config exposure shows deployment mode, not just parameters
7. **Docker just works** - Dockerfile sets `QUILT_DEPLOYMENT=remote`, no user config needed

## Configuration Behavior

### Precedence (highest to lowest)

1. **CLI flag** - `--deployment {remote,local,legacy}` (explicit override)
2. **Environment variable** - `QUILT_DEPLOYMENT={remote,local,legacy}` (Docker sets this)
3. **Explicit parameter flags** - `--backend`, `FASTMCP_TRANSPORT` (legacy overrides)
4. **Legacy env var** - `QUILT_MULTIUSER_MODE={true,false}` (backward compatibility)
5. **Default** - `deployment_mode=local` (platform + stdio)

### Example Invocations

```bash
# Local CLI (default - no flags needed)
uvx quilt-mcp                         # → local (platform + stdio)

# Explicit deployment modes
uvx quilt-mcp --deployment remote     # → remote (platform + http)
uvx quilt-mcp --deployment local      # → local (platform + stdio)
uvx quilt-mcp --deployment legacy     # → legacy (quilt3 + stdio)

# Docker: Dockerfile sets env var, just works
docker run quilt-mcp:latest           # → remote (QUILT_DEPLOYMENT=remote in Dockerfile)

# Docker override (if needed)
docker run -e QUILT_DEPLOYMENT=local quilt-mcp:latest  # → local

# Override backend/transport (advanced)
uvx quilt-mcp --deployment remote --backend quilt3     # → quilt3 + http (unusual)
```

## Reporting Integration

### Server Initialization (Layer 1)

**Current:**

```
Name: quilt-mcp-server
Version: 0.5.6 (platform)
```

**Proposed:**

```
Name: quilt-mcp-server
Version: 0.5.6 (local)                # Shows deployment, not backend
Instructions: Local deployment using platform backend...
```

### Configuration Resource (Layer 2)

**Current structure:**

```json
{
  "backend": {"name": "platform", "type": "graphql"},
  "deployment": {"multiuser": true, "transport": "stdio"}
}
```

**Proposed structure:**

```json
{
  "deployment": {
    "mode": "local",                    # NEW: High-level intent
    "backend": "platform",
    "transport": "stdio",
    "multiuser": true
  },
  "capabilities": {...}
}
```

### Tool Output (catalog_info, etc.)

Include deployment context in relevant tool responses:

```json
{
  "deployment_mode": "local",
  "catalog_url": "...",
  ...
}
```

## Implementation Tasks

### Phase 1: Core Parameter (Required)

**File:** `src/quilt_mcp/config.py`

- Add `DeploymentMode` enum: `REMOTE`, `LOCAL`, `LEGACY`
- Add `ModeConfig.deployment_mode` property
- Add `_resolve_deployment()` method: mode → (backend, transport)
- Update `__init__` to accept `deployment_mode` parameter (from CLI flag or env var)
- Read `QUILT_DEPLOYMENT` env var with precedence

**File:** `src/quilt_mcp/main.py`

- Add `--deployment {remote,local,legacy}` CLI argument
- Read `QUILT_DEPLOYMENT` env var as default
- Pass resolved mode to `ModeConfig` initialization
- Update help text with mode descriptions

**File:** `src/quilt_mcp/__init__.py`

- Export `DeploymentMode` enum

### Phase 2: Reporting Integration (Required)

**File:** `src/quilt_mcp/utils/common.py`

- Modify `create_mcp_server()` to show deployment mode in version string
- Update instructions to mention deployment mode

**File:** `src/quilt_mcp/resources/server_config.py` (if implementing 04-mcp-report-config)

- Add `deployment.mode` field to configuration resource
- Include mode description

**File:** `src/quilt_mcp/tools/catalog.py`

- Add `deployment_mode` field to `catalog_info()` response

### Phase 3: Docker & Documentation (Required)

**File:** `Dockerfile`

- Add `ENV QUILT_DEPLOYMENT=remote` (new, explicit)
- Keep `FASTMCP_TRANSPORT=http` for now (backward compat, can remove later)
- Docker deployments automatically use remote mode without user configuration

**File:** `README.md`

- Replace backend flag examples with deployment mode examples
- Show three standard configurations as deployment modes
- Add migration guide for existing users

**Files:** `spec/a21-platform-default/*.md`

- Update 02-configuration-overview.md with deployment_mode parameter
- Update 03-local-remote.md to use deployment mode terminology
- Update 04-mcp-report-config.md to include deployment_mode in reporting

### Phase 4: Testing (Required)

**File:** `tests/unit/test_config.py`

- Test deployment mode resolution (CLI flag, env var, default)
- Test override precedence
- Test default behavior (local)
- Test Docker scenario (QUILT_DEPLOYMENT=remote)

**File:** `tests/e2e/`

- Test each deployment mode end-to-end
- Test mixed override scenarios

## Migration Strategy

### Backward Compatibility

**Existing flags continue working:**

- `--backend quilt3` → deployment_mode=legacy (inferred from backend)
- `QUILT_MULTIUSER_MODE=true` → deployment_mode=local (inferred, deprecated)
- `FASTMCP_TRANSPORT=http` → overrides transport (still works)

**Docker containers:**

- Add `ENV QUILT_DEPLOYMENT=remote` to Dockerfile
- Existing `FASTMCP_TRANSPORT=http` kept for now (can deprecate later)
- Result: Docker automatically uses remote mode, no user config needed

### User Communication

**Migration message (if no deployment flag):**

```
INFO: Using 'local' deployment (platform + stdio).
      For other deployments: --deployment {remote,local,legacy}
      See: github.com/quiltdata/quilt-mcp-server#deployment-modes
```

**Deprecation timeline:**

- **v0.16**: Add `--deployment`, keep all existing flags, infer when possible
- **v0.17**: Deprecate direct use of `--backend` in favor of `--deployment`
- **v0.18**: `--backend` becomes override-only (must use with `--deployment`)

## Benefits

1. **Simpler mental model** - One concept instead of three
2. **Self-documenting** - "remote" vs "local" is clear intent
3. **Better defaults** - `deployment=local` makes sense for CLI tool
4. **Clearer reporting** - Users see "local deployment" not "graphql backend + stdio transport"
5. **Easier onboarding** - New users learn one flag
6. **Docker clarity** - `QUILT_DEPLOYMENT=remote` vs arcane transport variable

## Alternatives Considered

### Alt 1: Keep current parameters, improve docs

❌ Doesn't solve conceptual complexity

### Alt 2: Add `--mode` instead of `--deployment`

❌ "Mode" is ambiguous (debug mode? operation mode?)

### Alt 3: Use `--profile` or `--config`

❌ Implies loading external config file

### Alt 4: Auto-detect from environment

❌ Not explicit, hard to troubleshoot

## Open Questions

1. **How to handle partial overrides?**
   - Example: `--deployment remote --backend quilt3`
   - Proposal: Allow but warn about unusual combinations

2. **Should we infer deployment mode from parameters?**
   - Example: `--backend platform` + `FASTMCP_TRANSPORT=http` → deployment_mode=remote
   - Proposal: Yes for backward compatibility, log inferred mode

3. **Add validation for nonsensical combinations?**
   - Example: Block `--deployment remote --backend quilt3`?
   - Proposal: Allow but log warning (flexibility > strict validation)

---

**Status:** Proposed
**Author:** Claude (Sonnet 4.5)
**Date:** 2026-02-10
**Related:** 01-uvx-backend.md, 02-configuration-overview.md, 03-local-remote.md, 04-mcp-report-config.md
