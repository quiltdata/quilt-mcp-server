# GraphQL Bearer Token Integration

## Overview

This document describes the integration of bearer token authentication with GraphQL operations in the Quilt MCP Server, replacing the legacy `quilt3` session-based authentication for GraphQL calls.

## Problem Statement

### Initial Issue
GraphQL operations (search, package queries, etc.) were still using the old `quilt3` session-based authentication instead of the new bearer token system. This created a mismatch where:

- ✅ **Bearer tokens worked** for basic MCP operations
- ❌ **GraphQL calls failed** because they used outdated authentication

### Root Cause
The GraphQL tools were hardcoded to use `QuiltService()` which relies on `quilt3` sessions, not bearer tokens.

## Solution Architecture

### New GraphQL Bearer Service

Created `GraphQLBearerService` that provides:

1. **Bearer Token Authentication**: Uses `Authorization: Bearer <token>` headers
2. **GraphQL Query Execution**: Standard GraphQL query execution with proper error handling
3. **Object Search**: GraphQL-based bucket object search
4. **Package Search**: GraphQL-based package search
5. **Fallback Support**: Graceful fallback to `quilt3` sessions when bearer tokens unavailable

### Implementation Details

#### 1. GraphQL Bearer Service (`src/quilt_mcp/services/graphql_bearer_service.py`)

```python
class GraphQLBearerService:
    """GraphQL service using bearer token authentication."""
    
    def __init__(self, catalog_url: str = "https://demo.quiltdata.com"):
        self.catalog_url = catalog_url.rstrip('/')
    
    def get_graphql_endpoint(self) -> Tuple[Optional[requests.Session], Optional[str]]:
        """Get authenticated session and GraphQL endpoint URL."""
        # Get access token from environment variables (set by middleware)
        access_token = os.environ.get("QUILT_ACCESS_TOKEN")
        
        # Create authenticated session using BearerAuthService
        bearer_auth_service = get_bearer_auth_service()
        session = bearer_auth_service.get_authenticated_session(access_token)
        
        # Construct GraphQL endpoint URL
        graphql_url = urljoin(self.catalog_url + "/", "graphql")
        return session, graphql_url
    
    def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None):
        """Execute a GraphQL query using bearer token authentication."""
        session, graphql_url = self.get_graphql_endpoint()
        
        # Execute GraphQL query with proper error handling
        payload = {"query": query, "variables": variables or {}}
        resp = session.post(graphql_url, json=payload)
        
        # Parse and return response
        return self._parse_response(resp)
```

#### 2. Updated GraphQL Tools

**Before (Broken)**:
```python
def _get_graphql_endpoint():
    quilt_service = QuiltService()  # Uses quilt3 sessions
    session = quilt_service.get_session()
    return session, graphql_url
```

**After (Fixed)**:
```python
def _get_graphql_endpoint():
    try:
        # Try bearer token authentication first
        graphql_service = get_graphql_bearer_service()
        return graphql_service.get_graphql_endpoint()
    except Exception as e:
        # Fallback to quilt3 sessions
        quilt_service = QuiltService()
        return quilt_service.get_session(), graphql_url
```

#### 3. Updated Search Functions

**Bucket Object Search**:
```python
def bucket_objects_search_graphql(bucket: str, object_filter: dict = None, first: int = 100, after: str = ""):
    try:
        # Use bearer token GraphQL service
        graphql_service = get_graphql_bearer_service()
        return graphql_service.search_objects(bucket, object_filter, first, after)
    except Exception as e:
        # Fallback to quilt3 method
        logger.warning("Bearer token GraphQL search failed, falling back to quilt3: %s", e)
        # ... quilt3 fallback code
```

**Package Search**:
```python
def packages_search(query: str, registry: str = DEFAULT_REGISTRY, limit: int = 10, from_: int = 0):
    try:
        # Try bearer token GraphQL search first
        graphql_service = get_graphql_bearer_service()
        result = graphql_service.search_packages(query, registry, limit, from_)
        if result["success"]:
            return result
    except Exception as e:
        logger.warning("Bearer token GraphQL package search failed, falling back to quilt3: %s", e)
    
    # Fallback to original quilt3-based search
    # ... existing implementation
```

