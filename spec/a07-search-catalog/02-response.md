# Search Catalog Tool: Response to Architecture Analysis

**Date:** 2025-11-10
**Branch:** search-catalog-fixes
**Responding to:** [01-analysis.md](01-analysis.md)

---

## Executive Summary

This document addresses three critical concerns raised about the `search_catalog` tool architecture:

1. **Purpose Clarity**: The tool's primary purpose is to find relevant objects and packages using Elasticsearch indices, not to be a general-purpose S3 listing tool
2. **Error Handling Philosophy**: The tool should succeed intelligently or fail concretely with actionable guidance, never returning "fake answers"
3. **Backend Documentation**: Clear explanation of what the three backends are, when they work, and why they exist

This response proposes a fundamental architectural shift: **from parallel multi-backend federation to smart single-backend selection with explicit fallback**.

---

## Concern 1: What Is This Tool Actually For?

### Current State: Identity Crisis

The current implementation tries to be three things at once:

1. **Elasticsearch search interface** (via `quilt3.Bucket.search()`)
2. **GraphQL query interface** (for Enterprise catalogs)
3. **S3 listing fallback** (when the above fail)

**Problem**: This creates confusion about the tool's purpose and when it should succeed vs. fail.

### Proposed: Clear Purpose Definition

**Primary Purpose**: Search Quilt catalog indices (Elasticsearch/GraphQL) to find packages and objects by metadata, content, and relationships.

**Not For**:

- Raw S3 listing (use `bucket_objects_list` instead)
- File system exploration (use `bucket_objects_list` with prefix)
- Brute-force object discovery (use dedicated bucket tools)

### Decision Tree

```
User wants to search by...
├─ Metadata/content/relationships → search_catalog() ✓
├─ Known prefix/path → bucket_objects_list() ✓
└─ "See what's there" → bucket_objects_list() ✓
```

---

## Concern 2: Fail Concretely vs. Fake Answers

### Current State: Silent Degradation

The current implementation has problematic failure modes:

#### Example 1: The 403 S3 Fallback

```
User query: "packages about genomics"
ES backend: 403 Forbidden (auth issue)
GraphQL backend: Not available (not Enterprise)
S3 backend: Lists random S3 objects with "genomics" in key
Result: Returns S3 keys as if they were search results ❌
```

**Problem**: S3 listing is not equivalent to catalog search. It's a "fake answer."

#### Example 2: The Silent Authentication Failure

```
User query: "find CSV files"
All backends: Fail initialization (not authenticated)
Result: Empty results, "success": true ✓
User sees: "No results found" (not true - query wasn't executed) ❌
```

**Problem**: Failure to search is reported as successful empty search.

### Proposed: Explicit Failure with Guidance

#### Principle: Fail Fast, Fail Clear

**Rule 1**: If catalog indices are unavailable, the tool should fail, not return S3 listings.

**Rule 2**: Failure messages must include:

- What went wrong (specific error)
- Why it went wrong (root cause classification)
- How to fix it (actionable steps)
- What to use instead (alternative tools)

#### Example Failure Messages

**Authentication Failure**:

```json
{
  "success": false,
  "error": "Search catalog requires authentication",
  "error_category": "authentication",
  "details": {
    "cause": "No active Quilt session found",
    "authenticated": false,
    "catalog_url": null
  },
  "fix": {
    "required_action": "Authenticate with Quilt catalog",
    "command": "quilt3.login()",
    "documentation": "https://docs.quiltdata.com/..."
  },
  "alternatives": {
    "bucket_objects_list": "List objects in bucket without authentication (if bucket is public)",
    "bucket_objects_search": "Search S3 bucket objects directly (requires AWS credentials)"
  }
}
```

**Permission Failure**:

```json
{
  "success": false,
  "error": "Search catalog permission denied",
  "error_category": "permission",
  "details": {
    "cause": "HTTP 403: Catalog search not enabled for user role",
    "authenticated": true,
    "catalog_url": "https://catalog.example.com",
    "user_role": "viewer"
  },
  "fix": {
    "required_action": "Request catalog search permissions",
    "contact": "Contact your Quilt administrator to enable search for your role",
    "required_role": "One of: admin, editor, data-scientist"
  },
  "alternatives": {
    "package_browse": "Browse known packages directly by name",
    "bucket_objects_list": "List objects in specific bucket prefixes"
  }
}
```

