# (File shortened for brevity; apply_patch will replace entire content)
"""Quilt MCP Server - package exports with lazy loading."""

from __future__ import annotations

import importlib
from typing import Any

from .constants import (
    DEFAULT_BUCKET,
    DEFAULT_REGISTRY,
    KNOWN_TEST_ENTRY,
    KNOWN_TEST_PACKAGE,
    KNOWN_TEST_S3_OBJECT,
)

__version__ = "0.6.73"

__all__ = [
    "DEFAULT_REGISTRY",
    "DEFAULT_BUCKET",
    "KNOWN_TEST_PACKAGE",
    "KNOWN_TEST_ENTRY",
    "KNOWN_TEST_S3_OBJECT",
    "auth_status",
    "catalog_info",
    "catalog_name",
    "catalog_url",
    "catalog_uri",
    "configure_catalog",
    "filesystem_status",
    "switch_catalog",
    "bucket_object_info",
    "bucket_object_text",
    "bucket_objects_put",
    "bucket_object_fetch",
    "bucket_object_link",
    "packaging",
    "package_browse",
    "package_create",
    "package_create_from_s3",
    "list_metadata_templates",
    "get_metadata_template",
    "permissions",
    "bucket_access_check",
    "permissions_recommendations_get",
    "show_metadata_examples",
    "create_metadata_from_template",
    "fix_metadata_validation_issues",
    "create_quilt_summary_files",
    "generate_quilt_summarize_json",
    "generate_package_visualizations",
    "generate_multi_format_visualizations",
    "tabulator_tables_list",
    "tabulator_table_create",
    "tabulator_table_delete",
    "tabulator_table_rename",
    "tabulator_open_query_status",
    "tabulator_open_query_toggle",
    "package_visualization",
]

_LAZY_IMPORTS = {
    # Auth
    "auth_status": ".tools.auth",
    "catalog_info": ".tools.auth",
    "catalog_name": ".tools.auth",
    "catalog_url": ".tools.auth",
    "catalog_uri": ".tools.auth",
    "configure_catalog": ".tools.auth",
    "filesystem_status": ".tools.auth",
    "switch_catalog": ".tools.auth",
    # Buckets
    "bucket_object_info": ".tools.buckets",
    "bucket_object_text": ".tools.buckets",
    "bucket_objects_put": ".tools.buckets",
    "bucket_object_fetch": ".tools.buckets",
    "bucket_object_link": ".tools.buckets",
    # Packaging
    "packaging": ".tools.packaging",
    "package_browse": ".tools.packaging",
    "package_create": ".tools.packaging",
    "package_create_from_s3": ".tools.packaging",
    "list_metadata_templates": ".tools.packaging",
    "get_metadata_template": ".tools.packaging",
    # Permissions
    "permissions": ".tools.permissions",
    "bucket_access_check": ".tools.permissions",
    "permissions_recommendations_get": ".tools.permissions",
    # Metadata examples
    "show_metadata_examples": ".tools.metadata_examples",
    "create_metadata_from_template": ".tools.metadata_examples",
    "fix_metadata_validation_issues": ".tools.metadata_examples",
    # Quilt summary
    "create_quilt_summary_files": ".tools.quilt_summary",
    "generate_quilt_summarize_json": ".tools.quilt_summary",
    "generate_package_visualizations": ".tools.quilt_summary",
    "generate_multi_format_visualizations": ".tools.quilt_summary",
    # Tabulator
    "tabulator_tables_list": ".tools.tabulator",
    "tabulator_table_create": ".tools.tabulator",
    "tabulator_table_delete": ".tools.tabulator",
    "tabulator_table_rename": ".tools.tabulator",
    "tabulator_open_query_status": ".tools.tabulator",
    "tabulator_open_query_toggle": ".tools.tabulator",
    # Visualization enrichment
    "package_visualization": ".tools.package_visualization",
}


def __getattr__(name: str) -> Any:
    if name in {
        "DEFAULT_BUCKET",
        "DEFAULT_REGISTRY",
        "KNOWN_TEST_ENTRY",
        "KNOWN_TEST_PACKAGE",
        "KNOWN_TEST_S3_OBJECT",
    }:
        return globals()[name]

    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    module = importlib.import_module(_LAZY_IMPORTS[name], __name__)
    attr = getattr(module, name)
    globals()[name] = attr
    return attr


def __dir__() -> list[str]:
    dynamic = [attr for attr in globals() if not attr.startswith("_")]
    return sorted(set(__all__ + dynamic))
