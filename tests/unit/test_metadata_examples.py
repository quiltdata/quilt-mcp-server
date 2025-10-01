import pytest
from unittest.mock import patch

from quilt_mcp.tools.metadata_examples import (
    metadata_template_create,
)
from quilt_mcp.resources.metadata import (
    MetadataExamplesResource,
    MetadataTroubleshootingResource,
)


@pytest.mark.asyncio
async def test_metadata_examples_resource_structure():
    """Test metadata examples resource returns expected structure."""
    resource = MetadataExamplesResource()
    guide = await resource.list_items()

    assert isinstance(guide, dict)
    assert "metadata_usage_guide" in guide
    assert "troubleshooting" in guide
    assert "best_practices" in guide
    assert "quick_reference" in guide

    muc = guide["metadata_usage_guide"]
    assert "working_examples" in muc
    assert "common_patterns" in muc
    assert "recommended_approach" in muc

    quick = guide["quick_reference"]
    assert "available_templates" in quick
    assert set(["standard", "genomics", "ml", "research", "analytics"]).issubset(set(quick["available_templates"]))


@pytest.mark.asyncio
async def test_metadata_examples_resource_get():
    """Test getting metadata examples resource."""
    resource = MetadataExamplesResource()
    response = await resource.get()

    assert response.uri == "metadata://examples"
    assert response.mime_type == "application/json"
    assert isinstance(response.content, dict)
    assert "items" in response.content
    assert "metadata" in response.content

    # Check items were extracted
    items = response.content["items"]
    assert len(items) > 0
    assert all("type" in item for item in items)

    # Check metadata includes best practices and quick reference
    metadata = response.content["metadata"]
    assert "best_practices" in metadata
    assert "quick_reference" in metadata


def test_metadata_template_create_success():
    result = metadata_template_create(
        template_name="ml",
        description="Test dataset",
        custom_fields={"features_count": 10},
    )

    assert result["success"] is True
    assert result["template_used"] == "ml"
    metadata = result["metadata"]
    assert metadata["description"] == "Test dataset"
    assert metadata["features_count"] == 10
    assert metadata.get("package_type") in {"ml_dataset", "ml"}


def test_metadata_template_create_failure():
    with patch(
        "quilt_mcp.tools.metadata_examples.metadata_template_get",
        side_effect=Exception("boom"),
    ):
        result = metadata_template_create("unknown", "desc", {"x": 1})
        assert result["success"] is False
        assert "Failed to create metadata from template" in result["error"]
        assert result["template_requested"] == "unknown"
        assert "suggested_actions" in result


@pytest.mark.asyncio
async def test_metadata_troubleshooting_resource_contents():
    """Test metadata troubleshooting resource returns expected content."""
    resource = MetadataTroubleshootingResource()
    info = await resource.list_items()

    assert "common_issues_and_fixes" in info
    issues = info["common_issues_and_fixes"]
    assert "schema_validation_error" in issues
    assert "json_format_error" in issues
    assert "type_validation_error" in issues

    assert "step_by_step_fix" in info
    assert any("Choose your approach" in step or step.startswith("1.") for step in info["step_by_step_fix"])


@pytest.mark.asyncio
async def test_metadata_troubleshooting_resource_get():
    """Test getting metadata troubleshooting resource."""
    resource = MetadataTroubleshootingResource()
    response = await resource.get()

    assert response.uri == "metadata://troubleshooting"
    assert response.mime_type == "application/json"
    assert isinstance(response.content, dict)
    assert "items" in response.content
    assert "metadata" in response.content

    # Check items were extracted (issues)
    items = response.content["items"]
    assert len(items) > 0
    assert all("type" in item for item in items)
    assert all(item["type"] == "issue_fix" for item in items)

    # Check metadata includes step-by-step and workflow
    metadata = response.content["metadata"]
    assert "step_by_step_fix" in metadata
    assert "recommended_workflow" in metadata
