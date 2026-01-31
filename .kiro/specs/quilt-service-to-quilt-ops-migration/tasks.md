# QuiltService → QuiltOps Migration Task Checklist

This checklist identifies every method that depends on quilt3 or QuiltService with its QuiltOps replacement. Use this to update callees/tests and delete the legacy version.

---

## Migration Status Key

- ✅ **QuiltOps method exists** - Ready to migrate callers
- 🚧 **QuiltOps method needs implementation** - Must implement before migration
- 🔄 **Partial implementation** - Exists but needs enhancement
- ❌ **No QuiltOps equivalent needed** - Delete or handle differently

---

## Authentication & Configuration Methods

### ✅ `is_authenticated() -> bool`

**QuiltOps Replacement:** `QuiltOpsFactory.create()` + check if instance created successfully
**Callers:**

- [ ] `src/quilt_mcp/services/auth_metadata.py:47` (used in `_get_catalog_info`)

**Migration Strategy:**

```python
# Before
service = QuiltService()
if service.is_authenticated():
    ...

# After
try:
    ops = QuiltOpsFactory.create()
    # If we got here, we're authenticated
    ...
except AuthenticationError:
    # Not authenticated
    ...
```

---

### 🚧 `get_logged_in_url() -> str | None`

**QuiltOps Replacement:** NEW: `get_auth_status() -> Auth_Status`
**Callers:**

- [ ] `src/quilt_mcp/services/auth_metadata.py:56` (in `_get_catalog_host_from_config`)
- [ ] `src/quilt_mcp/services/auth_metadata.py:156` (in `auth_status`)
- [ ] `src/quilt_mcp/services/auth_metadata.py:168` (in `get_catalog_info`)

**Requires Implementation:**

```python
# design.md lines 172-178
@abstractmethod
def get_auth_status(self) -> Auth_Status:
    """Get current authentication status."""
    pass

@dataclass
class Auth_Status:
    is_authenticated: bool
    logged_in_url: Optional[str]
    catalog_name: Optional[str]
    registry_url: Optional[str]
```

---

### 🚧 `get_config() -> dict | None`

**QuiltOps Replacement:** NEW: `get_catalog_config(catalog_url) -> Catalog_Config`
**Callers:**

- [ ] `src/quilt_mcp/services/auth_metadata.py:69` (in `_get_catalog_host_from_config`)
- [ ] `src/quilt_mcp/services/auth_metadata.py:161` (in `auth_status`)
- [ ] `src/quilt_mcp/services/auth_metadata.py:178` (in `configure_catalog`)

**Requires Implementation:**

```python
# design.md lines 181-196
@abstractmethod
def get_catalog_config(self, catalog_url: str) -> Catalog_Config:
    """Get catalog configuration."""
    pass

@dataclass
class Catalog_Config:
    region: str
    api_gateway_endpoint: str
    analytics_bucket: str
    stack_prefix: str
    tabulator_data_catalog: str
```

---

### 🚧 `get_catalog_config(catalog_url: str) -> dict | None`

**QuiltOps Replacement:** NEW: `get_catalog_config(catalog_url) -> Catalog_Config`
**Callers:**

- [ ] `src/quilt_mcp/services/auth_metadata.py:202` (in `get_catalog_info`)

**Same as above - needs implementation**

---

### 🚧 `set_config(catalog_url: str) -> None`

**QuiltOps Replacement:** NEW: `configure_catalog(catalog_url: str) -> None`
**Callers:**

- [ ] `src/quilt_mcp/services/auth_metadata.py:491` (in `configure_catalog`)

**Requires Implementation:**

```python
# design.md lines 190-196
@abstractmethod
def configure_catalog(self, catalog_url: str) -> None:
    """Configure the default catalog URL."""
    pass
```

---

### 🚧 `get_catalog_info() -> dict`

**QuiltOps Replacement:** Composite of multiple new methods:

- `get_auth_status() -> Auth_Status`
- `get_catalog_config(catalog_url) -> Catalog_Config`
- `get_registry_url() -> Optional[str]`

**Callers:**

- [ ] `src/quilt_mcp/services/auth_metadata.py:54` (in `_get_catalog_info`)
- [ ] `src/quilt_mcp/services/auth_metadata.py:155` (in `auth_status`)

