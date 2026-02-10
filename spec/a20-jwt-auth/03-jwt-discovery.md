# JWT Discovery Architecture Analysis

**Spec ID:** a20-jwt-auth/03-jwt-discovery-architecture-analysis
**Status:** Analysis Complete
**Created:** 2026-02-09
**Author:** System Analysis
**Related:** a20-jwt-auth/01-e2e-tabulator-test.md, a20-jwt-auth/02-e2e-backend-integration.md

---

## Executive Summary

**Problem:** JWT credential discovery logic currently lives in test infrastructure (`tests/e2e/conftest.py::_check_auth_available()`), but the user wants to switch the default local server (`uvx quilt-mcp`) to use the platform backend. This requires moving JWT discovery from test code into production code.

**Impact:** Without this change, local `uvx quilt-mcp` execution cannot automatically discover JWT credentials and defaults to the quilt3 backend instead of platform backend.

**Recommendation:** Move JWT discovery logic into production code as part of the backend initialization flow, with multiple discovery strategies (environment variables, quilt3 session, auto-generation for development).

---

## Current Architecture

### 1. Server Initialization Flow

```
main.py:main()
  │
  ├─> load_dotenv()  # Load .env from current directory
  │
  ├─> get_mode_config()  # Read QUILT_MULTIUSER_MODE
  │   └─> Returns ModeConfig instance
  │       ├─> .is_multiuser (bool)
  │       ├─> .backend_type ("quilt3" | "graphql")
  │       └─> .requires_jwt (bool)
  │
  ├─> mode_config.validate()  # Check required env vars
  │   └─> For multiuser: requires QUILT_CATALOG_URL, QUILT_REGISTRY_URL
  │
  └─> run_server()
      └─> Server accepts MCP requests
          └─> Tools call QuiltOpsFactory.create()
```

### 2. Backend Selection Logic

**File:** `src/quilt_mcp/ops/factory.py`

```python
class QuiltOpsFactory:
    @staticmethod
    def create() -> QuiltOps:
        mode_config = get_mode_config()

        if mode_config.backend_type == "quilt3":
            return Quilt3_Backend()  # Local development

        elif mode_config.backend_type == "graphql":
            return Platform_Backend()  # Multiuser production
```

**Key Decision Point:** `QUILT_MULTIUSER_MODE` environment variable

- `false` (default) → `Quilt3_Backend`
- `true` → `Platform_Backend`

### 3. JWT Loading (Current Implementation)

**File:** `src/quilt_mcp/backends/platform_backend.py`

```python
class Platform_Backend:
    def __init__(self):
        self._access_token = self._load_access_token()
        # ... rest of initialization

    def _load_access_token(self) -> str:
        runtime_auth = get_runtime_auth()
        if runtime_auth and runtime_auth.access_token:
            return runtime_auth.access_token
        raise AuthenticationError("JWT access token is required")
```

**Current Behavior:**

- Assumes JWT is already in `runtime_context`
- No discovery logic - just reads what's there
- Raises error if not found

### 4. Runtime Context (JWT Storage)

**File:** `src/quilt_mcp/context/runtime_context.py`

```python
@dataclass(frozen=True)
class RuntimeAuthState:
    scheme: str
    access_token: Optional[str] = None
    claims: Dict[str, Any] = field(default_factory=dict)

_runtime_context_var: ContextVar[RuntimeContextState]

def get_runtime_auth() -> Optional[RuntimeAuthState]:
    return _runtime_context_var.get().auth
```

**Current State:**

- Context variable holds JWT token
- No mechanism to populate it in production
- Only populated by tests via `push_runtime_context()`

### 5. Test Infrastructure (Current Discovery Logic)

**File:** `tests/e2e/conftest.py`

```python
def _check_auth_available(mode: str) -> bool:
    """Check if required authentication is available."""
    if mode == "quilt3":
        config_file = Path.home() / ".quilt" / "config.yml"
        return config_file.exists()

    elif mode == "platform":
        return bool(
            os.getenv("PLATFORM_TEST_ENABLED") and
            os.getenv("QUILT_CATALOG_URL") and
            os.getenv("QUILT_REGISTRY_URL")
        )
    return False
```

**What This Does:**

- For `quilt3`: checks if `~/.quilt/config.yml` exists
- For `platform`: checks if platform env vars are set
- **Does NOT** actually discover or load JWT tokens
- Only used for test skipping logic

**What It Should Do (in production):**

- Actually discover JWT credentials from multiple sources
- Load JWT token into runtime context or return it
- Handle fallback strategies (session → env var → generate)

---

