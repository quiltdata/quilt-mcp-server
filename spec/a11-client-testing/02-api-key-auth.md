# API Key Authentication Mode for Remote MCP Clients

**Status**: Draft
**Created**: 2026-01-29
**Objective**: Add API key authentication to enable simple remote MCP client access with full Quilt catalog and S3 functionality

## Problem Statement

The current MCP server supports two authentication modes, but neither solves the **remote client** use case:

1. **IAM Mode** (default) - Uses local AWS credentials
   - ✅ Works for local development
   - ❌ Requires `~/.quilt/` and `~/.aws/` files on client machine
   - ❌ Doesn't work for remote HTTP/SSE connections
   - ❌ No authentication to Quilt catalog API (search fails without `quilt3.login()`)

2. **JWT Mode** - Assumes AWS roles per request
   - ✅ Works for multi-user production deployments
   - ✅ Stateless and secure
   - ❌ Requires complex JWT generation infrastructure
   - ❌ Clients must sign JWTs with shared secrets or private keys
   - ❌ No authentication to Quilt catalog API (only AWS STS)
   - ❌ Requires coordination with identity provider

### The Gap: Remote Client Access

**Target scenario**: User runs Claude Desktop and wants to connect to a remote MCP server:

```
┌─────────────────────────┐
│   Claude Desktop        │
│   (user's laptop)       │
└─────────────────────────┘
           │
           │ HTTP/SSE over network
           ▼
┌─────────────────────────┐
│   MCP Server            │
│   (remote instance)     │
└─────────────────────────┘
```

**Current problems**:

1. **Search doesn't work** - Requires authenticated Quilt catalog session
   - Search is the **most vital MCP tool** (user's words)
   - Uses `quilt3.search_api()` which needs catalog authentication
   - Currently depends on `quilt3.login()` being called locally

2. **JWT is too complex** - Clients can't easily generate JWTs
   - Requires signing infrastructure (HS256/RS256 keys)
   - Must construct proper claims (role arn, session_tags, exp, iat, iss, aud)
   - Need to handle expiration and refresh
   - Desktop clients don't have this infrastructure

3. **IAM mode requires local files** - Doesn't work remotely
   - Expects `~/.quilt/quiltconfig` from `quilt3.login()`
   - Expects `~/.aws/credentials` for S3 access
   - Remote client doesn't have these files

### What Users Need

A **simple authentication method** for remote clients that:

- Requires only a single credential (API key)
- Authenticates to both Quilt catalog AND AWS
- Works over HTTP/SSE transport
- Can be configured in MCP client config
- Doesn't require local filesystem state

## Current State Analysis

### How Quilt API Keys Work

From [Quilt documentation](https://docs.quilt.bio/quilt-python-sdk/api-reference/authentication#api-key-authentication):

**API Key Format**: `qk_<random_string>`

**Creation**:

```python
# Interactive login first (one-time setup)
quilt3.login()

# Generate API key
api_key = quilt3.api_keys.create("my-key-name")
# Returns: "qk_abc123xyz..."
```

**Usage**:

```python
# In scripts/automation
import quilt3
quilt3.login_with_api_key("qk_abc123xyz...")

# Now all quilt3 operations work:
quilt3.Package.browse(...)  # S3 access
quilt3.search_packages(...)  # Catalog API access
```

**Key properties**:

- One-time generation via interactive login
- Stored securely by user (not shown again)
- Provides **both** catalog authentication AND AWS credentials
- Works identically to interactive login after setup

### What `quilt3.login_with_api_key()` Provides

Based on quilt3 library behavior (needs verification via testing):

1. **Authenticated HTTP session** to Quilt catalog
   - Used by `quilt3.session.get_session()`
   - Required for `search_api()`, admin operations, metadata access

2. **AWS credentials** for S3 access
   - Accessible via `quilt3.get_boto3_session()` (if available)
   - OR falls back to ambient AWS credentials
   - Credentials may come from catalog-provided temporary tokens

3. **Registry URL** configuration
   - Sets `quilt3.session.get_registry_url()`
   - Used for catalog API endpoint resolution

### Existing MCP Authentication Flow

Current authentication in [src/quilt_mcp/services/auth_service.py:71-85](../../src/quilt_mcp/services/auth_service.py#L71-L85):

```python
def get_auth_service() -> AuthServiceProtocol:
    if get_jwt_mode_enabled():  # MCP_REQUIRE_JWT=true
        return JWTAuthService()
    else:
        return IAMAuthService()
```

**IAM Auth Service** ([src/quilt_mcp/services/iam_auth_service.py](../../src/quilt_mcp/services/iam_auth_service.py)):

- Checks `quilt3.logged_in()` and uses `quilt3.get_boto3_session()`
- Falls back to `boto3.Session()` (ambient AWS credentials)
- Works if user ran `quilt3.login()` or `quilt3.login_with_api_key()` **on the server machine**

**JWT Auth Service** ([src/quilt_mcp/services/jwt_auth_service.py](../../src/quilt_mcp/services/jwt_auth_service.py)):

- Reads JWT from RuntimeAuthState (populated by middleware)
- Assumes AWS role using claims
- Returns scoped boto3 session
- **Does NOT** authenticate to Quilt catalog

### Search Implementation Dependencies

Search backend in [src/quilt_mcp/search/backends/elasticsearch.py:449-453](../../src/quilt_mcp/search/backends/elasticsearch.py#L449-L453):

```python
search_api = self.quilt_service.get_search_api()
# Returns: quilt3.search_util.search_api

response = search_api(query=dsl_query, index=index_pattern, limit=limit)
```

**Critical dependency**: `search_api()` requires an authenticated quilt3 session.

Without authentication:

- Returns 401/403 errors
- Search tool fails completely
- User cannot search packages or files

## Requirements

### Functional Requirements

**FR1: API Key Authentication Mode**

- Support a third authentication mode: **API Key**
- Activated by presence of `QUILT_API_KEY` environment variable
- Takes precedence over IAM mode (more explicit)
- Does NOT conflict with JWT mode (separate use cases)

**FR2: Automatic Quilt Catalog Authentication**

- Call `quilt3.login_with_api_key()` at service initialization
- Verify successful authentication via `quilt3.logged_in()`
- Make authenticated session available to all tools
- Enable `search_api()` and other catalog operations

**FR3: AWS Credentials Resolution**

- Primary: Use `quilt3.get_boto3_session()` if available
- Fallback: Use ambient AWS credentials (same as IAM mode)
- Return valid `boto3.Session` for S3 operations
- Support all S3-based MCP tools

**FR4: Remote Client Support**

- Work over HTTP/SSE transport (no local filesystem required)
- API key passed via environment variable in MCP client config
- Server authenticates using API key on startup
- All subsequent requests use authenticated session

**FR5: Configuration Simplicity**

- Single environment variable: `QUILT_API_KEY`
- No JWT infrastructure required
- No shared secrets or key signing
- Works with standard MCP client configurations

**FR6: Error Handling**

- Startup failure if API key is invalid
- Clear error message: "API key authentication failed - verify QUILT_API_KEY is valid"
- Distinguish between:
  - Missing API key (falls back to IAM mode)
  - Invalid API key (startup error)
  - Network/catalog connectivity issues

### Non-Functional Requirements

**NFR1: Authentication Mode Precedence**

Clear, unambiguous mode selection:

1. If `QUILT_API_KEY` set → **API Key mode**
2. Else if `MCP_REQUIRE_JWT=true` → **JWT mode**
3. Else → **IAM mode** (default)

**NFR2: Backward Compatibility**

- Existing IAM mode unchanged
- Existing JWT mode unchanged
- No breaking changes to current users
- All existing tests continue to pass

**NFR3: Security**

- API key never logged or exposed in error messages
- API key only stored in memory
- Failed authentication logged without revealing key
- Catalog session credentials handled securely

**NFR4: Observability**

- Startup logs indicate "Authentication mode: API Key"
- Log successful catalog authentication (with user identity, not key)
- Log authentication failures (without key details)
- Track auth mode metrics

**NFR5: Performance**

- One-time authentication at startup
- Session reused across all requests
- No per-request authentication overhead
- No performance impact on other modes

## Design: Three-Mode Authentication Architecture

### Authentication Mode Decision Matrix

| Environment | Mode Selected | Authenticates To | Provides |
|-------------|---------------|------------------|----------|
| `QUILT_API_KEY=qk_xxx` | **API Key** | Quilt Catalog + AWS | Catalog session + AWS creds |
| `MCP_REQUIRE_JWT=true` | **JWT** | AWS (STS) | AWS credentials per request |
| (neither set) | **IAM** | AWS (ambient) | AWS credentials from environment |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server Startup                        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Auth Service Factory                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │  1. Check QUILT_API_KEY → ApiKeyAuthService        │    │
│  │  2. Check MCP_REQUIRE_JWT → JWTAuthService         │    │
│  │  3. Default → IAMAuthService                       │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐  ┌────────────────┐  ┌──────────────┐
│ IAMAuth      │  │ JWTAuth        │  │ ApiKeyAuth   │
│ Service      │  │ Service        │  │ Service      │
├──────────────┤  ├────────────────┤  ├──────────────┤
│ - Check      │  │ - Extract JWT  │  │ - Call       │
│   quilt3     │  │   from runtime │  │   quilt3.    │
│   logged_in()│  │ - Assume AWS   │  │   login_     │
│ - Use        │  │   role         │  │   with_api_  │
│   ambient    │  │ - Return       │  │   key()      │
│   AWS creds  │  │   scoped boto3 │  │ - Get quilt3 │
│ - Return     │  │   session      │  │   session    │
│   boto3      │  │                │  │ - Get boto3  │
│   session    │  │                │  │   from quilt3│
└──────────────┘  └────────────────┘  └──────────────┘
```

### Component Design

#### New Component: ApiKeyAuthService

**Location**: [src/quilt_mcp/services/api_key_auth_service.py](../../src/quilt_mcp/services/api_key_auth_service.py) (new file)

**Responsibilities**:

1. **Initialization**:
   - Read `QUILT_API_KEY` from environment
   - Call `quilt3.login_with_api_key(api_key)`
   - Verify authentication succeeded
   - Raise clear error if authentication fails

2. **Session Management**:
   - Cache authenticated state
   - Provide boto3 session from quilt3 or ambient credentials
   - Ensure session remains valid for server lifetime

3. **Error Handling**:
   - Invalid API key → Startup failure with clear message
   - Catalog connectivity issues → Startup failure with diagnostic info
   - AWS credential issues → Fall back to ambient credentials

**Interface** (matches AuthServiceProtocol):

```python
class ApiKeyAuthService:
    auth_type: Literal["api_key"] = "api_key"

    def __init__(self) -> None:
        """Initialize with API key authentication."""
        # Implementation in Phase 1

    def get_boto3_session(self) -> boto3.Session:
        """Return boto3 session (from quilt3 or ambient)."""
        # Implementation in Phase 1
```

#### Modified Component: Auth Service Factory

**Location**: [src/quilt_mcp/services/auth_service.py](../../src/quilt_mcp/services/auth_service.py)

**Changes**:

1. Add API key mode detection
2. Update mode selection logic
3. Add API key mode to AuthMode type
4. Update logging and metrics

**New logic**:

```python
def get_auth_service() -> AuthServiceProtocol:
    global _AUTH_SERVICE
    if _AUTH_SERVICE is None:
        # Priority 1: API Key (most explicit)
        if os.getenv("QUILT_API_KEY"):
            _AUTH_SERVICE = ApiKeyAuthService()
            logger.info("Authentication mode selected: API Key")
            record_auth_mode("api_key")
        # Priority 2: JWT (requires explicit flag)
        elif get_jwt_mode_enabled():
            _validate_jwt_mode()
            _AUTH_SERVICE = JWTAuthService()
            logger.info("Authentication mode selected: JWT")
            record_auth_mode("jwt")
        # Priority 3: IAM (default)
        else:
            _AUTH_SERVICE = IAMAuthService()
            logger.info("Authentication mode selected: IAM")
            record_auth_mode("iam")
    return _AUTH_SERVICE
```

### File Structure

**New Files**:

- `src/quilt_mcp/services/api_key_auth_service.py` - API key authentication implementation

**Modified Files**:

- `src/quilt_mcp/services/auth_service.py` - Add API key mode to factory
- `docs/AUTHENTICATION.md` - Document API key mode
- `README.md` - Add API key configuration example
- `tests/unit/test_auth_service_factory.py` - Add API key mode tests
- `tests/unit/test_api_key_auth_service.py` - New test file
- `tests/integration/test_auth_modes.py` - Add API key mode integration tests

**No changes needed**:

- JWT implementation (orthogonal use case)
- IAM implementation (fallback behavior unchanged)
- Search implementation (works automatically with authenticated session)
- Tool implementations (transparent to auth mode)

## Implementation Phases

### Phase 1: Core API Key Authentication (Must Have)

**Estimated effort**: 2-3 days

#### Task 1.1: Create ApiKeyAuthService

**Goal**: Implement API key authentication service

**Where**: `src/quilt_mcp/services/api_key_auth_service.py` (new file)

**What to implement**:

- [ ] Create `ApiKeyAuthService` class implementing `AuthServiceProtocol`
- [ ] Read `QUILT_API_KEY` from environment in `__init__()`
- [ ] Call `quilt3.login_with_api_key(api_key)`
- [ ] Verify authentication with `quilt3.logged_in()`
- [ ] Raise `AuthServiceError` with clear message if authentication fails
- [ ] Implement `get_boto3_session()`:
  - [ ] Try `quilt3.get_boto3_session()` if available
  - [ ] Fall back to `boto3.Session()` (ambient credentials)
  - [ ] Cache session for reuse
- [ ] Add logging for successful/failed authentication
- [ ] Extract user identity for logging (if available from quilt3 session)

**Configuration needed**:

- `QUILT_API_KEY` - The API key (format: `qk_<string>`)

**Success criteria**:

- ✅ Service initializes with valid API key
- ✅ Authentication failure raises clear error
- ✅ Returns valid boto3 session
- ✅ Quilt catalog session available (`quilt3.logged_in()` returns true)
- ✅ Search tools work (can call `search_api()`)

#### Task 1.2: Update Auth Service Factory

**Goal**: Add API key mode to authentication mode selection

**Where**: `src/quilt_mcp/services/auth_service.py`

**What to implement**:

- [ ] Import `ApiKeyAuthService`
- [ ] Add `"api_key"` to `AuthMode` type
- [ ] Update `get_auth_service()` to check for `QUILT_API_KEY` first
- [ ] Add startup logging for API key mode
- [ ] Add metrics recording for API key mode
- [ ] Update `reset_auth_service()` to clear API key state (for tests)

**Precedence logic**:

1. If `QUILT_API_KEY` → ApiKeyAuthService
2. Elif `MCP_REQUIRE_JWT=true` → JWTAuthService
3. Else → IAMAuthService

**Success criteria**:

- ✅ API key mode selected when `QUILT_API_KEY` set
- ✅ JWT mode still works when `MCP_REQUIRE_JWT=true` (no API key)
- ✅ IAM mode still default when neither set
- ✅ Startup logs clearly indicate selected mode
- ✅ Metrics recorded correctly

#### Task 1.3: Add Unit Tests

**Goal**: Test API key authentication in isolation

**Where**: `tests/unit/test_api_key_auth_service.py` (new file)

**What to test**:

- [ ] Successful authentication:
  - [ ] Valid API key initializes service
  - [ ] `quilt3.login_with_api_key()` called correctly
  - [ ] Boto3 session returned
- [ ] Authentication failures:
  - [ ] Missing API key raises error
  - [ ] Invalid API key raises error with clear message
  - [ ] Catalog connectivity issues handled
- [ ] Session management:
  - [ ] Boto3 session from quilt3 (if available)
  - [ ] Boto3 session from ambient credentials (fallback)
  - [ ] Session cached and reused
- [ ] Error messages:
  - [ ] API key never appears in error messages
  - [ ] Clear guidance for authentication failures

**Test infrastructure**:

- [ ] Mock `quilt3.login_with_api_key()`
- [ ] Mock `quilt3.logged_in()`
- [ ] Mock `quilt3.get_boto3_session()`
- [ ] Mock `boto3.Session()`

**Success criteria**:

- ✅ All API key service behaviors tested
- ✅ >90% code coverage for ApiKeyAuthService
- ✅ Tests use mocks (no real Quilt API calls)
- ✅ Tests run fast (<1s)

#### Task 1.4: Update Factory Tests

**Goal**: Test API key mode selection logic

**Where**: `tests/unit/test_auth_service_factory.py`

**What to test**:

- [ ] Mode precedence:
  - [ ] API key takes precedence over IAM
  - [ ] JWT takes precedence over IAM (existing test)
  - [ ] API key and JWT both set → API key wins (or error?)
- [ ] Environment variable handling:
  - [ ] `QUILT_API_KEY` → API key mode
  - [ ] `MCP_REQUIRE_JWT=true` → JWT mode
  - [ ] Neither → IAM mode
- [ ] Service instantiation:
  - [ ] Correct service type returned
  - [ ] Service properly initialized
  - [ ] Factory caching works

**Success criteria**:

- ✅ All mode selection paths tested
- ✅ Mode precedence clear and tested
- ✅ No breaking changes to existing tests

### Phase 2: Integration and Documentation (Must Have)

**Estimated effort**: 2-3 days

#### Task 2.1: Add Integration Tests

**Goal**: Test API key mode end-to-end

**Where**: `tests/integration/test_auth_modes.py`

**What to test**:

- [ ] API key mode:
  - [ ] Server starts successfully with valid API key
  - [ ] Search tools work (catalog authentication verified)
  - [ ] S3 tools work (AWS credentials verified)
  - [ ] Package operations work
  - [ ] Admin operations work (if API key has permissions)
- [ ] Mode isolation:
  - [ ] API key mode doesn't interfere with IAM mode
  - [ ] API key mode doesn't interfere with JWT mode
  - [ ] Can switch between modes via environment variable
- [ ] Error scenarios:
  - [ ] Invalid API key → startup failure
  - [ ] Missing catalog connectivity → clear error
  - [ ] AWS credential issues → graceful degradation

**Test infrastructure**:

- [ ] Generate test API key (or mock quilt3 for CI)
- [ ] Mock catalog responses for API key validation
- [ ] Test with real MCP server instance (if possible)
- [ ] Test with HTTP transport

**Success criteria**:

- ✅ API key mode works end-to-end
- ✅ All critical tools tested (search, S3, packages)
- ✅ Error handling verified
- ✅ Can run in CI without real API keys

#### Task 2.2: Update Authentication Documentation

**Goal**: Document API key mode for users

**Where**: `docs/AUTHENTICATION.md`

**What to document**:

- [ ] Overview section:
  - [ ] Add API key as third authentication mode
  - [ ] Update comparison table (IAM vs JWT vs API Key)
  - [ ] When to use each mode
- [ ] API key mode section:
  - [ ] How to generate API key (link to Quilt docs)
  - [ ] How to configure MCP server with API key
  - [ ] What API key provides (catalog + AWS access)
  - [ ] Security best practices (storing API keys)
- [ ] Configuration reference:
  - [ ] `QUILT_API_KEY` environment variable
  - [ ] Mode precedence rules
  - [ ] Example configurations
- [ ] Troubleshooting:
  - [ ] "API key authentication failed" → check key validity
  - [ ] "Search not working" → verify catalog connectivity
  - [ ] "AWS access denied" → verify AWS credential fallback

**Success criteria**:

- ✅ Clear explanation of API key mode
- ✅ Step-by-step setup instructions
- ✅ Example configurations for common scenarios
- ✅ Troubleshooting guide

#### Task 2.3: Update README

**Goal**: Add API key configuration example to main README

**Where**: `README.md`

**What to add**:

- [ ] Quick start section:
  - [ ] Add API key authentication option
  - [ ] Show MCP client config with API key
- [ ] Configuration section:
  - [ ] Add `QUILT_API_KEY` to environment variables table
  - [ ] Add authentication modes comparison
  - [ ] Link to detailed auth docs

**Example config to add**:

```json
{
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["quilt-mcp"],
      "env": {
        "QUILT_CATALOG_URL": "https://your-catalog.quiltdata.com",
        "QUILT_API_KEY": "qk_your_api_key_here"
      }
    }
  }
}
```

**Success criteria**:

- ✅ API key mode visible in README
- ✅ Example configuration clear and copy-paste ready
- ✅ Links to detailed documentation

#### Task 2.4: Create Manual Testing Guide

**Goal**: Document how to manually test API key mode

**Where**: `docs/TESTING_AUTH_MODES.md` (update existing)

**What to add**:

- [ ] API key mode testing:
  - [ ] How to generate test API key
  - [ ] How to run MCP server with API key
  - [ ] How to verify search works
  - [ ] How to verify S3 access works
  - [ ] How to test with Claude Desktop
- [ ] Common issues:
  - [ ] API key not recognized
  - [ ] Search still failing
  - [ ] AWS access denied

**Example test procedure**:

```bash
# 1. Generate API key (one-time)
python3 -c "import quilt3; quilt3.login(); print(quilt3.api_keys.create('test-key'))"

# 2. Run MCP server with API key
export QUILT_API_KEY="qk_..."
python -m quilt_mcp

# 3. Verify authentication in startup logs
# Expected: "Authentication mode selected: API Key"

# 4. Test search (via MCP client or curl)
# ...
```

**Success criteria**:

- ✅ Manual testing procedure documented
- ✅ Can follow guide to verify API key mode works
- ✅ Common issues addressed

### Phase 3: Remote Client Support (Should Have)

**Estimated effort**: 1-2 days

#### Task 3.1: Verify HTTP/SSE Transport Compatibility

**Goal**: Ensure API key mode works with remote HTTP clients

**Where**: Existing HTTP transport implementation

**What to verify**:

- [ ] API key read from environment on server startup
- [ ] Authentication persists across HTTP requests
- [ ] SSE connections work with API key mode
- [ ] Session ID handling works correctly
- [ ] No CORS issues with remote clients

**Test scenarios**:

- [ ] Claude Desktop connecting to remote MCP server
- [ ] HTTP client with multiple concurrent requests
- [ ] Long-running SSE connections
- [ ] Server restart handling

**Success criteria**:

- ✅ Remote clients can connect with API key
- ✅ No transport-specific issues
- ✅ Works with stateless and stateful HTTP modes

#### Task 3.2: Create Remote Client Examples

**Goal**: Provide working examples for common remote scenarios

**Where**: `docs/deployment/` (update or create)

**What to create**:

- [ ] Claude Desktop remote config:
  - [ ] MCP client configuration
  - [ ] API key setup
  - [ ] Testing steps
- [ ] Docker deployment with API key:
  - [ ] Dockerfile example
  - [ ] Environment variable configuration
  - [ ] Health check configuration
- [ ] Kubernetes deployment:
  - [ ] Secret management for API key
  - [ ] ConfigMap for catalog URL
  - [ ] Service/Ingress configuration

**Success criteria**:

- ✅ Working examples for common platforms
- ✅ Security best practices followed
- ✅ Examples tested and verified

#### Task 3.3: Update Stateless Deployment Docs

**Goal**: Document API key mode for stateless deployments

**Where**: `spec/a10-multiuser/01-stateless.md`, `02-test-stateless.md`

**What to add**:

- [ ] API key as authentication option for stateless mode
- [ ] Comparison with JWT mode for different use cases
- [ ] When to use API key vs JWT
- [ ] Testing API key in stateless deployments

**Success criteria**:

- ✅ Stateless deployment docs include API key option
- ✅ Clear guidance on mode selection
- ✅ Integration with existing stateless tests

## Configuration Reference

### Environment Variables

| Variable | Mode | Required | Description |
|----------|------|----------|-------------|
| `QUILT_API_KEY` | API Key | Yes | Quilt API key (format: `qk_<string>`) |
| `QUILT_CATALOG_URL` | All | Optional | Catalog URL (can be inferred from API key) |
| `MCP_REQUIRE_JWT` | JWT | No | Enable JWT mode (default: false) |
| `AWS_PROFILE` | IAM/API Key | Optional | AWS profile for S3 access |
| `AWS_ACCESS_KEY_ID` | IAM/API Key | Optional | AWS access key (fallback) |
| `AWS_SECRET_ACCESS_KEY` | IAM/API Key | Optional | AWS secret key (fallback) |

### Authentication Mode Selection

**Precedence** (highest to lowest):

1. **API Key Mode**: `QUILT_API_KEY` set
2. **JWT Mode**: `MCP_REQUIRE_JWT=true` (and no API key)
3. **IAM Mode**: Neither of the above (default)

### Configuration Examples

#### Local Development (IAM Mode)

```json
{
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["quilt-mcp"],
      "env": {
        "AWS_PROFILE": "my-profile"
      }
    }
  }
}
```

#### Remote Client (API Key Mode)

```json
{
  "mcpServers": {
    "quilt": {
      "command": "uvx",
      "args": ["quilt-mcp"],
      "env": {
        "QUILT_CATALOG_URL": "https://catalog.example.com",
        "QUILT_API_KEY": "qk_abc123xyz..."
      }
    }
  }
}
```

#### Multi-tenant Production (JWT Mode)

```json
{
  "mcpServers": {
    "quilt": {
      "command": "docker",
      "args": ["run", "-p", "8000:8000", "quilt-mcp:latest"],
      "env": {
        "MCP_REQUIRE_JWT": "true",
        "MCP_JWT_SECRET": "shared-secret"
      }
    }
  }
}
```

## Comparison: API Key vs JWT vs IAM

| Feature | IAM Mode | JWT Mode | API Key Mode |
|---------|----------|----------|--------------|
| **Use Case** | Local development | Multi-tenant SaaS | Remote clients |
| **Auth to Quilt** | Local `quilt3.login()` | ❌ None | ✅ Via API key |
| **Auth to AWS** | Ambient credentials | Per-request STS | From quilt3 or ambient |
| **Search support** | ✅ If logged in | ❌ No catalog auth | ✅ Always |
| **Setup complexity** | Easy | Complex (JWT infra) | Easy |
| **Remote access** | ❌ Requires local files | ✅ Stateless | ✅ Stateless |
| **Multi-user** | ❌ Shared creds | ✅ Per-user isolation | ⚠️ Shared API key |
| **Credential** | AWS creds + quilt login | JWT token | Single API key |

## Success Criteria

### Phase 1 Success (Core Implementation)

- ✅ API key mode works end-to-end
- ✅ Search functionality verified
- ✅ S3 operations verified
- ✅ Clear error messages for auth failures
- ✅ All unit tests pass
- ✅ No breaking changes to existing modes

### Phase 2 Success (Integration)

- ✅ Integration tests cover API key mode
- ✅ Documentation complete and clear
- ✅ README updated with examples
- ✅ Manual testing guide works

### Phase 3 Success (Remote Support)

- ✅ HTTP/SSE transport verified
- ✅ Remote client examples provided
- ✅ Stateless deployment docs updated
- ✅ Production-ready

## Testing Strategy

### Unit Testing

**ApiKeyAuthService**:

- Valid API key initialization
- Invalid API key error handling
- Boto3 session resolution (quilt3 vs ambient)
- Session caching
- Error message formatting

**Auth Service Factory**:

- Mode precedence logic
- API key mode selection
- Service instantiation
- Caching behavior

### Integration Testing

**API Key Mode End-to-End**:

- Server startup with API key
- Search operations (catalog authentication)
- S3 operations (AWS credentials)
- Package operations
- Admin operations (if permitted)

**Mode Isolation**:

- API key doesn't affect IAM mode
- API key doesn't affect JWT mode
- Mode switching works correctly

**Error Scenarios**:

- Invalid API key
- Network connectivity issues
- AWS credential failures

### Manual Testing

**Local Testing**:

```bash
# Generate API key
python3 -c "import quilt3; quilt3.login(); print(quilt3.api_keys.create('test'))"

