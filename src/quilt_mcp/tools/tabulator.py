"""
Quilt Tabulator Management Tools

This module provides MCP tools for managing Quilt tabulator tables, which enable
SQL querying across multiple Quilt packages using AWS Athena.

Tabulator tables aggregate data from package contents based on configurable
patterns and schemas, providing a powerful data discovery and analysis layer.
"""

import yaml
import logging
from typing import Dict, List, Any, Optional
from ..utils import format_error_response

logger = logging.getLogger(__name__)

# QuiltService provides admin module access
from ..services.quilt_service import QuiltService

# Initialize service and check availability
quilt_service = QuiltService()
ADMIN_AVAILABLE = quilt_service.is_admin_available()

if not ADMIN_AVAILABLE:
    logger.warning("quilt3.admin not available - tabulator functionality disabled")


class TabulatorService:
    """Service for managing Quilt tabulator tables."""

    def __init__(self, use_quilt_auth: bool = True):
        self.use_quilt_auth = use_quilt_auth
        self.admin_available = ADMIN_AVAILABLE and use_quilt_auth

    def _build_tabulator_config(
        self,
        schema: List[Dict[str, str]],
        package_pattern: str,
        logical_key_pattern: str,
        parser_config: Dict[str, Any],
    ) -> str:
        """Build YAML configuration for tabulator table."""
        config = {
            "schema": schema,
            "source": {
                "type": "quilt-packages",
                "package_name": package_pattern,
                "logical_key": logical_key_pattern,
            },
            "parser": parser_config,
        }
        return yaml.dump(config, default_flow_style=False)

    def _validate_schema(self, schema: List[Dict[str, str]]) -> List[str]:
        """Validate schema configuration."""
        errors = []
        valid_types = {"STRING", "INT", "FLOAT", "BOOLEAN", "TIMESTAMP"}

        if not schema:
            errors.append("Schema cannot be empty")
            return errors

        for i, column in enumerate(schema):
            if not isinstance(column, dict):
                errors.append(f"Schema column {i} must be a dictionary")
                continue

            if "name" not in column:
                errors.append(f"Schema column {i} missing 'name' field")
            elif not column["name"] or not isinstance(column["name"], str):
                errors.append(f"Schema column {i} name must be a non-empty string")

            if "type" not in column:
                errors.append(f"Schema column '{column.get('name', f'column_{i}')}' missing 'type' field")
            elif column["type"] not in valid_types:
                errors.append(
                    f"Invalid type '{column['type']}' for column '{column.get('name', f'column_{i}')}'. Valid types: {', '.join(sorted(valid_types))}"
                )

        return errors

    def _validate_patterns(self, package_pattern: str, logical_key_pattern: str) -> List[str]:
        """Validate regex patterns."""
        errors = []
        import re

        if not package_pattern:
            errors.append("Package pattern cannot be empty")
        else:
            try:
                re.compile(package_pattern)
            except re.error as e:
                errors.append(f"Invalid package pattern: {e}")

        if not logical_key_pattern:
            errors.append("Logical key pattern cannot be empty")
        else:
            try:
                re.compile(logical_key_pattern)
            except re.error as e:
                errors.append(f"Invalid logical key pattern: {e}")

        return errors

    def _validate_parser_config(self, parser_config: Dict[str, Any]) -> List[str]:
        """Validate parser configuration."""
        errors = []
        valid_formats = {"csv", "tsv", "parquet"}

        if not parser_config:
            errors.append("Parser configuration cannot be empty")
            return errors

        format_value = parser_config.get("format")
        if not format_value:
            errors.append("Parser configuration missing 'format' field")
            return errors

        if isinstance(format_value, str):
            format_value = format_value.lower()
            parser_config["format"] = format_value

        if format_value not in valid_formats:
            errors.append(
                f"Invalid format '{parser_config['format']}'. Valid formats: {', '.join(sorted(valid_formats))}"
            )
            return errors

        # Format-specific validation
        if parser_config.get("format") in ["csv", "tsv"]:
            if "delimiter" not in parser_config:
                # Set default delimiter based on format
                parser_config["delimiter"] = "\t" if parser_config["format"] == "tsv" else ","
            if "header" not in parser_config:
                parser_config["header"] = True

        return errors

    def list_tables(self, bucket_name: str) -> Dict[str, Any]:
        """List all tabulator tables for a bucket."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            # Use the direct API to list tabulator tables
            admin_tabulator = quilt_service.get_tabulator_admin()
            tables = admin_tabulator.list_tables(bucket_name)

            # Parse and enrich table information
            enriched_tables = []
            for table in tables:
                table_info = {
                    "name": table.name,
                    "config_yaml": table.config,
                }

                # Parse YAML config to extract schema and patterns
                try:
                    if table_info["config_yaml"]:
                        config = yaml.safe_load(table_info["config_yaml"])
                        table_info["schema"] = config.get("schema", [])
                        table_info["source"] = config.get("source", {})
                        table_info["parser"] = config.get("parser", {})
                        table_info["column_count"] = len(config.get("schema", []))
                except yaml.YAMLError as e:
                    table_info["config_error"] = str(e)

                enriched_tables.append(table_info)

            result = {
                "success": True,
                "tables": enriched_tables,
                "bucket_name": bucket_name,
                "count": len(enriched_tables),
            }

            # Enhance with table formatting for better readability
            from ..formatting import format_tabulator_results_as_table

            result = format_tabulator_results_as_table(result)

            return result

        except Exception as e:
            logger.error(f"Failed to list tabulator tables: {e}")
            return format_error_response(f"Failed to list tabulator tables: {str(e)}")

    def create_table(
        self,
        bucket_name: str,
        table_name: str,
        schema: List[Dict[str, str]],
        package_pattern: str,
        logical_key_pattern: str,
        parser_config: Dict[str, Any],
        description: str = None,
    ) -> Dict[str, Any]:
        """Create a new tabulator table."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            # Validate inputs
            validation_errors = []

            if not bucket_name:
                validation_errors.append("Bucket name cannot be empty")
            if not table_name:
                validation_errors.append("Table name cannot be empty")

            validation_errors.extend(self._validate_schema(schema))
            validation_errors.extend(self._validate_patterns(package_pattern, logical_key_pattern))
            validation_errors.extend(self._validate_parser_config(parser_config))

            if validation_errors:
                return {
                    "success": False,
                    "error": f"Validation errors: {'; '.join(validation_errors)}",
                    "error_details": validation_errors,
                }

            # Build tabulator configuration
            config_yaml = self._build_tabulator_config(schema, package_pattern, logical_key_pattern, parser_config)

            # Execute GraphQL mutation to create table
            admin_tabulator = quilt_service.get_tabulator_admin()
            response = admin_tabulator.set_table(bucket_name=bucket_name, table_name=table_name, config=config_yaml)

            if hasattr(response, "__typename"):
                if response.__typename == "InvalidInput":
                    errors = (
                        [error.message for error in response.errors]
                        if hasattr(response, "errors")
                        else ["Invalid input"]
                    )
                    return format_error_response(f"Invalid input: {'; '.join(errors)}")
                elif response.__typename == "OperationError":
                    return format_error_response(
                        f"Operation error: {response.message if hasattr(response, 'message') else 'Unknown error'}"
                    )

            return {
                "success": True,
                "table_name": table_name,
                "bucket_name": bucket_name,
                "config": config_yaml,
                "schema": schema,
                "package_pattern": package_pattern,
                "logical_key_pattern": logical_key_pattern,
                "parser_config": parser_config,
                "description": description or f"Tabulator table for {bucket_name}",
                "message": f"Tabulator table '{table_name}' created successfully",
            }

        except Exception as e:
            logger.error(f"Failed to create tabulator table: {e}")
            return format_error_response(f"Failed to create tabulator table: {str(e)}")

    def delete_table(self, bucket_name: str, table_name: str) -> Dict[str, Any]:
        """Delete a tabulator table."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            if not bucket_name:
                return format_error_response("Bucket name cannot be empty")
            if not table_name:
                return format_error_response("Table name cannot be empty")

            # Delete by setting config to None
            admin_tabulator = quilt_service.get_tabulator_admin()
            response = admin_tabulator.set_table(bucket_name=bucket_name, table_name=table_name, config=None)

            if hasattr(response, "__typename"):
                if response.__typename == "InvalidInput":
                    errors = (
                        [error.message for error in response.errors]
                        if hasattr(response, "errors")
                        else ["Invalid input"]
                    )
                    return format_error_response(f"Invalid input: {'; '.join(errors)}")
                elif response.__typename == "OperationError":
                    return format_error_response(
                        f"Operation error: {response.message if hasattr(response, 'message') else 'Unknown error'}"
                    )

            return {
                "success": True,
                "table_name": table_name,
                "bucket_name": bucket_name,
                "message": f"Tabulator table '{table_name}' deleted successfully",
            }

        except Exception as e:
            logger.error(f"Failed to delete tabulator table: {e}")
            return format_error_response(f"Failed to delete tabulator table: {str(e)}")

    def rename_table(self, bucket_name: str, table_name: str, new_table_name: str) -> Dict[str, Any]:
        """Rename a tabulator table."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            if not bucket_name:
                return format_error_response("Bucket name cannot be empty")
            if not table_name:
                return format_error_response("Table name cannot be empty")
            if not new_table_name:
                return format_error_response("New table name cannot be empty")

            # Execute GraphQL mutation to rename table
            admin_tabulator = quilt_service.get_tabulator_admin()
            response = admin_tabulator.rename_table(
                bucket_name=bucket_name,
                table_name=table_name,
                new_table_name=new_table_name,
            )

            if hasattr(response, "__typename"):
                if response.__typename == "InvalidInput":
                    errors = (
                        [error.message for error in response.errors]
                        if hasattr(response, "errors")
                        else ["Invalid input"]
                    )
                    return format_error_response(f"Invalid input: {'; '.join(errors)}")
                elif response.__typename == "OperationError":
                    return format_error_response(
                        f"Operation error: {response.message if hasattr(response, 'message') else 'Unknown error'}"
                    )

            return {
                "success": True,
                "old_table_name": table_name,
                "new_table_name": new_table_name,
                "bucket_name": bucket_name,
                "message": f"Tabulator table renamed from '{table_name}' to '{new_table_name}'",
            }

        except Exception as e:
            logger.error(f"Failed to rename tabulator table: {e}")
            return format_error_response(f"Failed to rename tabulator table: {str(e)}")

    def get_open_query_status(self) -> Dict[str, Any]:
        """Get tabulator open query status."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            admin_tabulator = quilt_service.get_tabulator_admin()
            response = admin_tabulator.get_open_query()

            return {
                "success": True,
                "open_query_enabled": (response.admin.tabulator_open_query if hasattr(response, "admin") else False),
            }

        except Exception as e:
            logger.error(f"Failed to get open query status: {e}")
            return format_error_response(f"Failed to get open query status: {str(e)}")

    def set_open_query(self, enabled: bool) -> Dict[str, Any]:
        """Set tabulator open query status."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            admin_tabulator = quilt_service.get_tabulator_admin()
            response = admin_tabulator.set_open_query(enabled=enabled)

            return {
                "success": True,
                "open_query_enabled": (response.admin.tabulator_open_query if hasattr(response, "admin") else enabled),
                "message": f"Open query {'enabled' if enabled else 'disabled'}",
            }

        except Exception as e:
            logger.error(f"Failed to set open query status: {e}")
            return format_error_response(f"Failed to set open query status: {str(e)}")