**Migration Note:** This is a high-level helper that should be refactored to use multiple QuiltOps methods

---

## Session & GraphQL Methods

### 🚧 `has_session_support() -> bool`

**QuiltOps Replacement:** NEW: `get_auth_status() -> Auth_Status` (check `is_authenticated`)
**Callers:**

- [ ] `src/quilt_mcp/services/quilt_service.py:90` (internal use in `get_catalog_config`)

**Migration Note:** This is an internal implementation detail - QuiltOps just requires authentication

---

### 🚧 `get_session() -> Any`

**QuiltOps Replacement:** NEW: `execute_graphql_query(query, variables, registry) -> Dict`
**Callers:**

- [ ] `src/quilt_mcp/services/quilt_service.py:95` (internal use in `get_catalog_config`)
- [ ] `src/quilt_mcp/search/backends/elasticsearch.py:228` (in `_get_available_buckets`)

**Requires Implementation:**

```python
# design.md lines 502-518
@abstractmethod
def execute_graphql_query(
    self,
    query: str,
    variables: Optional[Dict] = None,
    registry: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a GraphQL query against the catalog."""
    pass
```

---

### 🚧 `get_registry_url() -> str | None`

**QuiltOps Replacement:** NEW: `get_registry_url() -> Optional[str]`
**Callers:**

- [ ] `src/quilt_mcp/search/backends/elasticsearch.py:186` (in `_check_session`)
- [ ] `src/quilt_mcp/search/backends/elasticsearch.py:207` (in `health_check`)
- [ ] `src/quilt_mcp/search/backends/elasticsearch.py:229` (in `_get_available_buckets`)

**Requires Implementation:**

```python
# design.md lines 538-544
@abstractmethod
def get_registry_url(self) -> Optional[str]:
    """Get the current default registry URL."""
    pass
```

---

### 🚧 `create_botocore_session() -> Any`

**QuiltOps Replacement:** NEW: `get_boto3_client(service_name, region) -> Any`
**Callers:**

- [ ] `src/quilt_mcp/services/athena_service.py:90` (in `_create_sqlalchemy_engine`)
- [ ] `src/quilt_mcp/services/athena_service.py:190` (in `_create_glue_client`)
- [ ] `src/quilt_mcp/services/athena_service.py:204` (in `_create_s3_client`)
- [ ] `src/quilt_mcp/services/athena_service.py:495` (in `list_workgroups`)

**Requires Implementation:**

```python
# design.md lines 520-535
@abstractmethod
def get_boto3_client(
    self,
    service_name: str,
    region: Optional[str] = None,
) -> Any:
    """Get authenticated boto3 client for AWS services."""
    pass
```

---

## Package Operations

### 🚧 `create_package_revision(...) -> Dict`

**QuiltOps Replacement:** NEW: `create_package_revision(...) -> Package_Creation_Result`
**Callers:**

- [ ] `src/quilt_mcp/tools/packages.py` (in `package_create`)

**Requires Implementation:**

```python
# design.md lines 241-250
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

@dataclass
class Package_Creation_Result:
    package_name: str
    registry: str
    top_hash: str
    catalog_url: Optional[str]
    file_count: int
    success: bool
```

---

### ✅ `browse_package(name, registry, top_hash) -> Any`

**QuiltOps Replacement:** EXISTING: `browse_content(package_name, registry, path) -> List[Content_Info]`
**Callers:**

- [ ] `src/quilt_mcp/tools/packages.py` (in various browse methods)

**Migration Strategy:**

```python
# Before
pkg = service.browse_package(name, registry)
# Manual iteration over pkg contents

# After
contents = ops.browse_content(package_name, registry, path="")
# Get List[Content_Info] directly
```

---

### 🚧 `list_packages(registry) -> Iterator[str]`

**QuiltOps Replacement:** NEW: `list_all_packages(registry) -> List[str]`
**Callers:**

- [ ] `src/quilt_mcp/tools/packages.py` (in `packages_list`)

**Requires Implementation:**

```python
# design.md lines 262-266
@abstractmethod
def list_all_packages(self, registry: str) -> List[str]:
    """List all package names in registry."""
    pass
```

