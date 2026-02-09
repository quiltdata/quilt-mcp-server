# A18: Existing JWT Code Analysis

**Date:** 2025-02-05
**Status:** Analysis
**Purpose:** Document all existing JWT-related code in the codebase

## Overview

This document provides a factual analysis of all JWT-related code currently in the quilt-mcp-server repository, examining what each component does, how they interact, and where they're used.

## Key Finding: MCP Server DOES Validate JWTs

**Important contradiction discovered:** The claim in `01-invalid-jwt-auth.md` that "The MCP server never validates JWTs - it simply forwards them to the Platform GraphQL backend" is **incorrect**.

The MCP server performs **full cryptographic JWT validation** using the `jwt_decoder.py` module with PyJWT library before any requests reach the Platform backend.

## Core JWT Infrastructure

### 1. `src/quilt_mcp/services/jwt_decoder.py` (256 lines)

**Purpose:** Core JWT signature validation and secret management

**What it does:**

- Validates JWT signatures using PyJWT library with HS256 algorithm
- Fetches and caches JWT signing secrets from two sources:
  - `MCP_JWT_SECRET` environment variable (development/testing)
  - AWS SSM Parameter Store via `MCP_JWT_SECRET_SSM_PARAMETER` (production)
- Implements secret rotation support with caching:
  - Soft refresh: 300 seconds (5 minutes)
  - Hard TTL: 3600 seconds (1 hour)
  - Maintains previous secret for rotation window
- Validates JWT claims structure:
  - **Required:** `exp` (expiration timestamp)
  - **Required:** `id` or `uuid` (at least one must be present)
  - **Optional:** `iss` (issuer, validated if `MCP_JWT_ISSUER` env var set)
  - **Optional:** `aud` (audience, validated if `MCP_JWT_AUDIENCE` env var set)
  - **Strict:** Rejects any additional claims beyond `{id, uuid, exp}`

**Key classes:**

- `JwtSecretProvider` - Manages secret fetching, caching, rotation
- `JwtDecoder` - JWT validation logic
- `JwtDecodeError` - Custom exception with error codes
- `JwtConfigError` - Configuration validation errors

**Error codes returned:**

- `missing_token` - No token provided
- `invalid_token` - Malformed JWT structure
- `token_expired` - JWT exp claim is past
- `invalid_issuer` - iss claim doesn't match expected
- `invalid_audience` - aud claim doesn't match expected
- `invalid_signature` - Signature validation failed (tries rotation)
- `invalid_claims` - Missing required claims or extra claims present

**Secret rotation logic:**
On signature validation failure, attempts to decode with:

1. Previous cached secret (if within HARD_TTL)
2. Force-refreshed secret from SSM
If both fail, raises `invalid_signature` error

**Configuration requirements:**

- JWT mode requires either `MCP_JWT_SECRET` OR `MCP_JWT_SECRET_SSM_PARAMETER`
- SSM mode additionally requires `AWS_REGION` or `AWS_DEFAULT_REGION`
- Calls `validate_config()` to check requirements before operation

**Thread safety:** Uses threading.Lock for secret cache access

### 2. `src/quilt_mcp/middleware/jwt_middleware.py` (96 lines)

**Purpose:** Starlette HTTP middleware for JWT authentication

**What it does:**

- Intercepts all HTTP requests to MCP server
- Extracts `Authorization` header from requests
- Validates Bearer token format
- Calls `jwt_decoder.decode()` for cryptographic validation
- Populates `RuntimeAuthState` with token and validated claims
- Manages runtime context lifecycle per request
- Records authentication metrics via `auth_metrics` service

**Request flow:**

1. Check if path is in `HEALTH_PATHS` (`/`, `/health`, `/healthz`) - skip JWT
2. Check `require_jwt` flag - if False, skip validation
3. Extract Authorization header - 401 if missing
4. Validate "Bearer " prefix - 401 if wrong format
5. Extract token - 401 if empty
6. Call `jwt_decoder.decode(token)` - 403 if invalid
7. Create `RuntimeAuthState` with token + claims
8. Push context onto runtime stack
9. Call next middleware/handler
10. Reset runtime context (cleanup)

**Error responses:**

