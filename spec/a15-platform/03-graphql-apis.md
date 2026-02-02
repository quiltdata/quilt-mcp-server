# Platform Backend GraphQL API Mapping

**Status:** Design Phase
**Created:** 2026-01-31
**Purpose:** Map QuiltOps interface methods to Platform GraphQL queries/mutations

## Overview

This document maps each QuiltOps interface method to the corresponding Platform GraphQL API operations. The Platform backend will replace the current stub implementation at [platform_backend.py](../../../src/quilt_mcp/backends/platform_backend.py) with real GraphQL-based operations.

## GraphQL Endpoint

**Base URL Pattern:** `{registry_url}/graphql`

- Example: `https://example-registry.quiltdata.com/graphql`
- Method: `POST`
- Content-Type: `application/json`
- **Authentication: JWT Bearer Token** (primary method)

**Request Format:**

```json
{
  "query": "query { ... }",
  "variables": { ... }
}
```

## Authentication Strategy: JWT Bearer Tokens

The Platform backend uses **JWT authentication** as the primary method, following the existing pattern from [JWTAuthService](../../../src/quilt_mcp/services/jwt_auth_service.py).

### JWT Claims Structure

```python
{
    # Standard JWT claims
    "iss": "mcp-server",              # Issuer
    "aud": "mcp-server",              # Audience
    "sub": "user-123",                # Subject (user ID)
    "exp": 1234567890,                # Expiration timestamp
    "iat": 1234567890,                # Issued at timestamp

    # AWS role assumption
    "role_arn": "arn:aws:iam::123456789012:role/QuiltRole",

    # Catalog authentication (key claims for Platform backend)
    "catalog_token": "quilt-bearer-token-xyz...",  # Bearer token for catalog
    "catalog_url": "https://my-catalog.quiltdata.com",
    "registry_url": "https://my-registry.quiltdata.com"
}
```

### Creating Authenticated Sessions from JWT

The Platform backend will extract catalog credentials from JWT claims and create authenticated HTTP sessions:

```python
class Platform_Backend(QuiltOps):
    def __init__(self):
        self._catalog_url: Optional[str] = None
        self._session: requests.Session = requests.Session()

        # Extract catalog claims from JWT runtime context
        runtime_auth = get_runtime_auth()
        if runtime_auth and runtime_auth.claims:
            claims = runtime_auth.claims

            # Extract catalog authentication
            catalog_token = claims.get("catalog_token")
            catalog_url = claims.get("catalog_url")
            registry_url = claims.get("registry_url")

            if catalog_token:
                # Set bearer token in session headers
                self._session.headers["Authorization"] = f"Bearer {catalog_token}"

            if catalog_url:
                self._catalog_url = catalog_url

            if registry_url:
                self._registry_url = registry_url
```

### Session Usage for GraphQL Queries

```python
def execute_graphql_query(
    self,
    query: str,
    variables: Optional[Dict] = None,
    registry: Optional[str] = None
) -> Dict[str, Any]:
    # Determine GraphQL endpoint
    graphql_url = f"{normalize_url(self._registry_url)}/graphql"

    # Prepare payload
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    # Execute with authenticated session (bearer token in headers)
    response = self._session.post(graphql_url, json=payload)
    response.raise_for_status()

    return response.json()
```

**Key Points:**

- JWT `catalog_token` is used as Bearer token for all GraphQL requests
- Session is configured once during `__init__` from JWT runtime context
- All GraphQL queries automatically include authentication headers
- Follows the same pattern as [Quilt3_Backend session management](../../../src/quilt_mcp/backends/quilt3_backend_session.py)

## QuiltOps Method Mapping

### 1. Authentication & Configuration (4 methods)

#### 1.1 `get_auth_status() -> Auth_Status`

**Implementation Strategy:** Check session state + query catalog metadata

**GraphQL Queries:**

```graphql
# No specific query - use HTTP session validation
# Check if session is authenticated by attempting a simple query
query AuthCheck {
  me {
    name
    email
  }
}
```

