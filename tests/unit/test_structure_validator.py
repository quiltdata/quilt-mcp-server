from __future__ import annotations

from quilt_mcp.utils import structure_validator as sv


def test_validate_package_structure_empty_and_recommendations():
    valid, warnings, recs = sv.validate_package_structure({})
    assert valid is False
    assert any("empty" in w.lower() for w in warnings)

    structure = {
        "misc": [{"Key": "misc/file1.csv"}],
        "misc/deep/deeper/deepest/too-deep": [{"Key": "misc/deep/deeper/deepest/too-deep/file2.txt"}],
    }
    valid2, warnings2, recs2 = sv.validate_package_structure(structure)
    assert valid2 is True
    assert any("deep nesting" in w.lower() for w in warnings2)
    assert any("readme" in r.lower() for r in recs2)


def test_validate_folder_structure_discouraged_patterns_and_special_chars():
    warnings, recs = sv.validate_folder_structure("tmp/special@folder")
    assert any("discouraged pattern" in w.lower() for w in warnings)
    assert any("special characters" in w.lower() for w in warnings)
    assert isinstance(recs, list)


def test_suggest_folder_organization_by_file_types():
    files = [
        {"Key": "data.csv"},
        {"Key": "logs/output.log"},
        {"Key": "images/pic.png"},
        {"Key": "README.md"},
        {"Key": "schema.schema"},
        {"Key": "settings.yaml"},
    ]
    suggestions = sv.suggest_folder_organization(files)

    assert "data/processed" in suggestions
    assert "data/raw" in suggestions
    assert "data/media" in suggestions
    assert "docs" in suggestions
    assert "docs/schemas" in suggestions
    assert "metadata" in suggestions


def test_validate_file_naming_checks_spaces_special_chars_hidden():
    ok, warnings = sv.validate_file_naming("bad file@name.txt")
    assert ok is False
    assert any("spaces" in w.lower() for w in warnings)
    assert any("special characters" in w.lower() for w in warnings)

    ok2, warnings2 = sv.validate_file_naming(".hiddenfile")
    assert any("hidden file" in w.lower() for w in warnings2)
    assert ok2 is True
