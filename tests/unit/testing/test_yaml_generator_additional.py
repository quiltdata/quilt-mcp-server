"""Additional edge-case coverage for YAML generator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from quilt_mcp.testing.yaml_generator import generate_test_yaml


def _mk_handler(name: str, doc: str = "Doc") -> MagicMock:
    handler = MagicMock()
    handler.fn = MagicMock()
    handler.fn.__name__ = name
    handler.fn.__doc__ = doc
    return handler


@pytest.mark.asyncio
async def test_generate_yaml_prioritizes_bucket_objects_list_and_populates_uri_variables(tmp_path):
    server = MagicMock()
    server.get_tools = AsyncMock(
        return_value={
            "bucket_objects_list": _mk_handler("bucket_objects_list", "List objects"),
            "x_tool": _mk_handler("x_tool", "Other tool"),
        }
    )
    static_resource = MagicMock(description="Static resource")
    template_resource = MagicMock(description="Template resource")
    server.get_resources = AsyncMock(return_value={"auth://status": static_resource})
    server.get_resource_templates = AsyncMock(
        return_value={"resource://{bucket}/{database}/{table}/{name}/{id}/{region}": template_resource}
    )

    output_file = tmp_path / "gen.yaml"
    env_vars = {
        "QUILT_CATALOG_URL": "https://catalog.example",
        "QUILT_TEST_BUCKET": "s3://test-bucket",
        "QUILT_TEST_PACKAGE": "pkg/name",
        "QUILT_TEST_ENTRY": "entry.csv",
    }

    with patch("quilt_mcp.testing.yaml_generator.get_user_athena_database", return_value="athena_db"):
        await generate_test_yaml(
            server=server,
            output_file=str(output_file),
            env_vars=env_vars,
            skip_discovery=True,
            discovery_timeout=1.0,
        )

    config = yaml.safe_load(output_file.read_text())
    assert "bucket_objects_list" in config["test_tools"]
    uri_case = config["test_resources"]["resource://{bucket}/{database}/{table}/{name}/{id}/{region}"]
    assert uri_case["uri_variables"]["bucket"] == "test-bucket"
    assert uri_case["uri_variables"]["database"] == "athena_db"
    assert uri_case["uri_variables"]["table"] == "test_table"
    assert uri_case["uri_variables"]["name"] == "test_user"
    assert uri_case["uri_variables"]["id"] == "test-workflow-001"
    assert uri_case["uri_variables"]["region"] == "CONFIGURE_REGION"


@pytest.mark.asyncio
async def test_generate_yaml_raises_when_static_resource_missing_description(tmp_path):
    server = MagicMock()
    server.get_tools = AsyncMock(return_value={"x_tool": _mk_handler("x_tool")})
    server.get_resources = AsyncMock(return_value={"resource://bad": MagicMock(description="")})
    server.get_resource_templates = AsyncMock(return_value={})
    output_file = tmp_path / "bad-static.yaml"

    with patch("quilt_mcp.testing.yaml_generator.get_user_athena_database", return_value="athena_db"):
        with pytest.raises(ValueError, match="missing a description"):
            await generate_test_yaml(
                server=server,
                output_file=str(output_file),
                env_vars={},
                skip_discovery=True,
                discovery_timeout=1.0,
            )


@pytest.mark.asyncio
async def test_generate_yaml_raises_when_template_missing_description(tmp_path):
    server = MagicMock()
    server.get_tools = AsyncMock(return_value={"x_tool": _mk_handler("x_tool")})
    server.get_resources = AsyncMock(return_value={})
    server.get_resource_templates = AsyncMock(return_value={"resource://{id}": MagicMock(description=None)})
    output_file = tmp_path / "bad-template.yaml"

    with patch("quilt_mcp.testing.yaml_generator.get_user_athena_database", return_value="athena_db"):
        with pytest.raises(ValueError, match="missing a description"):
            await generate_test_yaml(
                server=server,
                output_file=str(output_file),
                env_vars={},
                skip_discovery=True,
                discovery_timeout=1.0,
            )
