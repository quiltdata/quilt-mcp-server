"""Quilt MCP Server - A secure MCP server for accessing Quilt data.

This package provides Model Context Protocol (MCP) tools for interacting with
Quilt packages and S3 buckets through a secure, authenticated interface.
"""

from __future__ import annotations

from .constants import (
    DEFAULT_BUCKET,
    DEFAULT_REGISTRY,
    KNOWN_TEST_ENTRY,
    KNOWN_TEST_PACKAGE,
    KNOWN_TEST_S3_OBJECT,
)

# Re-export all tools for easy access
from .tools.auth import (
    auth_status,
    catalog_info,
    catalog_name,
    catalog_uri,
    catalog_url,
    configure_catalog,
    filesystem_status,
    switch_catalog,
)
from .tools.buckets import (
    bucket_object_fetch,
    bucket_object_info,
    bucket_object_link,
    bucket_object_text,
    bucket_objects_put,
)
from .tools.packaging import (
    packaging,
    package_browse,
    package_create,
    package_create_from_s3,
    list_metadata_templates,
    get_metadata_template,
)
from .tools.permissions import (
    permissions,
    bucket_access_check,
    permissions_recommendations_get,
)
from .tools.metadata_examples import (
    show_metadata_examples,
    create_metadata_from_template,
    fix_metadata_validation_issues,
)
from .tools.quilt_summary import (
    create_quilt_summary_files,
    generate_quilt_summarize_json,
    generate_package_visualizations,
)

# Removed old packages module - functionality moved to packaging
from .tools.tabulator import (
    tabulator_tables_list,
    tabulator_table_create,
    tabulator_table_delete,
    tabulator_table_rename,
    tabulator_open_query_status,
    tabulator_open_query_toggle,
)

__version__ = "0.5.6"

__all__ = [
    # Constants
    "DEFAULT_REGISTRY",
    "DEFAULT_BUCKET",
    "KNOWN_TEST_PACKAGE",
    "KNOWN_TEST_ENTRY",
    "KNOWN_TEST_S3_OBJECT",
    # Auth tools (7 tools)
    "auth_status",
    "catalog_info",
    "catalog_name",
    "catalog_url",
    "catalog_uri",
    "configure_catalog",
    "filesystem_status",
    "switch_catalog",
    # Bucket tools (5 tools)
    "bucket_object_info",
    "bucket_object_text",
    "bucket_objects_put",
    "bucket_object_fetch",
    "bucket_object_link",
    # Package tools (6 tools)
    "packaging",
    "package_browse",
    "package_create",
    "package_create_from_s3",
    "list_metadata_templates",
    "get_metadata_template",
    # Permission tools (3 tools)
    "permissions",
    "bucket_access_check",
    "permissions_recommendations_get",
    # Metadata examples (3 tools)
    "show_metadata_examples",
    "create_metadata_from_template",
    "fix_metadata_validation_issues",
    # Quilt summary (3 tools)
    "create_quilt_summary_files",
    "generate_quilt_summarize_json",
    "generate_package_visualizations",
    # Tabulator tools (6 tools)
    "tabulator_tables_list",
    "tabulator_table_create",
    "tabulator_table_delete",
    "tabulator_table_rename",
    "tabulator_open_query_status",
    "tabulator_open_query_toggle",
]
