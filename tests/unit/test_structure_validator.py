"""Behavioral tests for package structure validator."""

from __future__ import annotations

from quilt_mcp.validators import structure_validator as sv


def test_validate_package_structure_deduplicates_warnings():
    structure = {
        "temp/data": [{"Key": "temp/data/file1.csv"}],
        "temp/models": [{"Key": "temp/models/model.pkl"}],
    }

    is_valid, warnings, recommendations = sv.validate_package_structure(structure)

    assert is_valid is True
    assert warnings.count("Folder 'temp/data' contains discouraged pattern 'temp'") == 1
    assert warnings.count("Folder 'temp/models' contains discouraged pattern 'temp'") == 1
    # Ensure the general organization recommendation appears once
    assert recommendations.count("Consider organizing data files into 'data/' subfolder structure") == 1
