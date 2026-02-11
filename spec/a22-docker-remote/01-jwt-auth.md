# JWT Authentication and Remote Mode Testing

**Status**: Analysis
**Date**: 2025-02-11
**Context**: Understanding JWT authentication infrastructure and remote mode testing patterns

## Overview

This document analyzes the existing JWT authentication infrastructure and identifies patterns for testing remote mode deployments locally. The analysis reveals that most infrastructure already exists - the challenge is making it accessible for local development iteration.

## Deployment Modes

The system supports three deployment modes (defined in `src/quilt_mcp/config.py`):

| Mode | Backend | Transport | Multiuser | Use Case |
|------|---------|-----------|-----------|----------|
| **remote** | platform (graphql) | http | true | Production Docker containers (multi-client HTTP server) |
| **local** | platform (graphql) | stdio | true | IDE integration (Claude Desktop, VS Code) |
| **legacy** | quilt3 | stdio | false | Local development with quilt3 library and AWS credentials |

### Mode Properties

Each mode has specific constraints:

```python
# From src/quilt_mcp/config.py
class ModeConfig:
    @property
    def allows_filesystem_state(self) -> bool:
        """Only quilt3 backend allows filesystem state."""
        return self.backend == "quilt3"

    @property
    def requires_jwt(self) -> bool:
        """Platform backend requires JWT authentication."""
        return self.is_multiuser

    @property
    def allows_quilt3_library(self) -> bool:
        """Only legacy mode allows quilt3 library usage."""
        return self.backend == "quilt3"
```

**Key Constraint**: Remote mode (`QUILT_DEPLOYMENT=remote`) cannot access filesystem for credentials because:
1. Containers may be stateless with read-only filesystems
2. Multiple concurrent HTTP clients require isolated authentication
3. JWT tokens must be passed per-request via HTTP headers

## JWT Discovery Hierarchy

JWT tokens are discovered in priority order (`src/quilt_mcp/auth/jwt_discovery.py`):

1. **Runtime context** (middleware-provided from HTTP requests) - highest priority
2. **Environment secrets** (`MCP_JWT_SECRET` or `PLATFORM_TEST_JWT_SECRET`)
3. **quilt3 session** (from `~/.quilt/auth.json` if authenticated)
4. **Auto-generation** (if `QUILT_ALLOW_TEST_JWT=true`)

### JWT Authentication Flow

Remote mode (HTTP transport):
```
HTTP Request with Authorization: Bearer <jwt>
         ↓
JwtExtractionMiddleware (extracts token)
         ↓
RuntimeAuthState (stores token in context)
         ↓
JWTAuthService.get_boto3_session()
         ↓
Exchange JWT for temporary AWS credentials
         ↓
Cached credentials (5-minute refresh buffer)
```

Local mode (stdio transport):
```
MCP request over stdio
         ↓
RequestContextFactory
         ↓
JWTDiscovery.discover() (environment → session → generate)
         ↓
JWTAuthService or IAMAuthService
         ↓
Tool execution
```

**Critical Design**: JWT tokens are **NOT validated locally**. They are passed directly to the GraphQL backend, which validates them and exchanges them for temporary AWS credentials.

## Existing Test Infrastructure

### JWT Generation

The `make_test_jwt()` helper exists in `tests/conftest.py`:

```python
def make_test_jwt(
    *,
    secret: str,
    subject: str = "stateless-user",
    expires_in: int = 600,
    extra_claims: Dict[str, Any] | None = None,
) -> str:
    """Generate a catalog-format JWT for testing."""
    import jwt
    import time
    import uuid

    payload = {
        "id": subject,
        "uuid": str(uuid.uuid4()),
        "exp": int(time.time()) + expires_in,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, secret, algorithm="HS256")
```

### Runtime Context Management

Thread-safe, request-scoped authentication (`src/quilt_mcp/context/runtime_context.py`):

```python
@dataclass(frozen=True)
class RuntimeAuthState:
    scheme: str  # "Bearer"
    access_token: Optional[str] = None
    claims: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)

# Context manipulation
token_handle = push_runtime_context(
    environment="web",
    auth=RuntimeAuthState(scheme="Bearer", access_token=jwt_token, claims={})
)
try:
    # Use token
    ...
finally:
    reset_runtime_context(token_handle)
```

### Docker Testing Infrastructure

Comprehensive stateless testing (`tests/conftest.py` lines 572-670):

```python
@pytest.fixture
def stateless_container(docker_client, build_docker_image: str):
    """Docker container with full stateless constraints."""
    container = docker_client.containers.run(
        image=build_docker_image,
        environment={
            "QUILT_MULTIUSER_MODE": "true",
            "QUILT_CATALOG_URL": "http://test-catalog.example.com",
            "QUILT_REGISTRY_URL": "http://test-registry.example.com",
        },
        read_only=True,  # Read-only filesystem
        security_opt=["no-new-privileges:true"],
        cap_drop=["ALL"],  # Drop all Linux capabilities
        tmpfs={"/tmp": "size=100M", "/run": "size=10M"},
        mem_limit="512m",
        cpu_count=1.0,
    )
```

