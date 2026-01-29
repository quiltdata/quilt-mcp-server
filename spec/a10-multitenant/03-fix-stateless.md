# Fix Stateless Deployment Test Failures

**Status**: Draft
**Created**: 2026-01-28
**Objective**: Fix the 4 failing tests in the stateless deployment test suite

## Test Results Summary

Current status from `make test-stateless`:

- **12 passing tests** ✅
- **4 failing tests** ❌
- **1 skipped test** (requires implementation)

## What's Broken

### Failure 1: MCP Protocol Endpoint Missing

**Test**: `test_tools_list_endpoint`

**Problem**: The MCP protocol endpoint `/mcp/v1/tools/list` returns 404 Not Found

**Observed behavior**:

- Server root (`/`) responds correctly with status and version info
- MCP protocol endpoints are not accessible
- Clients cannot discover available tools

**Why this matters**:

- MCP clients use the `tools/list` endpoint to discover capabilities
- Without proper routing, the server cannot participate in MCP protocol communication
- This is a fundamental requirement for MCP server operation

**What needs investigation**:

- Is the MCP protocol router properly configured for HTTP transport?
- Are MCP endpoints registered correctly in the FastAPI app?
- Is there a routing conflict or missing route configuration?
- Does the HTTP transport layer properly handle MCP protocol paths?

### Failure 2: Filesystem Write Violations

**Test**: `test_no_filesystem_writes_outside_tmpfs`

**Problem**: Container wrote to `/app` directory despite read-only filesystem constraint

**Observed behavior**:

- Files were created in `/app` (outside allowed tmpfs directories)
- Read-only filesystem requirement not enforced
- Application attempts to write to locations that should be immutable

**Why this matters**:

- Stateless deployment requires strict read-only root filesystem
- Writes outside tmpfs can persist state across requests (security risk)
- Violates multitenant isolation requirements
- Creates potential for cross-tenant data leakage

**What needs investigation**:

- What is being written to `/app`?
- Is it cache files, configuration, logs, or telemetry?
- Is quilt3 attempting to create directories in the application directory?
- Are there temporary files being created in the wrong location?

**What needs to be fixed**:

- Redirect all writable locations to tmpfs directories (`/tmp`, `/app/.cache`, `/run`)
- Configure application to never write to `/app` root
- Set `HOME=/tmp` or similar to redirect user directories
- Ensure quilt3 and all dependencies respect read-only constraints

### Failure 3: Missing JWT Error Messages

**Test**: `test_request_without_jwt_fails_clearly`

**Problem**: Requests without JWT return generic "404 Not Found" instead of clear authentication error

**Observed behavior**:

- Status: 404
- Response: "Not Found"
- No mention of JWT, authorization, or authentication requirements

**Why this matters**:

- Developers cannot debug authentication issues without clear error messages
- Generic 404 suggests endpoint doesn't exist (misleading)
- Production deployments need actionable error messages
- Poor developer experience leads to wasted time troubleshooting

**Expected behavior**:

- Status: 401 Unauthorized (or 403 Forbidden)
- Response should clearly state one of:
  - "JWT token required"
  - "Authorization header missing"
  - "Bearer token not provided"

**What needs to be fixed**:

- Authentication middleware must intercept requests before routing
- Missing JWT should return 401 with clear message
- Error response should explain what's required
- Error should not expose internal implementation details

### Failure 4: Invalid JWT Error Messages

**Test**: `test_request_with_malformed_jwt_fails_clearly`

**Problem**: Requests with malformed JWT return generic "404 Not Found" instead of validation error

**Observed behavior**:

- Status: 404
- Response: "Not Found"
- No explanation of JWT validation failure

**Why this matters**:

- Malformed JWT suggests misconfiguration or token generation bug
- Generic 404 hides the real problem
- Developers cannot distinguish between missing endpoint and auth failure
- Production debugging becomes significantly harder

**Expected behavior**:

- Status: 401 Unauthorized
- Response should clearly state one of:
  - "Invalid JWT token"
  - "Token signature invalid"
  - "Malformed authorization header"
  - "JWT validation failed: [specific reason]"

**What needs to be fixed**:

- JWT validation should happen before routing
- Invalid token format should return specific error
- Token signature failures should be clearly identified
- Expired tokens should be distinguished from invalid tokens

## Root Cause Analysis

### Common Theme: HTTP Transport Layer Issues

All 4 failures point to issues in the HTTP transport layer implementation:

1. **Routing**: MCP endpoints not properly registered
2. **Authentication Middleware**: Not intercepting requests before routing
3. **Error Handling**: Generic HTTP errors instead of protocol-aware responses
4. **Filesystem Configuration**: Application not respecting read-only constraints

### Architecture Gap

**Current state** (inferred from failures):

