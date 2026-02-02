# Platform Backend Local Authentication Bridge

**Status**: 📋 Specification

**Branch**: TBD (new feature)

**Related**: [README.md](./README.md), [02-graphql.md](./02-graphql.md)

---

## Problem Statement

The Platform backend (`platform_backend.py`) cannot currently run as a local MCP server because:

1. **JWT Requirement**: Platform backend requires JWT tokens with specific claims (`catalog_token`, `catalog_url`, `registry_url`)
2. **Transport Mismatch**: Platform backend is designed for HTTP transport (multitenant mode), not stdio
3. **No Credential Bridge**: No mechanism exists to convert quilt3 session credentials to Platform-compatible JWTs
4. **Mode Exclusivity**: `QUILT_MULTITENANT_MODE` makes Quilt3 and Platform backends mutually exclusive

### Current Architecture

```
User Environment
├── quilt3 session (~/.quilt/ or quilt3.session)
│   └── catalog_token (Bearer token for GraphQL API)
└── MCP Server
    ├── Quilt3_Backend (stdio transport, IAM auth)
    │   └── Uses quilt3.session directly
    └── Platform_Backend (HTTP transport, JWT auth)
        └── Requires JWT with catalog_token claim
        └── ❌ Cannot access quilt3 session
```

### Use Cases

**Desktop/CLI Users**: Want to test GraphQL backend locally without deploying multitenant infrastructure

**Development**: Need to debug Platform backend behavior using local credentials

**Feature Parity**: Platform backend should work everywhere Quilt3 backend works

---

## Proposed Solution

Create a **credential bridge** that extracts catalog tokens from quilt3 session and generates JWTs for Platform backend.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Local Development Mode                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User runs: export QUILT_BACKEND=platform-local             │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Credential Bridge (new)                              │  │
│  │ ─────────────────────────────────────────────────────│  │
│  │ 1. Check quilt3.logged_in()                          │  │
│  │ 2. Extract catalog_token from quilt3.session         │  │
│  │ 3. Get catalog_url from quilt3 config                │  │
│  │ 4. Generate JWT with required claims                 │  │
│  │ 5. Inject JWT into RuntimeAuthState                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Platform_Backend                                     │  │
│  │ ─────────────────────────────────────────────────────│  │
│  │ - Uses JWT from RuntimeAuthState                     │  │
│  │ - Runs GraphQL queries with catalog_token            │  │
│  │ - stdio transport (same as Quilt3_Backend)           │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### New Backend Mode: `platform-local`

Extend `config.py` to support a third backend type:

| Mode | Backend | Transport | Auth Source |
|------|---------|-----------|-------------|
| `quilt3` | Quilt3_Backend | stdio | quilt3.session (IAM) |
| `graphql` | Platform_Backend | HTTP | JWT from HTTP request |
| **`platform-local`** (new) | Platform_Backend | stdio | JWT from quilt3.session |

---

## Implementation Design

### Phase 1: Quilt3 Session Extraction

**New Module**: `src/quilt_mcp/auth/quilt3_session_extractor.py`