- 401: Missing/invalid Authorization header format
- 403: JWT validation failed (signature, expiration, claims)

**Logging:**

- Logs JWT validation failures with request_id
- Logs validation timing (ms) for performance monitoring
- Extracts request_id from `mcp-session-id` or `x-request-id` headers

**Metrics recorded:**

- `jwt_validation("success", duration_ms=X)` - Successful validation
- `jwt_validation("failure", duration_ms=X, reason=code)` - Failed validation

**Configuration:**

- `require_jwt` parameter controls enforcement (set by `mode_config.requires_jwt`)
- In IAM mode: middleware present but doesn't enforce (`require_jwt=False`)
- In Platform mode: middleware enforces JWT on all non-health endpoints

**Integration point:** Added to Starlette app in `utils.py:648-656`

### 3. `src/quilt_mcp/services/jwt_auth_service.py` (234 lines)

**Purpose:** Exchange JWT tokens for AWS temporary credentials

**What it does:**

- Takes validated JWT access token
- Exchanges it for temporary AWS credentials by calling Platform backend
- Caches credentials with automatic refresh
- Creates boto3.Session with temporary credentials

**Key methods:**

`get_boto3_session()` (lines 53-88):

1. Gets `RuntimeAuthState` from context
2. Validates JWT (or uses pre-validated claims)
3. Calls `_get_or_refresh_credentials()` for AWS creds
4. Returns boto3.Session configured with temporary credentials

`_get_or_refresh_credentials()` (lines 90-107):

- Thread-safe credential caching
- Checks if cached credentials still valid
- Fetches new credentials if expired or missing

`_are_credentials_valid()` (lines 109-132):

- Parses ISO 8601 expiration timestamp from AWS
- Checks expiration with 5-minute buffer
- Returns False if no credentials or expired

`_fetch_temporary_credentials()` (lines 134-183):

- Makes HTTP GET to `{QUILT_REGISTRY_URL}/api/auth/get_credentials`
- Sends JWT in `Authorization: Bearer` header
- Validates response contains required fields:
  - `AccessKeyId`
  - `SecretAccessKey`
  - `SessionToken`
  - `Expiration`
- Returns credential dictionary

`is_valid()` (lines 185-209):

- Validates JWT structure and expiration
- Checks allowed claims (`{id, uuid, exp}`)
- Requires at least one of `id` or `uuid`
- Checks `exp` timestamp > current time

`get_user_identity()` (lines 211-233):

- Extracts user info from JWT claims
- Returns dict with `user_id`, `email`, `name`
- Only allows whitelisted claims

**Error handling:**

- `JwtAuthServiceError` with error codes:
  - `missing_jwt` - No auth token in context
  - `missing_config` - QUILT_REGISTRY_URL not set
  - `invalid_jwt` - Token invalid/expired (401 from backend)
  - `forbidden` - Access denied (403 from backend)
  - `invalid_response` - Credential response missing fields
  - `timeout` - Request timeout (30s)
  - `request_failed` - Other HTTP errors

**Thread safety:** Uses threading.Lock for credential cache

**Dependencies:**

- Requires `QUILT_REGISTRY_URL` environment variable
- Uses requests library for HTTP calls
- Depends on `jwt_decoder` for token validation

### 4. `scripts/generate_test_jwt.py` (52 lines)

**Purpose:** CLI utility for generating test JWTs during development

**What it does:**

- Generates HS256-signed JWT tokens for testing
- Supports customizable claims and expiration
- Uses PyJWT library directly

**CLI arguments:**

- `--id` (required): User id claim
- `--uuid` (required): User uuid claim
- `--secret` (default: "dev-secret"): HS256 signing secret
- `--expires-in` (default: 3600): Expiration in seconds
- `--issuer`: Optional iss claim
- `--audience`: Optional aud claim
- `--extra-claims`: Additional JSON claims to merge

**Output:** Prints JWT token to stdout

**Example usage:**

```bash
python scripts/generate_test_jwt.py \
  --id=user-123 \
  --uuid=uuid-456 \
  --secret=dev-secret \
  --expires-in=3600
```

**Referenced in:**

