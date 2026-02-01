# Multitenant Mode: The Single Boolean Decision

**Date:** 2026-01-31
**Status:** Architectural Decision - Ready for Implementation
**Supersedes:** Scattered mode detection logic documented in 01-mode-map.md

---

## Executive Summary

**Decision:** Use `QUILT_MULTITENANT_MODE` as the single authoritative boolean that determines deployment mode.

**Rationale:** Multitenant mode **implies** all other mode dimensions. When `true`, the system runs in production/platform configuration (GraphQL + JWT + stateless + multitenant). When `false` (default), the system runs in local development configuration (quilt3 + session/IAM + persistent + single-user).

**Result:** Eliminates 4+ scattered environment variables, provides single source of truth, prevents invalid mode combinations, enables testing production mode locally.

---

## The Single Boolean

### Variable Name

```bash
QUILT_MULTITENANT_MODE
```

**Values:**

- `true` - Production/platform mode
- `false` - Local development mode (default)

**Note:** Variable already exists in codebase at [src/quilt_mcp/context/factory.py:36](../../src/quilt_mcp/context/factory.py#L36)

---

## Mode Definitions

### Mode: `QUILT_MULTITENANT_MODE=false` (Default - Local Development)

**Purpose:** Single developer working locally

**Characteristics:**

- **API Layer:** quilt3 Python library (`Quilt3_Backend`)
- **Authentication:** quilt3 session from `~/.quilt/` OR AWS credentials (AWS_PROFILE)
- **State Management:** Persistent - can read/write local filesystem
- **Tenancy:** Single-user - always uses "default" tenant
- **Deployment:** Typically local machine, but could be containerized for single user

**Typical Usage:**

```bash
# No env vars needed - this is the default
quilt-mcp-server
```

**What Works:**

- Read from `~/.quilt/config.json` and credentials
- Cache files locally
- Use quilt3 library directly
- AWS IAM credential chain (profile, environment, instance role)
- Single user, no tenant isolation needed

### Mode: `QUILT_MULTITENANT_MODE=true` (Production/Platform)

**Purpose:** Multi-user platform deployment OR testing platform mode locally

**Characteristics:**

- **API Layer:** Platform GraphQL API (`Platform_Backend` - currently missing)
- **Authentication:** JWT bearer tokens REQUIRED
- **State Management:** Stateless - read-only filesystem, no persistent state
- **Tenancy:** Multitenant - tenant extracted from JWT claims, isolation enforced
- **Deployment:** Can run anywhere (production cloud OR local Docker for testing)

**Required Configuration:**

```bash
QUILT_MULTITENANT_MODE=true
# JWT secrets must be configured:
MCP_JWT_SECRET=<secret>              # OR
MCP_JWT_SECRET_SSM_PARAMETER=<param> # SSM parameter name
MCP_JWT_ISSUER=<issuer>
MCP_JWT_AUDIENCE=<audience>
# Catalog URL for GraphQL:
QUILT_CATALOG_URL=<url>
```

**What Works:**

- JWT authentication via Authorization: Bearer header
- Tenant isolation via JWT claims
- GraphQL queries to Platform API
- Read-only filesystem (no ~/.quilt/ access)
- No local caching
- Can run in production cloud OR local Docker container (for testing)

**What Does NOT Work:**

- quilt3 library functions (no quilt3 sessions)
- Reading `~/.quilt/` credentials
- Local filesystem caching
- AWS credential chain (uses JWT role assumption instead)

---

## Key Insight: Testable in Any Location

**Critical understanding:** `QUILT_MULTITENANT_MODE=true` defines the **mode**, not the **location**.

```
Production deployment:
  QUILT_MULTITENANT_MODE=true
  Running in: AWS ECS container
  Purpose: Serve production users

Local testing:
  QUILT_MULTITENANT_MODE=true
  Running in: Docker container on laptop
  Purpose: Test production mode locally

Same mode, different locations - behavior is identical
```

This enables:

- Testing production configuration locally before deployment
- Verifying JWT flows work correctly
- Validating stateless behavior in development
- Catching filesystem dependency bugs early

---

## Implied Behaviors Matrix

| Behavior | `MULTITENANT_MODE=false` | `MULTITENANT_MODE=true` |
|----------|-------------------------|-------------------------|
| **Backend Type** | `Quilt3_Backend` | `Platform_Backend` (GraphQL) |
| **JWT Required** | No (optional) | Yes (enforced) |
| **Filesystem State** | Persistent (read/write) | Stateless (read-only) |
| **Tenant Mode** | Single-user ("default") | Multitenant (from JWT claims) |
| **Auth Fallback** | quilt3 session → AWS creds | JWT only, no fallback |
| **HTTP Response** | SSE streams OK | JSON responses preferred |
| **Cache Files** | Allowed | Prohibited |
| **~/.quilt/ Access** | Allowed | Prohibited |
| **GraphQL Usage** | Optional | Required |
| **quilt3 Library** | Primary API | Not used |

---

## Environment Variables: Before and After

### Variables That Are REMOVED

These variables are **REMOVED immediately** - their values are now derived from `QUILT_MULTITENANT_MODE`:

| Variable | Purpose (Before) | Action |
|----------|-----------------|--------|
| `QUILT_MCP_STATELESS_MODE` | Enable stateless HTTP mode | **DELETED** - Derived from `MULTITENANT_MODE` |
| `MCP_REQUIRE_JWT` | Require JWT authentication | **DELETED** - Always true if `MULTITENANT_MODE=true` |
| `QUILT_DISABLE_QUILT3_SESSION` | Disable quilt3 session auth | **DELETED** - Always disabled if `MULTITENANT_MODE=true` |

**Location:** Currently checked in:

- [src/quilt_mcp/utils.py:420](../../src/quilt_mcp/utils.py#L420) - `QUILT_MCP_STATELESS_MODE`
- [src/quilt_mcp/services/auth_service.py:64](../../src/quilt_mcp/services/auth_service.py#L64) - `MCP_REQUIRE_JWT`
- [src/quilt_mcp/services/iam_auth_service.py:29](../../src/quilt_mcp/services/iam_auth_service.py#L29) - `QUILT_DISABLE_QUILT3_SESSION`

### Variables That Remain (Configuration, Not Mode)

These variables **stay** - they're configuration details, not mode selection:

| Variable | Purpose | Used When |
|----------|---------|-----------|
| `QUILT_MULTITENANT_MODE` | **THE MODE BOOLEAN** | Always - single source of truth |
| `MCP_JWT_SECRET` | JWT signing secret | `MULTITENANT_MODE=true` |
| `MCP_JWT_SECRET_SSM_PARAMETER` | JWT secret from SSM | `MULTITENANT_MODE=true` (alternative) |
| `MCP_JWT_ISSUER` | Expected JWT issuer | `MULTITENANT_MODE=true` |
| `MCP_JWT_AUDIENCE` | Expected JWT audience | `MULTITENANT_MODE=true` |
| `MCP_JWT_SESSION_DURATION` | AWS session duration from JWT | `MULTITENANT_MODE=true` |
| `QUILT_CATALOG_URL` | Platform catalog URL | Both modes (different purposes) |
| `AWS_PROFILE` | AWS credential profile | `MULTITENANT_MODE=false` only |
| `AWS_REGION` | AWS region | Both modes |
| `QUILT_TEST_BUCKET` | Test bucket for integration tests | Test environments only |

---

## Required New Abstraction: ModeConfig

### Purpose

Centralize all mode-related decisions in a single abstraction that:

1. Reads `QUILT_MULTITENANT_MODE` once at startup
2. Provides clear properties for all derived behaviors
3. Validates mode configuration is complete
4. Used by all components instead of scattered env var checks

### Location

**New file:** `src/quilt_mcp/config/mode_config.py`

**Rationale:** Keep separate from general config, mode is fundamental architectural concern

### Interface Requirements

The ModeConfig class must provide:

**Core Properties:**

- `is_multitenant: bool` - The source of truth
- `is_local_dev: bool` - Inverse of is_multitenant (convenience)

**Derived Behaviors:**

- `backend_type: str` - Which backend to use ("quilt3" or "graphql")
- `requires_jwt: bool` - Whether JWT is mandatory
- `allows_filesystem_state: bool` - Can read/write persistent state
- `tenant_mode: str` - "single-user" or "multitenant"
- `requires_graphql: bool` - Must use GraphQL API
- `allows_quilt3_library: bool` - Can use quilt3 library functions

**Validation:**

- `validate()` - Check that required config is present for current mode
- `get_validation_errors() -> List[str]` - Return missing configuration

**Usage Pattern:**

```python
# All components should do this:
from quilt_mcp.config.mode_config import get_mode_config

mode = get_mode_config()  # Singleton

if mode.is_multitenant:
    # Use Platform_Backend, require JWT, etc.
else:
    # Use Quilt3_Backend, allow flexible auth, etc.
```

### Validation Requirements

When `MULTITENANT_MODE=true`, must validate at startup:

- JWT secret configured (via `MCP_JWT_SECRET` or `MCP_JWT_SECRET_SSM_PARAMETER`)
- JWT issuer configured (`MCP_JWT_ISSUER`)
- JWT audience configured (`MCP_JWT_AUDIENCE`)
- Catalog URL configured (`QUILT_CATALOG_URL`)

**Fail fast:** If configuration incomplete, raise clear error at server startup before accepting any requests.

---

## Components That Must Change

### 1. QuiltOps Factory - Backend Selection

**File:** [src/quilt_mcp/ops/factory.py](../../src/quilt_mcp/ops/factory.py)

**Current Behavior:**

- Only checks for quilt3 session (broken API)
- No fallback
- No Platform_Backend option

**Required Changes:**

- Query `mode_config.backend_type` instead of detecting auth
- If `backend_type == "quilt3"` → Create `Quilt3_Backend`
- If `backend_type == "graphql"` → Create `Platform_Backend` (must implement)
- Remove `_detect_quilt3_session()` method (wrong abstraction level)

**Decision:** Backend selection is driven by mode, not by detecting what credentials happen to be available.

### 2. Context Factory - Auth Service Selection

**File:** [src/quilt_mcp/context/factory.py](../../src/quilt_mcp/context/factory.py)

**Current Behavior:** (Lines 88-96)

- Checks runtime auth for JWT token
- Checks `get_jwt_mode_enabled()`
- Falls back to IAMAuthService

**Required Changes:**

- Query `mode_config.requires_jwt` instead of `get_jwt_mode_enabled()`
- In multitenant mode: Only create JWTAuthService, no fallback
- In local mode: Check runtime auth, fallback to IAMAuthService

**Lines affected:** 88-96

**Existing multitenant check:** (Lines 36-39)
Already reads `QUILT_MULTITENANT_MODE` - continue using, but also query ModeConfig for consistency

### 3. IAM Auth Service - Session Handling

**File:** [src/quilt_mcp/services/iam_auth_service.py](../../src/quilt_mcp/services/iam_auth_service.py)

**Current Behavior:** (Line 29)

- Checks `QUILT_DISABLE_QUILT3_SESSION` env var
- Conditionally tries quilt3 session

**Required Changes:**

- Query `mode_config.allows_quilt3_library` instead of env var
- In multitenant mode: Never try quilt3 session (always disabled)
- In local mode: Try quilt3 session if available

**Lines affected:** 29-35 (approximately)

**Additional Note:** IAMAuthService should probably NOT be used at all in multitenant mode - only JWTAuthService should be created.

### 4. Auth Service Module - Global JWT Flag

**File:** [src/quilt_mcp/services/auth_service.py](../../src/quilt_mcp/services/auth_service.py)

**Current Behavior:** (Lines 51-65)

- Global `_JWT_MODE_ENABLED` cached flag
- `get_jwt_mode_enabled()` function reads `MCP_REQUIRE_JWT`
- `reset_auth_service()` for tests

**Required Changes:**

- **REMOVE** `get_jwt_mode_enabled()` function - replace all calls with `mode_config.requires_jwt`
- **REMOVE** global `_JWT_MODE_ENABLED` cache
- **REMOVE** `reset_auth_service()` or adapt for ModeConfig reset in tests

**Lines affected:** 51-71

**Impact:** All callers of `get_jwt_mode_enabled()` must change:

- [src/quilt_mcp/context/factory.py:93](../../src/quilt_mcp/context/factory.py#L93)
- [src/quilt_mcp/utils.py:417](../../src/quilt_mcp/utils.py#L417) (approximately)

### 5. HTTP Utils - Stateless HTTP Configuration

**File:** [src/quilt_mcp/utils.py](../../src/quilt_mcp/utils.py)

**Current Behavior:** (Lines 420-425)

- Checks `QUILT_MCP_STATELESS_MODE` env var
- Passes to FastMCP `http_app(stateless_http=..., json_response=...)`

**Required Changes:**

- Query `mode_config.is_multitenant` instead of env var
- Set `stateless_http=mode_config.is_multitenant`
- Set `json_response=mode_config.is_multitenant`

**Lines affected:** 420-425

### 6. JWT Middleware - Enforcement Configuration

**File:** [src/quilt_mcp/middleware/jwt_middleware.py](../../src/quilt_mcp/middleware/jwt_middleware.py)

**Current Behavior:** (Lines 31-42)

- `__init__` accepts `require_jwt: bool` parameter
- If `not self.require_jwt`, skips validation

**Required Changes:**

- When creating middleware, pass `require_jwt=mode_config.requires_jwt`
- In multitenant mode: Always enforce JWT (require_jwt=True)
- In local mode: Do not enforce JWT (require_jwt=False)

**Lines affected:** Instantiation site(s) that create JwtAuthMiddleware

**Where instantiated:** Must search for where JwtAuthMiddleware is instantiated and ensure it queries mode_config

### 7. Runtime Context - Environment Identifier

**File:** [src/quilt_mcp/runtime_context.py](../../src/quilt_mcp/runtime_context.py)

**Current Behavior:** (Line 35)

- Default environment hardcoded as "desktop"
- Can be changed via `set_default_environment()`

**Required Changes:**

- Initialize default based on mode:
  - If `mode_config.is_multitenant` → default="web"
  - If `mode_config.is_local_dev` → default="desktop"

**Lines affected:** 35, 74-81 (set_default_environment function)

**Note:** This is a **minor/cosmetic** change - environment string is used for logging/telemetry, not functional decisions.

### 8. Permission Discovery Service - Boto3 Session Init

**File:** [src/quilt_mcp/services/permission_discovery.py](../../src/quilt_mcp/services/permission_discovery.py)

**Current Behavior:** (Line 81)

- Checks `QUILT_DISABLE_QUILT3_SESSION` when initializing boto3 session
- Lazy-initializes session

**Required Changes:**

- Query `mode_config.allows_quilt3_library` instead of env var
- In multitenant mode: Never use quilt3 session
- In local mode: Allow quilt3 session if available

**Lines affected:** ~81-90 (in `_ensure_session` method)

### 9. Main Server Initialization - Mode Validation

**File:** [src/quilt_mcp/main.py](../../src/quilt_mcp/main.py)

**Current Behavior:**

- Initializes MCP server
- No explicit mode validation at startup

**Required Changes:**

- **Early validation:** Call `mode_config.validate()` at startup
- If validation fails, log clear errors and exit before accepting requests
- Log current mode for visibility:

  ```
  INFO: Starting Quilt MCP Server in MULTITENANT mode
  INFO: - JWT authentication: REQUIRED
  INFO: - Backend: Platform GraphQL
  INFO: - State: Stateless (read-only filesystem)
  ```

**Where:** In `main()` or server initialization, before creating FastMCP app

### 10. Platform Backend Implementation - MISSING

**File:** `src/quilt_mcp/backends/platform_backend.py` (DOES NOT EXIST)

**Required:**

- Implement `Platform_Backend` class that extends `QuiltOps` abstract interface
- Use GraphQL queries to Platform API instead of quilt3 library
- Accept JWT token for authentication
- Implement all abstract methods from [src/quilt_mcp/ops/quilt_ops.py](../../src/quilt_mcp/ops/quilt_ops.py)

**Methods to implement:**

- `search_packages()`
- `get_package_info()`
- `browse_content()`
- `get_entry_info()`
- `create_package()`
- `create_package_revision()`
- All other QuiltOps abstract methods

**Critical:** This is REQUIRED for `MULTITENANT_MODE=true` to work. Currently missing.

**Location decision:** `src/quilt_mcp/backends/platform_backend.py` (new file, parallel to quilt3_backend.py)

---

## Test Configuration Changes

### Unit Tests - Continue Using Local Mode

**File:** [tests/conftest.py](../../tests/conftest.py)

**Current Behavior:** (Line 138)

```python
os.environ["QUILT_DISABLE_QUILT3_SESSION"] = "1"
```

**Required Changes:**

- **REMOVE** this line - no longer needed
- Unit tests run in local mode by default (`MULTITENANT_MODE=false`)
- Tests that need to mock auth can do so via service mocking, not env vars

**Rationale:** Unit tests should test local mode (default). Multitenant mode requires full integration testing.

### Stateless Tests - Explicit Multitenant Mode

**File:** [tests/stateless/conftest.py](../../tests/stateless/conftest.py)

**Current Behavior:**

- Runs Docker container with `--read-only` filesystem
- Various env vars set

**Required Changes:**

- Set `QUILT_MULTITENANT_MODE=true` explicitly
- Configure JWT secrets for testing
- Remove redundant env vars (STATELESS_MODE, REQUIRE_JWT, etc.)
- Ensure Platform_Backend is mocked or configured for tests

### Integration Tests - Test Both Modes

**Required:**

- Test suite for `MULTITENANT_MODE=false` (local dev scenarios)
- Test suite for `MULTITENANT_MODE=true` (platform scenarios)
- Verify mode config prevents invalid operations (e.g., filesystem access in multitenant)

**Files affected:**

- [tests/integration/test_jwt_integration.py](../../tests/integration/test_jwt_integration.py) - Should test multitenant mode
- [tests/integration/test_docker_container.py](../../tests/integration/test_docker_container.py) - Should test multitenant mode
- Most other integration tests - Should test local mode

---

## Implementation: Hard Switch

**This is a HARD switch with NO backward compatibility. No external clients exist.**

### Single Implementation Phase

1. Create `src/quilt_mcp/config/mode_config.py`
2. Implement ModeConfig class that reads `QUILT_MULTITENANT_MODE`
3. Update all components to query ModeConfig
4. **DELETE all code that reads deprecated env vars**
5. Update documentation to only mention `QUILT_MULTITENANT_MODE`

**Result:** Clean codebase with single mode boolean. Breaking changes are acceptable.

---

## Error Messages and User Guidance

### Startup Validation Errors

When `MULTITENANT_MODE=true` but config incomplete:

```
ERROR: Multitenant mode enabled but configuration incomplete.

Missing required configuration:
  - MCP_JWT_SECRET or MCP_JWT_SECRET_SSM_PARAMETER must be set
  - MCP_JWT_ISSUER must be set
  - MCP_JWT_AUDIENCE must be set

For multitenant mode, configure JWT authentication:
  export MCP_JWT_SECRET="your-secret"
  export MCP_JWT_ISSUER="https://your-issuer.com"
  export MCP_JWT_AUDIENCE="your-audience"

Or disable multitenant mode:
  export QUILT_MULTITENANT_MODE=false

Exiting.
```

### Invalid Operation Errors

When operation invalid for current mode:

**In multitenant mode, trying to use quilt3 session:**

```
ERROR: quilt3 session not available in multitenant mode.
Multitenant mode uses JWT authentication with Platform GraphQL API.
This operation requires local development mode (QUILT_MULTITENANT_MODE=false).
```

**In local mode, missing JWT when tool expects it:**

```
WARNING: JWT authentication not configured in local development mode.
This tool works best with authenticated access.
Consider running: quilt3 login
```

---

## Documentation Updates Required

### Files to Update

1. **README.md**
   - Add section on deployment modes
   - Document `QUILT_MULTITENANT_MODE` configuration
   - Update environment variable reference

2. **CLAUDE.md** (Project instructions)
   - Update mode documentation
   - Remove references to deprecated env vars

3. **Docker documentation** (if exists)
   - Update container configuration examples
   - Show multitenant mode setup

4. **Test documentation**
   - Explain how to test multitenant mode locally
   - Document test environment setup

### New Documentation Needed

1. **Deployment Guide**
   - How to deploy in multitenant mode
   - JWT configuration guide
   - Security considerations

2. **Architecture Document**
   - Mode-based component selection
   - Backend selection logic
   - Auth flow diagrams for each mode

---

## No Backward Compatibility

**HARD SWITCH: No external clients exist. Breaking changes are acceptable.**

### Immediate Removal

**These env vars are DELETED immediately:**

- `QUILT_MCP_STATELESS_MODE`
- `MCP_REQUIRE_JWT` (as mode flag)
- `QUILT_DISABLE_QUILT3_SESSION`

**Impact:** None - no external deployments exist.

### Internal Usage Only

Current internal usage is updated as part of this implementation:

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
# All other mode flags deleted
# Keep JWT config vars (secrets, issuer, audience)
```

**Local development:**

```bash
# Nothing needed (false is default)
```

---

## Success Criteria

### Configuration Simplicity

- [ ] Users set **ONE** env var (`QUILT_MULTITENANT_MODE`) to change modes
- [ ] No conflicting env var combinations possible
- [ ] Clear error messages if mode misconfigured

### Code Quality

- [ ] All code reading `QUILT_MCP_STATELESS_MODE` DELETED
- [ ] All code reading `MCP_REQUIRE_JWT` for mode detection DELETED
- [ ] All code reading `QUILT_DISABLE_QUILT3_SESSION` DELETED
- [ ] All mode decisions go through ModeConfig singleton

### Testability

- [ ] Can run multitenant mode in local Docker for testing
- [ ] Tests explicitly set mode they're testing
- [ ] CI tests both modes

### Functionality

- [ ] Local mode works exactly as before (backward compatible)
- [ ] Multitenant mode uses GraphQL (Platform_Backend implemented)
- [ ] Multitenant mode never accesses `~/.quilt/` directory
- [ ] Multitenant mode enforces JWT authentication
- [ ] Clear errors when operations invalid for current mode

---

## Open Questions / Decisions Needed

### 1. Platform_Backend Implementation Scope

**Question:** Should Platform_Backend be implemented as part of this refactor, or separately?

**Options:**

- **A:** Implement Platform_Backend first, then do mode refactor (sequential)
- **B:** Do mode refactor now, stub Platform_Backend, implement GraphQL separately (parallel)
- **C:** Do both together (larger scope)

**Recommendation:** Option B - Mode refactor can proceed with stub Platform_Backend that raises "not implemented" errors. This unblocks the architectural cleanup while GraphQL implementation proceeds in parallel.

### 2. Environment Variable Naming Convention

**Question:** Should we rename `QUILT_MULTITENANT_MODE` for consistency?

**Current:** `QUILT_MULTITENANT_MODE` (already in use)

**Alternatives:**

- `QUILT_MODE=local|multitenant` (enumeration instead of boolean)
- `QUILT_DEPLOYMENT_MODE=local|multitenant` (more explicit)
- Keep `QUILT_MULTITENANT_MODE` (don't break existing users)

**Recommendation:** Keep `QUILT_MULTITENANT_MODE` - it's already in use, changing it would break existing deployments for no functional benefit.

### 3. Test Environment JWT Configuration

**Question:** How should tests configure JWT secrets in multitenant mode?

**Options:**

- **A:** Use test-specific JWT secret (hardcoded or env var)
- **B:** Mock JWT decoder entirely in tests
- **C:** Use SSM parameter even in tests (requires AWS setup)

**Recommendation:** Option A - Tests set `MCP_JWT_SECRET=test-secret` explicitly, providing predictable behavior without AWS dependencies.

### 4. Graceful Fallback in Multitenant Mode

**Question:** Should multitenant mode EVER fall back to non-JWT auth, or always fail hard?

**Current design:** Fail hard - multitenant mode requires JWT, no fallback.

**Alternative:** Allow fallback to IAM auth if JWT validation fails (more permissive).

**Recommendation:** Fail hard - multitenant mode must enforce JWT for security and tenant isolation. Fallback would violate the mode contract.

---

## Summary

**One boolean controls everything:** `QUILT_MULTITENANT_MODE`

**When true:**

- Production/platform mode
- GraphQL + JWT + stateless + multitenant
- Can test locally in Docker

**When false (default):**

- Local development mode
- quilt3 + session/IAM + persistent + single-user
- Works exactly as today

**Changes required:**

1. Create ModeConfig abstraction (new file)
2. Update 8 existing files to query ModeConfig
3. Remove 3 redundant env vars
4. Implement Platform_Backend (stub or full)
5. Update tests to explicitly set mode
6. Validate mode config at startup

**Result:** Single source of truth, clear mode boundaries, testable platform mode locally, no invalid mode combinations.