```python
"""Extract authentication credentials from quilt3 session."""

import quilt3
from typing import Optional, Tuple
from urllib.parse import urlparse


class Quilt3SessionError(Exception):
    """Raised when quilt3 session is not available or invalid."""
    pass


def extract_catalog_token() -> str:
    """
    Extract the catalog bearer token from quilt3 session.

    Returns:
        Bearer token string (without "Bearer " prefix)

    Raises:
        Quilt3SessionError: If not logged in or token unavailable
    """
    if not hasattr(quilt3, "logged_in") or not quilt3.logged_in():
        raise Quilt3SessionError(
            "Not logged in to quilt3. Run 'quilt3 login' first."
        )

    # Get the active requests.Session from quilt3
    session = quilt3.session.get_session()

    # Extract Authorization header
    auth_header = session.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise Quilt3SessionError(
            "quilt3 session does not have a valid Bearer token"
        )

    # Return token without "Bearer " prefix
    return auth_header.replace("Bearer ", "", 1)


def extract_catalog_url() -> str:
    """
    Extract the catalog URL from quilt3 configuration.

    Returns:
        Catalog URL (e.g., "https://catalog.example.com")

    Raises:
        Quilt3SessionError: If catalog URL not configured
    """
    # Try to get catalog URL from quilt3's internal config
    # This may vary depending on quilt3 version
    try:
        if hasattr(quilt3, "config") and hasattr(quilt3.config, "get_catalog_url"):
            catalog_url = quilt3.config.get_catalog_url()
        else:
            # Fallback: inspect session base URL
            session = quilt3.session.get_session()
            # The session should have a base_url or similar attribute
            # This is implementation-specific
            raise NotImplementedError(
                "Cannot extract catalog_url from this quilt3 version"
            )

        if not catalog_url:
            raise Quilt3SessionError("Catalog URL not configured in quilt3")

        return catalog_url
    except Exception as e:
        raise Quilt3SessionError(f"Failed to extract catalog URL: {e}")


def derive_registry_url(catalog_url: str) -> str:
    """
    Derive the registry URL from a catalog URL.

    Platform convention: replace "open" subdomain with "registry"

    Args:
        catalog_url: e.g., "https://open.quiltdata.com"

    Returns:
        Registry URL: e.g., "https://registry.quiltdata.com"
    """
    parsed = urlparse(catalog_url)

    # Handle common patterns
    if parsed.hostname and parsed.hostname.startswith("open."):
        # Replace "open" with "registry"
        registry_hostname = parsed.hostname.replace("open.", "registry.", 1)
    else:
        # Fallback: assume same domain with /api path
        registry_hostname = parsed.hostname

    registry_url = f"{parsed.scheme}://{registry_hostname}"
    if parsed.port:
        registry_url += f":{parsed.port}"

    return registry_url


def get_quilt3_credentials() -> Tuple[str, str, str]:
    """
    Extract all required credentials from quilt3 session.

    Returns:
        Tuple of (catalog_token, catalog_url, registry_url)

    Raises:
        Quilt3SessionError: If any credential is unavailable
    """
    catalog_token = extract_catalog_token()
    catalog_url = extract_catalog_url()
    registry_url = derive_registry_url(catalog_url)

    return catalog_token, catalog_url, registry_url
```

### Phase 2: JWT Generation

**New Module**: `src/quilt_mcp/auth/local_jwt_generator.py`

```python
"""Generate JWTs for local Platform backend usage."""

import os
import time
import jwt
from typing import Dict, Optional


class LocalJWTError(Exception):
    """Raised when JWT generation fails."""
    pass


def generate_local_jwt(
    catalog_token: str,
    catalog_url: str,
    registry_url: str,
    secret_key: Optional[str] = None,
    expiration_seconds: int = 3600,
) -> str:
    """
    Generate a JWT for local Platform backend usage.

    Args:
        catalog_token: Bearer token from quilt3 session
        catalog_url: Catalog URL (e.g., "https://open.quiltdata.com")
        registry_url: Registry URL (e.g., "https://registry.quiltdata.com")
        secret_key: JWT signing key (defaults to MCP_JWT_SECRET env var)
        expiration_seconds: JWT expiration time (default: 1 hour)

    Returns:
        Encoded JWT string

    Raises:
        LocalJWTError: If secret key is not available
    """
    if secret_key is None:
        secret_key = os.getenv("MCP_JWT_SECRET")

    if not secret_key:
        raise LocalJWTError(
            "JWT secret key required. Set MCP_JWT_SECRET environment variable."
        )

    # Build JWT claims matching Platform backend expectations
    now = int(time.time())
    claims: Dict[str, any] = {
        # Platform backend required claims
        "catalog_token": catalog_token,
        "catalog_url": catalog_url,
        "registry_url": registry_url,

        # Standard JWT claims
        "sub": "local-user",
        "iss": "quilt-mcp-local",
        "aud": "quilt-mcp-server",
        "iat": now,
        "exp": now + expiration_seconds,

        # Metadata
        "mode": "platform-local",
    }

    # Encode JWT
    try:
        token = jwt.encode(claims, secret_key, algorithm="HS256")
        return token
    except Exception as e:
        raise LocalJWTError(f"Failed to encode JWT: {e}")


def validate_local_jwt(token: str, secret_key: Optional[str] = None) -> Dict:
    """
    Validate and decode a local JWT.

    Args:
        token: JWT string
        secret_key: JWT signing key (defaults to MCP_JWT_SECRET env var)

    Returns:
        Decoded JWT claims

    Raises:
        LocalJWTError: If validation fails
    """
    if secret_key is None:
        secret_key = os.getenv("MCP_JWT_SECRET")

    if not secret_key:
        raise LocalJWTError(
            "JWT secret key required. Set MCP_JWT_SECRET environment variable."
        )

    try:
        claims = jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
            audience="quilt-mcp-server",
        )
        return claims
    except jwt.InvalidTokenError as e:
        raise LocalJWTError(f"JWT validation failed: {e}")
```

