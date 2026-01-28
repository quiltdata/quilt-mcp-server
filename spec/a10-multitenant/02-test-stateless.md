# Test Stateless Deployment Target

**Status**: Draft
**Created**: 2026-01-28
**Objective**: Define test infrastructure to validate true stateless, multitenant-ready operation

## Purpose

Create a `make test-stateless` target (or equivalent) that runs the Docker container in a configuration that **emulates production multitenant deployment constraints**. This serves as:

1. **Validation Gate**: Proves container operates without persistent state
2. **Security Test**: Verifies container works under restricted permissions
3. **CI/CD Check**: Automated verification before deployment
4. **Documentation**: Living example of production configuration

## Multitenant Deployment Characteristics

A true multitenant deployment must have:

### Hard Constraints (Must Enforce)
1. **Read-only root filesystem** - No writes except tmpfs
2. **No persistent volumes** - State cleared on every restart
3. **JWT-only authentication** - No local credential files
4. **Non-root user** - Reduced privilege attack surface
5. **Minimal capabilities** - Drop all unnecessary Linux capabilities
6. **No privilege escalation** - Cannot gain additional privileges at runtime
7. **Isolated network** - No assumptions about network access
8. **Resource limits** - CPU and memory constraints

### Soft Constraints (Should Verify)
1. **Concurrent requests** - Multiple users simultaneously
2. **Request isolation** - No state leakage between requests
3. **Ephemeral tmpfs** - Temp files cleared between runs
4. **Environment-only config** - No filesystem configuration
5. **Graceful degradation** - Clear errors when misconfigured

## Test Target Requirements

### What the Target Should Do

The `test-stateless` target should:

1. **Build the Docker image** (or use pre-built test image)
2. **Run container with production-like constraints**
3. **Execute comprehensive tool test suite**
4. **Verify no persistent state created**
5. **Report pass/fail with clear diagnostics**
6. **Clean up all resources** (containers, tmpfs)

### What the Target Should NOT Do

- ❌ Mount any host directories (no `-v` flags except tmpfs)
- ❌ Run as root (unless testing escalation prevention)
- ❌ Allow writable filesystem outside tmpfs
- ❌ Use `~/.quilt/` or `~/.aws/` credentials
- ❌ Persist any data between test runs
- ❌ Skip security constraints for convenience

## Docker Runtime Configuration

### Required Flags

The container MUST be started with:

```bash
# Security constraints
--read-only                              # Read-only root filesystem
--security-opt=no-new-privileges:true    # Prevent privilege escalation
--cap-drop=ALL                           # Drop all capabilities
--cap-add=NET_BIND_SERVICE              # Only if binding port < 1024

# Filesystem
--tmpfs /tmp:size=100M,mode=1777         # Ephemeral temp directory
--tmpfs /app/.cache:size=50M,mode=700    # If quilt3 needs cache dir
--tmpfs /run:size=10M,mode=755           # Runtime data if needed

# Resource limits
--memory=512M                            # Max memory allocation
--memory-swap=512M                       # No swap space
--cpus=1.0                               # CPU limit

# Network isolation (optional for testing)
--network=none                           # Or isolated test network

# No volume mounts (verify empty)
# (no -v flags at all)
```

### Required Environment Variables

```bash
# Stateless mode enforcement
MCP_REQUIRE_JWT=true                     # Force JWT-only auth
QUILT_DISABLE_CACHE=true                 # If supported by quilt3
HOME=/tmp                                # Redirect home directory

# Catalog configuration (test instance)
QUILT_CATALOG_URL=https://test.quiltdata.com

# AWS credentials (test/mock)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test_key_id           # Or use IAM role
AWS_SECRET_ACCESS_KEY=test_secret       # Or use IAM role

# Optional: Observability
LOG_LEVEL=DEBUG                          # Verbose logging for test
QUILT_MCP_STATELESS_MODE=true           # Flag to enable extra checks
```

### Forbidden Configurations

The test MUST fail if:

```bash
# ❌ Volume mounts to host filesystem
-v ~/.quilt:/root/.quilt
-v ~/.aws:/root/.aws
-v /var/lib/quilt:/data

# ❌ Writable root filesystem
# (missing --read-only flag)

# ❌ Privileged mode
--privileged
--cap-add=ALL

# ❌ Permissive user
# (running as root without dropping privileges)

# ❌ Persistent storage
-v quilt-data:/app/data
--mount type=bind,...
```

## Test Scenarios

### Scenario 1: Basic Tool Execution

**Goal**: Verify all tools work with read-only filesystem

**Test steps**:
1. Start container with stateless constraints
2. Call `tools/list` via MCP protocol
3. Execute each tool with minimal valid parameters
4. Verify successful responses (or expected errors)

