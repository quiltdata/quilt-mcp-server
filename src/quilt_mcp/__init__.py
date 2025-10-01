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
    catalog_status,
    catalog_info,
    catalog_uri,
    catalog_url,
    filesystem_status,
    catalog_set,
    quick_start,
)
from .tools.buckets import (
    bucket_object_fetch,
    bucket_object_info,
    bucket_object_link,
    bucket_object_text,
    bucket_objects_list,
    bucket_objects_put,
)
from .tools.permissions import (
    aws_permissions_discover,
    bucket_access_check,
    bucket_recommendations_get,
)
from .tools.package_creation import (
    package_create,
    package_create_from_s3,
    package_delete,
    package_validate,
)
from .tools.metadata_templates import (
    metadata_template_get,
    metadata_validate_structure,
)
from .tools.metadata_examples import (
    metadata_template_create,
)
from .tools.governance import (
    admin_tabulator_access_get,
    admin_tabulator_access_set,
)
from .tools.quilt_summary import (
    create_quilt_summary_files,
    generate_quilt_summarize_json,
    generate_package_visualizations,
)
from .tools.search import (
    catalog_search,
    catalog_search_explain,
    catalog_search_suggest,
)
from .tools.packages import (
    package_browse,
    package_contents_search,
    package_diff,
    packages_list,
)
from .tools.tabulator import (
    tabulator_table_create,
    tabulator_table_delete,
    tabulator_table_rename,
)
from .tools.workflow_orchestration import (
    workflow_create,
    workflow_step_add,
    workflow_step_update,
    workflow_status_get,
    workflow_template_apply,
)

__version__ = "0.5.6"

__all__ = [
    # Constants
    "DEFAULT_REGISTRY",
    "DEFAULT_BUCKET",
    "KNOWN_TEST_PACKAGE",
    "KNOWN_TEST_ENTRY",
    "KNOWN_TEST_S3_OBJECT",
    # Public tools (alphabetical)
    "aws_permissions_discover",
    "bucket_access_check",
    "bucket_object_fetch",
    "bucket_object_info",
    "bucket_object_link",
    "bucket_object_text",
    "bucket_objects_list",
    "bucket_objects_put",
    "bucket_recommendations_get",
    "catalog_info",
    "catalog_search",
    "catalog_search_explain",
    "catalog_search_suggest",
    "catalog_set",
    "catalog_status",
    "catalog_uri",
    "catalog_url",
    "create_quilt_summary_files",
    "filesystem_status",
    "generate_package_visualizations",
    "generate_quilt_summarize_json",
    "metadata_template_create",
    "metadata_template_get",
    "metadata_validate_structure",
    "package_browse",
    "package_contents_search",
    "package_create",
    "package_create_from_s3",
    "package_delete",
    "package_diff",
    "package_validate",
    "packages_list",
    "quick_start",
    "tabulator_table_create",
    "tabulator_table_delete",
    "tabulator_table_rename",
    "workflow_create",
    "workflow_status_get",
    "workflow_step_add",
    "workflow_step_update",
    "workflow_template_apply",
    # Admin tools (must be last)
    "admin_tabulator_access_get",
    "admin_tabulator_access_set",
]
