"""Behavior-driven tests validating the Quilt MCP public export surface."""

from __future__ import annotations

import importlib

import pytest


def test_removed_tool_exports_are_absent() -> None:
    """Ensure deprecated tool names are neither exported nor importable."""
    removed_tools = {
        "create_package",
        "package_create_from_s3",
        "packages_search",
        "bucket_objects_search",
        "tabulator_open_query_status",
        "tabulator_open_query_toggle",
    }

    quilt_mcp = importlib.import_module("quilt_mcp")

    for tool_name in removed_tools:
        assert tool_name not in quilt_mcp.__all__, tool_name
        with pytest.raises(AttributeError):
            getattr(quilt_mcp, tool_name)


def test_package_tools_use_canonical_names() -> None:
    """Verify canonical package tools are exported and legacy names removed."""
    quilt_mcp = importlib.import_module("quilt_mcp")

    canonical = ["package_create", "package_tools_list"]
    for name in canonical:
        assert name in quilt_mcp.__all__, name
        assert callable(getattr(quilt_mcp, name))

    removed = ["create_package_enhanced", "list_package_tools"]
    for legacy in removed:
        assert legacy not in quilt_mcp.__all__, legacy
        with pytest.raises(AttributeError):
            getattr(quilt_mcp, legacy)


def test_catalog_search_replaces_unified_search() -> None:
    """Ensure unified search is renamed to catalog_search."""
    quilt_mcp = importlib.import_module("quilt_mcp")

    assert "catalog_search" in quilt_mcp.__all__
    assert callable(quilt_mcp.catalog_search)

    assert "unified_search" not in quilt_mcp.__all__
    with pytest.raises(AttributeError):
        quilt_mcp.unified_search


def test_tabulator_accessibility_exports() -> None:
    """Tabulator accessibility tools expose canonical names only."""
    quilt_mcp = importlib.import_module("quilt_mcp")

    assert "tabular_accessibility_get" in quilt_mcp.__all__
    assert callable(quilt_mcp.tabular_accessibility_get)

    assert "tabular_accessibility_set" in quilt_mcp.__all__
    assert callable(quilt_mcp.tabular_accessibility_set)

    removed = [
        "tabulator_open_query_status",
        "tabulator_open_query_toggle",
        "admin_tabulator_open_query_get",
        "admin_tabulator_open_query_set",
    ]
    for legacy in removed:
        assert legacy not in quilt_mcp.__all__, legacy
        with pytest.raises(AttributeError):
            getattr(quilt_mcp, legacy)


def test_metadata_templates_use_prefixed_names() -> None:
    """Metadata template helpers expose metadata_ prefixed names."""
    quilt_mcp = importlib.import_module("quilt_mcp")

    canonical = ["metadata_template_get", "metadata_template_create"]
    for name in canonical:
        assert name in quilt_mcp.__all__, name
        assert callable(getattr(quilt_mcp, name))

    removed = ["get_metadata_template", "create_metadata_from_template"]
    for legacy in removed:
        assert legacy not in quilt_mcp.__all__, legacy
        with pytest.raises(AttributeError):
            getattr(quilt_mcp, legacy)


def test_workflow_tools_use_step_and_status_prefixes() -> None:
    """Workflow orchestration tools expose renamed functions."""
    quilt_mcp = importlib.import_module("quilt_mcp")

    canonical = [
        "workflow_list",
        "workflow_step_add",
        "workflow_step_update",
        "workflow_status_get",
    ]
    for name in canonical:
        assert name in quilt_mcp.__all__, name
        assert callable(getattr(quilt_mcp, name))

    removed = [
        "workflow_list_all",
        "workflow_add_step",
        "workflow_update_step",
        "workflow_get_status",
    ]
    for legacy in removed:
        assert legacy not in quilt_mcp.__all__, legacy
        with pytest.raises(AttributeError):
            getattr(quilt_mcp, legacy)


def test_public_exports_are_sorted_with_admin_suffix() -> None:
    """Public exports stay alphabetized and group admin tools at the end."""
    quilt_mcp = importlib.import_module("quilt_mcp")

    exports = quilt_mcp.__all__
    assert len(exports) == len(set(exports)), "Duplicate entries found in __all__"

    constants = {
        "DEFAULT_REGISTRY",
        "DEFAULT_BUCKET",
        "KNOWN_TEST_PACKAGE",
        "KNOWN_TEST_ENTRY",
        "KNOWN_TEST_S3_OBJECT",
    }
    admin_exports = [
        "tabular_accessibility_get",
        "tabular_accessibility_set",
    ]

    assert exports[-len(admin_exports) :] == sorted(admin_exports)

    public_exports = [name for name in exports[: -len(admin_exports)] if name not in constants]
    assert public_exports == sorted(public_exports)

    trailing_without_admin = exports[: -len(admin_exports)]
    assert all(name not in admin_exports for name in trailing_without_admin)
