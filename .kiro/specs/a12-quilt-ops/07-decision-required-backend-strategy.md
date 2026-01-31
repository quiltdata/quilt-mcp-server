# Decision Required: Backend Selection Strategy

**Date:** 2026-01-31
**Status:** BLOCKED - Architectural decision needed before implementation
**Priority:** HIGH - Blocks 15+ failing integration tests

---

## Decision Summary

**Question:** How should `QuiltOpsFactory` handle authentication and backend selection?

**Current State:**
- Factory is incomplete Phase 1 stub
- Only detects quilt3 sessions (using wrong API)
- No fallback when quilt3 unavailable
- Tests expect AWS IAM fallback that doesn't exist

**Impact:**
- 15+ integration tests failing
- 2 MCP tools unusable in production (`packages_list`, `package_browse`)
- Confusion between factory and service layer auth strategies

---

## Three Strategic Options

### Option A: Complete Multi-Backend Architecture (Original Design)

**Implement the full Phase 2 design with all backends.**

#### What to Build

```
QuiltOpsFactory.create()
    ↓
    ├─ [quilt3 session detected] → Quilt3_Backend
    ├─ [JWT token detected]      → Platform_Backend (NEW)
    └─ [AWS credentials only]    → IAM_Backend (NEW)
```

**New classes to create:**

1. **Platform_Backend** (`src/quilt_mcp/backends/platform_backend.py`)
   - Implements QuiltOps via Platform GraphQL API
   - Uses JWT token authentication
   - For web/cloud deployments

2. **IAM_Backend** (`src/quilt_mcp/backends/iam_backend.py`)
   - Implements QuiltOps via direct AWS/S3 operations
   - Uses boto3 session with IAM credentials
   - No quilt3 library dependency

3. **Factory fallback logic** (update `src/quilt_mcp/ops/factory.py`)
   ```python
   def create() -> QuiltOps:
       # Check for quilt3 session (fix API)
       if not os.getenv("QUILT_DISABLE_QUILT3_SESSION") == "1":
           if session_info := _detect_quilt3_session():
               return Quilt3_Backend(session_info)

       # Check for JWT token
       if jwt_token := _detect_jwt_token():
           return Platform_Backend(jwt_token, catalog_url)

       # Check for AWS credentials
       if boto3_session := _detect_aws_credentials():
           registry = os.getenv("QUILT_DEFAULT_REGISTRY") or "s3://quilt-example"
           return IAM_Backend(boto3_session, registry)

       raise AuthenticationError("No valid authentication found")
   ```

#### Pros
- ✅ Complete solution matching original design
- ✅ Supports all deployment modes (local, web, cloud)
- ✅ Clean abstraction with proper fallbacks
- ✅ Tests can use IAM_Backend when quilt3 disabled
- ✅ Aligns with "backend-agnostic" QuiltOps interface

#### Cons
- ❌ Significant implementation work (2 new backends, 100+ methods)
- ❌ Platform_Backend requires GraphQL API knowledge
- ❌ IAM_Backend needs direct S3/API operations
- ❌ May duplicate logic from service layer
- ❌ Unclear if Platform GraphQL API is stable enough

#### Estimated Effort
- Platform_Backend: 3-5 days (GraphQL queries for all QuiltOps methods)
- IAM_Backend: 2-3 days (S3 operations for all QuiltOps methods)
- Factory updates: 1 day
- Test updates: 1-2 days
- **Total: ~2 weeks**

---

### Option B: Simplify to quilt3-Only (Accept Phase 1)

**Fix the API but keep factory limited to quilt3 sessions only.**

#### What to Change

1. **Fix factory API calls** (`src/quilt_mcp/ops/factory.py`)
   ```python
   def _detect_quilt3_session() -> Optional[dict]:
       if quilt3 is None:
           return None

       # Check disable flag
       if os.getenv("QUILT_DISABLE_QUILT3_SESSION") == "1":
           return None

       try:
           # Use CORRECT API
           if not quilt3.session.logged_in():
               return None

           registry_url = quilt3.session.get_registry_url()
           return {'registry': registry_url, 'logged_in': True}
       except Exception as e:
           logger.debug(f"Error detecting quilt3 session: {e}")
           return None
   ```

2. **Update documentation**
   - Remove "Phase 2" promises
   - Document factory as quilt3-only
   - Direct users to service layer for other auth modes

3. **Fix integration tests**
   - Remove `QUILT_DISABLE_QUILT3_SESSION` from tests using factory
   - Use real quilt3 session OR bypass factory entirely
   - Keep service layer for IAM/JWT scenarios

