"""Formatting utilities for Quilt MCP tools.

This module provides utilities for formatting data outputs in various formats,
with a focus on making tabular data more readable and user-friendly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
import logging
from itertools import islice

logger = logging.getLogger(__name__)


def format_as_table(
    data: Any,
    max_width: int = 120,
    max_rows: Optional[int] = None,
) -> str:
    """Format data as a readable ASCII table.

    Args:
        data: Data to format (DataFrame, list of dicts, or dict)
        max_width: Maximum width for the table
        max_rows: Maximum number of rows to display (None for all)

    Returns:
        Formatted table string
    """
    try:
        rows, columns = _normalize_tabular_data(data)
        if not rows or not columns:
            return str(data)

        if max_rows is not None and len(rows) > max_rows:
            display_rows = list(islice(rows, max_rows))
            truncated_msg = f"\n... ({len(rows) - max_rows} more rows)"
        else:
            display_rows = rows
            truncated_msg = ""

        formatted_rows = _stringify_rows(display_rows, columns)
        table_str = _render_ascii_table(formatted_rows, columns, max_width=max_width)

        if truncated_msg:
            table_str += truncated_msg

        return table_str

    except Exception as e:
        logger.error(f"Failed to format data as table: {e}")
        return f"Error formatting table: {str(e)}"


def should_use_table_format(data: Any, output_format: str = "auto", min_rows: int = 2, max_cols: int = 20) -> bool:
    """Determine if data should be formatted as a table.

    Args:
        data: Data to check
        output_format: Requested format ("auto", "table", "json", etc.)
        min_rows: Minimum rows to consider table formatting
        max_cols: Maximum columns for table formatting

    Returns:
        True if table formatting should be used
    """
    if output_format == "table":
        return True
    elif output_format != "auto":
        return False

    try:
        rows, columns = _normalize_tabular_data(data)
        if not rows or not columns:
            return False

        if len(rows) < min_rows or len(columns) > max_cols:
            return False

        return True

    except Exception:
        return False


def _normalize_tabular_data(data: Any) -> tuple[List[Dict[str, Any]], List[str]]:
    """
    Convert supported data structures into a list of dict rows and column names.
    """
    # Handle objects that look like DataFrames without importing pandas directly
    if hasattr(data, "to_dict") and callable(getattr(data, "to_dict")):
        try:
            records = data.to_dict(orient="records")  # type: ignore[call-arg]
            columns = list(getattr(data, "columns", [])) or (list(records[0].keys()) if records else [])
            return _ensure_record_dicts(records, columns), columns
        except Exception:
            pass

    if isinstance(data, list):
        if len(data) == 0:
            return [], []

        if all(isinstance(item, dict) for item in data):
            columns = list(data[0].keys())
            return _ensure_record_dicts(data, columns), columns

        if all(isinstance(item, (list, tuple)) for item in data):
            columns = [f"col_{index+1}" for index in range(len(data[0]))]
            records = [dict(zip(columns, row)) for row in data]
            return records, columns

    if isinstance(data, dict):
        columns = list(data.keys())
        return [dict(data)], columns

    return [], []


def _ensure_record_dicts(rows: Sequence[Dict[str, Any]], columns: List[str]) -> List[Dict[str, Any]]:
    """
    Ensure all rows are dictionaries with consistent keys.
    """
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        normalized.append({col: row.get(col) for col in columns})
    return normalized


def _stringify_rows(rows: List[Dict[str, Any]], columns: List[str]) -> List[List[str]]:
    """Convert rows into string matrix for rendering."""
    matrix: List[List[str]] = []
    for row in rows:
        matrix.append([_stringify_cell(row.get(col)) for col in columns])
    return matrix


def _stringify_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _render_ascii_table(rows: List[List[str]], columns: List[str], max_width: int) -> str:
    if not rows:
        return "No data to display"

    col_widths = [len(col) for col in columns]
    for row in rows:
        for idx, cell in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(cell))

    total_width = sum(col_widths) + 3 * (len(columns) - 1)
    if total_width > max_width:
        # Compute maximum width per column with a reasonable minimum
        available = max_width - 3 * (len(columns) - 1)
        max_col_width = max(8, available // len(columns))
        col_widths = [min(width, max_col_width) for width in col_widths]
        rows = [
            [
                cell if len(cell) <= col_widths[idx] else cell[: col_widths[idx] - 1] + "…"
                for idx, cell in enumerate(row)
            ]
            for row in rows
        ]
        columns = [
            col if len(col) <= col_widths[idx] else col[: col_widths[idx] - 1] + "…"
            for idx, col in enumerate(columns)
        ]

    header = " | ".join(col.ljust(col_widths[idx]) for idx, col in enumerate(columns))
    separator = "-+-".join("-" * col_widths[idx] for idx in range(len(columns)))
    body_lines = [
        " | ".join(cell.ljust(col_widths[idx]) for idx, cell in enumerate(row)) for row in rows
    ]

    return "\n".join([header, separator, *body_lines])


def enhance_result_with_table_format(result: Dict[str, Any]) -> Dict[str, Any]:
    """Enhance a result dictionary with table formatting when appropriate.

    Args:
        result: Result dictionary from a tool function

    Returns:
        Enhanced result with table formatting if applicable
    """
    if not result.get("success", False):
        return result

    # Look for tabular data in common fields
    tabular_fields = [
        "formatted_data",
        "data",
        "results",
        "tables",
        "workgroups",
        "databases",
    ]

    for field in tabular_fields:
        if field in result:
            data = result[field]

            # Skip if already formatted as CSV (which is table-like)
            if isinstance(data, str) and "\n" in data and "," in data:
                continue

            if should_use_table_format(data):
                table_str = format_as_table(data)
                result[f"{field}_table"] = table_str

                # For formatted_data, also set a display preference
                if field == "formatted_data":
                    result["display_format"] = "table"

    return result


def format_athena_results_as_table(result: Dict[str, Any]) -> Dict[str, Any]:
    """Specifically format Athena query results as tables when appropriate.

    Args:
        result: Athena query result dictionary

    Returns:
        Enhanced result with table formatting
    """
    if not result.get("success", False):
        return result

    # Check if we have formatted_data that should be displayed as a table
    if "formatted_data" in result:
        data = result["formatted_data"]

        # If it's CSV format, convert to table
        if isinstance(data, str) and result.get("format") == "csv":
            try:
                import io

                try:
                    import pandas as pd  # type: ignore
                except Exception:
                    logger.warning("pandas not available; displaying raw CSV string")
                    return result

                df = pd.read_csv(io.StringIO(data))
                table_str = format_as_table(df.to_dict(orient="records"))
                result["formatted_data_table"] = table_str
                result["display_format"] = "table"
            except Exception as e:
                logger.error(f"Failed to convert CSV to table: {e}")

        # If it's JSON format with tabular data, add table version
        elif isinstance(data, list) and should_use_table_format(data):
            table_str = format_as_table(data)
            result["formatted_data_table"] = table_str
            result["display_format"] = "table"

    return result


def format_users_as_table(result: Dict[str, Any]) -> Dict[str, Any]:
    """Format user list results with table display.

    Args:
        result: Result dictionary containing users list

    Returns:
        Enhanced result with formatted table
    """
    if not result.get("success") or not result.get("users"):
        return result

    try:
        users = result["users"]

        # Create a simplified view for table display
        table_data = []
        for user in users:
            table_data.append(
                {
                    "Name": user.get("name", ""),
                    "Email": user.get("email", ""),
                    "Active": "✓" if user.get("is_active") else "✗",
                    "Admin": "✓" if user.get("is_admin") else "✗",
                    "SSO Only": "✓" if user.get("is_sso_only") else "✗",
                    "Service": "✓" if user.get("is_service") else "✗",
                    "Role": user.get("role", ""),
                    "Extra Roles": (", ".join(user.get("extra_roles", [])) if user.get("extra_roles") else ""),
                    "Last Login": (user.get("last_login", "").split("T")[0] if user.get("last_login") else "Never"),
                }
            )

        # Generate table
        table_str = format_as_table(table_data, max_width=150)

        # Add table to result
        result["formatted_table"] = table_str
        result["display_hint"] = "Use formatted_table for better readability"

        return result

    except Exception as e:
        logger.warning(f"Failed to format users as table: {e}")
        return result


def format_roles_as_table(result: Dict[str, Any]) -> Dict[str, Any]:
    """Format role list results with table display.

    Args:
        result: Result dictionary containing roles list

    Returns:
        Enhanced result with formatted table
    """
    if not result.get("success") or not result.get("roles"):
        return result

    try:
        roles = result["roles"]

        # Create a simplified view for table display
        table_data = []
        for role in roles:
            table_data.append(
                {
                    "ID": role.get("id", ""),
                    "Name": role.get("name", ""),
                    "Type": role.get("type", ""),
                    "ARN": (
                        role.get("arn", "")[:60] + "..." if len(role.get("arn", "")) > 60 else role.get("arn", "")
                    ),
                }
            )

        # Generate table
        table_str = format_as_table(table_data, max_width=150)

        # Add table to result
        result["formatted_table"] = table_str
        result["display_hint"] = "Use formatted_table for better readability"

        return result

    except Exception as e:
        logger.warning(f"Failed to format roles as table: {e}")
        return result


def format_tabulator_results_as_table(result: Dict[str, Any]) -> Dict[str, Any]:
    """Format tabulator results as tables when appropriate.

    Args:
        result: Tabulator result dictionary

    Returns:
        Enhanced result with table formatting
    """
    if not result.get("success", False):
        return result

    # Format tables list
    if "tables" in result and isinstance(result["tables"], list):
        if should_use_table_format(result["tables"]):
            table_str = format_as_table(result["tables"])
            result["tables_table"] = table_str
            result["display_format"] = "table"

    # Format query rows
    if "rows" in result and isinstance(result["rows"], list):
        if should_use_table_format(result["rows"]):
            result["formatted_table"] = format_as_table(result["rows"])
            result.setdefault("display_format", "table")

    if "preview" in result and result.get("preview") and "formatted_table" in result:
        result.setdefault("preview_table", result["formatted_table"])

    return result
