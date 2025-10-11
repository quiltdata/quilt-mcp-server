"""
AWS Athena and Glue Data Catalog Tools

This module provides MCP tools for querying AWS Athena and discovering
metadata from AWS Glue Data Catalog using SQLAlchemy and PyAthena.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from ..services.athena_service import AthenaQueryService
from ..utils import format_error_response

logger = logging.getLogger(__name__)


def _sanitize_query_for_logging(query: str) -> str:
    """Sanitize query string to prevent formatting issues in logging."""
    # Replace % with %% to prevent string formatting issues
    return query.replace("%", "%%")


def _suggest_query_fix(query: str, error_message: str) -> str:
    """Suggest fixes for common query issues."""
    suggestions = []

    if "mismatched input" in error_message and "-" in query:
        suggestions.append("Try wrapping database/table names with hyphens in double quotes")

    if "TABLE_NOT_FOUND" in error_message:
        suggestions.append(
            "Use 'SHOW DATABASES' and 'SELECT table_name FROM information_schema.tables' to discover tables"
        )

    if "%" in query and "format string" in error_message:
        suggestions.append("Queries with '%' characters may cause formatting issues - try using different patterns")

    if suggestions:
        return " Suggestions: " + "; ".join(suggestions)
    return ""


def athena_databases_list(
    data_catalog_name: str = "AwsDataCatalog",
    service: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    List available databases in AWS Glue Data Catalog.

    Args:
        data_catalog_name: Name of the data catalog (default: AwsDataCatalog)

    Returns:
        List of databases with metadata
    """
    try:
        if service is None:
            service = AthenaQueryService(data_catalog_name=data_catalog_name)
        return service.discover_databases(data_catalog_name=data_catalog_name)
    except Exception as e:
        logger.error(f"Failed to list databases: {e}")
        return format_error_response(f"Failed to list databases: {str(e)}")


