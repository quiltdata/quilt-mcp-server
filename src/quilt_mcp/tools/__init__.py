"""MCP tools for Quilt data access.

This package contains all the MCP tool implementations organized by functionality:
- auth: Authentication and filesystem checks
- buckets: S3 bucket operations
- packages: Package browsing and search
- package_ops: Package creation, update, and deletion
- s3_package: S3-to-package creation functionality
- permissions: AWS permissions discovery and bucket recommendations
- unified_package: Simplified, intelligent package creation interface
- metadata_templates: Metadata templates and validation utilities
- package_management: Enhanced package management with better UX
- athena_glue: AWS Athena queries and Glue Data Catalog discovery
- tabulator: Quilt tabulator table management for SQL querying across packages

These tools are pure functions that are registered by the tools module.

Example usage:
    from quilt_mcp.tools import auth, buckets, packages, package_ops

    # Use auth tools
    status = auth.auth_status()

    # Use bucket tools
    objects = buckets.bucket_objects_list("my-bucket")

    # Use package tools
    pkg_list = packages.packages_list()
"""

from importlib import import_module
from types import ModuleType
from typing import Dict

_MODULE_PATHS = {
    "auth": "quilt_mcp.tools.auth",
    "buckets": "quilt_mcp.tools.buckets",
    "packages": "quilt_mcp.tools.packages",
    "package_ops": "quilt_mcp.tools.package_ops",
    "s3_package": "quilt_mcp.tools.s3_package",
    "permissions": "quilt_mcp.tools.permissions",
    "unified_package": "quilt_mcp.tools.unified_package",
    "metadata_templates": "quilt_mcp.tools.metadata_templates",
    "package_management": "quilt_mcp.tools.package_management",
    "metadata_examples": "quilt_mcp.tools.metadata_examples",
    "quilt_summary": "quilt_mcp.tools.quilt_summary",
    "graphql": "quilt_mcp.tools.graphql",
    "search": "quilt_mcp.tools.search",
    "data_visualization": "quilt_mcp.tools.data_visualization",
    "athena_glue": "quilt_mcp.tools.athena_glue",
    "tabulator": "quilt_mcp.tools.tabulator",
    "workflow_orchestration": "quilt_mcp.tools.workflow_orchestration",
    "governance": "quilt_mcp.tools.governance",
    # error_recovery temporarily disabled due to Callable parameter issues
}

AVAILABLE_MODULES = list(_MODULE_PATHS.keys())
__all__ = AVAILABLE_MODULES.copy()

_LOADED_MODULES: Dict[str, ModuleType] = {}


def __getattr__(name: str) -> ModuleType:
    if name not in _MODULE_PATHS:
        raise AttributeError(f"module 'quilt_mcp.tools' has no attribute '{name}'")
    if name not in _LOADED_MODULES:
        _LOADED_MODULES[name] = import_module(_MODULE_PATHS[name])
    return _LOADED_MODULES[name]


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + AVAILABLE_MODULES)
