# Registry GraphQL API Documentation

## Source Folders Examined

**External Projects**:

- `~/GitHub/enterprise/registry/` - Quilt registry (GraphQL schema and implementation)
  - `quilt_server/graphql/schema.graphql` - GraphQL schema definition
  - `quilt_server/views/graphql.py` - GraphQL endpoint implementation
  - `quilt_server/views/tabulator.py` - Tabulator REST endpoints
  - `quilt_server/tabulator.py` - Tabulator business logic
- `~/GitHub/quilt/api/python/quilt3/` - Quilt3 Python client (GraphQL usage examples)
  - `_graphql_client/` - Auto-generated GraphQL client code
  - `admin/buckets.py` - Admin bucket operations
  - `admin/users.py` - Admin user operations

**This Project**:

- `src/quilt_mcp/search/backends/elasticsearch.py` - Uses GraphQL for bucket discovery
- `src/quilt_mcp/backends/quilt3_backend.py` - Backend with `execute_graphql_query()` method

## Overview

The Quilt registry exposes a comprehensive GraphQL API at `POST /graphql` implemented using Ariadne. This API is used by both the Elasticsearch search backend and the quilt3 Python admin client for catalog operations.

## GraphQL Schema Location

**Primary schema**: `~/GitHub/enterprise/registry/quilt_server/graphql/schema.graphql`

**Implementation**: `~/GitHub/enterprise/registry/quilt_server/views/graphql.py`

```python
@app.route("/graphql", methods=["POST"])
@api(require_login=False)
def graphql_server():
    coro = run_graphql_async(
        request.get_json(),
        user=g.user,
        config=app.config,
        debug=app.debug,
    )
    success, result = asyncio.run(coro)
    status_code = 200 if success else 400
    return jsonify(result), status_code
```

## How Elasticsearch Backend Uses GraphQL

The Elasticsearch backend uses GraphQL for **catalog metadata only** (not for search operations).

### Bucket Discovery Query

**Location**: `src/quilt_mcp/search/backends/elasticsearch.py:255`

```python
# Get list of available buckets
result = self.backend.execute_graphql_query("{ bucketConfigs { name } }")
configs = result.get("data", {}).get("bucketConfigs", [])
bucket_names = [config["name"] for config in configs]
```

**GraphQL Schema** (line 595):
```graphql
type Query {
  bucketConfigs: [BucketConfig!]!
  bucketConfig(name: String!): BucketConfig
  ...
}

type BucketConfig {
  name: String!
  title: String!
  iconUrl: String
  description: String
  linkedData: Json
  overviewUrl: String
  tags: [String!]
  relevanceScore: Int!
  lastIndexed: Datetime
  browsable: Boolean!
  # ... more fields
}
```

### Fallback Implementation

When no backend is provided, the Elasticsearch backend falls back to direct HTTP requests:

```python
# Direct GraphQL POST to registry
resp = session.post(
    f"{normalize_url(registry_url)}/graphql",
    json={"query": "{ bucketConfigs { name } }"},
    timeout=30,
)
```

### What Elasticsearch Does NOT Use GraphQL For

The actual search operations use `quilt3.search_util.search_api()` which makes **direct Elasticsearch DSL queries**, not GraphQL.

**Search flow**:
1. GraphQL → Get available buckets (`bucketConfigs`)
2. Build index pattern → `bucket1,bucket2,bucket1_packages,bucket2_packages`
3. Elasticsearch DSL → `search_api(query=dsl_query, index=index_pattern, limit=limit)`

## How Quilt3 Admin Uses GraphQL

The quilt3 Python client uses GraphQL extensively for **all admin operations**.

### Generated Client Code

**Location**: `~/GitHub/quilt/api/python/quilt3/_graphql_client/`

The client is **code-generated** from GraphQL queries using `ariadne-codegen`. Each operation has:
- Query/mutation definition
- Pydantic response models
- Type-safe client methods

### Bucket Operations

**Query: `bucketsList`**
```graphql
query bucketsList {
  bucketConfigs {
    name
    title
    iconUrl
    description
    overviewUrl
    tags
    relevanceScore
    lastIndexed
    snsNotificationArn
    scannerParallelShardsDepth
    skipMetaDataIndexing
    fileExtensionsToIndex
    indexContentBytes
    prefixes
  }
}
```

**Python Usage** (`quilt3/admin/buckets.py`):
```python
def list() -> list[types.Bucket]:
    """List all bucket configurations in the registry."""
    return [types.Bucket(**b.model_dump()) for b in util.get_client().buckets_list()]
```

