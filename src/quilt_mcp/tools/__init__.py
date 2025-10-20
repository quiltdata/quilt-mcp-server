"""MCP tools for Quilt data access.

This package contains all the MCP tool implementations organized by functionality:
- catalog: Catalog configuration and URL generation
- buckets: S3 bucket operations
- packages: Package browsing, creation, update, deletion, and S3-to-package ingestion
- athena_glue: AWS Athena queries and Glue Data Catalog discovery
- tabulator: Quilt tabulator table management for SQL querying across packages
- data_visualization: Create visualizations from data
- quilt_summary: Generate package summary files
- search: Unified search across catalogs, packages, buckets (includes GraphQL queries)
- workflow_orchestration: Workflow orchestration and status tracking
- governance: Governance policies and compliance

These tools are pure functions that are registered by the tools module.

Example usage:
    from quilt_mcp.tools import catalog, buckets, packages

    # Use catalog tools
    url = catalog.catalog_url("s3://my-bucket", "user/package")

    # Use bucket tools
    objects = buckets.bucket_objects_list("my-bucket")

    # Use package tools
    pkg_list = packages.packages_list()
"""

from importlib import import_module
from types import ModuleType
from typing import Dict

_MODULE_PATHS = {
    "catalog": "quilt_mcp.tools.catalog",
    "buckets": "quilt_mcp.tools.buckets",
    "packages": "quilt_mcp.tools.packages",
    "quilt_summary": "quilt_mcp.tools.quilt_summary",
    "search": "quilt_mcp.tools.search",
    "data_visualization": "quilt_mcp.tools.data_visualization",
    "athena_glue": "quilt_mcp.services.athena_read_service",
    "tabulator": "quilt_mcp.services.tabulator_service",
    "workflow_orchestration": "quilt_mcp.services.workflow_service",
    "governance": "quilt_mcp.services.governance_service",
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
