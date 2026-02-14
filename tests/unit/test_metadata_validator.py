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


def test_validate_quilt_metadata_missing_sections_and_bad_types():
    valid, issues = mv.validate_quilt_metadata({})
    assert valid is False
    assert any("top-level section" in i for i in issues)

    metadata = {
        "quilt": {
            "created_by": "me",
            "creation_date": "not-a-date",
            "source": {"type": "s3_bucket"},
            "data_profile": {"total_files": "x", "file_types": "csv"},
        }
    }
    valid2, issues2 = mv.validate_quilt_metadata(metadata)
    assert valid2 is False
    assert any("Invalid 'creation_date' format" in i for i in issues2)
    assert any("Missing source 'bucket'" in i for i in issues2)
    assert any("'total_files' must be an integer" in i for i in issues2)
    assert any("'file_types' must be a list" in i for i in issues2)


def test_validate_user_metadata_recommendations():
    valid, recs = mv.validate_user_metadata({})
    assert valid is True
    assert any("consider adding user metadata" in r.lower() for r in recs)

    valid2, recs2 = mv.validate_user_metadata({"description": "short", "tags": [1, "a"], "author": "x"})
    assert valid2 is True
    assert any("very short" in r.lower() for r in recs2)
    assert any("all tags should be strings" in r.lower() for r in recs2)


def test_nested_helpers_and_suggestions():
    metadata = {
        "quilt": {
            "created_by": "me",
            "creation_date": "2024-01-01T00:00:00Z",
            "source": {"type": "s3_bucket", "bucket": "b"},
            "data_profile": {"total_files": 1},
        },
        "user_metadata": {"description": "valid description"},
    }

    assert mv._get_nested_value(metadata, "quilt.source.bucket") == "b"
    assert mv._get_nested_value(metadata, "quilt.nope") is None
    assert mv._validate_iso_date("2024-01-01T00:00:00Z") is True
    assert mv._validate_iso_date(123) is False

    suggestions = mv.suggest_metadata_improvements(metadata)
    assert any("tags or keywords" in s.lower() for s in suggestions)
