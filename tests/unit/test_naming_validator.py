from __future__ import annotations

from quilt_mcp.utils import naming_validator as nv


def test_validate_package_naming_rejects_bad_formats():
    valid, errors, suggestions = nv.validate_package_naming("badformat")
    assert valid is False
    assert errors
    assert suggestions == []

    valid2, errors2, _ = nv.validate_package_naming("a/b/c")
    assert valid2 is False
    assert any("exactly one '/'" in err for err in errors2)


def test_validate_package_naming_collects_best_practice_suggestions():
    valid, errors, suggestions = nv.validate_package_naming("data/v1")
    assert valid is True
    assert errors == []
    assert any("more descriptive package name" in s.lower() or "avoid version numbers" in s.lower() for s in suggestions)


def test_validate_name_component_edge_cases():
    valid, errors, _ = nv._validate_name_component("", "namespace")
    assert valid is False
    assert any("cannot be empty" in e for e in errors)

    valid2, errors2, _ = nv._validate_name_component("-bad-", "package")
    assert valid2 is False
    assert any("invalid characters" in e.lower() or "cannot start" in e.lower() for e in errors2)


def test_suggest_package_name_and_namespace_extraction():
    suggestions = nv.suggest_package_name(
        source_bucket="analytics-reports-prod",
        source_prefix="dashboard/monthly",
        description="business insights metrics",
    )
    assert suggestions
    assert all("/" in item for item in suggestions)

    ns = nv._extract_namespace_from_source("ml-training-bucket", "models/v2")
    assert ns in {"ml", "data"}


def test_clean_component_and_name_extraction():
    assert nv._clean_name_component("A weird###name___") == "a-weird-name"
    assert nv._clean_name_component("x") == ""

    names = nv._extract_package_names_from_source("my-data-bucket", "raw/files", "RNA seq study package")
    assert isinstance(names, list)
    assert len(names) <= 5
