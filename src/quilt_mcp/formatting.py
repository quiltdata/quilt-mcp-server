"""Formatting utilities for Quilt MCP tools.

This module provides utilities for formatting data outputs in various formats,
with a focus on making tabular data more readable and user-friendly.
"""

from __future__ import annotations

import pandas as pd
from typing import Any, Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


def format_as_table(
    data: pd.DataFrame | List[Dict[str, Any]] | Dict[str, Any],
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
        # Convert input to DataFrame
        if isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            # Handle single record or nested structure
            if all(isinstance(v, (str, int, float, bool, type(None))) for v in data.values()):
                # Single record
                df = pd.DataFrame([data])
            else:
                # Try to flatten or convert to records
                df = pd.DataFrame(data)
        else:
            return str(data)  # Fallback to string representation

        if df.empty:
            return "No data to display"

        # Limit rows if specified
        if max_rows and len(df) > max_rows:
            df_display = df.head(max_rows)
            truncated_msg = f"\n... ({len(df) - max_rows} more rows)"
        else:
            df_display = df
            truncated_msg = ""

        # Format the table with pandas styling
        try:
            # Create a copy of the dataframe and sanitize string values
            df_safe = df_display.copy()
            for col in df_safe.columns:
                if df_safe[col].dtype == "object":  # String columns
                    df_safe[col] = df_safe[col].astype(str).str.replace("%", "%%", regex=False)

            table_str = df_safe.to_string(index=False, max_cols=None, max_colwidth=30, justify="left")
        except (ValueError, TypeError) as e:
            # Handle formatting issues with special characters
            logger.warning(f"Table formatting failed, using simple representation: {e}")
            try:
                # Fallback: convert to simple string representation
                table_str = str(df_display.values.tolist())
            except Exception:
                table_str = f"[Data display error: {len(df_display)} rows x {len(df_display.columns)} columns]"

        # Add truncation message if needed
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
        # Check if data is tabular
        if isinstance(data, pd.DataFrame):
            return len(data) >= min_rows and len(data.columns) <= max_cols
        elif isinstance(data, list) and len(data) >= min_rows:
            if all(isinstance(item, dict) for item in data):
                # Check if all dicts have similar structure
                if len(data) > 0:
                    first_keys = set(data[0].keys())
                    return len(first_keys) <= max_cols and all(
                        set(item.keys()) == first_keys for item in data[:5]
                    )  # Check first 5

        return False

    except Exception:
        return False


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
                # Parse CSV string back to DataFrame for table formatting
                import io

                df = pd.read_csv(io.StringIO(data))
                table_str = format_as_table(df)
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

    return result
