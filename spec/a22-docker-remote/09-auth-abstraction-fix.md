# Remove `use_quilt_auth` - Fix Auth Abstraction Violation

## Problem

Services and tools bypass the backend abstraction by directly calling `get_s3_client(use_quilt_auth=...)` and `get_sts_client(use_quilt_auth=...)`. This creates:

1. **Leaky abstraction** - Services know about auth mechanisms (quilt3 vs platform vs Docker)
2. **Impossible credential injection** - Can't inject JWT-derived AWS credentials from platform backend
3. **Scattered auth logic** - 30+ places with `use_quilt_auth` parameters
4. **Testing complexity** - Can't mock auth at backend boundary

## Key Design Decisions

### 1. Backend Owns All AWS Client Creation

**Decision:** Backends expose a single method for AWS clients:

```
backend.get_aws_client(service_name: str) -> boto3.Client
```

**Rationale:**

- Backend already handles all auth modes (JWT, quilt3 session, runtime context)
- Services should be ignorant of auth mechanism
- Enables credential injection for platform backend (JWT → STS → AWS creds)

### 2. Three-Tier Credential Priority (Inside Backend Only)

**Priority:**

1. Runtime context (middleware-provided boto3 session or AWS credentials)
2. Backend-specific auth (platform: JWT→STS, quilt3: quilt3.get_boto3_session())
3. Default boto3 (environment/IAM role - fallback only)

**Rationale:**

- Runtime context = highest priority (Docker remote mode, ngrok tunneling)
- Backend-specific = normal operation
- Default = last resort for unconfigured environments

### 3. Remove `use_quilt_auth` Entirely

**Decision:** Delete the parameter from all 30+ locations (services, tools, utils)

**Rationale:**

- Services don't need to know about auth
- Complexity reduction (one code path, not two)
- Platform backend can now inject credentials transparently

### 4. Services Get Clients From Backend

**Decision:** Services receive backend instance, call `backend.get_aws_client()`

**Rationale:**

- Testable (mock backend.get_aws_client())
- Backend can switch auth strategies without service changes
- Aligns with existing backend abstraction pattern

## High-Level Tasks

### Phase 1: Backend Implementation

- [ ] Add `get_aws_client(service_name: str)` to backend base class
- [ ] Implement in `Quilt3Backend` (use quilt3 session → boto3)
- [ ] Implement in `PlatformBackend` (use JWT → STS → temporary creds → boto3)
- [ ] Add runtime context priority (check `_runtime_boto3_session()` first)
- [ ] Add fallback to default boto3 (IAM/environment creds)

### Phase 2: Service Refactoring

- [ ] Update `AthenaQueryService.__init__()` to accept backend, remove `use_quilt_auth`
- [ ] Update `GovernanceService.__init__()` to accept backend, remove `use_quilt_auth`
- [ ] Replace `get_s3_client(use_quilt_auth)` calls with `backend.get_aws_client("s3")`
- [ ] Replace `get_sts_client(use_quilt_auth)` calls with `backend.get_aws_client("sts")`

### Phase 3: Tool Refactoring

- [ ] Remove `use_quilt_auth` parameter from all Athena tools (3 tools)
- [ ] Remove `use_quilt_auth` parameter from `tabulator()` tool
- [ ] Remove hardcoded `use_quilt_auth=True` from resources.py and resource_access.py
- [ ] Update tool implementations to pass backend to services

### Phase 4: Utility Cleanup

- [ ] Delete `use_quilt_auth` parameter from `get_s3_client()` in utils/common.py
- [ ] Delete `use_quilt_auth` parameter from `get_sts_client()` in utils/common.py
- [ ] Move credential priority logic into backend implementations
- [ ] Keep `_runtime_boto3_session()` as internal helper for backends

### Phase 5: Testing & Validation

- [ ] Update unit tests for services (mock backend.get_aws_client())
- [ ] Update integration tests (verify credential flow)
- [ ] Test Docker remote mode (runtime context credentials)
- [ ] Test platform backend (JWT → AWS credentials flow)
- [ ] Test quilt3 backend (quilt3 session credentials)
- [ ] Verify no `use_quilt_auth` references remain (`grep -r`)

## Success Criteria

1. **Zero `use_quilt_auth` references** in codebase (except possibly deprecation warnings)
2. **All tests pass** for both quilt3 and platform backends
3. **Docker remote mode works** with runtime-injected credentials
4. **Platform backend** can inject JWT-derived AWS credentials into Athena/S3 operations
5. **Services are backend-agnostic** - no auth mechanism knowledge

## Impact

- **Services:** 2 files (athena_service.py, governance_service.py)
- **Tools:** 4 files (athena_read_service.py, tabulator.py, resources.py, resource_access.py)
- **Utils:** 1 file (common.py)
- **Backends:** 2 files (quilt3_backend.py, platform_backend.py - new method)
- **Tests:** Multiple test files need backend mocking updates

## Non-Goals

- Changing backend initialization or selection logic
- Modifying JWT discovery mechanisms
- Changing runtime context structure
- Altering quilt3.get_boto3_session() behavior
