"""Unit tests for tool_loops module.

Tests cover:
- Template substitution with {uuid} and {env.VAR}
- Tool loop execution with mock testers
- Tool loop generation
- Coverage validation
"""

import json
import re
from typing import Any, Dict
from unittest.mock import MagicMock, Mock

import pytest

from quilt_mcp.testing.tool_loops import (
    ToolLoopExecutor,
    generate_tool_loops,
    get_test_roles,
    substitute_templates,
    validate_tool_loops_coverage,
)


# ============================================================================
# Template Substitution Tests
# ============================================================================


def test_substitute_templates_replaces_uuid():
    """Verify {uuid} template substitution."""
    value = "test-package-{uuid}"
    env_vars = {}
    loop_uuid = "abc123"

    result = substitute_templates(value, env_vars, loop_uuid)

    assert result == "test-package-abc123"


def test_substitute_templates_replaces_env_vars():
    """Verify {env.VAR} template substitution."""
    value = "s3://{env.QUILT_TEST_BUCKET}/path"
    env_vars = {"QUILT_TEST_BUCKET": "my-bucket"}
    loop_uuid = "abc123"

    result = substitute_templates(value, env_vars, loop_uuid)

    assert result == "s3://my-bucket/path"


def test_substitute_templates_replaces_multiple_templates():
    """Verify multiple template substitutions in single string."""
    value = "s3://{env.BUCKET}/pkg-{uuid}/{env.PREFIX}"
    env_vars = {"BUCKET": "test-bucket", "PREFIX": "data"}
    loop_uuid = "xyz789"

    result = substitute_templates(value, env_vars, loop_uuid)

    assert result == "s3://test-bucket/pkg-xyz789/data"


def test_substitute_templates_handles_dict():
    """Verify template substitution in nested dictionaries."""
    value = {"name": "pkg-{uuid}", "bucket": "{env.BUCKET}", "nested": {"path": "s3://{env.BUCKET}/pkg-{uuid}"}}
    env_vars = {"BUCKET": "my-bucket"}
    loop_uuid = "test123"

    result = substitute_templates(value, env_vars, loop_uuid)

    assert result["name"] == "pkg-test123"
    assert result["bucket"] == "my-bucket"
    assert result["nested"]["path"] == "s3://my-bucket/pkg-test123"


def test_substitute_templates_handles_list():
    """Verify template substitution in lists."""
    value = ["pkg-{uuid}", "{env.BUCKET}", {"key": "val-{uuid}"}]
    env_vars = {"BUCKET": "test-bucket"}
    loop_uuid = "abc"

    result = substitute_templates(value, env_vars, loop_uuid)

    assert result[0] == "pkg-abc"
    assert result[1] == "test-bucket"
    assert result[2]["key"] == "val-abc"


def test_substitute_templates_preserves_non_string_types():
    """Verify non-string types are preserved."""
    value = {"count": 42, "enabled": True, "data": None, "ratio": 3.14}
    env_vars = {}
    loop_uuid = "test"

    result = substitute_templates(value, env_vars, loop_uuid)

    assert result["count"] == 42
    assert result["enabled"] is True
    assert result["data"] is None
    assert result["ratio"] == 3.14


def test_substitute_templates_raises_on_missing_env_var():
    """Verify error when environment variable not found."""
    value = "{env.MISSING_VAR}"
    env_vars = {}
    loop_uuid = "test"

    with pytest.raises(ValueError, match="Environment variable 'MISSING_VAR' not found"):
        substitute_templates(value, env_vars, loop_uuid)


def test_substitute_templates_handles_empty_string():
    """Verify empty string handling."""
    value = ""
    env_vars = {}
    loop_uuid = "test"

    result = substitute_templates(value, env_vars, loop_uuid)

    assert result == ""


def test_substitute_templates_handles_no_templates():
    """Verify strings without templates are unchanged."""
    value = "just a normal string"
    env_vars = {}
    loop_uuid = "test"

    result = substitute_templates(value, env_vars, loop_uuid)

    assert result == "just a normal string"


# ============================================================================
# Tool Loop Executor Tests
# ============================================================================


def test_tool_loop_executor_initialization():
    """Verify ToolLoopExecutor initializes correctly."""
    mock_tester = Mock()
    env_vars = {"TEST": "value"}

    executor = ToolLoopExecutor(mock_tester, env_vars, verbose=True)

    assert executor.tester == mock_tester
    assert executor.env_vars == env_vars
    assert executor.verbose is True
    assert executor.results.total == 0


