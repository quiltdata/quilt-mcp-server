# QuiltService → QuiltOps Migration Tasks (Part 2)

**Tasks 5-7: Admin Operations**

> **Navigation:**
> - [← Back to tasks.md](tasks.md) (Tasks 1-4)
> - [→ Continue to tasks-2.md](tasks-2.md) (Tasks 8-11)

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
- [ ] Test error handling for tabulator admin permission failures
- [ ] Add abstract tabulator methods to QuiltOps interface
- [ ] Write tests for tabulator methods Quilt3_Backend implementation
- [ ] Implement all tabulator methods in Quilt3_Backend using quilt3.admin

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

- [ ] Task 5: Run linting: `ruff check --fix src/quilt_mcp/ops/ src/quilt_mcp/domain/`
- [ ] Task 5: Run tests: `uv run pytest tests/unit/ops/ tests/unit/domain/ -v`
- [ ] Task 5: Verify all tests pass
- [ ] Task 5: Commit changes: `git add . && git commit -m "feat: implement tabulator admin methods"`

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
- [ ] Test error handling for user management permission failures and invalid inputs
- [ ] Add abstract user management methods to QuiltOps interface
- [ ] Write tests for user management methods Quilt3_Backend implementation
- [ ] Implement all user management methods in Quilt3_Backend using quilt3.admin

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

- [ ] Task 6: Run linting: `ruff check --fix src/quilt_mcp/ops/ src/quilt_mcp/domain/`
- [ ] Task 6: Run tests: `uv run pytest tests/unit/ops/ tests/unit/domain/ -v`
- [ ] Task 6: Verify all tests pass
- [ ] Task 6: Commit changes: `git add . && git commit -m "feat: implement user admin methods"`

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
- [ ] Test error handling for role operations
- [ ] Add abstract role methods to QuiltOps interface
- [ ] Write tests for role methods Quilt3_Backend implementation
- [ ] Implement role methods in Quilt3_Backend using quilt3.admin

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
- [ ] Test error handling for SSO operations
- [ ] Add abstract SSO methods to QuiltOps interface
- [ ] Write tests for SSO methods Quilt3_Backend implementation
- [ ] Implement SSO methods in Quilt3_Backend using quilt3.admin

**Callers to migrate:**

- `src/quilt_mcp/services/governance_service.py:950` (in `admin_sso_config_get`)
- `src/quilt_mcp/services/governance_service.py:1018` (in `admin_sso_config_set`)
- `src/quilt_mcp/services/governance_service.py:1066` (in `admin_sso_config_remove`)

### 7.5 Verification Checkpoint: Roles & SSO Operations

- [ ] Task 7: Run linting: `ruff check --fix src/quilt_mcp/ops/ src/quilt_mcp/domain/`
- [ ] Task 7: Run tests: `uv run pytest tests/unit/ops/ tests/unit/domain/ -v`
- [ ] Task 7: Verify all tests pass
- [ ] Task 7: Commit changes: `git add . && git commit -m "feat: implement role & SSO admin methods"`

---

**Continue to [tasks-2.md](tasks-2.md) for Service Migrations Part 1 (Tasks 8-11)**
