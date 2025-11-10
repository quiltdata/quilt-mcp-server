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
from .tools.catalog import (
    catalog_uri,
    catalog_url,
    catalog_configure,
)
from .services.auth_metadata import (
    auth_status,
    catalog_info,
    filesystem_status,
)
from .tools.buckets import (
    bucket_object_fetch,
    bucket_object_info,
    bucket_object_link,
    bucket_object_text,
    bucket_objects_list,
    bucket_objects_put,
)
from .services.permissions_service import (
    bucket_recommendations_get,
    check_bucket_access as bucket_access_check,
    discover_permissions as aws_permissions_discover,
)
from .services.metadata_service import (
    create_metadata_from_template,
    fix_metadata_validation_issues,
    get_metadata_template,
    list_metadata_templates,
    show_metadata_examples,
    validate_metadata_structure,
)
from .tools.quilt_summary import (
    create_quilt_summary_files,
    generate_quilt_summarize_json,
    generate_package_visualizations,
)
from .tools.packages import (
    package_browse,
    package_create,
    package_create_from_s3,
    package_delete,
    package_diff,
    package_update,
    packages_list,
)
from .services.tabulator_service import (
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
    # Auth tools
    "auth_status",
    "catalog_info",
    "catalog_url",
    "catalog_uri",
    "catalog_configure",
    "filesystem_status",
    # Bucket tools
    "bucket_object_info",
    "bucket_object_text",
    "bucket_objects_list",
    "bucket_objects_put",
    "bucket_object_fetch",
    "bucket_object_link",
    # Package tools
    "package_browse",
    "package_create",
    "package_create_from_s3",
    "package_delete",
    "package_diff",
    "package_update",
    "packages_list",
    # Permission tools
    "aws_permissions_discover",
    "bucket_access_check",
    "bucket_recommendations_get",
    # Metadata helpers
    "get_metadata_template",
    "list_metadata_templates",
    "validate_metadata_structure",
    # Metadata examples and guidance
    "show_metadata_examples",
    "create_metadata_from_template",
    "fix_metadata_validation_issues",
    # Quilt summary and visualization tools
    "create_quilt_summary_files",
    "generate_quilt_summarize_json",
    "generate_package_visualizations",
    # Tabulator tools
    "tabulator_tables_list",
    "tabulator_table_create",
    "tabulator_table_delete",
    "tabulator_table_rename",
    "tabulator_open_query_status",
    "tabulator_open_query_toggle",
]
