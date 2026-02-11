# A21: Platform Backend as Default for uvx

## Overview

Enable explicit backend selection via CLI flag for `uvx quilt-mcp` and change the default backend from `quilt3` to `platform`.

## Background

### Current Behavior

- `uvx quilt-mcp` runs with `quilt3` backend by default
- Backend selection is controlled by `QUILT_MULTIUSER_MODE` environment variable:
  - `QUILT_MULTIUSER_MODE=true` → platform backend ("graphql")
  - `QUILT_MULTIUSER_MODE=false` (default) → quilt3 backend
- Platform backend requires JWT authentication (via `JWTDiscovery.discover_or_raise()`)

### Problems

1. **No explicit CLI control**: Users must set environment variables to choose backend
2. **Wrong default**: `quilt3` is local-dev focused; `platform` is the production-ready option
3. **Unclear auth requirements**: Users may not realize platform backend needs authentication

## Goals

1. Add `--backend [quilt3|platform]` CLI flag to `uvx quilt-mcp`
2. Change default backend from `quilt3` to `platform`
3. Ensure platform backend properly gates with existing auth warning mechanisms
4. Maintain backward compatibility for existing deployments using `QUILT_MULTIUSER_MODE`

## Design

### 1. CLI Flag Implementation

#### Location

- File: `src/quilt_mcp/main.py`
- Function: `main()` argument parser

#### Flag Specification

```
--backend [quilt3|platform]
  Select backend implementation
  - quilt3: Local development backend (quilt3 library + local session)
  - platform: Production backend (GraphQL API + JWT auth)
  Default: platform
```

#### Precedence Rules

Backend selection follows this priority order (highest to lowest):

1. `--backend` CLI flag (explicit user choice)
2. `QUILT_MULTIUSER_MODE` environment variable (legacy support)
3. Default: `platform`

### 2. Configuration Changes

#### ModeConfig Class

File: `src/quilt_mcp/config.py`

**Current state:**

- `backend_type` property returns "graphql" if multiuser, "quilt3" otherwise
- Determined solely by `QUILT_MULTIUSER_MODE` env var

**Required changes:**

- Accept optional backend parameter in `__init__()`
- Store explicit backend choice if provided
- Update `backend_type` property to return normalized backend name:
  - "platform" → internal "graphql"
  - "quilt3" → internal "quilt3"
- Preserve existing `QUILT_MULTIUSER_MODE` behavior for backward compatibility

#### Backend Normalization

- CLI/user-facing name: `platform`
- Internal backend type: `graphql` (as used throughout codebase)
- CLI/user-facing name: `quilt3`
- Internal backend type: `quilt3` (unchanged)

### 3. Auth Gating for Platform Backend

#### Existing Auth Infrastructure

The codebase already has comprehensive auth handling:

1. **JWT Discovery** (`src/quilt_mcp/auth/jwt_discovery.py`)
   - `JWTDiscovery.discover_or_raise()`: Raises `AuthenticationError` with helpful message
   - Priority: runtime context → env secret → quilt3 session → auto-generation

2. **Platform Backend** (`src/quilt_mcp/backends/platform_backend.py`)
   - Constructor calls `_load_access_token()` → `JWTDiscovery.discover_or_raise()`
   - Already raises `AuthenticationError` if JWT not found or endpoints missing

3. **Auth Helpers** (`src/quilt_mcp/tools/auth_helpers.py`)
   - `check_s3_authorization()`: S3 operations
   - `check_package_authorization()`: Package operations
   - Both return error responses for auth failures

#### Required Changes

**None required for auth gating** - the existing mechanisms already provide:

- Early validation at backend initialization
- Clear error messages with troubleshooting steps
- Graceful fallback behavior

**Validation needed:**

- Ensure error messages are still user-friendly with new default
- Verify startup error handling displays JWT requirements clearly
- Test that `FASTMCP_DEBUG=1` output is helpful for auth debugging

