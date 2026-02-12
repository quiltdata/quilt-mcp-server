# Analysis: Docker Remote Mode with Pre-Injected JWT for Claude.ai

**Status**: Analysis Only - No Implementation
**Date**: 2026-02-11
**Context**: Understanding requirements for exposing local Docker MCP server to Claude.ai via ngrok without OAuth server

## Executive Summary

**Goal**: Run Docker container locally in "remote" mode, expose via ngrok, and allow Claude.ai to connect **without** OAuth authentication (which is not yet available).

**Proposed Hack**: Pre-inject a valid JWT into the Docker container environment, use it as a fallback when Claude.ai connects without authentication headers.

**Status**: This document is **analysis only**. It identifies the problem, examines current architecture, and highlights critical technical challenges that must be resolved before implementation.

---

## 1. The Problem

### What We Need

1. **Local Docker in Remote Mode**
   - Run Docker container locally with `QUILT_DEPLOYMENT=remote`
   - This enables HTTP transport (`FASTMCP_TRANSPORT=http`)
   - Container listens on `0.0.0.0:8000`

2. **Ngrok Tunnel**
   - Expose local Docker HTTP endpoint to internet via ngrok
   - Claude.ai can reach the MCP server at public URL (e.g., `https://uniformly-alive-halibut.ngrok-free.app`)

3. **Authentication Workaround**
   - Claude.ai Desktop doesn't support OAuth (not implemented yet)
   - Claude.ai makes requests **without** `Authorization: Bearer` headers
   - Need a way to authenticate these requests

### Current Blocker

**The auth server (OAuth flow) is not yet enabled.**

Without OAuth:

- Claude.ai cannot obtain JWTs through standard OAuth flow
- Claude.ai cannot send `Authorization: Bearer` headers
- Current middleware (`JwtExtractionMiddleware`) **requires** JWT and rejects unauthenticated requests with 401

---

## 2. Current JWT Authentication Architecture

### 2.1 JWT Discovery Flow (Production)

**File**: `src/quilt_mcp/auth/jwt_discovery.py`

```python
# Priority order for JWT discovery:
1. Runtime context (middleware-provided from Authorization header)
2. quilt3 session (from `quilt3 login`)
3. Auto-generation (if QUILT_ALLOW_TEST_JWT=true) - DEV ONLY
```

### 2.2 JWT Extraction Middleware (HTTP Transport)

**File**: `src/quilt_mcp/middleware/jwt_extraction.py`

Current behavior:

1. Extracts JWT from `Authorization: Bearer <token>` header
2. **NO local validation** - passes token through to GraphQL backend
3. Injects token into runtime context via `push_runtime_context()`
4. GraphQL backend validates JWT and exchanges for AWS credentials

**Critical Code Path**:

```python
class JwtExtractionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, require_jwt: bool = True):
        self.require_jwt = require_jwt

    async def dispatch(self, request: Request, call_next):
        # Health check endpoints bypass JWT
        if request.url.path in {"/", "/health", "/healthz"}:
            return await call_next(request)

        if not self.require_jwt:
            return await call_next(request)

        # Require Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header:
            return _error_response(401, "JWT authentication required")

        # Extract Bearer token (no validation)
        token = auth_header[7:].strip()  # Remove "Bearer "

        # Push to runtime context
        auth_state = RuntimeAuthState(scheme="Bearer", access_token=token)
        token_handle = push_runtime_context(
            environment=get_runtime_environment(),
            auth=auth_state
        )

        try:
            response = await call_next(request)
        finally:
            reset_runtime_context(token_handle)

        return response
```

**Key Observations**:

- `require_jwt` parameter exists but is currently `True` for remote mode
- Middleware only **extracts** JWT, never validates it
- All validation happens at GraphQL backend (`/api/auth/get_credentials`)
- Runtime context is **request-scoped** via context variables

### 2.3 JWT Auth Service (Backend Layer)

**File**: `src/quilt_mcp/services/jwt_auth_service.py`