**Not Available (Expected)**:

```json
{
  "success": false,
  "error": "Search catalog not available in this deployment",
  "error_category": "not_applicable",
  "details": {
    "cause": "This Quilt deployment does not have Elasticsearch search enabled",
    "deployment_type": "basic",
    "feature_required": "Enterprise Elasticsearch or GraphQL search"
  },
  "fix": {
    "required_action": "Use alternative search methods or upgrade deployment",
    "enterprise_feature": true
  },
  "alternatives": {
    "bucket_objects_list": "List and filter objects by prefix",
    "package_browse": "Browse packages by namespace",
    "workflow": "Use bucket_objects_list + filter locally for search-like functionality"
  }
}
```

---

## Concern 3: What Are The Three Backends?

### Backend Documentation

#### Backend 1: Elasticsearch via quilt3 Python API

**What It Is**:

- Wraps `quilt3.Bucket.search()` and `quilt3.search_packages()`
- Uses Elasticsearch indices maintained by Quilt catalog
- Searches package metadata, object metadata, and content

**When It Works**:

- ✅ User authenticated via `quilt3.login()`
- ✅ Quilt catalog has Elasticsearch enabled (standard in all hosted deployments)
- ✅ User role has search permissions

**When It Fails**:

- ❌ User not authenticated → `BackendStatus.UNAVAILABLE`
- ❌ Search disabled for user role → HTTP 403 → `BackendStatus.ERROR`
- ❌ Network issues → Timeout → `BackendStatus.ERROR`

**What It Searches**:

- Package names, descriptions, metadata
- Object logical keys, physical keys
- Object metadata (user-defined and system)
- Full-text content (if indexing enabled)

**Elasticsearch Indices Used**:

```
{bucket-name}-packages    # Package metadata index
{bucket-name}-objects     # Object metadata index
{bucket-name}-chunks      # Content chunks (full-text search)
```

**Query Capabilities**:

- Boolean queries (AND, OR, NOT)
- Phrase matching ("exact phrase")
- Wildcard patterns (file*.csv)
- Field-specific filters (ext:csv, size:>100MB)
- Full-text search across object contents

---

#### Backend 2: Enterprise GraphQL API

**What It Is**:

- Direct GraphQL queries to Quilt Enterprise catalog backend
- Bypasses Python `quilt3` library
- Uses authenticated HTTP session

**When It Works**:

- ✅ User authenticated via `quilt3.login()`
- ✅ Catalog is Enterprise tier
- ✅ GraphQL API endpoint is available (`/graphql`)

**When It Fails**:

- ❌ User not authenticated → `BackendStatus.UNAVAILABLE`
- ❌ Not Enterprise catalog → HTTP 404 on `/graphql` → `BackendStatus.NOT_APPLICABLE`
- ❌ GraphQL disabled/misconfigured → `BackendStatus.ERROR`

**What It Searches**:

- Package metadata via `packages` query
- Bucket configurations via `bucketConfigs`
- User and role information
- Package relationships

**GraphQL Schema Subset Used**:

```graphql
query SearchPackages($query: String!) {
  packages(query: $query) {
    name
    metadata
    modified
    hash
  }
}

query BucketConfigs {
  bucketConfigs {
    name
    title
    description
  }
}
```

**Query Capabilities**:

- Structured field queries
- Metadata filtering
- Relationship traversal
- Aggregations

**Why This Exists Separately**:

- Some Enterprise features only available via GraphQL
- Potential performance advantages for certain query types
- Future-proofing for GraphQL-only features

---

#### Backend 3: S3 Direct Listing (Fallback)

**What It Is**:

- Direct AWS S3 API calls via boto3
- Lists and filters objects by key prefix
- No metadata search, no content search

**When It Works**:

- ✅ AWS credentials available (environment, profile, IAM role)
- ✅ User has S3 ListBucket permission
- ✅ Bucket exists and is accessible

**When It Fails**:

- ❌ No AWS credentials → `BackendStatus.UNAVAILABLE`
- ❌ No S3 permissions → `BackendStatus.ERROR`
- ❌ Bucket doesn't exist → `BackendStatus.ERROR`