### Phase 3: Backend Factory Integration

**Modify**: `src/quilt_mcp/ops/factory.py`

```python
# Add new backend mode
def _create_backend(self) -> QuiltOps:
    """Create the appropriate backend based on mode configuration."""
    mode_config = get_mode_config()

    if mode_config.backend_type == "quilt3":
        return Quilt3_Backend()

    elif mode_config.backend_type == "graphql":
        return Platform_Backend()

    elif mode_config.backend_type == "platform-local":
        # NEW: Local Platform backend with quilt3 credentials
        return self._create_platform_local_backend()

    else:
        raise ServiceInitializationError(
            "Backend",
            f"Unknown backend type: {mode_config.backend_type}"
        )


def _create_platform_local_backend(self) -> Platform_Backend:
    """
    Create Platform backend using credentials from quilt3 session.

    Extracts catalog token from quilt3, generates a JWT, and injects
    it into the runtime context for Platform backend.

    Returns:
        Initialized Platform_Backend instance

    Raises:
        ServiceInitializationError: If credential extraction fails
    """
    from quilt_mcp.auth.quilt3_session_extractor import (
        get_quilt3_credentials,
        Quilt3SessionError,
    )
    from quilt_mcp.auth.local_jwt_generator import (
        generate_local_jwt,
        LocalJWTError,
    )
    from quilt_mcp.runtime_context import set_runtime_auth, RuntimeAuthState

    try:
        # Extract credentials from quilt3 session
        catalog_token, catalog_url, registry_url = get_quilt3_credentials()

        # Generate JWT
        jwt_token = generate_local_jwt(
            catalog_token=catalog_token,
            catalog_url=catalog_url,
            registry_url=registry_url,
        )

        # Inject JWT into runtime context
        # Platform backend will read this during initialization
        set_runtime_auth(RuntimeAuthState(access_token=jwt_token))

        # Create Platform backend (will use JWT from runtime context)
        return Platform_Backend()

    except Quilt3SessionError as e:
        raise ServiceInitializationError(
            "PlatformLocalBackend",
            f"Failed to extract quilt3 credentials: {e}. "
            "Run 'quilt3 login' to authenticate."
        )
    except LocalJWTError as e:
        raise ServiceInitializationError(
            "PlatformLocalBackend",
            f"Failed to generate JWT: {e}. "
            "Set MCP_JWT_SECRET environment variable."
        )
```

### Phase 4: Configuration Updates

**Modify**: `src/quilt_mcp/config.py`

```python
class BackendType(str, Enum):
    """Available backend types."""
    QUILT3 = "quilt3"
    GRAPHQL = "graphql"
    PLATFORM_LOCAL = "platform-local"  # NEW


class ModeConfig(BaseModel):
    """Configuration for backend selection and behavior."""

    backend_type: BackendType = Field(
        default=BackendType.QUILT3,
        description="Backend implementation to use"
    )

    # ... rest of config

    @classmethod
    def from_env(cls) -> "ModeConfig":
        """Create config from environment variables."""
        # Check explicit backend override
        backend_env = os.getenv("QUILT_BACKEND", "").lower()
        if backend_env == "platform-local":
            return cls(
                backend_type=BackendType.PLATFORM_LOCAL,
                transport_type=TransportType.STDIO,
                requires_jwt=True,
            )

        # Existing logic for quilt3/graphql modes
        multitenant = os.getenv("QUILT_MULTITENANT_MODE", "false").lower() == "true"
        if multitenant:
            return cls(
                backend_type=BackendType.GRAPHQL,
                transport_type=TransportType.HTTP,
                requires_jwt=True,
            )
        else:
            return cls(
                backend_type=BackendType.QUILT3,
                transport_type=TransportType.STDIO,
                requires_jwt=False,
            )
```

