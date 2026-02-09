"""Unit tests for tool classification and argument inference.

Tests the core classification logic that drives test generation,
coverage analysis, and tool loop orchestration.
"""

import inspect
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest

from quilt_mcp.context.request_context import RequestContext
from quilt_mcp.testing.tool_classifier import (
    classify_tool,
    create_mock_context,
    get_user_athena_database,
    infer_arguments,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_handler():
    """Create a mock handler with configurable signature."""

    def make_handler(fn):
        handler = Mock()
        handler.fn = fn
        return handler

    return make_handler


@pytest.fixture
def test_env_vars() -> Dict[str, str]:
    """Standard test environment variables."""
    return {
        "QUILT_TEST_BUCKET": "s3://test-bucket",
        "QUILT_CATALOG_URL": "https://test.quiltdata.com",
        "QUILT_TEST_PACKAGE": "test/package",
        "QUILT_TEST_ENTRY": ".test-file.json",
    }


@pytest.fixture
def discovered_data() -> Dict[str, Any]:
    """Sample discovered data from test runs."""
    return {
        "s3_keys": ["s3://test-bucket/data/file1.json", "s3://test-bucket/data/file2.csv"],
        "package_names": ["test/package1", "test/package2"],
        "tables": [{"name": "table1", "database": "test_db"}, {"name": "table2", "database": "test_db"}],
    }


# ============================================================================
# Tests: create_mock_context()
# ============================================================================


def test_create_mock_context_returns_valid_context():
    """Create_mock_context should return a properly configured RequestContext."""
    ctx = create_mock_context()

    assert isinstance(ctx, RequestContext)
    assert ctx.request_id == "test-request-mcp-test-setup"
    assert ctx.user_id == "test-user-mcp-test-setup"
    assert ctx.auth_service is not None
    assert ctx.permission_service is not None


def test_create_mock_context_has_working_auth_service():
    """Mock auth service should return valid responses."""
    ctx = create_mock_context()

    assert ctx.auth_service.is_valid() is True
    assert ctx.auth_service.get_boto3_session() is None


def test_create_mock_context_has_working_permission_service():
    """Mock permission service should return valid responses."""
    ctx = create_mock_context()

    permissions = ctx.permission_service.discover_permissions()
    assert permissions == {"buckets": []}

    access = ctx.permission_service.check_bucket_access()
    assert access == {"accessible": True}


# ============================================================================
# Tests: classify_tool() - Effect Classification
# ============================================================================


def test_classify_tool_detects_create_effect(mock_handler):
    """Tools with 'create' in name should be classified as create effect."""

    def package_create(bucket: str):
        pass

    handler = mock_handler(package_create)
    effect, category = classify_tool("package_create", handler)

    assert effect == "create"
    assert category == "write-effect"


def test_classify_tool_detects_remove_effect(mock_handler):
    """Tools with 'delete'/'remove' in name should be classified as remove effect."""

    def package_delete(package: str):
        pass

    handler = mock_handler(package_delete)
    effect, category = classify_tool("package_delete", handler)

    assert effect == "remove"
    assert category == "write-effect"


def test_classify_tool_detects_update_effect(mock_handler):
    """Tools with 'update' in name should be classified as update effect."""

    def package_update(package: str, metadata: dict):
        pass

    handler = mock_handler(package_update)
    effect, category = classify_tool("package_update", handler)

    assert effect == "update"
    assert category == "write-effect"


def test_classify_tool_detects_configure_effect(mock_handler):
    """Tools with 'configure'/'toggle' in name should be classified as configure effect."""

    def bucket_configure(bucket: str, settings: dict):
        pass

    handler = mock_handler(bucket_configure)
    effect, category = classify_tool("bucket_configure", handler)

    assert effect == "configure"


def test_classify_tool_detects_none_effect_for_read_only(mock_handler):
    """Read-only tools should have 'none' effect."""

    def bucket_list():
        pass

    handler = mock_handler(bucket_list)
    effect, category = classify_tool("bucket_list", handler)

    assert effect == "none"
    assert category == "zero-arg"


def test_classify_tool_detects_none_context_required(mock_handler):
    """Read-only tools with context parameter should have 'none-context-required' effect."""

    def bucket_access_check(context: RequestContext):
        pass

    handler = mock_handler(bucket_access_check)
    effect, category = classify_tool("bucket_access_check", handler)

    assert effect == "none-context-required"
    assert category == "context-required"


# ============================================================================
# Tests: classify_tool() - Category Classification
# ============================================================================


def test_classify_tool_detects_zero_arg_category(mock_handler):
    """Tools with no required args should be zero-arg category."""

    def bucket_list():
        pass

    handler = mock_handler(bucket_list)
    effect, category = classify_tool("bucket_list", handler)

    assert category == "zero-arg"


def test_classify_tool_detects_required_arg_category(mock_handler):
    """Tools with only required args should be required-arg category."""

    def bucket_info(bucket: str):
        pass

    handler = mock_handler(bucket_info)
    effect, category = classify_tool("bucket_info", handler)

    assert category == "required-arg"


def test_classify_tool_detects_optional_arg_category(mock_handler):
    """Tools with mix of required and optional args should be optional-arg category."""

    def package_list(bucket: str, limit: int = 10):
        pass

    handler = mock_handler(package_list)
    effect, category = classify_tool("package_list", handler)

    assert category == "optional-arg"


def test_classify_tool_detects_write_effect_category(mock_handler):
    """Tools with create/update/remove effect should be write-effect category."""

    def package_create(bucket: str, name: str):
        pass

    handler = mock_handler(package_create)
    effect, category = classify_tool("package_create", handler)

    assert category == "write-effect"


def test_classify_tool_detects_context_required_category(mock_handler):
    """Tools requiring RequestContext should be context-required category."""

    def bucket_access_check(context: RequestContext, bucket: str = "test"):
        pass

    handler = mock_handler(bucket_access_check)
    effect, category = classify_tool("bucket_access_check", handler)

    assert category == "context-required"


def test_classify_tool_ignores_context_in_required_args(mock_handler):
    """Context parameter should not count as required arg for category."""

    def tool_with_context(context: RequestContext):
        pass

    handler = mock_handler(tool_with_context)
    effect, category = classify_tool("tool_with_context", handler)

    # Should be context-required, not required-arg
    assert category == "context-required"


# ============================================================================
# Tests: classify_tool() - Edge Cases
# ============================================================================


def test_classify_tool_handles_multiple_effect_keywords(mock_handler):
    """Tool names with multiple effect keywords should use first match."""

    def package_create_or_update(bucket: str):
        pass

    handler = mock_handler(package_create_or_update)
    effect, category = classify_tool("package_create_or_update", handler)

    # 'create' appears first in keyword check order
    assert effect == "create"


def test_classify_tool_is_case_insensitive(mock_handler):
    """Classification should work regardless of name casing."""

    def PackageCreate(bucket: str):
        pass

    handler = mock_handler(PackageCreate)
    effect, category = classify_tool("PackageCreate", handler)

    assert effect == "create"


# ============================================================================
# Tests: infer_arguments() - Bucket Parameters
# ============================================================================


def test_infer_arguments_handles_bucket_parameter(mock_handler, test_env_vars):
    """Bucket parameter should be inferred from TEST_BUCKET env var."""

    def bucket_info(bucket: str):
        pass

    handler = mock_handler(bucket_info)
    args = infer_arguments("bucket_info", handler, test_env_vars)

    assert "bucket" in args
    assert args["bucket"] == "test-bucket"  # Just the bucket name


def test_infer_arguments_handles_bucket_name_parameter(mock_handler, test_env_vars):
    """Bucket_name parameter should use just bucket name, not full URI."""

    def bucket_info(bucket_name: str):
        pass

    handler = mock_handler(bucket_info)
    args = infer_arguments("bucket_info", handler, test_env_vars)

    assert "bucket_name" in args
    assert args["bucket_name"] == "test-bucket"


def test_infer_arguments_handles_full_bucket_uri(mock_handler, test_env_vars):
    """Parameters like 'test_bucket' should get full s3:// URI."""

    def tool(test_bucket: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "test_bucket" in args
    assert args["test_bucket"] == "s3://test-bucket"


# ============================================================================
# Tests: infer_arguments() - Package Parameters
# ============================================================================


def test_infer_arguments_handles_package_parameter(mock_handler, test_env_vars):
    """Package parameter should be inferred from TEST_PACKAGE env var."""

    def package_info(package: str):
        pass

    handler = mock_handler(package_info)
    args = infer_arguments("package_info", handler, test_env_vars)

    assert "package" in args
    assert args["package"] == "test/package"


def test_infer_arguments_handles_package_name_parameter(mock_handler, test_env_vars):
    """Package_name parameter should use TEST_PACKAGE value."""

    def package_info(package_name: str):
        pass

    handler = mock_handler(package_info)
    args = infer_arguments("package_info", handler, test_env_vars)

    assert "package_name" in args
    assert args["package_name"] == "test/package"


# ============================================================================
# Tests: infer_arguments() - S3 URI and Path Parameters
# ============================================================================


def test_infer_arguments_handles_s3_uri_with_discovered_data(mock_handler, test_env_vars, discovered_data):
    """S3_uri should prefer discovered S3 keys when available."""

    def bucket_object_text(s3_uri: str):
        pass

    handler = mock_handler(bucket_object_text)
    args = infer_arguments("bucket_object_text", handler, test_env_vars, discovered_data)

    assert "s3_uri" in args
    assert args["s3_uri"] == "s3://test-bucket/data/file1.json"


def test_infer_arguments_handles_s3_uri_without_discovered_data(mock_handler, test_env_vars):
    """S3_uri should fall back to constructed path when no discovered data."""

    def bucket_object_text(s3_uri: str):
        pass

    handler = mock_handler(bucket_object_text)
    args = infer_arguments("bucket_object_text", handler, test_env_vars)

    assert "s3_uri" in args
    assert args["s3_uri"] == "s3://test-bucket/test/package/.test-file.json"


def test_infer_arguments_handles_path_parameter(mock_handler, test_env_vars):
    """Path parameter should use TEST_ENTRY value."""

    def tool(path: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "path" in args
    assert args["path"] == ".test-file.json"


def test_infer_arguments_handles_logical_key_parameter(mock_handler, test_env_vars):
    """Logical_key parameter should use TEST_ENTRY value."""

    def tool(logical_key: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "logical_key" in args
    assert args["logical_key"] == ".test-file.json"


# ============================================================================
# Tests: infer_arguments() - Query Parameters
# ============================================================================


def test_infer_arguments_handles_athena_query(mock_handler, test_env_vars):
    """Query parameter for athena tools should get SQL query."""

    def search_athena(query: str):
        pass

    handler = mock_handler(search_athena)
    args = infer_arguments("search_athena", handler, test_env_vars)

    assert "query" in args
    assert args["query"] == "SELECT 1 as test_value"


def test_infer_arguments_handles_tabulator_query(mock_handler, test_env_vars):
    """Query parameter for tabulator tools should get SQL query."""

    def tabulator_query(query: str):
        pass

    handler = mock_handler(tabulator_query)
    args = infer_arguments("tabulator_query", handler, test_env_vars)

    assert "query" in args
    assert args["query"] == "SELECT 1 as test_value"


def test_infer_arguments_handles_non_sql_query(mock_handler, test_env_vars):
    """Query parameter for non-SQL tools should use test entry."""

    def search_simple(query: str):
        pass

    handler = mock_handler(search_simple)
    args = infer_arguments("search_simple", handler, test_env_vars)

    assert "query" in args
    assert args["query"] == ".test-file.json"


# ============================================================================
# Tests: infer_arguments() - Database/Table Parameters
# ============================================================================


def test_infer_arguments_handles_database_parameter(mock_handler, test_env_vars):
    """Database parameter should use provided athena_database."""

    def tool(database: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars, athena_database="my_test_db")

    assert "database" in args
    assert args["database"] == "my_test_db"


def test_infer_arguments_handles_database_without_athena_db(mock_handler, test_env_vars):
    """Database parameter should default to 'default' when athena_database not provided."""

    def tool(database: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "database" in args
    assert args["database"] == "default"


def test_infer_arguments_handles_table_parameter(mock_handler, test_env_vars):
    """Table parameter should use generic test table name."""

    def tool(table: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "table" in args
    assert args["table"] == "test_table"


# ============================================================================
# Tests: infer_arguments() - Catalog Parameters
# ============================================================================


def test_infer_arguments_handles_catalog_url_parameter(mock_handler, test_env_vars):
    """Catalog_url parameter should use test bucket."""

    def tool(catalog_url: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "catalog_url" in args
    assert args["catalog_url"] == "s3://test-bucket"


def test_infer_arguments_handles_registry_parameter(mock_handler, test_env_vars):
    """Registry parameter should use test bucket."""

    def tool(registry: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "registry" in args
    assert args["registry"] == "s3://test-bucket"


# ============================================================================
# Tests: infer_arguments() - Limit Parameters
# ============================================================================


def test_infer_arguments_handles_limit_parameter(mock_handler, test_env_vars):
    """Limit parameter should default to 10."""

    def tool(limit: int):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "limit" in args
    assert args["limit"] == 10


def test_infer_arguments_handles_max_results_parameter(mock_handler, test_env_vars):
    """Max_results parameter should default to 10."""

    def tool(max_results: int):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "max_results" in args
    assert args["max_results"] == 10


# ============================================================================
# Tests: infer_arguments() - Visualization Parameters
# ============================================================================


def test_infer_arguments_handles_visualization_structure(mock_handler, test_env_vars):
    """Organized_structure parameter should get sample file data."""

    def tool(organized_structure: dict):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "organized_structure" in args
    assert "files" in args["organized_structure"]
    assert args["organized_structure"]["files"][0]["name"] == "test.txt"


def test_infer_arguments_handles_file_types(mock_handler, test_env_vars):
    """File_types parameter should get sample type mapping."""

    def tool(file_types: dict):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "file_types" in args
    assert args["file_types"] == {"txt": 1}


def test_infer_arguments_handles_package_metadata(mock_handler, test_env_vars):
    """Package_metadata parameter gets matched by 'package' keyword first.

    Note: Due to the order of if/elif checks, 'package_metadata' matches
    the generic 'package' check before reaching the specific metadata logic.
    This is preserved from the original script behavior.
    """

    def tool(package_metadata: dict):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "package_metadata" in args
    # package_metadata gets special handling to return a dictionary structure
    assert isinstance(args["package_metadata"], dict)
    assert args["package_metadata"]["name"] == "test/package"
    assert "description" in args["package_metadata"]


def test_infer_arguments_handles_plot_data(mock_handler, test_env_vars):
    """Data parameter should get sample plot data."""

    def tool(data: dict):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "data" in args
    assert "x" in args["data"]
    assert "y" in args["data"]


def test_infer_arguments_handles_plot_type(mock_handler, test_env_vars):
    """Plot_type parameter should default to scatter."""

    def tool(plot_type: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "plot_type" in args
    assert args["plot_type"] == "scatter"


# ============================================================================
# Tests: infer_arguments() - Type-based Inference
# ============================================================================


def test_infer_arguments_handles_bool_parameters(mock_handler, test_env_vars):
    """Boolean parameters should infer True for positive keywords."""

    def tool(include_metadata: bool, exclude_large: bool):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "include_metadata" in args
    assert args["include_metadata"] is True  # 'include' keyword

    assert "exclude_large" in args
    assert args["exclude_large"] is False  # 'exclude' not in positive keywords


def test_infer_arguments_handles_int_parameters(mock_handler, test_env_vars):
    """Integer parameters should default to 10."""

    def tool(count: int):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "count" in args
    assert args["count"] == 10


def test_infer_arguments_handles_str_parameters_with_name(mock_handler, test_env_vars):
    """String parameters with 'name' should get test_name."""

    def tool(user_name: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "user_name" in args
    assert args["user_name"] == "test_name"


def test_infer_arguments_handles_str_parameters_generic(mock_handler, test_env_vars):
    """Generic string parameters should get test_value."""

    def tool(description: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "description" in args
    assert args["description"] == "test_value"


# ============================================================================
# Tests: infer_arguments() - Edge Cases
# ============================================================================


def test_infer_arguments_skips_context_parameter(mock_handler, test_env_vars):
    """Context parameter should not be included in inferred arguments."""

    def tool(context: RequestContext, bucket: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "context" not in args
    assert "bucket" in args


def test_infer_arguments_skips_optional_parameters(mock_handler, test_env_vars):
    """Parameters with defaults should not be inferred."""

    def tool(bucket: str, limit: int = 10):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars)

    assert "bucket" in args
    assert "limit" not in args  # Has default, so skipped


def test_infer_arguments_handles_empty_discovered_data(mock_handler, test_env_vars):
    """Empty discovered data should not break inference."""

    def tool(s3_uri: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars, discovered_data={})

    assert "s3_uri" in args
    # Should fall back to constructed path
    assert args["s3_uri"].startswith("s3://test-bucket")


def test_infer_arguments_handles_none_discovered_data(mock_handler, test_env_vars):
    """None discovered data should not break inference."""

    def tool(s3_uri: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, test_env_vars, discovered_data=None)

    assert "s3_uri" in args


def test_infer_arguments_handles_minimal_env_vars(mock_handler):
    """Should work with minimal environment variables (use defaults)."""

    def tool(bucket: str):
        pass

    handler = mock_handler(tool)
    args = infer_arguments("tool", handler, {})

    assert "bucket" in args
    # Should use default value
    assert args["bucket"] == "quilt-example"


# ============================================================================
# Tests: get_user_athena_database()
# ============================================================================


@patch('quilt_mcp.testing.tool_classifier.find_matching_stack')
@patch('quilt_mcp.testing.tool_classifier.stack_outputs')
def test_get_user_athena_database_returns_db_name(mock_stack_outputs, mock_find_stack):
    """Should extract UserAthenaDatabaseName from stack outputs."""
    mock_find_stack.return_value = "mock-stack"
    mock_stack_outputs.return_value = [
        {"OutputKey": "BucketName", "OutputValue": "test-bucket"},
        {"OutputKey": "UserAthenaDatabaseName", "OutputValue": "quilt_test_athena_db"},
        {"OutputKey": "CatalogUrl", "OutputValue": "https://test.example.com"},
    ]

    db_name = get_user_athena_database("https://test.example.com")

    assert db_name == "quilt_test_athena_db"
    mock_find_stack.assert_called_once_with("https://test.example.com")


@patch('quilt_mcp.testing.tool_classifier.find_matching_stack')
@patch('quilt_mcp.testing.tool_classifier.stack_outputs')
def test_get_user_athena_database_returns_default_when_not_found(mock_stack_outputs, mock_find_stack):
    """Should return 'default' when UserAthenaDatabaseName not in outputs."""
    mock_find_stack.return_value = "mock-stack"
    mock_stack_outputs.return_value = [
        {"OutputKey": "BucketName", "OutputValue": "test-bucket"},
    ]

    db_name = get_user_athena_database("https://test.example.com")

    assert db_name == "default"


@patch('quilt_mcp.testing.tool_classifier.find_matching_stack')
def test_get_user_athena_database_handles_stack_not_found(mock_find_stack):
    """Should return 'default' and not raise when stack not found."""
    mock_find_stack.side_effect = Exception("Stack not found")

    db_name = get_user_athena_database("https://test.example.com")

    assert db_name == "default"


@patch('quilt_mcp.testing.tool_classifier.find_matching_stack')
@patch('quilt_mcp.testing.tool_classifier.stack_outputs')
def test_get_user_athena_database_handles_empty_output_value(mock_stack_outputs, mock_find_stack):
    """Should return 'default' when output value is empty."""
    mock_find_stack.return_value = "mock-stack"
    mock_stack_outputs.return_value = [
        {"OutputKey": "UserAthenaDatabaseName", "OutputValue": ""},
    ]

    db_name = get_user_athena_database("https://test.example.com")

    assert db_name == "default"


@patch('quilt_mcp.testing.tool_classifier.find_matching_stack')
@patch('quilt_mcp.testing.tool_classifier.stack_outputs')
def test_get_user_athena_database_handles_none_output_value(mock_stack_outputs, mock_find_stack):
    """Should return 'default' when output value is None."""
    mock_find_stack.return_value = "mock-stack"
    mock_stack_outputs.return_value = [
        {"OutputKey": "UserAthenaDatabaseName", "OutputValue": None},
    ]

    db_name = get_user_athena_database("https://test.example.com")

    assert db_name == "default"


# ============================================================================
# Integration Tests
# ============================================================================


def test_classify_and_infer_work_together(mock_handler, test_env_vars):
    """Classification and inference should work together for typical tool."""

    def package_create(bucket: str, name: str, metadata: dict = None):
        pass

    handler = mock_handler(package_create)

    # Classify the tool
    effect, category = classify_tool("package_create", handler)
    assert effect == "create"
    assert category == "write-effect"

    # Infer arguments
    args = infer_arguments("package_create", handler, test_env_vars)
    assert "bucket" in args
    assert "name" in args
    assert "metadata" not in args  # Has default, so skipped


def test_context_required_tool_workflow(mock_handler, test_env_vars):
    """Context-required tools should classify correctly and infer non-context args."""

    def bucket_access_check(context: RequestContext, bucket: str):
        pass

    handler = mock_handler(bucket_access_check)

    # Should classify as context-required
    effect, category = classify_tool("bucket_access_check", handler)
    assert effect == "none-context-required"
    assert category == "context-required"

    # Should infer bucket but not context
    args = infer_arguments("bucket_access_check", handler, test_env_vars)
    assert "bucket" in args
    assert "context" not in args

    # Can create mock context separately
    ctx = create_mock_context()
    assert isinstance(ctx, RequestContext)