---

## Bucket Operations

### ❌ `create_bucket(bucket_uri) -> Any`

**QuiltOps Replacement:** NONE - Not a domain operation
**Callers:**

- [ ] `src/quilt_mcp/tools/stack_buckets.py` (if used)

**Migration Strategy:**
Use `get_boto3_client('s3')` directly instead. Design doc (line 686) states this is not a Quilt domain operation.

---

## Search Operations

### 🚧 `get_search_api() -> Any`

**QuiltOps Replacement:** NEW: `search_packages(query, registry) -> List[Package_Info]`
**Callers:**

- [ ] `src/quilt_mcp/search/backends/elasticsearch.py:449` (in `search`)
- [ ] `src/quilt_mcp/tools/packages.py` (if used for search)

**Requires Implementation:**

```python
# design.md lines 620-646
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
    """Search for S3 objects across all packages."""
    pass
```

---

## Admin Operations - Tabulator

### 🚧 `is_admin_available() -> bool`

**QuiltOps Replacement:** Try/catch on admin operations
**Callers:**

- [ ] `src/quilt_mcp/services/tabulator_service.py:19` (module-level check)
- [ ] `src/quilt_mcp/services/governance_service.py:25` (module-level check)

**Migration Strategy:**

```python
# Before
ADMIN_AVAILABLE = quilt_service.is_admin_available()
if ADMIN_AVAILABLE:
    admin = quilt_service.get_tabulator_admin()

# After
try:
    tables = ops.list_tabulator_tables(catalog_name)
    # Admin is available
except PermissionError:
    # Admin not available
```

---

### 🚧 `get_tabulator_admin() -> Any`

**QuiltOps Replacement:** NEW: Multiple domain methods:

- `list_tabulator_tables(catalog_name) -> List[Tabulator_Table]`
- `create_tabulator_table(...) -> Tabulator_Table`
- `delete_tabulator_table(...) -> bool`
- `get_tabulator_table_info(...) -> Tabulator_Table`

**Callers:**

- [ ] `src/quilt_mcp/services/tabulator_service.py:141` (in `list_tables`)
- [ ] `src/quilt_mcp/services/tabulator_service.py:210` (in `create_table`)
- [ ] `src/quilt_mcp/services/tabulator_service.py:253` (in `delete_table`)
- [ ] `src/quilt_mcp/services/tabulator_service.py:292` (in `rename_table`)
- [ ] `src/quilt_mcp/services/tabulator_service.py:329` (in `get_open_query_status`)
- [ ] `src/quilt_mcp/services/tabulator_service.py:348` (in `set_open_query`)
- [ ] `src/quilt_mcp/services/governance_service.py:34` (module-level)
- [ ] `src/quilt_mcp/services/governance_service.py:1102` (in `admin_tabulator_open_query_get`)
- [ ] `src/quilt_mcp/services/governance_service.py:1152` (in `admin_tabulator_open_query_set`)

**Requires Implementation:**

```python
# design.md lines 422-456
@abstractmethod
def list_tabulator_tables(self, catalog_name: str) -> List[Tabulator_Table]:
    """List all Athena tables in the tabulator catalog."""
    pass

@abstractmethod
def create_tabulator_table(...) -> Tabulator_Table:
    """Create a new Athena table in tabulator."""
    pass

@abstractmethod
def delete_tabulator_table(catalog_name: str, table_name: str) -> bool:
    """Delete an Athena table from tabulator."""
    pass

@abstractmethod
def get_tabulator_table_info(...) -> Tabulator_Table:
    """Get detailed information about a tabulator table."""
    pass
```

---

## Admin Operations - Users

### 🚧 `get_users_admin() -> Any`

**QuiltOps Replacement:** NEW: Multiple domain methods:

- `list_catalog_users(registry) -> List[User_Info]`
- `get_user(username, registry) -> User_Info`
- `create_user(username, email, role, registry) -> User_Info`
- `delete_user(username, registry) -> bool`
- `set_user_role(username, role, registry) -> User_Info`

**Callers:**

