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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP


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
        return json.dumps(result, indent=2)

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
        return json.dumps(result, indent=2)

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
        return json.dumps(result, indent=2)

    # ====================
    # Permissions Resources
    # ====================

    @mcp.resource(
        "permissions://discover",
        name="Permissions Discovery",
        description="Discover AWS permissions for current user/role",
        mime_type="application/json",
    )
    async def permissions_discover() -> str:
        """Discover AWS permissions."""
        from quilt_mcp.services.permissions_service import discover_permissions

        result = await asyncio.to_thread(discover_permissions)
        return json.dumps(result, indent=2)

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
        return json.dumps(result, indent=2)

    @mcp.resource(
        "permissions://buckets/{bucket}/access",
        name="Bucket Access Check",
        description="Check access permissions for a specific bucket",
        mime_type="application/json",
    )
    async def bucket_access(bucket: str) -> str:
        """Check bucket access permissions."""
        from quilt_mcp.services.permissions_service import check_bucket_access

        result = await asyncio.to_thread(check_bucket_access, bucket=bucket)
        return json.dumps(result, indent=2)

    # ====================
    # Admin Resources
    # ====================

    @mcp.resource(
        "admin://users",
        name="Admin Users List",
        description="List all users in the Quilt registry with their roles and status",
        mime_type="application/json",
    )
    async def admin_users() -> str:
        """List all users."""
        from quilt_mcp.services.governance_service import admin_users_list

        result = await admin_users_list()
        return json.dumps(result, indent=2)

    @mcp.resource(
        "admin://roles",
        name="Admin Roles List",
        description="List all available roles in the Quilt registry",
        mime_type="application/json",
    )
    async def admin_roles() -> str:
        """List all roles."""
        from quilt_mcp.services.governance_service import admin_roles_list

        result = await admin_roles_list()
        return json.dumps(result, indent=2)

    @mcp.resource(
        "admin://users/{name}",
        name="Admin User Details",
        description="Get detailed information about a specific user",
        mime_type="application/json",
    )
    async def admin_user(name: str) -> str:
        """Get user details."""
        from quilt_mcp.services.governance_service import admin_user_get

        result = await asyncio.to_thread(admin_user_get, name=name)
        return json.dumps(result, indent=2)

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
        return json.dumps(result, indent=2)

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
        return json.dumps(result, indent=2)

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
        return json.dumps(result.model_dump() if hasattr(result, 'model_dump') else result, indent=2)

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
        return json.dumps(result.model_dump() if hasattr(result, 'model_dump') else result, indent=2)

    @mcp.resource(
        "athena://query/history",
        name="Athena Query History",
        description="Recent Athena query execution history",
        mime_type="application/json",
    )
    async def athena_query_history() -> str:
        """Get query history."""
        from quilt_mcp.services.athena_read_service import athena_query_history

        result = await asyncio.to_thread(athena_query_history)
        return json.dumps(result.model_dump() if hasattr(result, 'model_dump') else result, indent=2)

    @mcp.resource(
        "athena://databases/{database}/tables",
        name="Athena Tables",
        description="List tables in an Athena database",
        mime_type="application/json",
    )
    async def athena_tables(database: str) -> str:
        """List tables in database."""
        from quilt_mcp.services.athena_read_service import athena_tables_list

        result = await asyncio.to_thread(athena_tables_list, database=database)
        return json.dumps(result.model_dump() if hasattr(result, 'model_dump') else result, indent=2)

    @mcp.resource(
        "athena://databases/{database}/tables/{table}/schema",
        name="Athena Table Schema",
        description="Get schema for a specific Athena table",
        mime_type="application/json",
    )
    async def athena_table_schema(database: str, table: str) -> str:
        """Get table schema."""
        from quilt_mcp.services.athena_read_service import athena_table_schema

        result = await asyncio.to_thread(athena_table_schema, database=database, table=table)
        return json.dumps(result.model_dump() if hasattr(result, 'model_dump') else result, indent=2)

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
        return json.dumps(result, indent=2)

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
        return json.dumps(result, indent=2)

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
        return json.dumps(result, indent=2)

    @mcp.resource(
        "metadata://templates/{template}",
        name="Metadata Template Details",
        description="Get detailed information about a specific metadata template",
        mime_type="application/json",
    )
    async def metadata_template(template: str) -> str:
        """Get template details."""
        from quilt_mcp.services.metadata_service import get_metadata_template

        result = await asyncio.to_thread(get_metadata_template, name=template)
        return json.dumps(result, indent=2)

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
        return json.dumps(result, indent=2)

    @mcp.resource(
        "workflow://workflows/{workflow_id}/status",
        name="Workflow Status",
        description="Get status for a specific workflow",
        mime_type="application/json",
    )
    async def workflow_status(workflow_id: str) -> str:
        """Get workflow status."""
        from quilt_mcp.services.workflow_service import workflow_get_status

        result = await asyncio.to_thread(workflow_get_status, id=workflow_id)
        return json.dumps(result, indent=2)

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

        result = await asyncio.to_thread(tabulator_buckets_list)
        return json.dumps(result, indent=2)

    @mcp.resource(
        "tabulator://buckets/{bucket}/tables",
        name="Tabulator Tables",
        description="List tables in a tabulator bucket",
        mime_type="application/json",
    )
    async def tabulator_tables(bucket: str) -> str:
        """List tables in bucket."""
        from quilt_mcp.services.tabulator_service import tabulator_tables_list

        result = await asyncio.to_thread(tabulator_tables_list, bucket_name=bucket)
        return json.dumps(result, indent=2)