**Mutations**:
```graphql
mutation bucketAdd(input: BucketAddInput!) {
  bucketAdd(input: $input) {
    __typename
    ... on BucketAddSuccess {
      bucketConfig { ... }
    }
    ... on BucketAlreadyAdded { }
    ... on BucketDoesNotExist { }
    ... on InsufficientPermissions { message }
  }
}
```

### User Management Operations

**User queries** (lines 548-551):
```graphql
type UserAdminQueries {
  list: [User!]!
  get(name: String!): User
}

type Query {
  admin: AdminQueries! @admin
}

type AdminQueries {
  user: UserAdminQueries!
  ssoConfig: SsoConfig
  isDefaultRoleSettingDisabled: Boolean!
  tabulatorOpenQuery: Boolean!
  packager: PackagerAdminQueries!
}
```

**User mutations** (lines 934-948):
```graphql
type UserAdminMutations {
  create(input: UserInput!): UserResult!
  mutate(name: String!): MutateUserAdminMutations
}

type MutateUserAdminMutations {
  delete: OperationResult!
  setEmail(email: String!): UserResult!
  setRole(role: String!, extraRoles: [String!], append: Boolean! = false): UserResult!
  addRoles(roles: [String!]!): UserResult!
  removeRoles(roles: [String!]!, fallback: String): UserResult!
  setAdmin(admin: Boolean!): UserResult!
  setActive(active: Boolean!): UserResult!
  resetPassword: OperationResult!
}
```

### Role and Policy Management

**GraphQL schema** (lines 620-626):
```graphql
type Query {
  policies: [Policy!]! @admin
  policy(id: ID!): Policy @admin
  roles: [Role!]! @admin
  role(id: ID!): Role @admin
  defaultRole: Role @admin
  status: StatusResult! @admin
}
```

## Tabulator API - Dual Interface

Tabulator has **two separate API surfaces**:

### 1. REST Endpoints (for Athena Connector)

**Location**: `~/GitHub/enterprise/registry/quilt_server/views/tabulator.py`

All endpoints use **POST** with KMS signature authentication:

```python
POST /tabulator/credentials
POST /tabulator/buckets
POST /tabulator/buckets/<bucket_name>
POST /tabulator/buckets/<bucket_name>/<table_name>
POST /tabulator/spill-location
```

**Purpose**: Used by the **Athena connector** running in AWS Lambda
- Returns AWS credentials for queries
- Lists buckets with tabulator tables
- Returns table configurations (YAML)
- Provides S3 spill location for large queries

**Authentication**: KMS signature verification
```python
if (signature := request.headers.get("x-quilt-signature")) is None:
    return "Missing signature", 403
kms.verify(
    KeyId=app.config["QUILT_TABULATOR_KMS_KEY_ID"],
    MessageType="RAW",
    Message=request.data,
    Signature=base64.b64decode(signature),
    SigningAlgorithm="RSASSA_PSS_SHA_512",
)
```

### 2. GraphQL Queries and Mutations (for Admin UI and Users)

**Tabulator operations use permission-based access control, not role-based.**

#### Read Tabulator Tables (Non-Admin)

**Schema** (line 149):
```graphql
type BucketConfig {
  name: String!
  title: String!
  # ...
  tabulatorTables: [TabulatorTable!]!  # NO @admin directive - anyone with read access
}

type TabulatorTable {
  name: String!
  config: String!
}
```

**Query for listing tables**:
```graphql
query bucketTabulatorTablesList($name: String!) {
  bucketConfig(name: $name) {
    tabulatorTables {
      name
      config
    }
  }
}
```

**Permission**: Any user with **read access** to the bucket can list tables.

#### Manage Tabulator Tables (Write Permission)

**Schema** (lines 998-999):
```graphql
type Mutation {
  # Root-level mutations - NO @admin directive
  bucketSetTabulatorTable(
    bucketName: String!
    tableName: String!
    config: String
  ): BucketSetTabulatorTableResult!

  bucketRenameTabulatorTable(
    bucketName: String!
    tableName: String!
    newTableName: String!
  ): BucketSetTabulatorTableResult!
}
```

**Permission**: Any user with **write access** to the bucket can create/update/rename/delete tables.

**Implementation** (`quilt_server/tabulator.py:119-123`):
```python
def check_bucket(name: str) -> models.Bucket:
    u = context.get_user()

    # Allow to modify tables: admin or write access
    if u and (u.is_admin or auth.bucket_is_writable_by(name, u)):
        return models.Bucket.query.filter_by(name=name).one()

    raise BucketNotAllowed
```