---

## Usage Examples

### Setup: Generate JWT Secret

```bash
# Generate a random secret for local JWT signing
export MCP_JWT_SECRET=$(openssl rand -base64 32)

# Optionally save to shell profile
echo "export MCP_JWT_SECRET='$MCP_JWT_SECRET'" >> ~/.bashrc
```

### Usage: Run Platform Backend Locally

```bash
# 1. Ensure logged in to quilt3
quilt3 login

# 2. Set backend to platform-local mode
export QUILT_BACKEND=platform-local

# 3. Start MCP server (stdio mode)
uv run python -m quilt_mcp

# Or use MCP Inspector
make run-inspector
```

### Testing: Compare Backends

```bash
# Test with Quilt3 backend (default)
export QUILT_BACKEND=quilt3
uv run python -m quilt_mcp

# Test with Platform backend (local mode)
export QUILT_BACKEND=platform-local
uv run python -m quilt_mcp

# Both should return identical results for the same operations
```

### Configuration Matrix

| Environment Variable | Backend | Transport | Auth Source | Use Case |
|---------------------|---------|-----------|-------------|----------|
| `QUILT_BACKEND=quilt3` (default) | Quilt3_Backend | stdio | quilt3.session (IAM) | Standard local development |
| `QUILT_BACKEND=platform-local` | Platform_Backend | stdio | JWT from quilt3.session | Test GraphQL backend locally |
| `QUILT_MULTITENANT_MODE=true` | Platform_Backend | HTTP | JWT from HTTP request | Production/multitenant |

---

## Testing Strategy

### Unit Tests

**New Test File**: `tests/unit/auth/test_quilt3_session_extractor.py`

```python
"""Tests for quilt3 session credential extraction."""

import pytest
from unittest.mock import Mock, patch
from quilt_mcp.auth.quilt3_session_extractor import (
    extract_catalog_token,
    extract_catalog_url,
    derive_registry_url,
    get_quilt3_credentials,
    Quilt3SessionError,
)


def test_extract_catalog_token_success():
    """Should extract Bearer token from quilt3 session."""
    mock_session = Mock()
    mock_session.headers = {"Authorization": "Bearer test-token-123"}

    with patch("quilt3.logged_in", return_value=True):
        with patch("quilt3.session.get_session", return_value=mock_session):
            token = extract_catalog_token()
            assert token == "test-token-123"


def test_extract_catalog_token_not_logged_in():
    """Should raise error if not logged in."""
    with patch("quilt3.logged_in", return_value=False):
        with pytest.raises(Quilt3SessionError, match="Not logged in"):
            extract_catalog_token()


def test_derive_registry_url():
    """Should convert catalog URL to registry URL."""
    assert derive_registry_url("https://open.quiltdata.com") == \
        "https://registry.quiltdata.com"

    assert derive_registry_url("https://open.example.com:8080") == \
        "https://registry.example.com:8080"


def test_get_quilt3_credentials_integration():
    """Should extract all credentials together."""
    mock_session = Mock()
    mock_session.headers = {"Authorization": "Bearer token-xyz"}

    with patch("quilt3.logged_in", return_value=True):
        with patch("quilt3.session.get_session", return_value=mock_session):
            with patch("quilt3.config.get_catalog_url", return_value="https://open.test.com"):
                token, catalog_url, registry_url = get_quilt3_credentials()

                assert token == "token-xyz"
                assert catalog_url == "https://open.test.com"
                assert registry_url == "https://registry.test.com"
```

**New Test File**: `tests/unit/auth/test_local_jwt_generator.py`