- `scripts/test-multiuser.py`
- `scripts/tests/test_jwt_search.py`
- `scripts/mcp-test.py`
- Various spec documents (a10, a11, a15, a16)

**Current status:** Unclear if actively maintained or superseded by newer test infrastructure

## Integration Points

### How JWT Infrastructure Wires Together

**HTTP Request Flow (Platform Mode):**

```
HTTP Request
  ↓
JwtAuthMiddleware.dispatch()
  ↓
jwt_decoder.decode(token)  ← Cryptographic validation
  ↓
RuntimeAuthState(token, claims)
  ↓
push_runtime_context()
  ↓
MCP Tool Handler
  ↓
jwt_auth_service.get_boto3_session()
  ↓
_fetch_temporary_credentials(token)  ← Exchange for AWS creds
  ↓
Platform Backend: /api/auth/get_credentials
  ↓
boto3.Session (temporary AWS credentials)
  ↓
S3/AWS Operations
```

**Configuration Loading:**

```
main.py startup
  ↓
get_mode_config()
  ↓
mode_config.validate()
  ↓
mode_config.requires_jwt → passed to JwtAuthMiddleware
  ↓
jwt_decoder.validate_config() ← Checks secret configuration
```

**Secret Management:**

```
JwtSecretProvider initialization
  ↓
Check MCP_JWT_SECRET env var
  ↓ (if not set)
Check MCP_JWT_SECRET_SSM_PARAMETER env var
  ↓
Fetch from SSM with boto3
  ↓
Cache with 5min soft refresh, 1hr hard TTL
  ↓
On signature failure: try previous secret + force refresh
```

### Runtime Context Management

**Context Stack (per-request lifecycle):**

```python
# Middleware creates auth state
auth_state = RuntimeAuthState(
    scheme="Bearer",
    access_token=token,
    claims=validated_claims
)

# Push onto context stack
token_handle = push_runtime_context(
    environment=get_runtime_environment(),
    auth=auth_state
)

try:
    # Request handling (tools can access via get_runtime_auth())
    response = await call_next(request)
finally:
    # Always cleanup
    reset_runtime_context(token_handle)
```

**Context accessed by:**

- `jwt_auth_service.py` - Gets auth state for credential exchange
- `context/user_extraction.py` - Gets user identity
- `backends/platform_backend.py` - Gets token for GraphQL requests
- Tool handlers - Can access user context

### Mode-Based Behavior

**Platform Mode (requires_jwt=True):**

- `JwtAuthMiddleware` enforces JWT on all non-health endpoints
- Every request must have valid Bearer token
- Token validated cryptographically by `jwt_decoder`
- Token exchanged for AWS credentials via Platform backend
- 401/403 errors returned for invalid tokens

**IAM Mode (requires_jwt=False):**

- `JwtAuthMiddleware` present but doesn't enforce
- Requests proceed without JWT validation
- AWS credentials from ambient IAM role or credentials file
- `jwt_auth_service` not used

**Local Development:**

- Uses `MCP_JWT_SECRET` from environment or .env
- No SSM secret fetching
- Simpler configuration for testing

## Test Coverage

### Unit Tests

**`tests/unit/test_jwt_auth_service.py` (43 lines):**

- Tests missing JWT detection (error code: `missing_jwt`)
- Tests missing QUILT_REGISTRY_URL detection (error code: `missing_config`)
- Uses `RuntimeAuthState` to simulate auth context
- Tests both with pre-validated claims and without

**`tests/unit/services/test_jwt_auth_service.py` (110 lines):**

- Tests `is_valid()` behavior:
  - False without auth
  - Respects expiration timestamp
  - False on invalid token (via stubbed decoder)
  - False when missing `exp` claim
- Tests `get_user_identity()`:
  - Extracts user_id from claims
  - Falls back to decoding token
  - Returns None for missing user
- Uses monkeypatch to stub time and decoder
- Tests with synthetic claims data

**What these tests cover:**

- Pure business logic (expiration math, claim validation)
- Configuration validation (missing env vars)
- Error code coverage
- Edge cases in state management

**What these tests DON'T cover:**

- Real JWT signature validation (no real keys/signing)
- Actual AWS credential exchange (no HTTP mocking shown)
- Thread-safe credential caching under load
- Security guarantees of cryptographic operations