# Global service instance
_tabulator_service = None


def get_tabulator_service() -> TabulatorService:
    """Get or create the tabulator service instance."""
    global _tabulator_service
    if _tabulator_service is None:
        _tabulator_service = TabulatorService()
    return _tabulator_service


# PRIVATE HELPER FUNCTIONS (not exposed as MCP tools)


def _tabulator_query(
    query: str,
    database_name: Optional[str] = None,
    workgroup_name: Optional[str] = None,
    max_results: int = 1000,
    output_format: str = "json",
    use_quilt_auth: bool = True,
) -> Dict[str, Any]:
    """
    PRIVATE helper for executing queries against Tabulator catalog.

    Auto-discovers tabulator_data_catalog from catalog_info() and executes
    query using athena_query_execute. This function is NOT exposed as an MCP tool.

    Args:
        query: SQL query to execute
        database_name: Optional database name (None for catalog-level queries like SHOW DATABASES)
        workgroup_name: Athena workgroup to use (optional, auto-discovered if not provided)
        max_results: Maximum number of results to return
        output_format: Output format (json, csv, parquet, table)
        use_quilt_auth: Use quilt3 assumed role credentials if available

    Returns:
        Query execution results with data, metadata, and formatting
    """
    try:
        # Import here to avoid circular dependency
        from .auth import catalog_info
        from .athena_glue import athena_query_execute

        # Auto-discover data_catalog_name from catalog_info
        info = catalog_info()
        if not info.get("tabulator_data_catalog"):
            return format_error_response(
                "tabulator_data_catalog not configured. This requires a Tabulator-enabled catalog. "
                "Check catalog configuration."
            )

        data_catalog_name = info["tabulator_data_catalog"]

        # Execute query using athena_query_execute
        return athena_query_execute(
            query=query,
            database_name=database_name,
            workgroup_name=workgroup_name,
            data_catalog_name=data_catalog_name,
            max_results=max_results,
            output_format=output_format,
            use_quilt_auth=use_quilt_auth,
        )

    except Exception as e:
        logger.error(f"Error in _tabulator_query: {e}")
        return format_error_response(f"Failed to execute tabulator query: {str(e)}")