- HTTP server accepts requests at root (`/`)
- MCP protocol endpoints not accessible
- Authentication happens after routing (if at all)
- Error handling returns generic HTTP status codes
- Filesystem writes not properly redirected

**Required state**:

- HTTP server serves both root and MCP protocol paths
- Authentication middleware runs before routing
- MCP-aware error responses with clear messages
- All writes redirected to tmpfs locations
- Read-only filesystem enforced by container runtime

## What Needs to Be Fixed

### Task 1: Fix MCP Protocol Endpoint Routing

**Goal**: Make `/mcp/v1/tools/list` and other MCP endpoints accessible

**Tasks**:

1. Investigate HTTP transport router configuration
2. Verify MCP protocol endpoint registration in FastAPI app
3. Ensure all MCP paths are properly mounted
4. Test that MCP protocol messages are routed correctly
5. Verify endpoint responds with proper MCP protocol schema

**Success criteria**:

- `/mcp/v1/tools/list` returns 200 OK
- Response contains list of available tools in MCP format
- All other MCP protocol endpoints accessible
- MCP clients can successfully connect and query tools

**Acceptance test**:

```
Start container in stateless mode
→ Call GET/POST /mcp/v1/tools/list
→ Expect: 200 OK with valid MCP tools/list response
→ Response contains tool definitions
```

### Task 2: Enforce Read-Only Filesystem

**Goal**: Ensure container writes only to tmpfs directories

**Tasks**:

1. Audit application code for filesystem writes
2. Identify what is being written to `/app`
3. Configure application to use tmpfs locations for all writes
4. Set environment variables to redirect writable directories (e.g., `HOME=/tmp`)
5. Configure quilt3 to not create cache/config directories outside tmpfs
6. Verify container startup with `--read-only` flag
7. Test that application functions correctly with read-only root filesystem

**Success criteria**:

- Container starts successfully with `--read-only` flag
- No writes to `/app` directory
- All writes go to `/tmp`, `/app/.cache`, or `/run` (tmpfs mounts)
- Application operates normally with filesystem constraints
- No "Read-only file system" errors in logs

**Acceptance test**:

```
Start container with --read-only and tmpfs mounts
→ Execute all MCP tools
→ Inspect filesystem with `docker diff`
→ Expect: Only /tmp, /app/.cache, /run show changes
→ No files created in /app root or other locations
```

### Task 3: Implement Clear JWT Error Messages (Missing JWT)

**Goal**: Return actionable error when JWT token is missing

**Tasks**:

1. Add authentication middleware that runs before routing
2. Check for Authorization header presence
3. If missing and `MCP_REQUIRE_JWT=true`, return 401 with clear message
4. Error response should include:
   - Status: 401 Unauthorized
   - Message: Clear statement that JWT is required
   - Details: How to provide JWT (Authorization header format)
5. Ensure error is returned before attempting to route request

**Success criteria**:

- Request without Authorization header returns 401 (not 404)
- Error message mentions "JWT" or "Authorization" or "Bearer token"
- Error message is actionable (tells user what to do)
- Error does not reveal internal implementation details
- Consistent across all MCP endpoints

**Acceptance test**:

```
Start container with MCP_REQUIRE_JWT=true
→ Call /mcp/v1/tools/list without Authorization header
→ Expect: 401 Unauthorized
→ Response body contains one of:
   - "JWT token required"
   - "Authorization header missing"
   - "Bearer token not provided"
```

### Task 4: Implement Clear JWT Error Messages (Invalid JWT)

**Goal**: Return specific error when JWT token is malformed or invalid

**Tasks**:

1. Parse Authorization header in authentication middleware
2. Validate JWT format (three parts separated by dots)
3. Attempt signature verification
4. Return specific error based on failure type:
   - Malformed format: "Malformed JWT token"
   - Invalid signature: "JWT signature verification failed"
   - Expired token: "JWT token expired"
   - Invalid claims: "JWT claims invalid"