**Make Target**: `make test-mcp-docker` runs full Docker test suite with stateless constraints.

### Backend Mode Parametrization

Tests can run against both backends (`tests/conftest.py` lines 209-287):

```python
@pytest.fixture(params=_backend_mode_params())
def backend_mode(request, monkeypatch, clean_auth, test_env):
    """Parametrize tests for quilt3 and/or platform backends."""
    mode = request.param

    if mode == "platform":
        # Set multiuser mode
        monkeypatch.setenv("QUILT_MULTIUSER_MODE", "true")

        # Discover or generate JWT
        access_token = (
            os.getenv("PLATFORM_TEST_JWT_TOKEN") or
            _get_quilt3_session_jwt() or
            make_test_jwt(secret="test-secret", subject="test-user")
        )

        # Push to runtime context
        token_handle = push_runtime_context(
            environment="web",
            auth=RuntimeAuthState(
                scheme="Bearer",
                access_token=access_token,
                claims=jwt.decode(access_token, options={"verify_signature": False})
            )
        )
        request.addfinalizer(lambda: reset_runtime_context(token_handle))
```

**Environment Control**: `TEST_BACKEND_MODE=platform` or `TEST_BACKEND_MODE=quilt3` controls which backend to test.

## Current Testing Approaches

### 1. Docker Testing (Production-Like)

**Command**: `make test-mcp-docker`

**What it does**:
1. Builds Docker image with `QUILT_DEPLOYMENT=remote`
2. Starts container with read-only filesystem and security constraints
3. Generates JWT via `make_test_jwt()`
4. Makes HTTP requests to container with `Authorization: Bearer` header
5. Validates MCP protocol functionality

**Advantages**:
- Full production constraints
- Tests actual deployment configuration
- Validates stateless operation

**Disadvantages**:
- Slow (Docker build + container lifecycle)
- Not suitable for rapid iteration
- Complex to debug

### 2. Pytest Backend Mode (Unit/Integration)

**Command**: `make test-func` or `make test-e2e`

**What it does**:
1. Parametrizes tests for `quilt3` and/or `platform` backends
2. Auto-discovers or generates JWT for platform tests
3. Pushes JWT to runtime context
4. Executes tests with proper auth state
5. Cleans up context after tests

**Advantages**:
- Fast execution
- Easy debugging
- Integrated with pytest ecosystem

**Disadvantages**:
- Uses stdio transport (not HTTP like production)
- Doesn't test HTTP middleware
- No stateless constraints

### 3. Manual quilt3 CLI (Legacy)

**Command**: `quilt3 login && uv run quilt-mcp`

**What it does**:
1. Authenticates with quilt3 library
2. Stores session in `~/.quilt/auth.json`
3. Server discovers JWT from quilt3 session
4. Works for local development only

**Advantages**:
- Simple setup
- Uses real credentials
- No manual JWT management

**Disadvantages**:
- Only works for legacy mode
- Requires filesystem access
- Not suitable for remote mode testing

## Gap Analysis

### What Works Today

✅ **Docker remote mode testing** - `make test-mcp-docker` fully tests production deployment
✅ **JWT infrastructure** - Discovery, generation, context management all complete
✅ **Backend parametrization** - Tests can run against both backends with proper auth
✅ **Stateless validation** - Docker tests enforce read-only filesystem and security constraints

### What's Missing

❌ **Local HTTP server for remote mode** - No convenient way to run HTTP server locally without Docker
❌ **HTTP client fixture** - No pytest fixture for making authenticated HTTP requests
❌ **Quick iteration workflow** - Docker testing is too slow for development
❌ **Documentation** - Developers don't know they CAN test remote mode locally

## Remote Mode Testing Challenge

**Problem Statement**: How to test remote mode (HTTP + JWT) locally without the overhead of Docker?

**Requirements**:
1. Start HTTP server in remote mode locally (not containerized)
2. Inject JWT for each HTTP request
3. Test individual tools/endpoints quickly
4. Support both manual testing (curl) and automated testing (pytest)

**Constraints**:
- Cannot use filesystem for credentials (simulating stateless container)
- Must use HTTP transport (not stdio)
- Must pass JWT via `Authorization: Bearer` header
- Should reuse existing JWT infrastructure

## Proposed Minimal Additions

### Option A: Make Target Only

Add to `make.dev`:

