# QuiltService Abstraction Analysis

**Date:** 2026-01-30
**Branch:** a11-jwt-client
**Prerequisites:** Read [21-search-bug-architectural-analysis.md](./21-search-bug-architectural-analysis.md) first
**Status:** 🔍 Critical architectural evaluation

---

## Executive Summary

This document analyzes whether QuiltService is positioned correctly to solve the dual-runtime problem identified in the architectural analysis. We examine two critical questions:

**a) Interface/Abstraction:** Does QuiltService properly abstract mode/auth information away from tools?
**b) Implementation/Capability:** Can QuiltService access the information needed to route operations correctly?

**Key Findings:**

- ❌ **Question (a): NO** - Tools are exposed to implementation details and make runtime-specific calls
- ⚠️ **Question (b): PARTIALLY** - QuiltService CAN access runtime metadata, but lacks detection logic
- 🔴 **Critical Gap:** QuiltService has no mode detection, no routing logic, and exposes wrong abstractions

---

## Question (a): Does QuiltService Properly Abstract Mode/Auth?

### What "Proper Abstraction" Means

For QuiltService to properly abstract mode/auth, tools should:

1. ✅ Call domain-level operations (e.g., `search_catalog()`, `browse_package()`)
2. ✅ NOT know whether JWT or quilt3 session is being used
3. ✅ NOT construct GraphQL queries manually
4. ✅ NOT handle sessions or credentials directly
5. ✅ Work identically in stdio and HTTP modes

### Current Reality: Tools Are NOT Abstracted

#### Evidence 1: Search Backend Constructs GraphQL Manually

