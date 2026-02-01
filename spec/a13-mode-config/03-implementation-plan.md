# Implementation Plan: Single Boolean Mode Configuration

**Date:** 2026-01-31
**Status:** Implementation Ready
**Implements:** Design from 02-multitenant-mode.md

---

## Goal

Replace scattered mode detection with single `QUILT_MULTITENANT_MODE` boolean. Eliminate 3 redundant environment variables. Provide single source of truth for all mode-related decisions.

---

## Implementation Order

**HARD SWITCH: No backward compatibility, no external clients.**

### Step 1: Create ModeConfig Abstraction

**New file:** `src/quilt_mcp/config/mode_config.py`

**Requirements:**

- Read `QUILT_MULTITENANT_MODE` environment variable
- Singleton pattern with `get_mode_config()` function
- Properties: `is_multitenant`, `is_local_dev`, `backend_type`, `requires_jwt`, `allows_filesystem_state`, `tenant_mode`, `requires_graphql`, `allows_quilt3_library`
- Method: `validate()` - Check required config present for current mode
- Method: `get_validation_errors()` - Return list of missing configuration
- Fail fast on invalid configuration at initialization

### Step 2: Stub Platform_Backend (If Not Implementing Full GraphQL)

**New file:** `src/quilt_mcp/backends/platform_backend.py`

**Requirements:**

- Extend `QuiltOps` abstract interface
- All methods raise `NotImplementedError` with message: "Platform GraphQL backend not yet implemented. Use QUILT_MULTITENANT_MODE=false for local development."
- Allows mode refactor to proceed while GraphQL implementation happens separately

---

### Step 3: Update All Components and DELETE Old Code

#### 3.1. QuiltOps Factory - Backend Selection

**File:** `src/quilt_mcp/ops/factory.py`

**Changes:**

- Import `get_mode_config()`
- Query `mode_config.backend_type` instead of detecting credentials
- If `backend_type == "quilt3"` → Create `Quilt3_Backend`
- If `backend_type == "graphql"` → Create `Platform_Backend`
- Remove `_detect_quilt3_session()` method entirely

#### 3.2. Context Factory - Auth Service Selection

**File:** `src/quilt_mcp/context/factory.py` (lines 88-96)

**Changes:**

- Replace `get_jwt_mode_enabled()` with `mode_config.requires_jwt`
- If `mode_config.is_multitenant`: Only create `JWTAuthService`, no fallback allowed
- If `mode_config.is_local_dev`: Check runtime auth, fallback to `IAMAuthService`

#### 3.3. IAM Auth Service - Session Handling

**File:** `src/quilt_mcp/services/iam_auth_service.py` (line 29)

**Changes:**

- **DELETE** line reading `os.getenv("QUILT_DISABLE_QUILT3_SESSION")`
- Replace with `mode_config.allows_quilt3_library`
- If not allowed, skip quilt3 session entirely

#### 3.4. Auth Service Module - DELETE Global JWT Flag

**File:** `src/quilt_mcp/services/auth_service.py` (lines 51-71)

**Changes:**

- **DELETE** `_JWT_MODE_ENABLED` global variable
- **DELETE** `get_jwt_mode_enabled()` function
- **DELETE** `reset_auth_service()` function

**Update all callers:**

- Find: `get_jwt_mode_enabled()`
- Replace with: `get_mode_config().requires_jwt`
- Known locations: `src/quilt_mcp/context/factory.py:93`, `src/quilt_mcp/utils.py`

#### 3.5. HTTP Utils - DELETE Stateless Env Var

**File:** `src/quilt_mcp/utils.py` (lines 420-425)

**Changes:**

- **DELETE** line reading `os.environ.get("QUILT_MCP_STATELESS_MODE")`
- Replace with `mode_config.is_multitenant`
- Set `stateless_http=mode_config.is_multitenant`
- Set `json_response=mode_config.is_multitenant`

#### 3.6. JWT Middleware - Enforcement Setup

**File:** Search for where `JwtAuthMiddleware` is instantiated

**Changes:**

- Pass `require_jwt=mode_config.requires_jwt` to constructor
- Ensures JWT enforced in multitenant mode, optional in local mode

#### 3.7. Runtime Context - Default Environment

