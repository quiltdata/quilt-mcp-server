# JWT to AWS Credentials Exchange - Architecture Issue

**Status:** 🔴 **CRITICAL ARCHITECTURE FLAW IDENTIFIED**
**Date:** 2026-02-04

## Problem: Backwards Authentication Flow

The current platform backend testing configuration is **completely backwards**. We're disabling JWT authentication to get AWS access, when we should be **using JWT authentication to GET AWS credentials**.

### Current (WRONG) Approach

From [05-platform-backend-fix.md](./05-platform-backend-fix.md):

```python
# tests/conftest.py - platform backend fixture
if mode == "platform":
    # Keep multiuser mode FALSE to allow local AWS credentials for S3 access ❌ WRONG
    monkeypatch.setenv("QUILT_MULTIUSER_MODE", "false")  # ❌ This defeats the purpose
    monkeypatch.setenv("QUILT_BACKEND_TYPE", "graphql")
```

**Why this is wrong:**

- Sets `QUILT_MULTIUSER_MODE=false` to disable JWT mode
- Uses local IAM credentials from the environment
- Defeats the entire purpose of JWT authentication
- Cannot work in production stateless deployments (no local AWS credentials)

### Correct Approach (How Catalog Works)

The Quilt catalog properly exchanges JWT tokens for temporary AWS credentials:

#### 1. Frontend: RegistryCredentials Class

**File:** `quilt/catalog/app/utils/AWS/Credentials.jsx`

```javascript
class RegistryCredentials extends AWS.Credentials {
  refresh(callback) {
    this.refreshing = this.req({ endpoint: '/auth/get_credentials', ...this.reqOpts })
      .then((data) => {
        this.expireTime = data.Expiration ? new Date(data.Expiration) : null
        this.accessKeyId = data.AccessKeyId           // ✅ Temporary credentials
        this.secretAccessKey = data.SecretAccessKey    // ✅ From STS
        this.sessionToken = data.SessionToken          // ✅ Time-limited
      })
  }
}
```

**Key insight:** The JWT token is in the request headers (Authorization: Bearer <token>), and the backend exchanges it for temporary AWS credentials.

#### 2. Backend: Credential Refresh

**File:** `quilt/api/python/quilt3/session.py:289-299`

```python
def _refresh_credentials():
    session = get_session()  # Has JWT token in headers
    creds = session.get("{url}/api/auth/get_credentials".format(url=get_registry_url())).json()
    result = {
        'access_key': creds['AccessKeyId'],
        'secret_key': creds['SecretAccessKey'],
        'token': creds['SessionToken'],
        'expiry_time': creds['Expiration'],
    }
    _save_credentials(result)
    return result
```

#### 3. Credential Provider with Auto-Refresh

**File:** `quilt/api/python/quilt3/session.py:310-325`

```python
class QuiltProvider(CredentialProvider):
    METHOD = 'quilt-registry'
    CANONICAL_NAME = 'QuiltRegistry'

    def load(self):
        creds = RefreshableCredentials.create_from_metadata(
            metadata=self._credentials,
            method=self.METHOD,
            refresh_using=_refresh_credentials,  # ✅ Auto-refreshes when expired
        )
        return creds
```

## The Correct Flow

```
┌──────────────────────────────────────────────────────────────┐
│ 1. User Authenticates                                        │
│    - quilt3.login() or web login                            │
│    - Gets JWT access token + refresh token                  │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Request AWS Credentials                                   │
│    GET /api/auth/get_credentials                            │
│    Authorization: Bearer <JWT_TOKEN>                        │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. Backend Exchanges JWT for AWS Credentials                │
│    - Validates JWT token                                    │
│    - Calls AWS STS AssumeRoleWithWebIdentity                │
│    - Returns temporary credentials:                         │
│      * AccessKeyId                                          │
│      * SecretAccessKey                                      │
│      * SessionToken                                         │
│      * Expiration (typically 1 hour)                        │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. Use Temporary Credentials for S3 Operations               │
│    - Create boto3 session with temporary credentials        │
│    - Access S3 buckets with user's scoped permissions       │
│    - Automatically refresh when credentials expire          │
└──────────────────────────────────────────────────────────────┘
```

## What Needs to Be Fixed

### 1. Implement Credential Exchange in JWTAuthService