- [ ] `src/quilt_mcp/services/governance_service.py:31` (module-level)
- [ ] `src/quilt_mcp/services/governance_service.py:115` (in `admin_users_list`)
- [ ] `src/quilt_mcp/services/governance_service.py:191` (in `admin_user_get`)
- [ ] `src/quilt_mcp/services/governance_service.py:317` (in `admin_user_create`)
- [ ] `src/quilt_mcp/services/governance_service.py:379` (in `admin_user_delete`)
- [ ] `src/quilt_mcp/services/governance_service.py:443` (in `admin_user_set_email`)
- [ ] `src/quilt_mcp/services/governance_service.py:505` (in `admin_user_set_admin`)
- [ ] `src/quilt_mcp/services/governance_service.py:567` (in `admin_user_set_active`)
- [ ] `src/quilt_mcp/services/governance_service.py:620` (in `admin_user_reset_password`)
- [ ] `src/quilt_mcp/services/governance_service.py:700` (in `admin_user_set_role`)
- [ ] `src/quilt_mcp/services/governance_service.py:768` (in `admin_user_add_roles`)
- [ ] `src/quilt_mcp/services/governance_service.py:845` (in `admin_user_remove_roles`)

**Requires Implementation:**

```python
# design.md lines 319-368
@abstractmethod
def list_catalog_users(self, registry: str) -> List[User_Info]:
    """List all users with access to the catalog."""
    pass

@abstractmethod
def get_user(self, username: str, registry: str) -> User_Info:
    """Get detailed information about a specific user."""
    pass

@abstractmethod
def create_user(username: str, email: str, role: str, registry: str) -> User_Info:
    """Create a new user in the catalog."""
    pass

@abstractmethod
def delete_user(self, username: str, registry: str) -> bool:
    """Remove a user from the catalog."""
    pass

@abstractmethod
def set_user_role(username: str, role: str, registry: str) -> User_Info:
    """Update a user's role."""
    pass
```

---

## Admin Operations - Roles

### 🚧 `get_roles_admin() -> Any`

**QuiltOps Replacement:** NEW: Multiple domain methods:

- `list_roles(registry) -> List[Role_Info]`
- `get_role_policies(role_name, registry) -> List[Policy_Info]`

**Callers:**

- [ ] `src/quilt_mcp/services/governance_service.py:32` (module-level)
- [ ] `src/quilt_mcp/services/governance_service.py:893` (in `admin_roles_list`)

**Requires Implementation:**

```python
# design.md lines 355-368
@abstractmethod
def list_roles(self, registry: str) -> List[Role_Info]:
    """List all available roles in the catalog."""
    pass

@abstractmethod
def get_role_policies(role_name: str, registry: str) -> List[Policy_Info]:
    """Get IAM policies attached to a role."""
    pass
```

---

## Admin Operations - SSO

### 🚧 `get_sso_config_admin() -> Any`

**QuiltOps Replacement:** NEW: Multiple domain methods:

- `get_sso_config(registry) -> SSO_Config`
- `set_sso_config(config, registry) -> SSO_Config`
- `delete_sso_config(registry) -> bool`

**Callers:**

- [ ] `src/quilt_mcp/services/governance_service.py:33` (module-level)
- [ ] `src/quilt_mcp/services/governance_service.py:950` (in `admin_sso_config_get`)
- [ ] `src/quilt_mcp/services/governance_service.py:1018` (in `admin_sso_config_set`)
- [ ] `src/quilt_mcp/services/governance_service.py:1066` (in `admin_sso_config_remove`)

**Requires Implementation:**

