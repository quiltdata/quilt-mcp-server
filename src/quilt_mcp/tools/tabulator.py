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

# Initialize service
quilt_service = QuiltService()


class TabulatorService:
    """Service for managing Quilt tabulator tables."""

    def __init__(self, use_quilt_auth: bool = True):
        self.use_quilt_auth = use_quilt_auth

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
            # Use QuiltService to list tabulator tables
            tables = quilt_service.list_tabulator_tables(bucket_name)

            # Parse and enrich table information
            enriched_tables = []
            for table in tables:
                table_info = {
                    "name": table["name"],
                    "config_yaml": table["config"],
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

            # Use QuiltService to create table
            result = quilt_service.create_tabulator_table(bucket=bucket_name, name=table_name, config=config_yaml)

            # Enhance result with additional details
            result.update(
                {
                    "success": True,
                    "config": config_yaml,
                    "schema": schema,
                    "package_pattern": package_pattern,
                    "logical_key_pattern": logical_key_pattern,
                    "parser_config": parser_config,
                    "description": description or f"Tabulator table for {bucket_name}",
                }
            )

            return result

        except Exception as e:
            logger.error(f"Failed to create tabulator table: {e}")
            return format_error_response(f"Failed to create tabulator table: {str(e)}")

    def delete_table(self, bucket_name: str, table_name: str) -> Dict[str, Any]:
        """Delete a tabulator table."""
        try:
            if not bucket_name:
                return format_error_response("Bucket name cannot be empty")
            if not table_name:
                return format_error_response("Table name cannot be empty")

            # Use QuiltService to delete table
            quilt_service.delete_tabulator_table(bucket=bucket_name, name=table_name)

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
            if not bucket_name:
                return format_error_response("Bucket name cannot be empty")
            if not table_name:
                return format_error_response("Table name cannot be empty")
            if not new_table_name:
                return format_error_response("New table name cannot be empty")

            # Use QuiltService to rename table
            result = quilt_service.rename_tabulator_table(
                bucket=bucket_name, old_name=table_name, new_name=new_table_name
            )

            # Enhance result with additional details
            result.update(
                {
                    "success": True,
                    "old_table_name": table_name,
                    "new_table_name": new_table_name,
                    "bucket_name": bucket_name,
                }
            )

            return result

        except Exception as e:
            logger.error(f"Failed to rename tabulator table: {e}")
            return format_error_response(f"Failed to rename tabulator table: {str(e)}")

    def get_open_query_status(self) -> Dict[str, Any]:
        """Get tabulator open query status."""
        try:
            # Use QuiltService to get tabulator access status
            enabled = quilt_service.get_tabulator_access()

            return {
                "success": True,
                "open_query_enabled": enabled,
            }

        except Exception as e:
            logger.error(f"Failed to get open query status: {e}")
            return format_error_response(f"Failed to get open query status: {str(e)}")

    def set_open_query(self, enabled: bool) -> Dict[str, Any]:
        """Set tabulator open query status."""
        try:
            # Use QuiltService to set tabulator access status
            result = quilt_service.set_tabulator_access(enabled=enabled)

            # Enhance result with consistent field names
            result.update(
                {
                    "success": True,
                    "open_query_enabled": result.get("enabled", enabled),
                }
            )

            return result

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


# MCP Tool Functions


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