def athena_tables_list(
    database_name: str,
    data_catalog_name: str = "AwsDataCatalog",
    table_pattern: Optional[str] = None,
    service: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    List tables in a specific database.

    Args:
        database_name: Name of the database
        data_catalog_name: Name of the data catalog (default: AwsDataCatalog)
        table_pattern: Optional pattern to filter table names

    Returns:
        List of tables with metadata and schemas
    """
    try:
        if service is None:
            service = AthenaQueryService(data_catalog_name=data_catalog_name)
        return service.discover_tables(database_name, data_catalog_name=data_catalog_name, table_pattern=table_pattern)
    except Exception as e:
        logger.error(f"Failed to list tables: {e}")
        return format_error_response(f"Failed to list tables: {str(e)}")


def athena_table_schema(
    database_name: str,
    table_name: str,
    data_catalog_name: str = "AwsDataCatalog",
    service: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Get detailed schema information for a specific table.

    Args:
        database_name: Name of the database
        table_name: Name of the table
        data_catalog_name: Name of the data catalog (default: AwsDataCatalog)

    Returns:
        Detailed table schema including columns, types, partitions
    """
    try:
        if service is None:
            service = AthenaQueryService(data_catalog_name=data_catalog_name)
        return service.get_table_metadata(database_name, table_name, data_catalog_name=data_catalog_name)
    except Exception as e:
        logger.error(f"Failed to get table schema: {e}")
        return format_error_response(f"Failed to get table schema: {str(e)}")


def athena_workgroups_list(
    use_quilt_auth: bool = True,
    service: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    List available Athena workgroups that the user can access.

    Args:
        use_quilt_auth: Use quilt3 assumed role credentials if available

    Returns:
        List of accessible workgroups with their configurations
    """
    try:
        # Use consolidated AthenaQueryService for consistent authentication patterns
        if service is None:
            service = AthenaQueryService(use_quilt_auth=use_quilt_auth)

        # Get workgroups using the service's consolidated method
        workgroups = service.list_workgroups()

        # Determine region for response metadata
        region = "us-east-1" if use_quilt_auth else os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

        result = {
            "success": True,
            "workgroups": workgroups,
            "region": region,
            "count": len(workgroups),
        }

        # Enhance with table formatting for better readability
        from ..formatting import enhance_result_with_table_format

        result = enhance_result_with_table_format(result)

        return result

    except Exception as e:
        logger.error(f"Failed to list workgroups: {e}")
        return format_error_response(f"Failed to list workgroups: {str(e)}")


def athena_query_execute(
    query: str,
    database_name: Optional[str] = None,
    workgroup_name: Optional[str] = None,
    data_catalog_name: str = "AwsDataCatalog",
    max_results: int = 1000,
    output_format: str = "json",
    use_quilt_auth: bool = True,
    service: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Execute SQL query against Athena using SQLAlchemy/PyAthena.

    IMPORTANT SQL Syntax Requirements:
    - Use double quotes for table/column names with special characters
    - Example: SELECT * FROM "table-with-hyphens" WHERE "column-name" = 'value'
    - Do NOT use backticks (`) - these are not supported by Athena
    - Athena uses Presto/Trino SQL syntax, not MySQL syntax

    Args:
        query: SQL query to execute (must use double quotes, not backticks)
        database_name: Default database for query context (optional)
        workgroup_name: Athena workgroup to use (optional, auto-discovered if not provided)
        data_catalog_name: Data catalog to use (default: AwsDataCatalog)
        max_results: Maximum number of results to return
        output_format: Output format (json, csv, parquet, table)
        use_quilt_auth: Use quilt3 assumed role credentials if available

    Returns:
        Query execution results with data, metadata, and formatting
    """
    try:
        # Validate inputs
        if not query or not query.strip():
            return format_error_response("Query cannot be empty")

        # Check for backtick syntax early
        if "`" in query:
            corrected_query = query.replace("`", '"')
            return format_error_response(
                f"Athena does not support backtick identifiers. Use double quotes instead: {corrected_query}"
            )

        # Validate database name format if provided
        if database_name and ("-" in database_name or any(c in database_name for c in [" ", ".", "@", "/"])):
            # Suggest proper escaping for complex database names
            logger.info(f"Using database with special characters: {database_name}")

        # Pre-validate common query patterns that might cause issues
        query_upper = query.upper().strip()
        if "SHOW TABLES IN" in query_upper and database_name:
            # For SHOW TABLES queries, suggest using information_schema instead
            if "-" in database_name:
                suggestion = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{database_name}'"
                logger.info(f"Alternative query for database with hyphens: {suggestion}")

        if max_results < 1 or max_results > 10000:
            return format_error_response("max_results must be between 1 and 10000")

        if output_format not in ["json", "csv", "parquet", "table"]:
            return format_error_response("output_format must be one of: json, csv, parquet, table")

        # Execute query
        if service is None:
            service = AthenaQueryService(
                use_quilt_auth=use_quilt_auth,
                workgroup_name=workgroup_name,
                data_catalog_name=data_catalog_name,
            )
        result = service.execute_query(query, database_name, max_results)

        if not result.get("success"):
            return result

        # Format results
        formatted_result = service.format_results(result, output_format)

        # Enhance with table formatting for better readability
        from ..formatting import format_athena_results_as_table

        formatted_result = format_athena_results_as_table(formatted_result)

        return formatted_result

    except Exception as e:
        error_str = str(e)
        # Use safe logging to prevent formatting issues
        logger.error("Failed to execute query: %s", error_str)

        # Provide specific guidance for common errors
        if "glue:GetDatabase" in error_str:
            return format_error_response(
                f"Athena authentication failed - missing Glue permissions. "
                f"Add glue:GetDatabase, glue:GetTable permissions to your IAM role. "
                f"Original error: {error_str}"
            )
        elif "TABLE_NOT_FOUND" in error_str or "does not exist" in error_str:
            return format_error_response(
                f"Table not found. Use 'SHOW DATABASES' and 'SELECT table_name FROM information_schema.tables' "
                f"to discover available tables. Original error: {error_str}"
            )
        elif "SCHEMA_NOT_FOUND" in error_str or "Schema" in error_str and "does not exist" in error_str:
            return format_error_response(
                f"Database/schema not found. Use 'SHOW DATABASES' to see available databases. "
                f"For databases with hyphens, use double quotes. Original error: {error_str}"
            )
        elif "mismatched input" in error_str and "expecting" in error_str:
            return format_error_response(
                f"SQL syntax error. Athena uses Presto/Trino syntax. "
                f"Use double quotes for identifiers with special characters. "
                f"Original error: {error_str}"
            )
        elif "not enough arguments for format string" in error_str:
            return format_error_response(
                f"Query contains characters that interfere with formatting. "
                f"This is a known issue with queries containing '%' characters. "
                f"Try simplifying the query or using different patterns. "
                f"Original error: {error_str}"
            )
        else:
            # Add query-specific suggestions
            suggestions = _suggest_query_fix(query, error_str)
            return format_error_response(f"Query execution failed: {error_str}{suggestions}")


def athena_query_history(
    max_results: int = 50,
    status_filter: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    use_quilt_auth: bool = True,
    service: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Retrieve query execution history from Athena.

    Args:
        max_results: Maximum number of queries to return
        status_filter: Filter by query status (SUCCEEDED, FAILED, etc.)
        start_time: Start time for query range (ISO format)
        end_time: End time for query range (ISO format)

    Returns:
        List of historical query executions
    """
    try:
        import boto3
        from datetime import datetime, timedelta

        # Create Athena client
        if service is None:
            service = AthenaQueryService(use_quilt_auth=use_quilt_auth)
        athena_client = boto3.client("athena")

        # Set default time range if not provided
        if not start_time:
            # Default to last 24 hours
            start_dt = datetime.now(timezone.utc) - timedelta(days=1)
        else:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

        if not end_time:
            end_dt = datetime.now(timezone.utc)
        else:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        # List query executions
        kwargs = {
            "MaxResults": min(max_results, 50),  # Athena API limit
            "WorkGroup": "primary",
        }

        response = athena_client.list_query_executions(**kwargs)
        execution_ids = response.get("QueryExecutionIds", [])

        if not execution_ids:
            return {
                "success": True,
                "query_history": [],
                "count": 0,
                "message": "No query executions found",
            }

        # Get detailed information for each execution
        batch_response = athena_client.batch_get_query_execution(QueryExecutionIds=execution_ids)

        executions = []
        for exec_info in batch_response.get("QueryExecutions", []):
            # Filter by status if specified
            status = exec_info.get("Status", {}).get("State", "")
            if status_filter and status != status_filter:
                continue

            # Filter by time range
            submission_time = exec_info.get("Status", {}).get("SubmissionDateTime")
            if submission_time:
                if submission_time < start_dt or submission_time > end_dt:
                    continue

            execution_data = {
                "query_execution_id": exec_info.get("QueryExecutionId"),
                "query": exec_info.get("Query", ""),
                "status": status,
                "submission_time": (submission_time.isoformat() if submission_time else None),
                "completion_time": (
                    exec_info.get("Status", {}).get("CompletionDateTime").isoformat()
                    if exec_info.get("Status", {}).get("CompletionDateTime")
                    else None
                ),
                "execution_time_ms": exec_info.get("Statistics", {}).get("TotalExecutionTimeInMillis"),
                "data_scanned_bytes": exec_info.get("Statistics", {}).get("DataScannedInBytes"),
                "result_location": exec_info.get("ResultConfiguration", {}).get("OutputLocation"),
                "work_group": exec_info.get("WorkGroup"),
                "database": exec_info.get("QueryExecutionContext", {}).get("Database"),
                "error_message": exec_info.get("Status", {}).get("StateChangeReason"),
            }
            executions.append(execution_data)

        return {
            "success": True,
            "query_history": executions,
            "count": len(executions),
            "filters": {
                "status_filter": status_filter,
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat(),
                "max_results": max_results,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get query history: {e}")
        return format_error_response(f"Failed to get query history: {str(e)}")


def athena_query_validate(query: str) -> Dict[str, Any]:
    """
    Validate SQL query syntax without executing it.

    Args:
        query: SQL query to validate

    Returns:
        Validation results with syntax check and suggestions
    """
    try:
        import re

        if not query or not query.strip():
            return format_error_response("Query cannot be empty")

        # Basic SQL validation
        query_upper = query.upper().strip()

        # Check for dangerous operations first
        dangerous_keywords = [
            "DROP",
            "DELETE",
            "INSERT",
            "UPDATE",
            "CREATE",
            "ALTER",
            "TRUNCATE",
        ]
        if any(keyword in query_upper for keyword in dangerous_keywords):
            return {
                "success": False,
                "valid": False,
                "error": "Query contains potentially dangerous operations",
                "suggestions": [
                    "This tool only supports read operations (SELECT, SHOW, DESCRIBE)",
                    "Modify your query to use SELECT instead of data modification operations",
                ],
            }

        # Check for basic SQL structure
        valid_statements = ["SELECT", "WITH", "SHOW", "DESCRIBE", "EXPLAIN"]
        if not any(query_upper.startswith(stmt) for stmt in valid_statements):
            return {
                "success": False,
                "valid": False,
                "error": "Query must start with SELECT, WITH, SHOW, DESCRIBE, or EXPLAIN",
                "suggestions": [
                    "Start your query with SELECT to retrieve data",
                    "Use SHOW TABLES to list available tables",
                    "Use DESCRIBE table_name to see table schema",
                ],
            }

        # Check for unsupported syntax
        if "`" in query:
            # Suggest the corrected query
            corrected_query = query.replace("`", '"')
            return {
                "success": False,
                "valid": False,
                "error": "Athena does not support backtick identifiers",
                "suggestions": [
                    "Use double quotes for identifiers instead of backticks",
                    "Athena uses Presto/Trino SQL syntax, not MySQL syntax",
                    f"Corrected query: {corrected_query}",
                    'Example: SELECT * FROM "table-with-hyphens" WHERE "column-name" = \'value\'',
                ],
            }

        # Basic syntax checks
        open_parens = query.count("(")
        close_parens = query.count(")")
        if open_parens != close_parens:
            return {
                "success": False,
                "valid": False,
                "error": "Mismatched parentheses in query",
                "suggestions": ["Check that all opening parentheses have matching closing parentheses"],
            }

        # Check for basic SELECT structure
        if query_upper.startswith("SELECT"):
            if " FROM " not in query_upper:
                return {
                    "success": False,
                    "valid": False,
                    "error": "SELECT query must include FROM clause",
                    "suggestions": [
                        "Add a FROM clause to specify which table to query",
                        "Example: SELECT * FROM database_name.table_name",
                    ],
                }

        return {
            "success": True,
            "valid": True,
            "message": "Query syntax appears valid",
            "query_type": query_upper.split()[0],
            "suggestions": [
                "Query validation passed basic syntax checks",
                "Consider adding LIMIT clause to prevent large result sets",
                "Use specific column names instead of * for better performance",
            ],
        }

    except Exception as e:
        logger.error(f"Failed to validate query: {e}")
        return format_error_response(f"Query validation failed: {str(e)}")
