from __future__ import annotations

# Re-export key APIs for IDEs and type checkers
from .quilt import (
    mcp,
    is_lambda_environment,
    set_lambda_mode,
    get_lambda_mode,
    check_quilt_auth,
    check_filesystem_access,
    list_packages,
    search_packages,
    browse_package,
    search_package_contents,
)

__all__ = [
    "mcp",
    "is_lambda_environment",
    "set_lambda_mode",
    "get_lambda_mode",
    "check_quilt_auth",
    "check_filesystem_access",
    "list_packages",
    "search_packages",
    "browse_package",
    "search_package_contents",
]
