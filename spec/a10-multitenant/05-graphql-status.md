# GraphQL Status - Quilt MCP Server

**Date:** 2026-01-28
**Context:** Multi-tenant and stateless deployment analysis

## Executive Summary

The Quilt MCP Server makes GraphQL calls to Quilt catalog endpoints for:
1. Bucket discovery (3 locations)
2. Object search with filtering and pagination
3. Generic GraphQL query execution

All GraphQL calls depend on `quilt3` configuration for authentication and registry URL resolution.

---

## GraphQL Endpoints Used

### Base Endpoint Construction
```
{registry_url}/graphql
```

Where `registry_url` is obtained from quilt3 configuration (typically `https://{stack}.quiltdata.com`).

---

## GraphQL Queries in Codebase

### 1. Bucket Discovery - bucketConfigs Query

**Purpose:** Discover which buckets are configured in the Quilt catalog stack

**Query:**
```graphql
query {
  bucketConfigs {
    name
    title  # only in some locations
  }
}
```

**Locations:**

#### Location 1: Permission Discovery Service
**File:** `src/quilt_mcp/services/permission_discovery.py:602`
```python
query = {"query": "query { bucketConfigs { name } }"}
response = session.post(graphql_url, json=query, timeout=http_config.SERVICE_TIMEOUT)
```

**Usage Context:**
- Called by `PermissionDiscoveryService._discover_buckets_via_graphql()`
- Used as fallback when S3 bucket listing fails
- Returns set of bucket names accessible via the catalog

#### Location 2: Stack Buckets Tool
**File:** `src/quilt_mcp/tools/stack_buckets.py:61`
```python
query = {"query": "query { bucketConfigs { name title } }"}
response = session.post(graphql_url, json=query, timeout=http_config.SERVICE_TIMEOUT)
```

**Usage Context:**
- Primary tool for discovering buckets in a Quilt stack
- Returns both bucket name and title (user-friendly display name)
- Used by LLMs to understand available data sources

#### Location 3: Elasticsearch Backend
**File:** `src/quilt_mcp/search/backends/elasticsearch.py:236`
```python
resp = session.post(
    f"{registry_url.rstrip('/')}/graphql",
    json={"query": "{ bucketConfigs { name } }"},
    timeout=30,
)
```

**Usage Context:**
- Called by `ElasticsearchBackend._fetch_all_buckets()`
- Used to populate bucket list for search operations
- Returns list of bucket names for cross-bucket searches

---

### 2. Object Search - objects Query

**Purpose:** Search for objects within buckets with filtering, pagination, and package linkage

**Query:**
```graphql
query($bucket: String!, $filter: ObjectFilterInput, $first: Int, $after: String) {
  objects(bucket: $bucket, filter: $filter, first: $first, after: $after) {
    edges {
      node {
        key
        size
        updated
        contentType
        extension
        package {
          name
          topHash
          tag
        }
      }
      cursor
    }
    pageInfo {
      endCursor
      hasNextPage
    }
  }
}
```

**Location:** `src/quilt_mcp/tools/search.py:515-525`

**Function:** `search_objects_graphql()`

**Parameters:**
- `bucket`: S3 bucket name or s3:// URI
- `object_filter`: Dictionary of filter fields (e.g., `{"extension": "csv"}`)
- `first`: Page size (default 100, max 1000)
- `after`: Pagination cursor

**Returns:**
- List of objects with metadata
- Package linkage information (if object is part of a package)
- Pagination info for fetching additional results

**Usage Context:**
- Enables catalog-aware object search
- Links objects to their parent packages
- Supports filtering by file type, size, date, etc.

---

### 3. Generic GraphQL Tool

**Purpose:** Execute arbitrary GraphQL queries against the catalog

**Location:** `src/quilt_mcp/tools/search.py:388`

**Function:** `search_graphql(query, variables)`

**Parameters:**
- `query`: GraphQL query string
- `variables`: Optional variables dictionary

**Returns:**
- `SearchGraphQLSuccess` with data
- `SearchGraphQLError` with error details

**Implementation:**
```python
resp = session.post(
    graphql_url,
    json={"query": query, "variables": variables or {}},
    timeout=http_config.SERVICE_TIMEOUT
)
```

**Usage Context:**
- Provides flexibility for custom queries
- Used for advanced catalog exploration
- Allows LLMs to construct specialized queries

