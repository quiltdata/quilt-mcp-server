"""Tabulator service helpers shared by resources and tooling."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

import yaml

from quilt_mcp.formatting import format_tabulator_results_as_table
from quilt_mcp.services import auth_metadata
from quilt_mcp.services.quilt_service import QuiltService
from quilt_mcp.services import athena_read_service as athena_glue
from quilt_mcp.utils import format_error_response

logger = logging.getLogger(__name__)

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
                    f"Invalid type '{column['type']}' for column '{column.get('name', f'column_{i}')}'. "
                    f"Valid types: {', '.join(sorted(valid_types))}"
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
            except re.error as exc:
                errors.append(f"Invalid package pattern: {exc}")

        if not logical_key_pattern:
            errors.append("Logical key pattern cannot be empty")
        else:
            try:
                re.compile(logical_key_pattern)
            except re.error as exc:
                errors.append(f"Invalid logical key pattern: {exc}")

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

        if parser_config.get("format") in ["csv", "tsv"]:
            if "delimiter" not in parser_config:
                parser_config["delimiter"] = "\t" if parser_config["format"] == "tsv" else ","
            if "header" not in parser_config:
                parser_config["header"] = True

        return errors

    def list_tables(self, bucket_name: str) -> Dict[str, Any]:
        """List all tabulator tables for a bucket."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            admin_tabulator = quilt_service.get_tabulator_admin()
            tables = admin_tabulator.list_tables(bucket_name)

            enriched_tables = []
            for table in tables:
                table_info = {
                    "name": table.name,
                    "config_yaml": table.config,
                }
                try:
                    if table_info["config_yaml"]:
                        config = yaml.safe_load(table_info["config_yaml"])
                        table_info["schema"] = config.get("schema", [])
                        table_info["source"] = config.get("source", {})
                        table_info["parser"] = config.get("parser", {})
                        table_info["column_count"] = len(config.get("schema", []))
                except yaml.YAMLError as exc:
                    table_info["config_error"] = str(exc)

                enriched_tables.append(table_info)

            result = {
                "success": True,
                "tables": enriched_tables,
                "bucket_name": bucket_name,
                "count": len(enriched_tables),
            }

            return format_tabulator_results_as_table(result)

        except Exception as exc:
            logger.error(f"Failed to list tabulator tables: {exc}")
            return format_error_response(f"Failed to list tabulator tables: {exc}")

    def create_table(
        self,
        bucket_name: str,
        table_name: str,
        schema: List[Dict[str, str]],
        package_pattern: str,
        logical_key_pattern: str,
        parser_config: Dict[str, Any],
        description: str | None = None,
    ) -> Dict[str, Any]:
        """Create a new tabulator table."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            validation_errors: List[str] = []

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

            config_yaml = self._build_tabulator_config(schema, package_pattern, logical_key_pattern, parser_config)

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
                if response.__typename == "OperationError":
                    message = response.message if hasattr(response, "message") else "Unknown error"
                    return format_error_response(f"Operation error: {message}")

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

        except Exception as exc:
            logger.error(f"Failed to create tabulator table: {exc}")
            return format_error_response(f"Failed to create tabulator table: {exc}")

    def delete_table(self, bucket_name: str, table_name: str) -> Dict[str, Any]:
        """Delete a tabulator table."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            if not bucket_name:
                return format_error_response("Bucket name cannot be empty")
            if not table_name:
                return format_error_response("Table name cannot be empty")

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
                if response.__typename == "OperationError":
                    message = response.message if hasattr(response, "message") else "Unknown error"
                    return format_error_response(f"Operation error: {message}")

            return {
                "success": True,
                "table_name": table_name,
                "bucket_name": bucket_name,
                "message": f"Tabulator table '{table_name}' deleted successfully",
            }

        except Exception as exc:
            logger.error(f"Failed to delete tabulator table: {exc}")
            return format_error_response(f"Failed to delete tabulator table: {exc}")

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
                if response.__typename == "OperationError":
                    message = response.message if hasattr(response, "message") else "Unknown error"
                    return format_error_response(f"Operation error: {message}")

            return {
                "success": True,
                "old_table_name": table_name,
                "new_table_name": new_table_name,
                "bucket_name": bucket_name,
                "message": f"Tabulator table renamed from '{table_name}' to '{new_table_name}'",
            }

        except Exception as exc:
            logger.error(f"Failed to rename tabulator table: {exc}")
            return format_error_response(f"Failed to rename tabulator table: {exc}")

    def get_open_query_status(self) -> Dict[str, Any]:
        """Get tabulator open query status."""
        try:
            if not self.admin_available:
                return format_error_response("Admin functionality not available - check Quilt authentication")

            admin_tabulator = quilt_service.get_tabulator_admin()
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

            admin_tabulator = quilt_service.get_tabulator_admin()
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