# MCP Tool Functions


async def tabulator_tables_list(bucket_name: str) -> Dict[str, Any]:
    """
    List all tabulator tables configured for a bucket.

    Tabulator tables enable SQL querying across multiple Quilt packages,
    aggregating data based on configurable patterns and schemas.

    Args:
        bucket_name: Name of the S3 bucket to list tables for

    Returns:
        Dict containing:
        - success: Whether the operation succeeded
        - tables: List of tabulator tables with their configurations
        - bucket_name: The bucket name that was queried
        - count: Number of tables found
    """
    try:
        service = get_tabulator_service()
        return service.list_tables(bucket_name)
    except Exception as e:
        logger.error(f"Error in tabulator_tables_list: {e}")
        return format_error_response(f"Failed to list tabulator tables: {str(e)}")


async def tabulator_table_create(
    bucket_name: str,
    table_name: str,
    schema: List[Dict[str, str]],
    package_pattern: str,
    logical_key_pattern: str,
    parser_format: str = "csv",
    parser_delimiter: str = None,
    parser_header: bool = True,
    parser_skip_rows: int = 0,
    description: str = None,
) -> Dict[str, Any]:
    """
    Create a new tabulator table configuration.

    Tabulator tables aggregate data from package contents based on regex patterns
    that match package names and logical keys within packages.

    Args:
        bucket_name: Name of the S3 bucket
        table_name: Name for the new tabulator table
        schema: List of column definitions, each with 'name' and 'type' keys
                Valid types: STRING, INT, FLOAT, BOOLEAN, TIMESTAMP
        package_pattern: Regex pattern to match package names (supports named capture groups)
        logical_key_pattern: Regex pattern to match logical keys within packages
        parser_format: File format (csv, tsv, parquet) - default: csv
        parser_delimiter: Field delimiter for CSV/TSV (auto-detected if not provided)
        parser_header: Whether files have header row - default: True
        parser_skip_rows: Number of rows to skip at the beginning - default: 0
        description: Optional description of the table

    Returns:
        Dict containing success status and table creation details
    """
    try:
        # Build parser configuration
        parser_config = {"format": parser_format, "header": parser_header}

        if parser_format in ["csv", "tsv"]:
            if parser_delimiter is None:
                parser_config["delimiter"] = "\t" if parser_format == "tsv" else ","
            else:
                parser_config["delimiter"] = parser_delimiter

            if parser_skip_rows > 0:
                parser_config["skip_rows"] = parser_skip_rows

        service = get_tabulator_service()
        return service.create_table(
            bucket_name=bucket_name,
            table_name=table_name,
            schema=schema,
            package_pattern=package_pattern,
            logical_key_pattern=logical_key_pattern,
            parser_config=parser_config,
            description=description,
        )
    except Exception as e:
        logger.error(f"Error in tabulator_table_create: {e}")
        return format_error_response(f"Failed to create tabulator table: {str(e)}")


