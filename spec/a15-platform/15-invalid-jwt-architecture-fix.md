# Invalid JWT Architecture: Problem and Solution

**Status:** 🔴 Critical - Architecture must be rewritten
**Date:** 2026-02-02

---

## Problem

**The entire MCP server architecture is built on fake JWTs.**

### What We Did Wrong

When we needed presigned S3 URLs, we took a shortcut:

- Put `role arn` in JWT claims
- MCP uses STS AssumeRole to get AWS credentials
- MCP generates presigned URLs directly

**This doesn't work because:**

- Platform JWTs contain only: `id`, `uuid`, `exp`
- Platform never issues JWTs with `role arn`, `catalog_url`, or `registry_url`
- Tests generate fake JWTs with custom claims
- Code expects those fake claims
- The entire architecture is invalid

### Platform JWT (Real)

```json
{
  "id": "81a35282-0149-4eb3-bb8e-627379db6a1c",
  "uuid": "3caa49a9-3752-486e-b979-51a369d6df69",
  "exp": 1776817104
}
```

That's all. Nothing else.

---

## Solution

**Use Platform's browsing session API that exists today.**

### How Browsing Session API Works

1. **Create session** (GraphQL mutation with Platform JWT):

   ```graphql
   mutation {
     browsingSessionCreate(
       scope: "s3://bucket#package=name&hash=abc123"
       ttl: 180
     ) {
       ... on BrowsingSession {
         id       # ← Browsing session UUID (NOT user id)
         expires
       }
     }
   }
   ```

   Response: `{ "id": "abc-123-session-uuid", "expires": "2026-02-02T12:30:00Z" }`

2. **Get presigned URL** (REST API):

   ```
   GET /browse/abc-123-session-uuid/path/to/file.csv
                └──────┬──────┘
            BrowsingSession.id from step 1

   Returns: 302 redirect to presigned S3 URL
   ```

**Important ID distinction:**

- **JWT `id` field** = User UUID (for authentication - proves who you are)
- **Browse URL `{session-id}`** = BrowsingSession UUID (from GraphQL response - specifies which package session)
- These are **different UUIDs** with different purposes
- You need both: JWT in cookie to authenticate, session-id in URL to access files

### Why This Works

- ✅ Uses real Platform JWT (id, uuid, exp)
- ✅ Platform handles all authorization
- ✅ Platform generates presigned URLs
- ✅ MCP needs no AWS credentials
- ✅ Works today - no Platform changes needed

### Why We Rejected It Before

We dismissed it as "complex" and "slow" - but those are **optimization concerns**, not architectural
problems. We should have:

1. Used browsing session API first (works correctly)
2. Optimized later if needed (maybe request Platform bulk API)

Instead we invented a fake JWT architecture.

---

## What Must Change

### 1. JWT Handling

**Remove:**

- Extraction of `role arn`, `catalog_url`, `registry_url` from JWT
- All code that expects custom JWT claims

**Keep:**

- JWT contains only `id`, `uuid`, `exp`
- JWT used for Platform authorization

### 2. Configuration Management

**Remove:**

- Dynamic config from JWT claims

**Add:**

- Static config from environment variables:

  ```bash
  export QUILT_CATALOG_URL="https://catalog.quiltdata.com"
  export QUILT_REGISTRY_URL="https://registry.quiltdata.com"
  ```

### 3. AWS Credential Flow

**Remove:**

- STS AssumeRole logic
- All boto3 credential handling in MCP
- `role arn` everywhere

**Result:**

- MCP has no AWS credentials
- MCP never touches AWS APIs directly

### 4. File Access Pattern

**Remove:**

- MCP generating presigned URLs

**Add:**

- Create browsing session via GraphQL
- Get presigned URLs via REST API
- Cache session for reuse

### 5. Test Infrastructure

**Remove:**

- `tests/jwt_helpers.py` functions that create fake JWTs with custom claims
- All tests that use fake JWT claims

**Add:**

- Tests use real Platform JWT structure (id, uuid, exp)
- Test helpers that work with valid JWTs

---

## Implementation Tasks

### Phase 1: Add Browsing Session Support

1. Create `BrowsingSessionClient` class
   - GraphQL mutation to create sessions
   - REST API calls to get presigned URLs
   - Session caching and lifecycle management

2. Add session management to backends
   - Platform backend uses browsing sessions
   - Cache sessions per package hash
   - Handle session expiry and refresh

3. Update file access methods
   - Replace presigned URL generation with session API calls
   - Handle 302 redirects
   - Extract final presigned URL

### Phase 2: Remove Fake JWT Architecture

1. Update `JWTAuthService`
   - Remove `_extract_role arn()` method
   - Remove `extract_catalog_claims()` method
   - Remove STS AssumeRole logic
   - Remove all boto3 usage

2. Add environment-based configuration
   - Read `QUILT_CATALOG_URL` from environment
   - Read `QUILT_REGISTRY_URL` from environment
   - Fail fast if required config missing

3. Update test JWT generation
   - Remove custom claim parameters from `generate_test_jwt()`
   - Only generate JWTs with `id`, `uuid`, `exp`
   - Update all test fixtures

### Phase 3: Update All Tests

1. Fix integration tests
   - Update JWT generation calls
   - Remove role arn arguments
   - Use environment variables for config

2. Fix unit tests
   - Mock browsing session API responses
   - Test session caching logic
   - Test session expiry handling

3. Update test documentation
   - Document environment variable requirements
   - Document browsing session test patterns

### Phase 4: Cleanup

1. Remove deprecated code
    - Delete role arn-related helpers
    - Delete fake JWT claim utilities
    - Remove STS-related imports

2. Update documentation
    - Document browsing session architecture
    - Document environment configuration
    - Update deployment guides

3. Verify all tests pass
    - Unit tests with valid JWT structure
    - Integration tests with real auth flow
    - E2E tests with browsing sessions

---

## Files to Modify

### Core Services

- `src/quilt_mcp/services/jwt_auth_service.py` - Remove STS AssumeRole, custom claims
- `src/quilt_mcp/backends/platform_backend.py` - Add browsing session support

### Test Infrastructure

- `tests/jwt_helpers.py` - Remove fake JWT generation
- All integration test files using JWT

### Configuration

- Add environment variable handling
- Update deployment configuration examples

---

## Success Criteria

1. ✅ All code uses real Platform JWT structure (id, uuid, exp only)
2. ✅ MCP has no AWS credentials or boto3 usage
3. ✅ File access uses browsing session API
4. ✅ Static configuration from environment variables
5. ✅ All tests pass with valid JWT structure
6. ✅ No references to role arn anywhere in codebase
7. ✅ Platform enforces all authorization decisions

---

## Performance Considerations

**Browsing session API characteristics:**

- Session creation: ~100-200ms (one-time per package)
- File access: ~50ms per file (REST call + redirect)
- Session TTL: 180 seconds default (configurable)

**Optimization strategies (if needed later):**

- Cache sessions aggressively
- Reuse sessions across requests
- Request longer TTL for batch operations
- Ask Platform team for bulk presigned URL API

**Critical insight:** Correct architecture first, optimize second.

---

## Appendix: Implementation Notes (2026-02-03)

- Updated multitenant tooling and docs to use Platform JWT claims (`id`, `uuid`, `exp`) and removed role-ARN based flows.
- Added `QUILT_REGISTRY_URL` alongside `QUILT_CATALOG_URL` as required static config for Platform backend and stateless tests.
- Replaced direct S3 presign usage with browsing session API calls and added caching tests.