**Domain Object Construction:**

```python
Auth_Status(
    is_authenticated=bool(response.get('data', {}).get('me')),
    logged_in_url=catalog_url,  # From session config
    catalog_name=extract_dns_name(catalog_url),
    registry_url=catalog_url
)
```

**Notes:**

- Platform backend stores catalog_url in instance variable during `configure_catalog()`
- If no catalog configured, `is_authenticated=False`
- Unlike Quilt3, Platform backend doesn't have `logged_in()` method - uses config state

---

#### 1.2 `get_registry_url() -> Optional[str]`

**Implementation Strategy:** Return stored catalog URL from instance config

**No GraphQL Query Required** - simple instance variable access

```python
def get_registry_url(self) -> Optional[str]:
    return self._catalog_url  # Instance variable
```

---

#### 1.3 `get_catalog_config(catalog_url: str) -> Catalog_Config`

**GraphQL Query:**

```graphql
query CatalogConfig {
  config {
    defaultBucket
    region
    apiGatewayEndpoint
    s3Endpoint
    analyticsDefaultBucket
    stackPrefix
    tabulatorDataCatalog
  }
}
```

**Schema Definition** (from `schema.graphql`):

```graphql
type Config {
  defaultBucket: String!
  region: String!
  apiGatewayEndpoint: String!
  s3Endpoint: String
  analyticsDefaultBucket: String!
  stackPrefix: String!
  tabulatorDataCatalog: String!
  # ... other fields
}

type Query {
  config: Config!
}
```

**Domain Object Construction:**

```python
Catalog_Config(
    region=data['config']['region'],
    api_gateway_endpoint=data['config']['apiGatewayEndpoint'],
    registry_url=catalog_url,  # Input parameter
    analytics_bucket=data['config']['analyticsDefaultBucket'],
    stack_prefix=data['config']['stackPrefix'],
    tabulator_data_catalog=data['config']['tabulatorDataCatalog']
)
```

**Error Handling:**

- `AuthenticationError`: If not authenticated
- `BackendError`: If query fails or config not found

---

#### 1.4 `configure_catalog(catalog_url: str) -> None`

**Implementation Strategy:** Store catalog URL in instance variable + validate connectivity

**GraphQL Query (Validation):**

```graphql
query ValidateCatalog {
  config {
    region
  }
}
```

**Implementation:**

```python
def configure_catalog(self, catalog_url: str) -> None:
    # Normalize URL
    normalized_url = normalize_url(catalog_url)

    # Validate connectivity by querying config
    result = self.execute_graphql_query(
        "query { config { region } }",
        registry=normalized_url
    )

    # Store if successful
    self._catalog_url = normalized_url
```

---

### 2. Package Discovery & Retrieval (4 methods)

#### 2.1 `search_packages(query: str, registry: str) -> List[Package_Info]`

**GraphQL Query:**

```graphql
query SearchPackages($buckets: [String!], $searchString: String, $size: Int) {
  searchPackages(
    buckets: $buckets
    searchString: $searchString
    latestOnly: true
  ) {
    ... on PackagesSearchResultSet {
      total
      firstPage(size: $size) {
        hits {
          bucket
          name
          hash
          modified
          comment
          meta
        }
      }
    }
    ... on EmptySearchResultSet {
      __typename
    }
    ... on InvalidInput {
      message
    }
    ... on OperationError {
      message
    }
  }
}
```