## Authentication Flow

### 1. Request Processing

```
Frontend → MCP Client → MCP Server
    ↓           ↓           ↓
Bearer Token → Authorization Header → QuiltAuthMiddleware
    ↓           ↓           ↓
JWT Token → Environment Variable → GraphQLBearerService
    ↓           ↓           ↓
Valid Token → Authenticated Session → GraphQL Endpoint
```

### 2. GraphQL Request Flow

```
GraphQL Tool Call
    ↓
GraphQLBearerService.get_graphql_endpoint()
    ↓
BearerAuthService.get_authenticated_session(token)
    ↓
requests.Session with Authorization: Bearer <token>
    ↓
POST to https://demo.quiltdata.com/graphql
    ↓
GraphQL Response with Data
```

## Key Features

### 1. Seamless Integration

- **Backward Compatible**: Falls back to `quilt3` sessions when bearer tokens unavailable
- **No Breaking Changes**: Existing tools continue to work
- **Progressive Enhancement**: New bearer token functionality enhances existing capabilities

### 2. Robust Error Handling

```python
try:
    # Try bearer token GraphQL search first
    result = graphql_service.search_objects(bucket, filter, first, after)
    return result
except Exception as e:
    logger.warning("Bearer token GraphQL search failed, falling back to quilt3: %s", e)
    # Fallback to quilt3 method
```

### 3. Comprehensive GraphQL Support

- **Object Search**: Bucket object search with filters and pagination
- **Package Search**: Package discovery with metadata
- **Custom Queries**: Generic GraphQL query execution
- **Error Handling**: Proper GraphQL error parsing and reporting

## Supported GraphQL Operations

### 1. Object Search Query

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

### 2. Package Search Query

```graphql
query($query: String!, $limit: Int, $offset: Int) {
    packages(query: $query, first: $limit, after: $offset) {
        edges {
            node {
                name
                topHash
                tag
                updated
                description
                owner
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

## Configuration

### Environment Variables

The GraphQL bearer service uses the same environment variables as the main authentication system:

- `QUILT_ACCESS_TOKEN`: Bearer token (set by middleware)
- `QUILT_USER_INFO`: User information (set by middleware)
- `QUILT_CATALOG_DOMAIN`: Catalog URL (default: https://demo.quiltdata.com)

> **Runtime Context**
>
> The MCP server now exposes the active authentication state through `quilt_mcp.runtime_context`. Middleware populates `RuntimeAuthState` per request (distinguishing desktop/stdio flows from web/JWT flows) and the GraphQL servicemodule reads from that context before falling back to the environment variables above. This keeps concurrent requests isolated while remaining backwards compatible with existing env-var based integrations.

### Catalog URL Configuration

```python
# Default configuration
graphql_service = get_graphql_bearer_service()  # Uses https://demo.quiltdata.com

# Custom catalog
graphql_service = get_graphql_bearer_service("https://your-catalog.com")
```

## Testing

### 1. Unit Tests

```python
def test_graphql_bearer_service():
    # Mock bearer token
    os.environ["QUILT_ACCESS_TOKEN"] = "test-token"
    
    service = GraphQLBearerService()
    session, url = service.get_graphql_endpoint()
    
    assert session is not None
    assert "graphql" in url
    assert "Authorization" in session.headers
    assert session.headers["Authorization"] == "Bearer test-token"
```

### 2. Integration Tests

```python
def test_graphql_search_with_bearer_token():
    # Set up bearer token
    os.environ["QUILT_ACCESS_TOKEN"] = "valid-token"
    
    # Test object search
    result = bucket_objects_search_graphql("test-bucket", {"extension": "csv"})
    assert result["success"] == True
    assert "objects" in result
