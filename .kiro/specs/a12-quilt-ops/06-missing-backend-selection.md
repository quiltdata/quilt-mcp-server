# Missing Backend Selection: The Root Architectural Problem

**Date:** 2026-01-31
**Investigator:** Claude Code
**Status:** Critical architectural gap identified

---

## Executive Summary

The **real problem** is that there's **no explicit backend selection mechanism**. The QuiltOps abstraction was designed to support multiple backends (quilt3 library + Platform GraphQL), but only `Quilt3_Backend` exists and the factory has no way to choose between backends or detect which mode to use.

**Result:** The factory is an incomplete Phase 1 stub that:
1. Only knows how to detect quilt3 sessions (using a non-existent API)
2. Has no GraphQL/Platform backend fallback
3. Has no explicit mode selection
4. Causes confusion between "should use quilt3" vs "should use GraphQL" scenarios

**This explains why:**
- Tests disable quilt3 sessions (`QUILT_DISABLE_QUILT3_SESSION=1`) - they expect a different auth mode
- The service layer has separate auth detection - it's not using the factory
- Integration tests mock everything - there's no real backend to integrate with

---

## Evidence: Phase 1 Incomplete Implementation

### Factory Comments Reveal Incomplete Design

**File:** [src/quilt_mcp/ops/factory.py:33-47](../../src/quilt_mcp/ops/factory.py#L33-L47)

```python
"""Factory for creating QuiltOps instances with appropriate backends.

This factory determines which backend to use based on available authentication:
- quilt3 sessions → Quilt3_Backend
- JWT tokens → Platform_Backend (Phase 2)

JWT token support and Platform_Backend will be added in Phase 2.
"""

class QuiltOpsFactory:
    """Factory for creating QuiltOps instances with appropriate backend.

    Phase 1 Implementation:
    - Only checks for quilt3 sessions
    - Creates Quilt3_Backend instances only
    - JWT token support will be added in Phase 2
    """
```

**Key revelations:**
- ✅ Design acknowledges TWO backends should exist: `Quilt3_Backend` and `Platform_Backend`
- ❌ Only `Quilt3_Backend` is implemented
- ❌ JWT token detection not implemented
- ❌ Platform_Backend doesn't exist

### Factory.create() is Phase 1 Stub

**File:** [src/quilt_mcp/ops/factory.py:40-71](../../src/quilt_mcp/ops/factory.py#L40-L71)

```python
def create() -> QuiltOps:
    """Create QuiltOps instance with appropriate backend.

    Phase 1 Implementation:
    - Only checks for quilt3 sessions
    - Creates Quilt3_Backend instances only
    - JWT token support will be added in Phase 2

    Returns:
        QuiltOps instance with appropriate backend

    Raises:
        AuthenticationError: If no valid authentication is found
    """
    logger.debug("Creating QuiltOps instance - Phase 1 (quilt3 only)")

    # Phase 1: Only check for quilt3 sessions
    # JWT token support will be added in Phase 2

    # Check for quilt3 session
    session_info = QuiltOpsFactory._detect_quilt3_session()
    if session_info is not None:
        logger.info("Found valid quilt3 session, creating Quilt3_Backend")
        return Quilt3_Backend()

    # No valid authentication found
    logger.warning("No valid authentication found")
    raise AuthenticationError(
        "No valid authentication found. Please provide valid quilt3 session.\n"
        "To authenticate with quilt3, run: quilt3 login\n"
        "For more information, see: https://docs.quiltdata.com/installation-and-setup"
    )
```

**What's missing:**
```python
# Phase 2 logic (NOT IMPLEMENTED):
# jwt_token = QuiltOpsFactory._detect_jwt_token()
# if jwt_token is not None:
#     logger.info("Found valid JWT token, creating Platform_Backend")
#     return Platform_Backend(jwt_token)
```

### Abstract Interface Expects Two Backends

**File:** [src/quilt_mcp/ops/quilt_ops.py:1-6](../../src/quilt_mcp/ops/quilt_ops.py#L1-L6)

```python
"""QuiltOps abstract interface for domain-driven Quilt operations.

This module defines the abstract base class that provides a backend-agnostic interface
for Quilt operations. Implementations can use either quilt3 library or Platform GraphQL
while maintaining consistent domain-driven operations for MCP tools.
"""
```

**Design intent:** Support both quilt3 AND Platform GraphQL backends interchangeably.

**Reality:** Only quilt3 backend exists.

---

## Architecture Comparison: What EXISTS vs What Was DESIGNED

### Designed Architecture (from comments)

```
                    MCP Tools
                        ↓
                  QuiltOpsFactory
                   /          \
                  /            \
        [quilt3 session?]  [JWT token?]
              ↓                   ↓
      Quilt3_Backend      Platform_Backend
              ↓                   ↓
       quilt3 library         GraphQL API
```

### Actual Implementation

```
                    MCP Tools
                        ↓
                  QuiltOpsFactory
                        ↓
              [quilt3 session ONLY]
                        ↓
                 Quilt3_Backend
                        ↓
                  quilt3 library
                        ↓
                   ❌ BROKEN (wrong API)
```

**Problems:**
1. No Platform_Backend class
2. No JWT token detection
3. No backend selection logic
4. quilt3 session detection uses wrong API
5. No fallback when quilt3 not available

---

## Why Tests Disable quilt3 Sessions

Now it makes sense why [tests/conftest.py:138](../../tests/conftest.py#L138) disables quilt3:

```python
# Disable quilt3 session (which uses JWT credentials from Quilt catalog login)
# This forces tests to use local AWS credentials (AWS_PROFILE or default)
os.environ["QUILT_DISABLE_QUILT3_SESSION"] = "1"
```

**Original intent:** Tests expect to use a DIFFERENT auth mode (AWS IAM credentials via AWS_PROFILE), not quilt3 catalog JWT credentials.

**What was supposed to happen:**
1. Test environment disables quilt3 session
2. Factory detects no quilt3 session
3. Factory falls back to JWT/IAM mode
4. Platform_Backend (or IAM-based backend) is created
5. Tests run with AWS IAM credentials

**What actually happens:**
1. Test environment disables quilt3 session
2. Factory detects no quilt3 session (also because API is wrong)
3. Factory has NO fallback → raises `AuthenticationError`
4. Tests fail

---

## Service Layer vs Factory: Two Different Strategies

The codebase has TWO authentication strategies that don't align:

### Strategy 1: Service Layer (OLD, working)

**Files:**
- [src/quilt_mcp/services/iam_auth_service.py](../../src/quilt_mcp/services/iam_auth_service.py)
- [src/quilt_mcp/context/factory.py](../../src/quilt_mcp/context/factory.py)

**Logic:**
```python
runtime_auth = get_runtime_auth()
if runtime_auth and runtime_auth.access_token:
    return JWTAuthService()  # Web client with JWT
else:
    return IAMAuthService()  # Desktop/CLI client with AWS credentials
```

**Fallback hierarchy:**
1. Check for JWT token in runtime context
2. If JWT exists → Use JWTAuthService
3. If no JWT → Use IAMAuthService
4. IAMAuthService checks: quilt3 session → AWS_PROFILE → default credentials

**Result:** Works correctly, handles multiple auth modes

### Strategy 2: QuiltOps Factory (NEW, broken)

**File:** [src/quilt_mcp/ops/factory.py](../../src/quilt_mcp/ops/factory.py)

**Logic:**
```python
session_info = QuiltOpsFactory._detect_quilt3_session()
if session_info is not None:
    return Quilt3_Backend()
else:
    raise AuthenticationError()  # ← NO FALLBACK!
```

**Fallback hierarchy:**
1. Check for quilt3 session (using wrong API)
2. If not found → **FAIL IMMEDIATELY**

**Result:** No fallback, no JWT support, no IAM support

---

## The Missing Platform_Backend

Based on the design, there should be a `Platform_Backend` class:

### Expected Location
`src/quilt_mcp/backends/platform_backend.py` (DOES NOT EXIST)

### Expected Interface
```python
class Platform_Backend(QuiltOps):
    """Backend using Platform GraphQL API with JWT authentication."""

    def __init__(self, jwt_token: str, catalog_url: str):
        """Initialize with JWT token."""
        self.jwt_token = jwt_token
        self.catalog_url = catalog_url

    def search_packages(self, query: str, registry: str) -> List[Package_Info]:
        """Search packages via GraphQL."""
        # Execute GraphQL query with JWT auth
        pass

    # ... implement all QuiltOps methods via GraphQL
```

### Why It Doesn't Exist

**Likely reasons:**
1. **Incomplete migration:** QuiltOps abstraction started but never finished
2. **Phase 1 only:** Only local quilt3 support implemented initially
3. **Web backend not needed yet:** MCP server runs locally, doesn't need Platform GraphQL yet
4. **Different auth path:** Web/cloud deployments use service layer (which works), not factory

---

## Current Backend Reality Check

### What Backends Actually Exist

```bash
$ find src/quilt_mcp/backends -name "*.py"
src/quilt_mcp/backends/quilt3_backend.py
src/quilt_mcp/backends/quilt3_backend_base.py
src/quilt_mcp/backends/quilt3_backend_buckets.py
src/quilt_mcp/backends/quilt3_backend_content.py
src/quilt_mcp/backends/quilt3_backend_packages.py
src/quilt_mcp/backends/quilt3_backend_session.py
```

**Only ONE backend family:** `Quilt3_Backend` split across 6 mixin files

**Platform_Backend:** ❌ Does not exist

**GraphQL backend:** ❌ Does not exist

**IAM-only backend:** ❌ Does not exist (IAM handled by service layer separately)

---

## Where QuiltOpsFactory is Used

### Production Code

**File:** [src/quilt_mcp/tools/packages.py](../../src/quilt_mcp/tools/packages.py)

Two MCP tools use the factory:

1. **`packages_list()`** - Line 668
   ```python
   quilt_ops = QuiltOpsFactory.create()
   with suppress_stdout():
       package_infos = quilt_ops.search_packages(query="", registry=normalized_registry)
   ```

2. **`package_browse()`** - Line 812
   ```python
   quilt_ops = QuiltOpsFactory.create()
   with suppress_stdout():
       content_infos = quilt_ops.browse_content(package_name, registry=normalized_registry, path="")
   ```

**Status:** These would fail in production with current factory implementation.

### Test Code

**Integration tests:** Try to use the factory but fail due to authentication errors.

**Unit tests:** Mock the factory extensively to make tests pass.

---

## The Fundamental Design Question

### Question: What Should QuiltOpsFactory Actually Do?

**Option 1: Full Multi-Backend Support (Original Design)**
- Detect authentication type (quilt3 session, JWT token, AWS credentials)
- Select appropriate backend (Quilt3_Backend, Platform_Backend, IAM_Backend)
- Create backend instance with correct auth
- Return QuiltOps interface

**Pros:** Clean abstraction, supports all deployment modes
**Cons:** Requires implementing Platform_Backend and IAM_Backend

**Option 2: quilt3-Only (Current Reality)**
- Only support quilt3 sessions
- Always create Quilt3_Backend
- Fail if no quilt3 session

**Pros:** Simple, focused
**Cons:** Doesn't support web/cloud deployments, fails in test environments

**Option 3: Merge with Service Layer Auth**
- Remove factory entirely
- Use existing service layer auth (IAMAuthService, JWTAuthService)
- Create backends based on service layer decisions
- Unify authentication strategy

**Pros:** Eliminates duplication, leverages working code
**Cons:** Architectural refactoring required

---

## Why Integration Tests Fail: The Complete Picture

### Test Expectation
Integration tests expect to run with **AWS IAM credentials** (AWS_PROFILE), not quilt3 catalog credentials.

### Test Configuration
```python
# tests/conftest.py
os.environ["QUILT_DISABLE_QUILT3_SESSION"] = "1"  # Disable quilt3 login
boto3.setup_default_session(profile_name=os.getenv("AWS_PROFILE"))  # Use AWS IAM
```

**Intent:** "Use AWS IAM auth, not quilt3 catalog auth"

### What Should Happen (if Platform_Backend existed)
1. Test sets `QUILT_DISABLE_QUILT3_SESSION=1`
2. Factory checks for quilt3 session → None (disabled)
3. Factory checks for JWT token → None (local test)
4. Factory falls back to IAM mode → Creates IAM_Backend
5. IAM_Backend uses AWS_PROFILE credentials
6. Test runs successfully

### What Actually Happens
1. Test sets `QUILT_DISABLE_QUILT3_SESSION=1`
2. Factory checks for quilt3 session → None (wrong API + disabled)
3. Factory has no fallback → raises `AuthenticationError`
4. Test fails before reaching any operations

### Why Tests Mock Everything
Integration tests mock quilt3 extensively because:
1. Real factory doesn't work
2. No alternative backend exists
3. Tests need to simulate backend behavior without real backend

**Result:** "Integration tests" aren't really integrating - they're unit tests with extra mocks.

---

## Service Layer Already Handles This Correctly

The service layer has working multi-auth support that the factory should emulate:

**File:** [src/quilt_mcp/context/factory.py:88-96](../../src/quilt_mcp/context/factory.py#L88-L96)

```python
def _create_auth_service(self) -> AuthService:
    """Create auth service based on runtime context."""

    # Check for JWT token (web/cloud mode)
    runtime_auth = get_runtime_auth()
    if runtime_auth and runtime_auth.access_token:
        return JWTAuthService()

    # Check if JWT mode is required
    if get_jwt_mode_enabled():
        raise ServiceInitializationError("AuthService", "JWT authentication required but missing.")

    # Fallback to IAM (local/desktop mode)
    return IAMAuthService()
```

**IAMAuthService fallback chain:**
1. Check for quilt3 session (if not disabled)
2. Check for AWS_PROFILE
3. Check for default AWS credentials
4. Fail only if ALL methods unavailable

**This is the pattern QuiltOpsFactory should follow.**

---

## Architectural Solutions

### Solution 1: Implement Missing Backends

**Create Platform_Backend:**
```python
# src/quilt_mcp/backends/platform_backend.py
class Platform_Backend(QuiltOps):
    """Backend using Platform GraphQL with JWT auth."""
    def __init__(self, jwt_token: str, catalog_url: str):
        self.jwt_token = jwt_token
        self.catalog_url = catalog_url
    # Implement all QuiltOps methods via GraphQL
```

**Create IAM_Backend:**
```python
# src/quilt_mcp/backends/iam_backend.py
class IAM_Backend(QuiltOps):
    """Backend using AWS IAM credentials without quilt3."""
    def __init__(self, boto3_session: boto3.Session, registry: str):
        self.session = boto3_session
        self.registry = registry
    # Implement all QuiltOps methods via direct S3/API calls
```

**Update factory with fallback:**
```python
def create() -> QuiltOps:
    # Try quilt3 session
    if session_info := _detect_quilt3_session():
        return Quilt3_Backend()

    # Try JWT token
    if jwt_token := _detect_jwt_token():
        return Platform_Backend(jwt_token, catalog_url)

    # Try AWS IAM
    if boto3_session := _detect_aws_credentials():
        return IAM_Backend(boto3_session, registry)

    raise AuthenticationError("No valid authentication found")
```

**Pros:** Complete, follows original design
**Cons:** Significant implementation work

### Solution 2: Simplify to quilt3-Only

**Accept Phase 1 limitations:**
- Only support quilt3 sessions
- Fix the API mismatch
- Document that factory is quilt3-only
- Use service layer for other auth modes

**Update tests:**
- Remove `QUILT_DISABLE_QUILT3_SESSION` for tests using factory
- Use real quilt3 session in integration tests
- Keep service layer for IAM/JWT scenarios

**Pros:** Minimal changes, clear scope
**Cons:** Factory remains limited, doesn't support all modes

### Solution 3: Merge with Service Layer (Recommended)

**Eliminate QuiltOpsFactory:**
- Remove factory class entirely
- Use service layer auth (IAMAuthService, JWTAuthService)
- Create backends based on service layer decisions

**Refactor backend creation:**
```python
# In service layer or context factory
def create_quilt_ops() -> QuiltOps:
    auth_service = RequestContextFactory._create_auth_service()

    if isinstance(auth_service, JWTAuthService):
        return Platform_Backend(auth_service.get_token(), catalog_url)
    elif isinstance(auth_service, IAMAuthService):
        session = auth_service.get_boto3_session()
        if auth_service.has_quilt3_session():
            return Quilt3_Backend(session)
        else:
            return IAM_Backend(session, registry)
```

**Pros:** Unifies auth strategy, leverages working code, eliminates duplication
**Cons:** Requires refactoring, changes architecture

---

## Critical Files for Backend Selection

### Production Code - Factory
1. **[src/quilt_mcp/ops/factory.py](../../src/quilt_mcp/ops/factory.py)** - Incomplete factory, Phase 1 stub
2. **[src/quilt_mcp/ops/quilt_ops.py](../../src/quilt_mcp/ops/quilt_ops.py)** - Abstract interface (complete)

### Production Code - Backends
1. **[src/quilt_mcp/backends/quilt3_backend.py](../../src/quilt_mcp/backends/quilt3_backend.py)** - Only backend (exists)
2. **[src/quilt_mcp/backends/platform_backend.py](../../src/quilt_mcp/backends/platform_backend.py)** - GraphQL backend (MISSING)
3. **[src/quilt_mcp/backends/iam_backend.py](../../src/quilt_mcp/backends/iam_backend.py)** - IAM-only backend (MISSING)

### Production Code - Service Layer (Working Multi-Auth)
1. **[src/quilt_mcp/context/factory.py](../../src/quilt_mcp/context/factory.py)** - Context factory with working auth selection
2. **[src/quilt_mcp/services/iam_auth_service.py](../../src/quilt_mcp/services/iam_auth_service.py)** - IAM auth with fallbacks
3. **[src/quilt_mcp/services/jwt_auth_service.py](../../src/quilt_mcp/services/jwt_auth_service.py)** - JWT auth

### Test Configuration
1. **[tests/conftest.py](../../tests/conftest.py)** - Sets `QUILT_DISABLE_QUILT3_SESSION=1` expecting IAM fallback

### MCP Tools Using Factory
1. **[src/quilt_mcp/tools/packages.py](../../src/quilt_mcp/tools/packages.py)** - Lines 668, 812

---

## Recommendation

**Short-term (fix tests):**
1. Fix quilt3 API mismatch in factory (use correct `logged_in()` and `get_registry_url()`)
2. Add `QUILT_DISABLE_QUILT3_SESSION` check to factory
3. Update integration tests to either:
   - Use real quilt3 sessions (remove disable flag), OR
   - Use service layer directly (bypass factory)

**Long-term (complete architecture):**
1. Implement Platform_Backend for GraphQL/JWT mode
2. Implement IAM_Backend for AWS-only mode
3. Update factory with complete fallback chain
4. Consider merging factory logic into service layer for unified auth

**Alternative (simplify):**
1. Document factory as quilt3-only
2. Remove "Phase 2" promises from comments
3. Use service layer for non-quilt3 scenarios
4. Keep factory focused and simple

---

## Summary

The root problem is **missing backend selection infrastructure**:

1. ❌ **No Platform_Backend** - GraphQL/JWT backend doesn't exist
2. ❌ **No IAM_Backend** - AWS-only backend doesn't exist
3. ❌ **No fallback logic** - Factory fails if quilt3 not available
4. ❌ **Wrong API calls** - Even quilt3 detection is broken
5. ✅ **Service layer works** - But factory doesn't use it

**Tests fail because:** They expect IAM fallback that doesn't exist, so they disable quilt3 and get `AuthenticationError`.

**The fix requires:** Either implementing missing backends OR simplifying factory to quilt3-only with proper API calls.