**Schema Definition:**

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
  bucket: String!
  name: String!
  hash: String!
  modified: Datetime!
  comment: String
  meta: String  # JSON user_meta
  size: Float!
  totalEntriesCount: Int!
}
```

**Variables:**

```python
{
    "buckets": [bucket_name],  # Extract from registry: s3://bucket -> bucket
    "searchString": query,
    "size": 1000
}
```

**Domain Object Construction:**

```python
Package_Info(
    name=hit['name'],
    description=hit.get('comment', ''),  # GraphQL uses 'comment'
    tags=extract_tags_from_meta(hit.get('meta')),  # Parse JSON meta
    modified_date=hit['modified'],
    registry=registry,
    bucket=hit['bucket'],
    top_hash=hit['hash']
)
```

**Notes:**

- GraphQL uses `comment` field instead of `description`
- Tags must be extracted from `meta` JSON field
- `latestOnly: true` returns only latest package revisions

---

#### 2.2 `get_package_info(package_name: str, registry: str) -> Package_Info`

**GraphQL Query:**

```graphql
query GetPackage($bucket: String!, $name: String!) {
  package(bucket: $bucket, name: $name) {
    name
    hash
    modified
    comment
    userMeta
    workflow
    stats {
      totalBytes
      totalObjects
    }
  }
}
```

**Schema Definition:**

```graphql
type Query {
  package(bucket: String!, name: String!, hash: String): Package!
}

type Package {
  name: String!
  hash: String!
  modified: Datetime!
  comment: String
  userMeta: JsonRecord
  workflow: JsonRecord
  stats: PackageStats!
}

type PackageStats {
  totalBytes: Float!
  totalObjects: Int!
}
```

**Variables:**

```python
{
    "bucket": extract_bucket_from_registry(registry),
    "name": package_name
}
```

**Domain Object Construction:**

```python
Package_Info(
    name=data['package']['name'],
    description=data['package'].get('comment', ''),
    tags=extract_tags_from_user_meta(data['package'].get('userMeta', {})),
    modified_date=data['package']['modified'],
    registry=registry,
    bucket=bucket_name,
    top_hash=data['package']['hash']
)
```

---

#### 2.3 `list_all_packages(registry: str) -> List[str]`

**GraphQL Query:**

```graphql
query ListAllPackages($bucket: String!) {
  packages(bucket: $bucket) {
    page {
      packages {
        name
      }
    }
  }
}
```

**Schema Definition:**

```graphql
type Query {
  packages(bucket: String!): PackageList!
}

type PackageList {
  page: PackageListPage!
}

type PackageListPage {
  packages: [PackageListItem!]!
  nextToken: String
}

type PackageListItem {
  name: String!
  modified: Datetime!
}
```

**Domain Object Construction:**

```python
package_names = [
    pkg['name']
    for pkg in data['packages']['page']['packages']
]
```

**Notes:**

- Returns simple list of package names (not full Package_Info objects)
- May need pagination if registry has many packages

---

#### 2.4 `diff_packages(...) -> Dict[str, List[str]]`

**GraphQL Query:**

```graphql
query DiffPackages(
  $bucket1: String!
  $name1: String!
  $hash1: String
  $bucket2: String!
  $name2: String!
  $hash2: String
) {
  package1: package(bucket: $bucket1, name: $name1, hash: $hash1) {
    entries {
      logicalKey
      hash
    }
  }
  package2: package(bucket: $bucket2, name: $name2, hash: $hash2) {
    entries {
      logicalKey
      hash
    }
  }
}
```

**Implementation Strategy:**

```python
# Fetch both packages
entries1 = {e['logicalKey']: e['hash'] for e in data['package1']['entries']}
entries2 = {e['logicalKey']: e['hash'] for e in data['package2']['entries']}

# Compute differences
added = [k for k in entries2 if k not in entries1]
deleted = [k for k in entries1 if k not in entries2]
modified = [k for k in entries1 if k in entries2 and entries1[k] != entries2[k]]

return {
    "added": added,
    "deleted": deleted,
    "modified": modified
}
```

---

### 3. Content Operations (2 methods)

#### 3.1 `browse_content(package_name: str, registry: str, path: str = "") -> List[Content_Info]`

**GraphQL Query:**

```graphql
query BrowsePackage($bucket: String!, $name: String!, $path: String) {
  package(bucket: $bucket, name: $name) {
    dir(path: $path) {
      path
      size
      physicalKey
      modified
    }
    accessCounts(path: $path) {
      path
      counts {
        total
      }
    }
  }
}
```

**Schema Definition:**

```graphql
type Package {
  dir(path: String): [PackageDir!]!
}

