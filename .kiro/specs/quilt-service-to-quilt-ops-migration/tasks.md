# QuiltService → QuiltOps Migration Task Checklist

This checklist identifies every method that depends on quilt3 or QuiltService with its QuiltOps replacement.
Use this to update callees/tests and delete the legacy version.

> **Note:** For code examples and migration patterns, see the
> [Migration Code Appendix](./design.md#appendix-migration-code-examples) in design.md.

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

**Migration:** See Appendix A1 in design.md

---

### 🚧 `get_logged_in_url() -> str | None`

**QuiltOps Replacement:** NEW: `get_auth_status() -> Auth_Status`

**Callers:**

- [ ] `src/quilt_mcp/services/auth_metadata.py:56` (in `_get_catalog_host_from_config`)
- [ ] `src/quilt_mcp/services/auth_metadata.py:156` (in `auth_status`)
- [ ] `src/quilt_mcp/services/auth_metadata.py:168` (in `get_catalog_info`)

**Requires:** Implement `Auth_Status` dataclass and `get_auth_status()` method (design.md lines 172-178)

---

### 🚧 `get_config() -> dict | None`

**QuiltOps Replacement:** NEW: `get_catalog_config(catalog_url) -> Catalog_Config`

**Callers:**

- [ ] `src/quilt_mcp/services/auth_metadata.py:69` (in `_get_catalog_host_from_config`)
- [ ] `src/quilt_mcp/services/auth_metadata.py:161` (in `auth_status`)
- [ ] `src/quilt_mcp/services/auth_metadata.py:178` (in `configure_catalog`)

**Requires:** Implement `Catalog_Config` dataclass and `get_catalog_config()` method (design.md lines 181-196)

---

### 🚧 `get_catalog_config(catalog_url: str) -> dict | None`

**QuiltOps Replacement:** NEW: `get_catalog_config(catalog_url) -> Catalog_Config`

**Callers:**

- [ ] `src/quilt_mcp/services/auth_metadata.py:202` (in `get_catalog_info`)

**Requires:** Same as above - needs implementation

---

### 🚧 `set_config(catalog_url: str) -> None`

**QuiltOps Replacement:** NEW: `configure_catalog(catalog_url: str) -> None`

**Callers:**

- [ ] `src/quilt_mcp/services/auth_metadata.py:491` (in `configure_catalog`)

**Requires:** Implement `configure_catalog()` method (design.md lines 190-196)

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

**Requires:** Implement `execute_graphql_query()` method (design.md lines 502-518)

**Migration:** See Appendix A2 in design.md

---

### 🚧 `get_registry_url() -> str | None`

**QuiltOps Replacement:** NEW: `get_registry_url() -> Optional[str]`

**Callers:**

- [ ] `src/quilt_mcp/search/backends/elasticsearch.py:186` (in `_check_session`)
- [ ] `src/quilt_mcp/search/backends/elasticsearch.py:207` (in `health_check`)
- [ ] `src/quilt_mcp/search/backends/elasticsearch.py:229` (in `_get_available_buckets`)

**Requires:** Implement `get_registry_url()` method (design.md lines 538-544)

---

### 🚧 `create_botocore_session() -> Any`

**QuiltOps Replacement:** NEW: `get_boto3_client(service_name, region) -> Any`

**Callers:**

- [ ] `src/quilt_mcp/services/athena_service.py:90` (in `_create_sqlalchemy_engine`)
- [ ] `src/quilt_mcp/services/athena_service.py:190` (in `_create_glue_client`)
- [ ] `src/quilt_mcp/services/athena_service.py:204` (in `_create_s3_client`)
- [ ] `src/quilt_mcp/services/athena_service.py:495` (in `list_workgroups`)

**Requires:** Implement `get_boto3_client()` method (design.md lines 520-535)

**Migration:** See Appendix A3 in design.md

---

## Package Operations

### 🚧 `create_package_revision(...) -> Dict`

**QuiltOps Replacement:** NEW: `create_package_revision(...) -> Package_Creation_Result`

**Callers:**

- [ ] `src/quilt_mcp/tools/packages.py` (in `package_create`)

**Requires:** Implement `create_package_revision()` and `Package_Creation_Result` dataclass (design.md lines 241-250)

---

### ✅ `browse_package(name, registry, top_hash) -> Any`

**QuiltOps Replacement:** EXISTING: `browse_content(package_name, registry, path) -> List[Content_Info]`

**Callers:**

- [ ] `src/quilt_mcp/tools/packages.py` (in various browse methods)

**Migration:** See Appendix A4 in design.md

---

### 🚧 `list_packages(registry) -> Iterator[str]`

**QuiltOps Replacement:** NEW: `list_all_packages(registry) -> List[str]`

**Callers:**

- [ ] `src/quilt_mcp/tools/packages.py` (in `packages_list`)

**Requires:** Implement `list_all_packages()` method (design.md lines 262-266)

---

## Bucket Operations

### ❌ `create_bucket(bucket_uri) -> Any`

**QuiltOps Replacement:** NONE - Not a domain operation

**Callers:**

- [ ] `src/quilt_mcp/tools/stack_buckets.py` (if used)

**Migration Strategy:** Use `get_boto3_client('s3')` directly instead. Design doc (line 686) states
this is not a Quilt domain operation.

---

## Search Operations

### 🚧 `get_search_api() -> Any`

**QuiltOps Replacement:** NEW: `search_packages(query, registry)` and `search_objects(query, registry, filters)`

**Callers:**

- [ ] `src/quilt_mcp/search/backends/elasticsearch.py:449` (in `search`)
- [ ] `src/quilt_mcp/tools/packages.py` (if used for search)

**Requires:** Implement search methods (design.md lines 620-646)

---

## Admin Operations - Tabulator

### 🚧 `is_admin_available() -> bool`

**QuiltOps Replacement:** Try/catch on admin operations

**Callers:**

- [ ] `src/quilt_mcp/services/tabulator_service.py:19` (module-level check)
- [ ] `src/quilt_mcp/services/governance_service.py:25` (module-level check)

**Migration:** See Appendix A5 in design.md

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

**Requires:** Implement tabulator domain methods (design.md lines 422-456)

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

**Requires:** Implement user management methods (design.md lines 319-368)

---

## Admin Operations - Roles

### 🚧 `get_roles_admin() -> Any`

**QuiltOps Replacement:** NEW: Multiple domain methods:

- `list_roles(registry) -> List[Role_Info]`
- `get_role_policies(role_name, registry) -> List[Policy_Info]`

**Callers:**

- [ ] `src/quilt_mcp/services/governance_service.py:32` (module-level)
- [ ] `src/quilt_mcp/services/governance_service.py:893` (in `admin_roles_list`)

**Requires:** Implement role management methods (design.md lines 355-368)

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

**Requires:** Implement SSO config methods (see design.md Appendix)

---

## Admin Operations - Exceptions

### 🚧 `get_admin_exceptions() -> dict[str, type]`

**QuiltOps Replacement:** Use standard QuiltOps exceptions

**Callers:**

- [ ] `src/quilt_mcp/services/governance_service.py:38` (module-level)

**Migration Strategy:** Replace with QuiltOps exception hierarchy (design.md lines 697-721)

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

1. [ ] Implement `execute_graphql_query()` in QuiltOps interface
2. [ ] Implement `get_boto3_client()` in QuiltOps interface
3. [ ] Implement both in `Quilt3_Backend`

### Phase 3: Package Operations (Week 2)

1. [ ] Implement `create_package_revision()` in QuiltOps interface
2. [ ] Implement `list_all_packages()` in QuiltOps interface
3. [ ] Implement `get_package_versions()` in QuiltOps interface
4. [ ] Implement all in `Quilt3_Backend`

### Phase 4: Search Operations (Week 2-3)

1. [ ] Implement `search_objects()` in QuiltOps interface
2. [ ] Enhance `search_packages()` if needed
3. [ ] Implement in `Quilt3_Backend`

### Phase 5: Admin - Tabulator (Week 3)

1. [ ] Implement all tabulator domain methods in QuiltOps interface
2. [ ] Implement `Tabulator_Table` and `Column_Info` dataclasses
3. [ ] Implement all in `Quilt3_Backend`
4. [ ] Migrate `src/quilt_mcp/services/tabulator_service.py`

### Phase 6: Admin - Users (Week 3-4)

1. [ ] Implement all user management methods in QuiltOps interface
2. [ ] Implement `User_Info` dataclass
3. [ ] Implement all in `Quilt3_Backend`
4. [ ] Migrate user management in `src/quilt_mcp/services/governance_service.py`

### Phase 7: Admin - Roles & SSO (Week 4)

1. [ ] Implement role management methods in QuiltOps interface
2. [ ] Implement SSO methods in QuiltOps interface
3. [ ] Implement `Role_Info`, `Policy_Info`, `SSO_Config` dataclasses
4. [ ] Implement all in `Quilt3_Backend`
5. [ ] Migrate remaining governance in `src/quilt_mcp/services/governance_service.py`

### Phase 8: Migrate Callers (Week 4-5)

1. [ ] Migrate `src/quilt_mcp/services/auth_metadata.py`
2. [ ] Migrate `src/quilt_mcp/services/athena_service.py`
3. [ ] Migrate `src/quilt_mcp/search/backends/elasticsearch.py`
4. [ ] Migrate `src/quilt_mcp/tools/packages.py`
5. [ ] Migrate `src/quilt_mcp/tools/stack_buckets.py`

### Phase 9: Testing & Cleanup (Week 5)

1. [ ] Update all tests to use QuiltOps instead of QuiltService
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