**What It Searches**:

- S3 object keys only (file paths)
- No metadata, no content, no relationships

**S3 API Operations Used**:

```python
# List objects with prefix
s3.list_objects_v2(
    Bucket=bucket,
    Prefix=prefix,
    MaxKeys=1000
)

# Filter by key pattern (client-side)
# No server-side search capability
```

**Query Capabilities**:

- Prefix filtering only (e.g., `data/2024/`)
- Key substring matching (client-side)
- File extension filtering (client-side)
- **NO metadata or content search**

**Why This Exists**:

- **Historical reasons** (fallback when search unavailable)
- **Edge case coverage** (public buckets, non-catalog S3)

**⚠️ Problem**: This is not equivalent to catalog search and should not be presented as such.

---

### Backend Comparison Matrix

| Capability | Elasticsearch | GraphQL | S3 Listing |
|------------|--------------|---------|------------|
| **Search Type** | Index-based | Query-based | List + Filter |
| **Metadata Search** | ✅ Full | ✅ Full | ❌ None |
| **Content Search** | ✅ Full-text | ❌ No | ❌ No |
| **Package Search** | ✅ Yes | ✅ Yes | ❌ No |
| **Relationship Traversal** | ⚠️ Limited | ✅ Full | ❌ No |
| **Performance** | Fast (indexed) | Fast (optimized) | Slow (list all) |
| **Requires Quilt Auth** | ✅ Yes | ✅ Yes | ❌ No (AWS only) |
| **Requires Enterprise** | ❌ No | ✅ Yes | ❌ No |
| **Deployment Coverage** | ~95% | ~20% | 100% |

---

## Proposed Architecture Changes

### Change 1: Remove S3 Backend from `search_catalog`

**Rationale**: S3 listing is not catalog search. It returns different data with different semantics.

**Impact**:

- `search_catalog` only uses Elasticsearch or GraphQL
- If neither available → Explicit failure with guidance
- Users directed to `bucket_objects_list` for S3 exploration

**Migration Path**:

```python
# Current (confusing)
search_catalog("CSV files")
→ Falls back to S3 listing
→ Returns S3 keys (not packages)

# Proposed (explicit)
search_catalog("CSV files")
→ Fails with clear error
→ Suggests: "Use bucket_objects_list for S3 key filtering"
```

### Change 2: Smart Single-Backend Selection

**Current**: Try all backends in parallel, aggregate results

**Proposed**: Select one backend based on deployment detection

```python
def select_search_backend() -> SearchBackend:
    """Select the best available search backend."""

    # 1. Check if authenticated
    if not quilt_service.is_authenticated():
        raise AuthenticationRequired(
            message="Search catalog requires authentication",
            fix="Run quilt3.login()",
            alternatives=["bucket_objects_list"]
        )

    # 2. Try GraphQL (Enterprise features)
    graphql = EnterpriseGraphQLBackend()
    if graphql.status == BackendStatus.AVAILABLE:
        return graphql

    # 3. Try Elasticsearch (standard)
    es = Quilt3ElasticsearchBackend()
    if es.status == BackendStatus.AVAILABLE:
        return es

    # 4. No search available → fail explicitly
    raise SearchNotAvailable(
        message="Catalog search not available in this deployment",
        details=get_backend_diagnostics(),
        alternatives=["bucket_objects_list", "package_browse"]
    )
```

**Benefits**:

- Clearer semantics (one search backend, one result format)
- Faster execution (no parallel fan-out)
- Easier debugging (single backend status)
- No fake answers (no S3 fallback)

### Change 3: Explicit Backend Status Tool

**New Tool**: `get_search_backend_status()`

```python
{
  "authenticated": true,
  "catalog_url": "https://catalog.example.com",
  "search_backend": {
    "type": "elasticsearch",
    "status": "available",
    "capabilities": [
      "metadata_search",
      "content_search",
      "package_search",
      "wildcard_patterns"
    ]
  },
  "alternate_backends": {
    "graphql": {
      "status": "not_applicable",
      "reason": "Not an Enterprise catalog"
    },
    "s3_direct": {
      "status": "available",
      "note": "Use bucket_objects_list for S3 key filtering"
    }
  },
  "recommendations": [
    "Elasticsearch backend is ready for catalog search",
    "Use search_catalog() for package/metadata search",
    "Use bucket_objects_list() for S3 key exploration"
  ]
}
```