type PackageDir {
  path: String!
  size: Float
  physicalKey: String
  modified: Datetime
}
```

**Domain Object Construction:**

```python
Content_Info(
    path=entry['path'],
    size=int(entry['size']) if entry.get('size') else None,
    type='file' if entry.get('physicalKey') else 'directory',
    modified_date=entry.get('modified'),
    download_url=None  # Populated separately if needed
)
```

**Notes:**

- `physicalKey` presence indicates file (vs directory)
- Path separators handled by GraphQL API
- Download URLs require separate query (see get_content_url)

---

#### 3.2 `get_content_url(package_name: str, registry: str, path: str) -> str`

**GraphQL Query:**

```graphql
query GetContentURL($bucket: String!, $name: String!, $path: String!) {
  package(bucket: $bucket, name: $name) {
    file(path: $path) {
      physicalKey
    }
  }
}
```

**Implementation Strategy:**

```python
# Step 1: Get physicalKey from GraphQL
result = self.execute_graphql_query(query, variables)
physical_key = result['data']['package']['file']['physicalKey']

# Step 2: Generate presigned URL using boto3
s3_client = self.get_boto3_client('s3')
url = s3_client.generate_presigned_url(
    'get_object',
    Params={
        'Bucket': bucket_name,
        'Key': physical_key
    },
    ExpiresIn=3600  # 1 hour
)

return url
```

**Notes:**

- GraphQL doesn't directly provide download URLs
- Must use boto3 to generate presigned S3 URLs
- Requires AWS credentials from catalog config

---

### 4. Bucket Operations (1 method)

#### 4.1 `list_buckets() -> List[Bucket_Info]`

**GraphQL Query:**

```graphql
query ListBuckets {
  bucketConfigs {
    name
    title
    description
    tags
    lastIndexed
    relevanceScore
  }
}
```

**Schema Definition:**

```graphql
type Query {
  bucketConfigs: [BucketConfig!]!
}

type BucketConfig {
  name: String!
  title: String!
  description: String
  tags: [String!]
  lastIndexed: Datetime
  relevanceScore: Int!
  browsable: Boolean!
  # ... many more fields
}
```

**Domain Object Construction:**

```python
Bucket_Info(
    name=config['name'],
    region='unknown',  # Not in GraphQL response - need to get from AWS
    access_level='read',  # Assume read access (user can query it)
    created_date=config.get('lastIndexed')
)
```

**Notes:**

- GraphQL `bucketConfigs` provides bucket metadata, not AWS details
- Region must be obtained from catalog config or boto3
- Access level is inferred (if user can see it, they have at least read access)

---

### 5. Package Creation & Updates (2 methods)

#### IMPORTANT: Use quilt3 Package Engine, NOT GraphQL mutations

The Platform backend should delegate to the quilt3 Package Engine for package creation and updates,
exactly like [Quilt3_Backend does](../../../src/quilt_mcp/backends/quilt3_backend_packages.py#L298-L410).
This provides:

- **Consistent behavior** with Quilt3_Backend
- **Efficient local operations** (no GraphQL roundtrips)
- **Full selector_fn support** for copy behavior
- **auto_organize logic** already implemented
- **Proven error handling** patterns

#### 5.1 `create_package_revision(...) -> Package_Creation_Result`

**Implementation Strategy: Delegate to quilt3.Package**

```python
def create_package_revision(
    self,
    package_name: str,
    s3_uris: List[str],
    metadata: Optional[Dict] = None,
    registry: Optional[str] = None,
    message: str = "Package created via QuiltOps",
    auto_organize: bool = True,
    copy: bool = False,
) -> Package_Creation_Result:
    """Create package using quilt3 Package Engine."""
    try:
        # Use quilt3 Package class (requires quilt3 import)
        import quilt3

        # Step 1: Create empty package
        package = quilt3.Package()

        # Step 2: Add files to package
        for s3_uri in s3_uris:
            # Extract logical key based on auto_organize
            logical_key = self._extract_logical_key(s3_uri, auto_organize=auto_organize)

            # Add entry to package (maps logical key to physical S3 location)
            package.set(logical_key, s3_uri)

        # Step 3: Set package metadata
        if metadata:
            package.set_meta(metadata)

        # Step 4: Define selector function for copy behavior
        if copy:
            # Copy all files to registry bucket
            selector_fn = lambda logical_key, entry: True
        else:
            # Don't copy - just reference existing S3 locations
            selector_fn = lambda logical_key, entry: False

        # Step 5: Push package to registry
        registry_url = registry or self._registry_url
        if not registry_url:
            raise ValidationError("No registry configured")

        top_hash = package.push(
            package_name,
            registry=registry_url,
            message=message,
            selector_fn=selector_fn,
        )

        # Step 6: Construct result
        file_count = len(s3_uris)
        bucket_name = registry_url.replace("s3://", "").split("/")[0]
        catalog_url = f"{self._catalog_url}/b/{bucket_name}/packages/{package_name}"

        return Package_Creation_Result(
            package_name=package_name,
            top_hash=top_hash,
            registry=registry_url,
            catalog_url=catalog_url,
            file_count=file_count,
            success=True,
        )

    except Exception as e:
        # Mirror Quilt3_Backend error handling
        raise BackendError(
            f"Platform backend create_package_revision failed: {str(e)}",
            context={
                'package_name': package_name,
                'registry': registry,
                's3_uri_count': len(s3_uris),
            },
        )