#### Admin-Only Operations

**Schema** (lines 573, 967-969):
```graphql
type AdminQueries {
  tabulatorOpenQuery: Boolean!  # Query open query mode setting
}

type AdminMutations {
  # Deprecated admin versions - prefer root-level mutations above
  bucketSetTabulatorTable(...): BucketSetTabulatorTableResult! @deprecated
  bucketRenameTabulatorTable(...): BucketSetTabulatorTableResult! @deprecated

  # Admin-only setting
  setTabulatorOpenQuery(enabled: Boolean!): TabulatorOpenQueryResult!
}
```

**Permission**: Only **admins** can query/set the global "open query" mode.

**Python client** (`quilt3/_graphql_client/client.py`):
```python
def bucket_tabulator_tables_list(
    self, name: str, **kwargs: Any
) -> Optional[BucketTabulatorTablesListBucketConfig]:
    query = gql("""
        query bucketTabulatorTablesList($name: String!) {
          bucketConfig(name: $name) {
            tabulatorTables {
              name
              config
            }
          }
        }
    """)
    variables = {"name": name}
    response = self.execute(query=query, operation_name="bucketTabulatorTablesList", variables=variables, **kwargs)
    data = self.get_data(response)
    return BucketTabulatorTablesList.model_validate(data).bucket_config
```

### Table Configuration Format

Tables are defined in **YAML** with validated schema:

**Pydantic models** (`quilt_server/tabulator.py`):
```python
class Column(pydantic.v1.BaseModel):
    name: str = Field(min_length=1, max_length=255, regex=r"^[A-Za-z][A-Za-z0-9_-]*$")
    type: Literal["BOOLEAN", "TINYINT", "SMALLINT", "INT", "BIGINT",
                   "FLOAT", "DOUBLE", "STRING", "BINARY", "DATE", "TIMESTAMP"]
    nullable: Optional[bool]

class PackageSource(pydantic.v1.BaseModel):
    type: Literal["quilt-packages"]
    package_name: str = Field(min_length=1)
    logical_key: str = Field(min_length=1)

class Config(pydantic.v1.BaseModel):
    schema_: list[Column] = Field(alias="schema", min_items=1)
    source: PackageSource
    parser: Union[CsvParser, ParquetParser] = Field(discriminator="format")
    continue_on_error: Optional[bool]
```

### Tabulator Permission Summary

| Operation               | GraphQL Endpoint                       | Requires @admin? | Permission Check             |
|-------------------------|----------------------------------------|------------------|------------------------------|
| **Read tables**         | `bucketConfig.tabulatorTables`         | ❌ No            | Read access to bucket        |
| **Create/Update table** | `bucketSetTabulatorTable`              | ❌ No            | Write access OR admin        |
| **Rename table**        | `bucketRenameTabulatorTable`           | ❌ No            | Write access OR admin        |
| **Delete table**        | `bucketSetTabulatorTable(config:null)` | ❌ No            | Write access OR admin        |
| **Get open query mode** | `admin.tabulatorOpenQuery`             | ✅ Yes           | Admin only                   |
| **Set open query mode** | `admin.setTabulatorOpenQuery`          | ✅ Yes           | Admin only                   |

**Key Insight**: Tabulator table management follows **bucket-level permissions**, not
global admin roles. This is the same pattern as bucket updates and package operations.

## Native Search GraphQL Queries (Not Currently Used)

The registry has native GraphQL search operations that are **not used by the Elasticsearch backend**:

**Object search** (lines 600-604):
```graphql
type Query {
  searchObjects(
    buckets: [String!]
    searchString: String
    filter: ObjectsSearchFilter
  ): ObjectsSearchResult!
}

type ObjectsSearchResult = ObjectsSearchResultSet | EmptySearchResultSet | InvalidInput | OperationError

type ObjectsSearchResultSet {
  total: Int!
  stats: ObjectsSearchStats!
  firstPage(size: Int = 30, order: SearchResultOrder): ObjectsSearchResultSetPage!
}

type ObjectsSearchResultSetPage {
  cursor: String
  hits: [SearchHitObject!]!
}

type SearchHitObject {
  id: ID!
  score: Float!
  bucket: String!
  key: String!
  version: String!
  size: Float!
  modified: Datetime!
  deleted: Boolean!
  indexedContent: String
}
```