---

## Implementation Plan

### Phase 1: Documentation & Classification (Week 1)

#### 1.1 Document Backend Purposes

- ✅ Create backend comparison matrix
- ✅ Document when each backend works
- ✅ Explain query capabilities per backend

#### 1.2 Classify Error Categories

```python
class ErrorCategory(Enum):
    AUTHENTICATION = "authentication"      # User not logged in
    AUTHORIZATION = "authorization"        # User lacks permissions
    NOT_APPLICABLE = "not_applicable"      # Feature not in this deployment
    NETWORK = "network"                    # Connection issues
    CONFIGURATION = "configuration"        # Misconfigured backend
    UNKNOWN = "unknown"                    # Unexpected errors
```

#### 1.3 Define Error Response Schema

```python
@dataclass
class SearchError:
    success: bool = False
    error: str                            # Human-readable message
    error_category: ErrorCategory         # Classified error type
    details: Dict[str, Any]               # Diagnostic information
    fix: Dict[str, str]                   # How to resolve
    alternatives: Dict[str, str]          # Alternative tools
```

---

### Phase 2: Remove S3 Backend (Week 1-2)

#### 2.1 Mark S3 Backend as Deprecated

```python
class S3FallbackBackend(SearchBackend):
    """DEPRECATED: S3 listing is not equivalent to catalog search.

    Use bucket_objects_list tool instead for S3 key exploration.
    This backend will be removed in v0.11.0.
    """

    def __init__(self):
        super().__init__(BackendType.S3_DEPRECATED)
        self._update_status(
            BackendStatus.NOT_APPLICABLE,
            "S3 listing removed from search_catalog. Use bucket_objects_list instead."
        )
```

#### 2.2 Update Backend Registry

```python
def _initialize_backends(self):
    """Initialize search backends (catalog search only)."""
    # Elasticsearch backend (standard)
    es_backend = Quilt3ElasticsearchBackend()
    self.registry.register(es_backend)

    # GraphQL backend (Enterprise)
    graphql_backend = EnterpriseGraphQLBackend()
    self.registry.register(graphql_backend)

    # NOTE: S3 backend removed - use bucket_objects_list tool instead
```

#### 2.3 Update Tests

- Remove S3 backend test cases from `test_unified_search.py`
- Add tests for explicit failure when no catalog search available
- Add tests for error message quality

---

### Phase 3: Smart Backend Selection (Week 2)

#### 3.1 Implement Selection Logic

```python
def _select_primary_backend(self) -> SearchBackend:
    """Select the best available search backend.

    Raises:
        AuthenticationRequired: User not authenticated
        SearchNotAvailable: No search backend available
    """
    # Check authentication first
    if not self.quilt_service.is_authenticated():
        raise AuthenticationRequired(...)

    # Prefer GraphQL (more features)
    graphql = self.registry.get_backend(BackendType.GRAPHQL)
    if graphql and graphql.status == BackendStatus.AVAILABLE:
        return graphql

    # Fallback to Elasticsearch (standard)
    es = self.registry.get_backend(BackendType.ELASTICSEARCH)
    if es and es.status == BackendStatus.AVAILABLE:
        return es

    # No backend available → fail explicitly
    raise SearchNotAvailable(
        message="Catalog search not available",
        details=self._get_backend_diagnostics(),
        alternatives={
            "bucket_objects_list": "List and filter S3 objects by prefix",
            "package_browse": "Browse packages by name"
        }
    )
```

#### 3.2 Update Search Flow

```python
async def search(self, query: str, **kwargs) -> Dict[str, Any]:
    """Execute catalog search using best available backend."""
    start_time = time.time()

    try:
        # Select single backend (may raise exception)
        backend = self._select_primary_backend()

        # Parse query
        analysis = parse_query(query, kwargs.get("scope"), kwargs.get("target"))

        # Execute search on selected backend
        response = await backend.search(query, **kwargs)

        # Return results with backend info
        return {
            "success": True,
            "backend_used": backend.backend_type.value,
            "results": response.results,
            "query_time_ms": (time.time() - start_time) * 1000,
            ...
        }

    except AuthenticationRequired as e:
        return e.to_dict()  # Structured error response

    except SearchNotAvailable as e:
        return e.to_dict()  # Structured error response

    except Exception as e:
        return SearchError(
            error="Unexpected search error",
            error_category=ErrorCategory.UNKNOWN,
            details={"exception": str(e)},
            ...
        ).to_dict()
```

