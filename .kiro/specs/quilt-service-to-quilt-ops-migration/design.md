# QuiltOps Abstraction Layer - Design Document

## Purpose

QuiltOps is a **backend-agnostic abstraction layer** that isolates all Quilt catalog interactions behind a clean domain interface. This enables the codebase to switch between quilt3 library and direct GraphQL API calls without changing any MCP tool code.

---

## Core Design Principles

### 1. Domain Operations, Not Backend Leakage

**✅ CORRECT: High-level domain operations**

```python
# QuiltOps interface
def list_catalog_users(self, registry: str) -> List[User_Info]:
    """List all users with access to the catalog."""
    pass
```

**❌ WRONG: Exposing backend-specific modules**

```python
# This leaks quilt3 implementation details
def get_users_admin(self) -> Any:
    """Return quilt3.admin.users module."""
    return quilt3.admin.users
```

**Why?** The second approach makes GraphQL backend implementation impossible because GraphQL doesn't have a "users admin module" - it has API endpoints. Domain operations can be implemented by either backend.

---

### 2. Return Domain Objects, Not Backend Types

**✅ CORRECT: Domain types**

```python
@dataclass
class User_Info:
    username: str
    email: str
    role: str
    active: bool
```

**❌ WRONG: Backend-specific types**

```python
def get_package(self, name: str) -> quilt3.Package:
    """Returns quilt3.Package object."""
    pass
```

**Why?** Domain objects can be constructed from either quilt3 objects OR GraphQL responses. Backend-specific types lock us into one implementation.

---

### 3. Complete Operations, Not Partial Helpers

**✅ CORRECT: Complete workflow**

```python
def create_package_revision(
    self,
    package_name: str,
    s3_uris: List[str],
    metadata: Optional[Dict] = None,
    registry: Optional[str] = None,
) -> Package_Creation_Result:
    """Create and push a package in one operation."""
    pass
```

**❌ WRONG: Partial helper exposing internal state**

```python
def create_package(self, name: str) -> quilt3.Package:
    """Create package object (caller must populate and push)."""
    pass
```

**Why?** Complete operations encapsulate the entire workflow, allowing backends to optimize or implement differently. Partial helpers expose internal state management that may not translate across backends.

---

### 4. What Belongs in QuiltOps vs Utils

**QuiltOps Interface (src/quilt_mcp/ops/quilt_ops.py):**

- Methods that interact with Quilt catalogs/registries
- Methods that could be replaced with GraphQL API calls
- Examples: package operations, user management, catalog configuration

**Utils Module (src/quilt_mcp/utils.py):**

- Pure helper functions with NO quilt3 dependencies
- Generic utilities: parsing, formatting, validation
- Examples: URL parsing, date formatting, S3 URI validation

**NOT Allowed in Utils:**

```python
# ❌ WRONG - This belongs in QuiltOps
def get_quilt3_session() -> Any:
    return quilt3.session.get_session()
```

**Why?** Anything that touches quilt3 MUST go through QuiltOps so it can be replaced with GraphQL later.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Tools Layer                         │
│  (packages.py, catalog.py, governance.py, etc.)             │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ Uses domain operations only
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   QuiltOps Interface                         │
│                (src/quilt_mcp/ops/quilt_ops.py)             │
│                                                              │
│  Abstract methods defining domain operations:               │
│  - Package operations (create, browse, search)              │
│  - User management (list, create, delete)                   │
│  - Catalog configuration (get, set)                         │
│  - Content access (get URLs, browse)                        │
│  - Role management (list, assign)                           │
│  - Bucket operations (list accessible buckets)              │
│                                                              │
│  Returns: Domain objects (Package_Info, User_Info, etc.)    │
└─────────────┬───────────────────────┬───────────────────────┘
              │                       │
              │                       │
