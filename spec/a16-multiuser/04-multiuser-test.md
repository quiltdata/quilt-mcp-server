# Multiuser Testing Asymmetry

## Executive Summary

The test suite exhibits a significant asymmetry: **quilt3 backend is extensively tested with live AWS integration, while platform backend testing is confined to unit tests with mocked GraphQL responses.**

## What `make test-all` Actually Tests

The test runner orchestrates 5 phases:

1. **Lint** - Format + type checking
2. **Coverage** - Unit, integration, E2E tests
3. **Docker** - Build validation
4. **Script Tests** - MCP integration + stateless tests
5. **MCPB** - Package validation

Key finding: **Integration tests predominantly exercise quilt3 backend against real AWS resources.**

## Testing Coverage by Backend

### Quilt3 Backend (Live-tested)

**Unit Tests:**

- 1,343 LOC
- 60 test functions
- Minimal mocking (basic initialization only)

**Integration Tests:**

- 20 test files (~271 test functions total)
- Uses `quilt3_backend` session fixture ([tests/conftest.py:274](tests/conftest.py#L274))
- Real AWS operations: S3, Athena, Elasticsearch
- Live catalog authentication
- Examples:
  - [test_integration.py](tests/integration/test_integration.py) - Full package CRUD with real S3
  - [test_packages_integration.py](tests/integration/test_packages_integration.py) - Package versioning
  - [test_athena.py](tests/integration/test_athena.py) - Live Athena queries
  - [test_elasticsearch_index_discovery.py](tests/integration/test_elasticsearch_index_discovery.py) - Real ES queries

**Total: ~3,600 LOC of tests, majority against live services**

### Platform Backend (Mock-only)

**Unit Tests:**

- 2,582 LOC
- 93 test functions
- All GraphQL responses mocked
- No live catalog communication

**Integration Tests:**

- **ZERO live tests**
- [test_multiuser_access.py](tests/integration/test_multiuser_access.py) - Uses stub classes, not real platform backend
- [test_multiuser.py](tests/integration/test_multiuser.py) - Stub-based concurrency tests

**Total: 2,582 LOC of tests, all mocked**

## The Asymmetry

| Aspect | Quilt3 Backend | Platform Backend |
|--------|----------------|------------------|
| Live integration tests | ✅ 20 files | ❌ None |
| Mock-based unit tests | Minimal | Extensive |
| AWS operations tested | All (S3, Athena, ES) | None |
| GraphQL tested | N/A | Mock responses only |
| JWT auth tested | Via catalog | Stub objects only |
| Catalog API tested | Live | Never |

**The pattern:** Quilt3 tests lean on real AWS, Platform tests lean on mocks.

## Root Cause

The `quilt3_backend` fixture in [tests/conftest.py:274-299](tests/conftest.py#L274-L299) provides session-scoped live backend:

```python
@pytest.fixture(scope="session")
def quilt3_backend():
    """Provide initialized Quilt3_Backend for integration tests."""
    backend = Quilt3_Backend()
    # Verify auth status is available
    auth_status = backend.get_auth_status()
    if not auth_status.is_authenticated:
        pytest.skip("Quilt3 not authenticated")
    return backend
```

**Platform backend has no equivalent fixture.** All platform tests in [tests/unit/backends/test_platform_backend_*.py](tests/unit/backends/) manually construct backends with mocked HTTP responses.

## Opportunities to Improve Platform Backend Testing

### 1. Add Live Integration Tests

**Priority: High**

Create `platform_backend` fixture analogous to `quilt3_backend`:

```python
@pytest.fixture(scope="session")
def platform_backend():
    """Provide initialized Platform_Backend for integration tests."""
    # Requires:
    # - QUILT_CATALOG_URL
    # - QUILT_REGISTRY_URL
    # - Valid JWT token with test user
    backend = Platform_Backend()
    return backend
```

**Tests to add:**

- `test_platform_packages_integration.py` - Package CRUD via GraphQL
- `test_platform_buckets_integration.py` - Bucket list/config via API
- `test_platform_auth_integration.py` - JWT token validation
- `test_platform_permissions_integration.py` - Role-based access

### 2. Test Multiuser Access Patterns

**Priority: High**

[test_multiuser_access.py](tests/integration/test_multiuser_access.py) currently uses stubs:

```python
class _StubAuth:
    def get_boto3_session(self):
        raise AssertionError("boto3 session should not be requested")
```

**Upgrade to real platform backend:**

- Test concurrent users with real JWT tokens
- Verify GraphQL query isolation
- Test permission inheritance from catalog roles

### 3. Test GraphQL Query Correctness

**Priority: Medium**

Current platform unit tests mock GraphQL responses. Need tests that:

- Execute real queries against catalog
- Verify response schema matches expectations
- Test error handling for malformed queries
- Validate pagination, filtering, sorting

### 4. Test Stateless Mode End-to-End

**Priority: Medium**

Existing stateless tests ([test_stateless/](tests/stateless/)) focus on Docker deployment. Need:

- Full workflow tests: JWT → GraphQL → S3 operations
- Permission verification across user roles
- Package operations in multiuser context

### 5. Add Platform-Specific E2E Tests

**Priority: Low**

Current E2E tests assume quilt3 backend. Add:

- `test_platform_e2e_workflows.py` - Complete user workflows
- Package creation → browse → delete lifecycle
- Search across multiple users' packages

## Implementation Path

### Phase 1: Foundation (Week 1)

1. Create `platform_backend` fixture in conftest.py
2. Add environment variable validation (catalog URL, JWT)
3. Write 5 basic integration tests (auth, buckets, packages, content, admin)

### Phase 2: Multiuser (Week 2)

4. Upgrade [test_multiuser_access.py](tests/integration/test_multiuser_access.py) to use real backend
2. Add concurrent user tests with real JWT tokens
3. Test permission isolation

### Phase 3: Coverage (Week 3)

7. Achieve parity: 20+ platform integration tests matching quilt3 coverage
2. Add GraphQL schema validation tests
3. Document platform testing requirements in [CLAUDE.md](../../CLAUDE.md)

## Risk Mitigation

**Challenge:** Platform backend requires live catalog with JWT authentication

**Solutions:**

- Use test catalog instance (not production)
- Generate test JWTs with short expiration
- Add `@pytest.mark.platform_integration` to skip when credentials unavailable
- Document setup in `docs/TESTING_PLATFORM_BACKEND.md`

## Metrics

**Success criteria:**

- Platform backend has ≥20 integration test files
- Integration tests cover all GraphQL mutations/queries
- CI runs platform tests when `PLATFORM_TEST_ENABLED=true`
- Coverage report shows >80% for platform backend with integration tests

**Current state:**

- Quilt3: ~60% unit + 40% integration coverage
- Platform: 100% unit (mocked) + 0% integration

**Target state:**

- Platform: ~40% unit (mocked) + 60% integration (live)

## Related Files

- Test configuration: [tests/conftest.py](../../tests/conftest.py)
- Platform unit tests: [tests/unit/backends/test_platform_backend_*.py](../../tests/unit/backends/)
- Integration tests: [tests/integration/](../../tests/integration/)
- Multiuser stubs: [tests/integration/test_multiuser_access.py](../../tests/integration/test_multiuser_access.py)
- Test orchestrator: [scripts/test-runner.py](../../scripts/test-runner.py)
