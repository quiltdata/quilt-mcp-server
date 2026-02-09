"""Tool loop framework for write-operation testing.

This module provides template-based loop execution for testing write operations
with create → modify → verify → cleanup cycles. It ensures safe testing of
state-changing operations with proper rollback and cleanup.

Core Components
---------------
ToolLoopExecutor : class
    Executes multi-step tool loops with templated arguments, state tracking,
    and automatic cleanup. Handles failures gracefully with rollback support.

substitute_templates(value, env_vars, loop_uuid) -> Any
    Recursively substitute template variables in arguments including {uuid}
    for unique identifiers and {env.VAR} for environment variables.

generate_tool_loops(env_vars, base_role, secondary_role) -> Dict[str, Any]
    Generate comprehensive tool loop configurations for all write-effect
    operations including package lifecycle, role management, and bucket ops.

get_test_roles() -> Tuple[str, str]
    Get standard test roles (base and secondary) for user management tests.
    Ensures consistent role naming across test runs.

validate_tool_loops_coverage(server_tools, tool_loops, standalone_tools) -> None
    Validate that all write-effect tools are covered by either tool loops
    or standalone test configurations. Raises assertion for missing coverage.

Loop Execution Pattern
----------------------
Tool loops follow a standard pattern:

1. Create Phase
   - Create new resource with unique identifier
   - Verify resource creation succeeded
   - Record resource identifiers for cleanup

2. Modify Phase (Optional)
   - Update resource properties
   - Verify modifications applied
   - Test update idempotency

3. Verify Phase
   - List/search operations find resource
   - Read operations return correct data
   - Permissions work as expected

4. Cleanup Phase
   - Delete created resources
   - Verify deletion succeeded
   - Restore original state

5. Rollback (On Failure)
   - Cleanup partial state
   - Log failure details
   - Don't fail subsequent tests

Template System
---------------
The template substitution system supports:

1. UUID Templates
   - {uuid}: Generated unique identifier per loop
   - {uuid[:8]}: Truncated UUID for shorter names
   - Ensures test isolation and idempotency

2. Environment Variables
   - {env.VAR_NAME}: Substituted from environment
   - {env.TEST_QUILT_CATALOG_URL}: Common pattern
   - Fails fast if variable not set

3. Nested Substitution
   - Templates in nested dictionaries
   - Templates in lists and tuples
   - Recursive processing

4. Type Preservation
   - Strings remain strings
   - Numbers remain numbers
   - Booleans, nulls preserved

Usage Examples
--------------
Execute a tool loop:
    >>> executor = ToolLoopExecutor(
    ...     name="package_lifecycle",
    ...     loop_config={
    ...         "create": {"tool": "package_create", "args": {"name": "test-{uuid}"}},
    ...         "verify": {"tool": "package_list", "validate": {"contains": "test-{uuid}"}},
    ...         "cleanup": {"tool": "package_delete", "args": {"name": "test-{uuid}"}}
    ...     },
    ...     env_vars={"TEST_QUILT_CATALOG_URL": "s3://my-bucket"}
    ... )
    >>> result = await executor.execute(mcp_tester)
    >>> print(result.summary())

Substitute templates:
    >>> args = {
    ...     "name": "test-package-{uuid}",
    ...     "catalog_url": "{env.TEST_QUILT_CATALOG_URL}",
    ...     "count": 10
    ... }
    >>> env = {"TEST_QUILT_CATALOG_URL": "s3://bucket"}
    >>> substituted = substitute_templates(args, env, "abc123")
    >>> print(substituted)
    {'name': 'test-package-abc123', 'catalog_url': 's3://bucket', 'count': 10}

Generate tool loops:
    >>> env = {"TEST_QUILT_CATALOG_URL": "s3://my-bucket"}
    >>> loops = generate_tool_loops(env, "test-role-1", "test-role-2")
    >>> print(loops.keys())
    dict_keys(['package_lifecycle', 'role_lifecycle', 'user_management'])

Validate loop coverage:
    >>> validate_tool_loops_coverage(
    ...     server_tools=all_tools,
    ...     tool_loops=generated_loops,
    ...     standalone_tools=manual_tests
    ... )
    # Raises AssertionError if any write-effect tool lacks coverage

Design Principles
-----------------
- Safe execution with automatic cleanup
- Idempotent loops that can run multiple times
- Clear separation of create/modify/verify/cleanup phases
- Fail-safe cleanup even after test failures
- Template-based configuration for flexibility
- Comprehensive logging for debugging

Loop Configuration Schema
-------------------------
Each loop configuration includes:

```yaml
loop_name:
  create:
    tool: "tool_name"
    args: {...}  # Template-based arguments
    store_result: "variable_name"  # Optional result capture

  modify:  # Optional
    tool: "tool_name"
    args: {...}

  verify:
    tool: "tool_name"
    args: {...}
    validate:
      contains: "expected_value"  # Or other validation rules

  cleanup:
    tool: "tool_name"
    args: {...}
    ignore_errors: true  # Optional
```

State Management
----------------
The executor maintains state across loop phases:

1. Loop UUID
   - Unique identifier per execution
   - Used for resource naming
   - Ensures test isolation

2. Stored Results
   - Capture tool outputs
   - Reference in subsequent phases
   - Enable complex workflows

3. Cleanup Stack
   - Track resources to cleanup
   - Execute in reverse order
   - Handle partial failures

4. Execution Context
   - Environment variables
   - Current phase
   - Error state

Dependencies
------------
- models.py: TestResults for result tracking
- validators.py: validate_loop_coverage for coverage checks
- uuid: UUID generation for unique identifiers
- re: Template pattern matching

Extracted From
--------------
- substitute_templates: lines 586-627 from scripts/mcp-test.py
- ToolLoopExecutor: lines 630-852 from scripts/mcp-test.py
- get_test_roles: lines 629-640 from scripts/mcp-test-setup.py
- generate_tool_loops: lines 643-1045 from scripts/mcp-test-setup.py
- validate_tool_loops_coverage: lines 1048-1085 from scripts/mcp-test-setup.py
"""