```python
class JWTAuthService:
    def _resolve_access_token(self) -> Optional[str]:
        """Resolve JWT token from runtime context first, then discovery fallbacks."""
        # Priority 1: Runtime context (from middleware)
        runtime_auth = get_runtime_auth()
        if runtime_auth and runtime_auth.access_token:
            return runtime_auth.access_token

        # Priority 2: JWT discovery (quilt3 session, env vars, etc.)
        return JWTDiscovery.discover()

    def get_boto3_session(self):
        """Exchange JWT for temporary AWS credentials."""
        access_token = self._resolve_access_token()
        if not access_token:
            raise JwtAuthServiceError("JWT authentication required")

        # Exchange JWT for AWS credentials at GraphQL backend
        credentials = self._get_or_refresh_credentials(access_token)

        return boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
        )
```

**Key Observations**:

- Service checks runtime context **first**, then falls back to discovery
- JWT is passed to GraphQL backend at `/api/auth/get_credentials`
- Backend validates JWT and returns temporary AWS credentials
- Credentials are cached with auto-refresh on expiration

### 2.4 Runtime Context System

**File**: `src/quilt_mcp/context/runtime_context.py`

```python
@dataclass(frozen=True)
class RuntimeAuthState:
    """Authentication details for the active request/environment."""
    scheme: str
    access_token: Optional[str] = None
    claims: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RuntimeContextState:
    """Top-level runtime context shared with MCP tools."""
    environment: str  # "web" or "desktop"
    auth: Optional[RuntimeAuthState] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# Request-scoped context variable
_runtime_context_var: ContextVar[RuntimeContextState] = ContextVar(
    "quilt_runtime_context",
    default=_default_state,
)
```

**Key Observations**:

- Uses Python `ContextVar` for request isolation
- Middleware pushes auth state at request start
- Middleware pops auth state at request end
- Tools access via `get_runtime_auth()`

---

## 3. Docker Remote Deployment

### 3.1 Dockerfile Configuration

**File**: `Dockerfile`

```dockerfile
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    QUILT_DEPLOYMENT=remote \          # Sets deployment mode to "remote"
    FASTMCP_TRANSPORT=http \           # Forces HTTP transport
    FASTMCP_HOST=0.0.0.0 \             # Binds to all interfaces
    FASTMCP_PORT=8000                  # Listens on port 8000
```

**Deployment Mode Resolution** (`config.py`):

- `QUILT_DEPLOYMENT=remote` → `DeploymentMode.REMOTE`
- Remote mode → backend=`graphql` (platform), transport=`http`
- Platform backend → requires JWT authentication

### 3.2 Current Docker Test Setup

**File**: `scripts/docker_manager.py`

Current stateless container config:

```python
def create_stateless_config(self, ...):
    env_vars = {
        "QUILT_MULTIUSER_MODE": "true",          # Forces platform backend
        "QUILT_CATALOG_URL": catalog_url,
        "QUILT_REGISTRY_URL": registry_url,
        "QUILT_DISABLE_CACHE": "true",
        "HOME": "/tmp",
        "LOG_LEVEL": "DEBUG",
        "FASTMCP_TRANSPORT": "http",
        "FASTMCP_HOST": "0.0.0.0",
        "FASTMCP_PORT": "8000",
        "AWS_REGION": "us-east-1",
    }
```

**Testing Flow** (`scripts/mcp-test.py`):

```python
# Docker tests now require REAL JWTs (no fake fallback)
if args.jwt:
    # Priority 1: PLATFORM_TEST_JWT_TOKEN env var
    jwt_token = os.getenv("PLATFORM_TEST_JWT_TOKEN")

    # Priority 2: quilt3 session (from `quilt3 login`)
    if not jwt_token:
        jwt_token = get_from_quilt3_session()

    # Priority 3: FAIL - no fake JWTs allowed
    if not jwt_token:
        sys.exit(1)  # Must have real JWT
```

**Key Observations**:

