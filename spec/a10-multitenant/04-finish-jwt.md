# JWT Authentication with Toggleable Auth Modes

**Status**: Draft
**Created**: 2026-01-28
**Objective**: Re-enable JWT authentication with seamless toggling between IAM and JWT auth modes

## Problem Statement

JWT authentication was fully implemented (commit `f36c689`, Oct 18, 2025) and then completely removed (commit `0d5c917`, Dec 4, 2025). The removal suggests that JWT wasn't needed for current use cases, which are primarily local/IAM-based development.

However, for **multitenant production deployment** (see [01-stateless.md](01-stateless.md)), JWT authentication is **essential**:

1. **No local credentials** - Production containers must not use `~/.quilt/` or `~/.aws/` credential files
2. **Per-user isolation** - Each request must assume a different AWS role based on JWT claims
3. **Stateless operation** - No persistent credential storage across requests
4. **Multi-user support** - Same container serves multiple users with different permissions

**The challenge**: Re-enable JWT while maintaining backward compatibility for local development, which relies on IAM credentials.

## Current State Analysis

### What Still Exists (JWT-Ready Infrastructure)

**1. Runtime Context** ([src/quilt_mcp/runtime_context.py](src/quilt_mcp/runtime_context.py))

Complete `RuntimeAuthState` dataclass designed for JWT:

```python
@dataclass(frozen=True)
class RuntimeAuthState:
    scheme: str                              # "Bearer" for JWT
    access_token: Optional[str] = None       # JWT token string
    claims: Dict[str, Any] = ...             # Decoded JWT claims
    extras: Dict[str, Any] = ...             # Additional context
```

Available functions:

- `get_runtime_auth()` - Returns current auth state
- `get_runtime_access_token()` - Extracts JWT token
- `get_runtime_claims()` - Returns decoded claims
- `set_runtime_auth()` - Updates auth state
- `push_runtime_context()` - Creates request scope
- `clear_runtime_auth()` - Resets auth

