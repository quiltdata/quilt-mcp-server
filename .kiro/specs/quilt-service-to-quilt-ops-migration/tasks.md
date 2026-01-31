# QuiltService → QuiltOps Migration Tasks

This task list guides the complete migration from QuiltService to QuiltOps abstraction,
implementing new domain methods and migrating all callers.

> **Note:** For code examples and migration patterns, see the
> [Migration Code Appendix](./design.md#appendix-migration-code-examples) in design.md.

---

## Task 1: Implement Foundation - Authentication & Configuration (TDD)

Create the foundation authentication and configuration methods using TDD approach.

### 1.1 TDD: Auth_Status domain object

- [x] Write tests for Auth_Status dataclass in `tests/unit/domain/test_auth_status.py`
- [x] Test required fields: is_authenticated, catalog_url, registry_url
- [x] Test optional fields and validation logic
- [x] Create `src/quilt_mcp/domain/auth_status.py` to make tests pass
- [x] Implement Auth_Status with proper validation

**Replaces:** `is_authenticated()`, `get_logged_in_url()`
**Reference:** design.md lines 172-178

### 1.2 TDD: get_auth_status() method

- [x] Write tests for `get_auth_status()` in `tests/unit/ops/test_quilt_ops.py`
- [x] Add abstract method to QuiltOps interface in `src/quilt_mcp/ops/quilt_ops.py`
- [x] Write tests for Quilt3_Backend implementation in `tests/unit/backends/test_quilt3_backend.py`
- [x] Implement in Quilt3_Backend using quilt3 session inspection
- [x] Test extraction of catalog_url and registry_url from quilt3 config

**Migration Note:** See Appendix A1 in design.md

### 1.3 TDD: Catalog_Config domain object

- [x] Write tests for Catalog_Config dataclass in `tests/unit/domain/test_catalog_config.py`
- [x] Test required fields: catalog_url, s3_buckets, default_bucket
- [x] Test configuration validation and error messages
- [x] Create `src/quilt_mcp/domain/catalog_config.py` to make tests pass
- [x] Implement Catalog_Config with proper validation

**Replaces:** `get_config()`, `get_catalog_config()`
**Reference:** design.md lines 181-196

### 1.4 TDD: get_catalog_config() and configure_catalog() methods

- [x] Write tests for `get_catalog_config()` in `tests/unit/ops/test_quilt_ops.py`
- [x] Write tests for `configure_catalog()` in `tests/unit/ops/test_quilt_ops.py`
- [x] Add abstract methods to QuiltOps interface
- [x] Write tests for Quilt3_Backend implementation
- [x] Implement both methods in Quilt3_Backend
- [x] Test GraphQL query execution for catalog config retrieval

**Reference:** design.md lines 181-196

### 1.5 TDD: get_registry_url() method

- [-] Write tests for `get_registry_url()` in `tests/unit/ops/test_quilt_ops.py`
- [ ] Add abstract method to QuiltOps interface
- [ ] Write tests for Quilt3_Backend implementation
- [ ] Implement in Quilt3_Backend using quilt3 config
- [ ] Test fallback to default registry when not configured

**Reference:** design.md lines 538-544

### 1.6 Verification Checkpoint: Foundation Methods

- [ ] Run linting: `ruff check --fix src/quilt_mcp/ops/ src/quilt_mcp/domain/`
- [ ] Run tests: `uv run pytest tests/unit/ops/ tests/unit/domain/ -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: implement auth & config foundation methods"`

---

## Task 2: Implement AWS & GraphQL Methods (TDD)

Implement methods for GraphQL queries and AWS boto3 client access.

### 2.1 TDD: execute_graphql_query() method

- [ ] Write tests for `execute_graphql_query()` in `tests/unit/ops/test_quilt_ops.py`
- [ ] Test query execution with variables
- [ ] Test error handling for invalid queries and auth failures
- [ ] Add abstract method to QuiltOps interface
- [ ] Write tests for Quilt3_Backend implementation
- [ ] Implement in Quilt3_Backend using quilt3 session

**Callers to migrate:**

- `src/quilt_mcp/services/quilt_service.py:95` (in `get_catalog_config`)
- `src/quilt_mcp/search/backends/elasticsearch.py:228` (in `_get_available_buckets`)

**Reference:** design.md lines 502-518
**Migration:** See Appendix A2 in design.md

### 2.2 TDD: get_boto3_client() method

- [ ] Write tests for `get_boto3_client()` in `tests/unit/ops/test_quilt_ops.py`
- [ ] Test client creation for different service types (s3, glue, athena)
- [ ] Test region override and default region handling
- [ ] Add abstract method to QuiltOps interface
- [ ] Write tests for Quilt3_Backend implementation
- [ ] Implement in Quilt3_Backend using quilt3's botocore session

**Callers to migrate:**

- `src/quilt_mcp/services/athena_service.py:90` (in `_create_sqlalchemy_engine`)
- `src/quilt_mcp/services/athena_service.py:190` (in `_create_glue_client`)
- `src/quilt_mcp/services/athena_service.py:204` (in `_create_s3_client`)
- `src/quilt_mcp/services/athena_service.py:495` (in `list_workgroups`)

**Reference:** design.md lines 520-535
**Migration:** See Appendix A3 in design.md

### 2.3 Verification Checkpoint: AWS & GraphQL Methods

- [ ] Run linting: `ruff check --fix src/quilt_mcp/ops/`
- [ ] Run tests: `uv run pytest tests/unit/ops/ -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: implement AWS & GraphQL methods"`

---

## Task 3: Implement Package Operations (TDD)

Implement package creation, listing, and version management methods.

### 3.1 TDD: Package_Creation_Result domain object

- [ ] Write tests for Package_Creation_Result dataclass in `tests/unit/domain/test_package_creation.py`
- [ ] Test required fields: package_name, top_hash, registry, catalog_url
- [ ] Create `src/quilt_mcp/domain/package_creation.py` to make tests pass
- [ ] Implement Package_Creation_Result with validation

**Reference:** design.md lines 241-250

### 3.2 TDD: create_package_revision() method

- [ ] Write tests for `create_package_revision()` in `tests/unit/ops/test_quilt_ops.py`
- [ ] Test package creation with files, metadata, and message
- [ ] Test error handling for invalid inputs and S3 errors
- [ ] Add abstract method to QuiltOps interface
- [ ] Write tests for Quilt3_Backend implementation
- [ ] Implement in Quilt3_Backend using quilt3.Package

**Callers to migrate:**

- `src/quilt_mcp/tools/packages.py` (in `package_create`)

**Reference:** design.md lines 241-250

### 3.3 TDD: list_all_packages() method

- [ ] Write tests for `list_all_packages()` in `tests/unit/ops/test_quilt_ops.py`
- [ ] Test package listing with pagination handling
- [ ] Test filtering and sorting options
- [ ] Add abstract method to QuiltOps interface
- [ ] Write tests for Quilt3_Backend implementation
- [ ] Implement in Quilt3_Backend using quilt3 API

**Callers to migrate:**

- `src/quilt_mcp/tools/packages.py` (in `packages_list`)

**Reference:** design.md lines 262-266

### 3.4 TDD: get_package_versions() method (if needed)

- [ ] Determine if this method is needed for version management
- [ ] Write tests if implementing
- [ ] Add to QuiltOps interface if implementing
- [ ] Implement in Quilt3_Backend if implementing

### 3.5 Verification Checkpoint: Package Operations

- [ ] Run linting: `ruff check --fix src/quilt_mcp/ops/ src/quilt_mcp/domain/`
- [ ] Run tests: `uv run pytest tests/unit/ops/ tests/unit/domain/ -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: implement package operation methods"`

---

## Task 4: Implement Search Operations (TDD)

Implement package and object search methods.

### 4.1 TDD: search_objects() method

- [ ] Write tests for `search_objects()` in `tests/unit/ops/test_quilt_ops.py`
- [ ] Test object search with filters and pagination
- [ ] Test error handling for search failures
- [ ] Add abstract method to QuiltOps interface
- [ ] Write tests for Quilt3_Backend implementation
- [ ] Implement in Quilt3_Backend using quilt3 search API

**Reference:** design.md lines 620-646

### 4.2 Enhance search_packages() if needed

- [ ] Review current `search_packages()` implementation
- [ ] Add any missing features for elasticsearch backend
- [ ] Write additional tests for enhanced functionality
- [ ] Update implementation in Quilt3_Backend

**Callers to migrate:**

- `src/quilt_mcp/search/backends/elasticsearch.py:449` (in `search`)
- `src/quilt_mcp/tools/packages.py` (if used for search)

### 4.3 Verification Checkpoint: Search Operations

- [ ] Run linting: `ruff check --fix src/quilt_mcp/ops/`
- [ ] Run tests: `uv run pytest tests/unit/ops/ -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: implement search operation methods"`

---

## Task 5: Implement Admin Operations - Tabulator (TDD)

Implement tabulator table management methods.

### 5.1 TDD: Tabulator domain objects

- [ ] Write tests for Tabulator_Table dataclass in `tests/unit/domain/test_tabulator.py`
- [ ] Write tests for Column_Info dataclass
- [ ] Test field validation and constraints
- [ ] Create `src/quilt_mcp/domain/tabulator.py` to make tests pass
- [ ] Implement Tabulator_Table and Column_Info with validation

**Reference:** design.md lines 422-456

### 5.2 TDD: Tabulator management methods

- [ ] Write tests for all tabulator methods in `tests/unit/ops/test_quilt_ops.py`:
  - `list_tabulator_tables(catalog_name)`
  - `create_tabulator_table(...)`
  - `delete_tabulator_table(...)`
  - `get_tabulator_table_info(...)`
- [ ] Test error handling for admin permission failures
- [ ] Add abstract methods to QuiltOps interface
- [ ] Write tests for Quilt3_Backend implementation
- [ ] Implement all methods in Quilt3_Backend using quilt3.admin

**Callers to migrate:**

- `src/quilt_mcp/services/tabulator_service.py:141` (in `list_tables`)
- `src/quilt_mcp/services/tabulator_service.py:210` (in `create_table`)
- `src/quilt_mcp/services/tabulator_service.py:253` (in `delete_table`)
- `src/quilt_mcp/services/tabulator_service.py:292` (in `rename_table`)
- `src/quilt_mcp/services/tabulator_service.py:329` (in `get_open_query_status`)
- `src/quilt_mcp/services/tabulator_service.py:348` (in `set_open_query`)
- `src/quilt_mcp/services/governance_service.py:1102` (in `admin_tabulator_open_query_get`)
- `src/quilt_mcp/services/governance_service.py:1152` (in `admin_tabulator_open_query_set`)

**Migration:** See Appendix A5 in design.md for is_admin_available() pattern

### 5.3 Verification Checkpoint: Tabulator Operations

- [ ] Run linting: `ruff check --fix src/quilt_mcp/ops/ src/quilt_mcp/domain/`
- [ ] Run tests: `uv run pytest tests/unit/ops/ tests/unit/domain/ -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: implement tabulator admin methods"`

---

## Task 6: Implement Admin Operations - Users (TDD)

Implement user management methods.

### 6.1 TDD: User_Info domain object

- [ ] Write tests for User_Info dataclass in `tests/unit/domain/test_user_info.py`
- [ ] Test required fields: username, email, role, is_active
- [ ] Test validation for email format and role values
- [ ] Create `src/quilt_mcp/domain/user_info.py` to make tests pass
- [ ] Implement User_Info with validation

**Reference:** design.md lines 319-368

### 6.2 TDD: User management methods

- [ ] Write tests for all user methods in `tests/unit/ops/test_quilt_ops.py`:
  - `list_catalog_users(registry)`
  - `get_user(username, registry)`
  - `create_user(username, email, role, registry)`
  - `delete_user(username, registry)`
  - `set_user_role(username, role, registry)`
- [ ] Test error handling for permission failures and invalid inputs
- [ ] Add abstract methods to QuiltOps interface
- [ ] Write tests for Quilt3_Backend implementation
- [ ] Implement all methods in Quilt3_Backend using quilt3.admin

**Callers to migrate:**

- `src/quilt_mcp/services/governance_service.py:115` (in `admin_users_list`)
- `src/quilt_mcp/services/governance_service.py:191` (in `admin_user_get`)
- `src/quilt_mcp/services/governance_service.py:317` (in `admin_user_create`)
- `src/quilt_mcp/services/governance_service.py:379` (in `admin_user_delete`)
- `src/quilt_mcp/services/governance_service.py:443` (in `admin_user_set_email`)
- `src/quilt_mcp/services/governance_service.py:505` (in `admin_user_set_admin`)
- `src/quilt_mcp/services/governance_service.py:567` (in `admin_user_set_active`)
- `src/quilt_mcp/services/governance_service.py:620` (in `admin_user_reset_password`)
- `src/quilt_mcp/services/governance_service.py:700` (in `admin_user_set_role`)
- `src/quilt_mcp/services/governance_service.py:768` (in `admin_user_add_roles`)
- `src/quilt_mcp/services/governance_service.py:845` (in `admin_user_remove_roles`)

### 6.3 Verification Checkpoint: User Operations

- [ ] Run linting: `ruff check --fix src/quilt_mcp/ops/ src/quilt_mcp/domain/`
- [ ] Run tests: `uv run pytest tests/unit/ops/ tests/unit/domain/ -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: implement user admin methods"`

---

## Task 7: Implement Admin Operations - Roles & SSO (TDD)

Implement role and SSO configuration management methods.

### 7.1 TDD: Role domain objects

- [ ] Write tests for Role_Info dataclass in `tests/unit/domain/test_role_info.py`
- [ ] Write tests for Policy_Info dataclass
- [ ] Test validation logic
- [ ] Create `src/quilt_mcp/domain/role_info.py` to make tests pass
- [ ] Implement Role_Info and Policy_Info with validation

**Reference:** design.md lines 355-368

### 7.2 TDD: Role management methods

- [ ] Write tests for role methods in `tests/unit/ops/test_quilt_ops.py`:
  - `list_roles(registry)`
  - `get_role_policies(role_name, registry)`
- [ ] Test error handling
- [ ] Add abstract methods to QuiltOps interface
- [ ] Write tests for Quilt3_Backend implementation
- [ ] Implement in Quilt3_Backend using quilt3.admin

**Callers to migrate:**

- `src/quilt_mcp/services/governance_service.py:893` (in `admin_roles_list`)

### 7.3 TDD: SSO_Config domain object

- [ ] Write tests for SSO_Config dataclass in `tests/unit/domain/test_sso_config.py`
- [ ] Test configuration validation
- [ ] Create `src/quilt_mcp/domain/sso_config.py` to make tests pass
- [ ] Implement SSO_Config with validation

### 7.4 TDD: SSO configuration methods

- [ ] Write tests for SSO methods in `tests/unit/ops/test_quilt_ops.py`:
  - `get_sso_config(registry)`
  - `set_sso_config(config, registry)`
  - `delete_sso_config(registry)`
- [ ] Test error handling
- [ ] Add abstract methods to QuiltOps interface
- [ ] Write tests for Quilt3_Backend implementation
- [ ] Implement in Quilt3_Backend using quilt3.admin

**Callers to migrate:**

- `src/quilt_mcp/services/governance_service.py:950` (in `admin_sso_config_get`)
- `src/quilt_mcp/services/governance_service.py:1018` (in `admin_sso_config_set`)
- `src/quilt_mcp/services/governance_service.py:1066` (in `admin_sso_config_remove`)

### 7.5 Verification Checkpoint: Roles & SSO Operations

- [ ] Run linting: `ruff check --fix src/quilt_mcp/ops/ src/quilt_mcp/domain/`
- [ ] Run tests: `uv run pytest tests/unit/ops/ tests/unit/domain/ -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: implement role & SSO admin methods"`

---

## Task 8: Migrate auth_metadata.py Service

Migrate authentication and metadata service to use QuiltOps.

### 8.1 Update auth_metadata.py imports and initialization

- [ ] Replace QuiltService import with QuiltOps
- [ ] Update service initialization to use QuiltOpsFactory
- [ ] Update type hints to use domain objects

**File:** `src/quilt_mcp/services/auth_metadata.py`

### 8.2 Migrate authentication methods

- [ ] Migrate `_get_catalog_info()` at line 47:
  - Replace `is_authenticated()` with `get_auth_status()`
- [ ] Migrate `_get_catalog_host_from_config()` at lines 56, 69:
  - Replace `get_logged_in_url()` with `get_auth_status()`
  - Replace `get_config()` with `get_catalog_config()`
- [ ] Migrate `auth_status()` at lines 156, 161:
  - Replace `get_logged_in_url()` with `get_auth_status()`
  - Replace `get_config()` with `get_catalog_config()`

**Migration:** See Appendix A1 in design.md

### 8.3 Migrate configuration methods

- [ ] Migrate `get_catalog_info()` at line 168:
  - Replace `get_logged_in_url()` with `get_auth_status()`
- [ ] Migrate `get_catalog_info()` at line 202:
  - Replace `get_catalog_config()` with new QuiltOps method
- [ ] Migrate `configure_catalog()` at line 178:
  - Replace `get_config()` with `get_catalog_config()`
- [ ] Migrate `configure_catalog()` at line 491:
  - Replace `set_config()` with `configure_catalog()`

### 8.4 Update error handling

- [ ] Replace QuiltService exceptions with QuiltOps exceptions
- [ ] Update error messages to reference QuiltOps
- [ ] Test error handling paths

### 8.5 Verification Checkpoint: auth_metadata.py Migration

- [ ] Run linting: `ruff check --fix src/quilt_mcp/services/auth_metadata.py`
- [ ] Run tests: `uv run pytest tests/unit/services/test_auth_metadata.py -v`
- [ ] Run integration tests: `uv run pytest tests/integration/ -k auth -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: migrate auth_metadata.py to QuiltOps"`

---

## Task 9: Migrate athena_service.py Service

Migrate Athena service to use QuiltOps boto3 client access.

### 9.1 Update athena_service.py imports

- [ ] Replace QuiltService import with QuiltOps
- [ ] Update service initialization to use QuiltOps instance
- [ ] Update type hints

**File:** `src/quilt_mcp/services/athena_service.py`

### 9.2 Migrate boto3 client creation

- [ ] Migrate `_create_sqlalchemy_engine()` at line 90:
  - Replace `create_botocore_session()` with `get_boto3_client()`
- [ ] Migrate `_create_glue_client()` at line 190:
  - Replace `create_botocore_session()` with `get_boto3_client('glue')`
- [ ] Migrate `_create_s3_client()` at line 204:
  - Replace `create_botocore_session()` with `get_boto3_client('s3')`
- [ ] Migrate `list_workgroups()` at line 495:
  - Replace `create_botocore_session()` with `get_boto3_client('athena')`

**Migration:** See Appendix A3 in design.md

### 9.3 Update error handling

- [ ] Replace QuiltService exceptions with QuiltOps exceptions
- [ ] Test AWS client creation error paths
- [ ] Verify region handling works correctly

### 9.4 Verification Checkpoint: athena_service.py Migration

- [ ] Run linting: `ruff check --fix src/quilt_mcp/services/athena_service.py`
- [ ] Run tests: `uv run pytest tests/unit/services/test_athena_service.py -v`
- [ ] Run integration tests: `uv run pytest tests/integration/ -k athena -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: migrate athena_service.py to QuiltOps"`

---

## Task 10: Migrate elasticsearch.py Search Backend

Migrate Elasticsearch search backend to use QuiltOps.

### 10.1 Update elasticsearch.py imports

- [ ] Replace QuiltService import with QuiltOps
- [ ] Update backend initialization to use QuiltOps instance
- [ ] Update type hints

**File:** `src/quilt_mcp/search/backends/elasticsearch.py`

### 10.2 Migrate session and registry methods

- [ ] Migrate `_check_session()` at line 186:
  - Replace `get_registry_url()` with QuiltOps method
- [ ] Migrate `health_check()` at line 207:
  - Replace `get_registry_url()` with QuiltOps method
- [ ] Migrate `_get_available_buckets()` at lines 228-229:
  - Replace `get_session()` with `execute_graphql_query()`
  - Replace `get_registry_url()` with QuiltOps method

**Migration:** See Appendix A2 in design.md for GraphQL patterns

### 10.3 Migrate search methods

- [ ] Migrate `search()` at line 449:
  - Replace `get_search_api()` with `search_packages()` or `search_objects()`
- [ ] Update search result transformation to use domain objects

### 10.4 Update error handling

- [ ] Replace QuiltService exceptions with QuiltOps exceptions
- [ ] Test search failure error paths
- [ ] Verify authentication error handling

### 10.5 Verification Checkpoint: elasticsearch.py Migration

- [ ] Run linting: `ruff check --fix src/quilt_mcp/search/backends/elasticsearch.py`
- [ ] Run tests: `uv run pytest tests/unit/search/ -v`
- [ ] Run integration tests: `uv run pytest tests/integration/ -k search -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: migrate elasticsearch.py to QuiltOps"`

---

## Task 11: Migrate packages.py Tool

Migrate package management tool to use QuiltOps.

### 11.1 Update packages.py imports

- [ ] Replace QuiltService import with QuiltOps
- [ ] Update tool functions to accept QuiltOps instance
- [ ] Update type hints to use domain objects

**File:** `src/quilt_mcp/tools/packages.py`

### 11.2 Migrate package listing

- [ ] Migrate `packages_list()`:
  - Replace `list_packages()` with `list_all_packages()`
- [ ] Update response formatting to use domain objects

### 11.3 Migrate package browsing

- [ ] Migrate `package_browse()`:
  - Replace `browse_package()` with `browse_content()`
- [ ] Migrate `package_diff()`:
  - Use `browse_content()` for both packages
- [ ] Update response formatting to use Content_Info

**Migration:** See Appendix A4 in design.md

### 11.4 Migrate package creation

- [ ] Migrate `package_create()`:
  - Replace `create_package_revision()` with QuiltOps method
- [ ] Update response to use Package_Creation_Result
- [ ] Test error handling for creation failures

### 11.5 Update error handling

- [ ] Replace QuiltService exceptions with QuiltOps exceptions
- [ ] Test all error paths
- [ ] Verify response formatting

### 11.6 Verification Checkpoint: packages.py Migration

- [ ] Run linting: `ruff check --fix src/quilt_mcp/tools/packages.py`
- [ ] Run tests: `uv run pytest tests/unit/tools/test_packages.py -v`
- [ ] Run integration tests: `uv run pytest tests/integration/ -k package -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: migrate packages.py to QuiltOps"`

---

## Task 12: Migrate tabulator_service.py Service

Migrate tabulator service to use QuiltOps admin methods.

### 12.1 Update tabulator_service.py imports

- [ ] Replace QuiltService import with QuiltOps
- [ ] Remove `is_admin_available()` checks (use try/catch instead)
- [ ] Update type hints to use domain objects

**File:** `src/quilt_mcp/services/tabulator_service.py`

**Migration:** See Appendix A5 in design.md for is_admin_available() pattern

### 12.2 Migrate table management methods

- [ ] Migrate `list_tables()` at line 141:
  - Replace `get_tabulator_admin()` with `list_tabulator_tables()`
- [ ] Migrate `create_table()` at line 210:
  - Replace `get_tabulator_admin()` with `create_tabulator_table()`
- [ ] Migrate `delete_table()` at line 253:
  - Replace `get_tabulator_admin()` with `delete_tabulator_table()`
- [ ] Migrate `rename_table()` at line 292:
  - Use appropriate QuiltOps methods

### 12.3 Migrate query status methods

- [ ] Migrate `get_open_query_status()` at line 329:
  - Replace `get_tabulator_admin()` with QuiltOps method
- [ ] Migrate `set_open_query()` at line 348:
  - Replace `get_tabulator_admin()` with QuiltOps method

### 12.4 Update error handling

- [ ] Replace admin availability checks with try/catch
- [ ] Use QuiltOps exceptions for error handling
- [ ] Update error messages

### 12.5 Verification Checkpoint: tabulator_service.py Migration

- [ ] Run linting: `ruff check --fix src/quilt_mcp/services/tabulator_service.py`
- [ ] Run tests: `uv run pytest tests/unit/services/test_tabulator_service.py -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: migrate tabulator_service.py to QuiltOps"`

---

## Task 13: Migrate governance_service.py Service

Migrate governance service to use QuiltOps admin methods.

### 13.1 Update governance_service.py imports

- [ ] Replace QuiltService import with QuiltOps
- [ ] Remove module-level admin checks (lines 25, 31-34)
- [ ] Remove `get_admin_exceptions()` usage (line 38)
- [ ] Update type hints to use domain objects

**File:** `src/quilt_mcp/services/governance_service.py`

### 13.2 Migrate user management methods

- [ ] Migrate `admin_users_list()` at line 115:
  - Replace `get_users_admin()` with `list_catalog_users()`
- [ ] Migrate `admin_user_get()` at line 191:
  - Replace `get_users_admin()` with `get_user()`
- [ ] Migrate `admin_user_create()` at line 317:
  - Replace `get_users_admin()` with `create_user()`
- [ ] Migrate `admin_user_delete()` at line 379:
  - Replace `get_users_admin()` with `delete_user()`
- [ ] Migrate remaining user methods at lines 443, 505, 567, 620, 700, 768, 845:
  - Replace `get_users_admin()` with appropriate QuiltOps methods

### 13.3 Migrate role management methods

- [ ] Migrate `admin_roles_list()` at line 893:
  - Replace `get_roles_admin()` with `list_roles()`
- [ ] Add role policy methods if needed

### 13.4 Migrate SSO configuration methods

- [ ] Migrate `admin_sso_config_get()` at line 950:
  - Replace `get_sso_config_admin()` with `get_sso_config()`
- [ ] Migrate `admin_sso_config_set()` at line 1018:
  - Replace `get_sso_config_admin()` with `set_sso_config()`
- [ ] Migrate `admin_sso_config_remove()` at line 1066:
  - Replace `get_sso_config_admin()` with `delete_sso_config()`

### 13.5 Migrate tabulator admin methods

- [ ] Migrate `admin_tabulator_open_query_get()` at line 1102:
  - Replace `get_tabulator_admin()` with QuiltOps method
- [ ] Migrate `admin_tabulator_open_query_set()` at line 1152:
  - Replace `get_tabulator_admin()` with QuiltOps method

### 13.6 Update error handling

- [ ] Replace admin exceptions with QuiltOps exceptions
- [ ] Remove admin availability checks (use try/catch)
- [ ] Update error messages for consistency

### 13.7 Verification Checkpoint: governance_service.py Migration

- [ ] Run linting: `ruff check --fix src/quilt_mcp/services/governance_service.py`
- [ ] Run tests: `uv run pytest tests/unit/services/test_governance_service.py -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: migrate governance_service.py to QuiltOps"`

---

## Task 14: Migrate stack_buckets.py Tool

Migrate stack buckets tool to use QuiltOps.

### 14.1 Update stack_buckets.py

- [ ] Review usage of `create_bucket()` (if any)
- [ ] Replace with `get_boto3_client('s3')` direct usage
- [ ] Update authentication checks to use QuiltOpsFactory
- [ ] Update error handling

**File:** `src/quilt_mcp/tools/stack_buckets.py`

**Note:** `create_bucket()` is not a Quilt domain operation (design.md line 686)

### 14.2 Verification Checkpoint: stack_buckets.py Migration

- [ ] Run linting: `ruff check --fix src/quilt_mcp/tools/stack_buckets.py`
- [ ] Run tests: `uv run pytest tests/unit/tools/test_stack_buckets.py -v`
- [ ] Verify all tests pass
- [ ] Commit changes: `git add . && git commit -m "feat: migrate stack_buckets.py to QuiltOps"`

---

## Task 15: Update All Tests to Use QuiltOps

Migrate all remaining tests to use QuiltOps abstraction.

### 15.1 Audit test files

- [ ] Find all tests using QuiltService: `grep -r "QuiltService" tests/ --include="*.py" | grep -v "__pycache__"`
- [ ] Find all tests using quilt_service: `grep -r "quilt_service\." tests/ --include="*.py" | grep -v "__pycache__"`
- [ ] Create list of test files to update

### 15.2 Update unit tests

- [ ] Update test fixtures to create QuiltOps instances via factory
- [ ] Update mocks to use QuiltOps interface
- [ ] Update assertions to work with domain objects
- [ ] Remove direct QuiltService imports

### 15.3 Update integration tests

- [ ] Update integration test setup to use QuiltOpsFactory
- [ ] Update test assertions for domain objects
- [ ] Test complete workflows with QuiltOps
- [ ] Verify error handling works correctly

### 15.4 Verification Checkpoint: Test Migration

- [ ] Run linting: `ruff check tests/`
- [ ] Run all unit tests: `uv run pytest tests/unit/ -v`
- [ ] Run all integration tests: `uv run pytest tests/integration/ -v`
- [ ] Verify no QuiltService references remain: `grep -r "QuiltService" tests/ --include="*.py"`
- [ ] Commit changes: `git add . && git commit -m "feat: migrate all tests to use QuiltOps"`

---

## Task 16: Remove QuiltService and Final Cleanup

Remove the legacy QuiltService class and perform final cleanup.

### 16.1 Verify no QuiltService references remain

- [ ] Check source code: `grep -r "QuiltService" src/ --include="*.py" | grep -v "__pycache__"`
- [ ] Check for quilt_service usage: `grep -r "quilt_service\." src/ --include="*.py" | grep -v "__pycache__"`
- [ ] Check for admin module accesses: `grep -r "get_.*_admin\(\)" src/ --include="*.py" | grep -v "__pycache__"`
- [ ] Check imports: `grep -r "from.*quilt_service import" src/ --include="*.py" | grep -v "__pycache__"`
- [ ] Document any remaining references that need migration

### 16.2 Delete QuiltService

- [ ] Delete `src/quilt_mcp/services/quilt_service.py`
- [ ] Update `src/quilt_mcp/services/__init__.py` to remove QuiltService export
- [ ] Remove QuiltService from any service registration/initialization
- [ ] Remove obsolete test files for QuiltService

### 16.3 Update documentation

- [ ] Update architecture documentation to reflect QuiltOps
- [ ] Update API documentation to use QuiltOps
- [ ] Update developer guides and examples
- [ ] Update README if necessary

### 16.4 Final verification

- [ ] Run full linting: `ruff check --fix src/ tests/`
- [ ] Run complete test suite: `uv run pytest -v`
- [ ] Run integration tests: `uv run pytest tests/integration/ -v`
- [ ] Verify test coverage: `uv run pytest --cov=src/quilt_mcp --cov-report=html`
- [ ] Manual testing of key workflows

### 16.5 Final Checkpoint: Migration Complete

- [ ] Commit final changes: `git add . && git commit -m "feat: remove QuiltService, migration complete"`
- [ ] Create migration summary: Document what was changed, any issues encountered, lessons learned
- [ ] Tag release: `git tag -a v2.0.0-quilt-ops -m "Complete QuiltService to QuiltOps migration"`

---

## Acceptance Criteria

### Migration Complete When

- [ ] All QuiltService methods have QuiltOps equivalents implemented
- [ ] All domain objects created and validated (Auth_Status, Catalog_Config, User_Info, etc.)
- [ ] All callers migrated to use QuiltOps instead of QuiltService:
  - [ ] `src/quilt_mcp/services/auth_metadata.py` (8 locations)
  - [ ] `src/quilt_mcp/services/athena_service.py` (4 locations)
  - [ ] `src/quilt_mcp/search/backends/elasticsearch.py` (4 locations)
  - [ ] `src/quilt_mcp/tools/packages.py` (multiple locations)
  - [ ] `src/quilt_mcp/services/tabulator_service.py` (6 locations)
  - [ ] `src/quilt_mcp/services/governance_service.py` (20+ locations)
  - [ ] `src/quilt_mcp/tools/stack_buckets.py` (if applicable)
- [ ] All tests pass with QuiltOps
- [ ] No references to QuiltService remain in codebase
- [ ] `src/quilt_mcp/services/quilt_service.py` deleted
- [ ] Documentation updated to reflect new architecture
- [ ] Test coverage maintained or improved
- [ ] All verification commands pass (see below)

### Verification Commands

```bash
# Verify no QuiltService references remain
grep -r "QuiltService" src/ --include="*.py" | grep -v "__pycache__"
# Expected: No results

# Verify no quilt_service references remain
grep -r "quilt_service\." src/ --include="*.py" | grep -v "__pycache__"
# Expected: No results

# Verify no admin module accesses remain
grep -r "get_.*_admin\(\)" src/ --include="*.py" | grep -v "__pycache__"
# Expected: No results

# Verify no QuiltService imports remain
grep -r "from.*quilt_service import" src/ --include="*.py" | grep -v "__pycache__"
# Expected: No results

# Verify QuiltService file deleted
test ! -f src/quilt_mcp/services/quilt_service.py
# Expected: Exit code 0 (file does not exist)

# Run full test suite
uv run pytest -v
# Expected: All tests pass

# Run with coverage
uv run pytest --cov=src/quilt_mcp --cov-report=term-missing
# Expected: Coverage maintained or improved
```

---

## Notes

- Each task follows TDD principles: write tests first, then implement
- Reference the [Migration Code Appendix](./design.md#appendix-migration-code-examples) in design.md for specific patterns
- Use domain objects consistently throughout the migration
- Replace exception handling with QuiltOps exception hierarchy
- Remove admin availability checks in favor of try/catch patterns
- Commit frequently at verification checkpoints
- Run tests after each major change to catch regressions early
