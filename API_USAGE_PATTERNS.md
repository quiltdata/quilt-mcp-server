# Quilt MCP Server API Usage Patterns

## Overview

The Quilt MCP Server uses **BOTH quilt3 Python SDK AND direct GraphQL API calls**, depending on the operation. Here's the breakdown:

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Tools Layer                       │
│  (catalog.py, packages.py, search.py, governance.py...) │
└─────────────────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│              QuiltService Abstraction                    │
│  (services/quilt_service.py - abstracts quilt3)         │
└─────────────────────────────────────────────────────────┘
                         ▼
           ┌─────────────┴─────────────┐
           ▼                            ▼
┌──────────────────────┐    ┌──────────────────────┐
│   quilt3 Python SDK  │    │  GraphQL Direct API  │
│  (Package operations)│    │ (Advanced queries)   │
└──────────────────────┘    └──────────────────────┘
           │                            │
           └─────────────┬──────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│              Quilt Catalog Backend                       │
│  (Registry API, S3, Athena, Elasticsearch...)           │
└─────────────────────────────────────────────────────────┘
```

## API Usage Breakdown

### 1. Primary quilt3 SDK Usage (90% of operations)

**Used for**:
- ✅ **Authentication** - `quilt3.logged_in()`, `quilt3.config()`
- ✅ **Package operations** - `quilt3.Package()`, `.browse()`, `.push()`, `.fetch()`, `.install()`
- ✅ **AWS credential management** - `quilt3.session.create_botocore_session()`
- ✅ **Session management** - `quilt3.session.get_session()`, `.get_registry_url()`
- ✅ **S3/Athena operations** - via `QuiltService.create_botocore_session()`

**Files using quilt3 SDK**:
- `src/quilt_mcp/services/quilt_service.py` - Primary abstraction (1,282 lines)
- `src/quilt_mcp/services/athena_service.py` - Uses `quilt3.session` for credentials
- `src/quilt_mcp/tools/packages.py` - Package browsing, listing
- `src/quilt_mcp/tools/package_creation.py` - Package creation, pushing
- `src/quilt_mcp/tools/catalog.py` - Catalog status, configuration
- `src/quilt_mcp/tools/buckets.py` - S3 operations via quilt3 sessions

**Example**:
```python
# In QuiltService
def create_botocore_session(self) -> boto3.Session:
    """Create authenticated botocore session using quilt3."""
    return quilt3.session.create_botocore_session()

def browse_package(self, package_name: str, registry: str, top_hash: str = None):
    """Browse package using quilt3.Package.browse()."""
    return quilt3.Package.browse(package_name, registry=registry, top_hash=top_hash)
```

### 2. Direct GraphQL API Usage (10% of operations)

**Used for**:
- ✅ **Advanced search** - Package/object search with complex filters
- ✅ **Governance/Policy management** - Policy CRUD operations
- ✅ **Bucket discovery** - `bucketConfigs` query
- ✅ **Object queries** - Complex object metadata queries

**Files using GraphQL directly**:
- `src/quilt_mcp/tools/graphql.py` - Generic GraphQL executor (141 lines)
- `src/quilt_mcp/tools/governance_impl_part3.py` - Policy management via GraphQL
- `src/quilt_mcp/search/backends/graphql.py` - Search backend (400+ lines)
- `src/quilt_mcp/tools/stack_buckets.py` - Bucket discovery

**GraphQL Implementation**:
```python
# From tools/graphql.py
def catalog_graphql_query(query: str, variables: dict | None = None) -> dict[str, Any]:
    """Execute an arbitrary GraphQL query against the configured Quilt Catalog."""
    
    # Get authenticated session from quilt3
    quilt_service = QuiltService()
    session = quilt_service.get_session()  # Returns requests.Session with auth
    registry_url = quilt_service.get_registry_url()
    
    # Construct GraphQL endpoint
    graphql_url = urljoin(registry_url.rstrip("/") + "/", "graphql")
    
    # Execute GraphQL query
    resp = session.post(graphql_url, json={"query": query, "variables": variables or {}})
    return resp.json()
