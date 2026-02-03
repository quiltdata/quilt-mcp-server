# Search Bug: Deeper Architectural Analysis

**Date:** 2026-01-30
**Branch:** a11-jwt-client
**Prerequisites:** Read [20-search-bug-root-cause-analysis.md](./20-search-bug-root-cause-analysis.md) first
**Status:** 🔬 Deep dive into fundamental architectural mismatch

---

## Executive Summary

The [previous analysis](./20-search-bug-root-cause-analysis.md) correctly identified the symptom: JWT credentials are stored in runtime metadata while search reads from quilt3's session API. However, the diagnosis was **architecturally shallow**.

The real issue is a **fundamental incompatibility** between quilt3's design assumptions and the MCP server's requirements. The bug reveals that the MCP server has two parallel, disconnected authentication systems competing for the same purpose.

---

## The Fundamental Mismatch

### quilt3's Design: Single-User CLI Tool

From [quilt3/session.py](../../.venv/lib/python3.12/site-packages/quilt3/session.py):

```python
# Global module-level state
_session = None

def get_session(timeout=None):
    """Creates a session or returns an existing session."""
    global _session
    if _session is None:
        auth = _create_auth(timeout)  # ← Reads ~/.quilt/auth.json
        _session = _create_session(auth)
    return _session

def _create_auth(timeout=None):
    url = get_registry_url()  # ← Reads ~/.quilt/config.yml
    contents = _load_auth()    # ← Reads ~/.quilt/auth.json
    auth = contents.get(url)
    return auth  # {'access_token': '...', 'refresh_token': '...', 'expires_at': ...}

def _create_session(auth):
    session = requests.Session()
    if auth is not None:
        session.headers["Authorization"] = f"Bearer {auth['access_token']}"  # ← KEY
    return session
```

**Design Assumptions:**

1. **File-based authentication** - Credentials in `~/.quilt/auth.json`
2. **Writable filesystem** - Can persist session files
3. **Global state** - One session per process (`_session` module variable)
4. **Single user** - One catalog, one set of credentials
5. **Interactive login** - User runs `quilt3 login` to create session files
6. **Long-lived process** - Session persists across operations

### MCP Server's Reality: Multi-Tenant HTTP Service

**Operational Requirements:**

1. **Read-only filesystem** - Container runs with `--read-only` flag
2. **Per-request auth** - Each HTTP request has different JWT credentials
3. **Stateless** - Container restarts, no persistent state
4. **Multi-tenant** - Concurrent requests from different users/catalogs
5. **Programmatic auth** - No interactive login, credentials in JWT
6. **Short-lived contexts** - Request scope, not process scope

**These are fundamentally incompatible.**

---

## Why `quilt3.config()` Is Useless

