# Multitenant Testing Specification

## Overview

This document specifies testing strategies for the Platform GraphQL backend with JWT authentication and multitenant support. The current `make test-all` primarily tests single-tenant mode. This spec provides both manual and automated testing approaches for multitenant scenarios.

## Current State

### Implemented Components

- **Platform Backend** ([platform_backend.py](../../src/quilt_mcp/backends/platform_backend.py))
  - JWT-based authentication
  - GraphQL API integration
  - Read operations via GraphQL
  - Write operations via quilt3 Package engine

- **Tenant Extraction** ([tenant_extraction.py](../../src/quilt_mcp/context/tenant_extraction.py))
  - Extracts tenant ID from JWT claims
  - Supports multiple claim keys: `tenant_id`, `tenant`, `org_id`, `organization_id`
  - Environment variable fallback

- **Existing Tests**
  - Unit tests: `tests/unit/backends/test_platform_backend_core.py`
  - Integration: `tests/integration/test_multitenant.py`
  - Security: `tests/security/test_multitenant_security.py`
  - Load: `tests/load/test_multitenant_load.py`

### Current Gaps

1. **No automated multitenant E2E tests** - Existing tests use mocks or single tenant
2. **No JWT generation in test suite** - Manual token creation required
3. **No multi-tenant orchestration** - Can't test tenant A + tenant B simultaneously
4. **Limited coverage** - Platform backend read operations not fully tested

## Manual Testing Guide

### Quick Start: Single Tenant Testing

**Prerequisites:**

```bash
# 1. Ensure quilt3 is configured with valid catalog session
quilt3 catalog

# 2. Set environment variables
export QUILT_CATALOG_URL="https://your-catalog.quiltdata.com"
export QUILT_TEST_BUCKET="your-test-bucket"
export QUILT_TENANT_ID="test-tenant-1"  # Optional, can come from JWT
```

**Generate JWT Token:**

```bash
# Auto-generate JWT with catalog authentication
python tests/jwt_helpers.py generate \
  --role-arn "arn:aws:iam::123456789012:role/QuiltMCPRole" \
  --secret "test-secret-key" \
  --auto-extract \
  --tenant-id "test-tenant-1"

# Copy the generated token
export MCP_JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Test Platform Backend:**

```bash
# Start local server with Platform backend (requires JWT)
FASTMCP_MODE=platform make run

# In another terminal, run tests
python scripts/mcp-test.py http://localhost:8001/mcp \
  --jwt \
  --role-arn "arn:aws:iam::123456789012:role/QuiltMCPRole" \
  --secret "test-secret-key" \
  --tools-test \
  --resources-test
```

### Multi-Tenant Testing

**Scenario: Test Two Tenants Simultaneously**

```bash
# Terminal 1: Start server
FASTMCP_MODE=platform make run

# Terminal 2: Test Tenant A
python scripts/mcp-test.py http://localhost:8001/mcp \
  --jwt \
  --role-arn "arn:aws:iam::123456789012:role/TenantA" \
  --secret "test-secret" \
  --tools-test \
  --tenant-id "tenant-a"

# Terminal 3: Test Tenant B
python scripts/mcp-test.py http://localhost:8001/mcp \
  --jwt \
  --role-arn "arn:aws:iam::123456789012:role/TenantB" \
  --secret "test-secret" \
  --tools-test \
  --tenant-id "tenant-b"
```

**Verify Tenant Isolation:**

```bash
# Create workflow for Tenant A
curl -X POST http://localhost:8001/mcp \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "workflow_create",
      "arguments": {"workflow_id": "test-wf", "description": "Tenant A"}
    },
    "id": 1
  }'

# Try to access from Tenant B (should fail)
curl -X POST http://localhost:8001/mcp \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "workflow_status",
      "arguments": {"workflow_id": "test-wf"}
    },
    "id": 2
  }'
# Expected: Error - workflow not found
```

### Testing JWT Claim Variations

**Test Different Tenant Claim Keys:**

```python
# tests/manual/test_tenant_claims.py
import jwt
import requests

def test_claim_variations():
    """Test that tenant extraction works with different claim keys."""

    secret = "test-secret"
    endpoint = "http://localhost:8001/mcp"

    # Test each supported claim key
    claim_keys = ["tenant_id", "tenant", "org_id", "organization_id"]

    for claim_key in claim_keys:
        token = jwt.encode({
            "role arn": "arn:aws:iam::123:role/Test",
            "catalog_token": "...",
            claim_key: f"test-tenant-{claim_key}",
            "exp": int(time.time()) + 3600
        }, secret, algorithm="HS256")

        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            }
        )

        assert response.status_code == 200
        print(f"✅ {claim_key}: SUCCESS")