┌─────────────▼──────────┐  ┌────────▼──────────────────────┐
│   Quilt3_Backend       │  │   GraphQL_Backend             │
│  (Current)             │  │   (Future)                    │
│                        │  │                               │
│  Uses: quilt3 library  │  │  Uses: Direct GraphQL calls   │
│  - quilt3.Package      │  │  - Catalog API mutations      │
│  - quilt3.admin.*      │  │  - Catalog API queries        │
│  - quilt3.session.*    │  │  - Authentication tokens      │
└────────────────────────┘  └───────────────────────────────┘
```

---

## Domain Operations by Category

### Authentication & Configuration

**Current (QuiltService):**

```python
service.is_authenticated() -> bool
service.get_logged_in_url() -> str | None
service.get_config() -> dict | None
service.get_catalog_config(url) -> dict | None
service.set_config(url) -> None
```

**New (QuiltOps):**

```python
class QuiltOps(ABC):
    @abstractmethod
    def get_auth_status(self) -> Auth_Status:
        """Get current authentication status.

        Returns:
            Auth_Status with is_authenticated, logged_in_url, catalog_name
        """
        pass

    @abstractmethod
    def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
        """Get catalog configuration.

        Returns:
            Catalog_Config with region, api_endpoint, analytics_bucket, etc.
        """
        pass

    @abstractmethod
    def configure_catalog(self, catalog_url: str) -> None:
        """Configure the default catalog URL.

        Args:
            catalog_url: URL of catalog to configure
        """
        pass
```

**Domain Objects:**

```python
@dataclass
class Auth_Status:
    is_authenticated: bool
    logged_in_url: Optional[str]
    catalog_name: Optional[str]
    registry_url: Optional[str]

@dataclass
class Catalog_Config:
    region: str
    api_gateway_endpoint: str
    analytics_bucket: str
    stack_prefix: str
    tabulator_data_catalog: str
```

**Implementation Notes:**

- Quilt3_Backend: Uses `quilt3.logged_in()`, `quilt3.config()`, session for config.json
- GraphQL_Backend: Uses token introspection, catalog API config endpoint
- No raw session/config objects exposed

---

### Package Operations

**Current (QuiltService):**

```python
service.create_package_revision(name, s3_uris, metadata, registry, message, auto_organize, copy)
service.browse_package(name, registry, top_hash) -> quilt3.Package  # ❌ Wrong
service.list_packages(registry) -> Iterator[str]
```

**New (QuiltOps):**

```python
class QuiltOps(ABC):
    @abstractmethod
    def create_package_revision(
        self,
        package_name: str,
        s3_uris: List[str],
        metadata: Optional[Dict] = None,
        registry: Optional[str] = None,
        message: str = "Package created via QuiltOps",
    ) -> Package_Creation_Result:
        """Create and push package in single operation."""
        pass

    @abstractmethod
    def browse_content(
        self,
        package_name: str,
        registry: str,
        path: str = ""
    ) -> List[Content_Info]:
        """Browse package contents (already exists ✓)."""
        pass

    @abstractmethod
    def list_all_packages(self, registry: str) -> List[str]:
        """List all package names in registry."""
        pass

    @abstractmethod
    def get_package_versions(
        self,
        package_name: str,
        registry: str
    ) -> List[Package_Version]:
        """List all versions/revisions of a package."""
        pass
```

**Domain Objects:**

```python
@dataclass
class Package_Creation_Result:
    package_name: str
    registry: str
    top_hash: str
    catalog_url: Optional[str]
    file_count: int
    success: bool

@dataclass
class Package_Version:
    hash: str
    created: str  # ISO timestamp
    author: str
    message: str
