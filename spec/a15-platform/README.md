# Platform Backend Implementation Specs

This directory contains specifications and design documentation for implementing the Platform GraphQL backend.

## Documents

### 🚀 Quick Start

**New to multitenant testing?** Start here:

- **[09-quick-start-multitenant.md](09-quick-start-multitenant.md)** - 5-minute setup guide for testing multitenant Platform backend

### 📋 [00-implementation-summary.md](00-implementation-summary.md)

**Start here!** Executive summary with quick reference tables, implementation phases, and success criteria.

**Key Sections:**

- Quick reference table
- JWT authentication approach
- Method implementation strategy
- 4-phase implementation plan
- Testing strategy
- Success criteria

### 🔍 [01-es-integration.md](01-es-integration.md)

Elasticsearch integration tests migration plan (60 broken tests after QuiltOps migration).

**Status:** Separate effort, not blocking Platform backend

**Focus:** Fixing test fixtures to use `quilt3_backend` instead of deprecated `quilt_service`

### 📖 [02-graphql.md](02-graphql.md)

GraphQL API documentation from registry codebase analysis.

**Content:**

- Registry GraphQL schema overview
- How Elasticsearch backend uses GraphQL (bucket discovery only)
- How quilt3 admin client uses GraphQL (all admin ops)
- Tabulator API (dual REST + GraphQL)
- Native search queries (not currently used)

### 🗺️ [03-graphql-apis.md](03-graphql-apis.md)

**Most detailed document.** Complete mapping of QuiltOps interface to GraphQL operations.

**Content:**

- JWT authentication strategy (detailed)
- All 16 QuiltOps method implementations
- GraphQL query examples with schema definitions
- Domain object construction patterns
- Helper methods needed
- Error handling patterns
- Resolved design decisions

### 🧪 [08-multitenant-testing-spec.md](08-multitenant-testing-spec.md)

**Comprehensive testing specification** for multitenant Platform backend implementation.

**Content:**

- Manual testing guide (single & multi-tenant)
- Automated testing strategies (unit, integration, E2E)
- JWT authentication testing
- Tenant isolation verification
- CI/CD integration
- Performance benchmarks
- Troubleshooting guide

### ⚡ [09-quick-start-multitenant.md](09-quick-start-multitenant.md)

**5-minute quick start** for multitenant testing.

**Content:**

- Prerequisites setup
- Automated testing (recommended)
- Manual testing steps
- Common issues & solutions
- Verification checklist

### 🔗 [10-jwt-helpers-integration.md](10-jwt-helpers-integration.md)

**Integration verification** - Confirms jwt_helpers.py properly supports multitenant testing.

**Content:**

- jwt_helpers.py enhancements (tenant_id parameter)
- Integration points with test orchestrator
- Verification tests
- Complete workflow example
- Troubleshooting guide

## Implementation Approach Summary

### Authentication: JWT Bearer Tokens

```python
# JWT claims provide catalog authentication
{
    "catalog_token": "bearer-token-for-graphql",
    "catalog_url": "https://my-catalog.quiltdata.com",
    "registry_url": "https://my-registry.quiltdata.com",
    "role_arn": "arn:aws:iam::123:role/QuiltRole"
}
```

### Read Operations: GraphQL Queries

All read operations use GraphQL:

- `search_packages()` → `searchPackages` query
- `get_package_info()` → `package` query
- `list_buckets()` → `bucketConfigs` query
- `browse_content()` → `package.dir` query

### Write Operations: quilt3 Package Engine

Package creation uses quilt3 library (NOT GraphQL):

- `create_package_revision()` → `quilt3.Package()` + `package.push()`
- `update_package_revision()` → Same as create

**Why?** Consistent with Quilt3_Backend, full feature support, proven patterns.

### AWS Operations: JWT + STS

boto3 clients use JWT role assumption:

```python
# JWTAuthService uses role_arn claim for STS AssumeRole
auth_service = JWTAuthService()
boto3_session = auth_service.get_boto3_session()
client = boto3_session.client('s3')
```

## Reading Order

1. **Start:** [00-implementation-summary.md](00-implementation-summary.md) - Get overview
2. **Deep dive:** [03-graphql-apis.md](03-graphql-apis.md) - See all implementation details
3. **Reference:** [02-graphql.md](02-graphql.md) - Understand GraphQL schema
4. **Optional:** [01-es-integration.md](01-es-integration.md) - If working on tests

## Quick Links

### Source Code References

- **Target file:** [platform_backend.py](../../src/quilt_mcp/backends/platform_backend.py) (current stub)
- **Reference impl:** [quilt3_backend.py](../../src/quilt_mcp/backends/quilt3_backend.py)
- **Interface:** [quilt_ops.py](../../src/quilt_mcp/ops/quilt_ops.py)
- **JWT auth:** [jwt_auth_service.py](../../src/quilt_mcp/services/jwt_auth_service.py)
- **Domain objects:** [domain/](../../src/quilt_mcp/domain/)

### Test References

- **JWT integration:** [test_jwt_search.py](../../scripts/tests/test_jwt_search.py)
- **Unit tests:** [tests/unit/backends/](../../tests/unit/backends/)
- **Integration tests:** [tests/integration/](../../tests/integration/)

## Status

**Phase:** Design Complete ✅

**Next:** Implementation Phase 1 (Core Infrastructure)

**Branch:** `a15-platform-backend` (to be created)

## Timeline Estimate

- **Phase 1** (Core): 3-5 days
- **Phase 2** (Read Ops): 3-5 days
- **Phase 3** (Write Ops): 2-3 days
- **Phase 4** (Admin Ops): 3-5 days

**Total:** 2-3 weeks for full implementation