```

##### Helper Method (from Quilt3_Backend)

```python
def _extract_logical_key(self, s3_uri: str, auto_organize: bool) -> str:
    """Extract logical key from S3 URI based on auto_organize setting.

    Args:
        s3_uri: S3 URI like "s3://bucket/path/to/file.csv"
        auto_organize: If True, preserve directory structure; if False, use filename only

    Returns:
        Logical key for package entry
    """
    # Parse S3 URI to extract key
    if not s3_uri.startswith("s3://"):
        raise ValidationError(f"Invalid S3 URI: {s3_uri}")

    # Remove s3:// prefix and split into bucket/key
    path = s3_uri[5:]  # Remove "s3://"
    parts = path.split("/", 1)
    if len(parts) < 2:
        raise ValidationError(f"Invalid S3 URI format: {s3_uri}")

    bucket, key = parts

    if auto_organize:
        # Preserve full directory structure
        return key
    else:
        # Use only filename (last component)
        return key.split("/")[-1]
```

##### Why Use quilt3 Package Engine Instead of GraphQL?

1. **Consistency**: Identical behavior to Quilt3_Backend
2. **Efficiency**: Local operations, no network roundtrips for package building
3. **Selector Functions**: Fine-grained control over copy behavior (not available in GraphQL)
4. **Error Handling**: Proven patterns from Quilt3_Backend
5. **Code Reuse**: Can extract shared helpers to base class

---

#### 5.2 `update_package_revision(...) -> Package_Creation_Result`

**Implementation Strategy: Use quilt3 Package Engine (same as create)**

The implementation is nearly identical to `create_package_revision`, using `quilt3.Package` and `package.push()`.
The quilt3 Package Engine automatically creates a new revision if the package already exists.

##### Key Differences from create_package_revision

- `auto_organize` defaults to **False** (not True)
- `copy` parameter is a **string** ("none", "all") instead of bool
- `registry` parameter is **required** (not optional)

```python
def update_package_revision(
    self,
    package_name: str,
    s3_uris: List[str],
    registry: str,
    metadata: Optional[Dict] = None,
    message: str = "Package updated via QuiltOps",
    auto_organize: bool = False,  # Different default!
    copy: str = "none",           # String enum!
) -> Package_Creation_Result:
    """Update package using quilt3 Package Engine."""

    # Convert copy string to selector function
    if copy == "all":
        selector_fn = lambda logical_key, entry: True
    elif copy == "none":
        selector_fn = lambda logical_key, entry: False
    else:
        raise ValidationError(f"Invalid copy parameter: {copy}. Must be 'all' or 'none'")

    # Delegate to same implementation as create_package_revision
    # (code is identical except for parameter defaults)
    ...