```

### 3. Fallback Tests

```python
def test_graphql_fallback_to_quilt3():
    # No bearer token available
    os.environ.pop("QUILT_ACCESS_TOKEN", None)
    
    # Should fallback to quilt3
    result = bucket_objects_search_graphql("test-bucket")
    # Should still work with quilt3 fallback
```

## Performance Considerations

### 1. Session Caching

The `BearerAuthService` caches authenticated sessions to avoid recreating them for each request:

```python
def get_authenticated_session(self, access_token: str) -> Optional[requests.Session]:
    # Check cache first
    if access_token in self.session_cache:
        return self.session_cache[access_token]
    
    # Create and cache new session
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {access_token}"})
    self.session_cache[access_token] = session
    return session
```

### 2. Error Handling Overhead

The fallback mechanism adds minimal overhead:

- **Bearer Token Available**: Direct GraphQL call (fast)
- **Bearer Token Missing**: One exception catch, then quilt3 fallback (slightly slower)
- **No Authentication**: Immediate failure (fast)

### 3. Network Efficiency

- **Single Authentication**: Bearer token used for all GraphQL calls
- **Connection Reuse**: HTTP session reuse for multiple requests
- **Proper Headers**: Standard HTTP headers for optimal caching

## Security Benefits

### 1. Consistent Authentication

- **Unified Auth**: Same bearer token used for all operations
- **No Session Conflicts**: No mixing of authentication methods
- **Clear Audit Trail**: All requests use same authentication source

### 2. Token Validation

- **JWT Validation**: Bearer tokens validated before use
- **Permission Checking**: GraphQL operations respect user permissions
- **Expiration Handling**: Automatic token expiration detection

### 3. Secure Headers

```python
session.headers.update({
    "Authorization": f"Bearer {access_token}",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "quilt-mcp-server/1.0.0"
})
```

## Troubleshooting

### 1. Common Issues

**Issue**: GraphQL calls failing with 401 Unauthorized
**Solution**: Check that `QUILT_ACCESS_TOKEN` environment variable is set

**Issue**: GraphQL calls falling back to quilt3
**Solution**: Verify bearer token is valid and not expired

**Issue**: GraphQL endpoint not found
**Solution**: Check catalog URL configuration

### 2. Debug Logging

```python
# Enable debug logging
import logging
logging.getLogger("quilt_mcp.services.graphql_bearer_service").setLevel(logging.DEBUG)
```

### 3. Fallback Behavior

When bearer token authentication fails, the system automatically falls back to `quilt3` sessions:

```python
logger.warning("Bearer token GraphQL search failed, falling back to quilt3: %s", e)
```

## Future Enhancements

### 1. GraphQL Query Optimization

- **Query Caching**: Cache frequently used GraphQL queries
- **Batch Queries**: Combine multiple queries into single requests
- **Query Analysis**: Optimize queries based on usage patterns

### 2. Advanced Error Handling

- **Retry Logic**: Automatic retry for transient failures
- **Circuit Breaker**: Prevent cascading failures
- **Health Checks**: Monitor GraphQL endpoint health

### 3. Performance Monitoring

- **Query Timing**: Track GraphQL query performance
- **Error Rates**: Monitor authentication failure rates
- **Usage Analytics**: Track GraphQL operation usage

## Conclusion

The GraphQL bearer token integration provides a seamless upgrade path from `quilt3` session-based authentication to modern bearer token authentication. The implementation maintains backward compatibility while providing enhanced security and consistency across all MCP server operations.

Key benefits:
- ✅ **Unified Authentication**: All operations use bearer tokens
- ✅ **Backward Compatibility**: Graceful fallback to `quilt3` sessions
- ✅ **Enhanced Security**: JWT-based authentication with proper validation
- ✅ **Better Error Handling**: Clear error messages and fallback mechanisms
- ✅ **Performance Optimized**: Session caching and connection reuse

The integration ensures that GraphQL operations work seamlessly with the new permission system while maintaining compatibility with existing deployments.
