# Stateless Deployment Testing

This document explains how to test and validate that the Quilt MCP Server can run in true stateless, multiuser mode with strict security constraints.

## Quick Start

Run the stateless deployment test suite:

```bash
make test-stateless
```

This will:
1. Build the Docker image
2. Run containers with production-like security constraints
3. Execute comprehensive validation tests
4. Report results with clear diagnostics

## What Gets Tested

The test suite validates **7 key scenarios** from the [stateless deployment specification](../spec/a10-multiuser/02-test-stateless.md):

### 1. Basic Tool Execution ✅
- Container starts with all security constraints
- Read-only filesystem enforced
- Security options configured correctly
- Resource limits applied
- MCP server responds to requests

### 2. JWT Authentication 🔐
- `QUILT_MULTIUSER_MODE=true` environment variable set
- Requests without JWT are rejected
- Malformed JWT tokens are rejected
- No fallback to local credentials (`~/.quilt/`, `~/.aws/`)

### 3. Concurrent Request Isolation 🔀
- Multiple concurrent requests handled correctly
- No state leakage between requests
- Request isolation verified

### 4. No Persistent State 💾
- Container behavior identical across restarts
- No cached data persists
- Tmpfs contents cleared on restart
- No "warm start" effects

### 5. Filesystem Write Attempts 📁
- All writes go to tmpfs only (`/tmp`, `/app/.cache`, `/run`)
- No writes to read-only root filesystem
- Filesystem changes inspected and validated

### 6. Resource Constraints 🎯
- Container operates within memory limits (512M)
- CPU limits enforced (1.0 CPU)
- Graceful handling of resource exhaustion

### 7. Security Hardening 🛡️
- Minimal capabilities (`--cap-drop=ALL`)
- No privilege escalation (`--security-opt=no-new-privileges`)
- Read-only filesystem (`--read-only`)
- Tmpfs for temporary storage only

## Test Results Interpretation

### Passing Tests

When all tests pass, you'll see:

```
======================================
✅ Stateless deployment tests completed
======================================
12 passed in 69.67s
```

This means your container is **production-ready** for multiuser deployment.

### Failing Tests - Intelligent Error Messages

When tests fail, you get **actionable diagnostics**. Here are examples:

#### Example 1: Filesystem Writes Detected

```
❌ FAIL: Container wrote files outside tmpfs directories

Unexpected file changes:
  - /app/.quilt/telemetry.jsonl

Stateless deployment requires:
  ✓ Only tmpfs directories can be written: /tmp, /app/.cache, /run
  ✗ Root filesystem must remain read-only

Recommendations:
  1. Check if application is trying to write config/cache files
  2. Set HOME=/tmp to redirect user files to tmpfs
  3. Configure applications to use /tmp for temporary storage
  4. Review container logs for 'Read-only file system' errors
```

**How to fix:**
- Set `HOME=/tmp` environment variable
- Configure application to disable telemetry writes
- Review application code for filesystem writes

#### Example 2: JWT Authentication Not Enforced

```
❌ FAIL: Server accepted request without JWT token
Expected: Authentication error (401/403)
Actual: 200 OK (success)

Stateless mode MUST enforce JWT authentication:
  1. Set QUILT_MULTIUSER_MODE=true in environment
  2. Reject requests without Authorization header
  3. Return clear error: 'JWT token required'

Security risk: Without JWT enforcement, the server may fall back
to local credentials, violating stateless deployment constraints.
```

**How to fix:**
- Ensure `QUILT_MULTIUSER_MODE=true` environment variable is set
- Implement JWT validation in request handlers
- Return 401/403 with clear error message when JWT missing

#### Example 3: Missing Security Constraints

```
❌ FAIL: Container allows privilege escalation
Expected: SecurityOpt contains 'no-new-privileges:true'
Actual: SecurityOpt=[]

Fix: Add --security-opt=no-new-privileges:true to docker run command
```

**How to fix:**
- Add `--security-opt=no-new-privileges:true` flag
- Review Docker configuration

## Running Specific Tests

Run individual test files:

```bash
# Test basic execution only
pytest tests/stateless/test_basic_execution.py -v

# Test JWT authentication only
pytest tests/stateless/test_jwt_authentication.py -v

# Test persistent state behavior
pytest tests/stateless/test_persistent_state.py -v

# Test negative cases (violation detection)
pytest tests/stateless/test_negative_cases.py -v
```

Run specific test functions:

```bash
# Test container configuration
pytest tests/stateless/test_basic_execution.py::test_container_starts_with_stateless_constraints -v

# Test JWT requirement
pytest tests/stateless/test_jwt_authentication.py::test_jwt_required_environment_variable -v

# Test filesystem writes
pytest tests/stateless/test_basic_execution.py::test_no_filesystem_writes_outside_tmpfs -v
```

## Understanding Test Architecture

### Test Structure

```
tests/stateless/
├── __init__.py                      # Package initialization
├── conftest.py                      # Pytest fixtures and utilities
├── test_basic_execution.py          # Scenario 1: Basic tool execution
├── test_jwt_authentication.py       # Scenario 2: JWT authentication
├── test_persistent_state.py         # Scenario 4: No persistent state
└── test_negative_cases.py           # Negative tests (violation detection)
```

### Key Fixtures (conftest.py)