**Package search** (lines 605-611):
```graphql
type Query {
  searchPackages(
    buckets: [String!]
    searchString: String
    filter: PackagesSearchFilter
    userMetaFilters: [PackageUserMetaPredicate!]
    latestOnly: Boolean! = false
  ): PackagesSearchResult!
}

type SearchHitPackage {
  id: ID!
  score: Float!
  bucket: String!
  name: String!
  pointer: String!
  hash: String!
  size: Float!
  modified: Datetime!
  totalEntriesCount: Int!
  comment: String
  meta: String # user_meta
  workflow: JsonRecord
  matchLocations: SearchHitPackageMatchLocations!
  matchingEntries: [SearchHitPackageMatchingEntry!]!
}
```

**Pagination** (lines 612-613):
```graphql
type Query {
  searchMoreObjects(after: String!, size: Int = 30): ObjectsSearchMoreResult!
  searchMorePackages(after: String!, size: Int = 30): PackagesSearchMoreResult!
}
```

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    Quilt Registry API                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  POST /graphql                                              │
│  ├─ Query: bucketConfigs ──────────► Elasticsearch Backend  │
│  ├─ Query: searchObjects ─────────► (Not used by ES)        │
│  ├─ Query: searchPackages ────────► (Not used by ES)        │
│  ├─ Query: admin.user.list ───────► quilt3.admin.users      │
│  ├─ Mutation: bucketAdd ──────────► quilt3.admin.buckets    │
│  └─ Mutation: bucketSetTabulatorTable ► quilt3 admin        │
│                                                              │
│  POST /tabulator/*                                          │
│  ├─ /credentials ─────────────────► Athena Connector        │
│  ├─ /buckets ─────────────────────► Athena Connector        │
│  ├─ /buckets/{name} ──────────────► Athena Connector        │
│  └─ /spill-location ──────────────► Athena Connector        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Insights

1. **Elasticsearch backend uses GraphQL minimally**: Only for bucket discovery via `bucketConfigs` query
2. **Actual search bypasses GraphQL**: Uses `quilt3.search_util.search_api()` directly to Elasticsearch
3. **Quilt3 admin uses GraphQL extensively**: All admin operations (users, roles, buckets, tabulator)
4. **Dual API for Tabulator**: REST endpoints for Athena connector, GraphQL for admin UI
5. **Native GraphQL search exists but unused**: `searchObjects` and `searchPackages` queries are available but not used by ES backend
6. **Code generation**: quilt3 client uses `ariadne-codegen` to generate type-safe Python models from GraphQL schema

## Potential Improvements

### Consider Using Native GraphQL Search

Instead of using `search_api()` with Elasticsearch DSL, the Elasticsearch backend could use the native GraphQL search queries:

**Current approach**:
```python
# Build DSL query
dsl_query = {"query": {"query_string": {"query": escaped_query}}}
# Call search_api directly
response = search_api(query=dsl_query, index=index_pattern, limit=limit)
```

**Potential alternative**:
```python
# Use GraphQL search
result = self.backend.execute_graphql_query("""
  query searchObjects($buckets: [String!], $searchString: String, $size: Int) {
    searchObjects(buckets: $buckets, searchString: $searchString) {
      ... on ObjectsSearchResultSet {
        total
        firstPage(size: $size) {
          hits {
            bucket
            key
            size
            modified
            score
          }
        }
      }
    }
  }
""", variables={"buckets": buckets, "searchString": query, "size": limit})
```

**Benefits**:
- Consistent API surface (all GraphQL)
- Better abstraction (registry handles ES details)
- Type-safe responses

**Drawbacks**:
- May lose flexibility of custom DSL queries
- Depends on registry search implementation
- Potential performance differences

## Related Files

- **Registry schema**: `~/GitHub/enterprise/registry/quilt_server/graphql/schema.graphql`
- **Registry GraphQL view**: `~/GitHub/enterprise/registry/quilt_server/views/graphql.py`
- **Tabulator REST views**: `~/GitHub/enterprise/registry/quilt_server/views/tabulator.py`
- **Tabulator models**: `~/GitHub/enterprise/registry/quilt_server/tabulator.py`
- **Quilt3 admin client**: `~/GitHub/quilt/api/python/quilt3/admin/`
- **Quilt3 GraphQL client**: `~/GitHub/quilt/api/python/quilt3/_graphql_client/`
- **ES backend**: `~/GitHub/quilt-mcp-server/src/quilt_mcp/search/backends/elasticsearch.py`
