"""MCP Resources - FastMCP decorator-based implementation.

This module defines all MCP resources using FastMCP's native decorator pattern.
Each resource is a simple async function decorated with @mcp.resource().

Resources are organized by category:
- Auth: Authentication and catalog status
- Permissions: AWS permissions discovery and bucket access
- Admin: User management and configuration
- Athena: AWS Athena database exploration
- Metadata: Package metadata templates
- Workflow: Workflow tracking and status
- Tabulator: Bucket and table listings
"""

import asyncio
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import FastMCP


def _serialize_result(result: Any) -> str:
    """Serialize result to JSON, handling Pydantic models and datetime objects.

    Args:
        result: The result to serialize (dict, Pydantic model, or other)

    Returns:
        JSON string representation
    """
    if hasattr(result, 'model_dump'):
        return json.dumps(result.model_dump(), indent=2, default=str)
    return json.dumps(result, indent=2, default=str)


def register_resources(mcp: "FastMCP") -> None:
    """Register all MCP resources with the FastMCP server.

    Args:
        mcp: FastMCP server instance to register resources with
    """

    # ====================
    # Auth Resources
    # ====================

    @mcp.resource(
        "auth://status",
        name="Auth Status",
        description="Check authentication status and catalog configuration",
        mime_type="application/json",
    )
    async def auth_status_resource() -> str:
        """Check authentication status."""
        from quilt_mcp.services.auth_metadata import auth_status

        result = await asyncio.to_thread(auth_status)
        return _serialize_result(result)

    @mcp.resource(
        "auth://catalog/info",
        name="Catalog Info",
        description="Get catalog configuration details",
        mime_type="application/json",
    )
    async def catalog_info_resource() -> str:
        """Get catalog info."""
        from quilt_mcp.services.auth_metadata import catalog_info

        result = await asyncio.to_thread(catalog_info)
        return _serialize_result(result)

    @mcp.resource(
        "auth://filesystem/status",
        name="Filesystem Status",
        description="Check filesystem permissions and writability",
        mime_type="application/json",
    )
    async def filesystem_status_resource() -> str:
        """Check filesystem status."""
        from quilt_mcp.services.auth_metadata import filesystem_status

        result = await asyncio.to_thread(filesystem_status)
        return _serialize_result(result)

    # ====================
    # Permissions Resources
    # ====================
    # Note: discover_permissions is exposed as a TOOL (not resource) to accept parameters

    @mcp.resource(
        "permissions://recommendations",
        name="Bucket Recommendations",
        description="Smart bucket recommendations based on permissions and context",
        mime_type="application/json",
    )
    async def bucket_recommendations() -> str:
        """Get bucket recommendations."""
        from quilt_mcp.services.permissions_service import bucket_recommendations_get

        result = await asyncio.to_thread(bucket_recommendations_get)
        return _serialize_result(result)

    # ====================
    # Admin Resources
    # ====================

    @mcp.resource(
        "admin://users",
        name="Admin Users List",
        description="List all users in the Quilt registry with their roles and status (requires admin privileges)",
        mime_type="application/json",
    )
    async def admin_users() -> str:
        """List all users (requires admin privileges)."""
        from quilt_mcp.services.governance_service import admin_users_list

        try:
            result = await admin_users_list()
            return _serialize_result(result)
        except Exception as e:
            # Provide helpful error message for authorization failures
            error_msg = str(e)
            if "Unauthorized" in error_msg or "403" in error_msg or "401" in error_msg:
                return _serialize_result(
                    {
                        "error": "Unauthorized",
                        "message": "This resource requires admin privileges in the Quilt catalog. Please ensure you are logged in with an admin account.",
                        "suggestion": "Contact your Quilt administrator to request admin access.",
                    }
                )
            return _serialize_result({"error": "Failed to list users", "message": error_msg})

    @mcp.resource(
        "admin://roles",
        name="Admin Roles List",
        description="List all available roles in the Quilt registry (requires admin privileges)",
        mime_type="application/json",
    )
    async def admin_roles() -> str:
        """List all roles (requires admin privileges)."""
        from quilt_mcp.services.governance_service import admin_roles_list

        try:
            result = await admin_roles_list()
            return _serialize_result(result)
        except Exception as e:
            # Provide helpful error message for authorization failures
            error_msg = str(e)
            if "Unauthorized" in error_msg or "403" in error_msg or "401" in error_msg:
                return _serialize_result(
                    {
                        "error": "Unauthorized",
                        "message": "This resource requires admin privileges in the Quilt catalog. Please ensure you are logged in with an admin account.",
                        "suggestion": "Contact your Quilt administrator to request admin access.",
                    }
                )
            return _serialize_result({"error": "Failed to list roles", "message": error_msg})

    @mcp.resource(
        "admin://config/sso",
        name="SSO Configuration",
        description="Current SSO configuration",
        mime_type="application/json",
    )
    async def admin_sso_config() -> str:
        """Get SSO configuration."""
        from quilt_mcp.services.governance_service import admin_sso_config_get

        result = await admin_sso_config_get()
        return _serialize_result(result)

    @mcp.resource(
        "admin://config/tabulator",
        name="Tabulator Configuration",
        description="Tabulator open query configuration",
        mime_type="application/json",
    )
    async def admin_tabulator_config() -> str:
        """Get tabulator configuration."""
        from quilt_mcp.services.governance_service import admin_tabulator_open_query_get

        result = await admin_tabulator_open_query_get()
        return _serialize_result(result)

    # ====================
    # Athena Resources
    # ====================

    @mcp.resource(
        "athena://databases",
        name="Athena Databases",
        description="List available Athena databases",
        mime_type="application/json",
    )
    async def athena_databases() -> str:
        """List Athena databases."""
        from quilt_mcp.services.athena_read_service import athena_databases_list

        result = await asyncio.to_thread(athena_databases_list)
        return _serialize_result(result)

    @mcp.resource(
        "athena://workgroups",
        name="Athena Workgroups",
        description="List available Athena workgroups",
        mime_type="application/json",
    )
    async def athena_workgroups() -> str:
        """List Athena workgroups."""
        from quilt_mcp.services.athena_read_service import athena_workgroups_list

        result = await asyncio.to_thread(athena_workgroups_list)
        return _serialize_result(result)

    @mcp.resource(
        "athena://query/history",
        name="Athena Query History",
        description="Recent Athena query execution history (last 50 queries)",
        mime_type="application/json",
    )
    async def athena_query_history_resource() -> str:
        """Get query history (default: last 50 queries)."""
        from quilt_mcp.services.athena_read_service import athena_query_history

        result = await asyncio.to_thread(
            athena_query_history,
            max_results=50,
            status_filter=None,
            start_time=None,
            end_time=None,
            use_quilt_auth=True,
            service=None,
        )
        return _serialize_result(result)

    # ====================
    # Metadata Resources
    # ====================

    @mcp.resource(
        "metadata://templates",
        name="Metadata Templates",
        description="List available metadata templates",
        mime_type="application/json",
    )
    async def metadata_templates() -> str:
        """List metadata templates."""
        from quilt_mcp.services.metadata_service import list_metadata_templates

        result = await asyncio.to_thread(list_metadata_templates)
        return _serialize_result(result)

    @mcp.resource(
        "metadata://examples",
        name="Metadata Examples",
        description="Example metadata configurations",
        mime_type="application/json",
    )
    async def metadata_examples() -> str:
        """Get metadata examples."""
        from quilt_mcp.services.metadata_service import show_metadata_examples

        result = await asyncio.to_thread(show_metadata_examples)
        return _serialize_result(result)

    @mcp.resource(
        "metadata://troubleshooting",
        name="Metadata Troubleshooting",
        description="Common metadata issues and solutions",
        mime_type="application/json",
    )
    async def metadata_troubleshooting() -> str:
        """Get troubleshooting guide."""
        # This function doesn't exist, create a simple placeholder
        result = {"status": "info", "message": "For metadata troubleshooting, use fix_metadata_validation_issues()"}
        return _serialize_result(result)

    # ====================
    # Workflow Resources
    # ====================

    @mcp.resource(
        "workflow://workflows",
        name="Workflows List",
        description="List all tracked workflows",
        mime_type="application/json",
    )
    async def workflows() -> str:
        """List all workflows."""
        from quilt_mcp.services.workflow_service import workflow_list_all

        result = await asyncio.to_thread(workflow_list_all)
        return _serialize_result(result)

    # ====================
    # Tabulator Resources
    # ====================

    @mcp.resource(
        "tabulator://buckets",
        name="Tabulator Buckets",
        description="List buckets with tabulator tables configured",
        mime_type="application/json",
    )
    async def tabulator_buckets() -> str:
        """List tabulator buckets."""
        from quilt_mcp.services.tabulator_service import tabulator_buckets_list

        result = await tabulator_buckets_list()
        return _serialize_result(result)
