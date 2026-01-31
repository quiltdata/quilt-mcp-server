# Mode Configuration Analysis: Mapping the Scattered Detection Logic

**Date:** 2026-01-31
**Status:** Analysis - Identifying the problem before designing the solution

---

## Executive Summary

The Quilt MCP Server has **no single authoritative deployment mode configuration**. Instead, mode-related decisions are scattered across **multiple environment variables** that are checked independently in different parts of the codebase. This creates:

1. **Inconsistent terminology** - "stateless", "JWT mode", "multitenant", "web/desktop"
2. **No single source of truth** - Different subsystems infer mode from different signals
3. **Unclear valid combinations** - Are all combinations of the 4 dimensions valid?
4. **Coordination failures** - Components make independent mode decisions

---

## The Four Dimensions of Deployment Mode

User identified 4 orthogonal dimensions that define deployment behavior:

### 1. API Choice

**What API layer is used for Quilt operations?**

- `quilt3` - Python library (quilt3.Package, quilt3.search, etc.)
- `graphql` - Platform GraphQL API

**Current detection:** Inferred from backend selection (QuiltOps factory)

### 2. AUTH Mechanism

**How does the server authenticate?**

- `session` - quilt3 session from `~/.quilt/` filesystem credentials
- `jwt` - JWT bearer token in Authorization header

**Current detection:** Multiple scattered checks

### 3. STATE Management

**Does the server maintain persistent state?**

- `persistent` - Can read/write to local filesystem (`~/.quilt/`, caches)
- `stateless` - Read-only filesystem, no persistent state

**Current detection:** `QUILT_MCP_STATELESS_MODE` environment variable

### 4. LOCALE

**Where is the server running?**

- `local` - Developer machine, single user
- `remote` - Containerized deployment, potentially multi-user

**Current detection:** No explicit flag, inferred from context

---

## Current Environment Variables (Scattered Indicators)

### Mode-Related Variables

