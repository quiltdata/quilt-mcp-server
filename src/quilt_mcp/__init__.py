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

# Re-export the main server instance and core utilities
from .server import is_lambda_environment, mcp

# Re-export all tools for easy access
from .tools.auth import auth_status, filesystem_status, catalog_info, catalog_name, catalog_url, catalog_uri
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
from .tools.packages import (
    package_browse,
    package_contents_search,
    package_diff,
    packages_list,
    packages_search,
)

__version__ = "0.1.0"

__all__ = [
    # Core
    "mcp",
    "is_lambda_environment",
    # Constants
    "DEFAULT_REGISTRY",
    "DEFAULT_BUCKET",
    "KNOWN_TEST_PACKAGE",
    "KNOWN_TEST_ENTRY",
    "KNOWN_TEST_S3_OBJECT",
    # Auth tools
    "auth_status",
    "filesystem_status",
    "catalog_info",
    "catalog_name", 
    "catalog_url",
    "catalog_uri",
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
    "package_delete",
    "package_diff",
    "package_update",
    "packages_list",
    "packages_search",
]
