# JWT Catalog Authentication Solution

**Date:** January 29, 2026  
**Status:** 🎯 **ROOT CAUSE IDENTIFIED - SOLUTION DEFINED**  

## The Complete Picture

### What We Discovered

1. **Local Environment Works**: Has both AWS credentials AND Quilt catalog bearer token
2. **Docker Container Fails**: Has AWS credentials (via JWT) but NO catalog bearer token
3. **Missing Link**: Our JWT provides AWS access but not catalog access

### The Two-Token Authentication System

Quilt MCP requires **TWO separate authentication mechanisms**:

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Request                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Authorization: Bearer <MCP_JWT>                │   │
│  │  - Contains AWS role ARN                        │   │
│  │  - Contains session tags                        │   │
│  │  - Used for AWS operations                      │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 MCP Server Processing                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │  AWS Operations (S3, etc.)                     │   │
│  │  ✅ Uses MCP JWT → AWS credentials              │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Catalog Operations (Search, etc.)             │   │
│  │  ❌ Needs separate catalog bearer token         │   │
│  │  📋 Token: eyJ0eXAiOiJKV1QiLCJhbGciOi...       │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Current JWT vs Required Information

**Our Current MCP JWT Contains:**

```json
{
  "iss": "mcp-test",
  "aud": "mcp-server", 
  "iat": 1706479600,
  "exp": 1706483200,
  "sub": "test-user",
  "role arn": "arn:aws:iam::123456789:role/TestRole",
  "session_tags": {...}
}
```

**Missing Catalog Authentication:**

```json
{
  "catalog_url": "https://nightly.quilttest.com",
  "catalog_token": "eyJ0eXAiOiJKV1QiLCJhbGciOi...",
  "registry_url": "https://nightly-registry.quilttest.com"
}
```

**Catalog Bearer Token Structure:**

```json
{
  "typ": "JWT",
  "alg": "HS256",
  "id": "81a35282-0149-4eb3-bb8e-627379db6a1c",
  "uuid": "3b5da635-afa3-4c3d-8c6f-39473c4bf8b9", 
  "exp": 1777432638
}
```

## Solution Options

### Option 1: Embed Catalog Token in MCP JWT ⭐ **RECOMMENDED**

**Approach**: Include the catalog bearer token as a claim in our MCP JWT.

**Modified JWT Structure:**

```json
{
  "iss": "mcp-test",
  "aud": "mcp-server",
  "iat": 1706479600,
  "exp": 1706483200,
  "sub": "test-user",
  "role arn": "arn:aws:iam::123456789:role/TestRole",
  "session_tags": {...},
  "catalog_url": "https://nightly.quilttest.com",
  "catalog_token": "eyJ0eXAiOiJKV1QiLCJhbGciOi...",
  "registry_url": "https://nightly-registry.quilttest.com"
}
```

**Implementation:**

1. **Update JWT Helper Script**:

```python
def generate_test_jwt(
    role arn: str,
    secret: str,
    catalog_token: str,  # NEW: Add catalog token
    catalog_url: str = "https://nightly.quilttest.com",  # NEW
    registry_url: str = "https://nightly-registry.quilttest.com",  # NEW
    ...
):
    payload = {
        # ... existing claims ...
        "catalog_url": catalog_url,
        "catalog_token": catalog_token,
        "registry_url": registry_url
    }
```

1. **Update JWT Auth Service**:

```python
def create_catalog_session(self):
    """Create authenticated catalog session from JWT claims."""
    claims = self.get_jwt_claims()
    
    catalog_token = claims.get('catalog_token')
    catalog_url = claims.get('catalog_url')
    registry_url = claims.get('registry_url')
    
    if not all([catalog_token, catalog_url, registry_url]):
        raise AuthenticationError("Missing catalog authentication in JWT")
    
    # Create authenticated session
    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {catalog_token}',
        'Content-Type': 'application/json'
    })
    
    # Configure quilt3 to use this session
    quilt3.config(catalog_url)
    quilt3.session._session = session
    quilt3.session._registry_url = registry_url
```

1. **Update Test Script**:

```bash
# Extract catalog token from current session
CATALOG_TOKEN=$(python -c "
from quilt_mcp.services.quilt_service import QuiltService
qs = QuiltService()
session = qs.get_session()
auth_header = session.headers.get('Authorization', '')
print(auth_header.replace('Bearer ', ''))
")

# Generate MCP JWT with catalog token
JWT_TOKEN=$(uv run python scripts/tests/jwt_helper.py generate \
  --role-arn "$QUILT_TEST_JWT_TOKEN" \
  --catalog-token "$CATALOG_TOKEN" \
  --secret "test-secret-key")
```

**Pros:**

- ✅ Simple and direct solution
- ✅ All authentication in one JWT
- ✅ No additional API calls needed
- ✅ Works with existing JWT infrastructure

**Cons:**

- ⚠️ JWT becomes larger
- ⚠️ Catalog token expiry separate from MCP JWT expiry
- ⚠️ Requires valid catalog session to generate test JWT

### Option 2: Programmatic Catalog Login

**Approach**: Use AWS credentials to authenticate with catalog programmatically.

**Implementation:**

```python
def authenticate_with_catalog_using_aws(self, aws_credentials):
    """Authenticate with catalog using AWS credentials."""
    # This would require catalog API support for AWS credential auth
    # May not be available in current Quilt catalog implementation
    pass
```

**Pros:**

- ✅ Single authentication source (AWS)
- ✅ No need to manage catalog tokens

**Cons:**

- ❌ Requires catalog API changes
- ❌ May not be supported by Quilt catalog
- ❌ More complex implementation

### Option 3: Mock Catalog Session for Testing