| Variable | Purpose | Values | Where Used | Dimension |
|----------|---------|--------|------------|-----------|
| `QUILT_MCP_STATELESS_MODE` | Enable stateless mode | `true`/`false` (default: `false`) | [utils.py:420](../../src/quilt_mcp/utils.py#L420) | STATE |
| `MCP_REQUIRE_JWT` | Require JWT authentication | `true`/`false` (default: `false`) | [auth_service.py:64](../../src/quilt_mcp/services/auth_service.py#L64) | AUTH |
| `QUILT_MULTITENANT_MODE` | Enable multitenant mode | `true`/`false` (default: `false`) | [context/factory.py:36](../../src/quilt_mcp/context/factory.py#L36) | LOCALE (partially) |
| `QUILT_DISABLE_QUILT3_SESSION` | Disable quilt3 session auth | `1`/`0` (default: enabled) | [iam_auth_service.py:29](../../src/quilt_mcp/services/iam_auth_service.py#L29) | AUTH |
| `QUILT_DISABLE_CACHE` | Disable filesystem caching | `true`/`false` | Tests only | STATE (partially) |
| `MCP_JWT_TOKEN` | JWT token for requests | JWT string | [jwt_integration.py:96](../../tests/integration/test_jwt_integration.py#L96) | AUTH |
| `MCP_JWT_SECRET` | JWT signing secret | Secret string | [jwt_decoder.py:53](../../src/quilt_mcp/services/jwt_decoder.py#L53) | AUTH (config) |
| `MCP_JWT_SECRET_SSM_PARAMETER` | JWT secret from SSM | Parameter name | [jwt_decoder.py:54](../../src/quilt_mcp/services/jwt_decoder.py#L54) | AUTH (config) |

### Runtime Context Variables (Not Env Vars)

| Variable | Purpose | Values | Where Set | Dimension |
|----------|---------|--------|-----------|-----------|
| `RuntimeContextState.environment` | Runtime environment identifier | `"desktop"` (default) or `"web"` | [runtime_context.py:35](../../src/quilt_mcp/runtime_context.py#L35) | LOCALE |
| `RuntimeAuthState.scheme` | Auth scheme for request | `"Bearer"`, etc. | [jwt_middleware.py:80](../../src/quilt_mcp/middleware/jwt_middleware.py#L80) | AUTH |

---

## Decision Points: Where Mode is Inferred

### 1. API Choice (Backend Selection)

**File:** [src/quilt_mcp/ops/factory.py](../../src/quilt_mcp/ops/factory.py)

**Logic:**

```python
# Phase 1: Only quilt3 backend exists
session_info = QuiltOpsFactory._detect_quilt3_session()
if session_info is not None:
    return Quilt3_Backend(session_info)
else:
    raise AuthenticationError()  # NO FALLBACK
```

**Problem:**

- Only one backend (quilt3) implemented
- No GraphQL/Platform backend exists
- No explicit mode selection
- **This doesn't actually choose API - it just has one option**

### 2. AUTH Mechanism (Multiple Scattered Checks)

#### Location A: Context Factory - Service Selection

**File:** [src/quilt_mcp/context/factory.py:88-96](../../src/quilt_mcp/context/factory.py#L88-L96)

**Logic:**

```python
def _create_auth_service(self) -> AuthService:
    runtime_auth = get_runtime_auth()
    if runtime_auth and runtime_auth.access_token:
        return JWTAuthService()  # JWT token present

    if get_jwt_mode_enabled():
        raise ServiceInitializationError("JWT required but missing")

    return IAMAuthService()  # Fallback to IAM/session auth
```

**Decision tree:**

1. Check runtime context for JWT token → Use JWT auth
2. Check `MCP_REQUIRE_JWT` → Fail if required but missing
3. Fallback → IAM auth (which may use quilt3 session or AWS credentials)

#### Location B: IAM Auth Service - Session Detection

**File:** [src/quilt_mcp/services/iam_auth_service.py:29](../../src/quilt_mcp/services/iam_auth_service.py#L29)

**Logic:**

```python
disable_quilt3_session = os.getenv("QUILT_DISABLE_QUILT3_SESSION") == "1"
if not disable_quilt3_session:
    # Try quilt3 session
    if quilt3.logged_in():
        return quilt3_session
# Fallback to AWS credentials
```

**Decision tree:**

1. Check `QUILT_DISABLE_QUILT3_SESSION` → Skip if disabled
2. Check `quilt3.logged_in()` → Use quilt3 session if available
3. Fallback → AWS IAM credentials (AWS_PROFILE or default)

#### Location C: JWT Decoder - Config Validation

**File:** [src/quilt_mcp/services/jwt_decoder.py](../../src/quilt_mcp/services/jwt_decoder.py)

**Logic:**

```python
env_secret = os.getenv("MCP_JWT_SECRET")
ssm_param = os.getenv("MCP_JWT_SECRET_SSM_PARAMETER")
# Use whichever is configured
```

**Determines:** How to validate JWT tokens

#### Location D: JWT Middleware - Request Auth

**File:** [src/quilt_mcp/middleware/jwt_middleware.py:31-42](../../src/quilt_mcp/middleware/jwt_middleware.py#L31-L42)

**Logic:**

```python
def __init__(self, app, *, require_jwt: bool = True):
    self.require_jwt = require_jwt

async def dispatch(self, request, call_next):
    if not self.require_jwt:
        return await call_next(request)
    # Validate JWT...
```

**Decision:** Whether to enforce JWT on HTTP requests

#### Location E: Auth Service Module - Global Flag

**File:** [src/quilt_mcp/services/auth_service.py:60-65](../../src/quilt_mcp/services/auth_service.py#L60-L65)

**Logic:**

```python
_JWT_MODE_ENABLED: Optional[bool] = None

def get_jwt_mode_enabled() -> bool:
    global _JWT_MODE_ENABLED
    if _JWT_MODE_ENABLED is None:
        _JWT_MODE_ENABLED = _parse_bool(os.getenv("MCP_REQUIRE_JWT"), default=False)
    return _JWT_MODE_ENABLED
```

**Decision:** Global flag for whether JWT is required

### 3. STATE Management

#### Location A: Utils - Stateless HTTP Mode

**File:** [src/quilt_mcp/utils.py:420-425](../../src/quilt_mcp/utils.py#L420-L425)

**Logic:**

```python
stateless_mode = os.environ.get("QUILT_MCP_STATELESS_MODE", "false").lower() == "true"

# Use JSON responses in stateless mode for simpler HTTP client integration
app = mcp.http_app(transport=transport, stateless_http=stateless_mode, json_response=stateless_mode)
```

**Effect:**

- Enables stateless HTTP mode in FastMCP
- Uses JSON responses instead of SSE streams
- **But doesn't enforce read-only filesystem or prevent state persistence!**

#### Location B: Tests - Explicit Disabling

**File:** [tests/conftest.py:138](../../tests/conftest.py#L138)

**Logic:**

```python
# Disable quilt3 session (which uses JWT credentials from Quilt catalog login)
# This forces tests to use local AWS credentials (AWS_PROFILE or default)
os.environ["QUILT_DISABLE_QUILT3_SESSION"] = "1"
```

**Effect:** Forces tests into "stateless-like" mode by disabling filesystem credentials

#### Location C: Docker - Infrastructure Level

**Files:**

- [tests/stateless/conftest.py:88](../../tests/stateless/conftest.py#L88)
- [spec/a11-client-testing/12-stateless-authentication-flaw.md](../../spec/a11-client-testing/12-stateless-authentication-flaw.md)

**Logic:**

```python
# Docker run with --read-only filesystem
# tmpfs mounts for /tmp, /app/.local
```

**Effect:** **TRUE stateless mode** - filesystem prevents state persistence

**Critical insight from spec:** "The whole point of stateless is that it CANNOT read the catalog credentials from the local filesystem."

### 4. LOCALE (Local vs Remote)

#### Location A: Runtime Context - Default Environment

**File:** [src/quilt_mcp/runtime_context.py:35](../../src/quilt_mcp/runtime_context.py#L35)

**Logic:**

```python
_default_state = RuntimeContextState(environment="desktop")
```

**Hardcoded default:** Always starts as "desktop" environment

#### Location B: Context Factory - Multitenant Mode

**File:** [src/quilt_mcp/context/factory.py:36-39](../../src/quilt_mcp/context/factory.py#L36-L39)

**Logic:**

```python
env_value = os.getenv("QUILT_MULTITENANT_MODE")
if env_value is None:
    return "single-user"
return "multitenant" if _parse_bool(env_value, default=False) else "single-user"
```

**Effect:** Determines tenant isolation mode

- `single-user` → Always use "default" tenant
- `multitenant` → Extract tenant from JWT claims, require tenant_id

**Problem:** This is a **partial indicator** of LOCALE, but:

- Doesn't distinguish local vs remote explicitly
- Could be remote single-user (one container per user)
- Could be local multitenant (development testing)

---

## The Coordination Problem

### Current State: Independent Decisions

Different components make mode decisions **independently**:

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server Process                        │
│                                                              │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │ QuiltOps Factory │      │  Context Factory │            │
│  │                  │      │                  │            │
│  │ Checks:          │      │ Checks:          │            │
│  │ - quilt3 session?│      │ - JWT token?     │            │
│  └──────────────────┘      │ - MCP_REQUIRE_JWT│            │
│                            └──────────────────┘            │
│                                                              │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  IAM Auth Svc    │      │   HTTP Utils     │            │
│  │                  │      │                  │            │
│  │ Checks:          │      │ Checks:          │            │
│  │ - DISABLE_SESSION│      │ - STATELESS_MODE │            │
│  │ - quilt3.login() │      └──────────────────┘            │
│  └──────────────────┘                                       │
│                                                              │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │ Runtime Context  │      │ JWT Middleware   │            │
│  │                  │      │                  │            │
│  │ Default:         │      │ Checks:          │            │
│  │ environment="d..." │      │ - require_jwt?   │            │
│  └──────────────────┘      └──────────────────┘            │
└─────────────────────────────────────────────────────────────┘
     ↑           ↑           ↑            ↑
     │           │           │            │
   No coordination - each component checks different env vars
```

### What's Missing: Centralized Mode Config

What **should** exist:

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server Process                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              ModeConfig (SINGLE SOURCE OF TRUTH)       │ │
│  │                                                        │ │
│  │  mode: "local" | "stateless"                          │ │
│  │                                                        │ │
│  │  Dimensions:                                          │ │
│  │  - api: "quilt3" | "graphql"                         │ │
│  │  - auth: "session" | "jwt"                           │ │
│  │  - state: "persistent" | "stateless"                 │ │
│  │  - locale: "local" | "remote"                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                          ↓                                   │
│            ALL COMPONENTS QUERY THIS CONFIG                  │
│                          ↓                                   │
│  ┌──────────────────┐   ┌──────────────────┐               │
│  │ QuiltOps Factory │   │ Context Factory  │               │
│  │ mode.api         │   │ mode.auth        │               │
│  └──────────────────┘   └──────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## Valid Mode Combinations

Are all 2^4 = 16 combinations valid? **No.**

User mentioned two **primary deployment modes**:

### Mode A: Local Development

- **API:** quilt3 library
- **AUTH:** quilt3 session (from `~/.quilt/`)
- **STATE:** persistent (can read/write filesystem)
- **LOCALE:** local (single developer machine)

**Environment:**

```bash
# No special env vars needed - all defaults
# Default behavior
```

### Mode B: Stateless Container

- **API:** GraphQL (NOT quilt3 library!)
- **AUTH:** JWT bearer token
- **STATE:** stateless (read-only filesystem)
- **LOCALE:** remote (containerized, potentially multitenant)

**Environment:**

```bash
QUILT_MCP_STATELESS_MODE=true
MCP_REQUIRE_JWT=true
QUILT_MULTITENANT_MODE=true  # if multitenant
QUILT_DISABLE_QUILT3_SESSION=1
# JWT secrets configured
```

### Invalid Combinations

Some combinations don't make sense:

| API | AUTH | STATE | LOCALE | Valid? | Why? |
|-----|------|-------|--------|--------|------|
| quilt3 | session | stateless | - | ❌ | quilt3 session requires persistent `~/.quilt/` |
| graphql | session | - | - | ❌ | GraphQL API requires JWT, not filesystem session |
| - | jwt | persistent | local | ⚠️  | Could work but unusual - JWT typically for remote |
| quilt3 | jwt | persistent | remote | ⚠️  | Could work but mixed - why quilt3 lib with JWT? |

**Key insight:** The dimensions are **not fully orthogonal** - some values imply others.

---

## The QuiltOps Limitation

User observation: "QuiltOps only seems to do 1.5 dimensions"

### What QuiltOps Does

**Current scope:** Backend abstraction for API choice

- `Quilt3_Backend` → Uses quilt3 library
- `Platform_Backend` (missing) → Would use GraphQL

**What it handles:**

1. ✅ API choice (dimension 1) - but only one option exists
2. ⚠️  AUTH choice (dimension 2) - partially, through session detection

**What it DOESN'T handle:**
3. ❌ STATE management (dimension 3)
4. ❌ LOCALE configuration (dimension 4)

### Example: QuiltOps Can't Enforce Stateless

```python
# QuiltOps doesn't know about stateless mode
quilt_ops = QuiltOpsFactory.create()

# This might read from ~/.quilt/ even in "stateless" mode
# because QuiltOps has no concept of state management
session = quilt_ops.get_session()
```

The stateless enforcement happens **outside** QuiltOps:

- Docker `--read-only` filesystem (infrastructure level)
- `QUILT_MCP_STATELESS_MODE` (HTTP layer only)

But nothing prevents QuiltOps code from **attempting** filesystem access.

---

## Components Affected by Mode

### Components That Need Mode Awareness

1. **QuiltOps Factory** ([src/quilt_mcp/ops/factory.py](../../src/quilt_mcp/ops/factory.py))
   - Needs: API choice
   - Currently: Only has quilt3 option

2. **Context Factory** ([src/quilt_mcp/context/factory.py](../../src/quilt_mcp/context/factory.py))
   - Needs: AUTH mechanism, LOCALE (tenant mode)
   - Currently: Works correctly with fallback logic

3. **Auth Services** ([src/quilt_mcp/services/](../../src/quilt_mcp/services/))
   - Needs: AUTH mechanism, STATE (can access filesystem?)
   - Currently: Multiple scattered checks

4. **HTTP Utils** ([src/quilt_mcp/utils.py](../../src/quilt_mcp/utils.py))
   - Needs: STATE (stateless HTTP?), AUTH (JWT middleware?)
   - Currently: Checks `QUILT_MCP_STATELESS_MODE`

5. **JWT Middleware** ([src/quilt_mcp/middleware/jwt_middleware.py](../../src/quilt_mcp/middleware/jwt_middleware.py))
   - Needs: AUTH (enforce JWT?)
   - Currently: Has `require_jwt` parameter but unclear how it's set

6. **Runtime Context** ([src/quilt_mcp/runtime_context.py](../../src/quilt_mcp/runtime_context.py))
   - Needs: LOCALE (environment identifier)
   - Currently: Defaults to "desktop", can be updated

7. **Permission Services** ([src/quilt_mcp/services/permission_discovery.py](../../src/quilt_mcp/services/permission_discovery.py))
   - Needs: AUTH (which credentials to use?)
   - Currently: Checks `QUILT_DISABLE_QUILT3_SESSION`

---

## The Authentication Flaw (from spec/a11-client-testing/12)

**Critical discovery:** Current "stateless" mode isn't truly stateless.

### The Problem

**Local testing works** because:

1. `quilt3.logged_in()` returns True
2. Reads credentials from `~/.quilt/config.json`
3. Search operations succeed

**Docker testing fails** because:

1. `--read-only` filesystem
2. No access to `~/.quilt/` directory
3. `quilt3.logged_in()` returns False
4. Search operations return 0 results

### The Design Flaw

Quote from spec: "We've been cheating the whole time!"

**What we claimed:** Stateless mode with JWT authentication

**What we actually had:** Local mode with filesystem credentials, running stateless HTTP

**The fix requires:**

1. Stop using quilt3 session in stateless mode
2. Use JWT auth service to assume roles
3. Use GraphQL API instead of quilt3 library
4. Never access `~/.quilt/` in stateless mode

---

## Terminology Confusion

Current codebase uses **inconsistent terminology**:

### Terms for Similar Concepts

**For deployment type:**

- "stateless mode" (`QUILT_MCP_STATELESS_MODE`)
- "JWT mode" (`MCP_REQUIRE_JWT`)
- "multitenant mode" (`QUILT_MULTITENANT_MODE`)
- "web environment" (`RuntimeContextState.environment="web"`)

**For authentication:**

- "JWT auth" (JWTAuthService)
- "IAM auth" (IAMAuthService)
- "session auth" (quilt3 session)
- "Bearer token" (JWT middleware)

**For backend:**

- "quilt3 backend" (Quilt3_Backend)
- "Platform backend" (missing Platform_Backend)
- "GraphQL" (conceptual, not implemented)

### What Users Say vs What Code Says

| User Term | Code Term(s) | Clear? |
|-----------|-------------|--------|
| "Local mode" | Default behavior, no env var | ❌ Not explicit |
| "Stateless mode" | `QUILT_MCP_STATELESS_MODE=true` | ⚠️  Partial (only HTTP layer) |
| "JWT auth" | `MCP_REQUIRE_JWT=true`, JWTAuthService | ✅ Clear |
| "Session auth" | quilt3.logged_in(), IAMAuthService | ⚠️  Mixed terminology |
| "GraphQL backend" | No code exists | ❌ Missing |

---

## Summary: What Got Lost

User insight: "Something vital got lost in the QuiltOps/stateless refactor."

### What Got Lost: Coherent Mode Architecture

**Before refactor (simpler but limited):**

- One mode: Local development
- One backend: quilt3 library
- One auth: quilt3 session
- Clear but inflexible

**After refactor (confused):**

- Two intended modes: Local and Stateless
- But scattered env vars instead of explicit mode declaration
- Backend abstraction (QuiltOps) only covers API choice, not full mode
- Auth decisions spread across multiple components
- No single source of truth
- Unclear valid combinations

**What should exist:**

- **ONE** deployment mode configuration
- Coordinates API + AUTH + STATE + LOCALE
- All components query this single config
- Clear valid mode combinations
- Consistent terminology

---

## Key Questions for Design

1. **Should deployment modes be named configurations?**
   - Option A: `DEPLOYMENT_MODE=local|stateless` (simple, opinionated)
   - Option B: Configure 4 dimensions independently (flexible, complex)

2. **Are there exactly 2 valid modes, or more?**
   - Just "local" and "stateless"?
   - Or more nuanced combinations?

3. **Should ModeConfig be separate from QuiltOps?**
   - Yes - ModeConfig is higher-level, coordinates multiple subsystems
   - QuiltOps is just one consumer of mode config

4. **How should mode be set?**
   - Single env var at deployment time?
   - Config file?
   - CLI argument?

5. **What should happen if misconfigured?**
   - Fail fast at startup?
   - Allow partial configs with warnings?

---

## Next Steps

1. **Design ModeConfig abstraction**
   - Define the API
   - Determine valid mode combinations
   - Decide on configuration mechanism

2. **Map components to mode requirements**
   - Which components need which dimensions?
   - Can we reduce dependencies?

3. **Implement Platform_Backend**
   - Required for true stateless mode
   - Uses GraphQL instead of quilt3 library

4. **Refactor scattered checks**
   - Replace individual env var checks with ModeConfig queries
   - Centralize mode validation

5. **Update tests**
   - Test both modes explicitly
   - Ensure stateless tests truly run stateless

---

## Critical Files Referenced

### Mode Detection Logic

- [src/quilt_mcp/utils.py:420](../../src/quilt_mcp/utils.py#L420) - `QUILT_MCP_STATELESS_MODE`
- [src/quilt_mcp/services/auth_service.py:64](../../src/quilt_mcp/services/auth_service.py#L64) - `MCP_REQUIRE_JWT`
- [src/quilt_mcp/context/factory.py:36](../../src/quilt_mcp/context/factory.py#L36) - `QUILT_MULTITENANT_MODE`
- [src/quilt_mcp/services/iam_auth_service.py:29](../../src/quilt_mcp/services/iam_auth_service.py#L29) - `QUILT_DISABLE_QUILT3_SESSION`

### Backend Selection

- [src/quilt_mcp/ops/factory.py](../../src/quilt_mcp/ops/factory.py) - QuiltOps factory (incomplete)
- [src/quilt_mcp/backends/quilt3_backend.py](../../src/quilt_mcp/backends/quilt3_backend.py) - Only backend

### Auth Components

- [src/quilt_mcp/context/factory.py:88-96](../../src/quilt_mcp/context/factory.py#L88-L96) - Auth service selection
- [src/quilt_mcp/middleware/jwt_middleware.py](../../src/quilt_mcp/middleware/jwt_middleware.py) - JWT validation
- [src/quilt_mcp/services/jwt_decoder.py](../../src/quilt_mcp/services/jwt_decoder.py) - JWT config

### Runtime Context

- [src/quilt_mcp/runtime_context.py:35](../../src/quilt_mcp/runtime_context.py#L35) - Default environment

### Documentation

- [spec/a11-client-testing/12-stateless-authentication-flaw.md](../../spec/a11-client-testing/12-stateless-authentication-flaw.md) - Stateless auth flaw analysis

### Test Configuration

- [tests/conftest.py:138](../../tests/conftest.py#L138) - Test auth setup
- [tests/stateless/conftest.py](../../tests/stateless/conftest.py) - Docker stateless tests
