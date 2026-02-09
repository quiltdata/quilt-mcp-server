# A19-05: MCP Tool Reference

**Status**: Current
**Author**: System
**Date**: 2024-02-08
**Server Version**: 2.14.4

## Overview

This document provides a comprehensive reference of all MCP capabilities in the Quilt MCP Server:

- **53 Tools**: Organized by category and effect type
- **15 Resources**: URI-based data access endpoints
- **16 Tool Loops**: Multi-step test workflows for write operations

## Quick Start: Testing MCP Capabilities

### How to Run Tests

Recommend: 60 second timeouts

**Individual Tools:**

```bash
# Test a specific tool
uv run python scripts/mcp-test.py --tools bucket_objects_list

# Test multiple tools
uv run python scripts/mcp-test.py --tools bucket_objects_list,package_browse

# Test tools by pattern (glob)
uv run python scripts/mcp-test.py --tools "bucket_*"

# Test all tools (excludes write operations)
uv run python scripts/mcp-test.py --tools
```

**Tool Loops** (for write operations):

```bash
# Test a specific loop
uv run python scripts/mcp-test.py --loops admin_user_basic

# Test multiple loops
uv run python scripts/mcp-test.py --loops admin_user_basic,package_lifecycle

# Test all loops
uv run python scripts/mcp-test.py --loops
```

**Resources:**

```bash
# Test a specific resource
uv run python scripts/mcp-test.py --resources "auth://status"

# Test resources by pattern
uv run python scripts/mcp-test.py --resources "auth://*"

# Test all resources
uv run python scripts/mcp-test.py --resources
```

**Combined Testing:**

```bash
# Run everything (tools + loops + resources)
uv run python scripts/mcp-test.py --all

# Run tools and resources only
uv run python scripts/mcp-test.py --tools --resources
```

### How to Regenerate Test Configuration

**⚠️ IMPORTANT: DO NOT manually edit `scripts/tests/mcp-test.yaml`**

The YAML configuration is auto-generated from the MCP server implementation. To regenerate:

```bash
# Full regeneration with discovery
uv run python scripts/mcp-test-setup.py

# Skip discovery (faster, no validation)
uv run python scripts/mcp-test-setup.py --skip-discovery

# Validate coverage without regenerating
uv run python scripts/mcp-test-setup.py --validate-only

# Show tools missing from config
uv run python scripts/mcp-test-setup.py --show-missing

# Show tool classifications
uv run python scripts/mcp-test-setup.py --show-categories
```

**When to regenerate:**

- After adding/removing tools in source code
- After modifying tool signatures
- After adding new resources
- When coverage validation fails

### Validation and Coverage

```bash
# Validate 100% tool coverage (exit 0 if pass, 1 if fail)
uv run python scripts/mcp-test-setup.py --validate-only

# List uncovered tools
uv run python scripts/mcp-test-setup.py --show-missing

# View tool categories and effects
uv run python scripts/mcp-test-setup.py --show-categories
```

## Tool Classification System

Tools are classified by two dimensions:

### By Category (Argument Requirements)

- **ZERO ARG**: No arguments required
- **REQUIRED ARG**: At least one required argument
- **OPTIONAL ARG**: All arguments are optional
- **WRITE EFFECT**: Tools that modify state

### By Effect Type

- **none**: Read-only operations, safe for discovery
- **configure**: Configuration changes (reversible)
- **create**: Creates new resources
- **update**: Modifies existing resources
- **remove**: Deletes resources

## Tool Inventory

### Summary Statistics

**Tools:**

- **Total Tools**: 53
- **Zero Arg**: 3 tools (6%)
- **Required Arg**: 5 tools (9%)
- **Optional Arg**: 20 tools (38%)
- **Write Effect**: 25 tools (47%)

**Resources:**

- **Total Resources**: 15
- **Auth Resources**: 3 (authentication & catalog)
- **Admin Resources**: 2 (user management)
- **Metadata Resources**: 3 (templates & examples)
- **Workflow Resources**: 1 (workflow listings)
- **Tabulator Resources**: 6 (bucket & table info)

