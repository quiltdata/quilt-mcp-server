from __future__ import annotations

from quilt_mcp.services import metadata_service as ms


def test_templates_listing_and_validation_helpers():
    templates = ms.list_metadata_templates()
    assert "available_templates" in templates
    assert "standard" in templates["available_templates"]

    template = ms.get_metadata_template("genomics", {"organism": "human"})
    assert template["organism"] == "human"
    assert "creation_date" in template

    unknown_template = ms.get_metadata_template("does-not-exist")
    assert unknown_template["package_type"] == "data"


def test_validate_metadata_structure_variants():
    invalid = ms.validate_metadata_structure("not-a-dict")  # type: ignore[arg-type]
    assert invalid["valid"] is False
    assert "dictionary" in invalid["error"].lower()

    validated = ms.validate_metadata_structure(
        {"description": "short"},
        template_name="ml",
    )
    assert validated["valid"] is True
    assert any("very short" in s.lower() or "template 'ml'" in s.lower() for s in validated["suggestions"])


def test_show_examples_and_fix_issues_content():
    examples = ms.show_metadata_examples()
    assert "metadata_usage_guide" in examples
    assert "troubleshooting" in examples
    assert "best_practices" in examples

    fixes = ms.fix_metadata_validation_issues()
    assert "common_issues_and_fixes" in fixes
    assert "step_by_step_fix" in fixes
    assert "recommended_workflow" in fixes


def test_create_metadata_from_template_success_and_error(monkeypatch):
    success = ms.create_metadata_from_template("standard", description="my package", custom_fields={"x": 1})
    assert success["success"] is True
    assert success["metadata"]["description"] == "my package"
    assert success["metadata"]["x"] == 1

    monkeypatch.setattr(ms, "get_metadata_template", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    failure = ms.create_metadata_from_template("standard")
    assert failure["success"] is False
    assert "failed to create metadata" in failure["error"].lower()