- Docker tests pass JWT via `Authorization: Bearer` header
- Tests require **real JWTs** (no generated/fake tokens)
- Container validates JWT against real GraphQL backend

---

## 4. Claude.ai Remote Connection Requirements

### 4.1 MCP Protocol Over HTTP

Claude.ai Desktop connects to remote MCP servers via:

1. **HTTP POST** to MCP endpoint (e.g., `http://localhost:8000/mcp`)
2. **JSON-RPC 2.0** protocol over HTTP
3. **Optional authentication** via headers

### 4.2 Current OAuth Gap

**What's Missing**:

- Claude.ai Desktop has no OAuth integration yet
- Cannot obtain JWT through standard OAuth flow
- Cannot provide `Authorization: Bearer` headers

**What Claude.ai Can Do**:

- Make HTTP requests to public URLs (via ngrok)
- Send custom headers (if configured in MCP settings)
- Store static tokens in configuration

**What Claude.ai Cannot Do** (yet):

- Initiate OAuth flows
- Refresh expired tokens automatically
- Handle 401 redirects to authorization endpoints

### 4.3 Ngrok Tunnel

**Purpose**: Expose local Docker HTTP endpoint to internet

```bash
# Start ngrok tunnel
ngrok http 8000 --domain=uniformly-alive-halibut.ngrok-free.app

# Claude.ai configuration (hypothetical)
{
  "mcpServers": {
    "quilt": {
      "url": "https://uniformly-alive-halibut.ngrok-free.app/mcp",
      "transport": "http"
      // No auth headers - this is the problem!
    }
  }
}
```

---

## 5. The Proposed Hack: Pre-Injected JWT

### 5.1 High-Level Concept

**Idea**: Pre-inject a valid JWT into the Docker container environment, use it as a fallback when requests arrive without authentication headers.

**Flow**:

```
1. Obtain valid JWT (via `quilt3 login`)
2. Inject JWT into Docker container as environment variable
3. Middleware checks Authorization header
4. If missing → fallback to pre-injected JWT from env
5. Use pre-injected JWT for backend authentication
```

### 5.2 Where to Inject JWT

**Option A: Environment Variable**

```bash
docker run \
  -e QUILT_FALLBACK_JWT="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -p 8000:8000 \
  quilt-mcp:test
```

**Option B: Docker Secret (more secure)**

```bash
echo "eyJhbGciOi..." | docker secret create quilt_jwt -
docker service create \
  --secret quilt_jwt \
  quilt-mcp:test
```

**Option C: Mounted Volume**

```bash
echo "eyJhbGciOi..." > /tmp/jwt-token
docker run \
  -v /tmp/jwt-token:/run/secrets/jwt:ro \
  quilt-mcp:test
```

### 5.3 Where to Use Pre-Injected JWT

**Current Middleware** (`jwt_extraction.py`):

```python
async def dispatch(self, request: Request, call_next):
    auth_header = request.headers.get("authorization")

    # CURRENT BEHAVIOR: Reject if missing
    if not auth_header:
        return _error_response(401, "JWT authentication required")
```

**Proposed Modification** (pseudocode):

```python
async def dispatch(self, request: Request, call_next):
    auth_header = request.headers.get("authorization")

    # NEW BEHAVIOR: Fallback to pre-injected JWT
    if not auth_header:
        fallback_jwt = os.getenv("QUILT_FALLBACK_JWT")
        if fallback_jwt:
            # Use pre-injected JWT
            token = fallback_jwt
        else:
            return _error_response(401, "JWT authentication required")
    else:
        # Extract from header as before
        token = auth_header[7:].strip()

    # Continue with token (from header or fallback)
    auth_state = RuntimeAuthState(scheme="Bearer", access_token=token)
    token_handle = push_runtime_context(...)
    ...
```

### 5.4 IP Whitelisting (Optional Layer)

**Purpose**: Restrict fallback JWT usage to trusted IPs (e.g., Claude.ai servers)

