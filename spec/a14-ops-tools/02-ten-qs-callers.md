# QuiltService Fake Abstraction Callers

## Overview

This document identifies where the 10 "fake abstraction" methods from QuiltService are called, grouped by use case to understand their impact scope.

## Summary Statistics

| Method                       | Internal Services | Tests | MCP Tools | Scripts | Backends | Search | Total |
|------------------------------|-------------------|-------|-----------|---------|----------|--------|-------|
| `get_users_admin()`          | 13                | 1     | 0         | 0       | 0        | 0      | 14    |
| `get_session()`              | 4                 | 3     | 2         | 1       | 1        | 1      | 12    |
| `get_tabulator_admin()`      | 9                 | 1     | 0         | 0       | 0        | 0      | 10    |
| `create_botocore_session()`  | 4                 | 2     | 0         | 0       | 1        | 0      | 7     |
| `get_sso_config_admin()`     | 5                 | 1     | 0         | 0       | 0        | 0      | 6     |
| `get_search_api()`           | 0                 | 1     | 0         | 2       | 0        | 1      | 4     |
| `get_roles_admin()`          | 3                 | 1     | 0         | 0       | 0        | 0      | 4     |
| `browse_package()`           | 0                 | 1     | 1         | 0       | 0        | 0      | 2     |
| `create_bucket()`            | 0                 | 1     | 0         | 0       | 0        | 0      | 1     |
| `get_quilt3_module()`        | 0                 | 0     | 1         | 0       | 0        | 0      | 1     |
| **Total**                    | **38**            | **12**| **4**     | **3**   | **2**    | **2**  | **61**|

**Key Insight:** 62% (38/61) of calls are from internal services, making them the primary consumers of fake abstractions.

---

## 1. `get_session()` - Returns raw `requests.Session`

**Total Callers: 12** (excluding self-reference in `get_catalog_config()`)

### Internal Services (4 calls)