## The Gap: Production JWT Discovery

### What's Missing

**Production code has NO JWT discovery mechanism:**

1. `Platform_Backend` expects JWT in runtime context
2. Runtime context is never populated in production
3. No code discovers JWT from:
   - Environment variables (`MCP_JWT_SECRET`, `PLATFORM_TEST_JWT_SECRET`)
   - quilt3 session (`~/.quilt/config.yml`)
   - Auto-generation for development

### Why This Matters for `uvx quilt-mcp`

**Current Behavior:**

```bash
$ uvx quilt-mcp
# QUILT_MULTIUSER_MODE not set → defaults to false
# → Creates Quilt3_Backend
# → Uses ~/.quilt/config.yml session
```

**Desired Behavior:**

```bash
$ uvx quilt-mcp
# Should auto-detect JWT credentials
# → If JWT available: use Platform_Backend
# → If not: fall back to Quilt3_Backend OR error with helpful message
```

---

## JWT Discovery Requirements

### Sources to Check (in priority order)

1. **Runtime Context** (already populated)
   - Check `get_runtime_auth().access_token`
   - If present, use it immediately
   - Source: Pushed by HTTP middleware for multiuser deployments

2. **Environment Variable** (`MCP_JWT_SECRET`)
   - Check `os.getenv("MCP_JWT_SECRET")`
   - If present, generate JWT from secret
   - Use case: Container deployments, CI/CD

3. **quilt3 Session** (`~/.quilt/config.yml`)
   - Check if `~/.quilt/config.yml` exists
   - Load and extract JWT from session
   - Use case: Local development with quilt3 login

4. **Auto-Generation** (development only)
   - Generate test JWT if `QUILT_ALLOW_TEST_JWT=true`
   - Use development secret
   - Use case: Local testing without real credentials

5. **No Credentials Available**
   - Clear error message
   - Suggest: `quilt3 login` or set `MCP_JWT_SECRET`
   - Option: Fall back to quilt3 backend

### Discovery Strategy

```python
def discover_jwt_token() -> Optional[str]:
    """Discover JWT token from available sources.

    Priority order:
    1. Runtime context (already set by middleware)
    2. Environment variable (MCP_JWT_SECRET)
    3. quilt3 session (~/.quilt/config.yml)
    4. Auto-generation (if enabled for development)

    Returns:
        JWT token string or None if not available
    """
    # Check runtime context first (multiuser deployments)
    runtime_auth = get_runtime_auth()
    if runtime_auth and runtime_auth.access_token:
        return runtime_auth.access_token

    # Check environment variable (containers, CI/CD)
    jwt_secret = os.getenv("MCP_JWT_SECRET")
    if jwt_secret:
        return generate_jwt_from_secret(jwt_secret)

    # Check quilt3 session (local development)
    jwt_from_session = extract_jwt_from_quilt3_session()
    if jwt_from_session:
        return jwt_from_session

    # Auto-generate for development (if enabled)
    if os.getenv("QUILT_ALLOW_TEST_JWT", "false").lower() == "true":
        return generate_test_jwt()

    return None
```

---

## Architecture Options

### Option A: Discovery in `Platform_Backend._load_access_token()`

**Implementation:**

```python
# src/quilt_mcp/backends/platform_backend.py

def _load_access_token(self) -> str:
    """Load JWT token from available sources."""
    # Try runtime context (multiuser mode)
    runtime_auth = get_runtime_auth()
    if runtime_auth and runtime_auth.access_token:
        return runtime_auth.access_token

    # Try environment variable
    jwt_secret = os.getenv("MCP_JWT_SECRET")
    if jwt_secret:
        return self._generate_jwt_from_secret(jwt_secret)

    # Try quilt3 session
    jwt_from_session = self._extract_jwt_from_quilt3_session()
    if jwt_from_session:
        return jwt_from_session

    # Auto-generate for development
    if os.getenv("QUILT_ALLOW_TEST_JWT", "false").lower() == "true":
        return self._generate_test_jwt()

    raise AuthenticationError(
        "JWT token not found. Options:\n"
        "1. Run 'quilt3 login' to authenticate\n"
        "2. Set MCP_JWT_SECRET environment variable\n"
        "3. For development: set QUILT_ALLOW_TEST_JWT=true"
    )
```

**Pros:**

- ✅ Encapsulated in backend
- ✅ Simple to implement
- ✅ Backend owns its authentication

**Cons:**

- ❌ Backend has too much responsibility
- ❌ Mixes credential discovery with backend logic
- ❌ Harder to test in isolation
- ❌ Duplicated if we add more backends