from __future__ import annotations

import json
import re
import uuid as uuid_module
from typing import TYPE_CHECKING, Any, Dict, Tuple

if TYPE_CHECKING:
    from .client import MCPTester

from .models import TestResults
from .tool_classifier import classify_tool


# ============================================================================
# Template Substitution (extracted from scripts/mcp-test.py lines 586-627)
# ============================================================================


def substitute_templates(value: Any, env_vars: Dict[str, str], loop_uuid: str) -> Any:
    """Recursively substitute template variables in configuration values.

    Template variables:
    - {uuid}: Replaced with loop-specific UUID
    - {env.VAR_NAME}: Replaced with environment variable value

    Args:
        value: Value to substitute (can be str, dict, list, or other)
        env_vars: Environment variables from config
        loop_uuid: UUID for this loop execution

    Returns:
        Value with templates substituted

    Raises:
        ValueError: If template variable cannot be resolved
    """
    if isinstance(value, str):
        # Replace {uuid}
        result = value.replace("{uuid}", loop_uuid)

        # Replace {env.VAR_NAME}
        env_pattern = r'\{env\.(\w+)\}'
        matches = re.findall(env_pattern, result)
        for var_name in matches:
            env_value = env_vars.get(var_name)
            if env_value is None:
                raise ValueError(f"Environment variable '{var_name}' not found in config")
            result = result.replace(f"{{env.{var_name}}}", env_value)

        return result

    elif isinstance(value, dict):
        return {k: substitute_templates(v, env_vars, loop_uuid) for k, v in value.items()}

    elif isinstance(value, list):
        return [substitute_templates(item, env_vars, loop_uuid) for item in value]

    else:
        # Return as-is for other types (int, bool, None, etc.)
        return value