```

**Implementation Notes:**

- No quilt3.Package objects exposed
- All operations return domain objects only
- GraphQL backend can implement using catalog mutations/queries

---

### User Management (Admin Operations)

**Current (QuiltService):**

```python
service.get_users_admin() -> Any  # Returns quilt3.admin.users module ❌
service.get_roles_admin() -> Any  # Returns quilt3.admin.roles module ❌
service.get_admin_exceptions() -> dict[str, type]
```

**New (QuiltOps):**

```python
class QuiltOps(ABC):
    @abstractmethod
    def list_catalog_users(self, registry: str) -> List[User_Info]:
        """List all users with access to the catalog."""
        pass

    @abstractmethod
    def get_user(self, username: str, registry: str) -> User_Info:
        """Get detailed information about a specific user."""
        pass

    @abstractmethod
    def create_user(
        self,
        username: str,
        email: str,
        role: str,
        registry: str,
    ) -> User_Info:
        """Create a new user in the catalog."""
        pass

    @abstractmethod
    def delete_user(self, username: str, registry: str) -> bool:
        """Remove a user from the catalog."""
        pass

    @abstractmethod
    def set_user_role(
        self,
        username: str,
        role: str,
        registry: str,
    ) -> User_Info:
        """Update a user's role."""
        pass

    @abstractmethod
    def list_roles(self, registry: str) -> List[Role_Info]:
        """List all available roles in the catalog."""
        pass

    @abstractmethod
    def get_role_policies(
        self,
        role_name: str,
        registry: str,
    ) -> List[Policy_Info]:
        """Get IAM policies attached to a role."""
        pass
```

**Domain Objects:**

```python
@dataclass
class User_Info:
    username: str
    email: str
    role: str
    active: bool
    date_joined: Optional[str]

@dataclass
class Role_Info:
    role_name: str
    arn: str
    policy_count: int

@dataclass
class Policy_Info:
    policy_name: str
    arn: str
    version: str
```

**Implementation Notes:**

- Replaces 12+ `get_users_admin()` calls with domain operations
- No admin modules or exceptions exposed
- Errors use standard QuiltOps exceptions (see Error Handling section)

---

### Tabulator & Data Access

**Current (QuiltService):**

```python
service.get_tabulator_admin() -> Any  # Returns quilt3.admin.tabulator module ❌
```

**Current Usage (tabulator_service.py):**

```python
admin = quilt_service.get_tabulator_admin()
tables = admin.list_tables(catalog_name="...")
admin.create_table(...)
admin.delete_table(...)
```

**New (QuiltOps):**

```python
class QuiltOps(ABC):
    @abstractmethod
    def list_tabulator_tables(self, catalog_name: str) -> List[Tabulator_Table]:
        """List all Athena tables in the tabulator catalog."""
        pass

    @abstractmethod
    def create_tabulator_table(
        self,
        catalog_name: str,
        table_name: str,
        s3_path: str,
        schema: Dict[str, str],
    ) -> Tabulator_Table:
        """Create a new Athena table in tabulator."""
        pass

    @abstractmethod
    def delete_tabulator_table(
        self,
        catalog_name: str,
        table_name: str,
    ) -> bool:
        """Delete an Athena table from tabulator."""
        pass

    @abstractmethod
    def get_tabulator_table_info(
        self,
        catalog_name: str,
        table_name: str,
    ) -> Tabulator_Table:
        """Get detailed information about a tabulator table."""
        pass
```

**Domain Objects:**

```python
@dataclass
class Tabulator_Table:
    table_name: str
    database: str
    s3_location: str
    columns: List[Column_Info]
    row_count: Optional[int]

@dataclass
class Column_Info:
    name: str
    type: str
    comment: Optional[str]