4. **Update MCP tools** (if needed)
   - `packages_list()` and `package_browse()` work with quilt3 only
   - Add fallback to service layer for non-quilt3 scenarios

#### Pros
- ✅ Minimal code changes
- ✅ Clear scope (quilt3-only)
- ✅ Quick to implement (days, not weeks)
- ✅ Service layer already handles other auth modes
- ✅ No risk of duplicating logic

#### Cons
- ❌ Factory remains limited
- ❌ Tests using factory require quilt3 login
- ❌ Doesn't match original "backend-agnostic" vision
- ❌ Two parallel auth systems (factory + service layer)
- ❌ MCP tools limited to quilt3 mode

#### Estimated Effort
- Factory API fix: 1-2 hours
- Test updates: 1 day
- Documentation: 2-3 hours
- **Total: ~2 days**

---

### Option C: Merge with Service Layer (Unify Auth)

**Eliminate factory, use service layer for all auth, create backends from service.**

#### What to Change

1. **Remove QuiltOpsFactory** entirely

2. **Add backend creation to service layer**
   ```python
   # In RequestContextFactory or new QuiltOpsService
   def create_quilt_ops(self) -> QuiltOps:
       """Create QuiltOps backend based on service layer auth."""
       auth_service = self._create_auth_service()

       if isinstance(auth_service, JWTAuthService):
           # Web/cloud mode with JWT
           catalog_url = get_runtime_auth().catalog_url
           jwt_token = auth_service.get_token()
           return Platform_Backend(jwt_token, catalog_url)

       elif isinstance(auth_service, IAMAuthService):
           # Local/desktop mode with AWS credentials
           boto3_session = auth_service.get_boto3_session()

           # Check if quilt3 session available
           if auth_service.has_quilt3_session():
               session_info = {
                   'registry': quilt3.session.get_registry_url(),
                   'logged_in': True,
               }
               return Quilt3_Backend(session_info)
           else:
               # Pure IAM mode
               registry = os.getenv("QUILT_DEFAULT_REGISTRY")
               return IAM_Backend(boto3_session, registry)
   ```

3. **Update MCP tools**
   - Replace `QuiltOpsFactory.create()` with `context.create_quilt_ops()`
   - Tools now use unified auth strategy

4. **Benefits**
   - Single auth decision point
   - Leverages working service layer
   - Eliminates duplication

#### Pros
- ✅ Unifies auth strategy (no duplication)
- ✅ Leverages proven service layer code
- ✅ Clean architecture (one decision point)
- ✅ Proper fallback chain already exists
- ✅ IAMAuthService handles quilt3/AWS/default correctly

#### Cons
- ❌ Still requires Platform_Backend and IAM_Backend
- ❌ Architectural refactoring (changes import patterns)
- ❌ May complicate request context flow
- ❌ Breaks existing factory-based code
- ❌ Not much simpler than Option A

#### Estimated Effort
- Remove factory: 1 day
- Integrate with service layer: 2 days
- Platform_Backend: 3-5 days
- IAM_Backend: 2-3 days
- Update all call sites: 1 day
- **Total: ~2 weeks**

---

## Comparison Matrix

| Aspect | Option A: Complete | Option B: Simplify | Option C: Merge |
|--------|-------------------|-------------------|-----------------|
| **Implementation Time** | ~2 weeks | ~2 days | ~2 weeks |
| **Code Complexity** | High (2 new backends) | Low (API fix only) | Medium (refactor + backends) |
| **Auth Modes Supported** | All (quilt3, JWT, IAM) | quilt3 only | All (quilt3, JWT, IAM) |
| **Architecture Clarity** | Clear (factory does all) | Unclear (two systems) | Clear (service does all) |
| **Risk** | Medium (new code) | Low (minimal changes) | Medium (architectural change) |
| **Matches Original Design** | Yes | No | Better than original |
| **Test Complexity** | Medium | Low | Medium |
| **Maintenance** | Medium | Low | Low |

---

## Recommendation: Option B (Short-term) + Option C (Long-term)

### Phase 1: Quick Fix (Option B)
**Timeline: This week**

1. Fix factory API to use correct quilt3 methods
2. Add `QUILT_DISABLE_QUILT3_SESSION` check
3. Update integration tests to use real quilt3 session
4. Document factory as quilt3-only
5. Unblock 15+ failing tests

**Benefits:**
- Tests pass immediately
- Minimal risk
- Clear scope

### Phase 2: Proper Architecture (Option C)
**Timeline: Next sprint**

1. Design unified auth/backend strategy
2. Implement Platform_Backend
3. Implement IAM_Backend
4. Merge factory into service layer
5. Update all MCP tools