def list_tabulator_tables(bucket_name: str) -> Dict[str, Any]:
    """List tables for a specific tabulator bucket."""
    try:
        service = get_tabulator_service()
        return service.list_tables(bucket_name)
    except Exception as exc:
        logger.error(f"Failed to list tabulator tables: {exc}")
        return format_error_response(f"Failed to list tabulator tables: {exc}")


async def tabulator_tables_list(bucket_name: str) -> Dict[str, Any]:
    """Async wrapper mirroring the legacy tool interface for listing tables."""
    try:
        service = get_tabulator_service()
        return service.list_tables(bucket_name)
    except Exception as e:
        logger.error(f"Error in tabulator_tables_list: {e}")
        return format_error_response(str(e))


async def tabulator_table_create(
    bucket_name: str,
    table_name: str,
    schema: List[Dict[str, str]],
    package_pattern: str,
    logical_key_pattern: str,
    parser_format: str = "csv",
    parser_delimiter: Optional[str] = None,
    parser_header: bool = True,
    parser_skip_rows: int = 0,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create tabulator table (legacy tool signature)."""
    try:
        parser_config: Dict[str, Any] = {"format": parser_format, "header": parser_header}
        if parser_format in {"csv", "tsv"}:
            parser_config["delimiter"] = parser_delimiter or ("\t" if parser_format == "tsv" else ",")
            if parser_skip_rows:
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
        return format_error_response(str(e))


async def tabulator_table_delete(bucket_name: str, table_name: str) -> Dict[str, Any]:
    """Delete tabulator table (legacy tool signature)."""
    try:
        service = get_tabulator_service()
        return service.delete_table(bucket_name=bucket_name, table_name=table_name)
    except Exception as e:
        logger.error(f"Error in tabulator_table_delete: {e}")
        return format_error_response(str(e))


async def tabulator_table_rename(bucket_name: str, table_name: str, new_table_name: str) -> Dict[str, Any]:
    """Rename tabulator table (legacy tool signature)."""
    try:
        service = get_tabulator_service()
        return service.rename_table(bucket_name=bucket_name, table_name=table_name, new_table_name=new_table_name)
    except Exception as e:
        logger.error(f"Error in tabulator_table_rename: {e}")
        return format_error_response(str(e))


async def tabulator_open_query_status() -> Dict[str, Any]:
    """Return tabulator open query flag."""
    try:
        service = get_tabulator_service()
        return service.get_open_query_status()
    except Exception as e:
        logger.error(f"Error in tabulator_open_query_status: {e}")
        return format_error_response(str(e))


async def tabulator_open_query_toggle(enabled: bool) -> Dict[str, Any]:
    """Toggle tabulator open query flag."""
    try:
        service = get_tabulator_service()
        return service.set_open_query(enabled=enabled)
    except Exception as e:
        logger.error(f"Error in tabulator_open_query_toggle: {e}")
        return format_error_response(str(e))


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
    "list_tabulator_tables",
    "tabulator_tables_list",
    "tabulator_table_create",
    "tabulator_table_delete",
    "tabulator_table_rename",
    "tabulator_open_query_status",
    "tabulator_open_query_toggle",
    "tabulator_buckets_list",
    "tabulator_bucket_query",
    "_tabulator_query",
]