### 4. User Experience

#### Success Cases

**Case 1: User with quilt3 login (typical)**

```bash
$ quilt3 login
$ uvx quilt-mcp
# ✓ Works: JWT discovered from quilt3 session → platform backend initialized
```

**Case 2: User with MCP_JWT_SECRET (production)**

```bash
$ export MCP_JWT_SECRET="..."
$ uvx quilt-mcp
# ✓ Works: JWT discovered from env → platform backend initialized
```

**Case 3: User wants quilt3 backend**

```bash
$ uvx quilt-mcp --backend quilt3
# ✓ Works: Explicit quilt3 selection → no JWT required
```

#### Error Cases

**Case 4: User has no authentication**

```bash
$ uvx quilt-mcp
# ✗ Error: JWT token not found. Options:
#   1. Run 'quilt3 login' to authenticate
#   2. Set MCP_JWT_SECRET environment variable
#   3. For development: set QUILT_ALLOW_TEST_JWT=true
```

**Case 5: Missing catalog endpoints**

```bash
$ uvx quilt-mcp
# ✗ Error: Platform backend requires QUILT_CATALOG_URL and QUILT_REGISTRY_URL
```

### 5. Backward Compatibility

#### Legacy Environment Variable Support

Existing deployments using `QUILT_MULTIUSER_MODE` continue to work:

```bash
# Old way (still supported)
$ QUILT_MULTIUSER_MODE=true uvx quilt-mcp
# → platform backend

$ QUILT_MULTIUSER_MODE=false uvx quilt-mcp
# → quilt3 backend

# New way (preferred)
$ uvx quilt-mcp --backend platform
$ uvx quilt-mcp --backend quilt3
```

#### Migration Path

- Phase 1: Add `--backend` flag with `platform` default (this spec)
- Phase 2: Deprecate `QUILT_MULTIUSER_MODE` in documentation (future)
- Phase 3: Remove `QUILT_MULTIUSER_MODE` support (future major version)

### 6. Documentation Updates

Required updates to README.md and docs:

1. Document `--backend` flag with examples
2. Update quickstart to mention authentication requirement
3. Add troubleshooting section for JWT errors
4. Document migration from `QUILT_MULTIUSER_MODE` to `--backend`
5. Update "Local Development" section to show `--backend quilt3`

## Implementation Tasks

### Task 1: Add CLI flag parsing

**File:** `src/quilt_mcp/main.py`

1. Add `--backend` argument to argparse parser
   - Type: `choices=["quilt3", "platform"]`
   - Default: `"platform"`
   - Help text explaining both backends
2. Parse argument before config initialization
3. Pass backend selection to config system

### Task 2: Update ModeConfig

**File:** `src/quilt_mcp/config.py`

1. Add `backend_override: Optional[str]` parameter to `__init__()`
2. Store backend override in instance variable
3. Update `backend_type` property logic:
   - If override exists: return normalized backend type
   - Else: use existing `QUILT_MULTIUSER_MODE` logic
4. Add backend normalization helper:
   - "platform" → "graphql"
   - "quilt3" → "quilt3"
5. Update validation to check backend-specific requirements

### Task 3: Wire CLI flag to config

**File:** `src/quilt_mcp/main.py`

1. Pass `args.backend` to `get_mode_config()` or config initialization
2. Ensure precedence: CLI flag > env var > default
3. Update startup logging to show selected backend
4. Update error messages to mention `--backend` flag

### Task 4: Update startup diagnostics

**File:** `src/quilt_mcp/main.py`

1. Update `print_startup_error()` for auth failures
   - Mention `--backend quilt3` as fallback option
   - Show current backend in error context
2. Enhance "Configuration Error" troubleshooting
   - Add backend-specific guidance
3. Update startup banner logging
   - Show selected backend source (CLI vs env vs default)

### Task 5: Add unit tests

**File:** `tests/unit/test_config.py` (or new file)