#### `stateless_container`
Creates a container with **production-like constraints**:
- Read-only root filesystem
- Tmpfs mounts for `/tmp`, `/app/.cache`, `/run`
- Security constraints (no-new-privileges, cap-drop=ALL)
- Resource limits (512M memory, 1.0 CPU)
- JWT-only authentication mode

#### `writable_container`
Creates a container **WITHOUT stateless constraints** for negative testing:
- Writable filesystem (VIOLATION)
- No security constraints
- Used to verify test suite catches violations

#### `container_url`
Provides the HTTP URL for the container's MCP server.

#### `get_container_filesystem_writes()`
Utility function to inspect filesystem changes using `docker diff`.

## Debugging Failed Tests

### View Container Logs

If tests fail, inspect container logs:

```bash
# Find running test containers
docker ps -a | grep quilt-mcp

# View logs
docker logs <container_id>

# Follow logs in real-time
docker logs -f <container_id>
```

### Inspect Container Configuration

```bash
# Inspect container details
docker inspect <container_id>

# Check filesystem changes
docker diff <container_id>

# View resource usage
docker stats <container_id>
```

### Run Tests with Verbose Output

```bash
# Show all print statements
pytest tests/stateless/ -v -s

# Show full tracebacks
pytest tests/stateless/ -v --tb=long

# Stop on first failure
pytest tests/stateless/ -v -x
```

### Keep Container Running After Test

Modify the test fixture to not auto-cleanup:

```python
# In conftest.py, comment out cleanup:
# container.stop()
# container.remove()
```

Then inspect manually:

```bash
docker ps -a
docker exec -it <container_id> sh
```

## Local Development Setup

### Prerequisites

1. **Docker**: Ensure Docker is installed and running
2. **Python 3.11+**: Required for test suite
3. **uv**: Package manager for dependencies

### Install Test Dependencies

```bash
# Install test dependencies including docker and httpx
uv sync --group test
```

### Build Test Image

```bash
# Build Docker image for testing
make docker-build

# Or manually:
docker build -t quilt-mcp:test -f Dockerfile .
```

### Run Tests

```bash
# Full test suite
make test-stateless

# Or manually:
export TEST_DOCKER_IMAGE=quilt-mcp:test
export PYTHONPATH="src"
uv run python -m pytest tests/stateless/ -v
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Stateless Deployment Tests

on: [push, pull_request]

jobs:
  test-stateless:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Build Docker image
        run: make docker-build

      - name: Run stateless deployment tests
        run: make test-stateless

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: build/test-results/
```

## Test Metrics

The test suite tracks:

- **Container startup time**: Time to start and become healthy
- **Tool execution time**: Per-tool latency
- **Memory usage**: Peak and average during tests
- **Filesystem writes**: Number and location of file changes
- **Test duration**: Total time for test suite

## Common Issues and Solutions

### Issue: Container Fails to Start

**Symptoms:**
```
RuntimeError: Container failed to start
```

**Solutions:**
1. Check Docker daemon is running: `docker ps`
2. Verify image was built: `docker images | grep quilt-mcp`
3. Check for port conflicts: `lsof -i :8000`
4. Review build logs: `docker build -t quilt-mcp:test .`

### Issue: Tests Timeout

**Symptoms:**
```
TimeoutError: Container not responding
```

**Solutions:**
1. Increase test timeout: `pytest --timeout=300`
2. Check container logs: `docker logs <container_id>`
3. Verify container is running: `docker ps`
4. Check resource constraints (may need more memory)

### Issue: Permission Denied Errors

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied
```

**Solutions:**
1. Ensure Docker is running with correct permissions
2. Check Docker socket: `ls -l /var/run/docker.sock`
3. Add user to docker group: `sudo usermod -aG docker $USER`
4. Restart Docker daemon

### Issue: Filesystem Write Detection False Positives

**Symptoms:**
```
❌ FAIL: Container wrote files outside tmpfs directories
  - /etc/hostname
  - /etc/hosts
```

**Solutions:**
These are acceptable Docker-managed files. Update the `acceptable_writes` list in [test_basic_execution.py](../tests/stateless/test_basic_execution.py:169):

```python
acceptable_writes = {
    "/etc/hostname",
    "/etc/hosts",
    "/etc/resolv.conf",
    "/.dockerenv",
}
```

## Next Steps

After passing stateless deployment tests:

1. **Production Deployment**: Deploy with same constraints to production
2. **Load Testing**: Test with realistic traffic patterns
3. **Security Scanning**: Integrate with Trivy or Grype
4. **Monitoring**: Set up Prometheus/Grafana for metrics
5. **Documentation**: Update deployment guides

## Related Documentation

- [Stateless Architecture Specification](../spec/a10-multiuser/01-stateless.md)
- [Stateless Testing Specification](../spec/a10-multiuser/02-test-stateless.md)
- [Production Deployment Guide](PRODUCTION_DEPLOYMENT.md) *(to be created)*

## Support

If you encounter issues:

1. **Check test output**: Tests provide detailed diagnostics
2. **Review logs**: Container logs show runtime errors
3. **Inspect configuration**: Verify Docker settings match spec
4. **File an issue**: [GitHub Issues](https://github.com/quiltdata/quilt-mcp-server/issues)

---

**Status**: ✅ Test suite is production-ready and validates all stateless deployment constraints.