1. [jwt_auth_service.py:109](../../src/quilt_mcp/services/jwt_auth_service.py#L109) - Auth service
2. [auth_service.py:49](../../src/quilt_mcp/services/auth_service.py#L49) - Base auth service
3. [iam_auth_service.py:54](../../src/quilt_mcp/services/iam_auth_service.py#L54) - IAM auth (call 1)
4. [iam_auth_service.py:58](../../src/quilt_mcp/services/iam_auth_service.py#L58) - IAM auth (call 2)
5. [iam_auth_service.py:65](../../src/quilt_mcp/services/iam_auth_service.py#L65) - IAM auth (call 3)

### Backends (1 call)

1. [quilt3_backend_session.py:73](../../src/quilt_mcp/backends/quilt3_backend_session.py#L73) - Session mixin (call 1)
2. [quilt3_backend_session.py:268](../../src/quilt_mcp/backends/quilt3_backend_session.py#L268) - Session mixin (call 2)

### MCP Tools (2 calls)

1. [search.py:378](../../src/quilt_mcp/tools/search.py#L378) - Package search tool
2. [stack_buckets.py:49](../../src/quilt_mcp/tools/stack_buckets.py#L49) - Bucket listing tool

### Search Backend (1 call)

1. [elasticsearch.py:228](../../src/quilt_mcp/search/backends/elasticsearch.py#L228) - Elasticsearch backend

### Scripts (1 call)

1. [list_all_indices.py:42](../../scripts/list_all_indices.py#L42) - Diagnostic script

### Tests (3 calls)

1. [test_auth_service.py:62](../../tests/unit/services/test_auth_service.py#L62) - Auth service tests
2. [test_iam_auth_service.py:23](../../tests/unit/services/test_iam_auth_service.py#L23) - IAM tests (call 1)
3. [test_iam_auth_service.py:30](../../tests/unit/services/test_iam_auth_service.py#L30) - IAM tests (call 2)
4. [test_quilt_service.py:296](../../tests/unit/test_quilt_service.py#L296) - QuiltService tests

**Impact:** High - Used across auth services, backends, MCP tools, and search. Critical for GraphQL access.

---

## 2. `create_botocore_session()` - Returns raw `botocore.Session`

**Total Callers: 7**

### Internal Services (4 calls)

1. [athena_service.py:90](../../src/quilt_mcp/services/athena_service.py#L90) - Athena service (call 1)
2. [athena_service.py:190](../../src/quilt_mcp/services/athena_service.py#L190) - Athena service (call 2)
3. [athena_service.py:204](../../src/quilt_mcp/services/athena_service.py#L204) - Athena service (call 3)
4. [athena_service.py:495](../../src/quilt_mcp/services/athena_service.py#L495) - Athena service (call 4)

### Backends (1 call)

1. [quilt3_backend_session.py:337](../../src/quilt_mcp/backends/quilt3_backend_session.py#L337) - Session mixin

### Tests (2 calls)

1. [test_quilt_service.py:323](../../tests/unit/test_quilt_service.py#L323) - QuiltService tests (success)
2. [test_quilt_service.py:332](../../tests/unit/test_quilt_service.py#L332) - QuiltService tests (failure)
3. [diagnostic_athena_connection.py:32](../../tests/fixtures/diagnostic_athena_connection.py#L32) - Diagnostic fixture

**Impact:** Medium - Primarily used by Athena service for AWS SDK client creation.

---

## 3. `browse_package()` - Returns raw `quilt3.Package`

**Total Callers: 2**

### MCP Tools (1 call)

1. [packages.py:1410](../../src/quilt_mcp/tools/packages.py#L1410) - Package update tool

### Tests (1 call)

1. [test_quilt_service.py:243](../../tests/unit/test_quilt_service.py#L243) - QuiltService tests (basic)
2. [test_quilt_service.py:252](../../tests/unit/test_quilt_service.py#L252) - QuiltService tests (with top_hash)

**Impact:** Low - Only used in package update tool. Candidate for QuiltOps migration.

---

## 4. `create_bucket()` - Returns raw `quilt3.Bucket`

**Total Callers: 1**

### Tests (1 call)

1. [test_quilt_service.py:261](../../tests/unit/test_quilt_service.py#L261) - QuiltService tests

**Impact:** Minimal - No production usage found! Only tested, never actually used.

---

## 5. `get_search_api()` - Returns raw `quilt3.search_util.search_api`

**Total Callers: 4**

### Search Backend (1 call)

1. [elasticsearch.py:449](../../src/quilt_mcp/search/backends/elasticsearch.py#L449) - Elasticsearch backend

### Scripts (2 calls)

1. [list_all_indices.py:58](../../scripts/list_all_indices.py#L58) - Diagnostic script
2. [discover_elasticsearch_indices.py:77](../../scripts/discover_elasticsearch_indices.py#L77) - Discovery script

### Tests (1 call)

1. [test_quilt_service.py:270](../../tests/unit/test_quilt_service.py#L270) - QuiltService tests

**Impact:** Low - Used only by search backend and diagnostic scripts.

---

## 6. `get_tabulator_admin()` - Returns raw `quilt3.admin.tabulator`

**Total Callers: 10**

### Internal Services (9 calls)

1. [tabulator_service.py:141](../../src/quilt_mcp/services/tabulator_service.py#L141) - Tabulator service (call 1)
2. [tabulator_service.py:210](../../src/quilt_mcp/services/tabulator_service.py#L210) - Tabulator service (call 2)
3. [tabulator_service.py:253](../../src/quilt_mcp/services/tabulator_service.py#L253) - Tabulator service (call 3)
4. [tabulator_service.py:292](../../src/quilt_mcp/services/tabulator_service.py#L292) - Tabulator service (call 4)
5. [tabulator_service.py:329](../../src/quilt_mcp/services/tabulator_service.py#L329) - Tabulator service (call 5)
6. [tabulator_service.py:348](../../src/quilt_mcp/services/tabulator_service.py#L348) - Tabulator service (call 6)
7. [governance_service.py:34](../../src/quilt_mcp/services/governance_service.py#L34) - Module-level import
8. [governance_service.py:1102](../../src/quilt_mcp/services/governance_service.py#L1102) - Governance service (call 1)
9. [governance_service.py:1152](../../src/quilt_mcp/services/governance_service.py#L1152) - Governance service (call 2)

### Tests (1 call)

1. [test_quilt_service.py:421](../../tests/unit/test_quilt_service.py#L421) - QuiltService tests (success)
2. [test_quilt_service.py:428](../../tests/unit/test_quilt_service.py#L428) - QuiltService tests (failure)

**Impact:** High - Heavily used by tabulator and governance services for admin operations.

---

## 7. `get_users_admin()` - Returns raw `quilt3.admin.users`

**Total Callers: 14** 🚨 **HIGHEST USAGE**

### Internal Services (13 calls!)

1. [governance_service.py:31](../../src/quilt_mcp/services/governance_service.py#L31) - Module-level import
2. [governance_service.py:115](../../src/quilt_mcp/services/governance_service.py#L115) - User list
3. [governance_service.py:191](../../src/quilt_mcp/services/governance_service.py#L191) - User get
4. [governance_service.py:317](../../src/quilt_mcp/services/governance_service.py#L317) - User create
5. [governance_service.py:379](../../src/quilt_mcp/services/governance_service.py#L379) - User update
6. [governance_service.py:443](../../src/quilt_mcp/services/governance_service.py#L443) - User delete
7. [governance_service.py:505](../../src/quilt_mcp/services/governance_service.py#L505) - User disable
8. [governance_service.py:567](../../src/quilt_mcp/services/governance_service.py#L567) - User enable
9. [governance_service.py:620](../../src/quilt_mcp/services/governance_service.py#L620) - User reset password
10. [governance_service.py:700](../../src/quilt_mcp/services/governance_service.py#L700) - User set password
11. [governance_service.py:768](../../src/quilt_mcp/services/governance_service.py#L768) - User list buckets
12. [governance_service.py:845](../../src/quilt_mcp/services/governance_service.py#L845) - User set role

### Tests (1 call)

1. [test_quilt_service.py:371](../../tests/unit/test_quilt_service.py#L371) - QuiltService tests (success)
2. [test_quilt_service.py:381](../../tests/unit/test_quilt_service.py#L381) - QuiltService tests (failure)

**Impact:** Very High - Governance service completely depends on this for all user management operations.

---

## 8. `get_roles_admin()` - Returns raw `quilt3.admin.roles`

**Total Callers: 4**

### Internal Services (3 calls)

1. [governance_service.py:32](../../src/quilt_mcp/services/governance_service.py#L32) - Module-level import
2. [governance_service.py:893](../../src/quilt_mcp/services/governance_service.py#L893) - Role list

### Tests (1 call)

1. [test_quilt_service.py:391](../../tests/unit/test_quilt_service.py#L391) - QuiltService tests (success)
2. [test_quilt_service.py:398](../../tests/unit/test_quilt_service.py#L398) - QuiltService tests (failure)

**Impact:** Medium - Used for role management in governance service.

---

## 9. `get_sso_config_admin()` - Returns raw `quilt3.admin.sso_config`

**Total Callers: 6**

### Internal Services (5 calls)

1. [governance_service.py:33](../../src/quilt_mcp/services/governance_service.py#L33) - Module-level import
2. [governance_service.py:950](../../src/quilt_mcp/services/governance_service.py#L950) - SSO config get
3. [governance_service.py:1018](../../src/quilt_mcp/services/governance_service.py#L1018) - SSO config put
4. [governance_service.py:1066](../../src/quilt_mcp/services/governance_service.py#L1066) - SSO config delete

### Tests (1 call)

1. [test_quilt_service.py:406](../../tests/unit/test_quilt_service.py#L406) - QuiltService tests (success)
2. [test_quilt_service.py:413](../../tests/unit/test_quilt_service.py#L413) - QuiltService tests (failure)

**Impact:** Medium - Used for SSO configuration in governance service.

---

## 10. `get_quilt3_module()` - Returns entire `quilt3` module

**Total Callers: 1**

### MCP Tools (1 call)

1. [packages.py:58](../../src/quilt_mcp/tools/packages.py#L58) - Module-level import for backward compatibility

**Impact:** Low - Single usage for backward compatibility. Used to access `quilt3.util.fix_url()`.

---

## Analysis by Consumer Type

### Internal Services: 38 calls (62%)

**Breakdown:**

- `governance_service.py`: 24 calls (4 admin modules × multiple operations)
- `tabulator_service.py`: 6 calls (tabulator admin)
- `athena_service.py`: 4 calls (botocore session)
- `auth_service.py` family: 4 calls (requests session)

**Observation:** Internal services are the primary consumers, particularly governance and tabulator services which heavily depend on raw admin modules.

### Backends: 2 calls (3%)

- `quilt3_backend_session.py`: 2 calls (session + botocore session)

**Observation:** Minimal backend usage, primarily in session management.

### MCP Tools: 4 calls (7%)

- `packages.py`: 2 calls (browse_package + get_quilt3_module)
- `search.py`: 1 call (get_session)
- `stack_buckets.py`: 1 call (get_session)

**Observation:** Tools show moderate usage, mixing package and session operations.

### Search Backend: 2 calls (3%)

- `elasticsearch.py`: 2 calls (get_session + get_search_api)

**Observation:** Search backend has tight coupling to quilt3 search internals.

### Scripts: 3 calls (5%)

- Diagnostic/discovery scripts: 3 calls (session + search API)

**Observation:** Operational scripts depend on low-level access.

### Tests: 12 calls (20%)

- QuiltService unit tests cover all 10 fake abstractions

**Observation:** Every fake abstraction has test coverage, but tests merely verify pass-through behavior.

---

## Migration Priority

Based on usage frequency and impact:

### Priority 1 (High Impact, Frequent Use)

1. **`get_users_admin()`** - 14 calls, governance service fully dependent
2. **`get_session()`** - 12 calls, used across auth, tools, search
3. **`get_tabulator_admin()`** - 10 calls, tabulator/governance services

### Priority 2 (Medium Impact)

1. **`create_botocore_session()`** - 7 calls, Athena service dependent
2. **`get_sso_config_admin()`** - 6 calls, SSO management
3. **`get_roles_admin()`** - 4 calls, role management
4. **`get_search_api()`** - 4 calls, search backend

### Priority 3 (Low Impact)

1. **`browse_package()`** - 2 calls, single tool usage
2. **`get_quilt3_module()`** - 1 call, backward compatibility
3. **`create_bucket()`** - 1 call (test only, no production usage!)

---

## Recommendations

1. **Admin Module Consolidation**: Create proper abstractions in governance/tabulator services to replace raw admin module access (34 calls across admin methods)

2. **Session Management**: Refactor `get_session()` callers to use higher-level operations instead of manipulating raw session objects (12 calls)

3. **Athena Service**: Abstract botocore session creation into dedicated AWS client factory (7 calls)

4. **Search Backend**: Abstract search API behind proper interface (4 calls)

5. **Dead Code**: Remove `create_bucket()` - it's tested but never used in production

6. **Tool Migration**: Migrate `browse_package()` and `get_quilt3_module()` to QuiltOps (3 calls)