**Tool Loops:**

- **Total Loops**: 16
- **Admin Loops**: 5 (user & SSO management)
- **Package Loops**: 2 (lifecycle & bulk operations)
- **Other Loops**: 9 (buckets, workflows, tabulator, viz)

### Read-Only Operations (28 tools)

Tools with `effect=none` are safe for discovery and testing:

- Zero arg: 3 tools
- Required arg: 2 tools
- Optional arg: 17 tools
- Context-required: 6 tools

### Write Operations (25 tools)

Tools that modify state, tested via tool loops:

- Create: 11 tools
- Update: 8 tools
- Remove: 6 tools

---

## Tools by Category

### ZERO ARG (3 tools)

No arguments required - simplest to test and discover.

#### Tool #1: `discover_permissions`

- [x] **Verified**
- **Effect**: none
- **Category**: zero-arg
- **Module**: resources
- **Description**: Discover available permissions and resources
- **Testing**: Direct invocation, no mocking needed

#### Tool #2: `get_resource`

- [x] **Verified**
- **Effect**: none
- **Category**: zero-arg
- **Module**: resources
- **Description**: Get resource information
- **Testing**: Direct invocation, requires resource context

#### Tool #3: `tabulator_list_buckets`

- [x] **Verified**
- **Effect**: none
- **Category**: zero-arg
- **Module**: tabulator
- **Description**: List all buckets accessible via Tabulator
- **Testing**: Requires AWS credentials, may return empty list

---

### REQUIRED ARG (5 tools)

At least one argument must be provided.

#### Tool #4: `athena_query_validate`

- [x] **Verified**
- **Effect**: none
- **Category**: required-arg
- **Module**: athena
- **Description**: Validate an Athena SQL query without executing
- **Required Args**: `query` (SQL string)
- **Testing**: Use sample queries from fixtures

#### Tool #5: `bucket_object_info`

- [x] **Verified**
- **Effect**: none
- **Category**: required-arg
- **Module**: buckets
- **Description**: Get metadata for a specific S3 object
- **Required Args**: `s3_uri` (full S3 path)
- **Testing**: Use known test bucket objects

#### Tool #6: `catalog_configure`

- [x] **Verified**
- **Effect**: configure
- **Category**: required-arg
- **Module**: catalog
- **Description**: Configure Quilt catalog URL
- **Required Args**: `catalog_url` (URL or friendly name)
- **Testing**: Use sandbox catalogs (demo, sandbox, open)

#### Tool #7: `tabulator_tables_list`

- [x] **Verified**
- **Effect**: none
- **Category**: required-arg
- **Module**: tabulator
- **Description**: List tables in a Tabulator bucket
- **Required Args**: `bucket` (bucket name)
- **Testing**: Requires Tabulator-enabled bucket

#### Tool #8: `workflow_template_apply`

- [x] **Verified**
- **Effect**: configure
- **Category**: required-arg
- **Module**: workflows
- **Description**: Apply a workflow template
- **Required Args**: `template_name`, `workflow_id`
- **Testing**: Via tool loops with create → apply → cleanup

---

### OPTIONAL ARG (20 tools)

All arguments have defaults or are truly optional.

#### Authentication & Catalog

##### Tool #9: `catalog_uri`

