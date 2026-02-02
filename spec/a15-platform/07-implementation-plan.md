# Platform GraphQL Backend Implementation Plan

**Status:** Ready for Implementation
**Branch:** `a16-graphql-backend`
**Created:** 2026-02-01
**Purpose:** Key tasks and decision points for Platform_Backend implementation

## Critical Decisions

### 1. GraphQL Endpoint Configuration

**Decision Required:** How to inject GraphQL endpoint URL

**Options:**

A. **Environment Variable (Recommended)**

- REQUIRE `QUILT_GRAPHQL_ENDPOINT`

**Reference:** See `/Users/ernest/GitHub/enterprise/registry/quilt_server/views/graphql.py` for actual endpoint paths

---

### 2. JWT Authentication Integration

**Current State:**

- JWT helpers exist at [tests/jwt_helpers.py](../../tests/jwt_helpers.py)
- Helpers can extract `catalog_token`, `catalog_url`, `registry_url` from quilt3 session
- JWTAuthService exists for role assumption

**Implementation Tasks:**

1. **TabulatorMixin Integration**
   - `get_graphql_endpoint()` - return endpoint from env or JWT claims
   - `get_graphql_auth_headers()` - return `{"Authorization": f"Bearer {catalog_token}"}`

2. **JWT Claim Extraction**
   - Read `catalog_token` from JWT claims in runtime context
   - Read `catalog_url` and `registry_url` for endpoint derivation
   - Handle missing claims gracefully (raise AuthenticationError)

3. **Session Initialization**
   - Create `requests.Session` in `__init__`
   - Set bearer token header once during initialization
   - Reuse session for all GraphQL requests

**Open Questions:**

- What happens if JWT expires mid-session?
- Do we need token refresh logic?
- Should we validate JWT claims on startup?

---

### 3. Enterprise Registry GraphQL Schema Reference

**Location:** `/Users/ernest/GitHub/enterprise/registry/quilt_server/graphql/`

**Critical Files to Review:**

- `schema.graphql` - Full GraphQL schema definition
- `views/graphql.py` - Django view handling GraphQL requests
- `resolvers/` - Query and mutation implementations

**Key Schema Elements Needed:**

- Package queries: `searchPackages`, `package`, `packages`
- Bucket queries: `bucketConfigs`, `bucketConfig`
- Content queries: `package.dir`, `package.file`
- Admin queries: `admin.user.*`, `roles`, `admin.ssoConfig`
- Tabulator queries: Already handled by TabulatorMixin

**Task:** Verify all QuiltOps methods map to existing schema queries

---

### 4. Integration Test Strategy

**Current State:**

- 732 unit tests passing
- Integration tests use Quilt3_Backend
- Tests are in `tests/integration/` and `tests/e2e/`

**Decision Required:** Refactor existing tests or create new ones?

**Option A: Refactor Existing Tests (Recommended)**

**Pros:**

- Ensures Platform_Backend has identical behavior to Quilt3_Backend
- Reuses existing test scenarios and assertions
- Validates QuiltOps abstraction works correctly

**Cons:**

- May expose subtle API differences
- Requires parametrization or backend fixtures

**Approach:**

- Parametrize integration tests with backend fixture
- Run same tests against both Quilt3_Backend and Platform_Backend
- Mark Platform-specific tests separately

**Example Pattern:**

```python
@pytest.fixture(params=["quilt3", "platform"])
def backend(request):
    if request.param == "quilt3":
        return Quilt3_Backend()
    else:
        return Platform_Backend()

@pytest.mark.integration
def test_search_packages(backend):
    results = backend.search_packages("test", "s3://bucket")
    assert len(results) > 0
```

**Option B: Duplicate Tests**

**Pros:**

- Platform tests can have different setup/teardown
- Can test Platform-specific features separately
- No risk of breaking Quilt3 tests

**Cons:**

- Code duplication (~500 lines)
- Tests may diverge over time
- More maintenance burden

**Recommendation:** Option A - Refactor with parametrization

**Tasks:**

1. Create backend factory fixture with JWT setup
2. Parametrize existing integration tests
3. Add Platform-specific tests for JWT scenarios
4. Mark tests requiring real catalog with `@pytest.mark.catalog`

---

## Implementation Phases

### Phase 1: Core Infrastructure (3-5 days)

**Milestone:** Execute GraphQL queries successfully

**Tasks:**