```python
"""Tests for local JWT generation."""

import jwt
import time
import pytest
from unittest.mock import patch
from quilt_mcp.auth.local_jwt_generator import (
    generate_local_jwt,
    validate_local_jwt,
    LocalJWTError,
)


def test_generate_local_jwt_success():
    """Should generate valid JWT with required claims."""
    token = generate_local_jwt(
        catalog_token="test-token",
        catalog_url="https://open.example.com",
        registry_url="https://registry.example.com",
        secret_key="test-secret",
    )

    # Decode without verification to inspect claims
    claims = jwt.decode(token, options={"verify_signature": False})

    assert claims["catalog_token"] == "test-token"
    assert claims["catalog_url"] == "https://open.example.com"
    assert claims["registry_url"] == "https://registry.example.com"
    assert claims["sub"] == "local-user"
    assert claims["iss"] == "quilt-mcp-local"
    assert claims["aud"] == "quilt-mcp-server"
    assert "exp" in claims
    assert "iat" in claims


def test_generate_local_jwt_missing_secret():
    """Should raise error if secret key not provided."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(LocalJWTError, match="secret key required"):
            generate_local_jwt(
                catalog_token="token",
                catalog_url="url",
                registry_url="url",
            )


def test_validate_local_jwt_success():
    """Should validate and decode JWT correctly."""
    secret = "test-secret"
    token = generate_local_jwt(
        catalog_token="test-token",
        catalog_url="https://open.example.com",
        registry_url="https://registry.example.com",
        secret_key=secret,
    )

    claims = validate_local_jwt(token, secret_key=secret)

    assert claims["catalog_token"] == "test-token"
    assert claims["catalog_url"] == "https://open.example.com"


def test_validate_local_jwt_expired():
    """Should reject expired JWT."""
    secret = "test-secret"
    token = generate_local_jwt(
        catalog_token="test-token",
        catalog_url="https://open.example.com",
        registry_url="https://registry.example.com",
        secret_key=secret,
        expiration_seconds=-10,  # Already expired
    )

    with pytest.raises(LocalJWTError, match="validation failed"):
        validate_local_jwt(token, secret_key=secret)
```

### Integration Tests

**New Test File**: `tests/integration/test_platform_local_backend.py`

```python
"""Integration tests for platform-local backend mode."""

import os
import pytest
from unittest.mock import patch, Mock
from quilt_mcp.ops.factory import QuiltOpsFactory
from quilt_mcp.backends.platform_backend import Platform_Backend


@pytest.mark.integration
def test_platform_local_backend_initialization():
    """Should initialize Platform backend using quilt3 credentials."""
    # Mock quilt3 session
    mock_session = Mock()
    mock_session.headers = {"Authorization": "Bearer test-token"}

    with patch("quilt3.logged_in", return_value=True):
        with patch("quilt3.session.get_session", return_value=mock_session):
            with patch("quilt3.config.get_catalog_url", return_value="https://open.test.com"):
                # Set environment for platform-local mode
                with patch.dict(os.environ, {
                    "QUILT_BACKEND": "platform-local",
                    "MCP_JWT_SECRET": "test-secret",
                }):
                    factory = QuiltOpsFactory()
                    backend = factory.create_backend()

                    # Should create Platform backend
                    assert isinstance(backend, Platform_Backend)

                    # Should have JWT in runtime context
                    from quilt_mcp.runtime_context import get_runtime_auth
                    auth = get_runtime_auth()
                    assert auth is not None
                    assert auth.access_token is not None


@pytest.mark.integration
def test_platform_local_backend_not_logged_in():
    """Should fail gracefully if not logged in to quilt3."""
    with patch("quilt3.logged_in", return_value=False):
        with patch.dict(os.environ, {
            "QUILT_BACKEND": "platform-local",
            "MCP_JWT_SECRET": "test-secret",
        }):
            factory = QuiltOpsFactory()

            with pytest.raises(Exception, match="Not logged in"):
                factory.create_backend()
```

### End-to-End Tests

**New Test File**: `tests/e2e/test_platform_local_mode.py`

```python
"""E2E tests for platform-local backend mode."""

import os
import pytest
from unittest.mock import patch


@pytest.mark.e2e
@pytest.mark.skipif(
    not os.getenv("QUILT_E2E_TESTS"),
    reason="E2E tests require QUILT_E2E_TESTS=1"
)
def test_platform_local_package_search():
    """
    E2E test: Search packages using platform-local backend.

    Prerequisites:
    - User must be logged in via 'quilt3 login'
    - MCP_JWT_SECRET must be set
    """
    from quilt_mcp.main import run_mcp_server

    # Run in platform-local mode
    with patch.dict(os.environ, {"QUILT_BACKEND": "platform-local"}):
        # This would start the MCP server and execute a package search
        # Full implementation would use MCP client to send requests
        pass  # TODO: Implement with MCP test client
```

---

## Migration and Compatibility

### Backward Compatibility