```

## Automated Testing

### Unit Tests (Fast, Mocked)

**Location:** `tests/unit/backends/test_platform_backend_multitenant.py`

```python
"""Unit tests for Platform backend multitenant behavior."""

import pytest
from unittest.mock import Mock, patch
from quilt_mcp.backends.platform_backend import Platform_Backend
from quilt_mcp.runtime_context import RuntimeAuthState

class TestPlatformBackendMultitenant:
    """Test tenant-specific behavior in Platform backend."""

    def test_tenant_extraction_from_jwt_claims(self, monkeypatch):
        """Test that tenant ID is extracted from JWT claims."""

        # Mock runtime context with tenant claim
        mock_auth = RuntimeAuthState(
            access_token="mock-token",
            claims={"tenant_id": "acme-corp", "catalog_token": "test-token"}
        )

        monkeypatch.setattr("quilt_mcp.backends.platform_backend.get_runtime_auth",
                           lambda: mock_auth)
        monkeypatch.setattr("quilt_mcp.backends.platform_backend.get_runtime_claims",
                           lambda: mock_auth.claims)
        monkeypatch.setattr("quilt_mcp.backends.platform_backend.get_runtime_metadata",
                           lambda: {})

        # Mock requests to avoid actual HTTP calls
        with patch('quilt_mcp.backends.platform_backend.requests'):
            backend = Platform_Backend()

            # Verify backend initialized
            assert backend is not None

    def test_graphql_endpoint_uses_tenant_specific_auth(self, monkeypatch):
        """Test that GraphQL queries use tenant-specific catalog token."""

        tenant_token = "tenant-specific-token-abc123"

        mock_auth = RuntimeAuthState(
            access_token="jwt-token",
            claims={
                "tenant_id": "acme-corp",
                "catalog_token": tenant_token,
                "catalog_url": "https://acme.quiltdata.com"
            }
        )

        monkeypatch.setattr("quilt_mcp.backends.platform_backend.get_runtime_auth",
                           lambda: mock_auth)
        monkeypatch.setattr("quilt_mcp.backends.platform_backend.get_runtime_claims",
                           lambda: mock_auth.claims)
        monkeypatch.setattr("quilt_mcp.backends.platform_backend.get_runtime_metadata",
                           lambda: {})

        with patch('quilt_mcp.backends.platform_backend.requests') as mock_requests:
            mock_session = Mock()
            mock_requests.Session.return_value = mock_session

            backend = Platform_Backend()

            # Verify session uses tenant's catalog token
            mock_session.headers.update.assert_called_with({
                "Authorization": f"Bearer {tenant_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            })
```

**Run Unit Tests:**

```bash
make test-unit
# or
uv run pytest tests/unit/backends/test_platform_backend_multitenant.py -v
```

### Integration Tests (Real Services)

**Location:** `tests/integration/test_platform_multitenant_e2e.py`

```python
"""Integration tests for Platform backend with real JWT authentication."""

import pytest
import os
from tests.jwt_helpers import generate_test_jwt, validate_quilt3_session_exists

@pytest.mark.integration
@pytest.mark.requires_jwt
class TestPlatformMultitenantE2E:
    """End-to-end tests with real Platform backend and JWT."""

    @pytest.fixture
    def jwt_token_tenant_a(self):
        """Generate JWT for tenant A."""
        if not validate_quilt3_session_exists():
            pytest.skip("quilt3 session not configured")

        return generate_test_jwt(
            role arn=os.environ["TEST_JWT_TOKEN_A"],
            secret=os.environ["TEST_JWT_SECRET"],
            tenant_id="tenant-a",
            auto_extract=True
        )

    @pytest.fixture
    def jwt_token_tenant_b(self):
        """Generate JWT for tenant B."""
        if not validate_quilt3_session_exists():
            pytest.skip("quilt3 session not configured")

        return generate_test_jwt(
            role arn=os.environ["TEST_JWT_TOKEN_B"],
            secret=os.environ["TEST_JWT_SECRET"],
            tenant_id="tenant-b",
            auto_extract=True
        )

    def test_tenants_cannot_access_each_others_workflows(
        self,
        jwt_token_tenant_a,
        jwt_token_tenant_b
    ):
        """Test that tenant isolation works end-to-end."""

        from quilt_mcp.context.factory import RequestContextFactory
        from quilt_mcp.runtime_context import set_runtime_auth, RuntimeAuthState

        factory = RequestContextFactory(mode="multitenant")

        # Tenant A creates workflow
        auth_a = RuntimeAuthState(access_token=jwt_token_tenant_a)
        with set_runtime_auth(auth_a):
            context_a = factory.create_context()
            context_a.workflow_service.create_workflow("secret-wf", "Tenant A Data")

        # Tenant B cannot access it
        auth_b = RuntimeAuthState(access_token=jwt_token_tenant_b)
        with set_runtime_auth(auth_b):
            context_b = factory.create_context()
            status = context_b.workflow_service.get_status("secret-wf")
            assert status.error == "Workflow 'secret-wf' not found"

    def test_platform_backend_list_packages_with_jwt(self, jwt_token_tenant_a):
        """Test Platform backend GraphQL query with real JWT."""

        from quilt_mcp.backends.platform_backend import Platform_Backend
        from quilt_mcp.runtime_context import set_runtime_auth, RuntimeAuthState

        auth = RuntimeAuthState(access_token=jwt_token_tenant_a)
        with set_runtime_auth(auth):
            backend = Platform_Backend()

            # Real GraphQL query to list packages
            registry = os.environ.get("QUILT_TEST_BUCKET", "s3://quilt-example")
            packages = backend.search_packages("", registry)

            # Should return results or empty list (not error)
            assert isinstance(packages, list)
```

**Run Integration Tests:**

```bash
# Set required environment variables
export TEST_JWT_TOKEN_A="arn:aws:iam::123:role/TenantA"
export TEST_JWT_TOKEN_B="arn:aws:iam::123:role/TenantB"
export TEST_JWT_SECRET="your-test-secret"
export QUILT_CATALOG_URL="https://your-catalog.quiltdata.com"

# Run tests
make test-integration
# or
uv run pytest tests/integration/test_platform_multitenant_e2e.py -v -m requires_jwt
```

### MCP Protocol Tests (Full Stack)

**Extend mcp-test.py for Multitenant:**

**Location:** `scripts/tests/mcp-test-multitenant.yaml`

```yaml
# Multitenant test configuration for mcp-test.py

environment:
  QUILT_TEST_BUCKET: "your-test-bucket"
  QUILT_CATALOG_URL: "https://your-catalog.quiltdata.com"

tenants:
  tenant-a:
    role arn: "arn:aws:iam::123456789012:role/TenantA"
    jwt_secret: "test-secret"
    expected_tools: 45
    expected_resources: 12

  tenant-b:
    role arn: "arn:aws:iam::123456789012:role/TenantB"
    jwt_secret: "test-secret"
    expected_tools: 45
    expected_resources: 12

test_scenarios:
  - name: "Basic connectivity"
    tenants: ["tenant-a", "tenant-b"]
    tests:
      - method: "initialize"
        expect: "success"
      - method: "tools/list"
        expect: "tools_count >= 40"

  - name: "Workflow isolation"
    description: "Tenant A creates workflow, Tenant B cannot access"
    steps:
      - tenant: "tenant-a"
        tool: "workflow_create"
        arguments:
          workflow_id: "isolated-wf"
          description: "Tenant A Only"

      - tenant: "tenant-b"
        tool: "workflow_status"
        arguments:
          workflow_id: "isolated-wf"
        expect: "error"
        error_contains: "not found"

  - name: "Package search by tenant"
    description: "Each tenant sees their own packages"
    steps:
      - tenant: "tenant-a"
        tool: "package_search"
        arguments:
          query: ""
          registry: "s3://tenant-a-bucket"
        expect: "success"

      - tenant: "tenant-b"
        tool: "package_search"
        arguments:
          query: ""
          registry: "s3://tenant-b-bucket"
        expect: "success"
```

**Run Multitenant MCP Tests:**

```bash
# Use dedicated test script
python scripts/test-multitenant.py \
  --config scripts/tests/mcp-test-multitenant.yaml \
  --endpoint http://localhost:8001/mcp \
  --verbose
```

## CI/CD Integration

### GitHub Actions Workflow

**Location:** `.github/workflows/test-multitenant.yml`

```yaml
name: Multitenant Tests

on:
  push:
    branches: [main, a*-platform*, a*-multitenant*]
  pull_request:
    branches: [main]

jobs:
  test-multitenant:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install dependencies
        run: |
          uv sync --group test

      - name: Configure test environment
        env:
          QUILT_CATALOG_URL: ${{ secrets.TEST_CATALOG_URL }}
          TEST_JWT_SECRET: ${{ secrets.TEST_JWT_SECRET }}
        run: |
          # Configure quilt3 session from secrets
          echo "${{ secrets.QUILT_SESSION_JSON }}" > ~/.quilt/auth.json

      - name: Run unit tests
        run: |
          make test-unit

      - name: Run multitenant integration tests
        env:
          TEST_JWT_TOKEN_A: ${{ secrets.TEST_JWT_TOKEN_A }}
          TEST_JWT_TOKEN_B: ${{ secrets.TEST_JWT_TOKEN_B }}
          TEST_JWT_SECRET: ${{ secrets.TEST_JWT_SECRET }}
        run: |
          uv run pytest tests/integration/test_platform_multitenant_e2e.py \
            -v -m requires_jwt \
            --cov=quilt_mcp \
            --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Make Targets

**Add to make.dev:**

```makefile
# Multitenant testing targets

.PHONY: test-multitenant test-multitenant-unit test-multitenant-integration test-multitenant-mcp

test-multitenant: test-multitenant-unit test-multitenant-integration test-multitenant-mcp
 @echo "✅ All multitenant tests passed"

test-multitenant-unit:
 @echo "Running multitenant unit tests..."
 @uv run pytest tests/unit/backends/test_platform_backend_multitenant.py \
  tests/unit/context/test_tenant_extraction.py \
  -v --cov=quilt_mcp

test-multitenant-integration:
 @echo "Running multitenant integration tests..."
 @if [ -z "$$TEST_JWT_TOKEN_A" ]; then \
  echo "⚠️  Skipping: TEST_JWT_TOKEN_A not set"; \
  exit 0; \
 fi
 @uv run pytest tests/integration/test_platform_multitenant_e2e.py \
  -v -m requires_jwt --cov=quilt_mcp

test-multitenant-mcp:
 @echo "Running multitenant MCP protocol tests..."
 @if [ -z "$$TEST_JWT_SECRET" ]; then \
  echo "⚠️  Skipping: TEST_JWT_SECRET not set"; \
  exit 0; \
 fi
 @python scripts/test-multitenant.py \
  --config scripts/tests/mcp-test-multitenant.yaml \
  --endpoint http://localhost:8001/mcp

# Quick manual testing
test-platform-local:
 @echo "Starting Platform backend locally..."
 @FASTMCP_MODE=platform make run &
 @sleep 3
 @python scripts/mcp-test.py http://localhost:8001/mcp \
  --jwt \
  --role-arn "$${TEST_JWT_TOKEN:-arn:aws:iam::123:role/Test}" \
  --secret "$${TEST_JWT_SECRET:-test-secret}" \
  --tools-test
 @pkill -f "make run"
```

**Usage:**

```bash
# Run all multitenant tests
make test-multitenant

# Run only unit tests (fast)
make test-multitenant-unit

# Run integration tests (requires AWS)
export TEST_JWT_TOKEN_A="arn:aws:iam::123:role/TenantA"
export TEST_JWT_TOKEN_B="arn:aws:iam::123:role/TenantB"
export TEST_JWT_SECRET="test-secret"
make test-multitenant-integration

# Quick local test
export TEST_JWT_TOKEN="arn:aws:iam::123:role/Test"
export TEST_JWT_SECRET="test-secret"
make test-platform-local
```

## Test Coverage Goals

### Phase 1: Core Functionality (Week 1)

- [ ] Unit tests for tenant extraction (DONE - test_tenant_extraction.py exists)
- [ ] Unit tests for Platform backend initialization with JWT
- [ ] Unit tests for GraphQL query construction
- [ ] Mock-based tests for all read operations

**Target:** 80% code coverage on Platform_Backend

### Phase 2: Integration Testing (Week 2)

- [ ] Real JWT generation in test fixtures
- [ ] GraphQL API integration tests
- [ ] Multi-tenant context isolation tests
- [ ] Workflow service tenant separation tests

**Target:** All QuiltOps methods tested with real GraphQL

### Phase 3: E2E & Security (Week 3)

- [ ] Full MCP protocol tests with JWT auth
- [ ] Cross-tenant access denial tests
- [ ] JWT claim variation tests
- [ ] Performance tests with concurrent tenants

**Target:** All security invariants verified

### Phase 4: CI/CD Automation (Week 4)

- [ ] GitHub Actions workflow for multitenant tests
- [ ] Automated JWT generation from secrets
- [ ] Test matrix across Python versions
- [ ] Coverage reports and quality gates

**Target:** Automated testing in CI pipeline

## Performance Benchmarks

### Tenant Context Creation

**Goal:** < 50ms to create new tenant context

```python
# tests/performance/test_multitenant_perf.py
import pytest
import time

@pytest.mark.performance
def test_tenant_context_creation_speed():
    """Tenant context creation should be fast."""

    from quilt_mcp.context.factory import RequestContextFactory

    factory = RequestContextFactory(mode="multitenant")

    start = time.time()
    for i in range(100):
        context = factory.create_context(tenant_id=f"tenant-{i}")
    elapsed = time.time() - start

    avg_time_ms = (elapsed / 100) * 1000
    assert avg_time_ms < 50, f"Context creation too slow: {avg_time_ms:.2f}ms"
```

### Concurrent Tenant Operations

**Goal:** Support 50+ concurrent tenants

```python
@pytest.mark.performance
def test_concurrent_tenant_operations():
    """Server should handle many concurrent tenants."""

    from concurrent.futures import ThreadPoolExecutor
    import requests

    endpoint = "http://localhost:8001/mcp"
    tokens = [generate_tenant_token(f"tenant-{i}") for i in range(50)]

    def query_tenant(token):
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1}
        )
        return response.status_code == 200

    with ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(query_tenant, tokens))

    success_rate = sum(results) / len(results)
    assert success_rate > 0.95, f"Too many failures: {success_rate:.2%}"
```

## Troubleshooting Guide

### Common Issues

**1. "JWT claim 'catalog_token' is required"**

```bash
# Solution: Ensure JWT includes catalog authentication
python tests/jwt_helpers.py generate \
  --role-arn "arn:aws:iam::123:role/Test" \
  --secret "test-secret" \
  --auto-extract  # This extracts catalog token from quilt3 session
```

**2. "quilt3 session not configured"**

```bash
# Solution: Log in to quilt3
quilt3 login

# Or set environment variable
export QUILT_CATALOG_URL="https://your-catalog.quiltdata.com"
```

**3. "GraphQL query not authorized"**

```bash
# Solution: Check catalog token validity
python -c "
from tests.jwt_helpers import extract_catalog_token_from_session
print(extract_catalog_token_from_session()[:50])
"

# Re-login if token expired
quilt3 login
```

**4. "No tenant ID found"**

```bash
# Solution: Set tenant explicitly
export QUILT_TENANT_ID="my-tenant"

# Or include in JWT claims
python tests/jwt_helpers.py generate \
  --tenant-id "my-tenant" \
  ...
```

## Success Criteria

### Automated Tests

- ✅ All unit tests pass (make test-multitenant-unit)
- ✅ Integration tests pass with real JWT (make test-multitenant-integration)
- ✅ MCP protocol tests pass (make test-multitenant-mcp)
- ✅ Security tests verify tenant isolation
- ✅ Performance benchmarks meet targets

### Manual Verification

- ✅ Can start server in Platform mode
- ✅ Can generate JWT with catalog auth
- ✅ Can test multiple tenants simultaneously
- ✅ Tenants cannot access each other's data
- ✅ All QuiltOps methods work via GraphQL

### CI/CD

- ✅ GitHub Actions workflow runs on PR
- ✅ Tests run automatically on main branch
- ✅ Coverage reports generated
- ✅ Quality gates enforced

## Next Steps

1. **Implement missing unit tests** (test_platform_backend_multitenant.py)
2. **Create integration test fixtures** (JWT generation, test tenants)
3. **Extend mcp-test.py** with multitenant config support
4. **Add make targets** for easy manual testing
5. **Set up CI/CD** workflow for automated testing
6. **Document** in main CLAUDE.md for agent awareness

## References

- [Platform Backend Implementation](./00-implementation-summary.md)
- [GraphQL API Details](./03-graphql-apis.md)
- [JWT Testing Guide](../../docs/JWT_TESTING.md) (if exists)
- [Existing MCP Tests](../../scripts/mcp-test.py)
- [JWT Helpers](../../tests/jwt_helpers.py)