**File:** `src/quilt_mcp/runtime_context.py` (lines 35, 74-81)

**Changes:**

- Initialize `_default_state` based on mode
- If `mode_config.is_multitenant` → `environment="web"`
- If `mode_config.is_local_dev` → `environment="desktop"`

#### 3.8. Permission Discovery - DELETE Session Env Var

**File:** `src/quilt_mcp/services/permission_discovery.py` (line 81)

**Changes:**

- **DELETE** line reading `os.getenv("QUILT_DISABLE_QUILT3_SESSION")`
- Replace with `mode_config.allows_quilt3_library`
- If not allowed, skip quilt3 session in boto3 initialization

#### 3.9. Main Server - Startup Validation

**File:** `src/quilt_mcp/main.py`

**Changes:**

- Early in startup (before accepting requests), call `mode_config.validate()`
- If validation fails, log errors from `get_validation_errors()` and exit
- Log current mode: "Starting Quilt MCP Server in [LOCAL|MULTITENANT] mode"
- Log key config: JWT required, backend type, state management

---

### Step 4: Update Tests

#### 4.1. Unit Tests - Remove Redundant Env Vars

**File:** `tests/conftest.py` (line 138)

**Changes:**

- Remove line: `os.environ["QUILT_DISABLE_QUILT3_SESSION"] = "1"`
- Unit tests run in default local mode
- No explicit mode configuration needed

#### 4.2. Stateless Tests - Explicit Multitenant Mode

**File:** `tests/stateless/conftest.py`

**Changes:**

- Set `QUILT_MULTITENANT_MODE=true` explicitly
- Configure JWT test secrets: `MCP_JWT_SECRET=test-secret`, issuer, audience
- **DELETE** redundant env vars: `QUILT_MCP_STATELESS_MODE`, `MCP_REQUIRE_JWT`, `QUILT_DISABLE_QUILT3_SESSION`

#### 4.3. Fix Test Failures

**After above changes:**

- Run `make test-all`
- Fix any tests broken by mode changes
- Update mocks to work with ModeConfig
- Ensure tests explicitly set mode they're testing

---

### Step 5: Verify Complete Removal

#### 5.1. Verify No Direct Env Var Checks

**Search entire codebase for DELETED env vars:**

```bash
grep -r "QUILT_MCP_STATELESS_MODE" src/quilt_mcp/
# Should return ZERO results (deleted from all source)

grep -r "QUILT_DISABLE_QUILT3_SESSION" src/quilt_mcp/
# Should return ZERO results (deleted from all source)

grep -r "MCP_REQUIRE_JWT" src/quilt_mcp/ | grep -v mode_config
# Should return ZERO results except mode_config.py
```

All mode decisions must go through `get_mode_config()`.

#### 5.2. Documentation Updates

**Files to update:**

- `README.md` - Add deployment mode section
- `CLAUDE.md` - Update mode documentation
- Docker/deployment docs - Update env var examples

---

## File Changes Summary

### New Files (2)

1. `src/quilt_mcp/config/mode_config.py` - ModeConfig abstraction
2. `src/quilt_mcp/backends/platform_backend.py` - Platform backend (stub or full)

### Modified Files (11)

1. `src/quilt_mcp/ops/factory.py` - Backend selection via mode
2. `src/quilt_mcp/context/factory.py` - Auth service selection via mode
3. `src/quilt_mcp/services/iam_auth_service.py` - Remove env var check
4. `src/quilt_mcp/services/auth_service.py` - Remove global JWT flag
5. `src/quilt_mcp/utils.py` - HTTP config via mode
6. `src/quilt_mcp/middleware/jwt_middleware.py` - JWT enforcement setup
7. `src/quilt_mcp/runtime_context.py` - Default environment via mode
8. `src/quilt_mcp/services/permission_discovery.py` - Remove env var check
9. `src/quilt_mcp/main.py` - Add startup validation
10. `tests/conftest.py` - Remove deprecated env var
11. `tests/stateless/conftest.py` - Explicit multitenant config

---

## Verification Steps

### 1. Code Quality Checks

```bash
# No deprecated env vars in source
grep -r "QUILT_MCP_STATELESS_MODE" src/quilt_mcp/
grep -r "QUILT_DISABLE_QUILT3_SESSION" src/quilt_mcp/
# Should find zero or only in ModeConfig
```

