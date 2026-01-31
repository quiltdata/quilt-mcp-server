# QuiltService → QuiltOps Migration Tasks

This task list guides the complete migration from QuiltService to QuiltOps abstraction,
implementing new domain methods and migrating all callers.

> **Note:** For code examples and migration patterns, see the
> [Migration Code Appendix](./design.md#appendix-migration-code-examples) in design.md.

**Task Files:**

- **[tasks.md](tasks.md)** (this file) - Tasks 1-4: Foundation & Core Operations
- **[tasks-1.md](tasks-1.md)** - Tasks 5-7: Admin Operations
- **[tasks-2.md](tasks-2.md)** - Tasks 8-11: Service Migrations (Part 1)
- **[tasks-3.md](tasks-3.md)** - Tasks 12-16: Service Migrations (Part 2) & Cleanup

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

- [x] Write tests for `get_registry_url()` in `tests/unit/ops/test_quilt_ops.py`
- [x] Add abstract method to QuiltOps interface
- [x] Write tests for Quilt3_Backend implementation
- [x] Implement in Quilt3_Backend using quilt3 config
- [x] Test fallback to default registry when not configured

**Reference:** design.md lines 538-544

### 1.6 Verification Checkpoint: Foundation Methods

- [x] Run linting: `ruff check --fix src/quilt_mcp/ops/ src/quilt_mcp/domain/`
- [x] Run tests: `uv run pytest tests/unit/ops/ tests/unit/domain/ -v`
- [x] Verify all tests pass
- [x] Commit changes: `git add . && git commit -m "feat: implement auth & config foundation methods"`

---

## Task 2: Implement AWS & GraphQL Methods (TDD)

Implement methods for GraphQL queries and AWS boto3 client access.

### 2.1 TDD: execute_graphql_query() method

- [x] Write tests for `execute_graphql_query()` in `tests/unit/ops/test_quilt_ops.py`
- [x] Test query execution with variables
- [x] Test error handling for invalid queries and auth failures
- [x] Add abstract method `execute_graphql_query()` to QuiltOps interface
- [x] Write tests for `execute_graphql_query()` Quilt3_Backend implementation
- [x] Implement `execute_graphql_query()` in Quilt3_Backend using quilt3 session

**Callers to migrate:**

- `src/quilt_mcp/services/quilt_service.py:95` (in `get_catalog_config`)
- `src/quilt_mcp/search/backends/elasticsearch.py:228` (in `_get_available_buckets`)

**Reference:** design.md lines 502-518
**Migration:** See Appendix A2 in design.md

### 2.2 TDD: get_boto3_client() method

- [x] Write tests for `get_boto3_client()` in `tests/unit/ops/test_quilt_ops.py`
- [x] Test client creation for different service types (s3, glue, athena)
- [x] Test region override and default region handling
- [x] Add abstract method `get_boto3_client()` to QuiltOps interface
- [x] Write tests for `get_boto3_client()` Quilt3_Backend implementation
- [x] Implement `get_boto3_client()` in Quilt3_Backend using quilt3's botocore session

**Callers to migrate:**

- `src/quilt_mcp/services/athena_service.py:90` (in `_create_sqlalchemy_engine`)
- `src/quilt_mcp/services/athena_service.py:190` (in `_create_glue_client`)
- `src/quilt_mcp/services/athena_service.py:204` (in `_create_s3_client`)
- `src/quilt_mcp/services/athena_service.py:495` (in `list_workgroups`)

**Reference:** design.md lines 520-535
**Migration:** See Appendix A3 in design.md

### 2.3 Verification Checkpoint: AWS & GraphQL Methods

- [x] Task 2: Run linting: `ruff check --fix src/quilt_mcp/ops/`
- [x] Task 2: Run tests: `uv run pytest tests/unit/ops/ -v`
- [x] Task 2: Verify all tests pass
- [x] Task 2: Commit changes: `git add . && git commit -m "feat: implement AWS & GraphQL methods"`

---

## Task 3: Implement Package Operations (TDD)

Implement package creation, listing, and version management methods.

### 3.1 TDD: Package_Creation_Result domain object

- [x] Write tests for Package_Creation_Result dataclass in `tests/unit/domain/test_package_creation.py`
- [x] Test required fields: package_name, top_hash, registry, catalog_url
- [x] Create `src/quilt_mcp/domain/package_creation.py` to make tests pass
- [x] Implement Package_Creation_Result with validation

**Reference:** design.md lines 241-250

### 3.2 TDD: create_package_revision() method

- [ ] Write tests for `create_package_revision()` in `tests/unit/ops/test_quilt_ops.py`
- [ ] Test package creation with files, metadata, and message
- [ ] Test error handling for invalid inputs and S3 errors
- [ ] Add abstract method `create_package_revision()` to QuiltOps interface
- [ ] Write tests for `create_package_revision()` Quilt3_Backend implementation
- [ ] Implement `create_package_revision()` in Quilt3_Backend using quilt3.Package

**Callers to migrate:**

- `src/quilt_mcp/tools/packages.py` (in `package_create`)

**Reference:** design.md lines 241-250

### 3.3 TDD: list_all_packages() method

- [ ] Write tests for `list_all_packages()` in `tests/unit/ops/test_quilt_ops.py`
- [ ] Test package listing with pagination handling
- [ ] Test filtering and sorting options
- [ ] Add abstract method `list_all_packages()` to QuiltOps interface
- [ ] Write tests for `list_all_packages()` Quilt3_Backend implementation
- [ ] Implement `list_all_packages()` in Quilt3_Backend using quilt3 API

**Callers to migrate:**

- `src/quilt_mcp/tools/packages.py` (in `packages_list`)

**Reference:** design.md lines 262-266

### 3.4 TDD: get_package_versions() method (if needed)

- [ ] Determine if `get_package_versions()` method is needed for version management
- [ ] Write tests for `get_package_versions()` if implementing
- [ ] Add `get_package_versions()` to QuiltOps interface if implementing
- [ ] Implement `get_package_versions()` in Quilt3_Backend if implementing

### 3.5 Verification Checkpoint: Package Operations

- [ ] Task 3: Run linting: `ruff check --fix src/quilt_mcp/ops/ src/quilt_mcp/domain/`
- [ ] Task 3: Run tests: `uv run pytest tests/unit/ops/ tests/unit/domain/ -v`
- [ ] Task 3: Verify all tests pass
- [ ] Task 3: Commit changes: `git add . && git commit -m "feat: implement package operation methods"`

---

## Task 4: Implement Search Operations (TDD)

Implement package and object search methods.

### 4.1 TDD: search_objects() method

- [ ] Write tests for `search_objects()` in `tests/unit/ops/test_quilt_ops.py`
- [ ] Test object search with filters and pagination
- [ ] Test error handling for search failures
- [ ] Add abstract method `search_objects()` to QuiltOps interface
- [ ] Write tests for `search_objects()` Quilt3_Backend implementation
- [ ] Implement `search_objects()` in Quilt3_Backend using quilt3 search API

**Reference:** design.md lines 620-646

### 4.2 Enhance search_packages() if needed

- [ ] Review current `search_packages()` implementation
- [ ] Add any missing features for elasticsearch backend
- [ ] Write additional tests for `search_packages()` enhanced functionality
- [ ] Update `search_packages()` implementation in Quilt3_Backend

**Callers to migrate:**

- `src/quilt_mcp/search/backends/elasticsearch.py:449` (in `search`)
- `src/quilt_mcp/tools/packages.py` (if used for search)

### 4.3 Verification Checkpoint: Search Operations

- [ ] Task 4: Run linting: `ruff check --fix src/quilt_mcp/ops/`
- [ ] Task 4: Run tests: `uv run pytest tests/unit/ops/ -v`
- [ ] Task 4: Verify all tests pass
- [ ] Task 4: Commit changes: `git add . && git commit -m "feat: implement search operation methods"`

---

**Continue to [tasks-1.md](tasks-1.md) for Admin Operations (Tasks 5-7)**
