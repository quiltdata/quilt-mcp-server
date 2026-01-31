# Factory API Mismatch Analysis: quilt3.session.get_session_info() Does Not Exist

**Date:** 2026-01-31
**Investigator:** Claude Code
**Status:** Root cause identified - API mismatch between factory expectations and actual quilt3 library

---

## Executive Summary

The `QuiltOpsFactory._detect_quilt3_session()` method calls `quilt3.session.get_session_info()`, which **does not exist** in the actual quilt3 library (v6.3.1). This causes:

1. **All integration tests fail** with `AuthenticationError` even when user has valid quilt3 login
2. **Production code would fail** if it ever ran without mocks (currently all uses are in test-mocked contexts)
3. **Confusion between unit tests (which mock this non-existent method) and integration tests (which try to use real quilt3)**

## The Problem

### What the Factory Code Expects

**File:** [src/quilt_mcp/ops/factory.py:88](../../src/quilt_mcp/ops/factory.py#L88)

```python
@staticmethod
def _detect_quilt3_session() -> Optional[dict]:
    """Detect and validate quilt3 session."""
    if quilt3 is None:
        logger.debug("quilt3 library not available")
        return None

    try:
        logger.debug("Checking for quilt3 session")
        # Get session information using the method expected by tests
        session_info = quilt3.session.get_session_info()  # ← THIS METHOD DOESN'T EXIST!
        if session_info:
            logger.debug("Found valid quilt3 session")
            return session_info
        else:
            logger.debug("No quilt3 session found")
            return None

    except Exception as e:
        logger.debug(f"Error checking quilt3 session: {e}")
        return None
```

### What Actually Happens at Runtime

```bash
$ uv run python -c "import quilt3; print(quilt3.session.get_session_info())"

Traceback (most recent call last):
  File "<string>", line 1, in <module>
AttributeError: module 'quilt3.session' has no attribute 'get_session_info'. Did you mean: 'get_session'?

quilt3 version: 6.3.1
logged_in: https://nightly.quilttest.com
```

**Result:** Even though the user IS logged in (`https://nightly.quilttest.com`), the factory can't detect it because it's calling the wrong API method.

### What the Actual quilt3 API Provides

```bash
$ uv run python -c "import quilt3; print([m for m in dir(quilt3.session) if not m.startswith('_')])"

['AUTH_PATH', 'BASE_PATH', 'CREDENTIALS_PATH', 'CredentialProvider',
 'CredentialResolver', 'QuiltException', 'QuiltProvider', 'RefreshableCredentials',
 'T', 'VERSION', 'boto3', 'botocore', 'clear_session', 'create_botocore_session',
 'get_boto3_session', 'get_from_config', 'get_registry_url', 'get_session',
 'logged_in', 'login', 'login_with_token', 'logout', 'metadata', 'open_url',
 'os', 'platform', 'requests', 'stat', 'subprocess', 'sys', 'time']
```

**Key session detection methods that DO exist:**

- `quilt3.session.logged_in()` - Returns catalog URL if logged in, `None` otherwise
- `quilt3.session.get_session()` - Returns authenticated `requests.Session` object
- `quilt3.session.get_registry_url()` - Returns S3 registry URL
- `quilt3.session.get_boto3_session()` - Returns `boto3.Session` with AWS credentials

**What DOESN'T exist:**

- ❌ `quilt3.session.get_session_info()` - **This is the method the factory calls!**

### Verification of User's Real Session

```bash
$ uv run python -c "import quilt3; print('logged_in:', quilt3.session.logged_in()); print('registry_url:', quilt3.session.get_registry_url())"

logged_in: https://nightly.quilttest.com
registry_url: https://nightly-registry.quilttest.com
```

**The user HAS a valid quilt3 session**, but the factory can't detect it because it's calling a non-existent API.

---

## Why Unit Tests Pass But Integration Tests Fail

### Unit Tests: Mock the Non-Existent Method

**File:** [tests/unit/ops/test_factory.py:54](../../tests/unit/ops/test_factory.py#L54)

```python
@patch('quilt_mcp.ops.factory.quilt3')
def test_create_with_valid_quilt3_session(self, mock_quilt3):
    """Test create() with valid quilt3 session returns Quilt3_Backend."""

    # Unit tests mock the non-existent method, so they work!
    mock_session_info = {
        'registry': 's3://test-registry',
        'credentials': {'access_key': 'test', 'secret_key': 'test'},
    }
    mock_quilt3.session.get_session_info.return_value = mock_session_info  # ← Mocks non-existent API

    result = QuiltOpsFactory.create()

    from quilt_mcp.backends.quilt3_backend import Quilt3_Backend
    assert isinstance(result, Quilt3_Backend)
    mock_quilt3.session.get_session_info.assert_called_once()
```

**Why this works:** The entire `quilt3` module is mocked, so you can mock methods that don't exist. The test never touches the real quilt3 library.

### Integration Tests: Try to Use Real quilt3 (Fails)

**File:** [tests/integration/test_end_to_end_workflows.py:16](../../tests/integration/test_end_to_end_workflows.py#L16)

```python
def test_complete_package_search_workflow(self):
    """Test complete workflow: search packages -> get package info -> browse content."""
    mock_session = MagicMock()

    with patch('quilt3.logged_in', return_value=True):
        with patch('quilt3.session.get_session', return_value=mock_session):
            with patch('quilt3.session.get_registry_url', return_value='s3://test-registry'):
                quilt_ops = QuiltOpsFactory.create()  # ← FAILS HERE
```

**Why this fails:**

1. Test patches specific quilt3 methods but imports the REAL quilt3 module
2. Factory calls `quilt3.session.get_session_info()` (not mocked)
3. Real quilt3 raises `AttributeError` because method doesn't exist
4. Exception is caught by factory's try/except
5. Factory returns `None` from `_detect_quilt3_session()`
6. Factory raises `AuthenticationError`
7. Test never reaches the mocked search operations

---

## Additional Complicating Factor: Test Configuration Disables quilt3

**File:** [tests/conftest.py:136-138](../../tests/conftest.py#L136-L138)

```python
def pytest_configure(config):
    """Configure pytest and set up AWS session if needed."""
    # ...

    # Disable quilt3 session (which uses JWT credentials from Quilt catalog login)
    # This forces tests to use local AWS credentials (AWS_PROFILE or default)
    os.environ["QUILT_DISABLE_QUILT3_SESSION"] = "1"
```

**Impact:** Even if the factory API was correct, integration tests are configured to explicitly disable quilt3 session detection.

**Where this is checked:**

- [src/quilt_mcp/services/iam_auth_service.py:29](../../src/quilt_mcp/services/iam_auth_service.py#L29)
- [src/quilt_mcp/services/permission_discovery.py:81](../../src/quilt_mcp/services/permission_discovery.py#L81)

```python
disable_quilt3_session = os.getenv("QUILT_DISABLE_QUILT3_SESSION") == "1"
```

**However:** The factory (`QuiltOpsFactory._detect_quilt3_session`) does NOT check this environment variable, so it would still try to use quilt3 even when disabled (but fails due to the API mismatch anyway).

---

## Architecture Confusion: Two Different Session Detection Patterns

The codebase has TWO different patterns for detecting quilt3 sessions:

### Pattern 1: Factory (Used by QuiltOps abstraction)

**File:** [src/quilt_mcp/ops/factory.py:88](../../src/quilt_mcp/ops/factory.py#L88)

```python
session_info = quilt3.session.get_session_info()  # ← DOESN'T EXIST
```

### Pattern 2: Service Layer (Used by IAM auth and permissions)

**File:** [src/quilt_mcp/services/iam_auth_service.py:30-38](../../src/quilt_mcp/services/iam_auth_service.py#L30-L38)

```python
def _quilt3_session(self) -> Optional[boto3.Session]:
    """Return a boto3 session sourced from quilt3 when available."""
    try:
        import quilt3
    except Exception:
        return None

    disable_quilt3_session = os.getenv("QUILT_DISABLE_QUILT3_SESSION") == "1"
    try:
        if disable_quilt3_session and "unittest.mock" not in type(quilt3).__module__:
            return None
        if hasattr(quilt3, "logged_in") and quilt3.logged_in():  # ← CORRECT API
            if hasattr(quilt3, "get_boto3_session"):
                session = quilt3.get_boto3_session()  # ← CORRECT API
                if isinstance(session, boto3.Session):
                    return session
    except Exception:
        return None
    return None
```

**Key differences:**

- ✅ Service layer uses REAL quilt3 APIs: `logged_in()`, `get_boto3_session()`
- ✅ Service layer respects `QUILT_DISABLE_QUILT3_SESSION` env var
- ✅ Service layer has mock-aware behavior
- ❌ Factory uses NON-EXISTENT API: `get_session_info()`
- ❌ Factory ignores `QUILT_DISABLE_QUILT3_SESSION` env var
- ❌ Factory has no mock-aware behavior

---

## How the Bug Was Introduced

### Git History Context

Recent commits show the QuiltOps abstraction was added:

```
31bfaaa fix(permissions): lazy-initialize boto3 session in PermissionDiscoveryService
0f09b4a fix(tests): add quilt3 session mocks to fix QuiltOpsFactory tests
b3840bb refactor: split tasks.md into 4 manageable files
b1165bf refactor: split Quilt3_Backend into modular mixin architecture
```

The commit `0f09b4a` mentions "add quilt3 session mocks to fix QuiltOpsFactory tests", which suggests:

1. QuiltOpsFactory was added with incorrect API usage
2. Unit tests were mocked to make them pass
3. The mocking hid the fact that the API doesn't exist
4. Integration tests (which try to use real quilt3) now fail

### Likely Root Cause

The developer who wrote `QuiltOpsFactory._detect_quilt3_session()` either:

1. **Assumed** a `get_session_info()` method existed without checking the actual quilt3 API
2. **Designed** an ideal API and intended to implement it, but used the non-existent version
3. **Confused** different authentication patterns between service layer and factory layer

The unit tests with mocks passed, giving false confidence that the code worked.

---

## Impact Analysis

### What Works (Because of Mocking)

1. ✅ **All unit tests** (40+ in test_factory.py) - Mock the entire quilt3 module
2. ✅ **All backend unit tests** (100+) - Either mock or directly instantiate backend
3. ✅ **Service layer authentication** - Uses correct quilt3 APIs

### What Breaks (Real quilt3 Usage)

1. ❌ **Integration tests** (15+ tests across 3 files) - Try to use real quilt3
2. ❌ **E2E tests** - Call `QuiltOpsFactory.create()` without comprehensive mocks
3. ❌ **Production usage** (if any) - Would fail if code paths using factory are executed

### Current Production Risk

**File:** [src/quilt_mcp/tools/packages.py](../../src/quilt_mcp/tools/packages.py)

Two MCP tools use the factory:

- `packages_list()` - Line 668
- `package_browse()` - Line 812

```python
def packages_list(...):
    # ...
    quilt_ops = QuiltOpsFactory.create()  # ← Would fail in production!
    with suppress_stdout():
        package_infos = quilt_ops.search_packages(query="", registry=normalized_registry)
```

**Current status:** These tools would raise `AuthenticationError` in production if called, even with valid quilt3 login.

**Why not discovered yet:** These specific MCP tools may not have been tested end-to-end with real quilt3 sessions (only with mocked environments).

---

## Correct quilt3 Session Detection Pattern

Based on the working service layer code and actual quilt3 API, the correct pattern is:

```python
@staticmethod
def _detect_quilt3_session() -> Optional[dict]:
    """Detect and validate quilt3 session."""
    if quilt3 is None:
        logger.debug("quilt3 library not available")
        return None

    # Check if quilt3 sessions are disabled (test environment)
    disable_quilt3_session = os.getenv("QUILT_DISABLE_QUILT3_SESSION") == "1"
    if disable_quilt3_session:
        logger.debug("quilt3 session disabled via environment variable")
        return None

    try:
        logger.debug("Checking for quilt3 session")

        # Use ACTUAL quilt3 API: logged_in() returns catalog URL or None
        if not quilt3.session.logged_in():
            logger.debug("No quilt3 session found")
            return None

        # Get registry URL using ACTUAL API
        registry_url = quilt3.session.get_registry_url()

        # Construct session info dict
        session_info = {
            'registry': registry_url,
            'logged_in': True,
        }

        logger.debug(f"Found valid quilt3 session: {registry_url}")
        return session_info

    except Exception as e:
        logger.debug(f"Error checking quilt3 session: {e}")
        return None
```

---

## Files Requiring Investigation/Changes

### Production Code

1. **[src/quilt_mcp/ops/factory.py](../../src/quilt_mcp/ops/factory.py)** - Line 88: Fix `_detect_quilt3_session()` to use correct API
2. **[src/quilt_mcp/backends/quilt3_backend_base.py](../../src/quilt_mcp/backends/quilt3_backend_base.py)** - Lines 108-128: Check if `_validate_session_accessibility()` also uses incorrect API

### Test Code

1. **[tests/unit/ops/test_factory.py](../../tests/unit/ops/test_factory.py)** - Update mocks to match correct API
2. **[tests/integration/test_end_to_end_workflows.py](../../tests/integration/test_end_to_end_workflows.py)** - May need mock updates or env var handling
3. **[tests/integration/test_packages_integration.py](../../tests/integration/test_packages_integration.py)** - May need updates
4. **[tests/conftest.py](../../tests/conftest.py)** - Line 138: Consider if `QUILT_DISABLE_QUILT3_SESSION` should apply to factory

### Documentation

1. **[.kiro/specs/a12-quilt-ops/03-mock-session.md](03-mock-session.md)** - Contains analysis assuming `get_session_info()` exists (needs update)
2. **[.kiro/specs/a12-quilt-ops/04-migrate-package-methods.md](04-migrate-package-methods.md)** - May reference incorrect API

---

## Questions for Design Decision

### Question 1: What Should _detect_quilt3_session() Return?

The factory expects a dict with session info:

```python
session_info = QuiltOpsFactory._detect_quilt3_session()
if session_info is not None:
    return Quilt3_Backend(session_info)
```

But `Quilt3_Backend.__init__` then validates this:

```python
def __init__(self, session_config: Dict[str, Any]):
    self.session = self._validate_session(session_config)
```

**Options:**

1. Return minimal dict: `{'registry': registry_url, 'logged_in': True}`
2. Return boto3 session: `{'boto3_session': quilt3.get_boto3_session(), 'registry': registry_url}`
3. Return full session context (if we can construct it from real APIs)

**Need to check:** What does `Quilt3_Backend._validate_session()` actually require?

### Question 2: Should Factory Respect QUILT_DISABLE_QUILT3_SESSION?

The service layer checks this env var, but factory doesn't. Should it?

**Current test setup:** `conftest.py` sets `QUILT_DISABLE_QUILT3_SESSION=1` for ALL tests.

**Implications:**

- If factory respects this, ALL tests would need to unset it OR provide alternative auth
- If factory ignores this, there's inconsistency between factory and service layer
- Integration tests may expect factory to use real quilt3 (conflicting with env var)

### Question 3: Should Integration Tests Use Real quilt3 or Mocks?

**Current state:** Integration tests try to use real quilt3 but also have some mocks.

**Philosophy question:**

- **Pure integration:** Use real quilt3 session, real AWS, real S3 (slow, requires credentials)
- **Hybrid:** Use real quilt3 API but mock AWS/S3 calls (faster, less setup)
- **Mocked integration:** Mock everything but test multi-component interactions (fastest)

The test file name suggests "end-to-end" but the mocks suggest "hybrid" approach.

---

## Related Documentation

- [03-mock-session.md](03-mock-session.md) - Previous analysis assuming `get_session_info()` exists (INCORRECT)
- [04-migrate-package-methods.md](04-migrate-package-methods.md) - Package method migration (may be affected)
- Service layer authentication: [src/quilt_mcp/services/iam_auth_service.py](../../src/quilt_mcp/services/iam_auth_service.py)
- Permission discovery: [src/quilt_mcp/services/permission_discovery.py](../../src/quilt_mcp/services/permission_discovery.py)

---

## Next Steps (DO NOT IMPLEMENT YET)

1. **Verify backend initialization requirements** - What dict structure does `Quilt3_Backend.__init__` actually need?
2. **Decide on session detection strategy** - Real API calls or maintain abstraction?
3. **Decide on test philosophy** - Pure integration, hybrid, or mocked?
4. **Update factory to use correct API** - Based on decisions above
5. **Update all tests** - Unit and integration
6. **Update documentation** - Correct the incorrect assumptions in existing specs

---

## Appendix: Complete quilt3.session API Surface

From actual quilt3 v6.3.1:

**Constants:**

- `AUTH_PATH`, `BASE_PATH`, `CREDENTIALS_PATH`, `VERSION`

**Classes:**

- `CredentialProvider`, `CredentialResolver`, `QuiltProvider`, `RefreshableCredentials`
- `QuiltException`

**Session Management:**

- `login(registry_url)` - Interactive login
- `login_with_token(registry_url, token)` - Token-based login
- `logout()` - Clear session
- `clear_session()` - Clear all session data
- `logged_in()` - Returns catalog URL string or None

**Session Access:**

- `get_session()` - Returns `requests.Session` with auth
- `get_registry_url()` - Returns S3 registry URL string
- `get_boto3_session()` - Returns `boto3.Session` with AWS credentials
- `create_botocore_session()` - Returns botocore session

**Utilities:**

- `get_from_config(key)` - Get config value
- `open_url(url)` - Open URL in browser
- `metadata()` - Get session metadata

**NOT PRESENT:**

- ❌ `get_session_info()` - **This does not exist!**