The JWT auth service calls [jwt_auth_service.py:161](../../src/quilt_mcp/services/jwt_auth_service.py#L161):

```python
quilt3.config(catalog_url)  # ← What does this actually do?
```

From quilt3 documentation:

```python
def config(*catalog_url, **config_values):
    """Set or read the QUILT configuration.

    To trigger autoconfiguration, call with just the navigator URL:
        quilt3.config('https://YOUR-CATALOG-URL.com')
    """
```

**What it actually does:**

1. Writes `registryUrl: <url>` to `~/.quilt/config.yml`
2. Returns the config object

**What it does NOT do:**

- ❌ Authenticate with the catalog
- ❌ Store any credentials
- ❌ Create a session
- ❌ Set bearer tokens
- ❌ Configure any runtime state

In read-only mode, **it can't even write the config file**, so it does literally nothing.

---

## The Two Parallel Authentication Systems

The MCP server has inadvertently created **two separate authentication mechanisms** that never talk to each other:

### System 1: quilt3's File-Based Auth (Original)

```
User runs: quilt3 catalog login
     ↓
Creates: ~/.quilt/auth.json
     ↓
Contains: {
  "https://catalog.com": {
    "access_token": "...",
    "refresh_token": "...",
    "expires_at": 1234567890
  }
}
     ↓
quilt3.session.get_session() reads this file
     ↓
Creates requests.Session with Authorization header
     ↓
✅ Works in stdio mode (has file access)
```

**Used by:**

- `QuiltService.get_session()` → [quilt_service.py:267](../../src/quilt_mcp/services/quilt_service.py#L267)
- Search backend → [elasticsearch.py:228](../../src/quilt_mcp/search/backends/elasticsearch.py#L228)
- Package operations → Various locations

### System 2: Runtime Metadata (JWT Mode)

```
HTTP request with Bearer token
     ↓
JWT middleware validates token
     ↓
JWTAuthService extracts catalog_token from JWT
     ↓
Stores in runtime_context.metadata:
{
  "catalog_token": "...",
  "catalog_url": "https://catalog.com",
  "registry_url": "https://catalog.com"
}
     ↓
❌ But nothing reads this for authentication!
     ↓
quilt3.session.get_session() still looks for ~/.quilt/auth.json
     ↓
❌ Fails in stateless mode (no file)
```

**Used by:**

- Nothing! It's stored but never retrieved for authentication.

### The Disconnect

```
┌─────────────────────────────────────────────────────────────┐
│ JWT Request comes in                                         │
│   catalog_token: "abc123..."                                 │
└─────────────────────────────────────────────────────────────┘
                          │
                          ├──→ JWTAuthService
                          │    └─→ update_runtime_metadata(catalog_token="abc123")
                          │        ✅ Token stored in ContextVar
                          │
                          └──→ Search backend calls:
                               QuiltService.get_session()
                                    │
                                    └─→ quilt3.session.get_session()
                                         │
                                         └─→ _create_auth()
                                              │
                                              └─→ _load_auth()
                                                   │
                                                   └─→ Reads ~/.quilt/auth.json
                                                        │
                                                        └─→ ❌ File doesn't exist
                                                             │
                                                             └─→ Returns None
                                                                  │
                                                                  └─→ Unauthenticated session
```

---

## Why the Shallow Fix Won't Work

The [previous spec](./20-search-bug-root-cause-analysis.md#solution-approaches) proposed:

```python
def get_registry_url(self) -> str | None:
    # Check runtime metadata first
    metadata = get_runtime_metadata()
    registry_url = metadata.get("registry_url")
    if registry_url:
        return registry_url

    # Fall back to quilt3 session
    return quilt3.session.get_registry_url()
```

**Problem:** This only fixes the URL check. The search backend also calls:

```python
session = self.quilt_service.get_session()  # ← [elasticsearch.py:228]
resp = session.post(f"{registry_url}/graphql", json={"query": "..."})
```

Even with the correct registry URL, **`get_session()` returns an unauthenticated `requests.Session`** because:

1. `QuiltService.get_session()` → calls `quilt3.session.get_session()`
2. quilt3 calls `_create_auth()` → reads `~/.quilt/auth.json`
3. File doesn't exist → returns `None`
4. `_create_session(None)` → creates session **without Authorization header**
5. GraphQL request → **401 Unauthorized**

The shallow fix addresses the symptom (session availability check) but not the disease (unauthenticated requests).

---

## Scope of Impact

This bug affects **any tool that needs catalog authentication**, not just search:

### Currently Broken in Stateless Mode

1. **search_catalog** - Needs authenticated Elasticsearch queries
2. **package_browse** - Needs authenticated GraphQL queries for package listing
3. **bucket_objects_list** (with catalog buckets) - May need catalog-based permissions
4. Any future tool using `QuiltService.get_session()`

### Working By Accident

Tools that use S3 directly (via boto3 session from JWT) work fine:

- `bucket_object_info` - Uses S3 API directly
- `bucket_object_download` - Uses S3 presigned URLs
- `bucket_objects_put` - Uses boto3 session from JWT

The architecture is **split-brain**: S3 operations use JWT credentials correctly, but catalog operations are still trying to use quilt3's file-based auth.

---

## The Even Deeper Problem: Two Runtime Models

The authentication mismatch is just one layer. **QuiltService must abstract over TWO COMPLETELY DIFFERENT RUNTIME ENVIRONMENTS:**

### Runtime 1: Stdio Mode (Desktop)

```
User has:
- AWS credentials (via ~/.aws/ or IAM role)
- Quilt3 session (via ~/.quilt/auth.json)

Execution model:
- Direct S3 access via boto3
- Local quilt3 API for package operations
- Can read/write local filesystem
- Long-lived Python process

Data access path:
User → quilt3 API → boto3 → S3
     ↓
     └→ Local session files
```

**Key characteristic:** The Python process has **direct AWS credentials** and can make S3 API calls directly.

### Runtime 2: HTTP Mode (Stateless)

```
User has:
- JWT with catalog credentials (NOT AWS credentials)
- No local filesystem access
- No boto3 credentials

Execution model:
- Registry-mediated S3 access via GraphQL/presigned URLs
- Catalog API for package operations
- Read-only filesystem
- Short-lived request context

Data access path:
User → HTTP/JWT → Registry GraphQL → S3 presigned URLs → S3
     ↓
     └→ ContextVar runtime metadata
```

**Key characteristic:** The process has **catalog credentials** but may not have direct AWS
credentials. All S3 access must go through the registry (GraphQL queries → presigned URLs → S3).

### The Bifurcation

QuiltService isn't just choosing between two auth sources - it's **choosing between two
completely different execution models**:

| Operation           | Stdio Mode                  | HTTP Mode                            |
| ------------------- | --------------------------- | ------------------------------------ |
| **S3 Access**       | `boto3.client('s3')` direct | Registry GraphQL → presigned URLs    |
| **Package queries** | `quilt3.Package.browse()`   | Registry GraphQL API                 |
| **Search**          | Local quilt3 + Elasticsearch| Registry GraphQL → Elasticsearch     |
| **Credentials**     | AWS (via IAM/~/.aws)        | Catalog token (from JWT)             |
| **Session storage** | `~/.quilt/auth.json`        | `ContextVar` runtime metadata        |

**This means QuiltService can't just "use runtime metadata for auth" - it needs to fundamentally change HOW IT EXECUTES OPERATIONS based on the runtime.**

### Example: Package Browsing

**Stdio mode:**

```python
# Direct quilt3 API usage
pkg = quilt3.Package.browse(package_name, registry=registry_url)
# quilt3 uses local AWS credentials to access S3 directly
```

**HTTP mode (what's needed):**

```python
# Must use GraphQL instead
query = """
  query GetPackage($name: String!, $registry: String!) {
    package(name: $name, registry: $registry) {
      hash
      entries {
        logical_key
        physical_key
        size
      }
    }
  }
"""
response = session.post(f"{registry_url}/graphql", json={"query": query})
# Registry returns metadata, then provides presigned URLs for actual data
```

The quilt3 API **doesn't work at all** in HTTP mode because it assumes direct S3 access.

### Wait, It Gets Worse

In HTTP mode, the MCP server **may not even have AWS credentials**. The JWT might contain:

- `catalog_token` - For authenticating to the catalog/registry
- `role arn` + `session_tags` - For assuming an AWS role to get temporary S3 credentials

But there's no guarantee. A JWT could have:

- ✅ Catalog credentials (for registry API access)
- ❌ No AWS credentials at all

In that case, **all S3 access must go through the registry** using presigned URLs from GraphQL
queries. The Python process cannot make direct `boto3.client('s3')` calls.

This means operations like:

- `quilt3.Package.browse()` - Tries to list S3 objects directly → **fails**
- `quilt3.Package.install()` - Tries to download from S3 directly → **fails**
- Search Elasticsearch directly - Tries to query ES endpoint directly → **fails** (auth issue)

**Every catalog/S3 operation needs two execution paths:**

1. **Stdio mode** - Direct AWS/S3/quilt3 API calls
2. **HTTP mode** - Registry GraphQL API → presigned URLs → indirect access

---

## Why Runtime Metadata Uses ContextVar

The runtime metadata system uses Python's `ContextVar` for **per-request isolation**:

```python
# runtime_context.py
_runtime_context_var: ContextVar[RuntimeContextState] = ContextVar(
    "quilt_runtime_context",
    default=_default_state,
)
```

**Why this matters:**

In HTTP mode, multiple requests are handled concurrently:

```
Request 1: User A → Catalog X → catalog_token="token_X"
Request 2: User B → Catalog Y → catalog_token="token_Y"
Request 3: User A → Catalog Z → catalog_token="token_Z"
```

`ContextVar` ensures each request sees only its own credentials. **This is the right design** for multi-tenant stateless services.

The problem is that **quilt3 uses global module state** (`_session`), which is wrong for multi-tenant scenarios. This creates a third incompatibility layer beyond authentication and execution models.

---

## Summary of Architectural Problems

The search bug exposed **three layers of architectural mismatch** between quilt3 (single-user CLI) and the MCP server (multi-tenant HTTP service):

### Layer 1: Authentication Storage

| Aspect | quilt3 | MCP Server (HTTP mode) |
| ------ | ------ | ---------------------- |
| Credential storage | `~/.quilt/auth.json` file | `ContextVar` runtime metadata |
| Filesystem | Writable | Read-only |
| Session scope | Process-global | Per-request |

**Problem:** `quilt3.config()` does nothing useful. JWT credentials stored in runtime metadata are
never used by quilt3's session API.

### Layer 2: Execution Model

| Aspect | quilt3 | MCP Server (HTTP mode) |
| ------ | ------ | ---------------------- |
| S3 access | Direct `boto3` calls | Registry GraphQL → presigned URLs |
| Package ops | `quilt3.Package.browse()` | Registry GraphQL API |
| Search | Direct Elasticsearch | Registry-mediated search |
| AWS creds | Required | May not exist |

**Problem:** quilt3 APIs assume direct AWS/S3 access. In HTTP mode, the process may only have
catalog credentials, requiring all operations to go through the registry.

### Layer 3: Concurrency Model

| Aspect | quilt3 | MCP Server (HTTP mode) |
| ------ | ------ | ---------------------- |
| Session state | Global `_session` variable | Per-request `ContextVar` |
| Concurrent users | Not supported | Required |
| Multi-catalog | Not supported | Required |

**Problem:** quilt3's global state is unsafe for concurrent requests from different
users/catalogs.

### The Core Issue

**QuiltService tried to use quilt3 as a thin wrapper**, assuming it could just "configure" quilt3
differently. But quilt3 is fundamentally designed for a different environment. The MCP server needs:

1. **Dual authentication paths** - Runtime metadata (HTTP) vs. file-based (stdio)
2. **Dual execution paths** - Registry GraphQL (HTTP) vs. direct quilt3/boto3 (stdio)
3. **Per-request isolation** - `ContextVar` state instead of global state

**The bug isn't a missing authentication call - it's that the entire architecture assumes the wrong
runtime model.**

---

## Conclusion

The search bug is a **symptom of systemic architectural incompatibility**:

- The MCP server has two parallel authentication systems that don't communicate
- quilt3 APIs don't work in stateless/multi-tenant environments
- Every catalog/S3 operation needs dual implementation paths
- Current QuiltService abstraction is insufficient - it only wraps quilt3 instead of abstracting over two fundamentally different runtimes

**This affects:** search_catalog, package_browse, and any future catalog-dependent tools.

**Scope:** Not a localized bug fix - requires architectural changes to QuiltService to properly
abstract over stdio vs HTTP runtime models.