5. Return 401 status with specific error message
6. Log detailed error for debugging (but don't expose in response)

**Success criteria**:

- Malformed JWT returns 401 with descriptive error (not 404)
- Error message identifies the specific problem
- Different JWT failures return different error messages
- Error response is consistent across all endpoints
- Helpful for debugging but doesn't expose security details

**Acceptance test**:

```
Start container with MCP_REQUIRE_JWT=true
→ Call /mcp/v1/tools/list with "Bearer invalid-jwt-string"
→ Expect: 401 Unauthorized
→ Response body contains one of:
   - "Invalid JWT token"
   - "Malformed JWT token"
   - "JWT signature invalid"
   - "JWT validation failed"
```

## Implementation Order

**Phase 1: Authentication (Highest Priority)**

1. Task 3: Fix missing JWT error messages
2. Task 4: Fix invalid JWT error messages

**Rationale**: Authentication must work before anything else. Without proper auth errors, developers cannot test or debug the system.

**Phase 2: Routing**
3. Task 1: Fix MCP protocol endpoint routing

**Rationale**: Once auth is working, endpoints need to be accessible. This unblocks tool discovery.

**Phase 3: Filesystem**
4. Task 2: Enforce read-only filesystem

**Rationale**: Most complex change; requires investigation and potentially multiple fixes. Can be done last since it doesn't block functionality.

## Testing Strategy

### Verification After Each Phase

**After Phase 1** (Authentication):

- Run: `pytest tests/stateless/test_jwt_authentication.py`
- Expect: `test_request_without_jwt_fails_clearly` passes
- Expect: `test_request_with_malformed_jwt_fails_clearly` passes

**After Phase 2** (Routing):

- Run: `pytest tests/stateless/test_basic_execution.py::test_tools_list_endpoint`
- Expect: Test passes
- Verify: MCP clients can discover tools

**After Phase 3** (Filesystem):

- Run: `pytest tests/stateless/test_basic_execution.py::test_no_filesystem_writes_outside_tmpfs`
- Expect: Test passes
- Verify: `docker diff` shows no changes outside tmpfs

**Full Test Suite**:

- Run: `make test-stateless`
- Expect: All 17 tests pass (currently 12 pass, 4 fail, 1 skip)

## Investigation Required

### Before Starting Implementation

The following information needs to be gathered:

**1. HTTP Transport Architecture**:

- How is the FastAPI app configured in HTTP transport mode?
- Where are MCP protocol endpoints registered?
- Is there a separate router for MCP paths vs. health check paths?
- Does the transport layer properly handle MCP protocol messages?

**2. Authentication Middleware**:

- Where is JWT validation currently happening?
- Is there existing authentication middleware?
- Does it run before or after routing?
- What error responses does it currently return?

**3. Filesystem Writes**:

- What specific files are being written to `/app`?
- Run container and examine `docker diff` output
- Check if it's quilt3, FastAPI, or application code writing files
- Identify if writes are cache, logs, telemetry, or something else

**4. Current Error Handling**:

- Where do 404 errors come from in the auth flow?
- Is routing happening before authentication?
- Are there error handlers that override auth failures?
- What's the order of middleware execution?

## Success Criteria

### Definition of Done

This specification is complete when:

1. ✅ All 4 failing tests pass consistently
2. ✅ `make test-stateless` shows 16+ tests passing (1 may remain skipped)
3. ✅ Container runs successfully with `--read-only` flag
4. ✅ MCP clients can discover and call tools
5. ✅ Clear, actionable error messages for auth failures
6. ✅ No filesystem writes outside tmpfs directories
7. ✅ All fixes documented and tested

### Regression Prevention

After fixes are implemented:

1. ✅ CI runs `make test-stateless` on every commit
2. ✅ Tests fail if any stateless constraint violated
3. ✅ Documentation updated to reflect proper configuration
4. ✅ Example deployment configurations show correct settings

## Out of Scope

The following are **not** part of this specification:

- Performance optimization
- Load testing
- Horizontal scaling
- Multi-region deployment
- Advanced security hardening (beyond read-only FS)
- Monitoring and observability improvements
- JWT token generation/refresh logic
- Integration with specific auth providers

These may be addressed in future specifications.

## Dependencies

### Required Before Implementation

1. Understanding of current HTTP transport implementation
2. Access to test environment with valid JWT tokens
3. Ability to run Docker containers locally with security constraints
4. pytest test infrastructure working

### No External Dependencies

All fixes should be possible with:

- Current FastAPI framework
- Existing JWT libraries
- Standard Docker configuration
- No new external services required

## Risk Assessment

### Low Risk

- **Task 3 & 4** (Auth error messages): Isolated to error handling logic
- **Task 1** (Endpoint routing): Well-understood FastAPI routing

### Medium Risk

- **Task 2** (Filesystem constraints): May require changes to quilt3 configuration or multiple application components

### Mitigation

- Implement in phases (auth → routing → filesystem)
- Test each phase independently
- Add comprehensive logging to debug issues
- Keep development mode working during changes

## Related Specifications

- `01-stateless.md` - Overall stateless architecture requirements
- `02-test-stateless.md` - Test suite specification and requirements
- (Future) `04-deployment-guide.md` - Production deployment instructions

## References

- Test suite: `tests/stateless/`
- Current failures: Output from `make test-stateless`
- MCP Protocol: <https://modelcontextprotocol.io>
- FastAPI middleware: <https://fastapi.tiangolo.com/tutorial/middleware/>
- Docker security: <https://docs.docker.com/engine/security/>