- [x] **Verified**
- **Effect**: none
- **Module**: catalog
- **Description**: Build Quilt+ URI (quilt+s3://...)
- **Optional Args**: `registry`, `package_name`, `path`, `top_hash`, `tag`, `catalog_host`
- **Testing**: Various URI format combinations

##### Tool #10: `catalog_url`

- [x] **Verified**
- **Effect**: none
- **Module**: catalog
- **Description**: Generate Quilt catalog URL (https://...)
- **Optional Args**: `registry`, `package_name`, `path`, `catalog_host`
- **Testing**: Various URL format combinations

#### Bucket Operations

##### Tool #11: `bucket_object_fetch`

- [x] **Verified**
- **Effect**: none
- **Module**: buckets
- **Description**: Fetch binary or text data from S3 object
- **Optional Args**: `s3_uri`, `max_bytes`, `base64_encode`
- **Testing**: Fetch small test files (< 1MB)

##### Tool #12: `bucket_object_link`

- [x] **Verified**
- **Effect**: none
- **Module**: buckets
- **Description**: Generate presigned URL for S3 object
- **Optional Args**: `s3_uri`, `expiration`
- **Testing**: Verify URL generation, not actual download

##### Tool #13: `bucket_object_text`

- [x] **Verified**
- **Effect**: none
- **Module**: buckets
- **Description**: Read text content from S3 object
- **Optional Args**: `s3_uri`, `max_bytes`, `encoding`
- **Testing**: Read small text files (README, CSV headers)

##### Tool #14: `bucket_objects_list`

- [x] **Verified**
- **Effect**: none
- **Module**: buckets
- **Description**: List objects in S3 bucket
- **Optional Args**: `bucket`, `prefix`, `max_keys`, `continuation_token`
- **Testing**: List with various prefix filters

##### Tool #15: `check_bucket_access`

- [x] **Verified**
- **Effect**: none
- **Module**: buckets
- **Description**: Check read/write access to S3 bucket
- **Optional Args**: `bucket`
- **Testing**: Test with known accessible buckets

#### Package Operations

##### Tool #16: `package_browse`

- [x] **Verified**
- **Effect**: none
- **Module**: packages
- **Description**: Browse package contents with file info
- **Optional Args**: `package_name`, `registry`, `top_hash`, `tag`, `path`, `recursive`, `include_signed_urls`, `top`
- **Testing**: Browse known test packages

##### Tool #17: `package_diff`

- [x] **Verified**
- **Effect**: none
- **Module**: packages
- **Description**: Compare two package versions
- **Optional Args**: `package_name`, `registry`, `left_hash`, `right_hash`, `left_tag`, `right_tag`, `include_details`
- **Testing**: Diff known package versions

##### Tool #18: `generate_package_visualizations`

- [x] **Verified**
- **Effect**: configure
- **Module**: visualization
- **Description**: Generate visualizations for package data
- **Optional Args**: `package_name`, `registry`, `top_hash`, `tag`, `path`, `viz_types`, `output_format`
- **Testing**: Generate viz for test packages

##### Tool #19: `generate_quilt_summarize_json`

- [x] **Verified**
- **Effect**: configure
- **Module**: packages
- **Description**: Generate quilt_summarize.json for package
- **Optional Args**: `package_name`, `registry`, `top_hash`, `tag`, `path`, `output_path`
- **Testing**: Generate summaries for test packages

#### Search Operations

##### Tool #20: `search_catalog`

- [x] **Verified**
- **Effect**: none
- **Module**: search
- **Description**: Search catalog for packages, objects, or queries
- **Optional Args**: `query`, `filter`, `limit`, `offset`, `sort_by`, `sort_order`
- **Testing**: Test with various query patterns

##### Tool #21: `search_explain`

- [x] **Verified**
- **Effect**: none
- **Module**: search
- **Description**: Explain how a search query is interpreted
- **Optional Args**: `query`, `search_type`
- **Testing**: Explain various query syntaxes

##### Tool #22: `search_suggest`

- [x] **Verified**
- **Effect**: none
- **Module**: search
- **Description**: Get search suggestions as user types
- **Optional Args**: `prefix`, `limit`, `context`
- **Testing**: Test autocomplete scenarios

#### Athena/Tabulator Operations

##### Tool #23: `athena_query_execute`

- [x] **Verified**
- **Effect**: configure
- **Module**: athena
- **Description**: Execute Athena SQL query
- **Optional Args**: `query`, `database`, `output_location`, `wait_for_completion`, `max_results`
- **Testing**: Execute read-only SELECT queries

##### Tool #24: `athena_table_schema`

- [x] **Verified**
- **Effect**: none
- **Module**: athena
- **Description**: Get schema for Athena table
- **Optional Args**: `table_name`, `database`
- **Testing**: Get schema for known tables

##### Tool #25: `athena_tables_list`

- [x] **Verified**
- **Effect**: none
- **Module**: athena
- **Description**: List tables in Athena database
- **Optional Args**: `database`, `pattern`
- **Testing**: List tables with various filters

##### Tool #26: `tabulator_bucket_query`

- [x] **Verified**
- **Effect**: none
- **Module**: tabulator
- **Description**: Query Tabulator data in bucket
- **Optional Args**: `bucket`, `query`, `limit`, `offset`
- **Testing**: Execute read-only queries

##### Tool #27: `tabulator_query_execute`

- [x] **Verified**
- **Effect**: configure
- **Module**: tabulator
- **Description**: Execute Tabulator query
- **Optional Args**: `query`, `bucket`, `table`, `limit`, `wait_for_completion`
- **Testing**: Execute read-only SELECT queries

#### Admin Operations (Read-Only)

##### Tool #28: `admin_user_get`

- [x] **Verified**
- **Effect**: none
- **Module**: admin
- **Description**: Get user information
- **Optional Args**: `username`, `email`, `user_id`
- **Testing**: Requires admin permissions

---

### WRITE EFFECT (25 tools)

Tools that modify state, tested via tool loops with create → verify → cleanup cycles.

#### Admin: SSO Configuration (2 tools)

##### Tool #29: `admin_sso_config_set`

- [x] **Verified**
- **Effect**: create
- **Category**: write-effect
- **Module**: admin
- **Description**: Set SSO configuration
- **Testing**: Tool loop with set → verify → remove

##### Tool #30: `admin_sso_config_remove`

- [x] **Verified**
- **Effect**: remove
- **Category**: write-effect
- **Module**: admin
- **Description**: Remove SSO configuration
- **Testing**: Part of SSO config loop

#### Admin: User Management (10 tools)

##### Tool #31: `admin_user_create`

- [x] **Verified**
- **Effect**: create
- **Module**: admin
- **Description**: Create new user account
- **Testing**: Tool loop with create → verify → delete

##### Tool #32: `admin_user_delete`

- [x] **Verified**
- **Effect**: remove
- **Module**: admin
- **Description**: Delete user account
- **Testing**: Part of user lifecycle loop

##### Tool #33: `admin_user_add_roles`

- [x] **Verified**
- **Effect**: update
- **Module**: admin
- **Description**: Add roles to user
- **Testing**: Role management loop

##### Tool #34: `admin_user_remove_roles`

- [x] **Verified**
- **Effect**: remove
- **Module**: admin
- **Description**: Remove roles from user
- **Testing**: Part of role management loop

##### Tool #35: `admin_user_reset_password`

- [x] **Verified**
- **Effect**: create
- **Module**: admin
- **Description**: Reset user password
- **Testing**: Password lifecycle loop

##### Tool #36: `admin_user_set_active`

- [x] **Verified**
- **Effect**: create
- **Module**: admin
- **Description**: Set user active/inactive status
- **Testing**: User status loop

##### Tool #37: `admin_user_set_admin`

- [x] **Verified**
- **Effect**: create
- **Module**: admin
- **Description**: Set user admin status
- **Testing**: Admin privilege loop

##### Tool #38: `admin_user_set_email`

- [x] **Verified**
- **Effect**: create
- **Module**: admin
- **Description**: Update user email
- **Testing**: User profile update loop

##### Tool #39: `admin_user_set_role`

- [x] **Verified**
- **Effect**: create
- **Module**: admin
- **Description**: Set user role
- **Testing**: Role assignment loop

##### Tool #40: `admin_tabulator_open_query_set`

- [x] **Verified**
- **Effect**: create
- **Module**: admin
- **Description**: Set open query permissions in Tabulator
- **Testing**: Tabulator config loop

#### Bucket Operations (1 tool)

##### Tool #41: `bucket_objects_put`

- [x] **Verified**
- **Effect**: create
- **Module**: buckets
- **Description**: Upload multiple objects to S3
- **Testing**: Tool loop with upload → verify → cleanup

#### Package Operations (4 tools)

##### Tool #42: `package_create`

- [x] **Verified**
- **Effect**: create
- **Module**: packages
- **Description**: Create new package from S3 objects
- **Testing**: Tool loop with create → verify → delete

##### Tool #43: `package_create_from_s3`

- [x] **Verified**
- **Effect**: create
- **Module**: packages
- **Description**: Create organized package from S3 bucket
- **Testing**: Bulk ingestion loop

##### Tool #44: `package_update`

- [x] **Verified**
- **Effect**: update
- **Module**: packages
- **Description**: Update existing package with new objects
- **Testing**: Update loop with create → update → verify → delete

##### Tool #45: `package_delete`

- [x] **Verified**
- **Effect**: remove
- **Module**: packages
- **Description**: Delete package from registry
- **Testing**: Part of package lifecycle loop

#### Visualization Operations (2 tools)

##### Tool #46: `create_data_visualization`

- [x] **Verified**
- **Effect**: create
- **Module**: visualization
- **Description**: Create data visualization
- **Testing**: Viz creation loop

##### Tool #47: `create_quilt_summary_files`

- [x] **Verified**
- **Effect**: create
- **Module**: packages
- **Description**: Create package summary files
- **Testing**: Summary generation loop

#### Tabulator Operations (3 tools)

##### Tool #48: `tabulator_table_create`

- [x] **Verified**
- **Effect**: create
- **Module**: tabulator
- **Description**: Create Tabulator table
- **Testing**: Table lifecycle loop

##### Tool #49: `tabulator_table_delete`

- [x] **Verified**
- **Effect**: remove
- **Module**: tabulator
- **Description**: Delete Tabulator table
- **Testing**: Part of table lifecycle loop

##### Tool #50: `tabulator_table_rename`

- [x] **Verified**
- **Effect**: update
- **Module**: tabulator
- **Description**: Rename Tabulator table
- **Testing**: Table rename loop

#### Workflow Operations (3 tools)

##### Tool #51: `workflow_create`

- [x] **Verified**
- **Effect**: create
- **Module**: workflows
- **Description**: Create new workflow
- **Testing**: Workflow lifecycle loop

##### Tool #52: `workflow_add_step`

- [x] **Verified**
- **Effect**: update
- **Module**: workflows
- **Description**: Add step to workflow
- **Testing**: Workflow modification loop

##### Tool #53: `workflow_update_step`

- [x] **Verified**
- **Effect**: update
- **Module**: workflows
- **Description**: Update workflow step
- **Testing**: Step update loop

---

## Resources (15 URI-Based Endpoints)

Resources provide URI-based access to server data and configurations. Unlike tools (which perform actions),
resources are read-only data endpoints accessible via URI patterns.

### Resource URI Schemes

**Authentication & Catalog (3 resources):**

- `auth://status` - Check authentication status and catalog configuration
- `auth://catalog/info` - Get catalog configuration details
- `auth://filesystem/status` - Check filesystem permissions and writability

**Admin Operations (2 resources):**

- `admin://users` - List all users in the Quilt registry with roles/status (requires admin)
- `admin://roles` - List all available roles and permissions (requires admin)

**Metadata & Documentation (3 resources):**

- `metadata://templates` - Get package metadata templates
- `metadata://examples` - Get example package configurations
- `metadata://troubleshooting` - Get troubleshooting guides and common issues

**Workflow Resources (1 resource):**

- `workflow://workflows` - List all available workflows in the registry

**Tabulator Resources (6 resources):**

- `tabulator://buckets` - List Tabulator-enabled buckets
- `tabulator://buckets/{bucket}` - Get bucket configuration
- `tabulator://buckets/{bucket}/tables` - List tables in bucket
- `tabulator://buckets/{bucket}/tables/{table}` - Get table schema
- `tabulator://buckets/{bucket}/tables/{table}/columns` - Get column metadata
- `tabulator://buckets/{bucket}/tables/{table}/stats` - Get table statistics

### Resource Testing

Resources are tested via the `--resources` flag:

```bash
# Test all resources
uv run python scripts/mcp-test.py --resources

# Test specific resource
uv run python scripts/mcp-test.py --resources "auth://status"

# Test by URI pattern (glob)
uv run python scripts/mcp-test.py --resources "tabulator://*"
```

### Resource Configuration

Resources are defined in `scripts/tests/mcp-test.yaml` under `test_resources`:

```yaml
test_resources:
  auth://status:
    description: Check authentication status and catalog configuration
    effect: none
    uri: auth://status
    uri_variables: {}
    expected_mime_type: application/json
    content_validation:
      type: json
      schema:
        type: object
```

**Resource properties:**

- `uri`: The resource URI pattern
- `uri_variables`: Variables for URI template substitution
- `expected_mime_type`: Expected content type
- `content_validation`: Schema and validation rules
- `effect`: Always `none` (resources are read-only)

---

## Testing Strategy by Category

### Zero Arg Tools (3)

- **Approach**: Direct invocation
- **Complexity**: Low
- **Discovery**: Always safe
- **Mocking**: None needed

### Required Arg Tools (5)

- **Approach**: Infer from environment/discovery
- **Complexity**: Medium
- **Discovery**: Safe (except configure effect)
- **Mocking**: Minimal (bucket names, queries)

### Optional Arg Tools (20)

- **Approach**: Use defaults when possible
- **Complexity**: Medium-High
- **Discovery**: Mostly safe
- **Mocking**: Selective (based on effect)

### Write Effect Tools (25)

- **Approach**: Tool loops (create → verify → cleanup)
- **Complexity**: High
- **Discovery**: Never discover (skip)
- **Mocking**: Extensive (requires test resources)

## Tool Loop Coverage

Tool loops provide end-to-end testing of write operations with create → verify → cleanup cycles.
Each loop tests one or more write-effect tools in a realistic workflow sequence.

### Running Tool Loops

```bash
# Test a specific loop
uv run python scripts/mcp-test.py --loops admin_user_basic

# Test multiple loops
uv run python scripts/mcp-test.py --loops admin_user_basic,package_lifecycle

# Test all loops
uv run python scripts/mcp-test.py --loops

# List available loops
uv run python scripts/mcp-test.py --list-loops
```

### Available Tool Loops (16 total)

**Admin User Management (5 loops):**

1. **`admin_user_basic`**: Basic user lifecycle
   - Tools: admin_user_create → admin_user_get → admin_user_delete
   - Duration: ~5s

2. **`admin_user_with_roles`**: Role management
   - Tools: admin_user_create → admin_user_add_roles → admin_user_get → admin_user_remove_roles → admin_user_delete
   - Duration: ~8s

3. **`admin_user_modifications`**: User attribute updates
   - Tools: admin_user_create → admin_user_set_email/set_active/set_admin → admin_user_delete
   - Duration: ~10s

4. **`admin_sso_config`**: SSO configuration
   - Tools: admin_sso_config_set → verify → admin_sso_config_remove
   - Duration: ~3s

5. **`admin_tabulator_query`**: Tabulator open query config
   - Tools: admin_tabulator_open_query_set → verify
   - Duration: ~2s

**Package Operations (2 loops):**

1. **`package_lifecycle`**: Complete package lifecycle
   - Tools: package_create → package_browse → package_update → package_browse → package_delete
   - Duration: ~15s

2. **`package_create_from_s3_loop`**: Bulk S3 ingestion
   - Tools: package_create_from_s3 → package_browse → package_delete
   - Duration: ~20s

**Bucket Operations (1 loop):**

1. **`bucket_objects_write`**: S3 upload and verification
   - Tools: bucket_objects_put → bucket_objects_list → bucket_object_info
   - Duration: ~5s

**Workflow Operations (1 loop):**

1. **`workflow_basic`**: Workflow creation and modification
   - Tools: workflow_create → workflow_add_step → workflow_update_step
   - Duration: ~7s

**Visualization Operations (1 loop):**

1. **`visualization_create`**: Data visualization generation
   - Tools: create_data_visualization → bucket_object_info
   - Duration: ~10s

**Tabulator Operations (1 loop):**

1. **`tabulator_table_lifecycle`**: Table create/rename/delete
   - Tools: tabulator_table_create → tabulator_tables_list → tabulator_table_rename → tabulator_table_delete
   - Duration: ~12s

**Quilt Summary (1 loop):**

1. **`quilt_summary_create`**: Generate package summaries
   - Tools: create_quilt_summary_files → bucket_objects_list
   - Duration: ~8s

### Tool Loop Features

- **Template Substitution**: Use `{uuid}` for unique IDs, `{env.VAR}` for environment variables
- **Cleanup on Failure**: Automatically cleanup resources even if steps fail
- **Prerequisites**: Loops handle tool dependencies (e.g., create before update)
- **Timeout Control**: Global and per-loop timeout configuration
- **Retry Logic**: Configurable retry attempts for transient failures

## Tool Discovery Results

Tool discovery is performed by `mcp-test-setup.py` with a 15-second timeout per tool.

### Discovery Behavior

- **Discovered**: Tools that return data without errors
- **Skipped**: Write-effect tools (never discovered)
- **Failed**: Tools that timeout or error
- **Context-Required**: Tools requiring authentication context

### Discovery Data Extraction

The discovery process captures:

- **S3 Keys**: From `bucket_objects_list` responses
- **Package Names**: From search/browse responses
- **Tables**: From Athena/Tabulator responses
- **Catalog Resources**: From resource listings

This data is used to:

1. Generate realistic test arguments
2. Validate tool functionality
3. Build tool loop templates
4. Ensure 100% coverage

## Tool Modules

Tools are organized into 12 functional modules:

1. **admin** (11 tools): User management, SSO, Tabulator config
2. **athena** (3 tools): Query execution and validation
3. **buckets** (7 tools): S3 object operations
4. **catalog** (3 tools): Catalog URL/URI generation
5. **packages** (8 tools): Package CRUD and browsing
6. **resources** (2 tools): Resource discovery
7. **search** (3 tools): Catalog search operations
8. **tabulator** (6 tools): Tabulator operations
9. **visualization** (2 tools): Viz generation
10. **workflows** (4 tools): Workflow management

## Tool Testing Configuration

**Configuration File**: `scripts/tests/mcp-test.yaml` (auto-generated by `mcp-test-setup.py`)

**⚠️ DO NOT EDIT MANUALLY** - Regenerate via: `uv run python scripts/mcp-test-setup.py`

### Configuration Structure

The YAML configuration has four main sections:

#### 1. Environment Variables

```yaml
environment:
  AWS_PROFILE: default
  AWS_DEFAULT_REGION: us-east-1
  QUILT_TEST_BUCKET: quilt-ernest-staging
  QUILT_TEST_PACKAGE: raw/test
  QUILT_CATALOG_URL: https://nightly.quilttest.com
```

#### 2. Test Tools (Individual Tool Tests)

```yaml
test_tools:
  bucket_objects_list:
    description: List objects in an S3 bucket with optional prefix filtering
    effect: none
    category: optional-arg
    arguments:
      bucket: quilt-ernest-staging
      prefix: raw/test/
      max_keys: 5
    response_schema:
      type: object
      properties:
        content:
          type: array
          items:
            type: object
      required:
        - content
```

#### 3. Test Resources (URI-Based Endpoints)

```yaml
test_resources:
  auth://status:
    description: Check authentication status and catalog configuration
    effect: none
    uri: auth://status
    uri_variables: {}
    expected_mime_type: application/json
    content_validation:
      type: json
      min_length: 1
      max_length: 100000
      schema:
        type: object
```

#### 4. Tool Loops (Multi-Step Write Operations)

```yaml
tool_loops:
  admin_user_basic:
    description: Test admin user create/get/delete cycle
    cleanup_on_failure: true
    steps:
      - tool: admin_user_create
        args:
          name: tlu{uuid}
          email: tlu{uuid}@example.com
          role: ReadQuiltBucket
        expect_success: true
      - tool: admin_user_get
        args:
          name: tlu{uuid}
        expect_success: true
      - tool: admin_user_delete
        args:
          name: tlu{uuid}
        expect_success: true
        is_cleanup: true
```

**Tool Loop Features:**

- **Template Variables**: `{uuid}` for unique IDs, `{env.VAR}` for environment variables
- **Cleanup Steps**: Mark steps with `is_cleanup: true` to run even on failure
- **Success Validation**: `expect_success: true|false` to validate step outcomes
- **Shared Context**: Variables from early steps flow to later steps

## Coverage Validation

The MCP server enforces 100% tool coverage to ensure all capabilities are tested.

### Coverage Requirements

Every tool must be covered by ONE of:

1. **Standalone test** in `test_tools` section (for read operations)
2. **Tool loop** in `tool_loops` section (for write operations)
3. **Explicit skip** with documented reason (rare)

### Validation Commands

```bash
# Check coverage status (exit 0 if 100%, 1 if missing)
uv run python scripts/mcp-test-setup.py --validate-only

# List tools missing from configuration
uv run python scripts/mcp-test-setup.py --show-missing

# View tool classifications and effects
uv run python scripts/mcp-test-setup.py --show-categories

# Regenerate to achieve 100% coverage
uv run python scripts/mcp-test-setup.py
```

### Coverage Report Example

```bash
$ uv run python scripts/mcp-test-setup.py --show-missing
✅ All 53 tools covered by test config

$ uv run python scripts/mcp-test-setup.py --validate-only
✅ Coverage validation PASSED: 53 tools covered
```

If coverage is incomplete:

```bash
$ uv run python scripts/mcp-test-setup.py --show-missing
❌ 3 tool(s) NOT covered by test config:
  • new_tool_example (category=optional-arg, effect=none)
  • another_new_tool (category=write-effect, effect=create)
  • third_tool (category=zero-arg, effect=none)

📋 Coverage: 50/53 tools
   Run without --show-missing to regenerate with 100% coverage
```

---

## References

### Configuration & Testing

- **Test Configuration**: [scripts/tests/mcp-test.yaml](../../scripts/tests/mcp-test.yaml) (auto-generated)
- **Test Runner**: [scripts/mcp-test.py](../../scripts/mcp-test.py)
- **Config Generator**: [scripts/mcp-test-setup.py](../../scripts/mcp-test-setup.py)
- **Testing Framework**: [src/quilt_mcp/testing/](../../src/quilt_mcp/testing/)

### Implementation

- **Tool Implementations**: [src/quilt_mcp/tools/](../../src/quilt_mcp/tools/)
- **Resource Implementations**: [src/quilt_mcp/resources/](../../src/quilt_mcp/resources/)
- **Tool Classification**: [src/quilt_mcp/testing/tool_classifier.py](../../src/quilt_mcp/testing/tool_classifier.py)
- **Discovery Engine**: [src/quilt_mcp/testing/discovery.py](../../src/quilt_mcp/testing/discovery.py)

### Testing Framework Modules

- **Discovery Orchestrator**: [src/quilt_mcp/testing/discovery.py](../../src/quilt_mcp/testing/discovery.py)
- **Tool Loop Generator**: [src/quilt_mcp/testing/tool_loops.py](../../src/quilt_mcp/testing/tool_loops.py)
- **Argument Inference**: [src/quilt_mcp/testing/argument_inference.py](../../src/quilt_mcp/testing/argument_inference.py)
- **Coverage Validation**: [src/quilt_mcp/testing/coverage.py](../../src/quilt_mcp/testing/coverage.py)
- **Output Generation**: [src/quilt_mcp/testing/output.py](../../src/quilt_mcp/testing/output.py)

## Changelog

- **2026-02-08**: Major enhancement - Made document actionable and testable
  - Added Quick Start section with clear testing commands
  - Documented all 15 resources (URI-based endpoints)
  - Expanded tool loops from 12 to 16 with detailed descriptions
  - Added "How to Regenerate" section with warnings against manual editing
  - Enhanced coverage validation with examples and exit codes
  - Added comprehensive YAML configuration examples
  - Improved references with direct links to implementation files
- **2024-02-08**: Initial tool reference created (v2.14.4, 53 tools)
- **2024-02-08**: Added sequential numbering (Tool #1-53) and verification checkboxes
