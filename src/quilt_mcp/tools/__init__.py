"""MCP tools for Quilt data access.

This package contains all the MCP tool implementations organized by functionality:
- catalog: Catalog configuration, status, and onboarding
- buckets: S3 bucket operations
- packages: Package browsing and search
- package_creation: Package creation workflows
- permissions: AWS permissions discovery and bucket recommendations
- metadata_templates: Metadata templates and validation utilities
- athena_glue: AWS Athena queries and Glue Data Catalog discovery
- tabulator: Quilt tabulator table management for SQL querying across packages

These tools are pure functions that are registered by the tools module.

Example usage:
    from quilt_mcp.tools import catalog, buckets, packages, package_creation

    # Use catalog tools
    status = catalog.catalog_status()

    # Use bucket tools
    objects = buckets.bucket_objects_list("my-bucket")

    # Use package tools
    pkg_list = packages.packages_list()
"""

from . import (
    catalog,
    buckets,
    package_creation,
    packages,
    permissions,
    metadata_templates,
    metadata_examples,
    quilt_summary,
    graphql,
    search,
    athena_glue,
    tabulator,
    workflow_orchestration,
    governance,
)

# error_recovery temporarily disabled due to Callable parameter issues

__all__ = [
    "catalog",
    "buckets",
    "packages",
    "package_creation",
    "permissions",
    "metadata_templates",
    "metadata_examples",
    "quilt_summary",
    "graphql",
    "search",
    "athena_glue",
    "tabulator",
    "workflow_orchestration",
    "governance",
]