```python
async def dispatch(self, request: Request, call_next):
    auth_header = request.headers.get("authorization")

    if not auth_header:
        # Check if request is from whitelisted IP
        client_ip = request.client.host
        allowed_ips = os.getenv("QUILT_ALLOWED_IPS", "").split(",")

        if client_ip not in allowed_ips:
            return _error_response(403, "IP not whitelisted")

        # Use fallback JWT for whitelisted IPs only
        fallback_jwt = os.getenv("QUILT_FALLBACK_JWT")
        if not fallback_jwt:
            return _error_response(401, "JWT authentication required")

        token = fallback_jwt
    else:
        token = auth_header[7:].strip()

    ...
```

**Challenges with IP Whitelisting**:

- Claude.ai IP ranges may change
- Ngrok hides original client IP (proxied)
- May need ngrok Pro for IP forwarding

---

## 6. Critical Technical Challenges

### 6.1 JWT Expiration

**Problem**: JWTs have limited lifespan (typically 1-24 hours)

**Current JWT Structure** (from GraphQL backend):

```json
{
  "id": "user-123",
  "uuid": "abc-def-ghi",
  "iat": 1707667200,  // Issued at
  "exp": 1707670800   // Expires at (1 hour later)
}
```

**Implications**:

- Pre-injected JWT will expire within hours
- Container must be restarted with fresh JWT
- No automatic refresh mechanism without OAuth

**Possible Mitigations**:

1. **Short-lived testing**: Accept frequent restarts for development
2. **Long-lived JWTs**: Request special JWT with longer expiration from backend
3. **Refresh script**: External script periodically updates container JWT
4. **JWT refresh endpoint**: Add endpoint to container to update JWT at runtime

### 6.2 Security Implications

**Threat Model**:

1. **JWT Exposure via Environment Variables**
   - Environment variables visible via `docker inspect`
   - Anyone with Docker access can extract JWT
   - JWT can be used to impersonate user

2. **Network Exposure via Ngrok**
   - Public URL accessible from internet
   - Anyone with URL can access MCP server (if using fallback JWT)
   - Ngrok URLs can be discovered/shared

3. **JWT Reuse Across Requests**
   - Same JWT used for all unauthenticated requests
   - No per-request isolation
   - Cannot distinguish between different clients

4. **Credential Caching**
   - JWT Auth Service caches AWS credentials
   - Multiple clients share same cached credentials
   - All clients have same AWS permissions

**Risk Assessment**:

- **High Risk** for production use
- **Acceptable Risk** for local development/testing with short-lived JWTs
- **Medium Risk** with IP whitelisting and ngrok authentication

### 6.3 Runtime Context Isolation

**Problem**: Runtime context is request-scoped, but fallback JWT is global

**Current Behavior**:

- Each request has isolated runtime context (via `ContextVar`)
- Middleware pushes auth state at request start
- Middleware pops auth state at request end

**With Fallback JWT**:

- All unauthenticated requests share same JWT
- All requests appear to come from same user
- Cannot distinguish between multiple clients

**Implications**:

- Logging shows same user for all requests
- Telemetry cannot track individual clients
- Rate limiting applies to shared identity

### 6.4 JWT Discovery Interference

**Current JWT Resolution** (`JWTAuthService._resolve_access_token()`):

```python
def _resolve_access_token(self) -> Optional[str]:
    # Priority 1: Runtime context (from middleware)
    runtime_auth = get_runtime_auth()
    if runtime_auth and runtime_auth.access_token:
        return runtime_auth.access_token

    # Priority 2: JWT discovery (quilt3 session, env vars, etc.)
    return JWTDiscovery.discover()
```

**Question**: How does fallback JWT interact with discovery?

**If fallback JWT is injected via middleware**:

- Runtime context always has token
- Discovery never runs
- Quilt3 session credentials ignored

**If fallback JWT is added to discovery**:

- Need to modify `JWTDiscovery.discover()`
- Changes shared discovery logic across deployments
- May affect local/legacy modes unintentionally

