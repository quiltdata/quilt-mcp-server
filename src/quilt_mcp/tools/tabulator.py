"""Stateless tabulator tools backed by catalog APIs."""

from __future__ import annotations

import inspect
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..clients import catalog as catalog_client
from ..formatting import format_tabulator_results_as_table
from ..runtime import get_active_token
from ..utils import format_error_response, resolve_catalog_url
from ..types.navigation import NavigationContext, get_context_bucket

import logging

logger = logging.getLogger(__name__)

ADMIN_AVAILABLE = False


def _normalize_query_rows(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    if not isinstance(payload, dict):
        return [], [], []

    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))

    errors = payload.get("errors")
    if errors:
        if isinstance(errors, list):
            message = "; ".join(str(err.get("message", err)) for err in errors)
        else:
            message = str(errors)
        raise RuntimeError(message)

    columns = payload.get("columns") or payload.get("columnNames") or []
    column_types = payload.get("columnTypes") or payload.get("types") or []

    candidate_keys = ["rows", "records", "items", "data", "results"]
    rows: Any = None
    for key in candidate_keys:
        if key in payload:
            rows = payload[key]
            break

    if rows is None and isinstance(payload.get("data"), dict):
        nested = payload.get("data")
        for key in candidate_keys:
            if key in nested:
                rows = nested[key]
                break

    normalized: List[Dict[str, Any]] = []
    if isinstance(rows, list):
        if rows and isinstance(rows[0], dict):
            normalized = rows
            if not columns:
                columns = list(rows[0].keys())
        elif columns:
            normalized = [dict(zip(columns, row)) for row in rows]
        else:
            normalized = [{"value": row} for row in rows]
            columns = ["value"]
    elif isinstance(rows, dict):
        for key in candidate_keys:
            nested = rows.get(key)
            if isinstance(nested, list):
                return _normalize_query_rows({"columns": columns, key: nested})

    return normalized, columns, column_types


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