```

**Mirror Quilt3_Backend Error Handling:**

Follow the exact error handling patterns from
[Quilt3_Backend.update_package_revision](../../../src/quilt_mcp/backends/quilt3_backend_packages.py#L412-L477)

---

### 6. AWS & GraphQL Access (2 methods)

#### 6.1 `execute_graphql_query(query: str, variables: Optional[Dict], registry: Optional[str]) -> Dict[str, Any]`

**Implementation Pattern:**

```python
def execute_graphql_query(
    self,
    query: str,
    variables: Optional[Dict] = None,
    registry: Optional[str] = None
) -> Dict[str, Any]:
    # Determine GraphQL endpoint
    if registry:
        graphql_url = f"{normalize_url(registry)}/graphql"
    elif self._catalog_url:
        graphql_url = f"{normalize_url(self._catalog_url)}/graphql"
    else:
        raise AuthenticationError("No catalog configured")

    # Prepare request
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    # Execute with authenticated session
    response = self._session.post(graphql_url, json=payload)
    response.raise_for_status()

    result = response.json()

    # Check for GraphQL errors
    if 'errors' in result:
        raise BackendError(f"GraphQL errors: {result['errors']}")

    return result
```

**Session Management:**

- Platform backend needs to maintain `requests.Session` with authentication
- Session may use cookies, bearer token, or API key
- Must handle token refresh if using short-lived tokens

---

#### 6.2 `get_boto3_client(service_name: str, region: Optional[str]) -> Any`

**Implementation Strategy: Use JWT-derived AWS session**

The Platform backend should use the AWS session obtained from JWT role assumption via
[JWTAuthService](../../../src/quilt_mcp/services/jwt_auth_service.py).

```python
def get_boto3_client(self, service_name: str, region: Optional[str] = None) -> Any:
    """Get authenticated boto3 client for AWS services.

    Uses AWS credentials from JWT role assumption (via JWTAuthService).
    The JWT contains role_arn claim, which JWTAuthService uses to assume
    the role and obtain temporary AWS credentials.
    """
    try:
        import boto3

        # Get AWS session from JWT auth service
        # This session has temporary credentials from STS AssumeRole
        from quilt_mcp.services.jwt_auth_service import JWTAuthService

        auth_service = JWTAuthService()
        boto3_session = auth_service.get_boto3_session()

        # Create client for requested service
        client = boto3_session.client(
            service_name,
            region_name=region  # region from JWT claims used if None
        )

        return client

    except Exception as e:
        raise BackendError(
            f"Failed to create boto3 client for {service_name}: {str(e)}"
        )
