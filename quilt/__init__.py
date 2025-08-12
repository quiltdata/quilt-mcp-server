from __future__ import annotations

# Re-export key APIs for IDEs and type checkers
from .quilt import mcp, is_lambda_environment  # shim provides core
from .constants import DEFAULT_REGISTRY, DEFAULT_BUCKET, KNOWN_TEST_PACKAGE, KNOWN_TEST_S3_OBJECT
from .tools.tools_auth import auth_check, filesystem_check
from .tools.tools_packages import (
    packages_list,
    packages_search,
    package_browse,
    package_contents_search,
)
from .tools.tools_package_ops import package_create, package_update
from .tools.tools_bucket import (
    bucket_objects_list,
    bucket_object_info,
    bucket_object_text,
    bucket_objects_put,
    bucket_object_fetch,
)

__all__ = [
    # Core objects
    "mcp",
    "is_lambda_environment",
    # Constants
    "DEFAULT_REGISTRY",
    "DEFAULT_BUCKET", 
    "KNOWN_TEST_PACKAGE",
    "KNOWN_TEST_S3_OBJECT",
    # Tools (alphabetical)
    "auth_check",
    "filesystem_check",
    "bucket_object_info",
    "bucket_object_text",
    "bucket_objects_list",
    "bucket_objects_put",
    "bucket_object_fetch",
    "package_browse",
    "package_contents_search",
    "package_create",
    "package_update",
    "packages_list",
    "packages_search",
]