**Current:** [src/quilt_mcp/services/jwt_auth_service.py:48-51](../../src/quilt_mcp/services/jwt_auth_service.py#L48-L51)

```python
def get_session(self):
    # ...
    raise JwtAuthServiceError(
        "AWS credentials are not available for JWT authentication.",
        code="aws_not_supported",
    )
```

**Should be:**

```python
def get_session(self):
    """Get boto3 session with temporary AWS credentials from JWT."""
    runtime_auth = get_runtime_auth()
    if runtime_auth is None or not runtime_auth.access_token:
        raise JwtAuthServiceError("JWT token required", code="missing_jwt")

    # Exchange JWT for temporary AWS credentials
    credentials = self._get_temporary_credentials(runtime_auth.access_token)

    # Create boto3 session with temporary credentials
    return boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
    )

def _get_temporary_credentials(self, access_token: str) -> dict:
    """Call /api/auth/get_credentials to exchange JWT for AWS credentials."""
    registry_url = get_registry_url()
    if not registry_url:
        raise JwtAuthServiceError("Registry URL not configured")

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"{registry_url}/api/auth/get_credentials",
        headers=headers,
        timeout=30
    )

    if response.status_code == 401:
        raise JwtAuthServiceError("JWT token invalid or expired", code="invalid_jwt")

    response.raise_for_status()
    return response.json()  # Returns AccessKeyId, SecretAccessKey, SessionToken, Expiration
```

### 2. Add Credential Caching and Auto-Refresh

Similar to `QuiltProvider`, implement:

- Cache credentials in memory
- Check expiration time before use
- Automatically refresh when expired
- Use `RefreshableCredentials` from botocore

### 3. Update Platform Backend Tests

**Change from:**

```python
# WRONG: Disable JWT to use local IAM credentials
monkeypatch.setenv("QUILT_MULTIUSER_MODE", "false")
monkeypatch.setenv("QUILT_BACKEND_TYPE", "graphql")
```

**To:**

```python
# CORRECT: Use JWT to get temporary AWS credentials
monkeypatch.setenv("QUILT_MULTIUSER_MODE", "true")  # Enable JWT mode
# Backend type is automatically "graphql" when multiuser=true
# JWT token in runtime context will be exchanged for AWS credentials
```

### 4. Remove the Backend Override Hack

The `QUILT_BACKEND_TYPE` override was a workaround for the wrong approach. With proper JWT credential exchange:

- `QUILT_MULTIUSER_MODE=true` → Platform backend + JWT auth
- JWT auth service exchanges token for AWS credentials
- No need for backend override

## Benefits of Correct Approach

### Security

- ✅ No long-lived AWS credentials in environment
- ✅ Temporary credentials expire (typically 1 hour)
- ✅ Credentials scoped to user's permissions
- ✅ Works in stateless deployments (Lambda, ECS)

### Functionality

- ✅ Works with real catalog authentication
- ✅ Proper user identity and permissions
- ✅ Automatic credential refresh
- ✅ Matches production deployment model

### Testing

- ✅ Platform backend tests work properly
- ✅ Can test full JWT flow end-to-end
- ✅ No need for environment-specific configurations
- ✅ Tests match production behavior

## Implementation Priority

**Priority:** 🔴 **CRITICAL**

This is not just a test configuration issue - it's a fundamental architecture flaw. The current workaround (disabling JWT to get AWS access) cannot work in production stateless deployments.

### Implementation Steps

1. **Implement JWT credential exchange** in `JWTAuthService`
   - Add `_get_temporary_credentials()` method
   - Implement credential caching
   - Add auto-refresh logic

2. **Add credential provider** similar to `QuiltProvider`
   - Use `RefreshableCredentials` from botocore
   - Register with botocore session

3. **Update platform backend tests**
   - Remove `QUILT_BACKEND_TYPE` override
   - Use `QUILT_MULTIUSER_MODE=true`
   - Let JWT service handle credentials

4. **Remove backend override hack**
   - Remove `backend_type_override` parameter
   - Simplify configuration logic

5. **Add integration tests**
   - Test JWT → AWS credentials exchange
   - Test credential expiration and refresh
   - Test error handling (invalid JWT, expired token)

## References

- **Catalog Frontend:** `quilt/catalog/app/utils/AWS/Credentials.jsx:24-73`
- **Catalog Backend:** `quilt/api/python/quilt3/session.py:289-339`
- **Current MCP JWT Service:** [src/quilt_mcp/services/jwt_auth_service.py](../../src/quilt_mcp/services/jwt_auth_service.py)
- **Current Wrong Fix:** [spec/a17-test-cleanup/05-platform-backend-fix.md](./05-platform-backend-fix.md)

## Conclusion

The current approach of disabling JWT mode to get AWS credentials is fundamentally backwards. We need to implement proper JWT-to-AWS-credentials exchange, exactly like the catalog does. This will:

1. Fix platform backend testing properly
2. Enable stateless deployments
3. Match production security model
4. Remove the need for configuration hacks

**Next Action:** Implement JWT credential exchange in `JWTAuthService` before proceeding with any other test cleanup work.