```

##### JWT Flow for AWS Credentials

1. JWT contains `role_arn` claim (e.g., `arn:aws:iam::123456789012:role/QuiltRole`)
2. JWTAuthService calls `sts.assume_role()` with the role ARN
3. STS returns temporary credentials (access key, secret key, session token)
4. JWTAuthService creates boto3.Session with these credentials
5. Platform backend uses this session to create service clients

**Error Handling:**

Mirror the exact error handling from
[Quilt3_Backend.get_boto3_client](../../../src/quilt_mcp/backends/quilt3_backend_session.py#L364-L409)

---

### 7. Admin Operations (via `admin` property)

#### 7.1 User Management Methods

**List Users:**

```graphql
query ListUsers {
  admin {
    user {
      list {
        name
        email
        isActive
        isAdmin
        isSsoOnly
        isService
        dateJoined
        lastLogin
        role {
          id
          name
          arn
          type
        }
        extraRoles {
          id
          name
          arn
          type
        }
      }
    }
  }
}
```

**Get User:**

```graphql
query GetUser($name: String!) {
  admin {
    user {
      get(name: $name) {
        name
        email
        isActive
        isAdmin
        # ... same fields as list
      }
    }
  }
}
```

**Create User:**

```graphql
mutation CreateUser($input: UserInput!) {
  admin {
    user {
      create(input: $input) {
        ... on UserSuccess {
          user {
            name
            email
            # ... full user fields
          }
        }
        ... on InvalidInput {
          message
        }
        ... on OperationError {
          message
        }
      }
    }
  }
}
```

**Delete User:**

```graphql
mutation DeleteUser($name: String!) {
  admin {
    user {
      mutate(name: $name) {
        delete {
          ... on OperationSuccess {
            message
          }
          ... on InvalidInput {
            message
          }
        }
      }
    }
  }
}
```

**Update User Operations (all via `mutate`):**

```graphql
mutation UpdateUser($name: String!, $email: String) {
  admin {
    user {
      mutate(name: $name) {
        setEmail(email: $email) {
          ... on UserSuccess {
            user { name email }
          }
        }
      }
    }
  }
}
```

---

#### 7.2 Role Management

**List Roles:**

```graphql
query ListRoles {
  roles {
    id
    name
    arn
    type
  }
}
```

**Note:** `@admin` directive required for roles query

---

#### 7.3 SSO Configuration

**Get SSO Config:**

```graphql
query GetSSOConfig {
  admin {
    ssoConfig {
      text
      timestamp
      uploader {
        name
        email
      }
    }
  }
}
```

**Set SSO Config:**

```graphql
mutation SetSSOConfig($config: String!) {
  admin {
    setSsoConfig(config: $config) {
      ... on SsoConfigSuccess {
        ssoConfig {
          text
          timestamp
        }
      }
      ... on InvalidInput {
        message
      }
    }
  }
}
```

**Remove SSO Config:**

```graphql
mutation RemoveSSOConfig {
  admin {
    removeSsoConfig {
      ... on OperationSuccess {
        message
      }
    }
  }
}
```

---

## Implementation Architecture

### Class Structure

```python
class Platform_Backend(QuiltOps):
    """Platform GraphQL backend implementation."""

    def __init__(self):
        self._catalog_url: Optional[str] = None
        self._session: requests.Session = requests.Session()
        self._admin_ops: Optional[Platform_Admin_Ops] = None

    @property
    def admin(self) -> 'Platform_Admin_Ops':
        if self._admin_ops is None:
            self._admin_ops = Platform_Admin_Ops(self)
        return self._admin_ops

class Platform_Admin_Ops(AdminOps):
    """Admin operations for Platform backend."""

    def __init__(self, backend: Platform_Backend):
        self._backend = backend
```

### Helper Methods Needed

```python
def _normalize_url(url: str) -> str:
    """Normalize catalog URL (remove trailing slash, ensure https)."""

def _extract_bucket_from_registry(registry: str) -> str:
    """Extract bucket name from s3://bucket-name format."""

def _parse_s3_uri(s3_uri: str) -> Tuple[str, str]:
    """Parse s3://bucket/key into (bucket, key)."""

def _extract_tags_from_meta(meta: Optional[Dict]) -> List[str]:
    """Extract tags from userMeta JSON."""

def _compute_logical_key(physical_key: str, auto_organize: bool) -> str:
    """Compute logical key based on auto_organize setting."""

def _transform_graphql_package(data: Dict) -> Package_Info:
    """Transform GraphQL package response to domain object."""

def _transform_graphql_user(data: Dict) -> User:
    """Transform GraphQL user response to domain object."""