### Option B: Separate `JWTDiscovery` Service

**Implementation:**

```python
# src/quilt_mcp/auth/jwt_discovery.py

class JWTDiscovery:
    """Discover JWT credentials from multiple sources."""

    @staticmethod
    def discover() -> Optional[str]:
        """Discover JWT token from available sources."""
        # Same discovery logic as Option A
        pass

    @staticmethod
    def is_jwt_available() -> bool:
        """Check if JWT credentials are available."""
        return JWTDiscovery.discover() is not None

# src/quilt_mcp/backends/platform_backend.py

def _load_access_token(self) -> str:
    token = JWTDiscovery.discover()
    if not token:
        raise AuthenticationError("JWT token not found")
    return token
```

**Pros:**

- ✅ Separation of concerns
- ✅ Easy to test in isolation
- ✅ Reusable for other backends
- ✅ Can be used in validation/health checks

**Cons:**

- ❌ More files/complexity
- ❌ Another abstraction layer

### Option C: Discovery in `QuiltOpsFactory.create()`

**Implementation:**

```python
# src/quilt_mcp/ops/factory.py

@staticmethod
def create() -> QuiltOps:
    mode_config = get_mode_config()

    if mode_config.backend_type == "graphql":
        # Discover and populate JWT before creating backend
        jwt_token = JWTDiscovery.discover()
        if jwt_token:
            # Push into runtime context for backend to use
            push_runtime_context(
                environment="desktop",
                auth=RuntimeAuthState(
                    scheme="Bearer",
                    access_token=jwt_token
                )
            )
        return Platform_Backend()

    elif mode_config.backend_type == "quilt3":
        return Quilt3_Backend()
```

**Pros:**

- ✅ Centralized credential setup
- ✅ Backend stays simple
- ✅ Runtime context properly populated

**Cons:**

- ❌ Factory has more responsibility
- ❌ Harder to understand initialization flow
- ❌ Mixing factory and auth concerns

### Option D: Hybrid - Discovery Service + Backend Default Mode

**Implementation:**

```python
# src/quilt_mcp/auth/jwt_discovery.py
class JWTDiscovery:
    @staticmethod
    def discover() -> Optional[str]:
        # Discovery logic
        pass

# src/quilt_mcp/config.py
class ModeConfig:
    @property
    def backend_type(self) -> Literal["quilt3", "graphql"]:
        # NEW: Auto-detect based on JWT availability
        if self._multiuser_mode is None:
            # Auto-detect mode
            if JWTDiscovery.is_jwt_available():
                return "graphql"
            else:
                return "quilt3"

        # Explicit mode set
        return "graphql" if self._multiuser_mode else "quilt3"

# src/quilt_mcp/backends/platform_backend.py
def _load_access_token(self) -> str:
    token = JWTDiscovery.discover()
    if not token:
        raise AuthenticationError("JWT required but not found")
    return token
```

**Pros:**

- ✅ Automatic backend selection based on credentials
- ✅ Clean separation of concerns
- ✅ User doesn't need to set `QUILT_MULTIUSER_MODE` manually
- ✅ Falls back gracefully

**Cons:**

- ❌ More implicit behavior (could be confusing)
- ❌ Changes default behavior significantly

---

## Recommendation: Option B (Separate JWT Discovery Service)

### Why Option B?

1. **Separation of Concerns**
   - Credential discovery is separate from backend logic
   - Easy to test and maintain
   - Clear responsibility boundaries

2. **Reusability**
   - Can be used in tests (replace `_check_auth_available`)
   - Can be used in factory
   - Can be used in validation/health checks

3. **Explicit Behavior**
   - User still controls mode with `QUILT_MULTIUSER_MODE`
   - Discovery happens transparently
   - Clear error messages when credentials missing

4. **Testability**
   - `JWTDiscovery` can be tested in isolation
   - Backend tests can mock `JWTDiscovery`
   - Clear test boundaries

### Implementation Plan

**1. Create JWT Discovery Service**

File: `src/quilt_mcp/auth/jwt_discovery.py`

```python
class JWTDiscovery:
    @staticmethod
    def discover() -> Optional[str]:
        """Discover JWT from available sources."""
        pass

    @staticmethod
    def discover_or_raise() -> str:
        """Discover JWT or raise helpful error."""
        pass

    @staticmethod
    def is_available() -> bool:
        """Check if JWT is available."""
        pass
```

**2. Update Platform_Backend**

File: `src/quilt_mcp/backends/platform_backend.py`