**No Breaking Changes**:
- Existing `quilt3` and `graphql` modes unchanged
- Default behavior remains `quilt3` backend
- New mode is opt-in via `QUILT_BACKEND=platform-local`

### Feature Detection

Code can detect active backend mode:

```python
from quilt_mcp.config import get_mode_config

mode = get_mode_config()
if mode.backend_type == "platform-local":
    # Using Platform backend with local credentials
    print("Testing GraphQL backend locally")
```

### Deprecation Path

None required. This is a new feature with no deprecations.

---

## Security Considerations

### JWT Secret Management

**Requirement**: `MCP_JWT_SECRET` must be set for platform-local mode

**Recommendations**:
1. Generate unique secret per user: `openssl rand -base64 32`
2. Store in user profile (`.bashrc`, `.zshrc`)
3. Never commit to version control
4. Use different secrets for dev/staging/prod

### Token Expiration

**Default**: 1 hour expiration for local JWTs

**Rationale**:
- Short-lived reduces risk if token leaked
- Local mode doesn't need long-lived tokens
- Can be regenerated on each server restart

### Credential Scope

**Local JWTs**:
- Only valid for local MCP server process
- Signed with user's local secret
- Cannot be used for multitenant deployments

**Security Boundary**:
- `platform-local` JWTs use local secret (HS256)
- Multitenant JWTs use SSM-backed secret (RS256 or HS256)
- Different signature verification paths

---

## Performance Considerations

### Initialization Overhead

**Platform-local mode adds**:
1. quilt3 session inspection: ~1ms
2. JWT generation: ~1ms
3. Runtime context injection: <1ms

**Total**: <5ms overhead during backend initialization

### Runtime Performance

**No difference** once initialized:
- Platform backend executes same GraphQL queries
- Network latency dominates (100-500ms per query)
- JWT overhead negligible compared to network

---

## Documentation Updates

### User Documentation

**New Section**: `docs/backends.md`

```markdown
## Backend Modes

Quilt MCP Server supports three backend modes:

### 1. Quilt3 Backend (Default)
- **Environment**: `QUILT_BACKEND=quilt3` (default)
- **Transport**: stdio
- **Authentication**: quilt3 session (IAM)
- **Use Case**: Standard local development

### 2. Platform Backend (Local)
- **Environment**: `QUILT_BACKEND=platform-local`
- **Transport**: stdio
- **Authentication**: JWT generated from quilt3 session
- **Use Case**: Test GraphQL backend locally

Prerequisites:
```bash
# 1. Login to quilt3
quilt3 login

# 2. Set JWT secret (one-time)
export MCP_JWT_SECRET=$(openssl rand -base64 32)
echo "export MCP_JWT_SECRET='$MCP_JWT_SECRET'" >> ~/.bashrc

# 3. Start server
export QUILT_BACKEND=platform-local
uv run python -m quilt_mcp
```

### 3. Platform Backend (Multitenant)
- **Environment**: `QUILT_MULTITENANT_MODE=true`
- **Transport**: HTTP
- **Authentication**: JWT from HTTP request
- **Use Case**: Production deployments
```

### CLAUDE.md Updates

Add to project instructions:

```markdown
### Platform Backend Local Mode

The Platform backend can now run locally using credentials from quilt3:

```bash
# Setup (one-time)
quilt3 login
export MCP_JWT_SECRET=$(openssl rand -base64 32)

# Run Platform backend locally
export QUILT_BACKEND=platform-local
make run
```

This is useful for testing GraphQL backend behavior without deploying multitenant infrastructure.
```

---

## Implementation Checklist

### Phase 1: Core Infrastructure ⏳ Not Started

- [ ] Create `auth/` directory under `src/quilt_mcp/`
- [ ] Implement `quilt3_session_extractor.py`
  - [ ] `extract_catalog_token()`
  - [ ] `extract_catalog_url()`
  - [ ] `derive_registry_url()`
  - [ ] `get_quilt3_credentials()`
- [ ] Implement `local_jwt_generator.py`
  - [ ] `generate_local_jwt()`
  - [ ] `validate_local_jwt()`
- [ ] Add unit tests for extractor
- [ ] Add unit tests for JWT generator

### Phase 2: Backend Integration ⏳ Not Started