```

---

## Authentication Strategy (UPDATED)

The Platform backend now uses **JWT Bearer tokens** extracted from runtime context (see top of document for details).

**Deprecated authentication options** (no longer used):

- ~~Session cookies~~ - Not needed, JWT provides stateless auth
- ~~API keys~~ - JWT is the standard
- ~~Username/password~~ - Authentication handled upstream

**Migration Note:**

Remove the old authentication sections above. All authentication is now handled via:

1. JWT middleware extracts bearer token from HTTP headers
2. Platform_Backend reads JWT claims from runtime context
3. `catalog_token` claim provides bearer token for GraphQL
4. `role_arn` claim provides AWS credentials via STS AssumeRole

---

## Testing Strategy

### Unit Tests

Test GraphQL query construction and response transformation:

```python
def test_search_packages_query_construction():
    backend = Platform_Backend()
    query, variables = backend._build_search_packages_query(
        query="covid",
        registry="s3://my-bucket"
    )
    assert "searchPackages" in query
    assert variables["buckets"] == ["my-bucket"]
    assert variables["searchString"] == "covid"
```

### Integration Tests

Test real GraphQL API calls:

```python
@pytest.mark.integration
def test_search_packages_integration(platform_backend):
    results = platform_backend.search_packages(
        query="test",
        registry="s3://test-bucket"
    )
    assert isinstance(results, list)
    assert all(isinstance(p, Package_Info) for p in results)
```

---

## Migration Path

### Phase 1: Core Implementation

- `configure_catalog()`, `get_registry_url()`, `get_auth_status()`
- `execute_graphql_query()`, `get_catalog_config()`
- Basic session management

### Phase 2: Read Operations

- `list_buckets()`, `search_packages()`, `get_package_info()`
- `browse_content()`, `get_content_url()`
- `list_all_packages()`

### Phase 3: Write Operations

- `create_package_revision()`, `update_package_revision()`
- `get_boto3_client()` (for S3 operations)
- `diff_packages()`

### Phase 4: Admin Operations

- User management (list, get, create, delete, update)
- Role management (list)
- SSO configuration (get, set, remove)

---

## Resolved Design Decisions

### ✅ 1. Authentication Method

**Decision:** JWT Bearer tokens via runtime context

- JWT contains `catalog_token` claim for GraphQL authentication
- Extracted from runtime context during `__init__`
- Set once in `requests.Session` headers
- See [JWTAuthService](../../../src/quilt_mcp/services/jwt_auth_service.py)

### ✅ 2. AWS Credentials

**Decision:** JWT role assumption via STS

- JWT contains `role_arn` claim
- JWTAuthService calls `sts.assume_role()` to get temporary credentials
- boto3.Session created with temp credentials
- Region from JWT claims or catalog config

### ✅ 3. Package Creation Strategy

**Decision:** Use quilt3 Package Engine (not GraphQL)

- Delegate to `quilt3.Package` class like Quilt3_Backend does
- Provides consistent behavior and full feature support
- GraphQL `packageConstruct` mutation not used
- Enables selector functions for fine-grained copy control

### ✅ 4. Error Handling

**Decision:** Mirror Quilt3_Backend patterns exactly

- Catch all exceptions and wrap in domain-specific errors
- Use `BackendError`, `AuthenticationError`, `ValidationError`, etc.
- Include context dict in error construction
- Follow patterns from [Quilt3_Backend](../../../src/quilt_mcp/backends/)

### ⚠️ 5. Pagination (Still Open)

**Question:** Do we need cursor-based pagination for large result sets?

- `searchPackages` supports pagination via cursor
- `packages` query has `nextToken`
- **Recommendation:** Start with simple implementation (no pagination)
- Add pagination in Phase 2 if needed based on usage patterns

---

## References

- GraphQL Schema: `~/GitHub/enterprise/registry/quilt_server/graphql/schema.graphql`
- Registry GraphQL View: `~/GitHub/enterprise/registry/quilt_server/views/graphql.py`
- Quilt3 GraphQL Client: `~/GitHub/quilt/api/python/quilt3/_graphql_client/`
- Current Stub: [platform_backend.py](../../../src/quilt_mcp/backends/platform_backend.py)
- QuiltOps Interface: [quilt_ops.py](../../../src/quilt_mcp/ops/quilt_ops.py)
- Domain Objects: [domain/](../../../src/quilt_mcp/domain/)