```python
# NEW - Not in design.md yet
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

---

## Admin Operations - Exceptions

### 🚧 `get_admin_exceptions() -> dict[str, type]`

**QuiltOps Replacement:** Use standard QuiltOps exceptions
**Callers:**

- [ ] `src/quilt_mcp/services/governance_service.py:38` (module-level)

**Migration Strategy:**
Replace with QuiltOps exception hierarchy:

```python
# design.md lines 697-721
from quilt_mcp.ops.exceptions import (
    QuiltOpsError,
    AuthenticationError,
    BackendError,
    ValidationError,
    NotFoundError,
    PermissionError,
)
```

---

## Implementation Priority

### Phase 1: Foundation (Week 1)

1. [ ] Implement `Auth_Status` and `get_auth_status()` in QuiltOps interface
2. [ ] Implement `Catalog_Config` and `get_catalog_config()` in QuiltOps interface
3. [ ] Implement `configure_catalog()` in QuiltOps interface
4. [ ] Implement `get_registry_url()` in QuiltOps interface
5. [ ] Implement all above in `Quilt3_Backend`
6. [ ] Add exception hierarchy in `src/quilt_mcp/ops/exceptions.py`

### Phase 2: AWS & GraphQL (Week 1-2)

7. [ ] Implement `execute_graphql_query()` in QuiltOps interface
2. [ ] Implement `get_boto3_client()` in QuiltOps interface
3. [ ] Implement both in `Quilt3_Backend`

### Phase 3: Package Operations (Week 2)

10. [ ] Implement `create_package_revision()` in QuiltOps interface
2. [ ] Implement `list_all_packages()` in QuiltOps interface
3. [ ] Implement `get_package_versions()` in QuiltOps interface
4. [ ] Implement all in `Quilt3_Backend`

### Phase 4: Search Operations (Week 2-3)

14. [ ] Implement `search_objects()` in QuiltOps interface
2. [ ] Enhance `search_packages()` if needed
3. [ ] Implement in `Quilt3_Backend`

### Phase 5: Admin - Tabulator (Week 3)

17. [ ] Implement all tabulator domain methods in QuiltOps interface
2. [ ] Implement `Tabulator_Table` and `Column_Info` dataclasses
3. [ ] Implement all in `Quilt3_Backend`
4. [ ] Migrate `src/quilt_mcp/services/tabulator_service.py`

### Phase 6: Admin - Users (Week 3-4)

21. [ ] Implement all user management methods in QuiltOps interface
2. [ ] Implement `User_Info` dataclass
3. [ ] Implement all in `Quilt3_Backend`
4. [ ] Migrate user management in `src/quilt_mcp/services/governance_service.py`

### Phase 7: Admin - Roles & SSO (Week 4)

25. [ ] Implement role management methods in QuiltOps interface
2. [ ] Implement SSO methods in QuiltOps interface
3. [ ] Implement `Role_Info`, `Policy_Info`, `SSO_Config` dataclasses
4. [ ] Implement all in `Quilt3_Backend`
5. [ ] Migrate remaining governance in `src/quilt_mcp/services/governance_service.py`

### Phase 8: Migrate Callers (Week 4-5)

30. [ ] Migrate `src/quilt_mcp/services/auth_metadata.py`
2. [ ] Migrate `src/quilt_mcp/services/athena_service.py`
3. [ ] Migrate `src/quilt_mcp/search/backends/elasticsearch.py`
4. [ ] Migrate `src/quilt_mcp/tools/packages.py`
5. [ ] Migrate `src/quilt_mcp/tools/stack_buckets.py`

### Phase 9: Testing & Cleanup (Week 5)

35. [ ] Update all tests to use QuiltOps instead of QuiltService
2. [ ] Run full test suite
3. [ ] Verify no QuiltService references remain (grep check)
4. [ ] Delete `src/quilt_mcp/services/quilt_service.py`
5. [ ] Update imports in `src/quilt_mcp/services/__init__.py`
6. [ ] Final integration testing

---

## Verification Commands

```bash
# Find all QuiltService usages
grep -r "QuiltService" src/ --include="*.py" | grep -v "__pycache__"

# Find all quilt_service references
grep -r "quilt_service\." src/ --include="*.py" | grep -v "__pycache__"

# Find all admin module accesses
grep -r "get_.*_admin\(\)" src/ --include="*.py" | grep -v "__pycache__"

# Verify QuiltService deletion readiness
grep -r "from.*quilt_service import" src/ --include="*.py" | grep -v "__pycache__"
```

---

## Success Criteria

- [ ] All QuiltService methods have QuiltOps equivalents
- [ ] All callers migrated to use QuiltOps
- [ ] All tests pass with QuiltOps
- [ ] No references to QuiltService remain in codebase
- [ ] `src/quilt_mcp/services/quilt_service.py` deleted
- [ ] Documentation updated