---

### Phase 4: Enhanced Error Handling (Week 2-3)

#### 4.1 Structured Exception Classes

```python
class SearchException(Exception):
    """Base class for all search errors."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        details: Dict[str, Any],
        fix: Dict[str, str],
        alternatives: Dict[str, str]
    ):
        self.message = message
        self.category = category
        self.details = details
        self.fix = fix
        self.alternatives = alternatives

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            "success": False,
            "error": self.message,
            "error_category": self.category.value,
            "details": self.details,
            "fix": self.fix,
            "alternatives": self.alternatives
        }

class AuthenticationRequired(SearchException):
    """User must authenticate before searching."""

    def __init__(self):
        super().__init__(
            message="Search catalog requires authentication",
            category=ErrorCategory.AUTHENTICATION,
            details={
                "cause": "No active Quilt session found",
                "authenticated": False
            },
            fix={
                "required_action": "Authenticate with Quilt catalog",
                "command": "quilt3.login()",
                "documentation": "https://docs.quiltdata.com/..."
            },
            alternatives={
                "bucket_objects_list": "List objects in public buckets (no auth required)"
            }
        )

class SearchNotAvailable(SearchException):
    """Search feature not available in this deployment."""

    def __init__(self, details: Dict[str, Any]):
        super().__init__(
            message="Catalog search not available in this deployment",
            category=ErrorCategory.NOT_APPLICABLE,
            details=details,
            fix={
                "required_action": "Use alternative search methods",
                "enterprise_feature": "Elasticsearch or GraphQL search required"
            },
            alternatives={
                "bucket_objects_list": "List and filter S3 objects",
                "package_browse": "Browse known packages by name"
            }
        )
```

#### 4.2 Backend-Specific Error Handling

```python
class Quilt3ElasticsearchBackend(SearchBackend):
    async def search(self, query: str, **kwargs) -> BackendResponse:
        try:
            # Execute search via quilt3
            results = self.quilt_service.search(query, **kwargs)
            return self._format_response(results)

        except requests.HTTPError as e:
            if e.response.status_code == 403:
                raise SearchException(
                    message="Search permission denied",
                    category=ErrorCategory.AUTHORIZATION,
                    details={
                        "http_status": 403,
                        "user_role": self._get_user_role(),
                        "catalog_url": self.quilt_service.get_registry_url()
                    },
                    fix={
                        "required_action": "Request search permissions from administrator",
                        "required_role": "editor, data-scientist, or admin"
                    },
                    alternatives={
                        "package_browse": "Browse public packages",
                        "bucket_objects_list": "List specific bucket prefixes"
                    }
                )
            elif e.response.status_code == 401:
                raise AuthenticationRequired()
            else:
                raise  # Re-raise for unexpected HTTP errors
```

---

### Phase 5: Backend Status Diagnostic Tool (Week 3)

#### 5.1 New MCP Tool Implementation

