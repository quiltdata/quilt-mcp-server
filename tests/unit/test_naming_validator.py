"""Behavior-driven tests for naming validator utilities."""

from __future__ import annotations

import pytest

from quilt_mcp.validators import naming_validator as nv


def test_validate_package_naming_requires_namespace_separator():
    is_valid, errors, suggestions = nv.validate_package_naming("invalid-name")

    assert is_valid is False
    assert any("namespace/name" in error for error in errors)
    assert suggestions == []


def test_suggest_package_name_falls_back_to_timestamp_suffix():
    suggestions = nv.suggest_package_name(source_bucket="ab")

    assert suggestions
    assert suggestions[0].startswith("data/")
    assert any(char.isdigit() for char in suggestions[0])
