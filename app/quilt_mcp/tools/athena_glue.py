from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import boto3
import time


def _athena_client():
    return boto3.client("athena")


def _glue_client():
    return boto3.client("glue")


def _escape_literal(value: Any) -> str:
    """Very simple SQL literal escaper for Athena. Strings are single-quoted and single quotes doubled.
    Numbers and booleans are returned as-is. None becomes NULL.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    # Treat everything else as string
    s = str(value).replace("'", "''")
    return f"'{s}'"


def _build_where_from_facets(facets: List[Dict[str, Any]]) -> str:
    """Build a SQL WHERE clause from a list of facet filters.

    Facet format examples:
    - {"field": "col", "op": "eq", "value": 5}
    - {"field": "col", "op": "in", "values": ["a", "b"]}
    - {"field": "col", "op": "between", "min": 1, "max": 10}
    - {"field": "col", "op": "like", "pattern": "%foo%"}
    - {"field": "col", "op": "gt"|"gte"|"lt"|"lte", "value": 3}
    Multiple facets are ANDed together.
    """
    if not facets:
        return ""

    clauses: List[str] = []
    for facet in facets:
        field = facet.get("field")
        op = str(facet.get("op", "eq")).lower()
        if not field:
            continue

        if op == "eq":
            clauses.append(f"({field} = {_escape_literal(facet.get('value'))})")
        elif op == "neq":
            clauses.append(f"({field} <> {_escape_literal(facet.get('value'))})")
        elif op == "in":
            values = facet.get("values") or []
            if values:
                literals = ", ".join(_escape_literal(v) for v in values)
                clauses.append(f"({field} IN ({literals}))")
        elif op == "between":
            clauses.append(
                f"({field} BETWEEN {_escape_literal(facet.get('min'))} AND {_escape_literal(facet.get('max'))})"
            )
        elif op == "gt":
            clauses.append(f"({field} > {_escape_literal(facet.get('value'))})")
        elif op == "gte":
            clauses.append(f"({field} >= {_escape_literal(facet.get('value'))})")
        elif op == "lt":
            clauses.append(f"({field} < {_escape_literal(facet.get('value'))})")
        elif op == "lte":
            clauses.append(f"({field} <= {_escape_literal(facet.get('value'))})")
        elif op == "like":
            pattern = facet.get("pattern")
            if pattern is None:
                pattern = facet.get("value")
            clauses.append(f"({field} LIKE {_escape_literal(pattern)})")
        elif op == "ilike":
            pattern = facet.get("pattern")
            if pattern is None:
                pattern = facet.get("value")
            clauses.append(f"(lower(cast({field} as varchar)) LIKE lower({_escape_literal(pattern)}))")
        else:
            # default to equality
            clauses.append(f"({field} = {_escape_literal(facet.get('value'))})")

    if not clauses:
        return ""
    return " WHERE " + " AND ".join(clauses)


def _poll_query_until_complete(client, query_execution_id: str, timeout_seconds: int = 300) -> Dict[str, Any]:
    start = time.time()
    while True:
        resp = client.get_query_execution(QueryExecutionId=query_execution_id)
        status = resp.get("QueryExecution", {}).get("Status", {}).get("State")
        if status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return resp
        if time.time() - start > timeout_seconds:
            raise TimeoutError(f"Athena query timed out after {timeout_seconds} seconds: {query_execution_id}")
        time.sleep(0.5)


def _collect_query_results(client, query_execution_id: str, max_rows: int = 1000) -> Tuple[List[str], List[Dict[str, Any]]]:
    paginator = client.get_paginator("get_query_results")
    columns: List[str] = []
    rows: List[Dict[str, Any]] = []
    first_page = True
    count = 0
    for page in paginator.paginate(QueryExecutionId=query_execution_id):
        result_set = page.get("ResultSet", {})
        result_rows = result_set.get("Rows", [])

        # The first row contains column metadata
        start_index = 0
        if first_page:
            metadata = result_set.get("ResultSetMetadata", {}).get("ColumnInfo", [])
            columns = [c.get("Name") for c in metadata]
            first_page = False
            # Skip header row if present (Athena includes header row in data)
            start_index = 1 if result_rows else 0

        for row in result_rows[start_index:]:
            data = [c.get("VarCharValue") for c in row.get("Data", [])]
            item = {columns[i]: data[i] if i < len(data) else None for i in range(len(columns))}
            rows.append(item)
            count += 1
            if count >= max_rows:
                return columns, rows

    return columns, rows


def athena_run_query(
    database: str,
    sql: str,
    workgroup: str = "primary",
    output_s3: Optional[str] = None,
    max_rows: int = 1000,
    timeout_seconds: int = 300,
) -> Dict[str, Any]:
    """Run an Athena SQL query and return rows and columns.

    Args:
        database: Athena database (Glue catalog) to run the query in
        sql: SQL statement
        workgroup: Athena workgroup
        output_s3: Optional S3 path for query results (if workgroup doesn't have one)
        max_rows: Maximum rows to return
        timeout_seconds: Maximum time to wait for query completion
    """
    client = _athena_client()
    start_args: Dict[str, Any] = {
        "QueryString": sql,
        "QueryExecutionContext": {"Database": database},
        "WorkGroup": workgroup,
    }
    if output_s3:
        start_args["ResultConfiguration"] = {"OutputLocation": output_s3}

    try:
        start_resp = client.start_query_execution(**start_args)
        qid = start_resp.get("QueryExecutionId")
        if not qid:
            return {"error": "Failed to start query"}
        exec_resp = _poll_query_until_complete(client, qid, timeout_seconds=timeout_seconds)
        state = exec_resp.get("QueryExecution", {}).get("Status", {}).get("State")
        if state != "SUCCEEDED":
            reason = exec_resp.get("QueryExecution", {}).get("Status", {}).get("StateChangeReason")
            return {"error": f"Query {state}: {reason}", "query_execution_id": qid}
        columns, rows = _collect_query_results(client, qid, max_rows=max_rows)
        return {
            "success": True,
            "query_execution_id": qid,
            "columns": columns,
            "rows": rows,
        }
    except Exception as e:
        return {"error": f"Athena query failed: {e}"}


def athena_query_by_facets(
    database: str,
    table: str,
    facets: List[Dict[str, Any]] | None = None,
    selected_columns: Optional[List[str]] = None,
    limit: int = 1000,
    workgroup: str = "primary",
) -> Dict[str, Any]:
    """Run a SELECT against a Glue table with a WHERE built from facets.

    Args:
        database: Glue database
        table: Glue table
        facets: List of facet filters
        selected_columns: Optional list of columns to project
        limit: Max rows to return
        workgroup: Athena workgroup
    """
    projection = ", ".join(selected_columns) if selected_columns else "*"
    where_clause = _build_where_from_facets(facets or [])
    sql = f"SELECT {projection} FROM {table}{where_clause} LIMIT {max(1, limit)}"
    return athena_run_query(database=database, sql=sql, workgroup=workgroup, max_rows=limit)


def glue_create_or_replace_view_from_facets(
    database: str,
    view_name: str,
    base_table: str,
    facets: List[Dict[str, Any]] | None = None,
    selected_columns: Optional[List[str]] = None,
    workgroup: str = "primary",
) -> Dict[str, Any]:
    """Create or replace an Athena view stored in Glue Catalog using facet filters.

    Args:
        database: Glue database
        view_name: Name of the view to create
        base_table: Source table
        facets: List of facet filters to apply in WHERE
        selected_columns: Columns to include in the view (default all)
        workgroup: Athena workgroup to use for DDL
    """
    projection = ", ".join(selected_columns) if selected_columns else "*"
    where_clause = _build_where_from_facets(facets or [])
    sql = f"CREATE OR REPLACE VIEW {view_name} AS SELECT {projection} FROM {base_table}{where_clause}"
    result = athena_run_query(database=database, sql=sql, workgroup=workgroup, max_rows=1)
    if result.get("error"):
        return result
    return {
        "success": True,
        "database": database,
        "view_name": view_name,
        "base_table": base_table,
        "facets": facets or [],
    }


def glue_get_table_schema(database: str, table: str) -> Dict[str, Any]:
    """Fetch column schema for a Glue table."""
    client = _glue_client()
    try:
        resp = client.get_table(DatabaseName=database, Name=table)
        sd = resp.get("Table", {}).get("StorageDescriptor", {})
        cols = sd.get("Columns", [])
        partitions = resp.get("Table", {}).get("PartitionKeys", [])
        columns = [
            {"name": c.get("Name"), "type": c.get("Type"), "comment": c.get("Comment")}
            for c in cols
        ]
        partition_columns = [
            {"name": c.get("Name"), "type": c.get("Type"), "comment": c.get("Comment")}
            for c in partitions
        ]
        return {
            "success": True,
            "database": database,
            "table": table,
            "columns": columns,
            "partition_columns": partition_columns,
        }
    except Exception as e:
        return {"error": f"Failed to fetch Glue table schema: {e}", "database": database, "table": table}


def _athena_to_tabulator_type(athena_type: str) -> Tuple[str, str]:
    """Map Athena/Glue types to Tabulator sorter and formatter types.

    Returns tuple of (sorter, hozAlign)
    """
    t = (athena_type or "").lower()
    if any(k in t for k in ["int", "bigint", "smallint", "integer"]):
        return "number", "right"
    if any(k in t for k in ["double", "float", "real", "decimal"]):
        return "number", "right"
    if t == "boolean":
        return "boolean", "center"
    if t in {"date"}:
        return "date", "left"
    if "timestamp" in t:
        return "datetime", "left"
    # arrays/maps/structs/strings -> sort as string
    return "string", "left"


def tabulator_schema_from_glue_table(database: str, table: str) -> Dict[str, Any]:
    """Build a Tabulator column schema from a Glue table definition."""
    schema = glue_get_table_schema(database, table)
    if schema.get("error"):
        return schema
    columns = []
    for col in schema.get("columns", []):
        name = col.get("name")
        type_str = col.get("type")
        sorter, align = _athena_to_tabulator_type(type_str)
        columns.append(
            {
                "field": name,
                "title": name,
                "sorter": sorter,
                "hozAlign": align,
                "headerFilter": True,
            }
        )
    return {"success": True, "columns": columns, "database": database, "table": table}


def tabulator_schema_from_rows(rows: List[Dict[str, Any]], sample_size: int = 100) -> Dict[str, Any]:
    """Infer a Tabulator schema from sample rows.

    This is a fallback when Glue schema is unavailable.
    """
    if not rows:
        return {"error": "No rows provided for schema inference"}
    sample = rows[:sample_size]
    # Collect types per field
    field_names = list(sample[0].keys())
    columns = []
    for name in field_names:
        # Inspect values for this column
        values = [r.get(name) for r in sample]
        inferred_type = "string"
        align = "left"
        if all(v is None or isinstance(v, (int, float)) for v in values):
            inferred_type = "number"
            align = "right"
        elif all(v is None or str(v).lower() in {"true", "false"} for v in values):
            inferred_type = "boolean"
            align = "center"
        elif all(v is None or _looks_like_iso_date(str(v)) for v in values):
            inferred_type = "date"
        elif all(v is None or _looks_like_iso_datetime(str(v)) for v in values):
            inferred_type = "datetime"

        columns.append(
            {
                "field": name,
                "title": name,
                "sorter": inferred_type,
                "hozAlign": align,
                "headerFilter": True,
            }
        )
    return {"success": True, "columns": columns}


def _looks_like_iso_date(value: str) -> bool:
    # Very light heuristic to avoid heavy parsing
    # e.g., 2024-01-31
    if len(value) >= 10 and value[4] == "-" and value[7] == "-":
        return True
    return False


def _looks_like_iso_datetime(value: str) -> bool:
    # e.g., 2024-01-31T12:34:56 or 2024-01-31 12:34:56
    return "T" in value or (len(value) >= 19 and value[10] == " ")

