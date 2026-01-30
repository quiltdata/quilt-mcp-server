# JWT Authentication Support for mcp-test.py

**Status**: Draft
**Created**: 2026-01-29
**Objective**: Add JWT authentication support to mcp-test.py to enable testing of stateless JWT-authenticated MCP deployments

## Problem Statement

The current [mcp-test.py](../../scripts/mcp-test.py) script supports testing MCP servers over HTTP and stdio transports, but lacks support for JWT authentication. This creates a testing gap for stateless deployments that require JWT tokens.

### Current State

**mcp-test.py Transport Support**:

- ✅ HTTP transport with JSON responses ([line 458-513](../../scripts/mcp-test.py#L458-L513))
- ✅ stdio transport for local testing ([line 515-555](../../scripts/mcp-test.py#L515-L555))
- ✅ SSE (Server-Sent Events) response parsing ([line 484-498](../../scripts/mcp-test.py#L484-L498))
- ❌ **No JWT authentication support**

**Current HTTP Request Setup** ([line 413-417](../../scripts/mcp-test.py#L413-L417)):

```python
self.session = requests.Session()
self.session.headers.update({
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/event-stream'
})
```

**Missing**:

- No `Authorization: Bearer <token>` header support
- No JWT token management
- No token expiration handling

### Testing Gap

**Current test targets** ([make.dev:25-31](../../make.dev#L25-L31)):

```makefile
test-all: lint test-catalog test-scripts mcpb-validate | $(RESULTS_DIR)
    # Runs all pytest tests including Docker integration
    # Does NOT specifically test stateless JWT mode
```

**Separate stateless test** ([make.dev:131-137](../../make.dev#L131-L137)):

```makefile
test-stateless: docker-build
    # Runs tests in tests/stateless/ directory
    # Requires TEST_DOCKER_IMAGE environment variable
```

**Problems**:

1. test-stateless runs pytest tests, not mcp-test.py integration tests
2. No way to test JWT-authenticated endpoints with mcp-test.py
3. test-all doesn't exercise JWT authentication paths
4. Stateless deployments require manual testing with JWT tokens

### Use Cases

**UC1: Testing stateless MCP deployments**

- Deploy MCP server with `MCP_REQUIRE_JWT=true`
- Generate valid JWT token
- Test all MCP endpoints with JWT authentication
- Verify tools and resources work correctly

**UC2: Integration testing JWT auth flow**

- Start Docker container in stateless JWT mode
- Programmatically generate JWT tokens
- Run full test suite (tools + resources)
- Verify session isolation and security

**UC3: Manual testing with real JWT tokens**

- User has deployed MCP server requiring JWT
- User generates JWT token from their auth system
- User runs mcp-test.py with `--jwt-token` to verify deployment
- Tests all functionality before client integration

## Requirements

### Functional Requirements

**FR1: JWT Token Support**

- Accept JWT token via `--jwt-token` command-line argument
- Add `Authorization: Bearer <token>` header to all HTTP requests
- Support for both stateless and stateful JWT modes
- Token validation happens server-side (client just passes it)

**FR2: Token Management**

- Store token in session headers (reuse across requests)
- No client-side token generation (tokens provided externally)
- No token refresh logic (tokens assumed valid for test duration)
- Clear error messages when auth fails (401/403 responses)

**FR3: Backward Compatibility**

- JWT support is **optional** - script works without JWT token
- No changes to stdio transport (JWT only for HTTP)
- Existing test configurations continue to work unchanged
- No breaking changes to command-line interface

**FR4: Test Configuration**

- Support JWT tokens in test configuration YAML
- Environment variable support: `MCP_JWT_TOKEN`
- Command-line argument takes precedence over env var
- Document JWT token format and requirements

**FR5: Error Handling**

- Detect 401 Unauthorized responses (missing/invalid token)
- Detect 403 Forbidden responses (insufficient permissions)
- Provide clear error messages with troubleshooting hints
- Exit with appropriate error codes

### Non-Functional Requirements

**NFR1: Security**

- Never log JWT tokens in verbose output
- Mask tokens in error messages (show first/last 4 chars only)
- Warn if JWT token passed on command line (prefer env var)
- Document secure token handling practices

**NFR2: Simplicity**

- Minimal code changes to existing functionality
- No new dependencies (use existing requests library)
- Single parameter to enable JWT mode
- No complex token generation logic

**NFR3: Testing**

- Verify JWT header is added correctly
- Test with valid and invalid tokens
- Verify error handling for auth failures
- Document JWT token generation for testing

**NFR4: Integration with test-all**

- Add new `test-stateless-mcp` target to make.dev
- Generate JWT tokens programmatically for CI testing
- Integrate with existing Docker test infrastructure
- Run as part of comprehensive test suite

## Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    mcp-test.py                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Command Line Arguments:                                     │
│  ├─ endpoint (required for HTTP)                            │
│  ├─ --jwt-token TOKEN (optional, new)                       │
│  ├─ --transport [http|stdio]                                │
│  └─ --tools-test, --resources-test, etc.                    │
│                                                               │
│  MCPTester.__init__():                                       │
│  ├─ If transport == "http":                                 │
│  │   ├─ Create requests.Session()                           │
│  │   ├─ Set Content-Type, Accept headers                    │
│  │   └─ If jwt_token provided:                              │
│  │       └─ Add Authorization: Bearer {token} header        │
│  │                                                           │
│  └─ If transport == "stdio":                                │
│      └─ No JWT support (stdio doesn't use HTTP headers)     │
│                                                               │
│  _make_http_request():                                       │
│  ├─ session.post(endpoint, json=request_data)               │
│  ├─ Authorization header sent automatically by session      │
│  └─ Handle 401/403 errors with JWT-specific messages        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                               │
                               │ HTTP + Authorization header
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              MCP Server (JWT Mode)                           │
├─────────────────────────────────────────────────────────────┤
│  FastMCP with MCP_REQUIRE_JWT=true                          │
│  ├─ Extracts JWT from Authorization header                  │
│  ├─ Validates JWT signature and claims                      │
│  ├─ Assumes AWS role from JWT claims                        │
│  └─ Returns scoped session                                  │
└─────────────────────────────────────────────────────────────┘
```

### Component Changes

#### 1. MCPTester.**init**() Modification

**Location**: [scripts/mcp-test.py:386-441](../../scripts/mcp-test.py#L386-L441)

**Current signature**:

```python
def __init__(
    self,
    endpoint: Optional[str] = None,
    process: Optional[subprocess.Popen] = None,
    stdin_fd: Optional[int] = None,
    stdout_fd: Optional[int] = None,
    verbose: bool = False,
    transport: str = "http"
):
```

**New signature** (add jwt_token parameter):

```python
def __init__(
    self,
    endpoint: Optional[str] = None,
    process: Optional[subprocess.Popen] = None,
    stdin_fd: Optional[int] = None,
    stdout_fd: Optional[int] = None,
    verbose: bool = False,
    transport: str = "http",
    jwt_token: Optional[str] = None  # NEW
):
```

**Logic changes**:

```python
if transport == "http":
    if not endpoint:
        raise ValueError("endpoint required for HTTP transport")
    self.endpoint = endpoint
    self.session = requests.Session()
    self.session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream'
    })

    # NEW: Add JWT authentication if token provided
    if jwt_token:
        self._log("JWT authentication enabled", "DEBUG")
        self.session.headers.update({
            'Authorization': f'Bearer {jwt_token}'
        })

    self.jwt_token = jwt_token  # Store for error handling
```

#### 2. Error Handling Enhancement

**Location**: [scripts/mcp-test.py:474-513](../../scripts/mcp-test.py#L474-L513)

**Current error handling**:

```python
try:
    response = self.session.post(...)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    raise Exception(f"HTTP request failed: {e}")
```

**Enhanced error handling**:

```python
try:
    response = self.session.post(...)

    # NEW: Special handling for auth errors
    if response.status_code == 401:
        if self.jwt_token:
            raise Exception(
                "Authentication failed: JWT token rejected (invalid or expired)\n"
                f"Token preview: {self._mask_token(self.jwt_token)}\n"
                "Troubleshooting:\n"
                "  - Verify token signature matches server JWT_SECRET\n"
                "  - Check token expiration (exp claim)\n"
                "  - Ensure token includes required claims (role_arn, etc.)"
            )
        else:
            raise Exception(
                "Authentication required: Server requires JWT token\n"
                "Solution: Pass --jwt-token TOKEN or set MCP_JWT_TOKEN env var"
            )

    if response.status_code == 403:
        raise Exception(
            "Authorization failed: Insufficient permissions\n"
            f"Token preview: {self._mask_token(self.jwt_token)}\n"
            "Troubleshooting:\n"
            "  - Verify JWT role_arn has necessary AWS permissions\n"
            "  - Check session_tags in token claims"
        )

    response.raise_for_status()

except requests.exceptions.RequestException as e:
    raise Exception(f"HTTP request failed: {e}")
```

**Helper method** (add to MCPTester class):

```python
def _mask_token(self, token: Optional[str]) -> str:
    """Mask JWT token for safe display (show first and last 4 chars)."""
    if not token:
        return "(none)"
    if len(token) <= 12:
        return "***"
    return f"{token[:4]}...{token[-4:]}"
```

#### 3. Command-Line Argument

**Location**: [scripts/mcp-test.py:1393-1471](../../scripts/mcp-test.py#L1393-L1471)

**Add new argument**:

```python
parser.add_argument(
    "--jwt-token",
    type=str,
    help="JWT token for authentication (HTTP transport only). "
         "Alternatively, set MCP_JWT_TOKEN environment variable. "
         "⚠️  Prefer env var for production use to avoid token exposure in logs."
)
```

**Token resolution logic** (add before creating tester):

```python
# Resolve JWT token (command line takes precedence over env var)
jwt_token = args.jwt_token or os.environ.get('MCP_JWT_TOKEN')

if jwt_token and transport != "http":
    print("⚠️  Warning: --jwt-token ignored for stdio transport")
    jwt_token = None

if jwt_token and args.jwt_token:
    # Token passed on command line - warn about security
    print("⚠️  Security Warning: JWT token passed on command line")
    print("    Prefer using MCP_JWT_TOKEN environment variable")
    print("    Command-line arguments may be visible in process lists\n")
```

**Pass token to tester**:

```python
if transport == "http":
    tester = MCPTester(
        endpoint=args.endpoint,
        verbose=args.verbose,
        transport="http",
        jwt_token=jwt_token  # NEW
    )
```

#### 4. Test Suite Runner Integration

**Location**: [scripts/mcp-test.py:652-740](../../scripts/mcp-test.py#L652-L740)

**Update signature**:

```python
@staticmethod
def run_test_suite(
    endpoint: str = None,
    stdin_fd: int = None,
    stdout_fd: int = None,
    transport: str = "http",
    verbose: bool = False,
    config: dict = None,
    run_tools: bool = False,
    run_resources: bool = False,
    specific_tool: str = None,
    specific_resource: str = None,
    process: Optional[subprocess.Popen] = None,
    selection_stats: Optional[Dict[str, Any]] = None,
    jwt_token: Optional[str] = None  # NEW
) -> bool:
```

**Pass token to tester instances**:

```python
if run_tools:
    if transport == "http":
        tester = ToolsTester(
            endpoint=endpoint,
            verbose=verbose,
            transport=transport,
            config=config,
            jwt_token=jwt_token  # NEW
        )
```

### File Structure

**Modified Files**:

- `scripts/mcp-test.py` - Add JWT token parameter and authentication logic
- `make.dev` - Add test-stateless-mcp target

**New Files**:

- `scripts/tests/jwt_helper.py` - Utility for generating test JWT tokens
- `docs/JWT_TESTING.md` - Documentation for JWT testing workflows

**No Changes Needed**:

- Test configuration YAML format (tokens passed via CLI/env, not config)
- Existing test targets (backward compatible)
- stdio transport (JWT is HTTP-only feature)

## Implementation Tasks

### Phase 1: Core JWT Support (Must Have)

**Estimated effort**: 4-6 hours

#### Task 1.1: Add JWT Token Parameter

**Goal**: Add jwt_token parameter to MCPTester class

**What to implement**:

- [ ] Add `jwt_token: Optional[str] = None` to `__init__()` signature
- [ ] Store jwt_token as instance variable
- [ ] Add Authorization header when jwt_token is provided (HTTP transport only)
- [ ] Log JWT mode enabled in debug output (without logging token)
- [ ] Add `_mask_token()` helper method for safe token display

**Files to modify**:

- `scripts/mcp-test.py` - MCPTester.**init**()

**Success criteria**:

- ✅ JWT token parameter accepted
- ✅ Authorization header added to HTTP session
- ✅ Token never logged in plain text
- ✅ stdio transport unaffected

#### Task 1.2: Enhanced Error Handling

**Goal**: Provide clear error messages for JWT authentication failures

**What to implement**:

- [ ] Detect 401 Unauthorized responses
- [ ] Detect 403 Forbidden responses
- [ ] Generate JWT-specific error messages with troubleshooting
- [ ] Distinguish between missing token vs invalid token
- [ ] Mask tokens in error messages

**Files to modify**:

- `scripts/mcp-test.py` - _make_http_request()

**Success criteria**:

- ✅ Clear error message when token missing but required
- ✅ Clear error message when token invalid
- ✅ Troubleshooting guidance included
- ✅ No token leakage in errors

#### Task 1.3: Command-Line Interface

**Goal**: Add --jwt-token argument and environment variable support

**What to implement**:

- [ ] Add `--jwt-token` argument to argparse
- [ ] Support `MCP_JWT_TOKEN` environment variable
- [ ] Command-line argument takes precedence over env var
- [ ] Warning when token passed on command line (security)
- [ ] Pass token through to tester instances

**Files to modify**:

- `scripts/mcp-test.py` - main() function argument parsing

**Success criteria**:

- ✅ Can specify token via --jwt-token
- ✅ Can specify token via MCP_JWT_TOKEN env var
- ✅ Security warning displayed for CLI tokens
- ✅ Token passed correctly to tester

#### Task 1.4: Update Test Suite Runner

**Goal**: Thread JWT token through run_test_suite() static method

**What to implement**:

- [ ] Add `jwt_token` parameter to `run_test_suite()`
- [ ] Pass token to ToolsTester instances
- [ ] Pass token to ResourcesTester instances
- [ ] Update ToolsTester and ResourcesTester to accept jwt_token

**Files to modify**:

- `scripts/mcp-test.py` - run_test_suite(), ToolsTester, ResourcesTester

**Success criteria**:

- ✅ JWT token propagated through test suite
- ✅ Both tools and resources tests work with JWT
- ✅ No token leakage in test output

### Phase 2: Testing Infrastructure (Should Have)

**Estimated effort**: 4-6 hours

#### Task 2.1: JWT Token Generation Helper

**Goal**: Create utility for generating test JWT tokens

**What to implement**:

- [ ] Create `scripts/tests/jwt_helper.py`
- [ ] Function: `generate_test_jwt(role_arn, secret, expiry_seconds=3600)`
- [ ] Support for standard claims: exp, iat, iss, aud
- [ ] Support for custom claims: role_arn, session_tags, external_id
- [ ] Use HS256 algorithm (matches JWT auth service)
- [ ] Command-line interface for manual token generation

**New file**:

- `scripts/tests/jwt_helper.py`

**Dependencies**:

- `PyJWT` library (likely already in dependencies)

**Example usage**:

```python
from scripts.tests.jwt_helper import generate_test_jwt

token = generate_test_jwt(
    role_arn="arn:aws:iam::123456789:role/test-role",
    secret="test-secret",
    expiry_seconds=3600
)

# Returns: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Success criteria**:

- ✅ Generates valid JWT tokens
- ✅ Tokens accepted by JWT auth service
- ✅ Can customize expiry and claims
- ✅ CLI interface for manual testing

#### Task 2.2: Add test-stateless-mcp Target

**Goal**: Create make target for testing stateless MCP with JWT

**What to implement**:

- [ ] Add `test-stateless-mcp` target to make.dev
- [ ] Generate test JWT token using jwt_helper.py
- [ ] Start Docker container with `MCP_REQUIRE_JWT=true`
- [ ] Run mcp-test.py with generated JWT token
- [ ] Test both tools and resources
- [ ] Report results

**Files to modify**:

- `make.dev` - Add new target after test-stateless

**Example implementation**:

```makefile
test-stateless-mcp: docker-build
 @echo "🧪 Testing stateless MCP deployment with JWT authentication..."
 @echo "Step 1: Generating test JWT token..."
 @JWT_TOKEN=$$(uv run python scripts/tests/jwt_helper.py generate \
  --role-arn "arn:aws:iam::123456789012:role/TestRole" \
  --secret "test-secret-key" \
  --expiry 3600) && \
 echo "Step 2: Starting Docker container in JWT mode..." && \
 docker run -d --name mcp-jwt-test \
  -e MCP_REQUIRE_JWT=true \
  -e MCP_JWT_SECRET="test-secret-key" \
  -e QUILT_MCP_STATELESS_MODE=true \
  -p 8002:8000 \
  quilt-mcp:test && \
 sleep 2 && \
 echo "Step 3: Running mcp-test.py with JWT..." && \
 uv run python scripts/mcp-test.py http://localhost:8002/mcp \
  --jwt-token "$$JWT_TOKEN" \
  --tools-test --resources-test \
  --config scripts/tests/mcp-test.yaml && \
 docker stop mcp-jwt-test && docker rm mcp-jwt-test || \
 (docker stop mcp-jwt-test && docker rm mcp-jwt-test && exit 1)
 @echo "✅ Stateless JWT testing completed"
```

**Success criteria**:

- ✅ Target runs without manual intervention
- ✅ JWT token generated programmatically
- ✅ Docker container starts in JWT mode
- ✅ Tests pass with JWT authentication
- ✅ Clean teardown on success or failure

#### Task 2.3: Integration with test-all

**Goal**: Decide whether to include JWT testing in test-all

**Options**:

**Option A: Add to test-all (recommended)**

```makefile
test-all: lint test-catalog test-scripts test-stateless-mcp mcpb-validate | $(RESULTS_DIR)
    # Includes JWT testing
```

**Pros**:

- ✅ Ensures JWT auth path is always tested
- ✅ Catches JWT regressions early
- ✅ Comprehensive CI coverage

**Cons**:

- ❌ Slightly longer test execution (~30s more)
- ❌ Requires Docker (already required for test-all)

**Option B: Keep separate (status quo)**

```makefile
# Run manually when needed
test-stateless-mcp: ...
```

**Pros**:

- ✅ Faster test-all execution
- ✅ On-demand testing for JWT changes

**Cons**:

- ❌ JWT path not regularly tested
- ❌ Risk of JWT regressions

**Recommendation**: **Option A** - Add to test-all

**Rationale**:

- JWT is a critical security path
- Stateless mode is production deployment pattern
- Docker already required for test-all
- Marginal time increase (~30s) acceptable for coverage

**What to implement**:

- [ ] Add test-stateless-mcp to test-all dependencies
- [ ] Update test-all documentation
- [ ] Ensure proper ordering (after docker-build)

**Files to modify**:

- `make.dev` - Update test-all target

**Success criteria**:

- ✅ test-all runs JWT tests automatically
- ✅ CI pipeline executes JWT tests
- ✅ Documentation reflects JWT test inclusion

### Phase 3: Documentation (Must Have)

**Estimated effort**: 2-3 hours

#### Task 3.1: JWT Testing Documentation

**Goal**: Document JWT testing workflows and token generation

**What to create**:

- [ ] Create `docs/JWT_TESTING.md`
- [ ] Document --jwt-token usage
- [ ] Document MCP_JWT_TOKEN env var
- [ ] Document token generation with jwt_helper.py
- [ ] Security best practices for tokens
- [ ] Example workflows for common scenarios
- [ ] Troubleshooting guide for auth failures

**New file**:

- `docs/JWT_TESTING.md`

**Content outline**:

```markdown
# JWT Testing with mcp-test.py

## Overview
How to test JWT-authenticated MCP servers

## Quick Start
1. Generate token: `python scripts/tests/jwt_helper.py generate --role-arn ...`
2. Run tests: `python scripts/mcp-test.py http://localhost:8000/mcp --jwt-token TOKEN`

## Token Generation
- Using jwt_helper.py
- Manual token creation
- Token format and claims

## Testing Scenarios
- Local development with JWT
- CI/CD with programmatic tokens
- Manual testing with real tokens

## Troubleshooting
- 401 errors (invalid token)
- 403 errors (insufficient permissions)
- Token expiration
- Signature mismatches

## Security Best Practices
- Never commit tokens
- Use environment variables
- Rotate tokens regularly
```

**Success criteria**:

- ✅ Clear step-by-step instructions
- ✅ Example commands that work
- ✅ Troubleshooting covers common issues
- ✅ Security guidance included

#### Task 3.2: Update mcp-test.py --help

**Goal**: Ensure help text clearly documents JWT usage

**What to update**:

- [ ] Add JWT examples to epilog
- [ ] Document --jwt-token argument
- [ ] Reference environment variable
- [ ] Link to JWT_TESTING.md

**Files to modify**:

- `scripts/mcp-test.py` - ArgumentParser epilog

**Example addition**:

```python
epilog="""
...existing examples...

JWT Authentication:
  # Using environment variable (recommended)
  export MCP_JWT_TOKEN="eyJhbG..."
  mcp-test.py http://localhost:8000/mcp --tools-test

  # Using command-line argument
  mcp-test.py http://localhost:8000/mcp --jwt-token "eyJhbG..." --tools-test

  # Generate test token
  python scripts/tests/jwt_helper.py generate --role-arn arn:aws:iam::...

For detailed JWT testing docs, see: docs/JWT_TESTING.md
"""
```

**Success criteria**:

- ✅ Help text shows JWT examples
- ✅ Clear guidance on token sources
- ✅ Link to detailed documentation

#### Task 3.3: Update README and Test Documentation

**Goal**: Ensure project documentation reflects JWT testing capability

**What to update**:

- [ ] Update README.md with JWT testing section
- [ ] Update test documentation (if exists)
- [ ] Add JWT examples to testing guides
- [ ] Link to JWT_TESTING.md

**Files to modify**:

- `README.md`
- Any testing-related docs

**Success criteria**:

- ✅ JWT testing discoverable in docs
- ✅ Clear integration with existing workflows
- ✅ Examples provided

## Integration with test-all Recommendation

### Current State

**test-all** ([make.dev:25](../../make.dev#L25)):

```makefile
test-all: lint test-catalog test-scripts mcpb-validate | $(RESULTS_DIR)
    @echo "Running all tests..."
    # Runs pytest on all tests
```

**test-stateless** ([make.dev:131](../../make.dev#L131)):

```makefile
test-stateless: docker-build
    @echo "Running stateless deployment tests only..."
    # Runs pytest on tests/stateless/ directory
```

**Problems**:

1. test-all doesn't explicitly call test-stateless
2. test-stateless only runs pytest tests, not mcp-test.py integration tests
3. JWT authentication path never tested in normal CI flow

### Proposed Changes

#### Option 1: Add test-stateless-mcp to test-all (Recommended)

```makefile
test-all: lint test-catalog test-scripts test-stateless-mcp mcpb-validate | $(RESULTS_DIR)
    @echo "Running all tests (including stateless JWT)..."
    @uv sync --group test
    @export TEST_DOCKER_IMAGE=quilt-mcp:test && \
        export QUILT_DISABLE_CACHE=true && \
        export PYTHONPATH="src" && \
        uv run python -m pytest tests/ -v --cov=quilt_mcp \
            --cov-report=xml:$(RESULTS_DIR)/coverage-all.xml \
            --cov-report=term-missing --durations=7
```

**Pros**:

- ✅ JWT path tested on every test-all run
- ✅ Catches JWT regressions immediately
- ✅ Provides end-to-end JWT validation
- ✅ Natural evolution of test suite

**Cons**:

- ❌ Adds ~30-45 seconds to test-all execution
- ❌ Requires Docker (already required)

**Impact on workflow**:

- Developers running `make test-all` automatically test JWT
- CI pipeline validates JWT auth without extra configuration
- Stateless mode becomes first-class testing citizen

#### Option 2: Replace test-stateless with test-stateless-mcp

```makefile
# Remove pytest-only test-stateless
# Replace with comprehensive test-stateless-mcp

test-stateless: test-stateless-mcp
    # Alias for backward compatibility
```

**Pros**:

- ✅ Consolidates stateless testing
- ✅ Single source of truth for stateless validation
- ✅ Cleaner naming

**Cons**:

- ❌ May break existing workflows expecting pytest-only tests
- ❌ Less granular testing control

#### Option 3: Keep Separate, Add to CI Only

```makefile
# test-all unchanged
test-all: lint test-catalog test-scripts mcpb-validate | $(RESULTS_DIR)
    ...

# test-stateless-mcp separate
test-stateless-mcp: docker-build
    ...

# New CI target
test-ci-complete: test-all test-stateless-mcp
    @echo "✅ Complete CI test suite passed"
```

**Pros**:

- ✅ Doesn't slow down local test-all
- ✅ Comprehensive CI coverage
- ✅ Backward compatible

**Cons**:

- ❌ JWT path not tested locally by default
- ❌ Two-tier test system (local vs CI)
- ❌ Developers might miss JWT regressions

### Recommendation: Option 1

**Rationale**:

1. **Security-critical path**: JWT auth is production security feature
2. **Acceptable cost**: 30-45s for comprehensive auth testing is reasonable
3. **Consistency**: Same tests run locally and in CI
4. **Early detection**: Developers catch JWT issues before CI

**Implementation**:

```makefile
test-all: lint test-catalog test-scripts docker-build test-stateless-mcp mcpb-validate | $(RESULTS_DIR)
    @echo "Running all tests (unit, integration, stateless JWT)..."
    @uv sync --group test
    @export TEST_DOCKER_IMAGE=quilt-mcp:test && \
        export QUILT_DISABLE_CACHE=true && \
        export PYTHONPATH="src" && \
        uv run python -m pytest tests/ -v --cov=quilt_mcp \
            --cov-report=xml:$(RESULTS_DIR)/coverage-all.xml \
            --cov-report=term-missing --durations=7
    @echo "✅ All tests passed (including stateless JWT authentication)"

test-stateless-mcp: docker-build
    @echo "🔐 Testing stateless MCP with JWT authentication..."
    @JWT_TOKEN=$$(uv run python scripts/tests/jwt_helper.py generate \
        --role-arn "arn:aws:iam::123456789012:role/TestRole" \
        --secret "test-secret-key" \
        --expiry 3600) && \
    docker run -d --name mcp-jwt-test \
        -e MCP_REQUIRE_JWT=true \
        -e MCP_JWT_SECRET="test-secret-key" \
        -e QUILT_MCP_STATELESS_MODE=true \
        -e AWS_REGION=us-east-1 \
        -p 8002:8000 \
        quilt-mcp:test && \
    sleep 3 && \
    (uv run python scripts/mcp-test.py http://localhost:8002/mcp \
        --jwt-token "$$JWT_TOKEN" \
        --tools-test --resources-test \
        --config scripts/tests/mcp-test.yaml && \
    docker stop mcp-jwt-test && docker rm mcp-jwt-test) || \
    (docker stop mcp-jwt-test && docker rm mcp-jwt-test && exit 1)
    @echo "✅ Stateless JWT testing completed"

# Keep test-stateless for backward compatibility (runs pytest only)
test-stateless: docker-build
    @echo "Running stateless deployment tests (pytest only)..."
    @echo "💡 For comprehensive JWT testing, run: make test-stateless-mcp"
    @export TEST_DOCKER_IMAGE=quilt-mcp:test && \
        export QUILT_DISABLE_CACHE=true && \
        export PYTHONPATH="src" && \
        uv run python -m pytest tests/stateless/ -v --tb=short --color=yes
```

## Testing Strategy

### Unit Testing

**New tests to add**:

- `tests/unit/test_mcp_test_jwt.py`
  - Test JWT header addition
  - Test token masking
  - Test error message generation
  - Mock HTTP requests with auth

**Scope**:

- Isolated testing of JWT functionality
- No real HTTP requests
- No real JWT token validation
- Focus on client-side logic

### Integration Testing

**New tests to add**:

- `tests/integration/test_jwt_authentication.py`
  - Test with real JWT tokens
  - Test with invalid tokens (401 expected)
  - Test with expired tokens (401 expected)
  - Test missing token when required (401 expected)

**Scope**:

- Real HTTP requests to test server
- Real JWT token generation and validation
- End-to-end auth flow
- Docker-based testing

### Manual Testing

**Test scenarios**:

1. **Valid JWT Token**:

   ```bash
   export MCP_JWT_TOKEN=$(python scripts/tests/jwt_helper.py generate ...)
   python scripts/mcp-test.py http://localhost:8000/mcp --tools-test
   # Expected: All tests pass
   ```

2. **Invalid JWT Token**:

   ```bash
   python scripts/mcp-test.py http://localhost:8000/mcp \
       --jwt-token "invalid-token" --tools-test
   # Expected: 401 error with clear message
   ```

3. **Missing JWT Token** (server requires):

   ```bash
   # Server has MCP_REQUIRE_JWT=true
   python scripts/mcp-test.py http://localhost:8000/mcp --tools-test
   # Expected: 401 error explaining JWT required
   ```

4. **JWT with Insufficient Permissions**:

   ```bash
   # Token has role_arn with limited permissions
   python scripts/mcp-test.py http://localhost:8000/mcp --tools-test
   # Expected: 403 error on protected operations
   ```

## Security Considerations

### Token Handling Best Practices

**DO**:

- ✅ Use environment variables for tokens (`MCP_JWT_TOKEN`)
- ✅ Mask tokens in logs and error messages
- ✅ Warn when tokens passed on command line
- ✅ Document token security in help text
- ✅ Generate tokens programmatically for CI

**DON'T**:

- ❌ Log tokens in verbose output
- ❌ Commit tokens to version control
- ❌ Pass tokens in URLs or config files
- ❌ Reuse tokens across environments
- ❌ Share tokens in documentation examples

### Token Lifecycle

**Generation**:

- Tokens generated by jwt_helper.py for testing
- Real tokens generated by auth system for production
- Short expiry for test tokens (1 hour default)

**Storage**:

- Test tokens: environment variables only
- Production tokens: secure secret management
- Never in config files or command history

**Transmission**:

- HTTPS only for token transmission
- Authorization header (not URL parameters)
- TLS 1.2+ required for production

**Revocation**:

- Test tokens expire after 1 hour
- Production tokens should support revocation
- No token persistence in mcp-test.py

## Success Criteria

### Phase 1 Success (Core Implementation)

- ✅ mcp-test.py accepts --jwt-token argument
- ✅ JWT token added to Authorization header correctly
- ✅ Clear error messages for auth failures
- ✅ Token masking prevents leakage
- ✅ Backward compatible (works without JWT)
- ✅ No breaking changes to existing tests

### Phase 2 Success (Testing Infrastructure)

- ✅ jwt_helper.py generates valid test tokens
- ✅ test-stateless-mcp target works end-to-end
- ✅ JWT tests integrated into test-all (optional)
- ✅ CI pipeline validates JWT authentication
- ✅ Docker container starts in JWT mode successfully

### Phase 3 Success (Documentation)

- ✅ JWT_TESTING.md provides clear guidance
- ✅ Help text includes JWT examples
- ✅ README documents JWT testing capability
- ✅ Security best practices documented
- ✅ Troubleshooting guide covers common issues

### Overall Success

- ✅ Can test stateless JWT deployments end-to-end
- ✅ JWT authentication path covered in CI
- ✅ Clear documentation and examples
- ✅ Secure token handling
- ✅ No disruption to existing workflows

## Related Specifications

- [01-protocol-testing.md](01-protocol-testing.md) - MCP protocol compliance testing
- [02-api-key-auth.md](02-api-key-auth.md) - Alternative authentication method
- [../a10-multitenant/04-finish-jwt.md](../a10-multitenant/04-finish-jwt.md) - JWT authentication implementation
- [../a10-multitenant/01-stateless.md](../a10-multitenant/01-stateless.md) - Stateless architecture

## References

- [Current mcp-test.py implementation](../../scripts/mcp-test.py)
- [make.dev test targets](../../make.dev)
- [JWT Auth Service](../../src/quilt_mcp/services/jwt_auth_service.py)
- [Stateless test directory](../../tests/stateless/)

## Open Questions

### Q1: Should jwt_helper.py support multiple signing algorithms?

**Current plan**: HS256 only (matches JWT auth service)

**Alternatives**:

- RS256 (asymmetric signatures)
- ES256 (elliptic curve)

**Decision needed**: Based on production requirements

**Impact**: Minimal - can extend later if needed

### Q2: Should we support JWT refresh tokens?

**Current plan**: No - tokens assumed valid for test duration

**Rationale**:

- Tests run for < 5 minutes typically
- 1-hour expiry more than sufficient
- Refresh adds complexity for minimal benefit

**Future enhancement**: If long-running tests needed

### Q3: Should test-stateless be replaced or kept?

**Current plan**: Keep both

- `test-stateless` - pytest tests only (backward compatible)
- `test-stateless-mcp` - mcp-test.py with JWT (new comprehensive test)

**Alternative**: Replace test-stateless entirely

**Decision needed**: Based on team preference

### Q4: What AWS role should test tokens assume?

**Current plan**: Configurable role_arn in jwt_helper.py

**For CI testing**: Mock role ARN (no real AWS access needed if mocked)

**For manual testing**: User's actual role ARN

**Decision needed**: What's the default for CI?

## Implementation Timeline

**Phase 1: Core JWT Support** - 1 day

- Task 1.1: Add JWT token parameter (2 hours)
- Task 1.2: Enhanced error handling (2 hours)
- Task 1.3: Command-line interface (2 hours)
- Task 1.4: Update test suite runner (2 hours)

**Phase 2: Testing Infrastructure** - 1 day

- Task 2.1: JWT token generation helper (3 hours)
- Task 2.2: Add test-stateless-mcp target (2 hours)
- Task 2.3: Integration with test-all (1 hour)

**Phase 3: Documentation** - 0.5 days

- Task 3.1: JWT testing documentation (2 hours)
- Task 3.2: Update mcp-test.py help (1 hour)
- Task 3.3: Update README and test docs (1 hour)

**Total estimated effort**: 2.5 days (20 hours)

**Critical path**:

1. Phase 1 (core functionality) - blocks everything
2. Phase 2.1 (jwt_helper.py) - blocks integration testing
3. Phase 2.2 (test-stateless-mcp) - blocks test-all integration
4. Phase 3 (documentation) - can happen in parallel

**Minimum viable implementation**: Phase 1 only (enables JWT testing)

**Recommended scope**: All phases (complete feature with testing and docs)