---

## Authentication and Session Management

### Session Source
All GraphQL calls use the authenticated session from `quilt3`:

```python
session, graphql_url = _get_graphql_endpoint()
```

This function:
1. Gets the quilt3 session (`quilt3.session.get_session()`)
2. Extracts registry URL from quilt3 config
3. Constructs GraphQL endpoint URL: `{registry_url}/graphql`

### Authentication Flow
```
quilt3.login() → Session with credentials → GraphQL calls use session
```

### Timeout Configuration
- Standard timeout: `http_config.SERVICE_TIMEOUT` (from config)
- Elasticsearch backend: 30 seconds hardcoded

---

## Multi-Tenant Implications

### Current Architecture

1. **Single Registry per Process**
   - Each MCP server instance connects to ONE Quilt registry
   - Registry URL comes from quilt3 configuration
   - Cannot query multiple registries in the same process

2. **Stateless Compatibility**
   - ✅ GraphQL calls are stateless HTTP requests
   - ✅ No server-side session storage required
   - ✅ Each request includes authentication headers
   - ⚠️ Session object is cached in quilt3 singleton

3. **Registry Switching Challenges**
   - Changing registries requires reconfiguring quilt3
   - Session object is module-level singleton
   - Cannot easily support multiple registries concurrently

---

## Multi-Tenant Support Scenarios

### Scenario 1: Multiple Stacks (Same Credentials)
**Example:** User has access to `prod.quiltdata.com` and `dev.quiltdata.com`

**Current Status:** ❌ Not Supported
- Can only connect to one registry at a time
- Would need to restart/reconfigure to switch

**Required Changes:**
- Pass registry URL explicitly to GraphQL functions
- Manage multiple authenticated sessions
- Update `_get_graphql_endpoint()` to accept registry parameter

### Scenario 2: Multiple Buckets (Single Stack)
**Example:** User accesses multiple buckets on `mycompany.quiltdata.com`

**Current Status:** ✅ Fully Supported
- `bucketConfigs` query returns all accessible buckets
- Object search accepts bucket parameter
- No code changes needed

### Scenario 3: Cross-Registry Operations
**Example:** Search objects across both prod and dev stacks

**Current Status:** ❌ Not Supported
- Would require parallel sessions to different registries
- No architecture for managing multiple GraphQL endpoints
- Would need significant refactoring

---

## Dependencies

### External Dependencies

1. **Quilt Catalog GraphQL Endpoint**
   - Must be available at `{registry_url}/graphql`
   - Must support `bucketConfigs` query
   - Must support `objects` query with filters

2. **Quilt3 Library**
   - Provides authenticated session
   - Manages credentials and tokens
   - Provides registry URL configuration

3. **Network Connectivity**
   - MCP server must be able to reach registry
   - Requires HTTPS access to catalog endpoints
   - Must respect catalog timeout settings

### Internal Dependencies

1. **Session Management**
   - `quilt3.session.get_session()` must return valid session
   - Session must have valid authentication tokens
   - Tokens must not be expired

2. **Configuration**
   - `quilt3.config.get_config_dir()` must be accessible
   - Config must contain valid registry URL
   - HTTP timeout settings must be configured

---

## Error Handling

### GraphQL-Specific Errors

1. **Connection Failures**
   - Network timeout
   - DNS resolution failure
   - SSL certificate errors

2. **Authentication Errors**
   - Expired tokens (HTTP 401)
   - Invalid credentials (HTTP 403)
   - Missing authentication headers

3. **Query Errors**
   - Invalid GraphQL syntax
   - Unknown fields requested
   - Type mismatches

4. **Data Errors**
   - Missing expected data structure
   - Empty results
   - Malformed responses

### Current Error Recovery

**Bucket Discovery:**
```python
except Exception as e:
    logger.warning(f"GraphQL bucket discovery failed: {e}")
    return set()  # Returns empty set, fallback continues
```

**Object Search:**
```python
if resp.status_code != 200:
    return SearchGraphQLError(error=f"GraphQL HTTP {resp.status_code}: {resp.text}")
```

**Generic GraphQL:**
```python
if "errors" in payload:
    return SearchGraphQLError(error=f"GraphQL errors: {payload.get('errors')}")
```

---

## Performance Characteristics

### Query Performance

1. **bucketConfigs Query**
   - Typically fast (< 1 second)
   - Cached by catalog
   - Infrequent changes