### Integration/E2E Tests

**Not found in unit test directories:**

- No tests of jwt_middleware.py HTTP flow
- No tests of jwt_decoder.py cryptographic validation
- No tests of SSM secret fetching
- No tests of secret rotation logic
- No end-to-end JWT validation with real tokens

**Mentioned in specs but not examined:**

- E2E tests may exist in `tests/e2e/` (not read in this analysis)
- Functional tests may exist in `tests/func/` (not read in this analysis)
- New test infrastructure in development (A18 spec)

## Dependencies

**External Libraries:**

- `PyJWT` - JWT encoding/decoding library
- `boto3` - AWS SDK (SSM parameter access, Session creation)
- `requests` - HTTP client for credential exchange
- `starlette` - ASGI middleware framework
- `fastmcp` - MCP server framework

**Internal Dependencies:**

- `runtime_context` - Thread-local context management
- `auth_metrics` - Metrics recording service
- `config` - Mode configuration (requires_jwt flag)

**Environment Variables Used:**

- `MCP_JWT_SECRET` - Signing secret (dev/test)
- `MCP_JWT_SECRET_SSM_PARAMETER` - SSM parameter name (production)
- `MCP_JWT_ISSUER` - Expected issuer claim (optional)
- `MCP_JWT_AUDIENCE` - Expected audience claim (optional)
- `QUILT_REGISTRY_URL` - Platform backend URL for credential exchange
- `AWS_REGION` / `AWS_DEFAULT_REGION` - For SSM access

## Claims Validation Rules

### Allowed Claims (Strict Whitelist)

**Required claims:**

- `exp` (number): Unix timestamp, must be > current time
- `id` OR `uuid` (string): At least one must be present

**Optional claims:**

- `iss` (string): Validated if `MCP_JWT_ISSUER` set
- `aud` (string): Validated if `MCP_JWT_AUDIENCE` set

**Rejected:**

- Any additional claims beyond `{id, uuid, exp, iss, aud}` cause validation failure
- Example: Claims with `email`, `name`, `roles`, etc. are **rejected**

### Validation Locations

**jwt_decoder.py (lines 187-195):**

```python
allowed_keys = {"id", "uuid", "exp"}
if not (claims.get("id") or claims.get("uuid")):
    raise JwtDecodeError("invalid_claims", "JWT claims must include id or uuid.")
extra_keys = set(claims.keys()) - allowed_keys
if extra_keys:
    raise JwtDecodeError(
        "invalid_claims",
        f"JWT claims include unsupported fields: {sorted(extra_keys)}.",
    )
```

**jwt_auth_service.py (lines 197-198):**

```python
_ALLOWED_CLAIMS = {"id", "uuid", "exp"}
if set(claims.keys()) - self._ALLOWED_CLAIMS:
    return False
```

**Implication:** The MCP server enforces a very strict JWT structure, rejecting standard claims like `email`, `name`, `sub`, etc.

## Security Characteristics

### What Is Validated

**Cryptographic validation:**

- HS256 signature verification with shared secret
- Token structure (must have 3 dot-separated parts)
- Expiration timestamp (`exp` claim)
- Issuer (`iss` claim, if configured)
- Audience (`aud` claim, if configured)

**Claims validation:**

- Presence of `id` or `uuid`
- Absence of unexpected claims (strict whitelist)
- Type checking (claims must be dict)

**Configuration validation:**

- Secret source availability (env or SSM)
- AWS region for SSM access
- Platform backend URL for credential exchange

### What Is NOT Validated

**Not checked by MCP server:**

- User permissions/authorization (delegated to Platform backend)
- Token revocation/blocklist (no revocation mechanism)
- Token "freshness" beyond expiration (no `iat` validation)
- Rate limiting per token/user
- Multi-tenancy/organization boundaries

**Trust assumptions:**

- Shared secret is secure (HS256 symmetric key)
- Platform backend properly validates user permissions
- AWS temporary credentials from Platform backend are trustworthy
- No JWT replay attack protection (relies on short expiration)

## Usage in Codebase

### Files Importing JWT Components

**jwt_middleware.py imported by:**

- `src/quilt_mcp/utils.py` (lines 648-656) - Adds to ASGI app