### 2. Automated Tests

```bash
make test-all           # All tests pass
make test-integration   # Local mode tests
make test-stateless     # Multitenant mode tests
make lint              # Code quality
```

### 3. Manual Testing - Local Mode

```bash
# Default - should work as before
uv run python -m quilt_mcp
# Test search, browse, package operations
```

### 4. Manual Testing - Multitenant Mode

```bash
# With valid config - should start
export QUILT_MULTITENANT_MODE=true
export MCP_JWT_SECRET=test-secret
export MCP_JWT_ISSUER=test-issuer
export MCP_JWT_AUDIENCE=test-audience
uv run python -m quilt_mcp
```

### 5. Manual Testing - Invalid Config

```bash
# Missing JWT config - should fail with clear error
export QUILT_MULTITENANT_MODE=true
# No JWT secrets set
uv run python -m quilt_mcp
# Expected: Clear validation error, exits before accepting requests
```

---

## Success Criteria

- [ ] ModeConfig created with all required properties
- [ ] All 10 components query ModeConfig instead of env vars
- [ ] ALL code reading `QUILT_MCP_STATELESS_MODE` DELETED from src/
- [ ] ALL code reading `QUILT_DISABLE_QUILT3_SESSION` DELETED from src/
- [ ] Local mode behavior unchanged (backward compatible)
- [ ] Multitenant mode validates config at startup
- [ ] All tests pass (unit, integration, stateless)
- [ ] Clear error messages for invalid configurations
- [ ] Documentation updated with mode configuration

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Breaking internal usage | No external clients; update internal configs as part of implementation |
| Platform_Backend not ready | Create stub with NotImplementedError, refactor proceeds independently |
| Test failures after changes | Update tests as part of implementation |
| Unclear test coverage | Tests must explicitly set mode, verify both modes tested |
| Invalid configuration | Startup validation fails fast with clear errors |

---

## No Migration Required

**HARD SWITCH: No external clients exist.**

### Internal Configuration Update

**Before:**

```bash
QUILT_MCP_STATELESS_MODE=true
MCP_REQUIRE_JWT=true
QUILT_MULTITENANT_MODE=true
QUILT_DISABLE_QUILT3_SESSION=1
```

**After:**

```bash
QUILT_MULTITENANT_MODE=true
# Keep JWT config (secrets, issuer, audience)
# All other mode flags DELETED
```

**Local development:**

```bash
# Nothing needed (false is default)
```

### Deleted Variables

These are DELETED immediately:

- `QUILT_MCP_STATELESS_MODE` - All code reading this DELETED
- `MCP_REQUIRE_JWT` (as mode flag) - All code reading this for mode detection DELETED
- `QUILT_DISABLE_QUILT3_SESSION` - All code reading this DELETED

---

## Decisions

### 1. Platform_Backend Scope

**Decision:** Create stub, implement GraphQL separately (parallel work)

**Rationale:** Stub allows mode refactor to proceed independently

### 2. Test JWT Configuration

**Decision:** Tests use `MCP_JWT_SECRET=test-secret` for predictable behavior without AWS dependencies

### 3. Fallback Behavior in Multitenant

**Decision:** No fallback - multitenant mode requires JWT, fails hard if missing (enforces security boundary)

---

## Estimated Scope

**Files touched:** 13 files (2 new, 11 modified)
**Complexity:** Medium - architectural refactoring with immediate cleanup
**Risk level:** Low - no external clients, breaking changes acceptable
**Testing effort:** Medium - verify both modes work correctly

**Blockers:**

- None if using stub Platform_Backend
- Platform GraphQL implementation if doing full backend

**Dependencies:**

- None - self-contained refactoring

---

## Post-Implementation

### Follow-up Work

1. **Platform_Backend Implementation** (if stubbed)
   - Implement all QuiltOps methods via GraphQL
   - Test with real Platform API
   - Remove NotImplementedError stubs

2. **Enhanced Testing**
   - Add mode-switching integration tests
   - Test invalid mode combinations explicitly
   - Performance benchmarks for both modes

### Monitoring

- Track mode usage in telemetry (local vs multitenant deployments)
- Monitor startup validation failures
- Alert on deprecated env var usage
