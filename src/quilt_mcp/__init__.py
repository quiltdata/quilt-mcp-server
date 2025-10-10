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
    bucket_objects_list,
    bucket_objects_put,
    bucket_objects_search,
)
from .tools.package_ops import package_create, package_delete, package_update
from .tools.s3_package import package_create_from_s3
from .tools.permissions import (
    aws_permissions_discover,
    bucket_access_check,
    bucket_recommendations_get,
)
from .tools.unified_package import (
    create_package,
    list_available_resources,
    quick_start,
)
from .tools.metadata_templates import (
    get_metadata_template,
    list_metadata_templates,
    validate_metadata_structure,
)
from .tools.package_management import (
    create_package_enhanced,
    package_update_metadata,
    package_validate,
    list_package_tools,
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
from .tools.packages import (
    package_browse,
    package_contents_search,
    package_diff,
    packages_list,
    packages_search,
)
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
    # Auth tools
    "auth_status",
    "catalog_info",
    "catalog_name",
    "catalog_url",
    "catalog_uri",
    "configure_catalog",
    "filesystem_status",
    "switch_catalog",
    # Bucket tools
    "bucket_object_info",
    "bucket_object_text",
    "bucket_objects_list",
    "bucket_objects_put",
    "bucket_object_fetch",
    "bucket_object_link",
    "bucket_objects_search",
    # Package tools
    "package_browse",
    "package_contents_search",
    "package_create",
    "package_create_from_s3",
    "package_delete",
    "package_diff",
    "package_update",
    "packages_list",
    "packages_search",
    # Permission tools
    "aws_permissions_discover",
    "bucket_access_check",
    "bucket_recommendations_get",
    # Unified tools
    "create_package",
    "list_available_resources",
    "quick_start",
    # Enhanced package management
    "create_package_enhanced",
    "get_metadata_template",
    "list_metadata_templates",
    "list_package_tools",
    "package_update_metadata",
    "package_validate",
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
