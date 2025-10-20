import pytest
from unittest.mock import patch

from quilt_mcp.services.metadata_service import (
    create_metadata_from_template,
)


def test_create_metadata_from_template_success():
    result = create_metadata_from_template(
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


def test_create_metadata_from_template_failure():
    with patch(
        "quilt_mcp.services.metadata_service.get_metadata_template",
        side_effect=Exception("boom"),
    ):
        result = create_metadata_from_template("unknown", "desc", {"x": 1})
        assert result["success"] is False
        assert "Failed to create metadata from template" in result["error"]
        assert result["template_requested"] == "unknown"
        assert "suggested_actions" in result
