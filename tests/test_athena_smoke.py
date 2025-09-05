#!/usr/bin/env python3
"""
Smoke tests for Athena MCP tools integration

These tests verify that the Athena tools are properly integrated
into the MCP server without requiring actual AWS resources.
"""

import pytest
from unittest.mock import Mock, patch
from quilt_mcp.tools.athena_glue import athena_databases_list, athena_query_execute, athena_query_validate


def test_athena_tools_basic_functionality():
    """Smoke test that Athena tools can be imported and called."""
    # Test query validation (no AWS required)
    result = athena_query_validate("SELECT * FROM test_table")
    assert isinstance(result, dict)
    assert 'success' in result
    assert 'valid' in result

    # Test dangerous query detection
    result = athena_query_validate("DROP TABLE test_table")
    assert result['success'] is False
    assert result['valid'] is False
    assert 'dangerous' in result['error']


@patch('quilt_mcp.tools.athena_glue.AthenaQueryService')
def test_athena_database_listing_smoke(mock_service_class):
    """Smoke test for database listing."""
    mock_service = Mock()
    mock_service_class.return_value = mock_service
    mock_service.discover_databases.return_value = {'success': True, 'databases': [{'name': 'test_db'}], 'count': 1}

    result = athena_databases_list()
    assert result['success'] is True
    assert len(result['databases']) == 1


@patch('quilt_mcp.tools.athena_glue.AthenaQueryService')
def test_athena_query_execution_smoke(mock_service_class):
    """Smoke test for query execution."""
    mock_service = Mock()
    mock_service_class.return_value = mock_service

    # Mock successful query execution
    mock_service.execute_query.return_value = {
        'success': True,
        'row_count': 1,
        'columns': ['test_col'],
        'truncated': False,
    }

    mock_service.format_results.return_value = {
        'success': True,
        'formatted_data': [{'test_col': 'test_value'}],
        'format': 'json',
    }

    result = athena_query_execute("SELECT 1 as test_col")
    assert result['success'] is True
    assert 'formatted_data' in result


def test_athena_tools_error_handling():
    """Test error handling in Athena tools."""
    # Test empty query
    result = athena_query_execute("")
    assert result['success'] is False
    assert 'empty' in result['error'].lower()

    # Test invalid max_results
    result = athena_query_execute("SELECT 1", max_results=0)
    assert result['success'] is False

    # Test invalid output format
    result = athena_query_execute("SELECT 1", output_format="invalid")
    assert result['success'] is False


def test_mcp_tool_registration():
    """Test that Athena tools are properly registered in MCP server."""
    from quilt_mcp.utils import get_tool_modules

    tool_modules = get_tool_modules()

    # Check that athena_glue module is included
    module_names = [module.__name__.split('.')[-1] for module in tool_modules]
    assert 'athena_glue' in module_names

    # Check that we can find the athena_glue module
    athena_module = None
    for module in tool_modules:
        if module.__name__.endswith('athena_glue'):
            athena_module = module
            break

    assert athena_module is not None

    # Check that the module has the expected functions
    import inspect

    functions = [
        name for name, obj in inspect.getmembers(athena_module, inspect.isfunction) if not name.startswith('_')
    ]

    expected_functions = [
        'athena_databases_list',
        'athena_tables_list',
        'athena_table_schema',
        'athena_query_execute',
        'athena_query_history',
        'athena_workgroups_list',
        'athena_query_validate',
    ]

    for func_name in expected_functions:
        assert func_name in functions, f"Function {func_name} not found in athena_glue module"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