### 6.5 Credential Exchange Backend

**Current Flow**:

```
JWT → /api/auth/get_credentials → AWS Credentials
```

**Backend Validation**:

- GraphQL backend validates JWT signature
- Checks JWT expiration
- Verifies user identity
- Returns temporary AWS credentials (1-hour TTL)

**With Pre-Injected JWT**:

- Backend validation works as normal
- JWT must be valid (not expired, correct signature)
- AWS credentials cached by `JWTAuthService`
- Credentials refreshed automatically on expiration

**Question**: Does backend log JWT reuse?

- If backend tracks JWT usage, repeated use may trigger alerts
- May appear as suspicious activity (same JWT, multiple IPs)

### 6.6 QUILT_ALLOW_TEST_JWT Confusion

**Current Test JWT Generation** (`jwt_discovery.py`):

```python
def _allow_test_jwt() -> bool:
    return os.getenv("QUILT_ALLOW_TEST_JWT", "false").lower() == "true"

def _generate_test_jwt() -> str:
    secret = "test-secret-for-jwt-generation"
    return _generate_jwt(secret, subject_prefix="test")
```

**Test JWTs are FAKE**:

- Signed with local secret, not backend secret
- Fail validation at GraphQL backend
- Only work with mocked backends (pytest fixtures)

**Pre-Injected JWT must be REAL**:

- Signed by GraphQL backend
- Valid signature and expiration
- Accepted by `/api/auth/get_credentials`

**Critical Distinction**:

- `QUILT_ALLOW_TEST_JWT` enables **fake** JWTs (mocked tests)
- `QUILT_FALLBACK_JWT` would use **real** JWTs (production backend)
- These are completely different mechanisms

---

## 7. Open Questions for Design

### 7.1 Configuration Questions

1. **What environment variable name?**
   - `QUILT_FALLBACK_JWT` (descriptive)
   - `QUILT_REMOTE_JWT` (mode-specific)
   - `QUILT_STATIC_JWT` (behavior-specific)

2. **Where to enforce fallback JWT?**
   - Middleware layer (`jwt_extraction.py`)
   - Discovery layer (`jwt_discovery.py`)
   - Both (with different priority)?

3. **Should fallback JWT be mode-specific?**
   - Only in `QUILT_DEPLOYMENT=remote`?
   - Also in `local` mode?
   - Disabled in `legacy` mode?

### 7.2 Security Questions

1. **How to obtain pre-injected JWT?**
   - Manual: `quilt3 login` → copy token from session
   - Script: Extract from quilt3 session automatically
   - API: Request long-lived JWT from backend

2. **Should we implement IP whitelisting?**
   - Pros: Restricts fallback JWT to trusted sources
   - Cons: Complex, Claude.ai IPs unknown, ngrok proxies IP

3. **How to handle JWT expiration?**
   - Accept manual container restarts?
   - Add runtime JWT refresh endpoint?
   - External monitoring/restart script?

4. **How to secure JWT in Docker?**
   - Environment variable (easy, less secure)
   - Docker secret (more secure, requires swarm mode)
   - Mounted volume (flexible, still accessible)

### 7.3 Operational Questions

1. **How to restart container with fresh JWT?**

   ```bash
   # Option 1: Manual restart
   docker stop mcp-remote
   export QUILT_FALLBACK_JWT=$(get_fresh_jwt)
   docker run ... -e QUILT_FALLBACK_JWT=$QUILT_FALLBACK_JWT

   # Option 2: Runtime update (requires new endpoint)
   curl -X POST http://localhost:8000/admin/update-jwt \
     -H "Authorization: Bearer admin-secret" \
     -d '{"jwt": "new-jwt-token"}'
   ```

2. **How to monitor JWT expiration?**
   - Log JWT expiration time at startup
   - Alert when JWT is close to expiration
   - Health check endpoint that validates JWT