**Success criteria**:
- ✅ All tools return responses
- ✅ No filesystem write errors
- ✅ Container continues running after all tool calls

**Failure indicators**:
- ❌ `Read-only file system` errors
- ❌ Tools attempting to write outside `/tmp`
- ❌ Container crashes or hangs

### Scenario 2: JWT Authentication

**Goal**: Verify JWT-only authentication works

**Test steps**:
1. Start container with `MCP_REQUIRE_JWT=true`
2. Attempt tool call without JWT (should fail clearly)
3. Attempt tool call with invalid JWT (should fail clearly)
4. Attempt tool call with valid JWT (should succeed)

**Success criteria**:
- ✅ Clear error message when JWT missing
- ✅ Clear error message when JWT invalid
- ✅ Successful execution with valid JWT
- ✅ No fallback to `~/.quilt/` credentials

**Failure indicators**:
- ❌ Uses local credentials despite JWT requirement
- ❌ Unclear error messages
- ❌ Container tries to write credentials to filesystem

### Scenario 3: Concurrent Request Isolation

**Goal**: Verify no state leakage between concurrent requests

**Test steps**:
1. Start container with stateless constraints
2. Send multiple concurrent MCP requests with different JWTs
3. Each request should have different context (user identity, bucket access)
4. Verify responses are correctly isolated

**Success criteria**:
- ✅ Request A doesn't see Request B's data
- ✅ Concurrent requests complete successfully
- ✅ No race conditions or shared state bugs

**Failure indicators**:
- ❌ Permission cache returns wrong user's permissions
- ❌ Boto3 session shared across requests
- ❌ Context leakage between requests

### Scenario 4: No Persistent State

**Goal**: Verify container is truly stateless

**Test steps**:
1. Start container with stateless constraints
2. Execute tools that might cache data (package operations, search)
3. Stop and remove container
4. Start new container (same image, same config)
5. Execute same tools again

**Success criteria**:
- ✅ Second run behaves identically to first run
- ✅ No cached data carried over
- ✅ No "warm start" behavior

**Failure indicators**:
- ❌ Second run faster due to caching
- ❌ Data from first run visible in second run
- ❌ Persistent files found outside tmpfs

### Scenario 5: Filesystem Write Attempts

**Goal**: Verify all writes go to tmpfs only

**Test steps**:
1. Start container with stateless constraints
2. Execute full tool suite
3. Inspect filesystem for any writes outside `/tmp`, `/app/.cache`, `/run`
4. Verify tmpfs directories contain only expected temporary files

**Success criteria**:
- ✅ No writes to `/app`, `/root`, `/var`, etc.
- ✅ Only tmpfs directories contain files
- ✅ No hidden files in unexpected locations

**Failure indicators**:
- ❌ Files found in `/app/.quilt/`
- ❌ Cache files in `/root/.cache/`
- ❌ Telemetry files in non-tmpfs locations

### Scenario 6: Resource Constraints

**Goal**: Verify container operates within resource limits

**Test steps**:
1. Start container with memory/CPU limits
2. Execute resource-intensive operations (large package operations, search)
3. Monitor memory and CPU usage
4. Verify graceful handling of resource exhaustion

**Success criteria**:
- ✅ Container stays within memory limit
- ✅ No memory leaks over time
- ✅ Graceful error on resource exhaustion

**Failure indicators**:
- ❌ Container killed by OOM
- ❌ Memory usage grows unbounded
- ❌ CPU throttling causes hangs

### Scenario 7: Security Hardening

**Goal**: Verify security constraints are effective

**Test steps**:
1. Start container with minimal capabilities
2. Attempt to escalate privileges (should fail)
3. Attempt to access restricted filesystem (should fail)
4. Attempt to make network connections (if network=none, should fail)

**Success criteria**:
- ✅ Cannot gain additional privileges
- ✅ Cannot write to read-only filesystem
- ✅ Cannot bypass security constraints

**Failure indicators**:
- ❌ Successfully escalates privileges
- ❌ Bypasses read-only filesystem
- ❌ Escapes container constraints

## Verification Checks

### Pre-Flight Checks (Before Test)

Before running tests, verify:

1. **Docker image exists** and is built with correct settings
2. **Test environment variables** are set (JWT tokens, AWS credentials)
3. **Network access** to test catalog (or mock server running)
4. **No conflicting containers** running on same ports

### Runtime Checks (During Test)

While tests run, monitor:

1. **Container logs** for errors or warnings
2. **Filesystem writes** using `docker diff` or inspection
3. **Resource usage** (memory, CPU, I/O)
4. **Network connections** (if monitoring enabled)

### Post-Test Checks (After Test)

After test completes, verify:

1. **Container removed** cleanly
2. **No volumes created** unintentionally
3. **Tmpfs directories cleared**
4. **No orphaned resources** (networks, volumes)

### Success Reporting

Test report should include:

```
Stateless Deployment Test Results
==================================

Configuration:
  ✓ Read-only filesystem: enabled
  ✓ Tmpfs mounts: /tmp (100M), /app/.cache (50M)
  ✓ Security: no-new-privileges, cap-drop=ALL
  ✓ Resources: 512M memory, 1.0 CPU
  ✓ Authentication: JWT-only mode

Test Scenarios:
  ✓ Basic tool execution: 84/84 tools passed
  ✓ JWT authentication: 3/3 tests passed
  ✓ Concurrent isolation: 10 concurrent requests, no leakage
  ✓ No persistent state: verified across 2 container restarts
  ✓ Filesystem writes: only tmpfs directories used
  ✓ Resource constraints: peak 345M memory, 0.7 CPU
  ✓ Security hardening: all privilege escalation attempts failed

Filesystem Inspection:
  ✓ No writes to /app
  ✓ No writes to /root
  ✓ No writes to /var
  ✓ Tmpfs /tmp: 12 files, 3.2M
  ✓ Tmpfs /app/.cache: 0 files (unused)

Warnings: None
Errors: None

Result: PASS ✓
Container is production-ready for multitenant deployment.
```

### Failure Reporting

On failure, report should include:

```
Stateless Deployment Test Results
==================================

Result: FAIL ✗

Failed Checks:
  ✗ Filesystem writes: Found 3 files outside tmpfs
    - /app/.quilt/mcp_telemetry.jsonl (1.1M)
    - /root/.cache/pip/... (15M)
    - /var/log/quilt.log (234K)

  ✗ JWT authentication: Fallback to ~/.quilt/ credentials
    - Expected: Error "JWT required in stateless mode"
    - Actual: Used local credentials from ~/.quilt/

Recommendations:
  1. Set QUILT_DISABLE_CACHE=true to prevent telemetry writes
  2. Configure HOME=/tmp to redirect cache directories
  3. Set MCP_REQUIRE_JWT=true and remove ~/.quilt/ directory

See logs: /tmp/test-stateless-20260128-143022.log
```

## Test Implementation Strategy

### Option A: Make Target

```makefile
# Conceptual structure (not actual code)

.PHONY: test-stateless
test-stateless:
    # 1. Build test image
    # 2. Generate test JWT tokens
    # 3. Start container with stateless constraints
    # 4. Run MCP protocol test suite
    # 5. Verify filesystem state
    # 6. Stop and remove container
    # 7. Report results
```

### Option B: Shell Script

```bash
# Conceptual structure (not actual code)

#!/bin/bash
# scripts/test-stateless.sh

# Steps:
# 1. Validate prerequisites
# 2. Build/pull Docker image
# 3. Configure test environment
# 4. Run container with production constraints
# 5. Execute test scenarios
# 6. Collect results and logs
# 7. Clean up resources
# 8. Exit with pass/fail status
```

### Option C: Python Test Suite

```python
# Conceptual structure (not actual code)

# tests/stateless/test_deployment.py

class TestStatelessDeployment:
    """Test suite for stateless deployment validation."""

    def setup_method(self):
        # Start container with production constraints
        pass

    def test_readonly_filesystem(self):
        # Verify read-only filesystem works
        pass

    def test_jwt_only_authentication(self):
        # Verify JWT-only mode
        pass

    def test_concurrent_isolation(self):
        # Verify request isolation
        pass

    def teardown_method(self):
        # Clean up container
        pass
```

### Option D: Docker Compose Test Profile

```yaml
# Conceptual structure (not actual code)

# docker-compose.test.yml

services:
  quilt-mcp-stateless-test:
    image: quilt-mcp-server:test
    read_only: true
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    tmpfs:
      - /tmp:size=100M,mode=1777
      - /app/.cache:size=50M,mode=700
    environment:
      - MCP_REQUIRE_JWT=true
      - QUILT_DISABLE_CACHE=true
    # ... etc
```

## Integration with CI/CD

### GitHub Actions Integration

The test should be callable from CI:

```yaml
# Conceptual CI configuration (not actual code)

name: Test Stateless Deployment

on: [push, pull_request]

jobs:
  test-stateless:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build test image
        # ...
      - name: Run stateless deployment test
        run: make test-stateless
      - name: Upload test results
        if: always()
        # ...
```

### Required CI Conditions

CI pipeline must:

1. **Run on every commit** to main/develop branches
2. **Block merges** if test fails
3. **Generate artifacts** (logs, reports)
4. **Alert on failures** (Slack, email, etc.)
5. **Cache Docker layers** for speed

