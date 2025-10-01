<!-- markdownlint-disable MD013 MD024 -->
# A06 Admin Consolidation Analysis

## Executive Summary

Analysis of 79 MCP tools identifies function groups that manage the same resource across multiple operations. These groups represent consolidation opportunities to simplify the API surface.

**Data Source**: `tests/fixtures/mcp-list.csv` - live server introspection

## Resource-Based Function Groupings

### 1. User Management (11 functions - governance module)

**User Management:**

- `admin_user_create` - Create user
- `admin_user_delete` - Delete user
- `admin_user_get` - Read user details
- `admin_users_list` - List all users
- `admin_user_set_active` - Update active status
- `admin_user_set_admin` - Update admin status
- `admin_user_set_email` - Update email
- `admin_user_reset_password` - Reset password

**Role Management:**

- `admin_user_set_role` - Set primary/extra roles
- `admin_user_add_roles` - Add roles to user
- `admin_user_remove_roles` - Remove roles from user
- `admin_roles_list` - List available roles (not user management)

**Consolidation Opportunity**: Classic CRUD pattern that could benefit from unified interface design.

#### Resource

- admin-users
- admin-roles

### 2. Package Management (12 functions - multiple modules)

- `create_package` (unified_package) - Unified interface

#### Obsolete (3 functions)

NOTE: create_package should be canonical. The others should be removed.
Warn of any non-trivial functionality that might be lost.

- `package_create` (package_management) - Enhanced creation with templates
- `package_update` (package_ops) - Update package
- `package_update_metadata`

#### Package Summary Generation (3 functions)

**Generate package documentation and visualizations:**

- `create_quilt_summary_files` (quilt_summary) - Generate package summaries
- `generate_quilt_summarize_json` (quilt_summary) - Generate summary JSON

Duplicates: create a single package_summarize tool

### 3. Search Operations (4 functions - different modules)

**Overlapping search with different backends:**

- `catalog_search` (search) - Intelligent unified search

NOTE: catalog_search should be canonical. The others should be removed.

#### Obsolete

- `packages_search` (packages) - Package-specific search
- `bucket_objects_search` (buckets) - Elasticsearch search
- `bucket_objects_search_graphql` (buckets) - GraphQL search

### 4. Tabulator Operations (5 functions - tabulator module)

- `get_tabulator_service` - Service instance -- why is this public?

#### Tabulator Access

- admin_tabulator_access_get
- admin_tabulator_access_set

#### Resource

tabulator_access

### 5. Admin SSO Operations (3 functions - governance module)

**Complete SSO configuration management:**

- `admin_sso_config_get` - Get SSO configuration
- `admin_sso_config_remove` - Remove SSO config
- `admin_sso_config_set` - Set SSO configuration

#### Resource

- admin_sso_config

### 6. Metadata Templates (2 functions - different modules)

**Similar template functionality:**

- `metadata_template_get` (metadata_templates) - Get template with custom fields
- `metadata_template_create` (metadata_examples) - Create from template (simplified interface)
- `list_metadata_templates`

#### Resource

- metadata_template

### 7. Catalog Config

- `catalog_info` - Get catalog configuration
- `catalog_name` - Get catalog name
- `configure_catalog` - Set catalog URL
- `switch_catalog` - Change catalogs

#### Resource

- catalog_config
