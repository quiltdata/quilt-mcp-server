"""Tabulator query and admin operations.

This module provides Athena query operations and admin functionality for tabulator.
Table management operations have been migrated to TabulatorMixin in the backend layer.

Remaining functionality:
- Athena query operations (_tabulator_query, list_tabulator_buckets, tabulator_bucket_query)
- Admin operations (open query status and toggle)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

from quilt_mcp.services import auth_metadata
from quilt_mcp.services import athena_read_service as athena_glue
from quilt_mcp.utils import format_error_response

logger = logging.getLogger(__name__)

# Check admin availability directly
try:
    import quilt3.admin.tabulator

    ADMIN_AVAILABLE = True
except ImportError:
    ADMIN_AVAILABLE = False

if not ADMIN_AVAILABLE:
    logger.warning("quilt3.admin not available - admin tabulator functionality disabled")


class TabulatorService:
    """Service for tabulator admin operations.

    Note: Table management operations (list/create/update/delete/rename) have been
    migrated to TabulatorMixin. This service now only handles:
    - Open query admin operations
    """

    def __init__(self, use_quilt_auth: bool = True):
        self.use_quilt_auth = use_quilt_auth
        self.admin_available = ADMIN_AVAILABLE and use_quilt_auth

    def get_open_query_status(self) -> Dict[str, Any]:
        """Get tabulator open query status."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            import quilt3.admin.tabulator as admin_tabulator

            response = admin_tabulator.get_open_query()

            enabled = response.admin.tabulator_open_query if hasattr(response, "admin") else False
            return {
                "success": True,
                "open_query_enabled": enabled,
            }

        except Exception as exc:
            logger.error(f"Failed to get open query status: {exc}")
            return format_error_response(f"Failed to get open query status: {exc}")

    def set_open_query(self, enabled: bool) -> Dict[str, Any]:
        """Set tabulator open query status."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            import quilt3.admin.tabulator as admin_tabulator

            response = admin_tabulator.set_open_query(enabled=enabled)

            current = response.admin.tabulator_open_query if hasattr(response, "admin") else enabled
            return {
                "success": True,
                "open_query_enabled": current,
                "message": f"Open query {'enabled' if current else 'disabled'}",
            }

        except Exception as exc:
            logger.error(f"Failed to set open query status: {exc}")
            return format_error_response(f"Failed to set open query status: {exc}")


_tabulator_service: Optional[TabulatorService] = None


def get_tabulator_service() -> TabulatorService:
    """Get or create the tabulator service instance."""
    global _tabulator_service
    if _tabulator_service is None:
        _tabulator_service = TabulatorService()
    return _tabulator_service


def _tabulator_query(
    query: str,
    database_name: Optional[str] = None,
    workgroup_name: Optional[str] = None,
    max_results: int = 1000,
    output_format: Literal["json", "csv", "parquet", "table"] = "json",
    use_quilt_auth: bool = True,
) -> Dict[str, Any]:
    """Execute a query against the Tabulator catalog."""
    try:
        info = auth_metadata.catalog_info()
        if not info.get("tabulator_data_catalog"):
            return format_error_response(
                "tabulator_data_catalog not configured. This requires a Tabulator-enabled catalog. "
                "Check catalog configuration."
            )

        data_catalog_name = info["tabulator_data_catalog"]

        return athena_glue.athena_query_execute(
            query=query,
            database_name=database_name,
            workgroup_name=workgroup_name,
            data_catalog_name=data_catalog_name,
            max_results=max_results,
            output_format=output_format,
            use_quilt_auth=use_quilt_auth,
        )

    except Exception as exc:
        logger.error(f"Failed to execute tabulator query: {exc}")
        return format_error_response(f"Failed to execute tabulator query: {exc}")


def list_tabulator_buckets() -> Dict[str, Any]:
    """List all buckets (databases) in the Tabulator catalog."""
    try:
        result = _tabulator_query("SHOW DATABASES")

        if not result.get("success"):
            return result

        buckets: List[str] = []
        formatted_data = result.get("formatted_data", [])

        for row in formatted_data:
            bucket_name = row.get("database_name") or row.get("db_name") or row.get("name")
            if bucket_name:
                buckets.append(bucket_name)

        return {
            "success": True,
            "buckets": buckets,
            "count": len(buckets),
            "message": f"Found {len(buckets)} bucket(s) in Tabulator catalog",
        }

    except Exception as exc:
        logger.error(f"Failed to list tabulator buckets: {exc}")
        return format_error_response(f"Failed to list tabulator buckets: {exc}")


async def tabulator_buckets_list() -> Dict[str, Any]:
    """Async legacy wrapper for listing tabulator buckets."""
    return list_tabulator_buckets()


async def tabulator_bucket_query(
    bucket_name: str,
    query: str,
    workgroup_name: Optional[str] = None,
    max_results: int = 1000,
    output_format: Literal["json", "csv", "parquet", "table"] = "json",
    use_quilt_auth: bool = True,
) -> Dict[str, Any]:
    """Execute a bucket-scoped tabulator query (legacy tool signature)."""
    if not bucket_name or not bucket_name.strip():
        return format_error_response("bucket_name cannot be empty")
    if not query or not query.strip():
        return format_error_response("query cannot be empty")

    return _tabulator_query(
        query=query,
        database_name=bucket_name,
        workgroup_name=workgroup_name,
        max_results=max_results,
        output_format=output_format,
        use_quilt_auth=use_quilt_auth,
    )


__all__ = [
    "ADMIN_AVAILABLE",
    "TabulatorService",
    "get_tabulator_service",
    "list_tabulator_buckets",
    "tabulator_buckets_list",
    "tabulator_bucket_query",
    "_tabulator_query",
]
