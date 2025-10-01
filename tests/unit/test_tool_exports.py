"""Behavior-driven tests validating the Quilt MCP public export surface."""

from __future__ import annotations

import importlib

import pytest


def test_removed_tool_exports_are_absent() -> None:
    """Ensure deprecated tool names are neither exported nor importable."""
    removed_tools = {
        "create_package",  # Renamed to package_create
        "package_update",  # Removed - anti-pattern
        "package_update_metadata",  # Removed - anti-pattern
        "packages_search",
        "bucket_objects_search",
        "tabulator_open_query_status",
        "tabulator_open_query_toggle",
        "auth_status",  # Renamed to catalog_status
        "switch_catalog",  # Renamed to catalog_set
        "search_explain",  # Renamed to catalog_search_explain
        "search_suggest",  # Renamed to catalog_search_suggest
        "validate_metadata_structure",  # Renamed to metadata_validate_structure
    }

    quilt_mcp = importlib.import_module("quilt_mcp")

    for tool_name in removed_tools:
        assert tool_name not in quilt_mcp.__all__, tool_name
        with pytest.raises(AttributeError):
            getattr(quilt_mcp, tool_name)


def test_primary_package_creation_functions_are_exported() -> None:
    """Ensure the two primary package creation functions are properly exported."""
    quilt_mcp = importlib.import_module("quilt_mcp")

    # The two primary package creation functions after consolidation
    primary_functions = ["package_create", "package_create_from_s3"]

    for func_name in primary_functions:
        assert func_name in quilt_mcp.__all__, f"{func_name} should be in __all__"
        assert hasattr(quilt_mcp, func_name), f"{func_name} should be importable"
        assert callable(getattr(quilt_mcp, func_name)), f"{func_name} should be callable"


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

    assert "admin_tabulator_access_get" in quilt_mcp.__all__
    assert callable(quilt_mcp.admin_tabulator_access_get)

    assert "admin_tabulator_access_set" in quilt_mcp.__all__
    assert callable(quilt_mcp.admin_tabulator_access_set)

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
        "workflow_step_add",
        "workflow_step_update",
        "workflow_status_get",
    ]
    for name in canonical:
        assert name in quilt_mcp.__all__, name
        assert callable(getattr(quilt_mcp, name))

    removed = [
        "workflow_list",  # Replaced by WorkflowResource (workflow://workflows)
        "workflow_list_all",
        "workflow_add_step",
        "workflow_update_step",
        "workflow_get_status",
    ]
    for legacy in removed:
        assert legacy not in quilt_mcp.__all__, legacy


def test_public_exports_alphabetical_with_admin_last() -> None:
    """Public exports stay alphabetized and admin tools come last."""
    quilt_mcp = importlib.import_module("quilt_mcp")

    exports = quilt_mcp.__all__
    assert len(exports) == len(set(exports)), "Duplicate entries found in __all__"

    # Constants that don't need to be sorted
    constants = {
        "DEFAULT_REGISTRY",
        "DEFAULT_BUCKET",
        "KNOWN_TEST_PACKAGE",
        "KNOWN_TEST_ENTRY",
        "KNOWN_TEST_S3_OBJECT",
    }

    non_constants = [name for name in exports if name not in constants]
    admin_tools = [name for name in non_constants if name.startswith("admin_")]
    regular_tools = [name for name in non_constants if not name.startswith("admin_")]

    # Verify regular tools are alphabetically sorted
    assert regular_tools == sorted(regular_tools), (
        f"Regular tools must be alphabetically sorted. Expected: {sorted(regular_tools)}, Got: {regular_tools}"
    )

    # If there are admin tools, verify they are alphabetically sorted and come last
    if admin_tools:
        assert admin_tools == sorted(admin_tools), (
            f"Admin tools must be alphabetically sorted. Expected: {sorted(admin_tools)}, Got: {admin_tools}"
        )

        last_regular_index = max((exports.index(name) for name in regular_tools), default=-1)
        first_admin_index = min((exports.index(name) for name in admin_tools))

        assert last_regular_index < first_admin_index, (
            f"Admin tools must come after all regular tools. "
            f"Last regular tool '{regular_tools[-1]}' at index {last_regular_index}, "
            f"first admin tool '{admin_tools[0]}' at index {first_admin_index}"
        )