```makefile
run-remote:
	@echo "Starting HTTP server in remote mode..."
	@export QUILT_DEPLOYMENT=remote && \
		export FASTMCP_TRANSPORT=http && \
		export FASTMCP_HOST=127.0.0.1 && \
		export FASTMCP_PORT=8003 && \
		uv run quilt-mcp
```

**Manual testing**:
```bash
# Terminal 1
make run-remote

# Terminal 2
JWT=$(uv run python -c "from tests.conftest import make_test_jwt; print(make_test_jwt(secret='test-secret'))")
curl -H "Authorization: Bearer $JWT" http://localhost:8003/health
```

**Pros**: Minimal change, reuses everything
**Cons**: Manual JWT generation required for each test

### Option B: Pytest Fixture

Add to `tests/conftest.py`:

```python
@pytest.fixture
def http_client_with_jwt():
    """HTTP client that auto-injects JWT."""
    import httpx
    from contextlib import contextmanager

    @contextmanager
    def client(base_url: str, jwt_secret: str = "test-secret"):
        token = make_test_jwt(secret=jwt_secret)
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(base_url=base_url, headers=headers) as c:
            yield c

    return client
```

**Usage**:
```python
def test_remote_endpoint(http_client_with_jwt):
    # Assumes server running on localhost:8003
    with http_client_with_jwt("http://localhost:8003") as client:
        response = client.get("/health")
        assert response.status_code == 200
```

**Pros**: Automated JWT injection, pytest integration
**Cons**: Requires manual server startup

### Option C: Helper Script

Create `scripts/test-remote.sh`:

```bash
#!/bin/bash
# Quick test helper for remote mode

PORT=8003
JWT=$(uv run python -c "from tests.conftest import make_test_jwt; print(make_test_jwt(secret='test-secret'))")

curl -H "Authorization: Bearer $JWT" \
     -H "Content-Type: application/json" \
     "http://localhost:${PORT}${1:-/health}"
```

**Usage**: `./scripts/test-remote.sh /health`

**Pros**: Simplest for manual testing
**Cons**: Shell script, not integrated with Python tests

## Recommendation

**Implement Option A + Option B** (minimal additions):

1. **Add `make run-remote` target** - Start local HTTP server quickly
2. **Add `http_client_with_jwt` fixture** - Enable pytest testing with JWT

This provides:
- Quick manual testing: `make run-remote` + curl
- Automated testing: pytest fixture for integration tests
- Full Docker testing: existing `make test-mcp-docker` for validation

**Total changes**: ~30 lines in `make.dev` and `tests/conftest.py`

## Environment Variables Reference

| Variable | Remote | Local | Legacy | Purpose |
|----------|--------|-------|--------|---------|
| `QUILT_DEPLOYMENT` | `remote` | `local` | `legacy` | Deployment mode |
| `QUILT_CATALOG_URL` | Required | Required | Optional | Platform backend URL |
| `QUILT_REGISTRY_URL` | Required | Required | Optional | Registry backend URL |
| `MCP_JWT_SECRET` | Optional | Optional | N/A | Generate JWT from secret |
| `QUILT_ALLOW_TEST_JWT` | Optional | Optional | N/A | Auto-generate test JWT |
| `FASTMCP_TRANSPORT` | `http` | `stdio` | `stdio` | Transport protocol |
| `FASTMCP_HOST` | `0.0.0.0` | N/A | N/A | HTTP bind address |
| `FASTMCP_PORT` | `8000` | N/A | N/A | HTTP bind port |

## Testing Comparison

| Aspect | Docker | Local HTTP | Pytest Backend |
|--------|--------|------------|----------------|
| **Speed** | Slow | Fast | Fast |
| **Transport** | HTTP | HTTP | stdio |
| **JWT** | Required | Required | Optional |
| **Filesystem** | Read-only | Read-write | Read-write |
| **Use Case** | Pre-deployment | Development | Unit/integration |

## Key Takeaways

1. **Infrastructure is complete** - JWT discovery, generation, context management all exist
2. **Docker testing works** - `make test-mcp-docker` fully validates production deployment
3. **Gap is convenience** - No easy way to run local HTTP server for rapid iteration
4. **Minimal additions needed** - One make target + one pytest fixture solves the problem
5. **No core changes required** - All authentication code already handles remote mode correctly

## References

- `src/quilt_mcp/config.py` - Deployment mode configuration
- `src/quilt_mcp/auth/jwt_discovery.py` - JWT token discovery
- `src/quilt_mcp/middleware/jwt_extraction.py` - HTTP JWT extraction
- `src/quilt_mcp/context/runtime_context.py` - Runtime authentication state
- `src/quilt_mcp/services/jwt_auth_service.py` - JWT authentication service
- `tests/conftest.py` - Test fixtures and utilities
- `tests/stateless/` - Docker stateless testing
- `spec/a21-platform-default/05-deployment-parameter.md` - Deployment mode specification
