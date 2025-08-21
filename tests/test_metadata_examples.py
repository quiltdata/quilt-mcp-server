from unittest.mock import patch

from quilt_mcp.tools.metadata_examples import (
    show_metadata_examples,
    create_metadata_from_template,
    fix_metadata_validation_issues,
)


def test_show_metadata_examples_structure():
    guide = show_metadata_examples()

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
    assert set(["standard", "genomics", "ml", "research", "analytics"]).issubset(
        set(quick["available_templates"])
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
        "quilt_mcp.tools.metadata_examples.get_metadata_template", side_effect=Exception("boom")
    ):
        result = create_metadata_from_template("unknown", "desc", {"x": 1})
        assert result["success"] is False
        assert "Failed to create metadata from template" in result["error"]
        assert result["template_requested"] == "unknown"
        assert "suggested_actions" in result


def test_fix_metadata_validation_issues_contents():
    info = fix_metadata_validation_issues()

    assert "common_issues_and_fixes" in info
    issues = info["common_issues_and_fixes"]
    assert "schema_validation_error" in issues
    assert "json_format_error" in issues
    assert "type_validation_error" in issues

    assert "step_by_step_fix" in info
    assert any("Choose your approach" in step or step.startswith("1.") for step in info["step_by_step_fix"]) 