```python
def _load_access_token(self) -> str:
    from quilt_mcp.auth.jwt_discovery import JWTDiscovery
    return JWTDiscovery.discover_or_raise()
```

**3. Update Test Infrastructure**

File: `tests/e2e/conftest.py`

```python
def _check_auth_available(mode: str) -> bool:
    from quilt_mcp.auth.jwt_discovery import JWTDiscovery

    if mode == "quilt3":
        config_file = Path.home() / ".quilt" / "config.yml"
        return config_file.exists()

    elif mode == "platform":
        return JWTDiscovery.is_available()

    return False
```

**4. Update Default Mode (Optional)**

If we want to auto-switch to platform backend when JWT available:

File: `src/quilt_mcp/config.py`

```python
class ModeConfig:
    def __init__(self, multiuser_mode: Optional[bool] = None):
        if multiuser_mode is not None:
            self._multiuser_mode = multiuser_mode
        else:
            env_value = os.getenv("QUILT_MULTIUSER_MODE")
            if env_value is None:
                # Auto-detect based on JWT availability
                from quilt_mcp.auth.jwt_discovery import JWTDiscovery
                self._multiuser_mode = JWTDiscovery.is_available()
            else:
                self._multiuser_mode = self._parse_bool(env_value)
```

---

## Migration Strategy

### Phase 1: Create JWT Discovery Service

1. Implement `JWTDiscovery` class
2. Add unit tests
3. Verify all discovery sources work

### Phase 2: Integrate with Platform_Backend

1. Update `_load_access_token()` to use `JWTDiscovery`
2. Add integration tests
3. Verify existing tests still pass

### Phase 3: Update Test Infrastructure

1. Replace `_check_auth_available()` logic with `JWTDiscovery`
2. Update E2E tests
3. Verify test skipping still works

### Phase 4: Auto-Detection (Optional)

1. Add auto-detection to `ModeConfig`
2. Update documentation
3. Add tests for auto-detection behavior

---

## Open Questions

1. **Should `uvx quilt-mcp` auto-detect backend?**
   - Option A: Require explicit `QUILT_MULTIUSER_MODE=true`
   - Option B: Auto-detect based on JWT availability
   - **Recommendation:** Start with Option A (explicit), add Option B later

2. **What if JWT is in session but expired?**
   - Should we validate JWT before using it?
   - Should we auto-refresh from quilt3 session?
   - **Recommendation:** Start with no validation, add later if needed

3. **Should we support multiple JWT sources simultaneously?**
   - What if runtime context AND session both have JWTs?
   - Which takes priority?
   - **Recommendation:** Use priority order (runtime → env → session → generated)

4. **How to handle JWT generation for development?**
   - Require explicit `QUILT_ALLOW_TEST_JWT=true`?
   - Auto-generate with warning?
   - **Recommendation:** Require explicit flag, show warning

---

## Impact Analysis

### Breaking Changes

- None if we keep explicit `QUILT_MULTIUSER_MODE` requirement
- Potential breaking change if we add auto-detection

### Performance Impact

- Minimal: JWT discovery runs once during backend initialization
- File system access for quilt3 session check
- **Mitigation:** Cache discovery result

### Security Considerations

- JWT discovery should not log sensitive tokens
- Test JWT generation should be clearly marked as insecure
- **Action:** Add security warnings for test JWTs

---

## Success Criteria

1. ✅ `uvx quilt-mcp` can discover JWT from quilt3 session
2. ✅ `uvx quilt-mcp` can use JWT from `MCP_JWT_SECRET`
3. ✅ Clear error messages when JWT not found
4. ✅ Test infrastructure uses same discovery logic
5. ✅ No breaking changes to existing deployments
6. ✅ JWT discovery logic in production code, not test code

---

## References

### Related Files

- `src/quilt_mcp/main.py` - Server entry point
- `src/quilt_mcp/config.py` - Mode configuration
- `src/quilt_mcp/ops/factory.py` - Backend factory
- `src/quilt_mcp/backends/platform_backend.py` - Platform backend
- `src/quilt_mcp/context/runtime_context.py` - JWT storage
- `tests/e2e/conftest.py` - Current discovery logic (test only)

### Related Specs

- `spec/a20-jwt-auth/01-e2e-tabulator-test.md`
- `spec/a20-jwt-auth/02-e2e-backend-integration.md`
- `spec/a18-valid-jwts/` - JWT validation work

---

## Sign-off

**Analysis Status:** Complete
**Recommendation:** Implement Option B (Separate JWT Discovery Service)
**Next Steps:** Review and approve approach, then implement
**Estimated Effort:** 1-2 days implementation + testing
