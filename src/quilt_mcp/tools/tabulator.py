"""Stateless tabulator tools backed by catalog APIs."""

from __future__ import annotations

import inspect
from typing import Any, Dict, List, Optional

from ..clients import catalog as catalog_client
from ..formatting import format_tabulator_results_as_table
from ..runtime import get_active_token
from ..utils import format_error_response, resolve_catalog_url
from ..types.navigation import NavigationContext, get_context_bucket

import logging

logger = logging.getLogger(__name__)

ADMIN_AVAILABLE = False


def _missing_prerequisites() -> Optional[Dict[str, Any]]:
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required for tabulator operations")

    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured for tabulator operations")

    return None


def _success(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload.setdefault("success", True)
    return payload


async def tabulator_tables_list(bucket_name: str) -> Dict[str, Any]:
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")

    prereq_error = _missing_prerequisites()
    if prereq_error:
        return prereq_error

    catalog_url = resolve_catalog_url()
    token = get_active_token()
    try:
        bucket_data = catalog_client.catalog_tabulator_tables_list(
            registry_url=catalog_url,
            bucket_name=bucket_name,
            auth_token=token,
        )
    except Exception as exc:
        return format_error_response(f"Failed to list tabulator tables: {exc}")

    tables = bucket_data.get("tabulatorTables") or []
    result = _success(
        {
            "bucket_name": bucket_name,
            "table_count": len(tables),
            "tables": tables,
        }
    )
    return format_tabulator_results_as_table(result)


async def tabulator_table_create(bucket_name: str, table_name: str, config_yaml: str) -> Dict[str, Any]:
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")
    if not table_name:
        return format_error_response("Table name cannot be empty")
    if not config_yaml:
        return format_error_response("Tabulator configuration cannot be empty")

    prereq_error = _missing_prerequisites()
    if prereq_error:
        return prereq_error

    catalog_url = resolve_catalog_url()
    token = get_active_token()

    try:
        bucket_data = catalog_client.catalog_tabulator_table_set(
            registry_url=catalog_url,
            bucket_name=bucket_name,
            table_name=table_name,
            config_yaml=config_yaml,
            auth_token=token,
        )
    except Exception as exc:
        return format_error_response(f"Failed to create tabulator table: {exc}")

    table = next(
        (t for t in bucket_data.get("tabulatorTables", []) if t.get("name") == table_name),
        None,
    )

    return _success(
        {
            "bucket_name": bucket_name,
            "table": table or {"name": table_name, "config": config_yaml},
            "message": f"Tabulator table '{table_name}' created successfully",
        }
    )


async def tabulator_table_delete(bucket_name: str, table_name: str) -> Dict[str, Any]:
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")
    if not table_name:
        return format_error_response("Table name cannot be empty")

    prereq_error = _missing_prerequisites()
    if prereq_error:
        return prereq_error

    catalog_url = resolve_catalog_url()
    token = get_active_token()

    try:
        bucket_data = catalog_client.catalog_tabulator_table_set(
            registry_url=catalog_url,
            bucket_name=bucket_name,
            table_name=table_name,
            config_yaml=None,
            auth_token=token,
        )
    except Exception as exc:
        return format_error_response(f"Failed to delete tabulator table '{table_name}': {exc}")

    remaining_tables = bucket_data.get("tabulatorTables", [])
    return _success(
        {
            "bucket_name": bucket_name,
            "table_name": table_name,
            "tables_remaining": len(remaining_tables),
            "message": f"Tabulator table '{table_name}' deleted successfully",
        }
    )


async def tabulator_table_rename(bucket_name: str, table_name: str, new_table_name: str) -> Dict[str, Any]:
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")
    if not table_name:
        return format_error_response("Current table name cannot be empty")
    if not new_table_name:
        return format_error_response("New table name cannot be empty")

    prereq_error = _missing_prerequisites()
    if prereq_error:
        return prereq_error

    catalog_url = resolve_catalog_url()
    token = get_active_token()

    try:
        bucket_data = catalog_client.catalog_tabulator_table_rename(
            registry_url=catalog_url,
            bucket_name=bucket_name,
            table_name=table_name,
            new_table_name=new_table_name,
            auth_token=token,
        )
    except Exception as exc:
        return format_error_response(f"Failed to rename tabulator table '{table_name}': {exc}")

    table = next(
        (t for t in bucket_data.get("tabulatorTables", []) if t.get("name") == new_table_name),
        None,
    )

    return _success(
        {
            "bucket_name": bucket_name,
            "old_table_name": table_name,
            "new_table_name": new_table_name,
            "table": table,
            "message": f"Tabulator table renamed from '{table_name}' to '{new_table_name}'",
        }
    )


async def tabulator_table_get(bucket_name: str, table_name: str) -> Dict[str, Any]:
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")
    if not table_name:
        return format_error_response("Table name cannot be empty")

    prereq_error = _missing_prerequisites()
    if prereq_error:
        return prereq_error

    catalog_url = resolve_catalog_url()
    token = get_active_token()

    try:
        bucket_data = catalog_client.catalog_tabulator_tables_list(
            registry_url=catalog_url,
            bucket_name=bucket_name,
            auth_token=token,
        )
    except Exception as exc:
        return format_error_response(f"Failed to fetch tabulator table '{table_name}': {exc}")

    table = next(
        (t for t in bucket_data.get("tabulatorTables", []) if t.get("name") == table_name),
        None,
    )

    if not table:
        return format_error_response(f"Tabulator table '{table_name}' not found in bucket '{bucket_name}'")

    return _success(
        {
            "bucket_name": bucket_name,
            "table": table,
        }
    )


async def tabulator_tables_overview() -> Dict[str, Any]:
    prereq_error = _missing_prerequisites()
    if prereq_error:
        return prereq_error

    catalog_url = resolve_catalog_url()
    token = get_active_token()

    try:
        bucket_configs = catalog_client.catalog_tabulator_buckets_with_tables(
            registry_url=catalog_url,
            auth_token=token,
        )
    except Exception as exc:
        return format_error_response(f"Failed to fetch tabulator overview: {exc}")

    buckets: list[Dict[str, Any]] = []
    for bucket in bucket_configs or []:
        tables = bucket.get("tabulatorTables") or []
        if not tables:
            continue
        buckets.append(
            {
                "bucket_name": bucket.get("name"),
                "table_count": len(tables),
                "tables": tables,
            }
        )

    return _success(
        {
            "bucket_count": len(buckets),
            "buckets": buckets,
        }
    )


async def tabulator_open_query_status() -> Dict[str, Any]:
    prereq_error = _missing_prerequisites()
    if prereq_error:
        return prereq_error

    catalog_url = resolve_catalog_url()
    token = get_active_token()

    try:
        enabled = catalog_client.catalog_tabulator_open_query_status(
            registry_url=catalog_url,
            auth_token=token,
        )
    except Exception as exc:
        return format_error_response(f"Failed to fetch tabulator open query status: {exc}")

    result = _success({"open_query_enabled": enabled})
    result["message"] = "Tabulator open query feature enabled"
    return result


async def tabulator_open_query_toggle(enabled: bool) -> Dict[str, Any]:
    if not isinstance(enabled, bool):
        return format_error_response("enabled must be a boolean value")

    prereq_error = _missing_prerequisites()
    if prereq_error:
        return prereq_error

    catalog_url = resolve_catalog_url()
    token = get_active_token()

    try:
        current = catalog_client.catalog_tabulator_open_query_set(
            registry_url=catalog_url,
            enabled=enabled,
            auth_token=token,
        )
    except Exception as exc:
        return format_error_response(f"Failed to update tabulator open query: {exc}")

    message = "Tabulator open query enabled" if current else "Tabulator open query disabled"
    return _success({"open_query_enabled": current, "message": message})


async def tabulator(
    action: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    _context: Optional[NavigationContext] = None,
) -> Dict[str, Any]:
    if action is None:
        return {
            "module": "tabulator",
            "actions": [
                "tables_list",
                "tables_overview",
                "table_create",
                "table_delete",
                "table_rename",
                "table_get",
                "open_query_status",
                "open_query_toggle",
            ],
        }

    params = dict(params or {})
    dispatch_map = {
        "tables_list": tabulator_tables_list,
        "tables_overview": tabulator_tables_overview,
        "table_create": tabulator_table_create,
        "table_delete": tabulator_table_delete,
        "table_rename": tabulator_table_rename,
        "table_get": tabulator_table_get,
        "open_query_status": tabulator_open_query_status,
        "open_query_toggle": tabulator_open_query_toggle,
    }

    func = dispatch_map.get(action)
    if func is None:
        return format_error_response(f"Unknown tabulator action: {action}")

    try:
        # Auto-infer bucket from navigation context when possible
        if action in {
            "tables_list",
            "table_create",
            "table_delete",
            "table_rename",
            "table_get",
        } and not params.get("bucket_name") and isinstance(_context, NavigationContext):
            inferred_bucket = get_context_bucket(_context)
            if inferred_bucket:
                params["bucket_name"] = inferred_bucket

        result = func(**params)
        if inspect.isawaitable(result):
            return await result
        return result
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Tabulator action %s failed", action)
        return format_error_response(f"Tabulator action failed: {exc}")