async def tabulator_table_delete(bucket_name: str, table_name: str) -> Dict[str, Any]:
    """
    Delete a tabulator table configuration.

    Args:
        bucket_name: Name of the S3 bucket
        table_name: Name of the tabulator table to delete

    Returns:
        Dict containing success status and deletion confirmation
    """
    try:
        service = get_tabulator_service()
        return service.delete_table(bucket_name, table_name)
    except Exception as e:
        logger.error(f"Error in tabulator_table_delete: {e}")
        return format_error_response(f"Failed to delete tabulator table: {str(e)}")


async def tabulator_table_rename(bucket_name: str, table_name: str, new_table_name: str) -> Dict[str, Any]:
    """
    Rename a tabulator table.

    Args:
        bucket_name: Name of the S3 bucket
        table_name: Current name of the tabulator table
        new_table_name: New name for the tabulator table

    Returns:
        Dict containing success status and rename confirmation
    """
    try:
        service = get_tabulator_service()
        return service.rename_table(bucket_name, table_name, new_table_name)
    except Exception as e:
        logger.error(f"Error in tabulator_table_rename: {e}")
        return format_error_response(f"Failed to rename tabulator table: {str(e)}")


async def tabulator_open_query_status() -> Dict[str, Any]:
    """
    Get the current status of tabulator open query feature.

    The open query feature allows broader access to tabulator functionality.

    Returns:
        Dict containing:
        - success: Whether the operation succeeded
        - open_query_enabled: Current status of the open query feature
    """
    try:
        service = get_tabulator_service()
        return service.get_open_query_status()
    except Exception as e:
        logger.error(f"Error in tabulator_open_query_status: {e}")
        return format_error_response(f"Failed to get open query status: {str(e)}")