```python
@tool
def get_search_backend_status() -> Dict[str, Any]:
    """Get detailed status of search backends and capabilities.

    Returns:
        Comprehensive backend status and recommendations
    """
    engine = get_search_engine()
    quilt_service = QuiltService()

    # Check authentication
    is_authenticated = quilt_service.is_authenticated()
    catalog_url = quilt_service.get_registry_url() if is_authenticated else None

    # Get backend statuses
    backends = {}
    for backend_type, backend in engine.registry._backends.items():
        backends[backend_type.value] = {
            "status": backend.status.value,
            "last_error": backend.last_error,
            "capabilities": backend.get_capabilities(),
            "available": backend.status == BackendStatus.AVAILABLE
        }

    # Determine primary backend
    primary_backend = None
    try:
        primary = engine._select_primary_backend()
        primary_backend = primary.backend_type.value
    except SearchException:
        primary_backend = None

    # Generate recommendations
    recommendations = _generate_recommendations(
        is_authenticated=is_authenticated,
        backends=backends,
        primary_backend=primary_backend
    )

    return {
        "authentication": {
            "is_authenticated": is_authenticated,
            "catalog_url": catalog_url,
            "user_email": quilt_service.get_user_email() if is_authenticated else None
        },
        "search_backend": {
            "primary": primary_backend,
            "status": "available" if primary_backend else "unavailable"
        },
        "all_backends": backends,
        "recommendations": recommendations
    }

def _generate_recommendations(
    is_authenticated: bool,
    backends: Dict[str, Any],
    primary_backend: Optional[str]
) -> List[str]:
    """Generate actionable recommendations based on status."""
    recommendations = []

    if not is_authenticated:
        recommendations.append(
            "⚠️ Not authenticated. Run quilt3.login() to enable catalog search."
        )
        return recommendations

    if primary_backend:
        recommendations.append(
            f"✅ Search ready using {primary_backend} backend"
        )
        recommendations.append(
            "💡 Use search_catalog() for package/metadata search"
        )
    else:
        recommendations.append(
            "⚠️ Catalog search not available in this deployment"
        )
        recommendations.append(
            "💡 Use bucket_objects_list() for S3 object exploration"
        )
        recommendations.append(
            "💡 Use package_browse() to browse known packages"
        )

    return recommendations
```

---

## Success Metrics

### Metric 1: Error Message Quality

**Target**: 100% of failures include actionable guidance

**Measurement**:

```python
def test_error_quality():
    """All errors must have required fields."""
    errors = collect_all_error_responses()

    for error in errors:
        assert "error" in error                    # Message
        assert "error_category" in error           # Classification
        assert "fix" in error                      # How to resolve
        assert "alternatives" in error             # What to use instead
        assert len(error["fix"]) > 0              # Non-empty guidance
        assert len(error["alternatives"]) > 0     # Non-empty alternatives
```

### Metric 2: No Fake Answers

**Target**: 0% of S3 listings presented as search results

**Measurement**:

```python
def test_no_s3_fallback():
    """S3 backend must not be used in search_catalog."""
    result = search_catalog("test query")

    if not result["success"]:
        # Failure is acceptable
        pass
    else:
        # Success must be from Elasticsearch or GraphQL
        assert result["backend_used"] in ["elasticsearch", "graphql"]
        assert result["backend_used"] != "s3"
```

### Metric 3: Authentication Detection

**Target**: 100% authentication failures detected before search execution

**Measurement**:

```python
def test_auth_detection():
    """Authentication failures must be detected upfront."""
    with mock_no_auth():
        result = search_catalog("test query")

        assert result["success"] is False
        assert result["error_category"] == "authentication"
        assert "quilt3.login()" in result["fix"]["command"]
```

### Metric 4: Clear Alternative Guidance

**Target**: Every failure suggests specific alternative tools

**Measurement**:

```python
def test_alternative_suggestions():
    """All failures must suggest alternatives."""
    failures = [
        mock_auth_failure(),
        mock_permission_failure(),
        mock_not_available_failure()
    ]

    for failure in failures:
        assert "alternatives" in failure
        alternatives = failure["alternatives"]

        # Must suggest at least one alternative tool
        assert len(alternatives) >= 1

        # Alternatives must be valid MCP tool names
        valid_tools = ["bucket_objects_list", "package_browse", "bucket_objects_search"]
        assert any(alt in valid_tools for alt in alternatives.keys())
```

---

## Migration Guide for Users

### For AI Agents

**Old Behavior**:

```python
# Agent sees query "find CSV files"
# Tries search_catalog()
# Gets S3 listing as "results"
# Presents S3 keys as if they were search results ❌
```

**New Behavior**:

```python
# Agent sees query "find CSV files"
# Tries search_catalog()
# Gets explicit failure with error_category="not_available"
# Sees alternatives: ["bucket_objects_list"]
# Switches to bucket_objects_list() ✓
# Presents results clearly as "S3 objects matching pattern" ✓
```

### For Human Users

**Old Behavior**:

```python
>>> search_catalog("genomics packages")
{
  "success": true,
  "results": [
    {"key": "s3://bucket/genomics-data.csv", ...}  # S3 key, not package
  ],
  "backend_used": "s3"
}
# User confused: "Is this a package or a file?" ❌
```