**Approach**: Create mock catalog authentication for testing only.

**Implementation:**

```python
def create_mock_catalog_session(self):
    """Create mock catalog session for testing."""
    if not os.getenv('QUILT_MCP_TESTING'):
        raise AuthenticationError("Mock session only for testing")
    
    # Mock the session to return test data
    # This allows testing without real catalog authentication
```

**Pros:**

- ✅ Simple for testing
- ✅ No dependency on real catalog tokens

**Cons:**

- ❌ Only works for testing
- ❌ Doesn't solve production use case
- ❌ May hide real authentication issues

## Recommended Implementation Plan

### Phase 1: Update JWT Generation (Option 1)

1. **Extract Current Catalog Token**:

```python
# In jwt_helper.py
def extract_current_catalog_token():
    """Extract catalog token from current quilt3 session."""
    try:
        from quilt_mcp.services.quilt_service import QuiltService
        qs = QuiltService()
        if qs.has_session_support():
            session = qs.get_session()
            auth_header = session.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                return auth_header[7:]  # Remove 'Bearer ' prefix
    except Exception:
        pass
    return None
```

1. **Update JWT Structure**:

```python
def generate_test_jwt(
    role arn: str,
    secret: str,
    catalog_token: Optional[str] = None,
    auto_extract_catalog: bool = True,
    ...
):
    if auto_extract_catalog and not catalog_token:
        catalog_token = extract_current_catalog_token()
        
    if not catalog_token:
        raise ValueError("Catalog token required for stateless operation")
    
    payload = {
        # ... existing claims ...
        "catalog_token": catalog_token,
        "catalog_url": "https://nightly.quilttest.com",
        "registry_url": "https://nightly-registry.quilttest.com"
    }
```

1. **Update JWT Auth Service**:

```python
def setup_catalog_authentication(self):
    """Setup catalog authentication from JWT claims."""
    claims = self.get_runtime_claims()
    
    catalog_token = claims.get('catalog_token')
    catalog_url = claims.get('catalog_url')
    registry_url = claims.get('registry_url')
    
    if catalog_token and catalog_url:
        self._configure_catalog_session(catalog_token, catalog_url, registry_url)
    else:
        logger.warning("No catalog authentication in JWT - search operations may fail")

def _configure_catalog_session(self, token, catalog_url, registry_url):
    """Configure quilt3 session with catalog authentication."""
    import quilt3
    
    # Create authenticated session
    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    
    # Configure quilt3
    quilt3.config(catalog_url)
    
    # Set the authenticated session
    if hasattr(quilt3, 'session'):
        quilt3.session._session = session
        if hasattr(quilt3.session, '_registry_url'):
            quilt3.session._registry_url = registry_url
```

### Phase 2: Update Test Infrastructure

1. **Update make.dev target**:

```makefile
test-stateless-mcp: docker-build
 @echo "🔐 Testing stateless MCP with JWT authentication..."
 @echo "Step 1: Extracting catalog token from current session..."
 @CATALOG_TOKEN=$$(uv run python -c "from scripts.tests.jwt_helper import extract_current_catalog_token; print(extract_current_catalog_token() or '')") && \
 if [ -z "$$CATALOG_TOKEN" ]; then \
  echo "❌ No catalog token available. Please run 'quilt3 login' first."; \
  exit 1; \
 fi && \
 echo "Step 2: Generating JWT with catalog authentication..." && \
 JWT_TOKEN=$$(uv run python scripts/tests/jwt_helper.py generate \
  --role-arn "$(QUILT_TEST_JWT_TOKEN)" \
  --catalog-token "$$CATALOG_TOKEN" \
  --secret "test-secret-key") && \
 echo "Step 3: Testing with complete authentication..." && \
 # ... rest of docker run command ...
```

1. **Update JWT Auth Service Integration**:

```python
# In auth service factory
def get_auth_service():
    require_jwt = os.getenv("MCP_REQUIRE_JWT", "false").lower() == "true"
    
    if require_jwt:
        jwt_service = JWTAuthService()
        # Setup catalog authentication from JWT
        jwt_service.setup_catalog_authentication()
        return jwt_service
    else:
        return IAMAuthService()
```

### Phase 3: Validation

1. **Test JWT Generation**:

```bash
# Test that JWT contains catalog token
JWT_TOKEN=$(uv run python scripts/tests/jwt_helper.py generate \
  --role-arn "arn:aws:iam::123456789:role/TestRole" \
  --secret "test-secret")

# Inspect JWT to verify catalog claims
uv run python scripts/tests/jwt_helper.py inspect \
  --token "$JWT_TOKEN" \
  --secret "test-secret"
```

1. **Test Stateless Operation**:

```bash
# Run stateless test with complete authentication
make test-stateless-mcp
```

1. **Verify Search Works**:

```bash
# Should now return results instead of 0
curl -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{"method":"tools/call","params":{"name":"search_catalog","arguments":{"query":"README.md"}}}'
```

## Expected Results

After implementing this solution:

1. **JWT Generation**: ✅ Includes both AWS and catalog authentication
2. **Docker Container**: ✅ Has access to both AWS and catalog via JWT
3. **Search Operations**: ✅ Work in stateless environment
4. **Test Results**: ✅ All 3 search_catalog tests pass

## Key Insights

1. **Not an Architecture Flaw**: The JWT implementation is sound, just incomplete
2. **Missing Catalog Auth**: We were only providing AWS authentication, not catalog authentication
3. **Two-Token System**: Quilt requires both AWS credentials and catalog bearer tokens
4. **Simple Solution**: Embed catalog token in MCP JWT for complete authentication

This solution maintains the stateless architecture while providing complete authentication for both AWS and catalog operations.
