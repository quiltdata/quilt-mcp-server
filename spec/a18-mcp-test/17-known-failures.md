
--- Testing tool: check_bucket_access ---
[2026-02-07 21:47:26] ℹ️ Calling tool: check_bucket_access
[2026-02-07 21:47:26] ℹ️ ✅ Tool check_bucket_access executed successfully
❌ check_bucket_access: FAILED - Tool returned error response
   Error: 1 validation error for call[check_bucket_access]
context
  Missing required keyword only argument [type=missing_keyword_only_argument, input_value={'bucket': 'quilt-ernest-staging'}, input_type=dict]
    For further information visit <https://errors.pydantic.dev/2.11/v/missing_keyword_only_argument>

--- Testing tool: discover_permissions ---
[2026-02-07 21:47:26] ℹ️ Calling tool: discover_permissions
[2026-02-07 21:47:26] ℹ️ ✅ Tool discover_permissions executed successfully
❌ discover_permissions: FAILED - Tool returned error response
   Error: 1 validation error for call[discover_permissions]
context
  Missing required keyword only argument [type=missing_keyword_only_argument, input_value={'check_buckets': ['quilt-ernest-staging']}, input_type=dict]
    For further information visit <https://errors.pydantic.dev/2.11/v/missing_keyword_only_argument>

--- Testing tool: generate_package_visualizations ---
[2026-02-07 21:47:26] ℹ️ Calling tool: generate_package_visualizations
[2026-02-07 21:47:28] ℹ️ ✅ Tool generate_package_visualizations executed successfully
[2026-02-07 21:47:28] ℹ️ ✅ Response schema validation passed
✅ generate_package_visualizations: PASSED

--- Testing tool: generate_quilt_summarize_json ---
[2026-02-07 21:47:28] ℹ️ Calling tool: generate_quilt_summarize_json
[2026-02-07 21:47:28] ℹ️ ✅ Tool generate_quilt_summarize_json executed successfully
❌ generate_quilt_summarize_json: FAILED - Tool returned error response
   Error: 1 validation error for call[generate_quilt_summarize_json]
package_metadata
  Input should be a valid dictionary [type=dict_type, input_value='raw/test', input_type=str]
    For further information visit <https://errors.pydantic.dev/2.11/v/dict_type>

--- Testing tool: workflow_template_apply ---
[2026-02-07 21:48:08] ℹ️ Calling tool: workflow_template_apply
[2026-02-07 21:48:08] ℹ️ ✅ Tool workflow_template_apply executed successfully
❌ workflow_template_apply: FAILED - Tool returned error response
   Error: Workflow 'test-wf-001' already exists

📊 Test Results: 26/30 tools passed

🔧 TOOLS (Tested 30/55 tested, 25 skipped)
   Selection: Idempotent only (SKIPPED: configure: 6, create: 15, none-context-required: 2, remove: 5, update: 5)
   ✅ 26 passed, ❌ 4 failed

   ❌ Failed Tools (4):

      • check_bucket_access
        Tool: check_bucket_access
        Input: {
         "bucket": "quilt-ernest-staging"
}
        Error: Tool returned error response: 1 validation error for call[check_bucket_access]
               context
                 Missing required keyword only argument [type=missing_keyword_only_argument, input_value={'bucket': 'quilt-ernest-staging'}, input_type=dict]
                   For further information visit <https://errors.pydantic.dev/2.11/v/missing_keyword_only_argument>
        Error Type: ErrorResponse

      • discover_permissions
        Tool: discover_permissions
        Input: {
         "check_buckets": [
                  "quilt-ernest-staging"
         ]
}
        Error: Tool returned error response: 1 validation error for call[discover_permissions]
               context
                 Missing required keyword only argument [type=missing_keyword_only_argument, input_value={'check_buckets': ['quilt-ernest-staging']}, input_type=dict]
                   For further information visit <https://errors.pydantic.dev/2.11/v/missing_keyword_only_argument>
        Error Type: ErrorResponse

      • generate_quilt_summarize_json
        Tool: generate_quilt_summarize_json
        Input: {
         "package_name": "raw/test",
         "package_metadata": "raw/test",
         "organized_structure": {
                  "files": [
                           {
                                    "name": "test.txt",
                                    "size": 100
                           }
                  ]
         },
         "readme_content": "# Test Package",
         "source_info": {
                  "type": "test"
         }
}
        Error: Tool returned error response: 1 validation error for call[generate_quilt_summarize_json]
               package_metadata
                 Input should be a valid dictionary [type=dict_type, input_value='raw/test', input_type=str]
                   For further information visit <https://errors.pydantic.dev/2.11/v/dict_type>
        Error Type: ErrorResponse

      • workflow_template_apply
        Tool: workflow_template_apply
        Input: {
         "template_name": "cross-package-aggregation",
         "workflow_id": "test-wf-001",
         "params": {
                  "source_packages": [
                           "raw/test"
                  ],
                  "target_package": "raw/test-agg"
         }
}
        Error: Tool returned error response: Workflow 'test-wf-001' already exists
        Error Type: ErrorResponse

   ⚠️  Untested Tools with Side Effects (4):
      • check_bucket_access
      • discover_permissions
      • generate_quilt_summarize_json
      • workflow_template_apply