**jwt_decoder.py imported by:**

- `src/quilt_mcp/middleware/jwt_middleware.py`
- `src/quilt_mcp/services/jwt_auth_service.py`
- `src/quilt_mcp/context/user_extraction.py`
- `src/quilt_mcp/backends/platform_backend.py`
- `src/quilt_mcp/services/auth_service.py`
- Test files

**jwt_auth_service.py imported by:**

- Backend implementations (for credential exchange)
- Auth service orchestration
- Tests

**generate_test_jwt.py imported by:**

- Referenced in specs, may be called by test scripts
- Not imported as module (CLI utility)

### Production Usage

**Active in production:**

- `jwt_decoder.py` - Critical security component
- `jwt_middleware.py` - HTTP authentication boundary
- `jwt_auth_service.py` - AWS credential exchange

**Development/testing only:**

- `generate_test_jwt.py` - Test utility

**Configuration determines usage:**

- Platform mode (multiuser): All JWT infrastructure active
- IAM mode (local dev): JWT infrastructure present but not enforced
- HTTP transport: JWT middleware in request path
- stdio transport: JWT middleware not in request path (stdio doesn't use HTTP)

## Environment Variables Reference

### JWT Authentication Configuration

**JWT Secret Management (one required):**

- `MCP_JWT_SECRET` (string)
  - **Purpose:** HS256 signing secret for JWT validation
  - **Used by:** `jwt_decoder.py`
  - **Environment:** Development, testing, local deployments
  - **Priority:** Checked first, takes precedence over SSM
  - **Validation:** Required in multiuser mode if SSM not configured
  - **Example:** `"dev-secret"`, `"my-secure-random-key"`
  - **Security:** Should be long random string, kept secret

- `MCP_JWT_SECRET_SSM_PARAMETER` (string)
  - **Purpose:** AWS SSM Parameter Store path containing JWT signing secret
  - **Used by:** `jwt_decoder.py` → `JwtSecretProvider`
  - **Environment:** Production deployments
  - **Requires:** `AWS_REGION` or `AWS_DEFAULT_REGION` must also be set
  - **Caching:** Secret cached with 5min soft refresh, 1hr hard TTL
  - **Rotation:** Supports graceful rotation (validates with previous secret)
  - **Example:** `"/prod/mcp/jwt-secret"`, `"/quilt-mcp/jwt-signing-key"`
  - **AWS Permissions:** Requires `ssm:GetParameter` permission

**JWT Claims Validation (optional):**

- `MCP_JWT_ISSUER` (string)
  - **Purpose:** Expected JWT `iss` (issuer) claim value
  - **Used by:** `jwt_decoder.decode()` validation
  - **Effect:** If set, tokens without matching `iss` are rejected
  - **Error code:** `invalid_issuer`
  - **Example:** `"https://auth.quiltdata.com"`, `"quilt-platform"`

- `MCP_JWT_AUDIENCE` (string)
  - **Purpose:** Expected JWT `aud` (audience) claim value
  - **Used by:** `jwt_decoder.decode()` validation
  - **Effect:** If set, tokens without matching `aud` are rejected
  - **Error code:** `invalid_audience`
  - **Example:** `"quilt-mcp-server"`, `"mcp-api"`

### Platform Backend Configuration

- `QUILT_REGISTRY_URL` (string, **required in multiuser mode**)
  - **Purpose:** Base URL for Quilt Platform registry API
  - **Used by:**
    - `jwt_auth_service.py` - Credential exchange endpoint
    - `platform_backend.py` - GraphQL endpoint construction
  - **Endpoints called:**
    - `{QUILT_REGISTRY_URL}/api/auth/get_credentials` (JWT → AWS creds)
    - `{QUILT_REGISTRY_URL}/graphql` (GraphQL queries, unless `QUILT_GRAPHQL_ENDPOINT` set)
  - **Example:** `"https://registry.quiltdata.com"`
  - **Validation:** Must be set in multiuser mode (checked by `config.py`)

- `QUILT_CATALOG_URL` (string, **required in multiuser mode**)
  - **Purpose:** Base URL for Quilt Platform catalog frontend
  - **Used by:** `platform_backend.py`
  - **Example:** `"https://catalog.quiltdata.com"`
  - **Validation:** Must be set in multiuser mode (checked by `config.py`)

- `QUILT_GRAPHQL_ENDPOINT` (string, optional)
  - **Purpose:** Override GraphQL endpoint URL
  - **Used by:** `platform_backend.py`
  - **Default:** Derived from `QUILT_REGISTRY_URL` as `{url}/graphql`
  - **Example:** `"https://custom-graphql.quiltdata.com/graphql"`

### Mode Configuration

- `QUILT_MULTIUSER_MODE` (boolean: "true"/"false"/"1"/"0"/"yes"/"no"/"on"/"off")
  - **Purpose:** Master switch controlling deployment mode
  - **Used by:** `config.py` → `ModeConfig`
  - **Default:** `false` (local development mode)
  - **Effects when `true` (multiuser/Platform mode):**
    - `requires_jwt = true` → JWT middleware enforces authentication
    - `backend_type = "graphql"` → Uses Platform backend
    - `default_transport = "http"` → HTTP server instead of stdio
    - `requires_graphql = true` → GraphQL queries required
    - `allows_filesystem_state = false` → No local filesystem caching
    - `allows_quilt3_library = false` → No quilt3 Python library usage
  - **Effects when `false` (local dev/IAM mode):**
    - `requires_jwt = false` → JWT middleware present but not enforced
    - `backend_type = "quilt3"` → Uses Quilt3 backend
    - `default_transport = "stdio"` → stdio transport for Claude Desktop
    - `allows_filesystem_state = true` → Local caching allowed
    - `allows_quilt3_library = true` → Can use quilt3 Python library
  - **Validation:** When `true`, requires `MCP_JWT_SECRET`, `QUILT_CATALOG_URL`, `QUILT_REGISTRY_URL`

### Transport Configuration

- `FASTMCP_TRANSPORT` (string: "stdio"/"http"/"sse"/"streamable-http")
  - **Purpose:** MCP protocol transport mechanism
  - **Used by:** `main.py`, `utils.py`, FastMCP framework
  - **Default:** Set by `mode_config.default_transport` ("stdio" for local, "http" for multiuser)
  - **Can override:** Yes, environment variable takes precedence
  - **Effect:** Determines server startup mode (stdio vs HTTP server)

- `FASTMCP_HOST` / `FASTMCP_ADDR` (string, HTTP mode only)
  - **Purpose:** Host address for HTTP server binding
  - **Default:** `"127.0.0.1"`
  - **Example:** `"0.0.0.0"` (all interfaces), `"localhost"`

- `FASTMCP_PORT` (integer, HTTP mode only)
  - **Purpose:** Port for HTTP server
  - **Default:** `8000`
  - **Example:** `"3000"`, `"8080"`

### AWS Configuration (for SSM secret access)

- `AWS_REGION` (string, required for SSM)
  - **Purpose:** AWS region for SSM Parameter Store access
  - **Used by:** `jwt_decoder.py` → boto3 SSM client
  - **Required when:** `MCP_JWT_SECRET_SSM_PARAMETER` is set
  - **Example:** `"us-east-1"`, `"us-west-2"`

- `AWS_DEFAULT_REGION` (string, fallback)
  - **Purpose:** Alternative to `AWS_REGION`
  - **Priority:** `AWS_REGION` checked first
  - **Used by:** Same SSM client initialization

### Other Configuration

- `MCP_SKIP_BANNER` (boolean: "true"/"false")
  - **Purpose:** Skip server startup banner
  - **Used by:** `main.py`
  - **Default:** `false`
  - **Use case:** Multi-server setups, cleaner logs

- `FASTMCP_DEBUG` (boolean: "1"/"0")
  - **Purpose:** Enable debug output
  - **Referenced in:** Error messages
  - **Example:** `FASTMCP_DEBUG=1 uvx quilt-mcp`

- `QUILT_SERVICE_TIMEOUT` (integer, seconds)
  - **Purpose:** Timeout for HTTP requests to Platform backend
  - **Used by:** `http_config.SERVICE_TIMEOUT`
  - **Default:** `60`
  - **Applies to:** GraphQL queries, API calls

## Configuration Dependencies

### Local Development Mode (requires_jwt=False)

**Minimum required:**

- None - works with ambient AWS credentials

**Optional:**

- `AWS_PROFILE` - For AWS credential selection
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - Explicit AWS credentials

### Platform/Multiuser Mode (requires_jwt=True)

**Required environment variables:**

```bash
QUILT_MULTIUSER_MODE=true
QUILT_CATALOG_URL=https://catalog.example.com
QUILT_REGISTRY_URL=https://registry.example.com

# Secret source (choose one):
MCP_JWT_SECRET=dev-secret-for-testing
# OR
MCP_JWT_SECRET_SSM_PARAMETER=/prod/mcp/jwt-secret
AWS_REGION=us-east-1
```

**Optional but recommended:**

```bash
MCP_JWT_ISSUER=https://auth.example.com
MCP_JWT_AUDIENCE=quilt-mcp-server
QUILT_GRAPHQL_ENDPOINT=https://custom-graphql.example.com/graphql
QUILT_SERVICE_TIMEOUT=30
```

### Validation Behavior

**Startup validation (`main.py`):**

1. Parse `QUILT_MULTIUSER_MODE`
2. Call `mode_config.validate()`
3. If multiuser mode, check:
   - `MCP_JWT_SECRET` is set
   - `QUILT_CATALOG_URL` is set
   - `QUILT_REGISTRY_URL` is set
4. Exit with error if validation fails

**Runtime validation (`jwt_decoder.py`):**

1. Call `jwt_decoder.validate_config()` on first use
2. Check secret source:
   - If `MCP_JWT_SECRET` set: Valid
   - Else if `MCP_JWT_SECRET_SSM_PARAMETER` set: Check `AWS_REGION`
   - Else: Raise `JwtConfigError`

**Credential exchange validation (`jwt_auth_service.py`):**

1. Check `QUILT_REGISTRY_URL` on each credential fetch
2. Raise `JwtAuthServiceError(code="missing_config")` if not set

## Configuration in .env File

**Current .env structure (from repository):**

The repository contains a `.env` file (not checked into git, local only) used for development via `dotenv`. This file is loaded by `main.py:89` via `load_dotenv()`.

**Note:** Production deployments do NOT use `.env` - they use environment variables from container/shell environment or MCP client configuration (e.g., Claude Desktop settings).

**Development workflow:**

1. Copy `.env.backup` or create `.env`
2. Set mode: `QUILT_MULTIUSER_MODE=false` (local) or `true` (platform)
3. If platform mode, add all required multiuser variables
4. Run: `make run` or `make run-inspector`

## Summary

### Current State

The quilt-mcp-server has a complete JWT authentication system that:

1. **Validates JWT signatures cryptographically** using PyJWT + HS256
2. **Manages secret rotation** with SSM integration
3. **Enforces strict claims structure** (rejects extra claims)
4. **Exchanges JWTs for AWS credentials** via Platform backend
5. **Operates as HTTP middleware** for request-level authentication
6. **Caches credentials and secrets** for performance

This contradicts the initial claim that "MCP server never validates JWTs" - it performs full cryptographic validation before forwarding to backends.

### Architecture Pattern

The system uses a layered authentication approach:

- **Layer 1:** JWT signature validation (MCP middleware)
- **Layer 2:** Credential exchange (MCP to Platform backend)
- **Layer 3:** Authorization (Platform backend GraphQL)

### Configuration Complexity

The JWT system requires careful coordination of 10+ environment variables across:

- Mode selection (1 variable)
- JWT secret management (2 variables, 1 required)
- Platform endpoints (2-3 variables)
- Claims validation (2 optional variables)
- AWS region (1-2 variables for SSM)
- Transport configuration (3 variables)

**Critical for operation:**

- Platform mode: 4 required variables minimum
- SSM-based secret: 2 additional variables required
- Claims validation: 2 additional optional variables

### Test Coverage Gap

Significant unit test coverage exists for business logic, but integration tests for:

- Real JWT validation with signed tokens
- SSM secret fetching
- Credential exchange HTTP flow
- Secret rotation scenarios

appear to be missing or not yet examined in this analysis.