1. [ ] Implement `get_graphql_endpoint()` with env var + JWT fallback
2. [ ] Implement `get_graphql_auth_headers()` from JWT catalog_token
3. [ ] Implement `__init__` to extract JWT claims from runtime context
4. [ ] Implement `execute_graphql_query()` (inherited from TabulatorMixin, just need helpers)
5. [ ] Implement `get_auth_status()` with GraphQL "me" query
6. [ ] Implement `get_catalog_config()` with config query
7. [ ] Implement `configure_catalog()` to store catalog URL
8. [ ] Implement `get_registry_url()` to return stored URL

**Testing:**

- Unit tests for each method with mocked GraphQL responses
- Integration test with real catalog using JWT
- Test endpoint derivation logic (env var vs JWT)

**Success Criteria:**

- Can execute GraphQL queries with JWT auth
- Auth status returns correct information
- Endpoint selection logic works in all scenarios

---

### Phase 2: Read Operations (3-5 days)

**Milestone:** All read tools work with Platform backend

**Tasks:**

1. [ ] Implement `list_buckets()` - bucketConfigs query
2. [ ] Implement `search_packages()` - searchPackages query
3. [ ] Implement `get_package_info()` - package query
4. [ ] Implement `browse_content()` - package.dir query
5. [ ] Implement `list_all_packages()` - packages query
6. [ ] Implement `diff_packages()` - dual package query + comparison
7. [ ] Implement `get_content_url()` - get physicalKey + generate presigned URL

**Helper Methods Needed:**

- `_transform_graphql_package()` - GraphQL response → Package_Info
- `_transform_graphql_content()` - GraphQL dir response → Content_Info
- `_extract_bucket_from_registry()` - s3://bucket → bucket
- `_extract_tags_from_meta()` - Parse userMeta JSON for tags

**Testing:**

- Parametrize existing integration tests with Platform backend
- Test GraphQL error handling
- Test missing data scenarios

**Success Criteria:**

- All package search/browse tools work
- Results match Quilt3_Backend behavior
- GraphQL errors properly handled

---

### Phase 3: Write Operations (2-3 days) ✅ COMPLETED

**Milestone:** Can create and update packages

**Tasks:**

1. [x] Implement `get_boto3_client()` using JWTAuthService
2. [x] Implement `create_package_revision()` using GraphQL `packageConstruct` mutation
3. [x] Implement `update_package_revision()` using GraphQL queries + `packageConstruct` mutation
4. [x] Extract `_extract_logical_key()` helper (shared with Quilt3_Backend)
5. [x] Test copy=False scenario (copy=True raises NotImplementedError)
6. [x] Test auto_organize behavior

**Key Decision:** Use GraphQL `packageConstruct` mutation, NOT quilt3.Package

**Rationale:**

- **Architectural consistency:** Pure GraphQL for all operations (read + write)
- **No quilt3 dependency:** Removes quilt3 import from Platform_Backend
- **Platform-native:** Aligns with Platform's Lambda-based package creation
- **Simpler testing:** Mock GraphQL responses vs complex quilt3 mocking

**Implementation Notes:**

- `copy=True` parameter raises `NotImplementedError` (deferred to future work)
- `update_package_revision()` queries existing package contents via GraphQL
- Metadata merging implemented in Python (no longer handled by quilt3)
- All error types handled: InvalidInput, ComputeFailure, network errors

**Testing:**

- Test package creation with GraphQL mutation mocks
- Test update preserves existing files via GraphQL queries
- Test all error scenarios (InvalidInput, ComputeFailure)
- Test copy parameter validation (NotImplementedError)

**See also:** [12-graphql-native-write-operations.md](./12-graphql-native-write-operations.md) for detailed specification

**Success Criteria:**

- Can create packages with Platform backend using GraphQL
- Copy behavior: copy=False works, copy=True raises NotImplementedError
- Metadata merging works correctly in updates
- All GraphQL error types handled properly

---

### Phase 4: Admin Operations (Optional - 3-5 days)

**Milestone:** Full admin API support

**Note:** Defer this phase if not immediately needed

**Tasks:**

1. [ ] Create Platform_Admin_Ops class
2. [ ] Implement user management (list, get, create, delete, update)
3. [ ] Implement role management (list)
4. [ ] Implement SSO configuration (get, set, remove)
5. [ ] Create User and Role domain objects if needed

**Testing:**

- Admin integration tests (requires admin JWT)
- Test permission errors for non-admin users

**Success Criteria:**

- All admin operations functional
- Proper permission checking

---

## Open Questions

### GraphQL Endpoint

- [ ] Is endpoint always at `/graphql` or sometimes `/api/graphql`?
- [ ] Should we support multiple registry URLs per session?
- [ ] How to handle endpoint discovery failures?