def test_tool_loop_executor_execute_simple_loop_success(capsys):
    """Verify successful execution of simple tool loop."""
    # Setup mock tester
    mock_tester = Mock()
    mock_tester.call_tool.return_value = {"content": [{"text": json.dumps({"status": "success"})}]}

    env_vars = {"BUCKET": "test-bucket"}
    executor = ToolLoopExecutor(mock_tester, env_vars, verbose=False)

    loop_config = {
        "description": "Test loop",
        "cleanup_on_failure": True,
        "steps": [{"tool": "test_tool", "args": {"bucket": "{env.BUCKET}"}, "expect_success": True}],
    }

    # Execute loop
    success = executor.execute_loop("test_loop", loop_config)

    # Verify success
    assert success is True
    assert executor.results.passed == 1
    assert executor.results.failed == 0

    # Verify output
    captured = capsys.readouterr()
    assert "Executing Tool Loop: test_loop" in captured.out
    assert "✅ Loop 'test_loop' PASSED" in captured.out


def test_tool_loop_executor_execute_loop_with_failure(capsys):
    """Verify loop execution handles failures correctly."""
    # Setup mock tester that returns error
    mock_tester = Mock()
    mock_tester.call_tool.return_value = {"content": [{"text": json.dumps({"error": "Test error"})}]}

    env_vars = {}
    executor = ToolLoopExecutor(mock_tester, env_vars, verbose=False)

    loop_config = {
        "description": "Test loop",
        "cleanup_on_failure": False,
        "steps": [{"tool": "test_tool", "args": {}, "expect_success": True}],
    }

    # Execute loop
    success = executor.execute_loop("test_loop", loop_config)

    # Verify failure
    assert success is False
    assert executor.results.passed == 0
    assert executor.results.failed == 1

    # Verify output
    captured = capsys.readouterr()
    assert "❌ Loop 'test_loop' FAILED" in captured.out


