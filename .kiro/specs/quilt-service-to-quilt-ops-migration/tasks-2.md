# QuiltService → QuiltOps Migration Tasks (Part 3)

**Tasks 8-11: Service Migrations (Part 1)**

> **Navigation:**
> - [← Back to tasks-1.md](tasks-1.md) (Tasks 5-7)
> - [→ Continue to tasks-3.md](tasks-3.md) (Tasks 12-16)

---

## Task 8: Migrate auth_metadata.py Service

Migrate authentication and metadata service to use QuiltOps.

### 8.1 Update auth_metadata.py imports and initialization

- [ ] Replace QuiltService import with QuiltOps in auth_metadata.py
- [ ] Update auth_metadata.py service initialization to use QuiltOpsFactory
- [ ] Update auth_metadata.py type hints to use domain objects

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

### 8.4 Update auth_metadata.py error handling

- [ ] Replace QuiltService exceptions with QuiltOps exceptions in auth_metadata.py
- [ ] Update error messages in auth_metadata.py to reference QuiltOps
- [ ] Test auth_metadata.py error handling paths

### 8.5 Verification Checkpoint: auth_metadata.py Migration

- [ ] Task 8: Run linting: `ruff check --fix src/quilt_mcp/services/auth_metadata.py`
- [ ] Task 8: Run tests: `uv run pytest tests/unit/services/test_auth_metadata.py -v`
- [ ] Task 8: Run integration tests: `uv run pytest tests/integration/ -k auth -v`
- [ ] Task 8: Verify all tests pass
- [ ] Task 8: Commit changes: `git add . && git commit -m "feat: migrate auth_metadata.py to QuiltOps"`

---

## Task 9: Migrate athena_service.py Service

Migrate Athena service to use QuiltOps boto3 client access.

### 9.1 Update athena_service.py imports

- [ ] Replace QuiltService import with QuiltOps in athena_service.py
- [ ] Update athena_service.py service initialization to use QuiltOps instance
- [ ] Update athena_service.py type hints

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

### 9.3 Update athena_service.py error handling

- [ ] Replace QuiltService exceptions with QuiltOps exceptions in athena_service.py
- [ ] Test AWS client creation error paths in athena_service.py
- [ ] Verify region handling works correctly in athena_service.py

### 9.4 Verification Checkpoint: athena_service.py Migration

- [ ] Task 9: Run linting: `ruff check --fix src/quilt_mcp/services/athena_service.py`
- [ ] Task 9: Run tests: `uv run pytest tests/unit/services/test_athena_service.py -v`
- [ ] Task 9: Run integration tests: `uv run pytest tests/integration/ -k athena -v`
- [ ] Task 9: Verify all tests pass
- [ ] Task 9: Commit changes: `git add . && git commit -m "feat: migrate athena_service.py to QuiltOps"`

---

## Task 10: Migrate elasticsearch.py Search Backend

Migrate Elasticsearch search backend to use QuiltOps.

### 10.1 Update elasticsearch.py imports

- [ ] Replace QuiltService import with QuiltOps in elasticsearch.py
- [ ] Update elasticsearch.py backend initialization to use QuiltOps instance
- [ ] Update elasticsearch.py type hints

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

### 10.4 Update elasticsearch.py error handling

- [ ] Replace QuiltService exceptions with QuiltOps exceptions in elasticsearch.py
- [ ] Test search failure error paths in elasticsearch.py
- [ ] Verify authentication error handling in elasticsearch.py

### 10.5 Verification Checkpoint: elasticsearch.py Migration

- [ ] Task 10: Run linting: `ruff check --fix src/quilt_mcp/search/backends/elasticsearch.py`
- [ ] Task 10: Run tests: `uv run pytest tests/unit/search/ -v`
- [ ] Task 10: Run integration tests: `uv run pytest tests/integration/ -k search -v`
- [ ] Task 10: Verify all tests pass
- [ ] Task 10: Commit changes: `git add . && git commit -m "feat: migrate elasticsearch.py to QuiltOps"`

---

## Task 11: Migrate packages.py Tool

Migrate package management tool to use QuiltOps.

### 11.1 Update packages.py imports

- [ ] Replace QuiltService import with QuiltOps in packages.py
- [ ] Update packages.py tool functions to accept QuiltOps instance
- [ ] Update packages.py type hints to use domain objects

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

### 11.5 Update packages.py error handling

- [ ] Replace QuiltService exceptions with QuiltOps exceptions in packages.py
- [ ] Test all packages.py error paths
- [ ] Verify packages.py response formatting

### 11.6 Verification Checkpoint: packages.py Migration

- [ ] Task 11: Run linting: `ruff check --fix src/quilt_mcp/tools/packages.py`
- [ ] Task 11: Run tests: `uv run pytest tests/unit/tools/test_packages.py -v`
- [ ] Task 11: Run integration tests: `uv run pytest tests/integration/ -k package -v`
- [ ] Task 11: Verify all tests pass
- [ ] Task 11: Commit changes: `git add . && git commit -m "feat: migrate packages.py to QuiltOps"`

---

**Continue to [tasks-3.md](tasks-3.md) for Service Migrations Part 2 & Cleanup (Tasks 12-16)**
