"""Tabulator table management tools using backend operations.

These tools provide table management for Quilt tabulator functionality through
the backend layer, replacing the deprecated TabulatorService.
"""

from typing import List, Dict, Any, Optional, Literal
import logging

from quilt_mcp.ops.factory import QuiltOpsFactory
from quilt_mcp.utils import format_error_response

logger = logging.getLogger(__name__)


async def tabulator_tables_list(bucket: str) -> Dict[str, Any]:
    """List all tabulator tables in a bucket.

    Args:
        bucket: S3 bucket name

    Returns:
        Dict with success status, tables list, and metadata
    """
    try:
        backend = QuiltOpsFactory.create()
        tables = backend.list_tabulator_tables(bucket)

        # Enrich tables with parsed config info
        import yaml

        enriched_tables = []
        for table in tables:
            table_info = {
                "name": table["name"],
                "config_yaml": table["config"],
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

        from quilt_mcp.formatting import format_tabulator_results_as_table

        result = {
            "success": True,
            "tables": enriched_tables,
            "bucket_name": bucket,
            "count": len(enriched_tables),
        }

        return format_tabulator_results_as_table(result)

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
    """Create or update a tabulator table.

    Args:
        bucket_name: S3 bucket name
        table_name: Table name
        schema: List of column definitions with 'name' and 'type'
        package_pattern: Regex pattern for package names
        logical_key_pattern: Regex pattern for logical keys
        parser_format: File format (csv, tsv, parquet)
        parser_delimiter: Delimiter character (for CSV/TSV)
        parser_header: Whether file has header row
        parser_skip_rows: Number of rows to skip
        description: Optional table description

    Returns:
        Dict with operation result
    """
    try:
        import yaml

        # Build parser config
        parser_config: Dict[str, Any] = {"format": parser_format, "header": parser_header}
        if parser_format in {"csv", "tsv"}:
            parser_config["delimiter"] = parser_delimiter or ("\t" if parser_format == "tsv" else ",")
            if parser_skip_rows:
                parser_config["skip_rows"] = parser_skip_rows

        # Build full config YAML
        config_dict = {
            "schema": schema,
            "source": {
                "type": "quilt-packages",
                "package_name": package_pattern,
                "logical_key": logical_key_pattern,
            },
            "parser": parser_config,
        }
        config_yaml = yaml.dump(config_dict, default_flow_style=False)

        backend = QuiltOpsFactory.create()
        result = backend.create_tabulator_table(bucket_name, table_name, config_yaml)

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
        logger.error(f"Error in tabulator_table_create: {e}")
        return format_error_response(str(e))


async def tabulator_table_delete(bucket_name: str, table_name: str) -> Dict[str, Any]:
    """Delete a tabulator table.

    Args:
        bucket_name: S3 bucket name
        table_name: Table name to delete

    Returns:
        Dict with operation result
    """
    try:
        backend = QuiltOpsFactory.create()
        backend.delete_tabulator_table(bucket_name, table_name)

        return {
            "success": True,
            "table_name": table_name,
            "bucket_name": bucket_name,
            "message": f"Tabulator table '{table_name}' deleted successfully",
        }

    except Exception as e:
        logger.error(f"Error in tabulator_table_delete: {e}")
        return format_error_response(str(e))


async def tabulator_table_rename(
    bucket_name: str, table_name: str, new_table_name: str
) -> Dict[str, Any]:
    """Rename a tabulator table.

    Args:
        bucket_name: S3 bucket name
        table_name: Current table name
        new_table_name: New table name

    Returns:
        Dict with operation result
    """
    try:
        backend = QuiltOpsFactory.create()
        backend.rename_tabulator_table(bucket_name, table_name, new_table_name)

        return {
            "success": True,
            "old_table_name": table_name,
            "new_table_name": new_table_name,
            "bucket_name": bucket_name,
            "message": f"Tabulator table renamed from '{table_name}' to '{new_table_name}'",
        }

    except Exception as e:
        logger.error(f"Error in tabulator_table_rename: {e}")
        return format_error_response(str(e))


async def tabulator_open_query_status() -> Dict[str, Any]:
    """Get tabulator open query status.

    Note: This operation requires admin access and uses the legacy
    TabulatorService temporarily until admin operations are migrated.

    Returns:
        Dict with open query status
    """
    try:
        # This still needs admin access through the service
        # TODO: Migrate to backend admin operations
        from quilt_mcp.services.tabulator_service import get_tabulator_service

        service = get_tabulator_service()
        return service.get_open_query_status()

    except Exception as e:
        logger.error(f"Error in tabulator_open_query_status: {e}")
        return format_error_response(str(e))


async def tabulator_open_query_toggle(enabled: bool) -> Dict[str, Any]:
    """Toggle tabulator open query status.

    Note: This operation requires admin access and uses the legacy
    TabulatorService temporarily until admin operations are migrated.

    Args:
        enabled: Whether to enable open query

    Returns:
        Dict with operation result
    """
    try:
        # This still needs admin access through the service
        # TODO: Migrate to backend admin operations
        from quilt_mcp.services.tabulator_service import get_tabulator_service

        service = get_tabulator_service()
        return service.set_open_query(enabled)

    except Exception as e:
        logger.error(f"Error in tabulator_open_query_toggle: {e}")
        return format_error_response(str(e))


__all__ = [
    "tabulator_tables_list",
    "tabulator_table_create",
    "tabulator_table_delete",
    "tabulator_table_rename",
    "tabulator_open_query_status",
    "tabulator_open_query_toggle",
]