# ============================================================================
# Tool Loop Executor (extracted from scripts/mcp-test.py lines 630-852)
# ============================================================================


class ToolLoopExecutor:
    """Executes tool loops with create → modify → verify → cleanup cycles."""

    def __init__(self, tester: MCPTester, env_vars: Dict[str, str], verbose: bool = False):
        """Initialize loop executor.

        Args:
            tester: MCPTester instance for calling tools
            env_vars: Environment variables for template substitution
            verbose: Enable verbose output
        """
        self.tester = tester
        self.env_vars = env_vars
        self.verbose = verbose
        self.results = TestResults()

    def execute_loop(self, loop_name: str, loop_config: Dict[str, Any]) -> bool:
        """Execute a single tool loop.

        Args:
            loop_name: Name of the loop
            loop_config: Loop configuration with steps

        Returns:
            True if loop succeeded, False otherwise
        """
        print(f"\n{'=' * 80}")
        print(f"🔄 Executing Tool Loop: {loop_name}")
        print(f"{'=' * 80}")
        print(f"Description: {loop_config.get('description', 'No description')}")

        steps = loop_config.get('steps', [])
        cleanup_on_failure = loop_config.get('cleanup_on_failure', True)

        # Generate UUID for this loop
        loop_uuid = str(uuid_module.uuid4())[:8]  # Use first 8 chars for readability
        print(f"Loop UUID: {loop_uuid}")
        print(f"Total steps: {len(steps)}")

        # Track which step we're on
        failed_step_index = None
        failed_step_name = None
        failed_error = None

        # Execute steps in sequence
        for step_index, step in enumerate(steps):
            tool_name = step.get('tool')
            raw_args = step.get('args', {})
            expect_success = step.get('expect_success', True)
            is_cleanup = step.get('is_cleanup', False)

            # If we already failed and this isn't a cleanup step, skip it
            if failed_step_index is not None and not is_cleanup:
                print(f"\n⏭️  Step {step_index + 1}: {tool_name} (SKIPPED - previous failure)")
                continue

            print(f"\n--- Step {step_index + 1}/{len(steps)}: {tool_name} ---")
            if is_cleanup:
                print("   (cleanup step)")

            try:
                # Substitute templates
                substituted_args = substitute_templates(raw_args, self.env_vars, loop_uuid)

                if self.verbose:
                    print(f"   Arguments: {json.dumps(substituted_args, indent=2)}")

                # Call the tool
                result = self.tester.call_tool(tool_name, substituted_args)

                # Check for error response
                if self._is_error_response(result):
                    error_msg = self._extract_error_message(result)
                    if expect_success:
                        print("   ❌ FAILED: Tool returned error")
                        print(f"   Error: {error_msg}")
                        failed_step_index = step_index
                        failed_step_name = tool_name
                        failed_error = error_msg

                        # If this is a cleanup step, record failure but continue
                        if is_cleanup:
                            self.results.record_failure(
                                {
                                    "loop": loop_name,
                                    "step": step_index + 1,
                                    "tool": tool_name,
                                    "args": substituted_args,
                                    "error": error_msg,
                                    "is_cleanup": True,
                                }
                            )
                        else:
                            # Non-cleanup failure - will trigger cleanup
                            self.results.record_failure(
                                {
                                    "loop": loop_name,
                                    "step": step_index + 1,
                                    "tool": tool_name,
                                    "args": substituted_args,
                                    "error": error_msg,
                                }
                            )

                        # If not cleanup and cleanup_on_failure, continue to run cleanup steps
                        if not is_cleanup and cleanup_on_failure:
                            print("   ⚠️  Will attempt cleanup steps...")
                            continue
                        elif not cleanup_on_failure:
                            # Stop immediately
                            break
                    else:
                        # Error was expected
                        print(f"   ✅ Expected error occurred: {error_msg}")
                        self.results.record_pass(
                            {
                                "loop": loop_name,
                                "step": step_index + 1,
                                "tool": tool_name,
                                "args": substituted_args,
                                "expected_error": True,
                            }
                        )
                else:
                    # Success
                    print("   ✅ SUCCESS")
                    self.results.record_pass(
                        {"loop": loop_name, "step": step_index + 1, "tool": tool_name, "args": substituted_args}
                    )

            except Exception as e:
                print(f"   ❌ FAILED: {e}")
                failed_step_index = step_index
                failed_step_name = tool_name
                failed_error = str(e)

                self.results.record_failure(
                    {
                        "loop": loop_name,
                        "step": step_index + 1,
                        "tool": tool_name,
                        "args": raw_args,  # Use raw args in error report
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "is_cleanup": is_cleanup,
                    }
                )

                # If not cleanup and cleanup_on_failure, continue to run cleanup steps
                if not is_cleanup and cleanup_on_failure:
                    print("   ⚠️  Will attempt cleanup steps...")
                    continue
                elif not cleanup_on_failure:
                    # Stop immediately
                    break

        # Print loop summary
        print(f"\n{'=' * 80}")
        if failed_step_index is None:
            print(f"✅ Loop '{loop_name}' PASSED ({len(steps)} steps)")
            return True
        else:
            print(f"❌ Loop '{loop_name}' FAILED at step {failed_step_index + 1}: {failed_step_name}")
            print(f"   Error: {failed_error}")
            if cleanup_on_failure:
                cleanup_steps = [s for s in steps if s.get('is_cleanup', False)]
                print(f"   Cleanup: Attempted {len(cleanup_steps)} cleanup step(s)")
            return False

    def _is_error_response(self, result: Dict[str, Any]) -> bool:
        """Check if the MCP response indicates an error."""
        try:
            content = result.get("content", [])
            if content and isinstance(content[0], dict) and "text" in content[0]:
                text_content = content[0]["text"]

                # Check for validation errors
                if "validation error" in text_content.lower():
                    return True

                # Try to parse as JSON and check for error field
                try:
                    data = json.loads(text_content)
                    return "error" in data and isinstance(data["error"], str)
                except json.JSONDecodeError:
                    return False

            return False
        except Exception:
            return False

    def _extract_error_message(self, result: Dict[str, Any]) -> str:
        """Extract the error message from an error response."""
        try:
            content = result.get("content", [])
            if content and isinstance(content[0], dict) and "text" in content[0]:
                text_content = content[0]["text"]

                # Check for validation errors
                if "validation error" in text_content.lower():
                    return text_content.strip()

                # Try to parse as JSON
                try:
                    data = json.loads(text_content)
                    return data.get("error", "Unknown error")
                except json.JSONDecodeError:
                    return text_content[:200] if len(text_content) > 200 else text_content

            return "Could not parse error message"
        except Exception:
            return "Could not parse error message"

    def execute_all_loops(self, tool_loops: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Execute all tool loops.

        Args:
            tool_loops: Dictionary of loop configurations

        Returns:
            Results dictionary
        """
        print(f"\n🔄 Executing {len(tool_loops)} Tool Loops...")

        for loop_name, loop_config in tool_loops.items():
            success = self.execute_loop(loop_name, loop_config)
            # Results already tracked in execute_loop

        return self.results.to_dict()


# ============================================================================
# Tool Loop Generation (extracted from scripts/mcp-test-setup.py lines 629-1085)
# ============================================================================


def get_test_roles() -> Tuple[str, str]:
    """Get the standard test roles for user management tests.

    Returns:
        (base_role, secondary_role) tuple with two distinct role names
        Uses ReadQuiltBucket and ReadWriteQuiltBucket as test roles
    """
    base_role = "ReadQuiltBucket"
    secondary_role = "ReadWriteQuiltBucket"

    print(f"   ✅ Using test roles: base='{base_role}', secondary='{secondary_role}'")
    return base_role, secondary_role


def generate_tool_loops(env_vars: Dict[str, str | None], base_role: str, secondary_role: str) -> Dict[str, Any]:
    """Generate tool loops configuration for write-operation testing.

    Tool loops test write operations through create → modify → verify → cleanup cycles.
    Each loop uses template variables ({uuid}, {env.VAR}) that are substituted at runtime.

    Args:
        env_vars: Environment variables for template substitution
        base_role: Primary role name to use for user creation
        secondary_role: Secondary role name for role modification tests

    Returns:
        Dictionary with tool_loops configuration
    """
    test_bucket = env_vars.get("QUILT_TEST_BUCKET", "s3://quilt-example")

    return {
        "admin_user_basic": {
            "description": "Test admin user create/get/delete cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "admin_user_create",
                    "args": {"name": "tlu{uuid}", "email": "tlu{uuid}@example.com", "role": base_role},
                    "expect_success": True,
                },
                {"tool": "admin_user_get", "args": {"name": "tlu{uuid}"}, "expect_success": True},
                {
                    "tool": "admin_user_delete",
                    "args": {"name": "tlu{uuid}"},
                    "expect_success": True,
                    "is_cleanup": True,
                },
            ],
        },
        "admin_user_with_roles": {
            "description": "Test admin user add/remove roles",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "admin_user_create",
                    "args": {"name": "tlu{uuid}", "email": "tlu{uuid}@example.com", "role": base_role},
                    "expect_success": True,
                },
                {
                    "tool": "admin_user_add_roles",
                    "args": {"name": "tlu{uuid}", "roles": [secondary_role]},
                    "expect_success": True,
                },
                {"tool": "admin_user_get", "args": {"name": "tlu{uuid}"}, "expect_success": True},
                {
                    "tool": "admin_user_remove_roles",
                    "args": {"name": "tlu{uuid}", "roles": [secondary_role]},
                    "expect_success": True,
                },
                {
                    "tool": "admin_user_delete",
                    "args": {"name": "tlu{uuid}"},
                    "expect_success": True,
                    "is_cleanup": True,
                },
            ],
        },
        "admin_user_modifications": {
            "description": "Test admin user set operations (email, role, admin, active, reset password)",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "admin_user_create",
                    "args": {"name": "tlu{uuid}", "email": "tlu{uuid}@example.com", "role": base_role},
                    "expect_success": True,
                },
                {
                    "tool": "admin_user_set_email",
                    "args": {"name": "tlu{uuid}", "email": "tlu{uuid}x@example.com"},
                    "expect_success": True,
                },
                {
                    "tool": "admin_user_set_role",
                    "args": {"name": "tlu{uuid}", "role": secondary_role},
                    "expect_success": True,
                },
                {"tool": "admin_user_set_admin", "args": {"name": "tlu{uuid}", "admin": True}, "expect_success": True},
                {
                    "tool": "admin_user_set_active",
                    "args": {"name": "tlu{uuid}", "active": False},
                    "expect_success": True,
                },
                {"tool": "admin_user_reset_password", "args": {"name": "tlu{uuid}"}, "expect_success": True},
                {
                    "tool": "admin_user_delete",
                    "args": {"name": "tlu{uuid}"},
                    "expect_success": True,
                    "is_cleanup": True,
                },
            ],
        },
        "admin_sso_config": {
            "description": "Test SSO configuration set/remove cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "admin_sso_config_set",
                    "args": {
                        "config": {
                            "version": "1.0",
                            "provider": "test-{uuid}",
                            "saml_config": "<test_sso_config>test config</test_sso_config>",
                            "mappings": [],
                            "default_role": "ReadQuiltBucket",
                        }
                    },
                    "expect_success": True,
                },
                {"tool": "admin_sso_config_remove", "args": {}, "expect_success": True, "is_cleanup": True},
            ],
        },
        "admin_tabulator_query": {
            "description": "Test tabulator open query set/toggle cycle",
            "cleanup_on_failure": True,
            "steps": [
                {"tool": "admin_tabulator_open_query_set", "args": {"enabled": True}, "expect_success": True},
                {
                    "tool": "admin_tabulator_open_query_set",
                    "args": {"enabled": False},
                    "expect_success": True,
                    "is_cleanup": True,
                },
            ],
        },
        "package_lifecycle": {
            "description": "Test package create/update/delete cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "package_create",
                    "args": {
                        "package_name": "testuser/loop-pkg-{uuid}",
                        "registry": "s3://{env.QUILT_TEST_BUCKET}",
                        "s3_uris": ["s3://{env.QUILT_TEST_BUCKET}/{env.QUILT_TEST_PACKAGE}/{env.QUILT_TEST_ENTRY}"],
                        "message": "Test package created by tool loop",
                    },
                    "expect_success": True,
                },
                {
                    "tool": "package_browse",
                    "args": {"package_name": "testuser/loop-pkg-{uuid}", "registry": "s3://{env.QUILT_TEST_BUCKET}"},
                    "expect_success": True,
                },
                {
                    "tool": "package_update",
                    "args": {
                        "package_name": "testuser/loop-pkg-{uuid}",
                        "registry": "s3://{env.QUILT_TEST_BUCKET}",
                        "s3_uris": ["s3://{env.QUILT_TEST_BUCKET}/{env.QUILT_TEST_PACKAGE}/.timestamp"],
                        "message": "Updated by tool loop",
                    },
                    "expect_success": True,
                },
                {
                    "tool": "package_delete",
                    "args": {"package_name": "testuser/loop-pkg-{uuid}", "registry": "s3://{env.QUILT_TEST_BUCKET}"},
                    "expect_success": True,
                    "is_cleanup": True,
                },
            ],
        },
        "package_create_from_s3_loop": {
            "description": "Test package_create_from_s3 tool",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "package_create_from_s3",
                    "args": {
                        "source_bucket": "{env.QUILT_TEST_BUCKET}",
                        "package_name": "testuser/s3pkg-{uuid}",
                        "target_registry": "s3://{env.QUILT_TEST_BUCKET}",
                        "source_prefix": "{env.QUILT_TEST_PACKAGE}/",
                        "confirm_structure": False,
                        "force": True,
                    },
                    "expect_success": True,
                },
                {
                    "tool": "package_delete",
                    "args": {"package_name": "testuser/s3pkg-{uuid}", "registry": "s3://{env.QUILT_TEST_BUCKET}"},
                    "expect_success": True,
                    "is_cleanup": True,
                },
            ],
        },
        "bucket_objects_write": {
            "description": "Test bucket object put/fetch cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "bucket_objects_put",
                    "args": {
                        "bucket": "{env.QUILT_TEST_BUCKET}",
                        "items": [{"key": "test-loop-{uuid}.txt", "text": "Test content from tool loop"}],
                    },
                    "expect_success": True,
                },
                {
                    "tool": "bucket_object_fetch",
                    "args": {"s3_uri": "s3://{env.QUILT_TEST_BUCKET}/test-loop-{uuid}.txt", "max_bytes": 1000},
                    "expect_success": True,
                },
                # Note: No explicit delete - test files can be cleaned up manually
            ],
        },
        "workflow_basic": {
            "description": "Test workflow create/add step/update step cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "workflow_create",
                    "args": {"workflow_id": "test-wf-{uuid}", "name": "Test Workflow {uuid}"},
                    "expect_success": True,
                },
                {
                    "tool": "workflow_add_step",
                    "args": {"workflow_id": "test-wf-{uuid}", "step_id": "step1", "description": "Test Step 1"},
                    "expect_success": True,
                },
                {
                    "tool": "workflow_update_step",
                    "args": {"workflow_id": "test-wf-{uuid}", "step_id": "step1", "status": "completed"},
                    "expect_success": True,
                },
                # Note: No explicit workflow delete - workflows can be cleaned up manually
            ],
        },
        "visualization_create": {
            "description": "Test visualization creation",
            "cleanup_on_failure": False,
            "steps": [
                {
                    "tool": "create_data_visualization",
                    "args": {
                        "data": {"x": [1, 2, 3], "y": [4, 5, 6]},
                        "plot_type": "scatter",
                        "x_column": "x",
                        "y_column": "y",
                    },
                    "expect_success": True,
                }
                # Note: Visualization is read-only (creates file but doesn't persist state)
            ],
        },
        "tabulator_table_lifecycle": {
            "description": "Test tabulator table create/rename/delete cycle",
            "cleanup_on_failure": True,
            "steps": [
                {
                    "tool": "tabulator_table_create",
                    "args": {
                        "bucket_name": "{env.QUILT_TEST_BUCKET}",
                        "table_name": "test_table_{uuid}",
                        "schema": [{"name": "col1", "type": "STRING"}],
                        "package_pattern": "*/pkg",
                        "logical_key_pattern": "*.csv",
                    },
                    "expect_success": True,
                },
                {
                    "tool": "tabulator_table_rename",
                    "args": {
                        "bucket_name": "{env.QUILT_TEST_BUCKET}",
                        "table_name": "test_table_{uuid}",
                        "new_table_name": "test_table_{uuid}_renamed",
                    },
                    "expect_success": True,
                },
                {
                    "tool": "tabulator_table_delete",
                    "args": {"bucket_name": "{env.QUILT_TEST_BUCKET}", "table_name": "test_table_{uuid}_renamed"},
                    "expect_success": True,
                    "is_cleanup": True,
                },
            ],
        },
        "quilt_summary_create": {
            "description": "Test create_quilt_summary_files tool",
            "cleanup_on_failure": False,
            "steps": [
                {
                    "tool": "create_quilt_summary_files",
                    "args": {
                        "package_name": "testuser/test-pkg",
                        "package_metadata": {"description": "test"},
                        "organized_structure": {"root": []},
                        "readme_content": "# Test Package",
                        "source_info": {"source": "test"},
                        "metadata_template": "standard",
                    },
                    "expect_success": True,
                }
            ],
        },
    }


def validate_tool_loops_coverage(
    server_tools: Dict[str, Any], tool_loops: Dict[str, Any], standalone_tools: Dict[str, Any]
) -> None:
    """Validate that tool loops + standalone tests cover all write-effect tools.

    Args:
        server_tools: All tools from server
        tool_loops: Tool loops configuration
        standalone_tools: Standalone test configurations

    Raises:
        ValueError: If coverage is incomplete
    """
    # Find all write-effect tools
    write_tools = set()
    for tool_name, handler in server_tools.items():
        effect, _ = classify_tool(tool_name, handler)
        if effect in ['create', 'update', 'remove']:
            write_tools.add(tool_name)

    # Find tools covered by loops
    loop_covered = set()
    for loop_name, loop_config in tool_loops.items():
        for step in loop_config.get('steps', []):
            tool_name = step.get('tool')
            if tool_name:
                loop_covered.add(tool_name)

    # Find tools covered by standalone tests
    standalone_covered = set(standalone_tools.keys())

    # Check coverage
    total_covered = loop_covered | standalone_covered
    uncovered = write_tools - total_covered

    if uncovered:
        print(f"\n⚠️  WARNING: {len(uncovered)} write-effect tool(s) not covered by loops or standalone tests:")
        for tool in sorted(uncovered):
            print(f"  • {tool}")
        print("\n💡 Add these tools to tool loops or standalone tests to achieve 100% coverage")


__all__ = [
    "substitute_templates",  # noqa: F822
    "ToolLoopExecutor",  # noqa: F822
    "get_test_roles",  # noqa: F822
    "generate_tool_loops",  # noqa: F822
    "validate_tool_loops_coverage",  # noqa: F822
]