1. Test CLI flag precedence over environment variable
2. Test default backend is "platform"
3. Test backend normalization (platform → graphql)
4. Test backward compatibility with `QUILT_MULTIUSER_MODE`
5. Test validation errors for platform backend without config

### Task 6: Add integration tests

**Files:** `tests/func/` or `tests/e2e/`

1. Test startup with `--backend platform` and valid JWT
2. Test startup with `--backend quilt3` (no JWT needed)
3. Test startup with `--backend platform` and missing JWT (error)
4. Test backward compat: `QUILT_MULTIUSER_MODE=true` works
5. Test precedence: `--backend` overrides `QUILT_MULTIUSER_MODE`

### Task 7: Update documentation

**Files:** `README.md`, `docs/` (if exists)

1. Add "Backend Selection" section to README
2. Update quickstart with authentication note
3. Add authentication troubleshooting guide
4. Document `--backend` flag in CLI reference
5. Add migration guide from `QUILT_MULTIUSER_MODE`
6. Update all examples to use new default

### Task 8: Update test fixtures

**Files:** Various test files

1. Review all test setup code using `QUILT_MULTIUSER_MODE`
2. Update to use explicit config or CLI flag where appropriate
3. Ensure tests don't break with new default
4. Add tests for both backend modes where relevant

## Testing Strategy

### Unit Tests

- Config parsing and backend selection logic
- Precedence rules (CLI > env > default)
- Backend normalization
- Validation errors

### Functional Tests

- Startup with different backend selections
- Auth error handling
- Environment variable backward compatibility
- Precedence verification

### Integration Tests

- Full startup flow with platform backend + JWT
- Full startup flow with quilt3 backend
- Error messages for missing auth
- Config validation at startup

### Manual Testing

```bash
# Test 1: Default behavior (should require auth)
uvx quilt-mcp

# Test 2: Explicit platform (should require auth)
uvx quilt-mcp --backend platform

# Test 3: Explicit quilt3 (should work without auth)
uvx quilt-mcp --backend quilt3

# Test 4: With quilt3 login (should work)
quilt3 login
uvx quilt-mcp

# Test 5: Backward compat (should still work)
QUILT_MULTIUSER_MODE=true uvx quilt-mcp
QUILT_MULTIUSER_MODE=false uvx quilt-mcp

# Test 6: Precedence (CLI should win)
QUILT_MULTIUSER_MODE=false uvx quilt-mcp --backend platform
```

## Security Considerations

1. **JWT Exposure**: No change to existing JWT handling
2. **Default Auth**: Making platform default means users must authenticate by default (more secure)
3. **Backward Compat**: Legacy env var support doesn't introduce new security issues
4. **Error Messages**: Ensure auth errors don't leak sensitive token information

## Performance Considerations

- No performance impact: backend selection happens once at startup
- Config validation is already early in startup flow

## Alternatives Considered

### Alternative 1: Keep quilt3 as default

**Rejected:** quilt3 backend is local-dev focused; platform is production-ready

### Alternative 2: Require explicit backend selection (no default)

**Rejected:** Poor UX; most users want platform backend

### Alternative 3: Auto-detect backend based on environment

**Rejected:** Too magical; explicit selection is clearer

### Alternative 4: Rename backends in CLI

**Rejected:** Internal "graphql" name should stay internal; "platform" is clearer to users

## Future Work

1. Deprecate `QUILT_MULTIUSER_MODE` environment variable
2. Add `--backend auto` to auto-detect based on available auth
3. Consider `~/.quilt/config` file for persistent backend preference
4. Add backend selection to Claude Desktop MCP settings UI

## References

- Current implementation: `src/quilt_mcp/main.py`
- Config management: `src/quilt_mcp/config.py`
- Auth discovery: `src/quilt_mcp/auth/jwt_discovery.py`
- Platform backend: `src/quilt_mcp/backends/platform_backend.py`