2. **objects Query**
   - Variable performance (1-10 seconds)
   - Depends on filter complexity
   - Depends on result set size
   - Benefits from Elasticsearch backend

### Caching Considerations

**Current State:** ❌ No caching implemented
- Each GraphQL call hits the catalog
- No client-side result caching
- No TTL-based cache invalidation

**Potential Optimizations:**
- Cache `bucketConfigs` results (TTL: 5-15 minutes)
- Cache object search results (TTL: 1-5 minutes)
- Use ETags for conditional requests

---

## Stateless Deployment Readiness

### ✅ Compatible with Stateless

1. **No Server-Side State**
   - Each GraphQL call is independent
   - No session storage required on server
   - Results are returned immediately

2. **Authentication is Request-Scoped**
   - Credentials come from quilt3 config
   - Session headers included in each request
   - No persistent session state

### ⚠️ Stateless Challenges

1. **Quilt3 Session Singleton**
   - Session object is module-level
   - Not thread-safe for concurrent registry switching
   - May cause issues with concurrent requests

2. **Configuration File Dependency**
   - Reads from `~/.config/quiltdata/config.yaml`
   - File I/O on each session retrieval
   - May not work in containerized environments

---

## Recommendations

### For Multi-Tenant Support

1. **Explicit Registry Parameter**
   ```python
   def search_objects_graphql(
       bucket: str,
       registry_url: Optional[str] = None,  # NEW
       ...
   ):
   ```

2. **Session Pool Management**
   - Create session pool for multiple registries
   - Cache sessions by registry URL
   - Implement thread-safe session retrieval

3. **Configuration Refactoring**
   - Accept credentials via parameters
   - Support environment variables
   - Reduce file system dependencies

### For Stateless Deployment

1. **Remove Singleton Dependency**
   - Pass session explicitly to GraphQL functions
   - Create session per request if needed
   - Avoid module-level session caching

2. **Configuration from Environment**
   - Read credentials from env vars
   - Support AWS Secrets Manager
   - Reduce file system reads

3. **Add Response Caching**
   - Cache `bucketConfigs` for 5 minutes
   - Use in-memory cache (Redis for distributed)
   - Implement cache invalidation strategy

---

## Testing Considerations

### Current Test Coverage

1. **Unit Tests**
   - Mock GraphQL responses
   - Test error handling
   - Test response parsing

2. **Integration Tests**
   - Real GraphQL endpoint calls
   - Authentication flow testing
   - Timeout behavior testing

### Gaps for Multi-Tenant

1. **Multiple Registry Tests**
   - Switching between registries
   - Concurrent registry access
   - Registry-specific authentication

2. **Stateless Behavior Tests**
   - Session independence
   - Configuration isolation
   - Thread safety

---

## Related Specifications

- `01-stateless.md` - Stateless deployment requirements
- `02-test-stateless.md` - Stateless testing strategy
- `03-fix-stateless.md` - Stateless implementation fixes

---

## Next Steps

1. **Document Decisions**
   - Decide on multi-tenant support scope
   - Define registry switching requirements
   - Specify session management strategy

2. **Prototype Changes**
   - Test explicit registry parameter approach
   - Evaluate session pool implementation
   - Measure performance impact

3. **Update Tests**
   - Add multi-registry test cases
   - Test concurrent GraphQL calls
   - Validate stateless behavior

---

## Appendix: GraphQL Schema Notes

### Known Schema Fields

**bucketConfigs:**
- `name` (String) - S3 bucket name
- `title` (String) - User-friendly display name
- Additional fields may be available depending on catalog version

**objects:**
- `key` (String) - Object key/path
- `size` (Int) - Object size in bytes
- `updated` (DateTime) - Last modified timestamp
- `contentType` (String) - MIME type
- `extension` (String) - File extension
- `package` (Object) - Parent package metadata
  - `name` (String) - Package name
  - `topHash` (String) - Package hash
  - `tag` (String) - Package tag/version

### Filter Capabilities

The `ObjectFilterInput` type supports:
- `extension` - Filter by file extension
- `size_gt`, `size_lt` - Filter by size
- `updated_gt`, `updated_lt` - Filter by date
- Additional filters vary by catalog version

**Note:** Exact schema may vary by Quilt Enterprise deployment. Query the catalog's `/graphql` endpoint with introspection for full schema.
