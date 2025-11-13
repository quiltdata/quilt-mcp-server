# Test Coverage Analysis - Tool Tests vs Resource Tests

**Analysis Date**: 2025-10-20
**Purpose**: Compare old tool tests with new resource tests to identify gaps before deletion

---

## Summary

| Domain | Old Tool Tests | Resource Tests | Coverage Status | Action |
|--------|---------------|----------------|-----------------|---------|
| Workflow | test_workflow_orchestration.py | test_workflow_resources.py | ⚠️ Partial | Port missing tests |
| Metadata | test_metadata_examples.py | test_metadata_resources.py | ⚠️ Partial | Port missing tests |
| Governance | test_governance.py | test_admin_resources.py | ⚠️ Partial | Port missing tests |
| Tabulator | test_tabulator.py | test_tabulator_resources.py | ⚠️ Partial | Port missing tests |

---

## Detailed Analysis

### 1. Workflow Tests

#### Old Tool Tests (`test_workflow_orchestration.py`)

**Active Tests** (DO NOT DELETE - These test service layer directly):
- ✅ `test_workflow_create_rejects_blank_identifier()` - Tests input validation
- ✅ `test_workflow_progression_updates_status_and_next_steps()` - Tests workflow lifecycle
- ✅ `test_workflow_template_apply_sets_dependencies_and_guidance()` - Tests template application