**2. HTTP Middleware Hooks** ([src/quilt_mcp/utils.py:382-428](src/quilt_mcp/utils.py#L382-L428))

The `build_http_app()` function has:

- CORS middleware allowing `Authorization` headers
- Request context management
- Placeholders for JWT extraction middleware

**3. Test Configuration** ([tests/conftest.py:124-142](tests/conftest.py#L124-L142))

Tests explicitly disable JWT and clear runtime auth:

```python
os.environ["MCP_REQUIRE_JWT"] = "false"
os.environ.pop("MCP_ENHANCED_JWT_SECRET", None)
clear_runtime_auth()
```

This shows the toggle mechanism already exists in concept.

### What Was Removed (Needs Restoration)

**1. JWT Decoder Service** (was: `src/quilt_mcp/services/jwt_decoder.py`, 123 lines)

Responsibilities:

- JWT parsing and base64 decoding
- Signature verification (HS256)
- Claims normalization and decompression
- Permission abbreviation expansion (e.g., "g" → "s3:GetObject")
- Bucket pattern expansion (prefixes, suffixes, groups)

**2. Bearer Auth Service** (was: `src/quilt_mcp/services/bearer_auth_service.py`, 403 lines)

Responsibilities:

- JWT secret resolution (env vars, AWS SSM)
- Authorization header extraction
- JWT validation and claims extraction
- Tool permission checking
- Boto3 session construction from JWT credentials
- AWS role assumption with JWT claims

**3. JWT Middleware** (was: in `src/quilt_mcp/utils.py`)

Responsibilities:

- Extract `Authorization: Bearer` header from requests
- Decode and validate JWT
- Populate RuntimeAuthState
- Handle JWT errors gracefully

**4. PyJWT Dependency** (was: in `pyproject.toml`)

Need to restore:

```toml
pyjwt = "^2.8.0"
```

### What Exists Only As Build Artifacts

Full implementations remain in `build/lib/quilt_mcp/services/`:

- `bearer_auth_service.py` (393 lines) - Complete but may be outdated
- `jwt_decoder.py` (123 lines) - Complete but may be outdated

**Risk**: Build artifacts may be stale relative to current codebase structure.

## Requirements

### Functional Requirements

**FR1: Dual Auth Mode Support**

- Must support **two distinct authentication modes**:
  - **IAM Mode** (default for local development): Uses AWS credentials from environment, profiles, or quilt3 session
  - **JWT Mode** (required for production): Uses JWT tokens from `Authorization: Bearer` headers
- Mode selection must be **explicit and unambiguous**
- Both modes must work correctly without interference

**FR2: JWT Mode Capabilities**

- Extract JWT from `Authorization: Bearer` header
- Validate JWT signature using configured secret (from env or AWS SSM)
- Decode JWT claims and populate RuntimeAuthState
- Assume AWS role based on JWT claims (role ARN, session tags, source identity)
- Check tool permissions against JWT claims
- Reject requests without valid JWT when in JWT mode

**FR3: IAM Mode Capabilities (Existing Behavior)**

- Use AWS credentials from standard locations:
  - Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
  - AWS profiles (`AWS_PROFILE`)
  - quilt3 session credentials (`quilt3.session`)
  - IAM roles (when running on EC2/ECS/Lambda)
- No JWT validation or claims checking
- No per-request role assumption (uses ambient credentials)

**FR4: Mode Toggling**

- Controlled by environment variable: `MCP_REQUIRE_JWT` (boolean)
  - `false` (default): Use IAM credentials only, ignore JWT headers
  - `true`: Require JWT authentication, reject without valid JWT
- Mode must be determined **at startup** (not per-request)
- Startup logs must clearly indicate active auth mode

**FR5: Clear Error Handling**

- JWT mode without JWT → 401 with message: "JWT authentication required. Provide Authorization: Bearer header."
- JWT mode with invalid JWT → 403 with details: "Invalid JWT: <reason>"
- JWT mode with insufficient permissions → 403 with details: "Tool requires permissions: <list>"
- IAM mode with JWT header → **Ignore JWT**, use IAM credentials (no error)
- Errors must **not** suggest local auth methods (e.g., "run quilt3 login") in production mode

**FR6: Security Requirements**

- JWT secrets must **never** be logged or exposed
- JWT validation must verify:
  - Signature (HS256 or RS256)
  - Expiration (`exp` claim)
  - Issuer (`iss` claim, if configured)
  - Audience (`aud` claim, if configured)
- Failed authentication attempts must be logged (without token contents)
- STS role assumption must use:
  - `SourceIdentity` from JWT `sub` claim for audit trails
  - `Tags` from JWT claims for ABAC (Attribute-Based Access Control)
  - `RoleSessionName` derived from user identifier

### Non-Functional Requirements

**NFR1: Backward Compatibility**

- Existing local development workflows must work **without any changes**
- Default mode must be IAM (preserve current behavior)
- Tests must continue to work without JWT configuration

**NFR2: Performance**

- JWT secret caching (if from SSM): refresh every 5 minutes, cache for 1 hour
- Decoded JWT claims caching: per-request scope only (no cross-request caching)
- No performance degradation in IAM mode

**NFR3: Observability**

- Startup logs show active auth mode
- JWT validation failures logged with request ID
- Successful JWT auth logged with user identity (sub claim)
- Tracking of:
  - Auth mode distribution (IAM vs JWT requests)
  - JWT validation latency
  - JWT validation failures (by reason)
  - Role assumption attempts/failures

**NFR4: Configuration Simplicity**

- Minimal environment variables required for each mode
- Clear documentation of all config options
- Sensible defaults for each mode
- Configuration validation at startup with clear error messages

## Design: Toggleable Authentication Architecture

### Mode Selection Logic

**Startup Sequence**:

1. Read `MCP_REQUIRE_JWT` environment variable (boolean)
2. Validate configuration (e.g., JWT mode requires JWT secret)
3. Initialize appropriate auth service
4. Log selected mode and configuration
5. Register HTTP middleware (if applicable)

**Decision Matrix**:

| MCP_REQUIRE_JWT | Result   | Notes                         |
|-----------------|----------|-------------------------------|
| `false`         | IAM Mode | Default - Use AWS credentials |
| `true`          | JWT Mode | Require JWT authentication    |
| (unset)         | IAM Mode | Default to IAM                |

**Environment Variable**:

- `MCP_REQUIRE_JWT` - Boolean (true/false), defaults to false

### Component Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FastMCP Application                   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              HTTP Middleware (if transport=http)         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  JWT Auth Middleware (only if MCP_REQUIRE_JWT=true) │   │
│  │  - Extract Authorization header                   │   │
│  │  - Validate and decode JWT                        │   │
│  │  - Populate RuntimeAuthState                      │   │
│  │  - Handle errors (401/403)                        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Tool Invocation Layer                  │
│  ┌──────────────┐         ┌───────────────────────┐    │
│  │ AuthService  │◄────────│ get_auth_service()    │    │
│  │  (Factory)   │         │ - Returns IAMAuth or  │    │
│  │              │         │   JWTAuth based on    │    │
│  │              │         │   runtime mode        │    │
│  └──────────────┘         └───────────────────────┘    │
│         │                                                │
│         ▼                                                │
│  ┌──────────────────────┬──────────────────────────┐   │
│  │   IAMAuthService     │    JWTAuthService        │   │
│  │   ──────────────     │    ──────────────        │   │
│  │ - Read AWS creds     │ - Get RuntimeAuthState   │   │
│  │   from env/profile   │ - Check tool permissions │   │
│  │ - Use quilt3 session │ - Assume role from JWT   │   │
│  │ - Return boto3       │ - Return scoped boto3    │   │
│  │   session            │   session                │   │
│  └──────────────────────┴──────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   AWS SDK (boto3)                        │
│           (Uses credentials from auth service)           │
└─────────────────────────────────────────────────────────┘
```

### File Structure

**New Files**:

- `src/quilt_mcp/services/jwt_decoder.py` - JWT parsing and claims extraction
- `src/quilt_mcp/services/jwt_auth_service.py` - JWT-based authentication (renamed from bearer_auth_service)
- `src/quilt_mcp/services/iam_auth_service.py` - IAM-based authentication (extracted from current auth_service)
- `src/quilt_mcp/middleware/jwt_middleware.py` - HTTP middleware for JWT extraction

**Modified Files**:

- `src/quilt_mcp/services/auth_service.py` - Becomes factory/facade for IAM/JWT auth
- `src/quilt_mcp/utils.py` - Integrate JWT middleware into HTTP app
- `pyproject.toml` - Add pyjwt dependency
- `tests/conftest.py` - Already configured for mode toggling
- `README.md` - Document auth modes and configuration

**Removed Complexity**:

- Merge `bearer_auth_service.py` concepts into `jwt_auth_service.py` with clearer naming
- Simplify permission checking (may be overkill for initial implementation)
- Consider deferring ABAC/fine-grained permissions to Phase 2

## What Needs to Change

### Phase 1: Core JWT Infrastructure (Must Have)

#### Task 1.1: Restore JWT Decoder Service

**Goal**: Create JWT parsing and validation service

**Where**: `src/quilt_mcp/services/jwt_decoder.py`

**What to implement**:

- [ ] Retrieve JWT implementation from commit `f36c689` or build artifacts
- [ ] Review and update for compatibility with current codebase
- [ ] Implement JWT signature verification (HS256 support required, RS256 optional)
- [ ] Implement claims extraction and normalization
- [ ] Implement expiration validation (`exp` claim)
- [ ] Add optional issuer (`iss`) and audience (`aud`) validation
- [ ] Create comprehensive unit tests for all validation paths
- [ ] Document expected JWT structure and required claims

**Configuration needed**:

- `MCP_JWT_SECRET` - Shared secret for HS256 (or path to public key for RS256)
- `MCP_JWT_ISSUER` - Expected issuer (optional)
- `MCP_JWT_AUDIENCE` - Expected audience (optional)
- `MCP_JWT_ALGORITHM` - Algorithm (default: HS256)

**Success criteria**:

- ✅ Validates well-formed JWTs
- ✅ Rejects expired JWTs
- ✅ Rejects JWTs with invalid signatures
- ✅ Extracts all standard claims (`sub`, `exp`, `iat`, `iss`, `aud`)
- ✅ Handles custom claims (permissions, role ARN, etc.)
- ✅ Clear error messages for all failure cases

#### Task 1.2: Create JWT Auth Service

**Goal**: Implement authentication service that uses JWT for AWS access

**Where**: `src/quilt_mcp/services/jwt_auth_service.py`

**What to implement**:

- [ ] Retrieve bearer_auth_service from commit history
- [ ] Refactor and rename to jwt_auth_service
- [ ] Integrate with RuntimeAuthState (read JWT from context)
- [ ] Implement AWS role assumption based on JWT claims:
  - [ ] Extract role ARN from JWT (e.g., `role_arn` claim)
  - [ ] Extract session tags from JWT (e.g., `session_tags` claim)
  - [ ] Extract source identity from JWT (`sub` claim)
  - [ ] Call STS AssumeRole with these parameters
  - [ ] Cache assumed credentials per request scope
- [ ] Create boto3 session from assumed credentials
- [ ] Implement error handling for:
  - [ ] Missing JWT in RuntimeAuthState
  - [ ] Missing required claims
  - [ ] STS AssumeRole failures
  - [ ] Expired assumed credentials

**Configuration needed**:

- JWT claims structure for role ARN (document expected format)
- STS session duration (default: 1 hour)
- Role session name template (default: `mcp-{sub}-{timestamp}`)

**Success criteria**:

- ✅ Constructs boto3 session from JWT claims
- ✅ Assumes AWS role with correct parameters
- ✅ Sets SourceIdentity for CloudTrail audit
- ✅ Passes session tags for ABAC
- ✅ Handles STS errors gracefully
- ✅ Works with RuntimeAuthState populated by middleware

**Open questions**:

- What JWT claims structure for role ARN? (Need to define standard)
- Should we support embedded temporary credentials in JWT? (Anti-pattern, probably no)
- How to handle role assumption failures? (Fail request vs fallback?)

#### Task 1.3: Extract IAM Auth Service

**Goal**: Separate current IAM authentication into dedicated service

**Where**: `src/quilt_mcp/services/iam_auth_service.py`

**What to implement**:

- [ ] Extract IAM credential logic from current `auth_service.py`
- [ ] Create `IAMAuthService` class with same interface as JWTAuthService
- [ ] Implement credential resolution:
  - [ ] Environment variables (AWS_ACCESS_KEY_ID, etc.)
  - [ ] AWS profiles (AWS_PROFILE)
  - [ ] quilt3 session credentials
  - [ ] IAM roles (EC2/ECS/Lambda instance roles)
- [ ] Return boto3 session using resolved credentials
- [ ] No RuntimeAuthState dependency (IAM mode doesn't use it)

**Success criteria**:

- ✅ Preserves all current IAM auth behavior
- ✅ Works identically to current implementation
- ✅ No breaking changes for existing users
- ✅ Clear interface for auth service factory

#### Task 1.4: Create Auth Service Factory

**Goal**: Make AuthService a factory that returns appropriate implementation

**Where**: `src/quilt_mcp/services/auth_service.py`

**What to implement**:

- [ ] Read `MCP_REQUIRE_JWT` environment variable at startup
- [ ] Validate configuration for selected mode
- [ ] Return IAMAuthService or JWTAuthService instance
- [ ] Cache auth service instance (singleton per mode)
- [ ] Add logging for mode selection
- [ ] Expose `get_jwt_mode_enabled()` function for debugging

**Pseudo-structure**:

```python
# Factory function (not actual code, just structure)
def get_auth_service() -> AuthServiceProtocol:
    require_jwt = os.getenv("MCP_REQUIRE_JWT", "false").lower() == "true"

    if require_jwt:
        return JWTAuthService()
    else:
        return IAMAuthService()
```

**Success criteria**:

- ✅ Returns correct service based on mode
- ✅ Validates configuration at startup
- ✅ Logs selected mode clearly
- ✅ Raises clear errors for invalid configuration
- ✅ All existing code continues to work (calls get_auth_service())

#### Task 1.5: Implement JWT Middleware

**Goal**: Extract JWT from HTTP requests and populate RuntimeAuthState

**Where**: `src/quilt_mcp/middleware/jwt_middleware.py`

**What to implement**:

- [ ] Create FastAPI/Starlette middleware class
- [ ] Extract `Authorization: Bearer <token>` header from requests
- [ ] Call JWTDecoder to validate and parse token
- [ ] Populate RuntimeAuthState with:
  - [ ] `scheme = "Bearer"`
  - [ ] `access_token = <token>`
  - [ ] `claims = <decoded_claims>`
- [ ] Use `push_runtime_context()` to set request-scoped state
- [ ] Handle errors:
  - [ ] Missing Authorization header → 401
  - [ ] Invalid Bearer format → 401
  - [ ] JWT validation failure → 403
- [ ] Clear RuntimeAuthState after request completes
- [ ] **Only activate in JWT mode** (check MCP_REQUIRE_JWT=true)

**Integration point**: `src/quilt_mcp/utils.py:build_http_app()`

**Success criteria**:

- ✅ Extracts JWT from header correctly
- ✅ Populates RuntimeAuthState accessible to tools
- ✅ Returns appropriate HTTP errors for auth failures
- ✅ Cleans up state after request
- ✅ Only active when mode=jwt
- ✅ Does not interfere with IAM mode

#### Task 1.6: Add PyJWT Dependency

**Goal**: Install JWT library for token validation

**Where**: `pyproject.toml`

**What to add**:

```toml
pyjwt = "^2.8.0"
```

**Additional considerations**:

- [ ] Check for cryptography dependency (required for RS256)
- [ ] Update poetry.lock
- [ ] Verify compatibility with existing dependencies

**Success criteria**:

- ✅ PyJWT installs without conflicts
- ✅ Can import `jwt` module
- ✅ HS256 and RS256 algorithms available

#### Task 1.7: Update Configuration and Documentation

**Goal**: Document auth modes and configuration options

**Where**: `README.md`, new file `docs/AUTHENTICATION.md`

**What to document**:

- [ ] Overview of two auth modes (IAM and JWT)
- [ ] When to use each mode
- [ ] Configuration environment variables:
  - [ ] `MCP_REQUIRE_JWT` (boolean toggle)
  - [ ] `MCP_JWT_SECRET` (JWT secret for validation)
  - [ ] `MCP_JWT_ISSUER` (optional issuer validation)
  - [ ] `MCP_JWT_AUDIENCE` (optional audience validation)
  - [ ] `MCP_JWT_ALGORITHM` (default: HS256)
- [ ] How JWT mode works (architecture diagram)
- [ ] Example JWT structure
- [ ] How to generate JWTs for testing
- [ ] Common error messages and solutions
- [ ] Migration guide from IAM to JWT mode

**Success criteria**:

- ✅ Clear explanation of both modes
- ✅ Step-by-step setup for JWT mode
- ✅ Example configurations for different scenarios
- ✅ Troubleshooting guide

### Phase 2: Integration and Testing (Must Have)

#### Task 2.1: Update HTTP App Builder

**Goal**: Integrate JWT middleware into HTTP server setup

**Where**: `src/quilt_mcp/utils.py` (build_http_app function)

**What to implement**:

- [ ] Check MCP_REQUIRE_JWT at HTTP app startup
- [ ] If MCP_REQUIRE_JWT=true, register JWT middleware
- [ ] If MCP_REQUIRE_JWT=false, skip JWT middleware
- [ ] Add startup log indicating middleware registration
- [ ] Ensure middleware runs before all other middleware
- [ ] Test that CORS middleware still works correctly

**Success criteria**:

- ✅ JWT middleware registered when MCP_REQUIRE_JWT=true
- ✅ JWT middleware skipped when MCP_REQUIRE_JWT=false
- ✅ No performance impact in IAM mode
- ✅ Other middleware continues to work

#### Task 2.2: Create JWT Mode Unit Tests

**Goal**: Test JWT components in isolation

**Where**: `tests/unit/test_jwt_*.py` (new files)

**Test files to create**:

- [ ] `tests/unit/test_jwt_decoder.py`:
  - [ ] Valid JWT validation
  - [ ] Expired JWT rejection
  - [ ] Invalid signature rejection
  - [ ] Missing claims handling
  - [ ] Issuer/audience validation
  - [ ] Edge cases (malformed tokens, etc.)
- [ ] `tests/unit/test_jwt_auth_service.py`:
  - [ ] Role assumption from JWT claims
  - [ ] Session tag extraction
  - [ ] Source identity setting
  - [ ] Error handling (missing claims, STS failures)
  - [ ] Boto3 session construction
- [ ] `tests/unit/test_jwt_middleware.py`:
  - [ ] Header extraction
  - [ ] RuntimeAuthState population
  - [ ] Error responses (401, 403)
  - [ ] State cleanup after request
- [ ] `tests/unit/test_auth_service_factory.py`:
  - [ ] Mode selection logic
  - [ ] Configuration validation
  - [ ] Service instantiation
  - [ ] Error handling

**Success criteria**:

- ✅ All JWT components have >90% test coverage
- ✅ All edge cases covered
- ✅ Tests use mocked dependencies (no real AWS calls)
- ✅ Tests are fast (<1s total)

#### Task 2.3: Create Integration Tests for Both Modes

**Goal**: Test end-to-end authentication in both modes

**Where**: `tests/integration/test_auth_modes.py` (new file)

**What to test**:

- [ ] IAM mode:
  - [ ] Tool execution with AWS credentials from environment
  - [ ] Tool execution with AWS profile
  - [ ] Ignores Authorization headers (if present)
  - [ ] Works with all existing tools
- [ ] JWT mode:
  - [ ] Tool execution with valid JWT
  - [ ] Rejection without JWT (401)
  - [ ] Rejection with invalid JWT (403)
  - [ ] Role assumption works correctly
  - [ ] Session tags passed to AWS
  - [ ] SourceIdentity recorded
- [ ] Mode switching:
  - [ ] Can switch modes via environment variable
  - [ ] No cross-contamination between modes
  - [ ] Startup logs indicate correct mode

**Test infrastructure needed**:

- [ ] JWT generator for test tokens (with configurable claims)
- [ ] Mock STS service for role assumption (using moto)
- [ ] Test fixtures for both modes

**Success criteria**:

- ✅ Both modes work end-to-end
- ✅ Mode switching is reliable
- ✅ No shared state between modes
- ✅ Tests can run in CI without real AWS credentials

#### Task 2.4: Update Existing Tests for Compatibility

**Goal**: Ensure all existing tests work in IAM mode (default)

**Where**: All existing test files

**What to verify**:

- [ ] All tests continue to pass with default IAM mode
- [ ] No tests accidentally require JWT mode
- [ ] Test fixtures properly set MCP_REQUIRE_JWT=false
- [ ] No tests leak auth state between test cases
- [ ] Clean up RuntimeAuthState in teardown

**Changes needed in conftest.py**:

- [ ] Explicitly set `MCP_REQUIRE_JWT=false` for all tests
- [ ] Clear RuntimeAuthState before each test
- [ ] Document why JWT is disabled for tests

**Success criteria**:

- ✅ All existing tests pass without modification
- ✅ No flaky tests due to auth state leakage
- ✅ Tests run in isolated auth contexts

#### Task 2.5: Create Manual Testing Guide

**Goal**: Document how to manually test both auth modes locally

**Where**: `docs/TESTING_AUTH_MODES.md` (new file)

**What to document**:

- [ ] How to run MCP server in IAM mode (default)
- [ ] How to run MCP server in JWT mode
- [ ] How to generate test JWTs with jose or jwt.io
- [ ] Example JWT payloads for different scenarios
- [ ] How to send authenticated requests using curl
- [ ] How to test with Claude Desktop (if applicable)
- [ ] How to verify role assumption (check CloudTrail)
- [ ] Common issues and debugging steps

**Success criteria**:

- ✅ Developer can manually test both modes
- ✅ Clear examples for common scenarios
- ✅ Debugging guidance for auth failures

### Phase 3: Production Readiness (Should Have)

#### Task 3.1: Implement JWT Secret Management

**Goal**: Support multiple ways to provide JWT secrets

**Where**: `src/quilt_mcp/services/jwt_decoder.py`

**What to implement**:

- [ ] Direct secret from environment: `MCP_JWT_SECRET`
- [ ] Secret from AWS SSM Parameter Store: `MCP_JWT_SECRET_SSM_PARAMETER`
- [ ] Secret from AWS Secrets Manager: `MCP_JWT_SECRET_SECRETS_MANAGER_ID`
- [ ] Secret from file: `MCP_JWT_SECRET_FILE` (for Kubernetes secrets)
- [ ] Secret caching (cache for 1 hour, refresh in background)
- [ ] Secret rotation handling (validate with new secret on failure, retry with old)

**Configuration precedence**:

1. `MCP_JWT_SECRET` (direct)
2. `MCP_JWT_SECRET_FILE` (file path)
3. `MCP_JWT_SECRET_SSM_PARAMETER` (AWS SSM)
4. `MCP_JWT_SECRET_SECRETS_MANAGER_ID` (AWS Secrets Manager)

**Success criteria**:

- ✅ Secrets loaded from all sources
- ✅ Caching reduces SSM/Secrets Manager calls
- ✅ Secret rotation handled gracefully
- ✅ Startup fails clearly if no secret provided in JWT mode

#### Task 3.2: Add Permission Checking (Optional)

**Goal**: Check tool permissions against JWT claims

**Where**: `src/quilt_mcp/services/jwt_auth_service.py`

**What to implement**:

- [ ] Define expected JWT claims structure for permissions
- [ ] Map tools to required permissions (e.g., bucket_objects_list → s3:ListBucket)
- [ ] Check JWT claims contain required permissions before tool execution
- [ ] Return 403 with clear message if permissions missing
- [ ] Make permission checking optional (feature flag: `MCP_JWT_CHECK_PERMISSIONS`)

**Example JWT structure**:

```json
{
  "sub": "user@example.com",
  "exp": 1706483200,
  "permissions": ["s3:GetObject", "s3:ListBucket", "quilt:GetPackage"],
  "role_arn": "arn:aws:iam::123456789012:role/QuiltMCPUser",
  "session_tags": [
    {"Key": "tenant", "Value": "acme-corp"},
    {"Key": "user", "Value": "alice"}
  ]
}
```

**Success criteria**:

- ✅ Tools blocked when permissions missing
- ✅ Clear error message listing required permissions
- ✅ Can be disabled via feature flag
- ✅ Does not apply in IAM mode

**Note**: This may be overkill for Phase 1. Consider deferring to Phase 4.

#### Task 3.3: Add Auth Metrics and Logging

**Goal**: Observability for authentication events

**Where**: All auth service files

**What to add**:

- [ ] Structured logging for:
  - [ ] Auth mode selected at startup
  - [ ] JWT validation attempts (success/failure)
  - [ ] JWT validation failure reasons
  - [ ] Role assumption attempts (success/failure)
  - [ ] Permission check failures
  - [ ] User identity from JWT (sub claim)
- [ ] Metrics (if metrics system exists):
  - [ ] Counter: `auth.mode` (labels: iam, jwt)
  - [ ] Counter: `auth.jwt.validation` (labels: success, failure, expired, invalid_signature)
  - [ ] Histogram: `auth.jwt.validation_duration_ms`
  - [ ] Counter: `auth.role_assumption` (labels: success, failure)
  - [ ] Histogram: `auth.role_assumption_duration_ms`

**Success criteria**:

- ✅ Auth events visible in logs
- ✅ Can trace auth flow for debugging
- ✅ Metrics available for monitoring (if system exists)
- ✅ No sensitive data (tokens, secrets) logged

#### Task 3.4: Create Deployment Examples

**Goal**: Show how to deploy in each auth mode

**Where**: `docs/deployment/` (new directory)

**What to create**:

- [ ] `iam-mode-local.md` - Running locally with IAM credentials
- [ ] `jwt-mode-docker.md` - Running in Docker with JWT
- [ ] `jwt-mode-ecs.md` - Deploying to ECS Fargate with JWT
- [ ] `jwt-mode-kubernetes.md` - Deploying to Kubernetes with JWT
- [ ] Example docker-compose files for both modes
- [ ] Example Kubernetes manifests for JWT mode
- [ ] Example ECS task definitions for JWT mode

**Success criteria**:

- ✅ Complete working examples for common platforms
- ✅ Examples include all required configuration
- ✅ Examples follow security best practices
- ✅ Examples tested and verified

#### Task 3.5: Update Stateless Deployment Tests

**Goal**: Integrate JWT mode into stateless tests

**Where**: `spec/a10-multitenant/02-test-stateless.md` implementation

**What to update**:

- [ ] Add JWT mode as requirement for stateless tests
- [ ] Generate test JWTs for stateless test scenarios
- [ ] Update test runner to use JWT authentication
- [ ] Verify role assumption works in stateless mode
- [ ] Ensure no JWT secrets stored in container filesystem

**Success criteria**:

- ✅ Stateless tests work with JWT auth
- ✅ Test proves JWT mode is stateless
- ✅ Test validates role assumption
- ✅ Test checks CloudTrail SourceIdentity

### Phase 4: Advanced Features (Nice to Have)

#### Task 4.1: Support Multiple JWT Algorithms

**Goal**: Support RS256, ES256 in addition to HS256

**What to implement**:

- [ ] RS256 (RSA signatures) using public key
- [ ] ES256 (ECDSA signatures) using public key
- [ ] Public key management (JWKs from JWKS endpoint)
- [ ] Algorithm selection via `MCP_JWT_ALGORITHM`

**Success criteria**:

- ✅ HS256, RS256, ES256 all work
- ✅ Can fetch public keys from JWKS endpoint
- ✅ Algorithm negotiation is secure

**Note**: Defer unless required by specific deployment.

#### Task 4.2: Implement JWT Claims Compression

**Goal**: Support compressed JWT claims (as in removed implementation)

**What to implement**:

- [ ] Permission abbreviations (g → s3:GetObject, etc.)
- [ ] Bucket pattern expansion
- [ ] Nested claim extraction
- [ ] Configurable claim mappings

**Reference**: Removed implementation had this (see build artifacts)

**Success criteria**:

- ✅ Compressed JWTs validated correctly
- ✅ Claims expanded to full form
- ✅ Backward compatible with non-compressed claims

**Note**: Only implement if JWT size is a concern.

#### Task 4.3: Add JWT Refresh Flow

**Goal**: Support JWT refresh tokens for long-running sessions

**What to implement**:

- [ ] Refresh token endpoint
- [ ] Token exchange (refresh → access)
- [ ] Automatic refresh before expiration
- [ ] Graceful handling of refresh failures

**Success criteria**:

- ✅ Tokens refreshed automatically
- ✅ No service interruption during refresh
- ✅ Expired tokens handled gracefully

**Note**: May not be needed for MCP protocol (short-lived sessions).

#### Task 4.4: Desktop Client JWT Integration

**Goal**: Restore desktop client JWT script (was reverted)

**What to restore**:

- [ ] Retrieve `scripts/quilt-mcp-remote.sh` from commit `6ac69fe`
- [ ] Review why it was reverted (commit `a35a802`)
- [ ] Fix issues that caused revert
- [ ] Test with Claude Desktop and VS Code
- [ ] Document setup for desktop clients

**Success criteria**:

- ✅ Desktop clients can use JWT auth
- ✅ Tokens read from quilt3 auth store
- ✅ Works on macOS and Linux

**Note**: Only implement if desktop JWT auth is required.

## Configuration Reference

### Environment Variables

#### Auth Mode Selection

| Variable           | Values           | Default | Description                 |
|--------------------|------------------|---------|-----------------------------|
| `MCP_REQUIRE_JWT`  | `true`, `false`  | `false` | Require JWT authentication  |

#### JWT Configuration (JWT Mode Only)

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `MCP_JWT_SECRET` | string | Yes* | Shared secret for HS256 |
| `MCP_JWT_SECRET_FILE` | path | Yes* | Path to secret file |
| `MCP_JWT_SECRET_SSM_PARAMETER` | string | Yes* | AWS SSM parameter name |
| `MCP_JWT_ISSUER` | string | No | Expected JWT issuer (iss claim) |
| `MCP_JWT_AUDIENCE` | string | No | Expected JWT audience (aud claim) |
| `MCP_JWT_ALGORITHM` | string | No | Algorithm (default: HS256) |

*One of the secret sources required in JWT mode

#### AWS Role Assumption (JWT Mode Only)

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `MCP_JWT_ROLE_ARN_CLAIM` | string | No | JWT claim for role ARN (default: `role_arn`) |
| `MCP_JWT_SESSION_TAGS_CLAIM` | string | No | JWT claim for session tags (default: `session_tags`) |
| `MCP_STS_SESSION_DURATION` | int | No | STS session duration seconds (default: 3600) |

#### IAM Configuration (IAM Mode Only)

Standard AWS environment variables:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`
- `AWS_PROFILE`
- `AWS_REGION`

### JWT Claims Structure

**Minimum required claims**:

```json
{
  "sub": "user@example.com",
  "exp": 1706483200,
  "iat": 1706479600
}
```

**Full claims for role assumption**:

```json
{
  "sub": "user@example.com",
  "exp": 1706483200,
  "iat": 1706479600,
  "iss": "https://auth.example.com",
  "aud": "quilt-mcp-server",
  "role_arn": "arn:aws:iam::123456789012:role/QuiltMCPUser",
  "session_tags": [
    {"Key": "tenant", "Value": "acme-corp"},
    {"Key": "user", "Value": "alice"},
    {"Key": "environment", "Value": "production"}
  ]
}
```

**Optional permission claims** (if Task 3.2 implemented):

```json
{
  "permissions": [
    "s3:GetObject",
    "s3:ListBucket",
    "quilt:GetPackage"
  ]
}
```

## Success Criteria

### Phase 1 Success (Core JWT)

- ✅ JWT mode works end-to-end with valid tokens
- ✅ IAM mode works identically to current implementation
- ✅ Mode selection is clear and reliable
- ✅ Auth failures have clear error messages
- ✅ All unit tests pass for both modes
- ✅ Integration tests cover both modes
- ✅ Documentation explains both modes

### Phase 2 Success (Integration)

- ✅ HTTP middleware integrates cleanly
- ✅ All existing tests pass without modification
- ✅ Manual testing guide is complete
- ✅ Both modes tested in realistic scenarios
- ✅ No performance regression in IAM mode

### Phase 3 Success (Production Ready)

- ✅ JWT secrets managed securely
- ✅ Auth events logged and monitored
- ✅ Deployment examples for common platforms
- ✅ Stateless tests include JWT mode
- ✅ Ready for production multitenant deployment

### Phase 4 Success (Advanced Features)

- ✅ Multiple JWT algorithms supported (if needed)
- ✅ JWT compression working (if needed)
- ✅ Token refresh implemented (if needed)
- ✅ Desktop clients work with JWT (if needed)

## Testing Strategy

### Unit Testing

**JWT Decoder**:

- Valid JWT parsing and validation
- Signature verification (valid, invalid, expired)
- Claims extraction (all types)
- Error handling (malformed, missing claims)

**JWT Auth Service**:

- Role assumption from claims
- Session tag extraction
- Source identity setting
- Boto3 session construction
- Error handling (STS failures)

**IAM Auth Service**:

- Credential resolution (env, profile, quilt3)
- Boto3 session construction
- Existing behavior preserved

**Auth Service Factory**:

- Mode selection logic
- Configuration validation
- Service instantiation
- Error handling

**JWT Middleware**:

- Header extraction
- RuntimeAuthState population
- HTTP error responses
- State cleanup

### Integration Testing

**IAM Mode**:

- End-to-end tool execution with AWS credentials
- All tools work correctly
- Authorization headers ignored
- Works with existing workflows

**JWT Mode**:

- End-to-end tool execution with JWT
- 401 without JWT
- 403 with invalid JWT
- Role assumption works
- Session tags passed
- SourceIdentity recorded

**Mode Switching**:

- Switch via environment variable
- No cross-contamination
- Startup logs correct

### Manual Testing

**Local IAM Mode**:

```bash
# Default mode (IAM)
python -m quilt_mcp
# or explicitly:
MCP_REQUIRE_JWT=false python -m quilt_mcp
```

**Local JWT Mode**:

```bash
# Generate test JWT
export TEST_JWT=$(python scripts/generate_test_jwt.py)

# Run in JWT mode
MCP_REQUIRE_JWT=true \
MCP_JWT_SECRET="test-secret-key" \
python -m quilt_mcp

# Test with curl
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $TEST_JWT" \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/list"}'
```

**Docker JWT Mode**:

```bash
docker run -p 8000:8000 \
  -e MCP_REQUIRE_JWT=true \
  -e MCP_JWT_SECRET="test-secret-key" \
  --read-only \
  --tmpfs /tmp:size=100M \
  quilt-mcp-server:latest
```

### Stateless Deployment Testing

See [02-test-stateless.md](02-test-stateless.md) for full stateless test specification.

**JWT-specific additions**:

- [ ] JWT mode enforced in stateless tests
- [ ] No JWT secrets in container filesystem
- [ ] Role assumption verified via CloudTrail
- [ ] Session tags visible in AWS logs

## Migration Strategy

### For Developers (Local Development)

**No action required** - IAM mode is default, existing workflows continue to work.

**Optional**: To test JWT mode locally:

1. Generate test JWT using provided script
2. Set `MCP_REQUIRE_JWT=true` and `MCP_JWT_SECRET`
3. Include Authorization header in requests

### For Production Deployments

**Step 1: Configure JWT Secret**

- Store JWT secret in AWS Secrets Manager or SSM
- Grant ECS task role permission to read secret

**Step 2: Set Environment Variables**

```bash
MCP_REQUIRE_JWT=true
MCP_JWT_SECRET_SSM_PARAMETER=/quilt-mcp/jwt-secret
MCP_JWT_ISSUER=https://auth.quiltdata.com
MCP_JWT_AUDIENCE=quilt-mcp-server
```

**Step 3: Deploy with JWT Enforcement**

- Update ECS task definition or Kubernetes deployment
- Ensure API Gateway/Load Balancer passes Authorization headers
- Monitor auth logs for failures

**Step 4: Verify**

- Check startup logs show "Auth mode: jwt"
- Test with valid JWT (200 response)
- Test without JWT (401 response)
- Check CloudTrail shows SourceIdentity

### Rollback Plan

If JWT mode has issues:

1. Set `MCP_REQUIRE_JWT=false` (or remove variable)
2. Redeploy
3. Service falls back to IAM credentials
4. Investigate JWT issues offline

## Open Questions

1. **JWT Claims Standard**: Should we define a standard JWT structure for Quilt MCP? (Document in Phase 1)

2. **Permission Granularity**: How granular should tool permissions be? Per-tool, per-S3-bucket, per-package? (Consider in Phase 3)

3. **Role Assumption Caching**: Should we cache assumed role credentials across requests for same user? (Security vs performance trade-off)

4. **Multi-Region Support**: How to handle role assumption in different AWS regions? (Future enhancement)

5. **JWT Expiration**: What's appropriate JWT lifetime for MCP protocol? (Short-lived: 1 hour? Long-lived: 24 hours?)

6. **Refresh Tokens**: Do we need refresh token support for long-running MCP sessions? (Probably not for initial implementation)

7. **Desktop Clients**: Should desktop clients (Claude Desktop, VS Code) use JWT or IAM? (IAM is simpler for local development)

8. **API Gateway Integration**: Should API Gateway validate JWT or pass-through to MCP server? (Both patterns have trade-offs)

## Implementation Phases Summary

### Phase 1: Core JWT (2-3 weeks)

- Restore JWT decoder and auth services
- Create auth service factory
- Add JWT middleware
- Unit tests for all components
- Basic documentation

### Phase 2: Integration (1-2 weeks)

- HTTP middleware integration
- Integration tests for both modes
- Update existing tests
- Manual testing guide

### Phase 3: Production Readiness (1-2 weeks)

- Secret management
- Metrics and logging
- Deployment examples
- Stateless test integration

### Phase 4: Advanced Features (As needed)

- Multiple JWT algorithms (1 week)
- Claims compression (1 week)
- Token refresh (1 week)
- Desktop client integration (1 week)

**Total estimated time**: 6-10 weeks for Phases 1-3 (production ready)

## References

- Original JWT implementation: commit `f36c689` (Oct 18, 2025)
- JWT removal: commit `0d5c917` (Dec 4, 2025)
- Desktop script (reverted): commit `6ac69fe` (Dec 16, 2025)
- Architecture spec: [spec/Archive/6-auth-spec.md](../Archive/6-auth-spec.md)
- Stateless deployment: [01-stateless.md](01-stateless.md)
- Stateless testing: [02-test-stateless.md](02-test-stateless.md)
- Runtime context: [src/quilt_mcp/runtime_context.py](../../src/quilt_mcp/runtime_context.py)
- Current auth service: [src/quilt_mcp/services/auth_service.py](../../src/quilt_mcp/services/auth_service.py)
- HTTP utils: [src/quilt_mcp/utils.py](../../src/quilt_mcp/utils.py)

## Related Specifications

- [01-stateless.md](01-stateless.md) - Stateless architecture requirements
- [02-test-stateless.md](02-test-stateless.md) - Stateless deployment testing
- [03-fix-stateless.md](03-fix-stateless.md) - Stateless deployment fixes
- [../Archive/6-auth-spec.md](../Archive/6-auth-spec.md) - Original auth architecture

## Appendix: Example JWT Generation Script

**Purpose**: Developers need a way to generate test JWTs for local testing.

**Location**: `scripts/generate_test_jwt.py` (to be created)

**Functionality** (conceptual, not actual code):

- Accept claims as command-line arguments
- Generate JWT signed with test secret
- Print token to stdout
- Support common scenarios (minimal, with role, with permissions)

**Example usage**:

```bash
# Minimal JWT
python scripts/generate_test_jwt.py --sub "user@example.com"

# With role assumption
python scripts/generate_test_jwt.py \
  --sub "user@example.com" \
  --role-arn "arn:aws:iam::123456789012:role/TestRole" \
  --session-tag "tenant=test,user=alice"

# Custom expiration
python scripts/generate_test_jwt.py \
  --sub "user@example.com" \
  --expires-in 3600
```