**Benefits:**
- Clean long-term architecture
- No duplication
- All auth modes supported

---

## Questions Needing Answers

### Q1: Is Platform GraphQL API stable/documented?

**Context:** Platform_Backend needs comprehensive GraphQL API for all QuiltOps methods.

**Questions:**
- Is there GraphQL schema documentation?
- Are all package operations available via GraphQL?
- What's the authentication flow with JWT?
- Is the API production-ready?

**If NO:** Platform_Backend may not be feasible → stick with Option B

### Q2: What do MCP tools actually need?

**Context:** Only 2 tools use factory: `packages_list()` and `package_browse()`

**Questions:**
- Are these tools only used locally (with quilt3)?
- Do they need web/cloud support?
- Can they use service layer directly?

**If local-only:** Option B sufficient → no need for Platform_Backend

### Q3: What's the deployment model?

**Context:** Different backends for different deployment modes

**Deployment scenarios:**
- **Local CLI** (current) → quilt3 session → Quilt3_Backend
- **Web UI** (future?) → JWT token → Platform_Backend
- **Server/Lambda** (future?) → IAM role → IAM_Backend

**Questions:**
- Is web UI deployment planned?
- Is server-side deployment planned?
- Timeline for non-local deployments?

**If local-only for foreseeable future:** Option B sufficient

### Q4: What do integration tests actually test?

**Context:** Tests are called "integration" but heavily mocked

**Questions:**
- Should they test real AWS operations?
- Should they test real quilt3 operations?
- Or just multi-component interaction?

**Answer affects:**
- Whether to keep `QUILT_DISABLE_QUILT3_SESSION`
- What credentials tests should use
- Mock vs real backend usage

---

## Immediate Next Steps

### Before Implementation (Choose Option)

1. **Answer Q2:** Audit MCP tool usage
   ```bash
   # Find all uses of QuiltOpsFactory
   grep -r "QuiltOpsFactory.create()" src/

   # Check tool deployment contexts
   ```

2. **Answer Q3:** Check deployment plans
   - Review product roadmap
   - Check for web/cloud requirements
   - Confirm local-only timeline

3. **Answer Q1:** Verify Platform API availability
   - Check internal GraphQL docs
   - Test JWT authentication flow
   - Confirm API coverage

4. **Answer Q4:** Define integration test philosophy
   - Review test goals
   - Decide on mock vs real
   - Update test documentation

### After Decision

**If Option A or C chosen:**
- Prototype Platform_Backend with one method
- Validate GraphQL API works
- Design IAM_Backend architecture
- Create detailed implementation plan

**If Option B chosen:**
- Fix factory API (use `logged_in()`, `get_registry_url()`)
- Add env var check
- Update integration tests
- Merge and deploy

---

## Files Requiring Decision Impact

### Critical Files (All Options)
- [src/quilt_mcp/ops/factory.py](../../src/quilt_mcp/ops/factory.py) - Factory implementation
- [src/quilt_mcp/tools/packages.py](../../src/quilt_mcp/tools/packages.py) - MCP tools using factory
- [tests/conftest.py](../../tests/conftest.py) - Test configuration
- [tests/integration/test_end_to_end_workflows.py](../../tests/integration/test_end_to_end_workflows.py) - Failing tests

### Additional Files (Option A/C)
- **NEW:** `src/quilt_mcp/backends/platform_backend.py` - GraphQL backend
- **NEW:** `src/quilt_mcp/backends/iam_backend.py` - IAM-only backend
- [src/quilt_mcp/context/factory.py](../../src/quilt_mcp/context/factory.py) - If merging auth

### Test Files (All Options)
- [tests/unit/ops/test_factory.py](../../tests/unit/ops/test_factory.py) - Factory tests
- [tests/integration/test_packages_integration.py](../../tests/integration/test_packages_integration.py) - Package tests
- **NEW:** `tests/unit/backends/test_platform_backend.py` (if Option A/C)
- **NEW:** `tests/unit/backends/test_iam_backend.py` (if Option A/C)

---

## Summary

**Current State:** Factory is incomplete stub that fails in all non-quilt3 scenarios

**The Decision:** How ambitious should the fix be?
- **Option A:** Build everything (2 weeks, full solution)
- **Option B:** Fix minimum (2 days, local-only)
- **Option C:** Refactor properly (2 weeks, clean architecture)

**Recommended Path:** Option B now (unblock tests), Option C later (if needed for deployment)

**Blocking Questions:** Answer Q1-Q4 before choosing

**Ready to Implement:** Option B can start immediately with current knowledge