3. **How to test this locally?**
   - Can we simulate Claude.ai connections?
   - Test tool that makes requests without auth headers
   - Validate fallback JWT is used correctly

### 7.4 Architecture Questions

1. **Should fallback JWT bypass middleware or work within it?**
   - **Within middleware**: Cleaner, request-scoped context preserved
   - **Bypass middleware**: Simpler, but breaks context isolation

2. **Should we add new middleware or modify existing?**
   - **Modify existing**: Simpler, single code path
   - **Add new middleware**: Cleaner separation, easier to remove later

3. **How does this affect stdio transport?**
   - Fallback JWT should be HTTP-only
   - Need to ensure no impact on local stdio mode

4. **What's the migration path when OAuth is ready?**
   - Remove fallback JWT support
   - Require OAuth for all remote connections
   - Provide clear deprecation timeline

---

## 8. Risk Assessment

### 8.1 Development/Testing Use Case

**Scenario**: Local development with ngrok tunnel for Claude.ai testing

**Risks**:

- **Low**: Short-lived JWT (1 hour)
- **Low**: Private ngrok URL (not easily discoverable)
- **Low**: Temporary setup (tear down after testing)

**Mitigations**:

- Use short-lived JWTs
- Regenerate ngrok URL per session
- Monitor for unexpected access

**Recommendation**: **ACCEPTABLE** for local dev/testing

### 8.2 Staging Environment

**Scenario**: Shared staging environment with persistent ngrok tunnel

**Risks**:

- **Medium**: Longer-lived JWT (potential for reuse)
- **Medium**: Persistent URL (discoverable over time)
- **High**: Shared staging data (potential for unauthorized access)

**Mitigations**:

- Implement IP whitelisting
- Use ngrok authentication
- Monitor access logs
- Rotate JWT daily

**Recommendation**: **CAUTION** - additional security controls required

### 8.3 Production Environment

**Scenario**: Production MCP server with public access

**Risks**:

- **HIGH**: Critical data exposure
- **HIGH**: Persistent JWT reuse
- **HIGH**: No per-client authentication

**Mitigations**:

- **DO NOT USE** fallback JWT in production
- **REQUIRE** OAuth implementation first
- Use proper authentication infrastructure

**Recommendation**: **NOT ACCEPTABLE** - wait for OAuth

---

## 9. Implementation Complexity Tiers

### Tier 1: Minimal (MVP for Local Testing)

**Changes**:

1. Modify `JwtExtractionMiddleware` to check `QUILT_FALLBACK_JWT` env var
2. Use fallback JWT when `Authorization` header is missing
3. Add logging to indicate fallback JWT usage

**Files Modified**:

- `src/quilt_mcp/middleware/jwt_extraction.py`

**Testing**:

- Manual test with Docker + ngrok
- Verify Claude.ai can connect without auth headers

**Effort**: ~2 hours
**Risk**: Low (easily reversible)

### Tier 2: Enhanced (With Monitoring)

**Changes**:

- All Tier 1 changes
- Add JWT expiration logging at startup
- Add health check endpoint that validates JWT
- Log warning when JWT is close to expiration (e.g., <15 minutes)

**Files Modified**:

- `src/quilt_mcp/middleware/jwt_extraction.py`
- `src/quilt_mcp/main.py` (add health check endpoint)
- `src/quilt_mcp/utils/common.py` (JWT parsing utilities)

**Testing**:

- Unit tests for JWT expiration detection
- Integration tests for health check endpoint

**Effort**: ~4-6 hours
**Risk**: Low-Medium (adds operational complexity)

### Tier 3: Production-Ready (With Security Controls)

**Changes**:

- All Tier 2 changes
- Implement IP whitelisting
- Add runtime JWT refresh endpoint (admin-authenticated)
- Implement JWT rotation mechanism
- Add comprehensive audit logging

**Files Modified**:

- `src/quilt_mcp/middleware/jwt_extraction.py`
- `src/quilt_mcp/middleware/ip_whitelist.py` (new)
- `src/quilt_mcp/main.py` (add admin endpoints)
- `src/quilt_mcp/utils/jwt_refresh.py` (new)
- `src/quilt_mcp/config.py` (add IP whitelist config)

**Testing**:

- Unit tests for IP whitelisting
- Integration tests for JWT refresh
- Security tests for admin endpoints

**Effort**: ~2-3 days
**Risk**: Medium-High (complex, requires careful security review)

---

## 10. Recommendations

### For Local Development/Testing (Current Need)

**RECOMMEND**: Implement **Tier 1** (Minimal MVP)

**Rationale**:

- Unblocks Claude.ai testing immediately
- Minimal code changes (easy to review and revert)
- Acceptable risk for local development
- No production use intended

**Next Steps**:

1. Confirm user acceptance of risks
2. Implement Tier 1 changes
3. Document setup process (ngrok + JWT injection)
4. Test with Claude.ai Desktop
5. Plan for OAuth implementation to replace this hack

### For Production Use (Future)

**RECOMMEND**: **Wait for OAuth**

**Rationale**:

- Pre-injected JWT is a hack, not a production solution
- Security risks too high for production data
- Proper authentication infrastructure needed
- Claude.ai OAuth support is coming (roadmap item)

**Alternative (if urgent)**:

- Implement Tier 3 (Production-Ready)
- Require additional security review
- Treat as temporary solution with deprecation timeline

---

## 11. Related Work

**Completed**:

- ✅ `spec/a22-docker-remote/01-jwt-auth.md` - JWT auth overview
- ✅ `spec/a22-docker-remote/02-jwt-docker-fix.md` - JWT discovery for Docker tests
- ✅ `spec/a22-docker-remote/03-jwt-docker-plan.md` - Real JWT requirement plan
- ✅ `spec/a22-docker-remote/04-jwt-docker-followon.md` - Implementation notes

**This Document**:

- 📝 `spec/a22-docker-remote/05-remote-ngrok-analysis.md` - Analysis only (this file)

**Future Work** (if Tier 1 is approved):

- 📋 `spec/a22-docker-remote/06-fallback-jwt-design.md` - Detailed design
- 📋 `spec/a22-docker-remote/07-fallback-jwt-impl.md` - Implementation guide
- 📋 `spec/a22-docker-remote/08-ngrok-setup.md` - Ngrok tunnel setup guide

---

## Appendix A: JWT Structure Example

**Typical JWT from GraphQL Backend**:

```
Header:
{
  "alg": "RS256",
  "typ": "JWT"
}

Payload:
{
  "id": "user-123",
  "uuid": "abc-def-ghi",
  "email": "user@example.com",
  "iat": 1707667200,
  "exp": 1707670800
}

Signature:
RSASHA256(
  base64UrlEncode(header) + "." +
  base64UrlEncode(payload),
  private_key
)
```

**How to Extract JWT from quilt3 Session**:

```python
import quilt3

session = quilt3.session.get_session()
auth_header = session.headers.get("Authorization")
if auth_header and auth_header.startswith("Bearer "):
    jwt_token = auth_header[7:]
    print(f"JWT: {jwt_token}")
```

---

## Appendix B: Current Make Targets

**Relevant Make Targets**:

```bash
# Build Docker image locally
make docker-build

# Run Docker tests with real JWT
make test-mcp-docker

# Start MCP server locally (stdio)
make run

# Start MCP Inspector (HTTP + UI)
make run-inspector
```

**New Make Target Needed** (if Tier 1 implemented):

```bash
# Run Docker in remote mode with ngrok
make run-docker-remote
```

---

## Document Status

- ✅ **Analysis Complete**: All architectural components examined
- ✅ **Risks Identified**: Security and operational risks documented
- ✅ **Questions Raised**: Open questions for design decisions
- ⏸️ **Implementation Pending**: Awaiting user approval for Tier 1 MVP

**Next Decision Point**: Should we proceed with Tier 1 (Minimal MVP) implementation?
