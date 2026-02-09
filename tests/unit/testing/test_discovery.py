"""Unit tests for discovery orchestration module.

Tests the DiscoveryOrchestrator class and metadata extraction functions
for MCP tool and resource discovery.
"""

import asyncio
import inspect
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from quilt_mcp.testing.discovery import (
    DiscoveryOrchestrator,
    extract_resource_metadata,
    extract_tool_metadata,
)
from quilt_mcp.testing.models import DiscoveredDataRegistry, DiscoveryResult


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_handler():
    """Create a mock tool handler."""
    handler = Mock()
    handler.fn = AsyncMock(return_value={"content": [{"data": "test"}]})
    return handler


@pytest.fixture
def sync_handler():
    """Create a synchronous mock handler."""
    handler = Mock()
    handler.fn = Mock(return_value={"content": [{"data": "test"}]})
    return handler


@pytest.fixture
def orchestrator():
    """Create a DiscoveryOrchestrator instance."""
    mock_server = Mock()
    return DiscoveryOrchestrator(server=mock_server, timeout=5.0, verbose=False, env_vars={"TEST_VAR": "test_value"})


# ============================================================================
# DiscoveryOrchestrator Tests
# ============================================================================


class TestDiscoveryOrchestratorInit:
    """Test DiscoveryOrchestrator initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        mock_server = Mock()
        orchestrator = DiscoveryOrchestrator(server=mock_server)

        assert orchestrator.server == mock_server
        assert orchestrator.timeout == 5.0
        assert orchestrator.verbose is True
        assert isinstance(orchestrator.registry, DiscoveredDataRegistry)
        assert orchestrator.results == {}
        assert orchestrator.env_vars == {}

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        mock_server = Mock()
        env_vars = {"KEY": "value"}
        orchestrator = DiscoveryOrchestrator(server=mock_server, timeout=10.0, verbose=False, env_vars=env_vars)

        assert orchestrator.timeout == 10.0
        assert orchestrator.verbose is False
        assert orchestrator.env_vars == env_vars


class TestDiscoverTool:
    """Test tool discovery execution."""

    @pytest.mark.asyncio
    async def test_discover_read_tool_success(self, orchestrator, mock_handler):
        """Test successful discovery of a read-only tool."""
        result = await orchestrator.discover_tool(
            tool_name="test_tool",
            handler=mock_handler,
            arguments={"arg": "value"},
            effect="none",
            category="required-arg",
        )

        assert result.status == "PASSED"
        assert result.tool_name == "test_tool"
        assert result.duration_ms > 0
        assert result.response == {"content": [{"data": "test"}]}
        assert result.error is None
        mock_handler.fn.assert_called_once_with(arg="value")

    @pytest.mark.asyncio
    async def test_discover_write_tool_skipped(self, orchestrator, mock_handler):
        """Test that write-effect tools are skipped during discovery."""
        result = await orchestrator.discover_tool(
            tool_name="test_create",
            handler=mock_handler,
            arguments={"name": "new_resource"},
            effect="create",
            category="write-effect",
        )

        assert result.status == "SKIPPED"
        assert result.tool_name == "test_create"
        assert result.duration_ms == 0
        assert "write operation" in result.error
        mock_handler.fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_discover_update_tool_skipped(self, orchestrator, mock_handler):
        """Test that update-effect tools are skipped."""
        result = await orchestrator.discover_tool(
            tool_name="test_update",
            handler=mock_handler,
            arguments={"id": "123"},
            effect="update",
            category="write-effect",
        )

        assert result.status == "SKIPPED"
        assert "update" in result.error.lower()

    @pytest.mark.asyncio
    async def test_discover_remove_tool_skipped(self, orchestrator, mock_handler):
        """Test that remove-effect tools are skipped."""
        result = await orchestrator.discover_tool(
            tool_name="test_remove",
            handler=mock_handler,
            arguments={"id": "123"},
            effect="remove",
            category="write-effect",
        )

        assert result.status == "SKIPPED"
        assert "remove" in result.error.lower()

    @pytest.mark.asyncio
    async def test_discover_tool_with_context_injection(self, orchestrator):
        """Test that RequestContext is injected for context-required tools."""

        # Create handler with context parameter
        async def handler_fn(arg: str, context):
            assert context is not None
            return {"result": "success"}

        handler = Mock()
        handler.fn = handler_fn

        result = await orchestrator.discover_tool(
            tool_name="test_tool",
            handler=handler,
            arguments={"arg": "value"},
            effect="none",
            category="context-required",
        )

        assert result.status == "PASSED"
        assert result.response == {"result": "success"}

    @pytest.mark.asyncio
    async def test_discover_tool_timeout(self, orchestrator):
        """Test timeout handling during discovery."""

        # Create handler that takes too long
        async def slow_handler():
            await asyncio.sleep(10)
            return {"data": "test"}

        handler = Mock()
        handler.fn = slow_handler

        result = await orchestrator.discover_tool(
            tool_name="slow_tool", handler=handler, arguments={}, effect="none", category="zero-arg"
        )

        assert result.status == "FAILED"
        assert result.error_category == "timeout"
        assert "Timeout after" in result.error

    @pytest.mark.asyncio
    async def test_discover_tool_exception(self, orchestrator, mock_handler):
        """Test exception handling during discovery."""
        mock_handler.fn.side_effect = ValueError("Invalid argument")

        result = await orchestrator.discover_tool(
            tool_name="failing_tool",
            handler=mock_handler,
            arguments={"arg": "bad"},
            effect="none",
            category="required-arg",
        )

        assert result.status == "FAILED"
        assert "Invalid argument" in result.error
        assert result.error_category in ["validation_error", "unknown"]

    @pytest.mark.asyncio
    async def test_discover_synchronous_tool(self, orchestrator, sync_handler):
        """Test discovery of synchronous tool functions."""
        result = await orchestrator.discover_tool(
            tool_name="sync_tool",
            handler=sync_handler,
            arguments={"arg": "value"},
            effect="none",
            category="required-arg",
        )

        assert result.status == "PASSED"
        assert result.response == {"content": [{"data": "test"}]}
        sync_handler.fn.assert_called_once_with(arg="value")

    @pytest.mark.asyncio
    async def test_discover_tool_with_pydantic_model_response(self, orchestrator):
        """Test discovery handles Pydantic model responses."""
        # Mock Pydantic model
        mock_response = Mock()
        mock_response.model_dump.return_value = {"field": "value"}

        async def handler_fn():
            return mock_response

        handler = Mock()
        handler.fn = handler_fn

        result = await orchestrator.discover_tool(
            tool_name="pydantic_tool", handler=handler, arguments={}, effect="none", category="zero-arg"
        )

        assert result.status == "PASSED"
        assert result.response == {"field": "value"}

    @pytest.mark.asyncio
    async def test_discover_tool_with_dict_method_response(self, orchestrator):
        """Test discovery handles responses with dict() method."""

        # Create a proper object with dict() method but no model_dump()
        class DictableObject:
            def dict(self):
                return {"data": "test"}

        async def handler_fn():
            return DictableObject()

        handler = Mock()
        handler.fn = handler_fn

        result = await orchestrator.discover_tool(
            tool_name="dict_tool", handler=handler, arguments={}, effect="none", category="zero-arg"
        )

        assert result.status == "PASSED"
        assert result.response == {"data": "test"}

    @pytest.mark.asyncio
    async def test_discover_tool_with_non_dict_response(self, orchestrator):
        """Test discovery handles non-dict responses."""

        async def handler_fn():
            return "plain string response"

        handler = Mock()
        handler.fn = handler_fn

        result = await orchestrator.discover_tool(
            tool_name="string_tool", handler=handler, arguments={}, effect="none", category="zero-arg"
        )

        assert result.status == "PASSED"
        assert result.response == {"content": ["plain string response"]}


class TestDataExtraction:
    """Test data extraction from tool responses."""

    def test_extract_s3_keys_from_bucket_objects_list(self, orchestrator):
        """Test S3 key extraction from bucket_objects_list response."""
        response = {
            "bucket": "test-bucket",
            "objects": [
                {"key": "file1.json", "s3_uri": "s3://test-bucket/file1.json"},
                {"key": "file2.csv", "s3_uri": "s3://test-bucket/file2.csv"},
            ],
        }

        discovered = orchestrator._extract_data("bucket_objects_list", response)

        assert "s3_keys" in discovered
        assert len(discovered["s3_keys"]) == 2
        assert "s3://test-bucket/file1.json" in discovered["s3_keys"]

    def test_extract_s3_keys_legacy_content_structure(self, orchestrator):
        """Test S3 key extraction from legacy content array."""
        response = {
            "content": [
                {"key": "old/path1.txt", "bucket": "legacy-bucket"},
                {"key": "old/path2.txt", "bucket": "legacy-bucket"},
            ]
        }

        discovered = orchestrator._extract_data("bucket_objects_list", response)

        assert "s3_keys" in discovered
        assert len(orchestrator.registry.s3_keys) == 2

    def test_extract_package_names_from_search(self, orchestrator):
        """Test package name extraction from search_catalog response."""
        response = {
            "content": [
                {"package_name": "package1", "version": "1.0.0"},
                {"name": "package2", "version": "2.0.0"},
                {"id": "package3"},
            ]
        }

        discovered = orchestrator._extract_data("search_catalog_packages", response)

        assert "package_names" in discovered
        assert len(discovered["package_names"]) == 3
        assert "package1" in orchestrator.registry.package_names

    def test_extract_tables_from_tables_list(self, orchestrator):
        """Test table extraction from tables_list response."""
        response = {
            "content": [
                {"name": "table1", "database": "db1", "columns": ["col1", "col2"]},
                {"name": "table2", "database": "db2"},
            ]
        }

        discovered = orchestrator._extract_data("athena_tables_list", response)

        assert "tables" in discovered
        assert len(discovered["tables"]) == 2
        assert orchestrator.registry.tables[0]["table"] == "table1"
        assert orchestrator.registry.tables[0]["database"] == "db1"

    def test_extract_schema_columns(self, orchestrator):
        """Test column extraction from schema responses."""
        response = {"content": [{"table": "test_table", "columns": ["id", "name", "email"]}]}

        discovered = orchestrator._extract_data("get_schema", response)

        assert "columns" in discovered
        assert discovered["columns"] == ["id", "name", "email"]

    def test_extract_data_handles_non_dict_response(self, orchestrator):
        """Test extraction handles non-dict responses gracefully."""
        discovered = orchestrator._extract_data("test_tool", "string response")

        assert discovered == {}

    def test_extract_data_handles_exceptions(self, orchestrator):
        """Test extraction handles exceptions gracefully."""
        response = {
            "objects": [
                {"broken": "data"}  # Missing required fields
            ]
        }

        # Should not raise, just return empty dict or partial data
        discovered = orchestrator._extract_data("bucket_objects_list", response)
        assert isinstance(discovered, dict)


class TestErrorCategorization:
    """Test error categorization logic."""

    def test_categorize_access_denied_errors(self, orchestrator):
        """Test categorization of access denied errors."""
        assert orchestrator._categorize_error("Access denied") == "access_denied"
        assert orchestrator._categorize_error("Permission denied") == "access_denied"
        assert orchestrator._categorize_error("Forbidden") == "access_denied"
        assert orchestrator._categorize_error("Unauthorized") == "access_denied"

    def test_categorize_timeout_errors(self, orchestrator):
        """Test categorization of timeout errors."""
        assert orchestrator._categorize_error("Connection timed out") == "timeout"
        assert orchestrator._categorize_error("Request timeout") == "timeout"

    def test_categorize_not_found_errors(self, orchestrator):
        """Test categorization of resource not found errors."""
        assert orchestrator._categorize_error("Resource not found") == "resource_not_found"
        assert orchestrator._categorize_error("Does not exist") == "resource_not_found"
        assert orchestrator._categorize_error("No such bucket") == "resource_not_found"

    def test_categorize_service_unavailable_errors(self, orchestrator):
        """Test categorization of service unavailable errors."""
        assert orchestrator._categorize_error("Service unavailable") == "service_unavailable"
        assert orchestrator._categorize_error("Connection refused") == "service_unavailable"
        assert orchestrator._categorize_error("Network error") == "service_unavailable"

    def test_categorize_validation_errors(self, orchestrator):
        """Test categorization of validation errors."""
        assert orchestrator._categorize_error("Invalid argument") == "validation_error"
        assert orchestrator._categorize_error("Validation failed") == "validation_error"
        assert orchestrator._categorize_error("Schema mismatch") == "validation_error"

    def test_categorize_unknown_errors(self, orchestrator):
        """Test categorization of unknown errors."""
        assert orchestrator._categorize_error("Something went wrong") == "unknown"
        assert orchestrator._categorize_error("Unexpected error") == "unknown"


class TestPrintSummary:
    """Test summary printing functionality."""

    def test_print_summary_with_results(self, orchestrator, capsys):
        """Test print_summary displays results correctly."""
        # Add test results
        orchestrator.results = {
            "tool1": DiscoveryResult(tool_name="tool1", status="PASSED", duration_ms=100.0),
            "tool2": DiscoveryResult(tool_name="tool2", status="FAILED", duration_ms=50.0, error="Test error"),
            "tool3": DiscoveryResult(tool_name="tool3", status="SKIPPED", duration_ms=0.0, error="Write operation"),
        }

        orchestrator.print_summary()
        captured = capsys.readouterr()

        assert "1 PASSED" in captured.out
        assert "1 FAILED" in captured.out
        assert "1 SKIPPED" in captured.out
        assert "tool2: Test error" in captured.out

    def test_print_summary_with_discovered_data(self, orchestrator, capsys):
        """Test print_summary displays discovered data."""
        orchestrator.registry.add_s3_keys(["s3://bucket/key1"])
        orchestrator.registry.add_package_names(["package1"])
        orchestrator.registry.add_tables([{"table": "table1", "database": "db1"}])

        orchestrator.print_summary()
        captured = capsys.readouterr()

        assert "Discovered Data" in captured.out
        assert "S3 keys" in captured.out
        assert "package names" in captured.out
        assert "tables" in captured.out


# ============================================================================
# Metadata Extraction Tests
# ============================================================================


class TestExtractToolMetadata:
    """Test tool metadata extraction."""

    @pytest.mark.asyncio
    async def test_extract_tool_metadata_success(self):
        """Test successful tool metadata extraction."""

        # Create mock server with tools
        def sample_tool(arg1: str, arg2: int = 42):
            """Sample tool for testing."""
            return {"result": "success"}

        handler = Mock()
        handler.fn = sample_tool
        handler.__class__.__name__ = "ToolHandler"

        mock_server = AsyncMock()
        mock_server.get_tools.return_value = {"sample_tool": handler}

        tools = await extract_tool_metadata(mock_server)

        assert len(tools) == 1
        tool = tools[0]
        assert tool["type"] == "tool"
        assert tool["name"] == "sample_tool"
        assert tool["description"] == "Sample tool for testing."
        assert "arg1: str" in tool["signature"]
        assert tool["is_async"] is False

    @pytest.mark.asyncio
    async def test_extract_async_tool_metadata(self):
        """Test extraction of async tool metadata."""

        async def async_tool():
            """Async tool for testing."""
            return {"result": "success"}

        handler = Mock()
        handler.fn = async_tool
        handler.__class__.__name__ = "AsyncHandler"

        mock_server = AsyncMock()
        mock_server.get_tools.return_value = {"async_tool": handler}

        tools = await extract_tool_metadata(mock_server)

        assert len(tools) == 1
        assert tools[0]["is_async"] is True

    @pytest.mark.asyncio
    async def test_extract_tool_metadata_missing_docstring(self):
        """Test error handling for tools without docstrings."""

        def no_doc_tool():
            return {"result": "success"}

        handler = Mock()
        handler.fn = no_doc_tool

        mock_server = AsyncMock()
        mock_server.get_tools.return_value = {"no_doc_tool": handler}

        with pytest.raises(ValueError, match="missing a docstring"):
            await extract_tool_metadata(mock_server)

    @pytest.mark.asyncio
    async def test_extract_multiple_tools_sorted(self):
        """Test extraction and sorting of multiple tools."""

        def tool_b():
            """Tool B."""
            pass

        def tool_a():
            """Tool A."""
            pass

        handler_a = Mock()
        handler_a.fn = tool_a
        handler_a.__class__.__name__ = "HandlerA"

        handler_b = Mock()
        handler_b.fn = tool_b
        handler_b.__class__.__name__ = "HandlerB"

        mock_server = AsyncMock()
        mock_server.get_tools.return_value = {"tool_b": handler_b, "tool_a": handler_a}

        tools = await extract_tool_metadata(mock_server)

        # Should be sorted by module then name
        assert len(tools) == 2
        # Tools should be in alphabetical order by name within same module
        assert tools[0]["name"] <= tools[1]["name"]


class TestExtractResourceMetadata:
    """Test resource metadata extraction."""

    @pytest.mark.asyncio
    async def test_extract_static_resource_metadata(self):
        """Test extraction of static resource metadata."""
        mock_resource = Mock()
        mock_resource.name = "test-resource"
        mock_resource.description = "Test resource description"

        mock_server = AsyncMock()
        mock_server.get_resources.return_value = {"quilt://bucket/package": mock_resource}
        mock_server.get_resource_templates.return_value = {}

        resources = await extract_resource_metadata(mock_server)

        assert len(resources) == 1
        resource = resources[0]
        assert resource["type"] == "resource"
        assert resource["name"] == "quilt://bucket/package"
        assert resource["description"] == "Test resource description"
        assert resource["is_async"] is True
        assert resource["handler_class"] == "FastMCP Resource"

    @pytest.mark.asyncio
    async def test_extract_resource_template_metadata(self):
        """Test extraction of resource template metadata."""
        mock_template = Mock()
        mock_template.name = "template-resource"
        mock_template.description = "Template description"

        mock_server = AsyncMock()
        mock_server.get_resources.return_value = {}
        mock_server.get_resource_templates.return_value = {"quilt://{bucket}/{package}": mock_template}

        resources = await extract_resource_metadata(mock_server)

        assert len(resources) == 1
        resource = resources[0]
        assert resource["name"] == "quilt://{bucket}/{package}"
        assert resource["handler_class"] == "FastMCP Template"

    @pytest.mark.asyncio
    async def test_extract_resource_missing_name(self):
        """Test error handling for resources without names."""
        mock_resource = Mock()
        mock_resource.name = None
        mock_resource.description = "Test description"

        mock_server = AsyncMock()
        mock_server.get_resources.return_value = {"quilt://test": mock_resource}
        mock_server.get_resource_templates.return_value = {}

        with pytest.raises(ValueError, match="missing a name"):
            await extract_resource_metadata(mock_server)

    @pytest.mark.asyncio
    async def test_extract_resource_missing_description(self):
        """Test error handling for resources without descriptions."""
        mock_resource = Mock()
        mock_resource.name = "test-resource"
        mock_resource.description = None

        mock_server = AsyncMock()
        mock_server.get_resources.return_value = {"quilt://test": mock_resource}
        mock_server.get_resource_templates.return_value = {}

        with pytest.raises(ValueError, match="missing a description"):
            await extract_resource_metadata(mock_server)

    @pytest.mark.asyncio
    async def test_extract_mixed_resources_sorted(self):
        """Test extraction of mixed static and template resources with sorting."""
        resource1 = Mock()
        resource1.name = "resource-b"
        resource1.description = "Resource B"

        resource2 = Mock()
        resource2.name = "resource-a"
        resource2.description = "Resource A"

        template1 = Mock()
        template1.name = "template-z"
        template1.description = "Template Z"

        mock_server = AsyncMock()
        mock_server.get_resources.return_value = {"uri://b": resource1, "uri://a": resource2}
        mock_server.get_resource_templates.return_value = {"uri://{z}": template1}

        resources = await extract_resource_metadata(mock_server)

        assert len(resources) == 3
        # Should be sorted by name (URI)
        names = [r["name"] for r in resources]
        assert names == sorted(names)


# ============================================================================
# Integration Tests
# ============================================================================


class TestDiscoveryIntegration:
    """Integration tests for discovery workflow."""

    @pytest.mark.asyncio
    async def test_full_discovery_workflow(self):
        """Test complete discovery workflow with multiple tools."""

        # Create mock tools
        async def list_tool():
            """List all items."""
            return {"objects": [{"key": "file1.json", "s3_uri": "s3://bucket/file1.json"}]}

        async def search_tool(query: str):
            """Search catalog."""
            return {"content": [{"package_name": "test-package"}]}

        list_handler = Mock()
        list_handler.fn = list_tool

        search_handler = Mock()
        search_handler.fn = search_tool

        mock_server = Mock()
        orchestrator = DiscoveryOrchestrator(server=mock_server, timeout=5.0, verbose=False)

        # Discover tools
        result1 = await orchestrator.discover_tool("bucket_objects_list", list_handler, {}, "none")

        result2 = await orchestrator.discover_tool(
            "search_catalog_packages", search_handler, {"query": "test"}, "none"
        )

        # Verify results
        assert result1.status == "PASSED"
        assert result2.status == "PASSED"
        assert len(orchestrator.registry.s3_keys) == 1
        assert len(orchestrator.registry.package_names) == 1

    @pytest.mark.asyncio
    async def test_discovery_with_errors_continues(self):
        """Test that discovery continues after individual tool errors."""

        async def good_tool():
            """Working tool."""
            return {"data": "success"}

        async def bad_tool():
            """Failing tool."""
            raise ValueError("Tool error")

        good_handler = Mock()
        good_handler.fn = good_tool

        bad_handler = Mock()
        bad_handler.fn = bad_tool

        mock_server = Mock()
        orchestrator = DiscoveryOrchestrator(server=mock_server, verbose=False)

        result1 = await orchestrator.discover_tool("good_tool", good_handler, {}, "none")

        result2 = await orchestrator.discover_tool("bad_tool", bad_handler, {}, "none")

        # Good tool should succeed
        assert result1.status == "PASSED"
        # Bad tool should fail but not crash
        assert result2.status == "FAILED"
        assert "Tool error" in result2.error