async def tabulator_table_query(
    bucket_name: str,
    table_name: str,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
    filters: Optional[Dict[str, Any]] = None,
    order_by: Optional[str] = None,
    selects: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    if not bucket_name:
        return format_error_response("Bucket name cannot be empty")
    if not table_name:
        return format_error_response("Table name cannot be empty")
    if limit is not None and (not isinstance(limit, int) or limit <= 0):
        return format_error_response("limit must be a positive integer if provided")
    if offset < 0:
        return format_error_response("offset cannot be negative")

    prereq_error = _missing_prerequisites()
    if prereq_error:
        return prereq_error

    catalog_url = resolve_catalog_url()
    token = get_active_token()

    try:
        response = catalog_client.catalog_tabulator_query(
            registry_url=catalog_url,
            bucket_name=bucket_name,
            table_name=table_name,
            limit=limit,
            offset=offset,
            filters=filters,
            order_by=order_by,
            selects=selects,
            auth_token=token,
        )
    except Exception as exc:
        return format_error_response(f"Failed to query tabulator table '{table_name}': {exc}")

    try:
        rows, columns, column_types = _normalize_query_rows(response)
    except Exception as exc:
        return format_error_response(f"Failed to normalize tabulator results: {exc}")

    result = _success(
        {
            "bucket_name": bucket_name,
            "table_name": table_name,
            "rows": rows,
            "columns": columns,
            "column_types": column_types,
            "row_count": len(rows),
            "limit": limit,
            "offset": offset,
            "next_offset": response.get("nextOffset") or response.get("next_offset"),
            "total_rows": response.get("totalRows")
            or response.get("total")
            or response.get("rowCount"),
            "metadata": response.get("metadata") or response.get("stats"),
            "raw_response": response,
        }
    )

    if filters:
        result["filters"] = filters
    if order_by:
        result["order_by"] = order_by
    if selects:
        result["selects"] = list(selects)

    return format_tabulator_results_as_table(result)


async def tabulator_table_preview(
    bucket_name: str,
    table_name: str,
    *,
    limit: int = 10,
    offset: int = 0,
    filters: Optional[Dict[str, Any]] = None,
    selects: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    preview_result = await tabulator_table_query(
        bucket_name=bucket_name,
        table_name=table_name,
        limit=limit,
        offset=offset,
        filters=filters,
        selects=selects,
    )

    if preview_result.get("success"):
        preview_result["preview"] = True

    return preview_result


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
    """
    Tabulator operations for querying tabular data across Quilt packages.
    
    Tabulator aggregates tabular data objects (CSV, TSV, Parquet) across multiple packages
    using AWS Athena. Admins define schemas and data sources, and users can run SQL queries
    directly on package contents.
    
    **Key Concepts:**
    - **Schema**: Defines table columns with names (lowercase, letters/numbers/underscores only)
      and types (BOOLEAN, INT, FLOAT, DOUBLE, STRING, DATE, TIMESTAMP, etc.)
    - **Source**: Defines which packages and objects to query using regex patterns with named 
      capture groups
    - **Parser**: Defines how to read files (csv/tsv with delimiter, or parquet)
    - **Auto-added Columns**: $pkg_name, $logical_key, $physical_key, $top_hash, $issue
    
    **Configuration YAML Example:**
    ```yaml
    schema:
      - name: sample_id    # column names must be lowercase letters/numbers/underscores
        type: STRING
      - name: tpm
        type: FLOAT
    source:
      type: quilt-packages  # currently the only supported type
      package_name: "^namespace/(?P<study_id>[^_]+)_.*$"  # regex with named capture groups
      logical_key: "data/(?P<sample_id>[^/]+)_genes\\.sf$"  # named groups become columns
    parser:
      format: csv  # or tsv, parquet
      delimiter: "\\t"  # for TSV, use tab delimiter
      header: true  # set to true if CSV/TSV has column headers
    continue_on_error: true  # skip files with errors (Quilt 1.58+)
    ```
    
    **Common Configuration Errors & Fixes:**
    
    1. **"INVALID_FUNCTION_ARGUMENT: undefined group option"**
       - **Cause**: Lambda DataFusion version too old for Parquet encoding
       - **Fix**: Contact Quilt support to update Lambda, or use direct Athena queries
    
    2. **Schema mismatch errors**
       - **Cause**: CSV/TSV column names don't match schema, or wrong case in Parquet
       - **Fix**: 
         - CSV/TSV: Names in schema don't need to match file columns (positional mapping)
         - Parquet: Names must match except for case
         - If files have headers, set `header: true` in parser config
    
    3. **Named capture groups not working**
       - **Cause**: Incorrect regex syntax or missing `?P<name>` syntax
       - **Fix**: Use `(?P<column_name>pattern)` syntax in package_name or logical_key
    
    4. **Memory/size errors**
       - **Cause**: Files too large (>10GB), rows too large (>100KB), or too many files (>10K)
       - **Fix**: Use `continue_on_error: true` and filter queries, or break data into smaller files
    
    **Querying Tabulator Tables:**
    
    Tables are accessed via special Athena databases. The fully qualified table name format is:
    ```
    "<stack>-tabulator"."<bucket_name>"."<table_name>"
    ```
    
    Example queries:
    ```sql
    -- Basic query
    SELECT * FROM "quilt-prod-tabulator"."my-bucket"."my-table" LIMIT 10;
    
    -- Using auto-added columns
    SELECT $pkg_name, $logical_key, sample_id, tpm
    FROM "quilt-prod-tabulator"."my-bucket"."rnaseq-data"
    WHERE study_id = 'STUDY001';
    
    -- Join with package metadata
    SELECT t.*, p.user_meta
    FROM "quilt-prod-tabulator"."my-bucket"."my-table" t
    JOIN "athena-db"."my-bucket_packages-view" p
    ON t.$pkg_name = p.pkg_name;
    ```
    
    **Important Notes:**
    - Schema consistency: All matching files must have the same schema (unless using 
      `continue_on_error: true` with Quilt 1.58+)
    - Column names: Must match `^[a-z_][a-z0-9_]*$` (lowercase, start with letter/underscore)
    - Named capture groups from regex patterns become additional columns
    - Open query mode (admin setting) allows access from external tools like Tableau
    
    Available actions:
    - tables_list: List all tabulator tables in a bucket
    - tables_overview: Get overview of all tables across all buckets
    - table_create: Create a new tabulator table with YAML configuration
    - table_delete: Delete a tabulator table
    - table_rename: Rename a tabulator table
    - table_get: Get configuration for a specific table
    - table_query: Execute a query against a tabulator table
    - table_preview: Preview first N rows of a table (convenience wrapper for query)
    - open_query_status: Check if open query mode is enabled
    - open_query_toggle: Enable/disable open query mode (admin only)
    
    Args:
        action: The tabulator operation to perform. If None, returns available actions.
        params: Action-specific parameters
        _context: Navigation context (optional, auto-infers bucket when available)
    
    Returns:
        Action-specific response dictionary
    
    Examples:
        # Discovery mode
        result = tabulator()
        
        # List tables in a bucket
        result = tabulator(action="tables_list", params={"bucket_name": "my-bucket"})
        
        # Create a table
        result = tabulator(action="table_create", params={
            "bucket_name": "my-bucket",
            "table_name": "rnaseq-data",
            "config_yaml": '''
schema:
  - name: sample_id
    type: STRING
  - name: gene_name
    type: STRING
  - name: tpm
    type: FLOAT
source:
  type: quilt-packages
  package_name: "^rnaseq/.*$"
  logical_key: "quantification/(?P<sample_id>[^/]+)_genes\\.sf$"
parser:
  format: csv
  delimiter: "\\t"
  header: true
'''
        })
        
        # Query a table
        result = tabulator(action="table_query", params={
            "bucket_name": "my-bucket",
            "table_name": "rnaseq-data",
            "limit": 100,
            "filters": {"sample_id": "SAMPLE001"}
        })
        
        # Preview a table
        result = tabulator(action="table_preview", params={
            "bucket_name": "my-bucket",
            "table_name": "rnaseq-data",
            "limit": 10
        })
    
    For detailed parameter documentation, see individual action functions.
    """
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
                "table_query",
                "table_preview",
                "open_query_status",
                "open_query_toggle",
            ],
            "documentation": "See tabulator docstring for comprehensive configuration guide and examples"
        }

    # Handle case where params is a JSON string instead of a dict
    # This can happen when the MCP client/LLM serializes the params
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except json.JSONDecodeError as exc:
            return format_error_response(f"Invalid JSON in params: {exc}")

    params = dict(params or {})
    dispatch_map = {
        "tables_list": tabulator_tables_list,
        "tables_overview": tabulator_tables_overview,
        "table_create": tabulator_table_create,
        "table_delete": tabulator_table_delete,
        "table_rename": tabulator_table_rename,
        "table_get": tabulator_table_get,
        "table_query": tabulator_table_query,
        "table_preview": tabulator_table_preview,
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
            "table_query",
            "table_preview",
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