### Test Environment Requirements

CI environment needs:

- Docker daemon available
- Sufficient resources (2GB RAM minimum)
- Network access to test catalog (or mock server)
- Test JWT tokens available as secrets
- Test AWS credentials (or mock)

## Success Criteria for Test Target

The `test-stateless` target is complete when:

1. ✅ **Automated**: Runs with single command (`make test-stateless`)
2. ✅ **Comprehensive**: Tests all 7 scenarios defined above
3. ✅ **Fast**: Completes in under 5 minutes
4. ✅ **Reliable**: No false positives or flaky tests
5. ✅ **Clear**: Obvious pass/fail with actionable errors
6. ✅ **Integrated**: Runs in CI/CD pipeline
7. ✅ **Documented**: README explains how to run and interpret results

## Edge Cases to Test

### Filesystem Behavior

- **What if** quilt3 tries to write telemetry? (Should fail gracefully)
- **What if** boto3 tries to cache credentials? (Should use tmpfs)
- **What if** package operation needs temporary space? (Should use /tmp)

### Authentication Edge Cases

- **What if** JWT expires during operation? (Should error clearly)
- **What if** JWT has wrong claims? (Should reject at authorization)
- **What if** no JWT and no ~/.quilt/? (Should error with helpful message)

### Resource Exhaustion

- **What if** memory limit reached? (Should fail gracefully, not OOM)
- **What if** tmpfs fills up? (Should error clearly: "No space left")
- **What if** too many concurrent requests? (Should queue or reject)

### Network Issues

- **What if** catalog unreachable? (Should timeout with clear error)
- **What if** S3 unreachable? (Should propagate boto3 error)
- **What if** slow network? (Should respect timeouts)

## Monitoring and Observability

### Metrics to Collect

During test, collect:

- **Startup time**: Time from container start to healthy
- **Tool execution time**: Per-tool latency
- **Memory usage**: Peak and average
- **CPU usage**: Peak and average
- **Filesystem I/O**: Reads/writes to tmpfs
- **Network I/O**: Bytes sent/received

### Logs to Capture

Capture these logs:

- **Container stdout/stderr**: All console output
- **MCP protocol messages**: Request/response pairs
- **Error logs**: All ERROR and WARNING level logs
- **Audit log**: All filesystem write attempts

### Debugging Failed Tests

When test fails, provide:

1. **Container logs** (last 1000 lines)
2. **Filesystem diff** (`docker diff`)
3. **Process list** (`docker top`)
4. **Resource usage** (`docker stats`)
5. **Network connections** (`netstat` output)
6. **Environment variables** (sanitized)

## Documentation Requirements

### README Section

Add to README.md:

```markdown
## Testing Stateless Deployment

To verify the container works in production multitenant mode:

```bash
make test-stateless
```

This runs the container with:
- Read-only filesystem
- JWT-only authentication
- Minimal privileges
- Resource limits

See `spec/a10-multitenant/02-test-stateless.md` for details.
```

### Developer Guide

Create `docs/STATELESS_TESTING.md`:

- How to run the test locally
- How to interpret results
- How to debug failures
- How to add new test scenarios
- How to mock external dependencies

### Operations Guide

Create `docs/PRODUCTION_DEPLOYMENT.md`:

- How stateless mode differs from development
- What constraints are enforced
- How to configure JWT authentication
- How to monitor stateless deployment
- Troubleshooting guide

## Open Questions

1. **Test data**: Do we need a dedicated test catalog, or mock S3/catalog API?
2. **JWT generation**: How to generate valid test JWTs? (Real auth server vs mock)
3. **Concurrency**: How many concurrent requests to test? (10? 100?)
4. **Duration**: Should we test long-running operations? (30 min package push)
5. **Cleanup**: How to handle test failures that leave containers running?

## Future Enhancements

### Phase 2
- **Load testing**: Test with realistic traffic patterns
- **Chaos testing**: Kill container during operations
- **Security scanning**: Integrate with Trivy, Grype
- **Performance regression**: Track metrics over time

### Phase 3
- **Multi-container**: Test with multiple replicas (load balancer)
- **Multi-region**: Test with different regions/catalogs
- **Backup/restore**: Test disaster recovery scenarios
- **Monitoring integration**: Send metrics to Prometheus/Grafana

## Related Specifications

- `01-stateless.md` - Overall stateless architecture
- (Future) `03-jwt-authentication.md` - JWT token generation and validation
- (Future) `04-ci-cd-integration.md` - Complete CI/CD pipeline

## References

- Docker security best practices: https://docs.docker.com/engine/security/
- MCP protocol testing: https://modelcontextprotocol.io/testing
- Container security scanning: https://github.com/aquasecurity/trivy