```

**Example GraphQL Queries**:

1. **Bucket Discovery**:
```graphql
query {
  bucketConfigs {
    name
    title
    description
  }
}
```

2. **Policy Management**:
```graphql
mutation CreatePolicy($input: PolicyInput!) {
  policyCreate(input: $input) {
    policy {
      id
      title
      managed
    }
  }
}
```

3. **Object Search**:
```graphql
query($bucket: String!, $filter: ObjectFilterInput, $first: Int) {
  objects(bucket: $bucket, filter: $filter, first: $first) {
    edges {
      node {
        key
        size
        updated
        contentType
        package { name topHash }
      }
    }
  }
}
```

## Why Both Approaches?

### quilt3 SDK Advantages:
- ✅ **Simpler API** for common operations
- ✅ **Automatic authentication** and credential management
- ✅ **Package abstractions** (browsing, pushing, fetching)
- ✅ **AWS integration** (S3, Athena, STS)
- ✅ **Stable interface** with versioning
- ✅ **Handles token refresh** automatically

### GraphQL Direct Advantages:
- ✅ **More powerful queries** with filtering and pagination
- ✅ **Access to catalog features** not exposed in quilt3 SDK
- ✅ **Policy/governance operations** (not in quilt3)
- ✅ **Flexible data retrieval** (only request needed fields)
- ✅ **Batch operations** and complex queries

## Authentication Flow

Both approaches use the **same authentication**:

1. **User provides**: `QUILT_API_TOKEN` (JWT) via environment variable
2. **quilt3 SDK**: Validates JWT with catalog, gets STS credentials
3. **GraphQL calls**: Use authenticated `requests.Session` from `quilt3.session.get_session()`

```python
# Authentication is shared!
quilt_service = QuiltService()

# quilt3 SDK path
botocore_session = quilt_service.create_botocore_session()  # Uses JWT
credentials = botocore_session.get_credentials()            # Returns STS creds

# GraphQL path
session = quilt_service.get_session()           # Uses JWT, returns requests.Session
registry_url = quilt_service.get_registry_url() # Gets GraphQL endpoint
# session already has auth headers from quilt3
```

## Key Insight: No Duplicate Authentication

The GraphQL queries **piggyback on quilt3's authentication**:
- quilt3 SDK handles JWT exchange and token refresh
- GraphQL queries use the authenticated `requests.Session` from quilt3
- No separate auth mechanism needed

## Current Usage Statistics

Based on code analysis:

| API Type | Usage Count | Percentage |
|----------|-------------|------------|
| quilt3 SDK methods | ~50+ direct calls | ~90% |
| GraphQL queries | ~10 query types | ~10% |

**quilt3 SDK is the primary interface**, GraphQL is used for advanced features not available in the SDK.

## Tool Categorization

### Pure quilt3 SDK Tools:
- ✅ `catalog.py` - Catalog info, status
- ✅ `packages.py` - Package browsing, listing
- ✅ `package_creation.py` - Package push, creation
- ✅ `buckets.py` - S3 operations (via quilt3 sessions)
- ✅ `athena_glue.py` - Athena queries (via quilt3 credentials)
- ✅ `metadata_*.py` - Metadata operations

### Mixed quilt3 + GraphQL Tools:
- 🔄 `search.py` - Uses GraphQL backend for advanced search
- 🔄 `governance.py` - Uses GraphQL for policy management
- 🔄 `stack_buckets.py` - Uses GraphQL for bucket discovery

### Pure GraphQL Tools:
- ⚡ `graphql.py` - Generic GraphQL executor
- ⚡ `governance_impl_part3.py` - Policy CRUD operations

## Best Practices

1. **Prefer quilt3 SDK** for standard operations
2. **Use GraphQL** when:
   - SDK doesn't support the feature (e.g., policy management)
   - Need complex filtering/pagination
   - Performance requires minimal data transfer
3. **Always use QuiltService** as the abstraction layer
4. **Don't bypass authentication** - use `quilt_service.get_session()` for GraphQL

## Future Considerations

- **More GraphQL usage** as catalog features expand
- **Potential quilt3 SDK enhancements** to reduce GraphQL needs
- **Caching strategies** for GraphQL query results
- **Error handling unification** across both approaches

---

**Date**: 2025-10-09  
**Author**: Claude/Simon  
**Status**: Current implementation documented