```

---

### Session & AWS Client Access

**Current (QuiltService):**

```python
service.has_session_support() -> bool
service.get_session() -> Any  # Returns requests.Session ❌
service.create_botocore_session() -> Any  # Returns botocore session ❌
service.get_registry_url() -> str | None
```

**Problem Analysis:**

These are used in:

1. **athena_service.py** - Creates boto3 clients with authenticated session
2. **elasticsearch.py** - Makes authenticated HTTP calls to catalog GraphQL
3. **auth_metadata.py** - Fetches catalog config.json

**New (QuiltOps):**

```python
class QuiltOps(ABC):
    @abstractmethod
    def execute_graphql_query(
        self,
        query: str,
        variables: Optional[Dict] = None,
        registry: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query against the catalog.

        Args:
            query: GraphQL query string
            variables: Query variables
            registry: Target registry (uses default if None)

        Returns:
            GraphQL response data
        """
        pass

    @abstractmethod
    def get_boto3_client(
        self,
        service_name: str,
        region: Optional[str] = None,
    ) -> Any:
        """Get authenticated boto3 client for AWS services.

        Args:
            service_name: AWS service name (e.g., 'athena', 's3')
            region: AWS region (uses catalog region if None)

        Returns:
            Configured boto3 client
        """
        pass

    @abstractmethod
    def get_registry_url(self) -> Optional[str]:
        """Get the current default registry URL.

        Returns:
            Registry S3 URL or None if not configured
        """
        pass
```

**Implementation Notes:**

**Quilt3_Backend:**

```python
def execute_graphql_query(self, query: str, variables=None, registry=None):
    session = quilt3.session.get_session()
    registry_url = registry or quilt3.session.get_registry_url()
    api_url = self._get_graphql_endpoint(registry_url)
    response = session.post(api_url, json={"query": query, "variables": variables})
    return response.json()

def get_boto3_client(self, service_name: str, region=None):
    botocore_session = quilt3.session.create_botocore_session()
    return boto3.Session(botocore_session=botocore_session).client(
        service_name, region_name=region
    )
```

**GraphQL_Backend:**

```python
def execute_graphql_query(self, query: str, variables=None, registry=None):
    # Use stored auth token directly
    headers = {"Authorization": f"Bearer {self._auth_token}"}
    response = requests.post(self._graphql_url,
                            json={"query": query, "variables": variables},
                            headers=headers)
    return response.json()

def get_boto3_client(self, service_name: str, region=None):
    # Use AWS credentials from catalog auth
    return boto3.client(
        service_name,
        region_name=region,
        aws_access_key_id=self._aws_access_key,
        aws_secret_access_key=self._aws_secret_key,
        aws_session_token=self._aws_session_token,
    )
```

**Why this works:**

- Both backends can implement authenticated requests
- No raw session objects exposed
- Callers get the functionality they need without backend coupling

---

### Search Operations

**Current (QuiltService):**

```python
service.get_search_api() -> Any  # Returns quilt3.search_util.search_api ❌
```

**Current Usage (elasticsearch.py):**

```python
search_api = quilt_service.get_search_api()
results = search_api.search(
    query="...",
    registry="...",
    limit=10
)
```

**New (QuiltOps):**

```python
class QuiltOps(ABC):
    @abstractmethod
    def search_packages(
        self,
        query: str,
        registry: str,
    ) -> List[Package_Info]:
        """Search for packages (already exists ✓)."""
        pass

    @abstractmethod
    def search_objects(
        self,
        query: str,
        registry: str,
        filters: Optional[Dict] = None,
    ) -> List[Object_Search_Result]:
        """Search for S3 objects across all packages.

        Args:
            query: Search query string
            registry: Registry to search
            filters: Optional filters (file type, size, date, etc.)

        Returns:
            List of matching objects with metadata
        """
        pass
```

**Domain Objects:**

```python
@dataclass
class Object_Search_Result:
    key: str
    package_name: str
    package_hash: str
    size: int
    last_modified: str
    metadata: Dict[str, Any]
```

---

### Bucket Operations

**Current (QuiltService):**

```python
service.create_bucket(bucket_uri: str) -> Any  # Returns quilt3.Bucket ❌
```

**Problem:** Exposes quilt3.Bucket object for S3 operations. Not actually used in current codebase.

**New (QuiltOps):**

```python
class QuiltOps(ABC):
    @abstractmethod
    def list_buckets(self) -> List[Bucket_Info]:
        """List accessible buckets (already exists ✓)."""
        pass

    # No create_bucket method needed - not a domain operation
    # S3 operations should use boto3 directly via get_boto3_client()
```

**Decision:** Remove `create_bucket()` - it's not a Quilt domain operation. If S3 access is needed, use `get_boto3_client('s3')` instead.

---

## Error Handling

### Standard Exceptions

All QuiltOps methods should raise domain-specific exceptions, never backend-specific errors:

```python
# src/quilt_mcp/ops/exceptions.py
class QuiltOpsError(Exception):
    """Base exception for QuiltOps operations."""
    pass

class AuthenticationError(QuiltOpsError):
    """Raised when authentication fails or credentials are invalid."""
    pass

class BackendError(QuiltOpsError):
    """Raised when backend operation fails."""
    pass

class ValidationError(QuiltOpsError):
    """Raised when input parameters are invalid."""
    pass

class NotFoundError(QuiltOpsError):
    """Raised when requested resource doesn't exist."""
    pass

class PermissionError(QuiltOpsError):
    """Raised when user lacks permission for operation."""
    pass
```

### Backend Translation

**Quilt3_Backend:**

```python
try:
    import quilt3.admin.users as users_admin
    user = users_admin.get_user(username)
except quilt3.admin.exceptions.UserNotFoundError as e:
    raise NotFoundError(f"User not found: {username}") from e
except quilt3.admin.exceptions.Quilt3AdminError as e:
    raise BackendError(f"Admin operation failed: {e}") from e
```

**GraphQL_Backend:**

```python
response = requests.post(graphql_url, json=query)
if response.status_code == 404:
    raise NotFoundError(f"User not found: {username}")
elif response.status_code == 403:
    raise PermissionError(f"Access denied for user operation")
elif not response.ok:
    raise BackendError(f"GraphQL query failed: {response.text}")
```

**Why?** Callers don't need to know about backend-specific exceptions. Domain exceptions work across all backends.

---

## Migration Strategy

### Phase 1: Add Domain Operations to QuiltOps Interface

For each QuiltService method category:

1. Design domain operations (no backend leakage)
2. Define domain objects (dataclasses)
3. Add abstract methods to QuiltOps interface
4. Add exception handling

### Phase 2: Implement in Quilt3_Backend

For each new domain operation:

1. Implement using existing quilt3 APIs
2. Translate quilt3 objects to domain objects
3. Map quilt3 exceptions to domain exceptions
4. Add unit tests

### Phase 3: Update Callers

For each file using QuiltService:

1. Replace QuiltService with QuiltOps dependency injection
2. Replace method calls with domain operations
3. Update to use domain objects instead of quilt3 objects
4. Update tests to match new implementation
5. Verify all tests pass

### Phase 4: Delete QuiltService

Once all callers migrated:

1. Verify no QuiltService references remain
2. Delete quilt_service.py
3. Run full test suite
4. Update documentation

---

## Example: Complete Migration of User Management

### Before (governance_service.py)

```python
from quilt_mcp.services.quilt_service import QuiltService

quilt_service = QuiltService()
ADMIN_AVAILABLE = quilt_service.is_admin_available()

if ADMIN_AVAILABLE:
    admin_users = quilt_service.get_users_admin()
    admin_exceptions = quilt_service.get_admin_exceptions()
    UserNotFoundError = admin_exceptions['UserNotFoundError']

def list_users(registry: str) -> List[Dict]:
    """List all users in the catalog."""
    if not ADMIN_AVAILABLE:
        raise Exception("Admin API not available")

    try:
        users = admin_users.list_users()  # Returns quilt3 admin objects
        return [
            {
                "username": u.name,
                "email": u.email,
                "role": u.role,
            }
            for u in users
        ]
    except UserNotFoundError as e:
        raise Exception(f"Error: {e}")
```

### After (governance_service.py)

```python
from quilt_mcp.ops import get_quilt_ops
from quilt_mcp.ops.exceptions import NotFoundError, BackendError
from quilt_mcp.domain import User_Info

quilt_ops = get_quilt_ops()

def list_users(registry: str) -> List[Dict]:
    """List all users in the catalog."""
    try:
        users: List[User_Info] = quilt_ops.list_catalog_users(registry)
        return [
            {
                "username": u.username,
                "email": u.email,
                "role": u.role,
            }
            for u in users
        ]
    except NotFoundError as e:
        raise Exception(f"Error: {e}")
```

**Changes:**

- ✅ No QuiltService dependency
- ✅ No admin module access
- ✅ Domain operations only
- ✅ Domain objects (User_Info)
- ✅ Domain exceptions
- ✅ Works with both quilt3 AND GraphQL backends

---

## Summary

### Key Decisions

1. **QuiltOps uses high-level domain operations only** - No get_session(), get_admin_module(), or other backend leakage
2. **All returns are domain objects** - No quilt3.Package, no admin modules, no sessions
3. **Complete operations, not partial helpers** - Each method does a full workflow
4. **Only Quilt operations go in QuiltOps** - Pure utilities stay in utils.py
5. **Standard exception hierarchy** - Backend-agnostic error handling

### Benefits

- ✅ Clean GraphQL backend implementation path
- ✅ No quilt3 coupling in MCP tools
- ✅ Testable with mock backends
- ✅ Clear separation of concerns
- ✅ Backend can optimize operations internally

### What's NOT in QuiltOps

- ❌ Raw session/config objects
- ❌ Admin modules
- ❌ Backend-specific exceptions
- ❌ Partial workflows requiring caller state management
- ❌ quilt3.Package or other library types
- ❌ Pure utilities (those go in utils.py)

---

## Appendix: Migration Code Examples

### A1: Migrating `is_authenticated()`

**Before:**

```python
service = QuiltService()
if service.is_authenticated():
    ...
```

**After:**

```python
try:
    ops = QuiltOpsFactory.create()
    # If we got here, we're authenticated
    ...
except AuthenticationError:
    # Not authenticated
    ...
```

---

### A2: Migrating `get_session()` for GraphQL

**Before:**

```python
session = quilt_service.get_session()
registry_url = quilt_service.get_registry_url()
api_url = self._get_graphql_endpoint(registry_url)
response = session.post(api_url, json={"query": query, "variables": variables})
```

**After:**

```python
response_data = ops.execute_graphql_query(
    query=query,
    variables=variables,
    registry=registry_url
)
```

---

### A3: Migrating `create_botocore_session()` for AWS Clients

**Before:**

```python
botocore_session = quilt_service.create_botocore_session()
boto3_session = boto3.Session(botocore_session=botocore_session)
client = boto3_session.client('athena', region_name=region)
```

**After:**

```python
client = ops.get_boto3_client('athena', region=region)
```

---

### A4: Migrating `browse_package()`

**Before:**

```python
pkg = service.browse_package(name, registry)
# Manual iteration over pkg contents
for key in pkg.keys():
    entry = pkg[key]
    # Process entry...
```

**After:**

```python
contents = ops.browse_content(package_name, registry, path="")
# Get List[Content_Info] directly
for content_info in contents:
    # Process content_info...
```

---

### A5: Migrating `is_admin_available()`

**Before:**

```python
ADMIN_AVAILABLE = quilt_service.is_admin_available()
if ADMIN_AVAILABLE:
    admin = quilt_service.get_tabulator_admin()
```

**After:**

```python
try:
    tables = ops.list_tabulator_tables(catalog_name)
    # Admin is available
except PermissionError:
    # Admin not available
```

---

### A6: Migrating `get_auth_status()` Implementation

**QuiltOps Interface:**

```python
@dataclass
class Auth_Status:
    is_authenticated: bool
    logged_in_url: Optional[str]
    catalog_name: Optional[str]
    registry_url: Optional[str]

@abstractmethod
def get_auth_status(self) -> Auth_Status:
    """Get current authentication status."""
    pass
```

**Quilt3_Backend Implementation:**

```python
def get_auth_status(self) -> Auth_Status:
    """Get current authentication status from quilt3."""
    try:
        logged_in_url = quilt3.logged_in()
        registry_url = quilt3.session.get_registry_url()
        catalog_name = None
        if logged_in_url:
            # Extract catalog name from URL if needed
            catalog_name = self._extract_catalog_name(logged_in_url)

        return Auth_Status(
            is_authenticated=bool(logged_in_url),
            logged_in_url=logged_in_url,
            catalog_name=catalog_name,
            registry_url=registry_url
        )
    except Exception as e:
        raise BackendError(f"Failed to get auth status: {e}") from e
```

---

### A7: Migrating `get_catalog_config()` Implementation

**QuiltOps Interface:**

```python
@dataclass
class Catalog_Config:
    region: str
    api_gateway_endpoint: str
    analytics_bucket: str
    stack_prefix: str
    tabulator_data_catalog: str

@abstractmethod
def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
    """Get catalog configuration."""
    pass
```

**Quilt3_Backend Implementation:**

```python
def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
    """Fetch catalog configuration from config.json."""
    try:
        session = quilt3.session.get_session()
        config_url = f"{catalog_url}/config.json"
        response = session.get(config_url)
        response.raise_for_status()
        config_data = response.json()

        return Catalog_Config(
            region=config_data.get('region', ''),
            api_gateway_endpoint=config_data.get('apiGatewayEndpoint', ''),
            analytics_bucket=config_data.get('analyticsBucket', ''),
            stack_prefix=config_data.get('stackPrefix', ''),
            tabulator_data_catalog=config_data.get('tabulatorDataCatalog', '')
        )
    except requests.HTTPError as e:
        raise NotFoundError(f"Catalog config not found: {catalog_url}") from e
    except Exception as e:
        raise BackendError(f"Failed to get catalog config: {e}") from e
```

---

### A8: Migrating `create_package_revision()` Implementation

**QuiltOps Interface:**

```python
@dataclass
class Package_Creation_Result:
    package_name: str
    registry: str
    top_hash: str
    catalog_url: Optional[str]
    file_count: int
    success: bool

@abstractmethod
def create_package_revision(
    self,
    package_name: str,
    s3_uris: List[str],
    metadata: Optional[Dict] = None,
    registry: Optional[str] = None,
    message: str = "Package created via QuiltOps",
) -> Package_Creation_Result:
    """Create and push package in single operation."""
    pass
```

**Quilt3_Backend Implementation:**

```python
def create_package_revision(
    self,
    package_name: str,
    s3_uris: List[str],
    metadata: Optional[Dict] = None,
    registry: Optional[str] = None,
    message: str = "Package created via QuiltOps",
) -> Package_Creation_Result:
    """Create and push a package using quilt3."""
    try:
        pkg = quilt3.Package()

        # Add files to package
        for s3_uri in s3_uris:
            logical_key = self._extract_logical_key(s3_uri)
            pkg.set(logical_key, s3_uri)

        # Set metadata if provided
        if metadata:
            pkg.set_meta(metadata)

        # Push to registry
        pkg_hash = pkg.push(package_name, registry=registry, message=message)

        # Get catalog URL
        catalog_url = None
        if registry:
            catalog_url = self._build_catalog_url(package_name, registry)

        return Package_Creation_Result(
            package_name=package_name,
            registry=registry or self.get_registry_url(),
            top_hash=pkg_hash,
            catalog_url=catalog_url,
            file_count=len(s3_uris),
            success=True
        )
    except Exception as e:
        raise BackendError(f"Failed to create package: {e}") from e
```

---

### A9: Migrating `execute_graphql_query()` Implementation

**Quilt3_Backend Implementation:**

```python
def execute_graphql_query(
    self,
    query: str,
    variables: Optional[Dict] = None,
    registry: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute GraphQL query using quilt3 session."""
    try:
        session = quilt3.session.get_session()
        registry_url = registry or quilt3.session.get_registry_url()

        if not registry_url:
            raise AuthenticationError("No registry configured")

        # Extract catalog URL from registry S3 URL
        api_url = self._get_graphql_endpoint(registry_url)

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = session.post(api_url, json=payload)
        response.raise_for_status()

        return response.json()
    except requests.HTTPError as e:
        if e.response.status_code == 403:
            raise PermissionError("GraphQL query not authorized") from e
        raise BackendError(f"GraphQL query failed: {e}") from e
    except Exception as e:
        raise BackendError(f"GraphQL execution error: {e}") from e
```

---

### A10: Migrating User Management

**Before (governance_service.py):**

```python
from quilt_mcp.services.quilt_service import QuiltService

quilt_service = QuiltService()
ADMIN_AVAILABLE = quilt_service.is_admin_available()

if ADMIN_AVAILABLE:
    admin_users = quilt_service.get_users_admin()
    admin_exceptions = quilt_service.get_admin_exceptions()
    UserNotFoundError = admin_exceptions['UserNotFoundError']

def list_users(registry: str) -> List[Dict]:
    """List all users in the catalog."""
    if not ADMIN_AVAILABLE:
        raise Exception("Admin API not available")

    try:
        users = admin_users.list_users()  # Returns quilt3 admin objects
        return [
            {
                "username": u.name,
                "email": u.email,
                "role": u.role,
            }
            for u in users
        ]
    except UserNotFoundError as e:
        raise Exception(f"Error: {e}")
```

**After (governance_service.py):**

```python
from quilt_mcp.ops import get_quilt_ops
from quilt_mcp.ops.exceptions import NotFoundError, BackendError, PermissionError
from quilt_mcp.domain import User_Info

quilt_ops = get_quilt_ops()

def list_users(registry: str) -> List[Dict]:
    """List all users in the catalog."""
    try:
        users: List[User_Info] = quilt_ops.list_catalog_users(registry)
        return [
            {
                "username": u.username,
                "email": u.email,
                "role": u.role,
            }
            for u in users
        ]
    except PermissionError as e:
        raise Exception(f"Admin access required: {e}")
    except NotFoundError as e:
        raise Exception(f"Error: {e}")
```

---

### A11: Migrating SSO Configuration Methods

**QuiltOps Interface:**

```python
@dataclass
class SSO_Config:
    provider: str
    metadata_url: Optional[str]
    entity_id: Optional[str]
    attribute_mapping: Dict[str, str]

@abstractmethod
def get_sso_config(self, registry: str) -> Optional[SSO_Config]:
    """Get current SSO configuration."""
    pass

@abstractmethod
def set_sso_config(self, config: str, registry: str) -> SSO_Config:
    """Set SSO configuration."""
    pass

@abstractmethod
def delete_sso_config(self, registry: str) -> bool:
    """Remove SSO configuration."""
    pass
```

**Quilt3_Backend Implementation:**

```python
def get_sso_config(self, registry: str) -> Optional[SSO_Config]:
    """Get SSO config using quilt3 admin."""
    try:
        from quilt3.admin import sso_config
        config_data = sso_config.get_config()

        if not config_data:
            return None

        return SSO_Config(
            provider=config_data.get('provider', ''),
            metadata_url=config_data.get('metadataUrl'),
            entity_id=config_data.get('entityId'),
            attribute_mapping=config_data.get('attributeMapping', {})
        )
    except Exception as e:
        raise BackendError(f"Failed to get SSO config: {e}") from e

def set_sso_config(self, config: str, registry: str) -> SSO_Config:
    """Set SSO config using quilt3 admin."""
    try:
        from quilt3.admin import sso_config
        result = sso_config.set_config(config)

        return SSO_Config(
            provider=result.get('provider', ''),
            metadata_url=result.get('metadataUrl'),
            entity_id=result.get('entityId'),
            attribute_mapping=result.get('attributeMapping', {})
        )
    except Exception as e:
        raise BackendError(f"Failed to set SSO config: {e}") from e
```