🔄 TOOL LOOPS
   ✅ 11 passed, ❌ 12 failed

   ❌ Failed Loops (12):

      • Loop: admin_user_basic
        Failed at step 1: admin_user_create
        Error: Admin operation failed: Admin operation failed: errors=[InvalidInputSelectionErrors(path='input.role', message='No role exists by the provided name', name='RoleNotFound', context={'role': 'viewer'})] typename__='InvalidInput'

      • Loop: admin_user_basic
        Failed at step 3: admin_user_delete
        (cleanup step failure)
        Error: User not found: User not found: None

      • Loop: admin_user_with_roles
        Failed at step 1: admin_user_create
        Error: Admin operation failed: Admin operation failed: errors=[InvalidInputSelectionErrors(path='input.role', message='No role exists by the provided name', name='RoleNotFound', context={'role': 'viewer'})] typename__='InvalidInput'

      • Loop: admin_user_with_roles
        Failed at step 5: admin_user_delete
        (cleanup step failure)
        Error: User not found: User not found: None

      • Loop: admin_user_modifications
        Failed at step 1: admin_user_create
        Error: Admin operation failed: Admin operation failed: errors=[InvalidInputSelectionErrors(path='input.role', message='No role exists by the provided name', name='RoleNotFound', context={'role': 'viewer'})] typename__='InvalidInput'

      • Loop: admin_user_modifications
        Failed at step 7: admin_user_delete
        (cleanup step failure)
        Error: User not found: User not found: None

      • Loop: admin_sso_config
        Failed at step 1: admin_sso_config_set
        Error: Admin operation failed: Admin operation failed: errors=[InvalidInputSelectionErrors(path='config.__root__', message='Config expected dict not str', name='ValidationError', context={'loc': ['__root__'], 'msg': 'Config expected dict not str', 'type': 'type_error'})] typename__='InvalidInput'

      • Loop: admin_sso_config
        Failed at step 2: admin_sso_config_remove
        (cleanup step failure)
        Error: Admin operation failed: Failed to remove SSO configuration: module 'quilt3.admin.sso_config' has no attribute 'remove'

      • Loop: package_lifecycle
        Failed at step 1: package_create
        Error: Failed to create package: Invalid S3 URI at index 0: must start with 's3://'

      • Loop: package_create_from_s3_loop
        Failed at step 1: package_create_from_s3
        Error: Cannot create package in target registry

      • Loop: bucket_objects_write
        Failed at step 2: bucket_object_fetch
        Error: 1 validation error for call[bucket_object_fetch]
s3_uri
  String should match pattern '^s3://[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]/.+' [type=string_pattern_mismatch, input_value='quilt-ernest-staging/test-loop-5c9fdade.txt', input_type=str]
    For further information visit <https://errors.pydantic.dev/2.11/v/string_pattern_mismatch>

      • Loop: tabulator_table_lifecycle
        Failed at step 1: tabulator_table_create
        Error: Invalid configuration: config.schema.0.type: unexpected value; permitted: 'BOOLEAN', 'TINYINT', 'SMALLINT', 'INT', 'BIGINT', 'FLOAT', 'DOUBLE', 'STRING', 'BINARY', 'DATE', 'TIMESTAMP'

🗂️  RESOURCES (15/15 tested)
   Type Breakdown: 15 static URIs, 0 templates
   ✅ 15 passed

================================================================================
   Overall Status: ❌ CRITICAL FAILURE

- 4/30 core tools failing
- 12 tool loops failing
- Immediate action required
================================================================================

🛑 Stopping server local-413592e0...
✅ Server stopped gracefully
make: *** [test-mcp] Error 1
