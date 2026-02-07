"""Behavioral tests for metadata validation helpers."""

from __future__ import annotations

import pytest

from quilt_mcp.utils import metadata_validator as mv


def test_validate_metadata_compliance_identifies_missing_fields():
    metadata = {
        "quilt": {
            "source": {"type": "api"},
            "creation_date": "2024-04-01T12:00:00Z",
            "data_profile": {"total_files": 0},
        }
    }

    compliant, errors, warnings = mv.validate_metadata_compliance(metadata)

    assert compliant is False
    assert any("Missing required field" in error for error in errors)
    assert any("Missing recommended field" in warning for warning in warnings)
    assert any("total_files" in error for error in errors)


def test_enhance_metadata_quality_adds_quality_section():
    metadata = {
        "quilt": {
            "data_profile": {"file_types": ["csv", "csv", "tsv"]},
        },
        "user_metadata": {"description": "Short"},
    }

    enhanced = mv.enhance_metadata_quality(metadata)

    quality = enhanced["quilt"]["metadata_quality"]
    assert quality["enhanced_by"] == "mcp-metadata-validator"
    assert quality["enhancement_date"].endswith("Z")
    assert enhanced["quilt"]["data_profile"]["file_types"] == ["csv", "tsv"]