**Skipped Tests** (1):
- ❌ `test_workflow_list_all_sorts_by_recent_activity()` - Marked for resource (workflow://workflows)

#### Resource Tests (`test_workflow_resources.py`)

**Coverage**:
- ✅ `test_read_success()` - Tests workflow list retrieval via resource
- ✅ `test_read_failure()` - Tests error handling
- ✅ `test_read_with_params()` - Tests workflow status retrieval with ID
- ✅ `test_read_missing_param()` - Tests validation

**Gap Analysis**:
- ⚠️ Missing: Sorting test (workflow list order verification)

**Recommendation**:
- **DO NOT DELETE** `test_workflow_orchestration.py` - Contains valuable service-level tests
- Port the sorting test to resource tests

---

### 2. Metadata Tests

#### Old Tool Tests (`test_metadata_examples.py`)

**Active Tests** (DO NOT DELETE):
- ✅ `test_create_metadata_from_template_success()` - Tests template creation
- ✅ `test_create_metadata_from_template_failure()` - Tests error handling

**Skipped Tests** (2):
- ❌ `test_show_metadata_examples_structure()` - Marked for resource (metadata://examples)
- ❌ `test_fix_metadata_validation_issues_contents()` - Marked for resource (metadata://troubleshooting)

#### Resource Tests (`test_metadata_resources.py`)

**Coverage**:
- ✅ `TestMetadataTemplatesResource` - Tests template list retrieval
- ✅ `TestMetadataExamplesResource` - Tests examples retrieval
- ✅ `TestMetadataTroubleshootingResource` - Tests troubleshooting guide
- ✅ `TestMetadataTemplateResource` - Tests specific template retrieval

**Gap Analysis**:
- ⚠️ Resource tests mock the service functions but don't verify their structure
- ⚠️ The skipped tests verify actual data structure (fields, nested keys)

**Recommendation**:
- **DO NOT DELETE** `test_metadata_examples.py` - Contains valuable service-level tests
- Port structure verification tests to resource tests

---

### 3. Governance Tests

#### Old Tool Tests (`test_governance.py`)

**Active Tests** (DO NOT DELETE - Test write operations):
- ✅ `test_admin_user_create_success()` - Tests user creation
- ✅ `test_admin_user_create_validation_errors()` - Tests validation
- ✅ `test_admin_user_delete_success()` - Tests deletion
- ✅ `test_admin_user_set_email_success()` - Tests email update
- ✅ `test_admin_user_set_admin_success()` - Tests admin status
- ✅ `test_admin_user_set_active_success()` - Tests active status
- ✅ `test_admin_user_reset_password_success()` - Tests password reset
- ✅ `test_admin_user_set_role_success()` - Tests role assignment
- ✅ `test_admin_user_add_roles_success()` - Tests role addition
- ✅ `test_admin_user_remove_roles_success()` - Tests role removal
- ✅ `test_admin_sso_config_set_success()` - Tests SSO config update
- ✅ `test_admin_sso_config_set_empty()` - Tests validation
- ✅ `test_admin_sso_config_remove_success()` - Tests SSO removal
- ✅ `test_admin_tabulator_open_query_set_success()` - Tests tabulator config

**Skipped Tests** (6):
- ❌ `test_admin_users_list_success()` - Marked for resource (admin://users)
- ❌ `test_admin_users_list_unavailable()` - Marked for resource (admin://users)
- ❌ `test_admin_user_get_success()` - Marked for resource (admin://users/{name})
- ❌ `test_admin_user_get_not_found()` - Marked for resource (admin://users/{name})
- ❌ `test_admin_user_get_empty_name()` - Marked for resource (admin://users/{name})
- ❌ `test_admin_roles_list_success()` - Marked for resource (admin://roles)
- ❌ `test_admin_roles_list_unavailable()` - Marked for resource (admin://roles)
- ❌ `test_admin_sso_config_get_success()` - Marked for resource (admin://config)
- ❌ `test_admin_sso_config_get_none()` - Marked for resource (admin://config)
- ❌ `test_admin_tabulator_open_query_get_success()` - Marked for resource (admin://config)

#### Resource Tests (`test_admin_resources.py`)

**Coverage**: Need to check this file

**Recommendation**:
- **DO NOT DELETE** `test_governance.py` - Contains many active write operation tests
- Verify resource tests cover all skipped read operations

---

### 4. Tabulator Tests

#### Old Tool Tests (`test_tabulator.py`)

**Active Tests** (DO NOT DELETE):
- ✅ `test_create_table_normalizes_parser_format()` - Tests table creation
- ✅ `test_create_table_returns_validation_errors()` - Tests validation
- ✅ `test_tabulator_query_discovers_catalog_from_catalog_info()` - Tests query discovery
- ✅ `test_tabulator_query_accepts_database_name()` - Tests query with database
- ✅ `test_tabulator_query_fails_without_catalog_config()` - Tests error handling
- ✅ `test_tabulator_bucket_query_calls_tabulator_query_with_database()` - Tests bucket query
- ✅ `test_tabulator_bucket_query_validates_bucket_name()` - Tests validation
- ✅ `test_tabulator_bucket_query_validates_query()` - Tests validation

**Skipped Tests** (2):
- ❌ `test_tabulator_buckets_list_calls_tabulator_query()` - Marked for resource (tabulator://buckets)
- ❌ `test_tabulator_buckets_list_handles_query_failure()` - Marked for resource (tabulator://buckets)

#### Resource Tests (`test_tabulator_resources.py`)

**Coverage**:
- ✅ `test_read_success()` - Tests bucket list retrieval
- ✅ `test_read_failure()` - Tests error handling
- ✅ `test_read_catalog_not_configured()` - Tests catalog config error
- ✅ `test_read_with_params()` - Tests table list with bucket param
- ✅ `test_read_missing_param()` - Tests validation
- ✅ `test_read_failure()` - Tests table list failure

**Gap Analysis**:
- ⚠️ Resource tests don't verify that _tabulator_query is called correctly
- ⚠️ Missing: Verification that SHOW DATABASES is used for bucket list

**Recommendation**:
- **DO NOT DELETE** `test_tabulator.py` - Contains valuable service-level tests
- Consider porting the query call verification tests

---

## Conclusion

### Files That CANNOT Be Deleted

All four test files contain active tests that verify important functionality:

1. **test_workflow_orchestration.py** - 3 active tests for service layer
2. **test_metadata_examples.py** - 2 active tests for service layer
3. **test_governance.py** - 14+ active tests for write operations
4. **test_tabulator.py** - 8 active tests for service layer

### Recommendation

**Do NOT delete any of these test files.** Instead:

1. Keep all active tests (they test service layer functionality)
2. For skipped tests:
   - Option A: Remove only the skipped test functions (keep the file)
   - Option B: Convert skipped tests to active tests that verify resource behavior
3. Port missing coverage to resource tests
4. Update skip messages to be more descriptive

### Alternative Approach

Since these files contain many active tests, we should:

1. **Remove only the individual skipped test functions**
2. **Keep the test files** - they provide valuable service-level test coverage
3. **Add any missing coverage to resource tests**
4. **Update documentation** to clarify that tool tests now test the service layer

This aligns with the architecture:
- **Service tests** (`test_*.py`) - Test service layer functions directly
- **Resource tests** (`test_*_resources.py`) - Test MCP resource layer

Both layers need testing!

---

## Action Items

### Phase 2, Task 2.2: Port Missing Test Cases

1. **Workflow**: Port sorting test to resource tests
2. **Metadata**: Port structure verification to resource tests
3. **Governance**: Verify all read operations covered in resource tests
4. **Tabulator**: Port query call verification if needed

### Phase 2, Task 2.3: Remove Deprecated Tests

**REVISED APPROACH**: Instead of deleting entire files, remove only skipped test functions:

```python
# Remove these functions from test_workflow_orchestration.py:
- test_workflow_list_all_sorts_by_recent_activity()

# Remove these functions from test_metadata_examples.py:
- test_show_metadata_examples_structure()
- test_fix_metadata_validation_issues_contents()

# Remove these functions from test_governance.py:
- test_admin_users_list_success()
- test_admin_users_list_unavailable()
- test_admin_user_get_success()
- test_admin_user_get_not_found()
- test_admin_user_get_empty_name()
- test_admin_roles_list_success()
- test_admin_roles_list_unavailable()
- test_admin_sso_config_get_success()
- test_admin_sso_config_get_none()
- test_admin_tabulator_open_query_get_success()

# Remove these functions from test_tabulator.py:
- test_tabulator_buckets_list_calls_tabulator_query()
- test_tabulator_buckets_list_handles_query_failure()
```

Keep the test files and all active tests!