async def tabulator_open_query_toggle(enabled: bool) -> Dict[str, Any]:
    """
    Enable or disable tabulator open query feature.

    Args:
        enabled: Whether to enable (True) or disable (False) open query

    Returns:
        Dict containing:
        - success: Whether the operation succeeded
        - open_query_enabled: Updated status of the open query feature
        - message: Confirmation message
    """
    try:
        service = get_tabulator_service()
        return service.set_open_query(enabled)
    except Exception as e:
        logger.error(f"Error in tabulator_open_query_toggle: {e}")
        return format_error_response(f"Failed to set open query status: {str(e)}")


async def tabulator_buckets_list() -> Dict[str, Any]:
    """
    List all buckets (databases) available in the Tabulator catalog.

    This discovers all Quilt buckets that have Tabulator tables configured,
    enabling exploration of the Tabulator catalog without knowing bucket names.

    Returns:
        Dict containing:
        - success: Whether the operation succeeded
        - buckets: List of bucket names (database names)
        - count: Number of buckets found
    """
    try:
        # Execute SHOW DATABASES query to discover buckets
        result = _tabulator_query("SHOW DATABASES")

        if not result.get("success"):
            return result

        # Extract bucket names from query results
        buckets = []
        formatted_data = result.get("formatted_data", [])

        for row in formatted_data:
            # Handle different response formats from Athena
            bucket_name = row.get("database_name") or row.get("db_name") or row.get("name")
            if bucket_name:
                buckets.append(bucket_name)

        return {
            "success": True,
            "buckets": buckets,
            "count": len(buckets),
            "message": f"Found {len(buckets)} bucket(s) in Tabulator catalog",
        }

    except Exception as e:
        logger.error(f"Error in tabulator_buckets_list: {e}")
        return format_error_response(f"Failed to list tabulator buckets: {str(e)}")


async def tabulator_bucket_query(
    bucket_name: str,
    query: str,
    workgroup_name: Optional[str] = None,
    max_results: int = 1000,
    output_format: str = "json",
    use_quilt_auth: bool = True,
) -> Dict[str, Any]:
    """
    Execute SQL query against a specific bucket in the Tabulator catalog.

    This is the recommended way to query Tabulator tables. It auto-discovers
    the Tabulator catalog and sets the database context to the specified bucket.

    Args:
        bucket_name: Name of the S3 bucket (database) to query
        query: SQL query to execute (e.g., "SELECT * FROM table_name LIMIT 10")
        workgroup_name: Athena workgroup to use (optional, auto-discovered if not provided)
        max_results: Maximum number of results to return
        output_format: Output format (json, csv, parquet, table)
        use_quilt_auth: Use quilt3 assumed role credentials if available

    Returns:
        Query execution results with data, metadata, and formatting
    """
    try:
        # Validate inputs
        if not bucket_name or not bucket_name.strip():
            return format_error_response("bucket_name cannot be empty")

        if not query or not query.strip():
            return format_error_response("query cannot be empty")

        # Execute query using _tabulator_query with database context
        return _tabulator_query(
            query=query,
            database_name=bucket_name,
            workgroup_name=workgroup_name,
            max_results=max_results,
            output_format=output_format,
            use_quilt_auth=use_quilt_auth,
        )

    except Exception as e:
        logger.error(f"Error in tabulator_bucket_query: {e}")
        return format_error_response(f"Failed to execute bucket query: {str(e)}")