**New Behavior**:

```python
>>> search_catalog("genomics packages")
{
  "success": false,
  "error": "Search catalog requires authentication",
  "fix": {
    "command": "quilt3.login()",
    "documentation": "https://..."
  },
  "alternatives": {
    "bucket_objects_list": "List S3 objects without authentication"
  }
}

>>> # User authenticates
>>> quilt3.login()

>>> # Try again
>>> search_catalog("genomics packages")
{
  "success": true,
  "results": [
    {
      "type": "package",
      "name": "genomics/reference-data",
      "metadata": {...}
    }
  ],
  "backend_used": "elasticsearch"
}
# Clear: This is a package ✓
```

---

## Appendices

### Appendix A: Backend Initialization Timing

**Current Problem**: Backends initialize at module load time

**Solution**: Lazy initialization at first search

```python
class SearchBackend(ABC):
    def __init__(self, backend_type: BackendType):
        self.backend_type = backend_type
        self._status = BackendStatus.UNKNOWN  # Not checked yet
        self._initialized = False

    async def ensure_initialized(self):
        """Ensure backend is initialized before use."""
        if not self._initialized:
            await self._check_availability()  # Subclass implements
            self._initialized = True

    async def search(self, query: str, **kwargs):
        """Search with lazy initialization."""
        await self.ensure_initialized()  # Check now, not at import
        return await self._execute_search(query, **kwargs)
```

**Benefits**:

- No failed initialization on cold start
- Authentication state checked when needed
- Backend can recover after auth without restart

### Appendix B: Error Response Schema (Full Spec)

```typescript
interface SearchErrorResponse {
  // Required fields
  success: false;
  error: string;                        // Human-readable message
  error_category: ErrorCategory;        // Enum classification

  // Diagnostic information
  details: {
    cause: string;                      // Root cause explanation
    authenticated: boolean;             // User auth status
    catalog_url: string | null;         // Current catalog
    [key: string]: any;                 // Additional context
  };

  // Resolution guidance
  fix: {
    required_action: string;            // What user must do
    command?: string;                   // Specific command to run
    documentation?: string;             // Link to docs
    contact?: string;                   // Who to contact for help
  };

  // Alternative approaches
  alternatives: {
    [tool_name: string]: string;        // Tool name → description
  };

  // Optional query context
  query?: string;                       // Original query
  scope?: string;                       // Search scope attempted
  target?: string;                      // Target attempted
}
```

### Appendix C: Testing Matrix

| Scenario | Expected Behavior | Validates |
|----------|-------------------|-----------|
| Not authenticated | `AuthenticationRequired` error | Auth detection |
| Authenticated, no search perms | `SearchException` 403 | Permission detection |
| Authenticated, search works | Success with ES/GraphQL | Happy path |
| Enterprise catalog | Uses GraphQL if available | Backend selection |
| Standard catalog | Uses Elasticsearch | Backend fallback |
| No backends available | `SearchNotAvailable` error | Graceful degradation |
| Network timeout | `SearchException` network | Network error handling |
| Invalid query syntax | `SearchException` configuration | Query validation |

---

## Conclusion

The proposed changes address all three concerns:

1. **✅ Clear Purpose**: `search_catalog` is for catalog search only, not S3 listing
2. **✅ Concrete Failures**: No fake answers, explicit errors with guidance
3. **✅ Backend Documentation**: Complete explanation of each backend's role

**Key Principles**:

- Fail fast and fail clear
- Never return fake answers
- Guide users to the right tool
- Make backend selection transparent

**Expected Outcomes**:

- Fewer user confusions about what search returns
- Better debugging when search doesn't work
- Clear separation between catalog search and S3 listing
- Actionable error messages for all failure modes

---

## Next Steps

1. **Review & Approve** this architectural direction
2. **Implement Phase 1** (documentation & classification)
3. **Implement Phase 2** (remove S3 backend)
4. **Test with real users** and gather feedback
5. **Iterate on error messages** based on common issues
6. **Complete Phases 3-5** for full implementation

**Timeline**: 3 weeks for complete implementation

**Breaking Changes**: Yes - S3 backend removal requires version bump (v0.11.0)

**Migration Support**: Deprecation warnings in v0.10.x, removal in v0.11.0