### JWT Claims

- [ ] What's the expected token lifetime?
- [ ] Do we need refresh token support?
- [ ] Should we validate JWT signature or trust it?
- [ ] What happens if catalog_token is missing from JWT?

### Testing Strategy

- [ ] Do we need separate integration tests for Platform backend?
- [ ] Can we use same test catalog for both backends?
- [ ] How to test JWT expiration scenarios?
- [ ] Should we mock GraphQL responses or use real catalog?

### Error Handling

- [ ] Should GraphQL errors be retried?
- [ ] How to distinguish between auth errors and data errors?
- [ ] Should we validate GraphQL query syntax before sending?

### Performance

- [ ] Should we cache GraphQL responses?
- [ ] Should we batch multiple queries?
- [ ] How to handle large result sets (pagination)?

---

## Environment Variables

**New Variables Needed:**

```bash
# GraphQL endpoint (optional - will derive from JWT if not set)
QUILT_GRAPHQL_ENDPOINT=https://my-registry.quiltdata.com/graphql

# JWT secret for token validation (testing only)
QUILT_JWT_SECRET=test-secret-key

# Override catalog URL from JWT
QUILT_CATALOG_URL=https://my-catalog.quiltdata.com
```

**Existing Variables (Reference):**

```bash
# Multitenant mode flag (triggers Platform backend)
QUILT_MULTITENANT_MODE=true

# JWT token for authentication
MCP_JWT_TOKEN=eyJhbGci...

# AWS region for boto3
AWS_DEFAULT_REGION=us-east-1
```

---

## Dependencies

**Code References:**

- [tests/jwt_helpers.py](../../tests/jwt_helpers.py) - JWT generation and extraction
- [src/quilt_mcp/ops/tabulator_mixin.py](../../src/quilt_mcp/ops/tabulator_mixin.py) - GraphQL execution pattern
- [src/quilt_mcp/services/jwt_auth_service.py](../../src/quilt_mcp/services/jwt_auth_service.py) - AWS credentials
- [src/quilt_mcp/backends/quilt3_backend.py](../../src/quilt_mcp/backends/quilt3_backend.py) - Reference implementation

**External References:**

- `/Users/ernest/GitHub/enterprise/registry/quilt_server/graphql/` - Schema and resolvers
- `/Users/ernest/GitHub/enterprise/registry/quilt_server/views/graphql.py` - Endpoint implementation

---

## Testing Checklist

### Unit Tests (No Network)

- [ ] GraphQL endpoint derivation (env var vs JWT)
- [ ] Auth header construction from JWT claims
- [ ] GraphQL query construction
- [ ] Response transformation to domain objects
- [ ] Error handling (auth, network, GraphQL errors)
- [ ] Helper method logic

### Integration Tests (Real Catalog)

- [ ] JWT authentication flow end-to-end
- [ ] Search packages with real GraphQL
- [ ] Browse package content
- [ ] Create/update packages
- [ ] AWS operations (presigned URLs)
- [ ] Error scenarios (invalid token, missing permissions)

### Parametrized Tests (Both Backends)

- [ ] Package search returns same results
- [ ] Package info matches
- [ ] Content browsing identical
- [ ] Package creation behavior matches

### Platform-Specific Tests

- [ ] JWT claim extraction
- [ ] Endpoint selection logic
- [ ] GraphQL error handling
- [ ] Token expiration handling

---

## Success Metrics

**Phase 1 Complete:**

- GraphQL queries execute successfully
- JWT authentication works
- 20+ unit tests passing

**Phase 2 Complete:**

- All read operations functional
- Integration tests parametrized
- 50+ tests passing (unit + integration)

**Phase 3 Complete:**

- Package creation/update works
- boto3 clients authenticate via JWT
- 70+ tests passing

**Production Ready:**

- All QuiltOps methods implemented
- 100% feature parity with Quilt3_Backend
- All integration tests pass with both backends
- No regression in existing tests
- Documentation complete

---

## Next Steps

1. **Review this spec** - Get team feedback on decisions
2. **Verify GraphQL schema** - Check enterprise/registry/quilt_server/graphql/
3. **Start Phase 1** - Implement core infrastructure
4. **Create JWT test fixtures** - Extend jwt_helpers.py as needed
5. **Parametrize integration tests** - Set up backend factory fixture

---

## Notes

- We're already on branch `a16-graphql-backend`
- TabulatorMixin is already implemented and working
- JWT helpers exist and work with quilt3 sessions
- QuiltOps abstraction is solid - just need implementation
- Reference enterprise registry code for exact GraphQL query structure