def test_tool_loop_executor_cleanup_on_failure(capsys):
    """Verify cleanup steps execute even after failure."""
    # Setup mock tester
    call_count = 0

    def mock_call(tool_name, args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call fails
            return {"content": [{"text": json.dumps({"error": "Failed"})}]}
        else:
            # Cleanup succeeds
            return {"content": [{"text": json.dumps({"status": "success"})}]}

    mock_tester = Mock()
    mock_tester.call_tool.side_effect = mock_call

    env_vars = {}
    executor = ToolLoopExecutor(mock_tester, env_vars, verbose=False)

    loop_config = {
        "description": "Test loop",
        "cleanup_on_failure": True,
        "steps": [
            {"tool": "create_tool", "args": {}, "expect_success": True},
            {"tool": "cleanup_tool", "args": {}, "expect_success": True, "is_cleanup": True},
        ],
    }

    # Execute loop
    success = executor.execute_loop("test_loop", loop_config)

    # Verify both tools were called
    assert mock_tester.call_tool.call_count == 2
    assert success is False

    # Verify results
    assert executor.results.failed == 1  # Create failed
    assert executor.results.passed == 1  # Cleanup passed


def test_tool_loop_executor_skips_non_cleanup_after_failure(capsys):
    """Verify non-cleanup steps are skipped after failure."""
    # Setup mock tester
    call_count = 0

    def mock_call(tool_name, args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call fails
            return {"content": [{"text": json.dumps({"error": "Failed"})}]}
        else:
            # Subsequent calls succeed
            return {"content": [{"text": json.dumps({"status": "success"})}]}

    mock_tester = Mock()
    mock_tester.call_tool.side_effect = mock_call

    env_vars = {}
    executor = ToolLoopExecutor(mock_tester, env_vars, verbose=False)

    loop_config = {
        "description": "Test loop",
        "cleanup_on_failure": True,
        "steps": [
            {"tool": "step1", "args": {}, "expect_success": True},
            {"tool": "step2", "args": {}, "expect_success": True},
            {"tool": "cleanup", "args": {}, "expect_success": True, "is_cleanup": True},
        ],
    }

    # Execute loop
    success = executor.execute_loop("test_loop", loop_config)

    # Verify only step1 and cleanup were called (step2 skipped)
    assert mock_tester.call_tool.call_count == 2

    # Verify output shows skipped step
    captured = capsys.readouterr()
    assert "SKIPPED - previous failure" in captured.out


def test_tool_loop_executor_expected_error_passes():
    """Verify expected errors are treated as success."""
    # Setup mock tester that returns error
    mock_tester = Mock()
    mock_tester.call_tool.return_value = {"content": [{"text": json.dumps({"error": "Expected error"})}]}

    env_vars = {}
    executor = ToolLoopExecutor(mock_tester, env_vars, verbose=False)

    loop_config = {
        "description": "Test loop",
        "steps": [
            {
                "tool": "test_tool",
                "args": {},
                "expect_success": False,  # Expect error
            }
        ],
    }

    # Execute loop
    success = executor.execute_loop("test_loop", loop_config)

    # Verify success (error was expected)
    assert success is True
    assert executor.results.passed == 1
    assert executor.results.failed == 0


def test_tool_loop_executor_verbose_output(capsys):
    """Verify verbose mode prints arguments."""
    mock_tester = Mock()
    mock_tester.call_tool.return_value = {"content": [{"text": json.dumps({"status": "success"})}]}

    env_vars = {}
    executor = ToolLoopExecutor(mock_tester, env_vars, verbose=True)

    loop_config = {
        "description": "Test loop",
        "steps": [{"tool": "test_tool", "args": {"test": "value"}, "expect_success": True}],
    }

    # Execute loop
    executor.execute_loop("test_loop", loop_config)

    # Verify arguments printed
    captured = capsys.readouterr()
    assert "Arguments:" in captured.out
    assert '"test": "value"' in captured.out


def test_tool_loop_executor_execute_all_loops():
    """Verify execute_all_loops processes multiple loops."""
    mock_tester = Mock()
    mock_tester.call_tool.return_value = {"content": [{"text": json.dumps({"status": "success"})}]}

    env_vars = {}
    executor = ToolLoopExecutor(mock_tester, env_vars, verbose=False)

    tool_loops = {
        "loop1": {"description": "Loop 1", "steps": [{"tool": "tool1", "args": {}}]},
        "loop2": {"description": "Loop 2", "steps": [{"tool": "tool2", "args": {}}]},
    }

    # Execute all loops
    results = executor.execute_all_loops(tool_loops)

    # Verify results
    assert results["total"] == 2
    assert results["passed"] == 2
    assert results["failed"] == 0


# ============================================================================
# Tool Loop Generation Tests
# ============================================================================


def test_get_test_roles(capsys):
    """Verify get_test_roles returns consistent role names."""
    base, secondary = get_test_roles()

    assert base == "ReadQuiltBucket"
    assert secondary == "ReadWriteQuiltBucket"
    assert base != secondary

    # Verify output
    captured = capsys.readouterr()
    assert "Using test roles" in captured.out


def test_generate_tool_loops_basic_structure():
    """Verify generate_tool_loops returns expected structure."""
    env_vars = {"QUILT_TEST_BUCKET": "test-bucket", "QUILT_TEST_PACKAGE": "test-pkg", "QUILT_TEST_ENTRY": "data.json"}
    base_role = "TestRole1"
    secondary_role = "TestRole2"

    loops = generate_tool_loops(env_vars, base_role, secondary_role)

    # Verify top-level structure
    assert isinstance(loops, dict)
    assert len(loops) > 0

    # Verify expected loops exist
    assert "admin_user_basic" in loops
    assert "package_lifecycle" in loops
    assert "workflow_basic" in loops


def test_generate_tool_loops_admin_user_basic():
    """Verify admin_user_basic loop structure."""
    env_vars = {"QUILT_TEST_BUCKET": "test-bucket"}
    loops = generate_tool_loops(env_vars, "Role1", "Role2")

    admin_loop = loops["admin_user_basic"]

    # Verify description
    assert "description" in admin_loop
    assert "create/get/delete" in admin_loop["description"]

    # Verify cleanup flag
    assert admin_loop["cleanup_on_failure"] is True

    # Verify steps
    steps = admin_loop["steps"]
    assert len(steps) == 3
    assert steps[0]["tool"] == "admin_user_create"
    assert steps[1]["tool"] == "admin_user_get"
    assert steps[2]["tool"] == "admin_user_delete"
    assert steps[2]["is_cleanup"] is True


def test_generate_tool_loops_package_lifecycle():
    """Verify package_lifecycle loop structure."""
    env_vars = {"QUILT_TEST_BUCKET": "test-bucket", "QUILT_TEST_PACKAGE": "test-pkg", "QUILT_TEST_ENTRY": "data.json"}
    loops = generate_tool_loops(env_vars, "Role1", "Role2")

    pkg_loop = loops["package_lifecycle"]

    # Verify description
    assert "package" in pkg_loop["description"].lower()

    # Verify steps
    steps = pkg_loop["steps"]
    assert len(steps) == 4
    assert steps[0]["tool"] == "package_create"
    assert steps[1]["tool"] == "package_browse"
    assert steps[2]["tool"] == "package_update"
    assert steps[3]["tool"] == "package_delete"
    assert steps[3]["is_cleanup"] is True


def test_generate_tool_loops_uses_template_variables():
    """Verify loops use {uuid} and {env.VAR} templates."""
    env_vars = {"QUILT_TEST_BUCKET": "test-bucket"}
    loops = generate_tool_loops(env_vars, "Role1", "Role2")

    # Check admin_user_basic for templates
    admin_loop = loops["admin_user_basic"]
    create_step = admin_loop["steps"][0]

    # Verify {uuid} template
    assert "{uuid}" in create_step["args"]["name"]
    assert "{uuid}" in create_step["args"]["email"]

    # Check package_lifecycle for {env.VAR} template
    pkg_loop = loops["package_lifecycle"]
    create_step = pkg_loop["steps"][0]

    assert "{env.QUILT_TEST_BUCKET}" in create_step["args"]["registry"]


def test_generate_tool_loops_all_loops_have_required_fields():
    """Verify all generated loops have required fields."""
    env_vars = {"QUILT_TEST_BUCKET": "test-bucket", "QUILT_TEST_PACKAGE": "pkg", "QUILT_TEST_ENTRY": "data.json"}
    loops = generate_tool_loops(env_vars, "Role1", "Role2")

    for loop_name, loop_config in loops.items():
        # Required fields
        assert "description" in loop_config, f"{loop_name} missing description"
        assert "cleanup_on_failure" in loop_config, f"{loop_name} missing cleanup_on_failure"
        assert "steps" in loop_config, f"{loop_name} missing steps"

        # Steps validation
        steps = loop_config["steps"]
        assert len(steps) > 0, f"{loop_name} has no steps"

        for i, step in enumerate(steps):
            assert "tool" in step, f"{loop_name} step {i} missing tool"
            assert "args" in step, f"{loop_name} step {i} missing args"


# ============================================================================
# Coverage Validation Tests
# ============================================================================


def test_validate_tool_loops_coverage_complete():
    """Verify validation passes when all write tools covered."""

    # Mock tools with effects
    def mock_handler():
        pass

    server_tools = {
        "tool_create": mock_handler,
        "tool_update": mock_handler,
        "tool_list": mock_handler,  # read-only, doesn't need coverage
    }

    # Mock classify_tool to return effects
    import quilt_mcp.testing.tool_loops as tool_loops_module

    original_classify = tool_loops_module.classify_tool

    def mock_classify(tool_name, handler):
        if "create" in tool_name:
            return ("create", "write-effect")
        elif "update" in tool_name:
            return ("update", "write-effect")
        else:
            return ("none", "zero-arg")

    tool_loops_module.classify_tool = mock_classify

    try:
        tool_loops = {"loop1": {"steps": [{"tool": "tool_create", "args": {}}, {"tool": "tool_update", "args": {}}]}}
        standalone_tools = {}

        # Should not raise
        validate_tool_loops_coverage(server_tools, tool_loops, standalone_tools)

    finally:
        tool_loops_module.classify_tool = original_classify


def test_validate_tool_loops_coverage_incomplete(capsys):
    """Verify validation warns about uncovered write tools."""

    # Mock tools with effects
    def mock_handler():
        pass

    server_tools = {"tool_create": mock_handler, "tool_update": mock_handler, "tool_remove": mock_handler}

    # Mock classify_tool
    import quilt_mcp.testing.tool_loops as tool_loops_module

    original_classify = tool_loops_module.classify_tool

    def mock_classify(tool_name, handler):
        if "create" in tool_name:
            return ("create", "write-effect")
        elif "update" in tool_name:
            return ("update", "write-effect")
        elif "remove" in tool_name:
            return ("remove", "write-effect")
        else:
            return ("none", "zero-arg")

    tool_loops_module.classify_tool = mock_classify

    try:
        tool_loops = {"loop1": {"steps": [{"tool": "tool_create", "args": {}}]}}
        standalone_tools = {"tool_update": {}}

        # Should print warning but not raise
        validate_tool_loops_coverage(server_tools, tool_loops, standalone_tools)

        # Verify warning printed
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "tool_remove" in captured.out
        assert "not covered" in captured.out

    finally:
        tool_loops_module.classify_tool = original_classify


def test_validate_tool_loops_coverage_no_write_tools():
    """Verify validation passes when no write tools exist."""

    def mock_handler():
        pass

    server_tools = {"tool_list": mock_handler, "tool_get": mock_handler}

    # Mock classify_tool
    import quilt_mcp.testing.tool_loops as tool_loops_module

    original_classify = tool_loops_module.classify_tool

    def mock_classify(tool_name, handler):
        return ("none", "zero-arg")

    tool_loops_module.classify_tool = mock_classify

    try:
        tool_loops = {}
        standalone_tools = {}

        # Should not raise or warn
        validate_tool_loops_coverage(server_tools, tool_loops, standalone_tools)

    finally:
        tool_loops_module.classify_tool = original_classify