# Run with API key
export QUILT_API_KEY="qk_..."
python -m quilt_mcp

# Verify in logs: "Authentication mode selected: API Key"
```

**Remote Testing**:

```bash
# Configure Claude Desktop with API key
# Test search, S3 access, package operations
# Verify all functionality works
```

**HTTP Transport Testing**:

```bash
# Run server with HTTP transport
export QUILT_API_KEY="qk_..."
python -m quilt_mcp --transport http

# Test with MCP client
# Test with curl for raw HTTP/SSE
```

## Migration Strategy

### For Local Users (No Action Required)

Existing IAM mode continues to work:

- `quilt3.login()` + AWS credentials still works
- No configuration changes needed
- API key mode is opt-in

### For Remote Client Users (New Capability)

1. **Generate API key** (one-time):

   ```python
   import quilt3
   quilt3.login()  # Interactive
   api_key = quilt3.api_keys.create("my-mcp-key")
   # Save the returned key securely
   ```

2. **Update MCP client config**:

   ```json
   {
     "env": {
       "QUILT_API_KEY": "qk_your_key_here"
     }
   }
   ```

3. **Verify**:
   - Server logs show "API Key" mode
   - Search works
   - S3 access works

### For Multi-tenant Deployments (No Change)

JWT mode continues to work:

- Use JWT for per-user isolation
- Use API key for simpler shared-credential scenarios
- Choose based on security requirements

## Security Considerations

### API Key Security

**Storage**:

- ✅ Store in environment variables (not code)
- ✅ Use secrets management for production (AWS Secrets Manager, Kubernetes Secrets)
- ❌ Never commit API keys to version control
- ❌ Never log API keys

**Transmission**:

- ✅ API key stays on MCP server (not sent over network per-request)
- ✅ HTTPS for all catalog API communication
- ✅ TLS for MCP client → server communication

**Scope**:

- ⚠️ API key provides full user access (not scoped per-request)
- ⚠️ All MCP requests share same API key credentials
- ⚠️ Not suitable for untrusted multi-user scenarios (use JWT instead)
- ✅ Suitable for trusted users with personal MCP servers

**Rotation**:

- User can generate multiple API keys
- User can revoke API keys via Quilt catalog
- Server restart required after key rotation

### When to Use Each Mode

| Scenario | Recommended Mode | Why |
|----------|------------------|-----|
| Personal local development | **IAM** | Simplest setup |
| Remote MCP for personal use | **API Key** | Easy + full features |
| Team shared MCP server | **API Key** | Simple shared auth |
| Multi-tenant SaaS | **JWT** | Per-user isolation |
| Untrusted users | **JWT** | Scoped credentials |
| CI/CD pipelines | **API Key** | Service account pattern |

## Open Questions

### Q1: How does quilt3.login_with_api_key() handle AWS credentials?

**Investigation needed**:

- Does it return AWS credentials directly?
- Does it require separate AWS credential configuration?
- What happens if AWS credentials aren't available?

**Action**: Test with real API key to verify behavior

**Impact**: May need to document AWS credential fallback behavior

### Q2: Can API keys be scoped to specific buckets/operations?

**Investigation needed**:

- Are Quilt API keys tied to user permissions?
- Can keys have limited scopes?
- How are permissions enforced?

**Action**: Review Quilt API key documentation and test

**Impact**: May affect security recommendations

### Q3: Should API key + JWT both being set be an error?

**Current decision**: API key takes precedence (mode priority)

**Alternative**: Raise error if both set (force explicit choice)

**Decision needed**: Based on user feedback and common usage patterns

### Q4: Should we support multiple API keys?

**Use case**: Failover or rotation scenarios

**Current decision**: Single API key only

**Future enhancement**: Could add `QUILT_API_KEY_LIST` if needed

## Related Specifications

- [spec/a10-multiuser/04-finish-jwt.md](../a10-multiuser/04-finish-jwt.md) - JWT authentication mode
- [spec/a10-multiuser/01-stateless.md](../a10-multiuser/01-stateless.md) - Stateless deployment architecture
- [spec/a10-multiuser/02-test-stateless.md](../a10-multiuser/02-test-stateless.md) - Stateless testing
- [spec/a11-client-testing/01-protocol-testing.md](01-protocol-testing.md) - MCP protocol compliance

## References

- [Quilt API Key Documentation](https://docs.quilt.bio/quilt-python-sdk/api-reference/authentication#api-key-authentication)
- [quilt3.login_with_api_key() API](https://docs.quilt.bio/quilt-python-sdk/api-reference/authentication)
- [MCP HTTP Transport Specification](https://spec.modelcontextprotocol.io/specification/basic/transports/#http-with-sse)
- [Current IAM Auth Service](../../src/quilt_mcp/services/iam_auth_service.py)
- [Current JWT Auth Service](../../src/quilt_mcp/services/jwt_auth_service.py)
- [Search Implementation](../../src/quilt_mcp/search/backends/elasticsearch.py)
