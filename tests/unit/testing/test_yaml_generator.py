"""Unit tests for yaml_generator module.

This test suite validates the YAML test configuration generation functions,
including CSV output, JSON output, and the main generate_test_yaml function.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from quilt_mcp.testing.yaml_generator import (
    generate_csv_output,
    generate_json_output,
    generate_test_yaml,
)


class TestGenerateCSVOutput:
    """Test CSV output generation."""

    def test_generates_valid_csv_with_headers(self, tmp_path):
        """Verify CSV contains proper headers and data rows."""
        items = [
            {
                "type": "tool",
                "module": "quilt_mcp.tools.buckets",
                "name": "bucket_list",
                "signature": "bucket_list() -> list",
                "description": "List all S3 buckets",
                "is_async": True,
                "full_module_path": "quilt_mcp.tools.buckets.bucket_list",
            },
            {
                "type": "resource",
                "module": "quilt_mcp.tools.resources",
                "name": "package_metadata",
                "signature": "package_metadata(uri: str)",
                "description": "Get package metadata",
                "is_async": False,
                "full_module_path": "quilt_mcp.tools.resources.package_metadata",
            },
        ]

        output_file = tmp_path / "output.csv"
        generate_csv_output(items, str(output_file))

        # Verify file exists and is readable
        assert output_file.exists()
        content = output_file.read_text()

        # Verify headers
        assert "type,module,function_name,signature,description,is_async,full_module_path" in content

        # Verify data rows
        assert "tool,quilt_mcp.tools.buckets,bucket_list" in content
        assert "resource,quilt_mcp.tools.resources,package_metadata" in content

    def test_handles_empty_items_list(self, tmp_path):
        """Verify CSV generation works with empty items list."""
        output_file = tmp_path / "empty.csv"
        generate_csv_output([], str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        # Should still have headers
        assert "type,module,function_name" in content

    def test_handles_special_characters_in_descriptions(self, tmp_path):
        """Verify CSV properly escapes special characters."""
        items = [
            {
                "type": "tool",
                "module": "test",
                "name": "test_tool",
                "signature": "test()",
                "description": 'Tool with "quotes" and, commas',
                "is_async": False,
                "full_module_path": "test.test_tool",
            }
        ]

        output_file = tmp_path / "special.csv"
        generate_csv_output(items, str(output_file))

        content = output_file.read_text()
        # CSV should handle quotes and commas properly
        assert "test_tool" in content


class TestGenerateJSONOutput:
    """Test JSON output generation."""

    def test_generates_valid_json_structure(self, tmp_path):
        """Verify JSON contains expected structure with metadata and items."""
        items = [
            {
                "type": "tool",
                "module": "quilt_mcp.tools.buckets",
                "name": "bucket_list",
                "signature": "bucket_list() -> list",
                "description": "List all S3 buckets",
                "is_async": True,
                "full_module_path": "quilt_mcp.tools.buckets.bucket_list",
            },
            {
                "type": "resource",
                "module": "quilt_mcp.tools.resources",
                "name": "package_metadata",
                "signature": "package_metadata(uri: str)",
                "description": "Get package metadata",
                "is_async": False,
                "full_module_path": "quilt_mcp.tools.resources.package_metadata",
            },
        ]

        output_file = tmp_path / "output.json"
        generate_json_output(items, str(output_file))

        # Verify file exists and is valid JSON
        assert output_file.exists()
        with open(output_file) as f:
            data = json.load(f)

        # Verify structure
        assert "metadata" in data
        assert "tools" in data
        assert "resources" in data

        # Verify metadata
        assert data["metadata"]["tool_count"] == 1
        assert data["metadata"]["resource_count"] == 1
        assert data["metadata"]["total_count"] == 2
        assert "quilt_mcp.tools.buckets" in data["metadata"]["modules"]

        # Verify tools and resources are separated
        assert len(data["tools"]) == 1
        assert len(data["resources"]) == 1
        assert data["tools"][0]["name"] == "bucket_list"
        assert data["resources"][0]["name"] == "package_metadata"

    def test_handles_empty_items_list(self, tmp_path):
        """Verify JSON generation works with empty items list."""
        output_file = tmp_path / "empty.json"
        generate_json_output([], str(output_file))

        assert output_file.exists()
        with open(output_file) as f:
            data = json.load(f)

        assert data["metadata"]["tool_count"] == 0
        assert data["metadata"]["resource_count"] == 0
        assert data["tools"] == []
        assert data["resources"] == []

    def test_separates_tools_and_resources_correctly(self, tmp_path):
        """Verify tools and resources are properly separated."""
        items = [
            {
                "type": "tool",
                "module": "m1",
                "name": "tool1",
                "signature": "t1()",
                "description": "T1",
                "is_async": True,
                "full_module_path": "m1.tool1",
            },
            {
                "type": "resource",
                "module": "m2",
                "name": "res1",
                "signature": "r1()",
                "description": "R1",
                "is_async": False,
                "full_module_path": "m2.res1",
            },
            {
                "type": "tool",
                "module": "m3",
                "name": "tool2",
                "signature": "t2()",
                "description": "T2",
                "is_async": False,
                "full_module_path": "m3.tool2",
            },
        ]

        output_file = tmp_path / "separated.json"
        generate_json_output(items, str(output_file))

        with open(output_file) as f:
            data = json.load(f)

        assert len(data["tools"]) == 2
        assert len(data["resources"]) == 1
        assert data["metadata"]["tool_count"] == 2
        assert data["metadata"]["resource_count"] == 1


class TestGenerateTestYAML:
    """Test YAML test configuration generation.

    These are integration tests that test the full generation workflow.
    """

    @pytest.fixture
    def mock_server(self):
        """Create a mock MCP server with minimal tools and resources."""
        server = MagicMock()

        # Mock get_tools() - returns dict of tool name -> handler
        tool_handler = MagicMock()
        tool_handler.fn = MagicMock()
        tool_handler.fn.__name__ = "bucket_list"
        tool_handler.fn.__doc__ = "List all S3 buckets in the account"

        server.get_tools = AsyncMock(return_value={"bucket_list": tool_handler})

        # Mock get_resources() - returns dict of URI -> resource
        resource = MagicMock()
        resource.description = "Package metadata resource"
        server.get_resources = AsyncMock(return_value={"package://test": resource})

        # Mock get_resource_templates() - returns dict of URI template -> template
        server.get_resource_templates = AsyncMock(return_value={})

        return server

    @pytest.fixture
    def env_vars(self):
        """Standard environment variables for testing."""
        return {
            "AWS_PROFILE": "test",
            "AWS_DEFAULT_REGION": "us-east-1",
            "QUILT_CATALOG_URL": "https://test.quiltdata.com",
            "QUILT_TEST_BUCKET": "s3://test-bucket",
            "QUILT_TEST_PACKAGE": "test/package",
            "QUILT_TEST_ENTRY": "test.csv",
        }

    @pytest.mark.asyncio
    async def test_generates_valid_yaml_with_skip_discovery(self, mock_server, env_vars, tmp_path):
        """Verify YAML generation works with skip_discovery=True."""
        output_file = tmp_path / "test.yaml"

        with patch('quilt_mcp.testing.yaml_generator.get_user_athena_database', return_value='test_db'):
            await generate_test_yaml(
                server=mock_server,
                output_file=str(output_file),
                env_vars=env_vars,
                skip_discovery=True,
                discovery_timeout=1.0,
            )

        # Verify file exists and is valid YAML
        assert output_file.exists()
        with open(output_file) as f:
            config = yaml.safe_load(f)

        # Verify structure
        assert "_generated_by" in config
        assert "environment" in config
        assert "test_tools" in config
        assert "test_resources" in config
        assert "tool_loops" in config

        # Verify environment section
        assert config["environment"]["AWS_PROFILE"] == "test"
        assert config["environment"]["QUILT_CATALOG_URL"] == "https://test.quiltdata.com"

        # Verify tools section has our test tool
        assert "bucket_list" in config["test_tools"]
        tool_config = config["test_tools"]["bucket_list"]
        assert "description" in tool_config
        assert "effect" in tool_config
        assert "arguments" in tool_config

        # Verify resources section has our test resource
        assert "package://test" in config["test_resources"]

    @pytest.mark.asyncio
    async def test_generates_yaml_with_discovery_enabled(self, mock_server, env_vars, tmp_path):
        """Verify YAML generation works with discovery enabled."""
        output_file = tmp_path / "test-discovery.yaml"

        # Mock the discovery orchestrator behavior
        with (
            patch('quilt_mcp.testing.yaml_generator.get_user_athena_database', return_value='test_db'),
            patch('quilt_mcp.testing.yaml_generator.DiscoveryOrchestrator') as mock_orchestrator_class,
        ):
            mock_orchestrator = MagicMock()
            mock_orchestrator.registry.to_dict.return_value = {"s3_keys": [], "packages": []}
            mock_orchestrator.verbose = True

            # Mock discover_tool to return a simple result
            mock_result = MagicMock()
            mock_result.status = "PASSED"
            mock_result.duration_ms = 100
            mock_result.response = {"content": [{"name": "test"}]}
            mock_result.discovered_data = {}
            mock_result.error = None
            mock_result.error_category = None
            mock_orchestrator.discover_tool = AsyncMock(return_value=mock_result)
            mock_orchestrator.results = {}
            mock_orchestrator.print_summary = MagicMock()

            mock_orchestrator_class.return_value = mock_orchestrator

            await generate_test_yaml(
                server=mock_server,
                output_file=str(output_file),
                env_vars=env_vars,
                skip_discovery=False,
                discovery_timeout=1.0,
            )

        # Verify file exists and is valid YAML
        assert output_file.exists()
        with open(output_file) as f:
            config = yaml.safe_load(f)

        # Verify discovery section exists
        assert "discovered_data" in config

        # Verify tool has discovery info
        tool_config = config["test_tools"]["bucket_list"]
        assert "discovery" in tool_config
        assert tool_config["discovery"]["status"] == "PASSED"

    @pytest.mark.asyncio
    async def test_handles_tool_variants_correctly(self, env_vars, tmp_path):
        """Verify tools with variants generate multiple test cases."""
        # Create a mock server with search_catalog tool (which has variants)
        server = MagicMock()

        search_handler = MagicMock()
        search_handler.fn = MagicMock()
        search_handler.fn.__name__ = "search_catalog"
        search_handler.fn.__doc__ = "Search catalog for files and packages"

        server.get_tools = AsyncMock(return_value={"search_catalog": search_handler})
        server.get_resources = AsyncMock(return_value={})
        server.get_resource_templates = AsyncMock(return_value={})

        output_file = tmp_path / "variants.yaml"

        with patch('quilt_mcp.testing.yaml_generator.get_user_athena_database', return_value='test_db'):
            await generate_test_yaml(
                server=server,
                output_file=str(output_file),
                env_vars=env_vars,
                skip_discovery=True,
                discovery_timeout=1.0,
            )

        with open(output_file) as f:
            config = yaml.safe_load(f)

        # Verify variants were created (search_catalog has scope variants)
        test_tools = config["test_tools"]
        variant_keys = [k for k in test_tools.keys() if k.startswith("search_catalog.")]

        # Should have variants like search_catalog.global.no_bucket, search_catalog.file.no_bucket, etc.
        assert len(variant_keys) >= 3  # At least global, file, package variants

    @pytest.mark.asyncio
    async def test_validates_tool_loops_coverage(self, mock_server, env_vars, tmp_path):
        """Verify tool loops are generated and coverage is validated."""
        output_file = tmp_path / "loops.yaml"

        with patch('quilt_mcp.testing.yaml_generator.get_user_athena_database', return_value='test_db'):
            await generate_test_yaml(
                server=mock_server,
                output_file=str(output_file),
                env_vars=env_vars,
                skip_discovery=True,
                discovery_timeout=1.0,
            )

        with open(output_file) as f:
            config = yaml.safe_load(f)

        # Verify tool_loops section exists and has content
        assert "tool_loops" in config
        assert isinstance(config["tool_loops"], dict)
        # Should have some loops for write operations
        assert len(config["tool_loops"]) > 0

    @pytest.mark.asyncio
    async def test_includes_custom_tool_configs(self, env_vars, tmp_path):
        """Verify custom tool configurations are applied correctly."""
        # Create server with a tool that has custom config
        server = MagicMock()

        catalog_config_handler = MagicMock()
        catalog_config_handler.fn = MagicMock()
        catalog_config_handler.fn.__name__ = "catalog_configure"
        catalog_config_handler.fn.__doc__ = "Configure catalog URL"

        server.get_tools = AsyncMock(return_value={"catalog_configure": catalog_config_handler})
        server.get_resources = AsyncMock(return_value={})
        server.get_resource_templates = AsyncMock(return_value={})

        output_file = tmp_path / "custom.yaml"

        with patch('quilt_mcp.testing.yaml_generator.get_user_athena_database', return_value='test_db'):
            await generate_test_yaml(
                server=server,
                output_file=str(output_file),
                env_vars=env_vars,
                skip_discovery=True,
                discovery_timeout=1.0,
            )

        with open(output_file) as f:
            config = yaml.safe_load(f)

        # Verify custom config was applied
        tool_config = config["test_tools"]["catalog_configure"]
        assert "arguments" in tool_config
        # catalog_configure should have catalog_url argument from custom_configs
        assert "catalog_url" in tool_config["arguments"]
        assert tool_config["arguments"]["catalog_url"] == env_vars["QUILT_CATALOG_URL"]


class TestYAMLGeneratorIntegration:
    """Integration tests for the full YAML generation workflow."""

    @pytest.mark.asyncio
    async def test_full_generation_workflow(self, tmp_path):
        """Test complete workflow: tools -> discovery -> loops -> YAML."""
        # This test validates the full integration of all components
        server = MagicMock()

        # Create multiple tools of different types
        tools = {}
        for tool_name in ["bucket_list", "package_create", "bucket_object_info"]:
            handler = MagicMock()
            handler.fn = MagicMock()
            handler.fn.__name__ = tool_name
            handler.fn.__doc__ = f"Test tool {tool_name}"
            tools[tool_name] = handler

        server.get_tools = AsyncMock(return_value=tools)
        server.get_resources = AsyncMock(return_value={})
        server.get_resource_templates = AsyncMock(return_value={})

        env_vars = {
            "QUILT_CATALOG_URL": "https://test.quiltdata.com",
            "QUILT_TEST_BUCKET": "s3://test-bucket",
            "QUILT_TEST_PACKAGE": "test/package",
            "QUILT_TEST_ENTRY": "test.csv",
        }

        output_file = tmp_path / "full.yaml"

        with patch('quilt_mcp.testing.yaml_generator.get_user_athena_database', return_value='test_db'):
            await generate_test_yaml(
                server=server,
                output_file=str(output_file),
                env_vars=env_vars,
                skip_discovery=True,
                discovery_timeout=1.0,
            )

        # Verify the complete structure
        assert output_file.exists()
        with open(output_file) as f:
            config = yaml.safe_load(f)

        # All major sections should exist
        assert all(
            key in config
            for key in ["_generated_by", "environment", "test_tools", "test_resources", "tool_loops", "test_config"]
        )

        # Should have test cases for all tools
        assert len(config["test_tools"]) >= 3

        # Tool loops should be generated
        assert len(config["tool_loops"]) > 0