- [ ] Add `PLATFORM_LOCAL` to `BackendType` enum in `config.py`
- [ ] Update `ModeConfig.from_env()` to handle `QUILT_BACKEND=platform-local`
- [ ] Implement `_create_platform_local_backend()` in `factory.py`
- [ ] Add integration tests for backend initialization

### Phase 3: Testing ⏳ Not Started

- [ ] Add integration test: `test_platform_local_backend.py`
- [ ] Add E2E test: `test_platform_local_mode.py`
- [ ] Test against real Quilt Platform deployment
- [ ] Verify package operations work identically to Quilt3 backend

### Phase 4: Documentation ⏳ Not Started

- [ ] Create `docs/backends.md` with mode comparison
- [ ] Update README with platform-local setup instructions
- [ ] Add troubleshooting section for common issues
- [ ] Update CLAUDE.md with new commands

### Phase 5: Polish ⏳ Not Started

- [ ] Add helpful error messages for missing prerequisites
- [ ] Add CLI flag to show current backend mode
- [ ] Add validation that checks quilt3 version compatibility
- [ ] Add logging for credential extraction steps

---

## Open Questions

1. **Quilt3 API Stability**: Does quilt3 library expose a stable API for extracting catalog URL and session token?
   - **Investigation needed**: Test with multiple quilt3 versions
   - **Fallback**: Document required quilt3 version range

2. **JWT Secret Management**: Should we provide a helper command to generate and store JWT secret?
   - **Option A**: Add `quilt-mcp init` command that generates secret
   - **Option B**: Document manual process only
   - **Recommendation**: Start with Option B, add Option A if users request it

3. **Transport Override**: Should platform-local support both stdio and HTTP?
   - **Current**: Only stdio (to match Quilt3 backend)
   - **Future**: Could support HTTP for testing multitenant infrastructure locally
   - **Recommendation**: Start with stdio only, add HTTP if needed

4. **Error Handling**: What should happen if JWT expires during long-running operations?
   - **Current**: 1-hour expiration, no refresh
   - **Options**:
     - Auto-regenerate JWT on expiration
     - Require server restart
     - Add refresh token flow
   - **Recommendation**: Start with require restart, add auto-regenerate if needed

---

## Success Criteria

### Must Have (MVP)

- [ ] Platform backend runs locally with quilt3 credentials
- [ ] Package search returns identical results to Quilt3 backend
- [ ] Package creation/update works end-to-end
- [ ] Clear error messages when prerequisites missing
- [ ] Unit test coverage >90%
- [ ] Basic integration tests pass

### Should Have

- [ ] E2E tests with real Platform deployment
- [ ] Complete user documentation
- [ ] Troubleshooting guide
- [ ] Performance benchmarks vs Quilt3 backend

### Nice to Have

- [ ] Automatic JWT refresh on expiration
- [ ] CLI tool to validate setup (`quilt-mcp doctor`)
- [ ] MCP Inspector presets for platform-local mode
- [ ] Comparison mode (run same query on both backends)

---

## References

### Related Code

- [platform_backend.py](../../src/quilt_mcp/backends/platform_backend.py) - Platform backend implementation
- [quilt3_backend.py](../../src/quilt_mcp/backends/quilt3_backend.py) - Quilt3 backend implementation
- [config.py](../../src/quilt_mcp/config.py) - Mode configuration
- [factory.py](../../src/quilt_mcp/ops/factory.py) - Backend factory
- [jwt_auth_service.py](../../src/quilt_mcp/services/jwt_auth_service.py) - JWT authentication
- [iam_auth_service.py](../../src/quilt_mcp/services/iam_auth_service.py) - IAM authentication

### Related Specifications

- [README.md](./README.md) - Platform backend overview
- [02-graphql.md](./02-graphql.md) - GraphQL API reference
- [09-quick-start-multitenant.md](./09-quick-start-multitenant.md) - Multitenant testing
- [10-jwt-helpers-integration.md](./10-jwt-helpers-integration.md) - JWT utilities

### External Documentation

- [quilt3 Python API](https://docs.quiltdata.com/api-reference/api) - Quilt3 library reference
- [PyJWT Documentation](https://pyjwt.readthedocs.io/) - JWT encoding/decoding
- [MCP Protocol](https://modelcontextprotocol.io/) - Model Context Protocol spec

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-02 | Claude | Initial specification |
