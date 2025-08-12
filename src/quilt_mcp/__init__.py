"""Quilt MCP Server - A secure MCP server for accessing Quilt data.

This package provides Model Context Protocol (MCP) tools for interacting with
Quilt packages and S3 buckets through a secure, authenticated interface.
"""

from __future__ import annotations

# Re-export the main server instance and core utilities
from .server import mcp, is_lambda_environment
from .constants import (
    DEFAULT_REGISTRY,
    DEFAULT_BUCKET, 
    KNOWN_TEST_PACKAGE,
    KNOWN_TEST_ENTRY,
    KNOWN_TEST_S3_OBJECT
)

# Re-export all tools for easy access
from .tools.auth import auth_check, filesystem_check
from .tools.packages import (
    packages_list,
    packages_search,
    package_browse,
    package_contents_search,
)
from .tools.package_ops import package_create, package_update, package_delete
from .tools.buckets import (
    bucket_objects_list,
    bucket_object_info,
    bucket_object_text,
    bucket_objects_put,
    bucket_object_fetch,
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
    "auth_check",
    "filesystem_check",
    # Bucket tools
    "bucket_object_info",
    "bucket_object_text",
    "bucket_objects_list",
    "bucket_objects_put",
    "bucket_object_fetch",
    # Package tools
    "package_browse",
    "package_contents_search",
    "package_create",
    "package_delete",
    "package_update",
    "packages_list",
    "packages_search",
]