From [elasticsearch.py:228-238](../../src/quilt_mcp/search/backends/elasticsearch.py#L228-L238):

```python
def _fetch_bucket_list(self) -> List[str]:
    """Fetch list of buckets via catalog GraphQL."""
    try:
        session = self.quilt_service.get_session()      # ← Gets low-level session
        registry_url = self.quilt_service.get_registry_url()

        if not session or not registry_url:
            return []

        resp = session.post(                            # ← Manually constructs GraphQL
            f"{registry_url.rstrip('/')}/graphql",
            json={"query": "{ bucketConfigs { name } }"},
            timeout=30,
        )

        # ... parse response manually
```

**Problems:**

- ❌ Tool explicitly retrieves `session` object (implementation detail)
- ❌ Tool constructs GraphQL endpoint URL manually
- ❌ Tool builds GraphQL query manually
- ❌ Tool handles HTTP response parsing
- ❌ **This entire block would fail in JWT mode** because `get_session()` returns unauthenticated session

**What proper abstraction looks like:**

```python
def _fetch_bucket_list(self) -> List[str]:
    """Fetch list of buckets via catalog."""
    try:
        return self.quilt_service.get_bucket_list()  # ← QuiltService handles everything
```

QuiltService should hide:

- Whether it uses quilt3 APIs or GraphQL
- How authentication works
- Session management
- HTTP mechanics

#### Evidence 2: GraphQL Search Tool Exposes Sessions

From [search.py:363-386](../../src/quilt_mcp/tools/search.py#L363-L386):

```python
def _get_graphql_endpoint():
    """Return (session, graphql_url) from QuiltService context or (None, None)."""
    try:
        from ..services.quilt_service import QuiltService

        quilt_service = QuiltService()

        if not quilt_service.has_session_support():
            return None, None
        session = quilt_service.get_session()          # ← Tool gets session
        registry_url = quilt_service.get_registry_url()
        if not registry_url:
            return None, None
        graphql_url = urljoin(registry_url.rstrip("/") + "/", "graphql")
        return session, graphql_url                     # ← Returns session to caller
    except Exception:
        return None, None

def search_graphql(query: str, variables: Optional[Dict] = None):
    """Execute an arbitrary GraphQL query against the configured Quilt Catalog."""
    session, graphql_url = _get_graphql_endpoint()     # ← Gets session from QuiltService
    if not session or not graphql_url:
        return SearchGraphQLError(...)

    resp = session.post(graphql_url, json={"query": query, "variables": variables or {}})
    # ...
```

**Problems:**

- ❌ Tool explicitly checks `has_session_support()` (mode awareness)
- ❌ Tool retrieves and uses `requests.Session` object directly
- ❌ Tool constructs GraphQL URL
- ❌ **Tool is responsible for HTTP mechanics**, not QuiltService

**What proper abstraction looks like:**

```python
def search_graphql(query: str, variables: Optional[Dict] = None):
    """Execute an arbitrary GraphQL query against the configured Quilt Catalog."""
    quilt_service = QuiltService()
    return quilt_service.execute_graphql(query, variables)  # ← QuiltService handles it
```

#### Evidence 3: QuiltService Exposes Wrong Abstractions

Current QuiltService interface from [quilt_service.py](../../src/quilt_mcp/services/quilt_service.py):

**Low-level session methods (wrong level):**

```python
def has_session_support(self) -> bool
def get_session(self) -> Any              # ← Returns requests.Session
def get_registry_url(self) -> str | None
def create_botocore_session(self) -> Any
```

**Package methods (better, but incomplete):**

```python
def create_package_revision(...) -> Dict
def browse_package(...) -> Any             # ← Returns quilt3.Package object!
def list_packages(registry: str) -> Iterator[str]
```

**Missing catalog operation methods:**

```python
# These DON'T EXIST but should:
def get_bucket_list(self) -> List[str]
def search_catalog(query: str, ...) -> SearchResults
def execute_graphql(query: str, variables: Dict) -> Dict
def get_package_metadata(name: str, registry: str) -> Dict
```

**The Problem:**

QuiltService provides **infrastructure primitives** (sessions, URLs) instead of **domain operations** (search, list, browse).

### Answer to Question (a): **NO**

**QuiltService does NOT properly abstract mode/auth from tools.**

Evidence:

1. ❌ Tools manually retrieve sessions and construct GraphQL queries
2. ❌ Tools check for `has_session_support()` (mode-aware code)
3. ❌ Tools handle HTTP mechanics and response parsing
4. ❌ QuiltService exposes low-level primitives instead of domain operations
5. ❌ `browse_package()` returns `quilt3.Package` objects (leaky abstraction)

**Impact:** Tools MUST know about runtime modes and will break when modes change.

---

## Question (b): Can QuiltService Access Required Information?

### What Information Is Needed

To route operations correctly, QuiltService needs:

1. **JWT credentials** (if available)
   - `catalog_token` - For authenticating to registry GraphQL
   - `catalog_url` - Target catalog URL
   - `registry_url` - Registry endpoint

2. **Mode detection**
   - Are JWT credentials present?
   - Is quilt3 session available?
   - What's the runtime environment?

3. **Configuration**
   - Is the container in stateless mode?
   - What operations are requested?

### Where This Information Lives

#### JWT Credentials: Runtime Context (ContextVar)

From [runtime_context.py:16-33](../../src/quilt_mcp/runtime_context.py#L16-L33):

```python
@dataclass(frozen=True)
class RuntimeAuthState:
    """Authentication details for the active request/environment."""
    scheme: str
    access_token: Optional[str] = None
    claims: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RuntimeContextState:
    """Top-level runtime context shared with MCP tools."""
    environment: str                              # ← "desktop" or "http"
    auth: Optional[RuntimeAuthState] = None       # ← JWT claims
    metadata: Dict[str, Any] = field(default_factory=dict)  # ← catalog_token, catalog_url

# Per-request isolation
_runtime_context_var: ContextVar[RuntimeContextState] = ContextVar(
    "quilt_runtime_context",
    default=_default_state,
)
```

**Available via:**

```python
from quilt_mcp.runtime_context import (
    get_runtime_state,
    get_runtime_environment,  # → "desktop" or "http"
    get_runtime_auth,         # → RuntimeAuthState with JWT claims
    get_runtime_metadata,     # → Dict with catalog_token, catalog_url, registry_url
    get_runtime_access_token,
    get_runtime_claims,
)
```

#### JWT Auth Service Sets This Context

From [jwt_auth_service.py:151-174](../../src/quilt_mcp/services/jwt_auth_service.py#L151-L174):

```python
def _configure_quilt3_session(self, token: Optional[str], catalog_url: Optional[str], registry_url: Optional[str]) -> None:
    """Configure quilt3 with catalog session information."""
    if not token or not catalog_url:
        return

    try:
        import quilt3

        # Configure quilt3 with the catalog URL (does nothing useful in read-only mode)
        quilt3.config(catalog_url)

        # Store catalog authentication in runtime metadata for later use
        update_runtime_metadata(                      # ← Sets ContextVar
            catalog_token=token,
            catalog_url=catalog_url,
            registry_url=registry_url,
            catalog_session_configured=True
        )

    except ImportError:
        logger.warning("quilt3 not available - catalog operations will not work")
```

**What gets stored:**

```python
metadata = {
    "catalog_token": "eyJhbG...",  # JWT token for catalog auth
    "catalog_url": "https://catalog.example.com",
    "registry_url": "https://catalog.example.com",
    "catalog_session_configured": True,
}
```

#### quilt3 Session: File-Based (~/.quilt/)

From [quilt3/session.py](../../.venv/lib/python3.12/site-packages/quilt3/session.py):

```python
def get_session(timeout=None):
    """Creates a session or returns an existing session."""
    global _session
    if _session is None:
        auth = _create_auth(timeout)  # ← Reads ~/.quilt/auth.json
        _session = _create_session(auth)
    return _session
```

**Currently accessed via:**

```python
quilt_service = QuiltService()
session = quilt_service.get_session()  # → quilt3.session.get_session()
```

### Can QuiltService Access This Information?

**YES - All information is accessible:**

| Information | Location | Access Method | Currently Used? |
|------------|----------|---------------|----------------|
| **JWT credentials** | `ContextVar` runtime metadata | `get_runtime_metadata()` | ❌ NO |
| **JWT catalog_token** | Runtime metadata | `get_runtime_metadata()["catalog_token"]` | ❌ NO |
| **JWT catalog_url** | Runtime metadata | `get_runtime_metadata()["catalog_url"]` | ❌ NO |
| **JWT registry_url** | Runtime metadata | `get_runtime_metadata()["registry_url"]` | ❌ NO |
| **Runtime environment** | `ContextVar` | `get_runtime_environment()` | ❌ NO |
| **JWT auth state** | `ContextVar` | `get_runtime_auth()` | ❌ NO |
| **JWT claims** | `ContextVar` | `get_runtime_claims()` | ❌ NO |
| **quilt3 session** | `~/.quilt/auth.json` | `quilt3.session.get_session()` | ✅ YES (only this) |

### What's Missing: Mode Detection Logic

QuiltService **CAN** access all required information, but it **DOES NOT** have logic to:

1. **Detect which mode to use:**

   ```python
   # This doesn't exist:
   def _detect_auth_mode(self) -> Literal["jwt", "quilt3", "none"]:
       """Detect which authentication/execution mode to use."""
       # Check for JWT first
       metadata = get_runtime_metadata()
       if metadata.get("catalog_token") and metadata.get("catalog_url"):
           return "jwt"

       # Check for quilt3 session
       if self.has_session_support():
           session = self.get_session()
           if session.headers.get("Authorization"):
               return "quilt3"

       return "none"
   ```

2. **Route operations based on mode:**

   ```python
   # This doesn't exist:
   def get_bucket_list(self) -> List[str]:
       """Get list of catalog buckets (works in both modes)."""
       mode = self._detect_auth_mode()

       if mode == "jwt":
           return self._get_bucket_list_graphql()
       elif mode == "quilt3":
           return self._get_bucket_list_quilt3()
       else:
           raise Exception("No authentication available")

   def _get_bucket_list_graphql(self) -> List[str]:
       """Implementation using JWT + GraphQL."""
       metadata = get_runtime_metadata()
       token = metadata["catalog_token"]
       registry_url = metadata["registry_url"]

       session = requests.Session()
       session.headers["Authorization"] = f"Bearer {token}"

       resp = session.post(
           f"{registry_url}/graphql",
           json={"query": "{ bucketConfigs { name } }"}
       )
       # ... parse and return

   def _get_bucket_list_quilt3(self) -> List[str]:
       """Implementation using quilt3 session."""
       # Use existing quilt3 APIs
   ```

3. **Provide clear errors when credentials are missing:**

   ```python
   # This doesn't exist:
   def _check_credentials_or_fail(self) -> None:
       """Verify credentials are available, provide clear error if not."""
       mode = self._detect_auth_mode()

       if mode == "none":
           env = get_runtime_environment()
           if env == "http":
               raise Exception(
                   "No JWT credentials provided. "
                   "In stateless mode, JWT authentication is required. "
                   "Check that the client is sending a valid JWT token."
               )
           else:
               raise Exception(
                   "No authentication available. "
                   "Run 'quilt3 login' to authenticate, or provide JWT credentials."
               )
   ```

### Answer to Question (b): **PARTIALLY**

**QuiltService CAN access all required information, but DOES NOT use it.**

Evidence:

1. ✅ Runtime metadata is accessible via `get_runtime_metadata()`
2. ✅ JWT credentials (`catalog_token`, `catalog_url`) are stored in ContextVar
3. ✅ Runtime environment is accessible via `get_runtime_environment()`
4. ❌ QuiltService doesn't import or use runtime context functions
5. ❌ No mode detection logic exists
6. ❌ No routing logic exists
7. ❌ No JWT-based GraphQL implementation exists

**Current state:** QuiltService only uses quilt3 session files (stdio mode), completely ignoring JWT credentials.

---

## The Critical Gap: No Mode Detection or Routing

### What Currently Happens

```
Tool calls QuiltService.get_session()
     ↓
QuiltService.get_session() → quilt3.session.get_session()
     ↓
quilt3 reads ~/.quilt/auth.json
     ↓
File doesn't exist in stateless mode → returns unauthenticated session
     ↓
Tool makes GraphQL request with unauthenticated session
     ↓
❌ 401 Unauthorized
```

**Meanwhile, JWT credentials sit unused in runtime metadata:**

```python
# This data exists but is never used!
metadata = {
    "catalog_token": "eyJhbG...",  # ← Has valid token
    "catalog_url": "https://catalog.example.com",
    "registry_url": "https://catalog.example.com",
}
```

### What Should Happen

```
Tool calls QuiltService.get_bucket_list()
     ↓
QuiltService detects mode: get_runtime_metadata() has catalog_token → JWT mode
     ↓
QuiltService._get_bucket_list_graphql():
  - Reads catalog_token from runtime metadata
  - Creates session with Bearer token
  - Makes authenticated GraphQL request
     ↓
✅ Returns bucket list
```

---

## Architectural Diagnosis

### The Two-Layer Problem

**Layer 1: Wrong Abstraction Level (Question a)**

QuiltService provides:

- ❌ Infrastructure primitives (sessions, URLs)
- ❌ Leaky abstractions (`quilt3.Package` objects)
- ❌ Mode-aware methods (`has_session_support()`)

QuiltService should provide:

- ✅ Domain operations (search, list, browse)
- ✅ Runtime-agnostic interfaces
- ✅ Automatic mode detection and routing

**Layer 2: Missing Implementation (Question b)**

QuiltService has access to:

- ✅ JWT credentials (runtime metadata)
- ✅ Runtime environment
- ✅ quilt3 session files
- ✅ All necessary information

QuiltService is missing:

- ❌ Mode detection logic
- ❌ Credential validation
- ❌ JWT-based GraphQL implementations
- ❌ Operation routing

### Why This Happened

From [quilt_service.py:1-5](../../src/quilt_mcp/services/quilt_service.py#L1-L5):

```python
"""QuiltService - Centralized abstraction for all quilt3 operations.

This service provides a single point of access to all quilt3 functionality,
isolating the 84+ MCP tools from direct quilt3 dependencies.
"""
```

**The service was designed to wrap quilt3, not to abstract Quilt operations (platform vs quilt3).**

Original goal (wrong): "Isolate tools from quilt3"
Actual need (right): "Abstract Quilt operations (platform vs quilt3) across runtime modes"

### What "Right Level of Abstraction" Would Look Like

**Proposed interface:**

```python
class CatalogService:  # Not "QuiltService"
    """Abstraction for Quilt catalog and package operations.

    Automatically detects runtime mode (JWT vs quilt3 session) and routes
    operations to the appropriate backend. Tools never need to know which
    mode is active.
    """

    # High-level catalog operations
    def get_bucket_list(self) -> List[str]
    def search_catalog(query: str, scope: str, ...) -> SearchResults
    def execute_graphql(query: str, variables: Dict) -> Dict

    # High-level package operations
    def list_packages(registry: str) -> List[str]
    def get_package_metadata(name: str, registry: str) -> PackageMetadata
    def browse_package(name: str, registry: str) -> PackageInfo  # Returns dict, not quilt3.Package
    def create_package(name: str, s3_uris: List[str], ...) -> PackageResult

    # Internal: Mode detection and routing (tools never call these)
    def _detect_mode(self) -> AuthMode
    def _route_to_backend(self, operation: str) -> Backend
```

**Key characteristics:**

- Tool calls `service.search_catalog()` → service handles everything
- Service detects JWT vs quilt3 mode internally
- Service uses GraphQL (JWT mode) or quilt3 APIs (stdio mode) automatically
- Service returns dicts/dataclasses, never `requests.Session` or `quilt3.Package`
- Tools work identically in both modes without any changes

---

## Conclusion

### Question (a): Does QuiltService properly abstract mode/auth from tools?

**Answer: NO**

QuiltService operates at the wrong abstraction level:

- Exposes infrastructure primitives (sessions, URLs)
- Tools manually construct GraphQL queries
- Tools are mode-aware (check `has_session_support()`)
- Leaky abstractions (`quilt3.Package` objects)

### Question (b): Can QuiltService access required information?

**Answer: PARTIALLY**

QuiltService **CAN** access all required information:

- ✅ JWT credentials available via `get_runtime_metadata()`
- ✅ Runtime environment via `get_runtime_environment()`
- ✅ quilt3 session files via existing code

But QuiltService **DOES NOT USE IT**:

- ❌ No imports of runtime context functions
- ❌ No mode detection logic
- ❌ No routing logic
- ❌ No JWT-based implementations

### The Core Problem

**QuiltService is at the wrong level of abstraction AND lacks the implementation to support dual modes.**

It's neither fish nor fowl:

- Too low-level to properly abstract operations from tools
- Too high-level to be a simple quilt3 wrapper
- Structured incorrectly to support mode detection/routing

### What This Means for the Search Bug

The search bug cannot be fixed with a simple patch because:

1. **Tools expect low-level primitives** (sessions, URLs) instead of operations
2. **No routing logic exists** to choose JWT vs quilt3 mode
3. **JWT credentials are stored but never used** by QuiltService
4. **Every catalog operation would need similar fixes** (search, browse, list, etc.)

**This is a systemic architectural issue, not a localized bug.**

---

## Next Steps

The architectural analysis identified three possible paths forward:

1. **Minimal fix** - Patch only the search bug (incomplete, more bugs will emerge)
2. **Refactor QuiltService** - Add mode detection and routing (addresses root cause)
3. **Rethink abstraction** - Replace with higher-level CatalogService (clean slate)

This analysis shows that option #1 is insufficient because:

- Tools are tightly coupled to infrastructure details
- No routing mechanism exists
- Fixing search wouldn't fix browse, list, or other operations

**Recommendation:** Proceed with architectural planning for option #2 or #3.
