"""Resource access tool - provides tool-based access to MCP resources.

This tool enables backward compatibility for older MCP clients (Claude Desktop, Cursor)
that don't support the MCP resources protocol natively. It provides a simple tool interface
to access the registered MCP resources (mode-dependent).

The tool works by directly invoking the same service functions that power the MCP resources,
maintaining 100% data parity with the native resource implementation.
"""

from typing import Optional, Union

from quilt_mcp.tools.responses import (
    GetResourceSuccess,
    GetResourceError,
)


# Static registry mapping URIs to their service functions
# This mirrors the resources defined in src/quilt_mcp/resources.py
_BASE_RESOURCE_SERVICE_MAP = {
    # Auth resources
    "auth://status": ("quilt_mcp.services.auth_metadata", "auth_status", False),
    "auth://catalog/info": ("quilt_mcp.services.auth_metadata", "catalog_info", False),
    "auth://filesystem/status": ("quilt_mcp.services.auth_metadata", "filesystem_status", False),
    # Permissions resources
    # Note: discover_permissions and bucket_recommendations_get are exposed as TOOLS (not resources) to accept parameters
    # Admin resources (all async)
    "admin://users": ("quilt_mcp.services.governance_service", "admin_users_list", True),
    "admin://roles": ("quilt_mcp.services.governance_service", "admin_roles_list", True),
    "admin://config/sso": ("quilt_mcp.services.governance_service", "admin_sso_config_get", True),
    "admin://config/tabulator": ("quilt_mcp.services.governance_service", "admin_tabulator_open_query_get", True),
    # Athena resources
    "athena://databases": ("quilt_mcp.services.athena_read_service", "athena_databases_list", False),
    "athena://workgroups": ("quilt_mcp.services.athena_read_service", "athena_workgroups_list", False),
    "athena://query/history": ("quilt_mcp.services.athena_read_service", "athena_query_history", False),
    # Metadata resources
    "metadata://templates": ("quilt_mcp.services.metadata_service", "list_metadata_templates", False),
    "metadata://examples": ("quilt_mcp.services.metadata_service", "show_metadata_examples", False),
    "metadata://troubleshooting": (None, None, False),  # Static response
    # Workflow resources
    "workflow://workflows": ("quilt_mcp.services.workflow_service", "workflow_list_all", False),
    # Tabulator resources
    "tabulator://buckets": ("quilt_mcp.services.tabulator_service", "tabulator_buckets_list", True),
}

_STATEFUL_RESOURCE_URIS = {
    "metadata://templates",
    "metadata://examples",
    "metadata://troubleshooting",
    "workflow://workflows",
}


def _get_resource_service_map() -> dict[str, tuple[str | None, str | None, bool]]:
    from quilt_mcp.config import get_mode_config

    mode_config = get_mode_config()
    if mode_config.is_multiuser:
        return {uri: entry for uri, entry in _BASE_RESOURCE_SERVICE_MAP.items() if uri not in _STATEFUL_RESOURCE_URIS}
    return _BASE_RESOURCE_SERVICE_MAP


async def get_resource(uri: Optional[str] = None) -> GetResourceSuccess | GetResourceError:
    """Access MCP resources via tool interface for backward compatibility.

    This tool provides access to MCP resources through a standard tool interface,
    enabling older MCP clients that don't support native resources to access resource data.

    ## Discovery Mode

    Call without a URI to list all available resources:

    ```python
    result = await get_resource()
    # Returns: {"resources": [...list of all 16 resources...]}
    ```

    ## Resource Access

    Call with a specific URI to read that resource:

    ```python
    result = await get_resource(uri="auth://status")
    # Returns the resource data
    ```

    ## Available Resources (mode-dependent)

    ### Auth Resources (3)
    - `auth://status` - Authentication status
    - `auth://catalog/info` - Catalog configuration
    - `auth://filesystem/status` - Filesystem permissions

    ### Permissions Resources (1)
    - `permissions://recommendations` - Bucket recommendations
    Note: `discover_permissions` is a TOOL (not resource) to accept bucket parameters

    ### Admin Resources (4) - Require admin privileges
    - `admin://users` - User list
    - `admin://roles` - Role list
    - `admin://config/sso` - SSO configuration
    - `admin://config/tabulator` - Tabulator configuration

    ### Athena Resources (3)
    - `athena://databases` - Database list
    - `athena://workgroups` - Workgroup list
    - `athena://query/history` - Query history (last 50)

    ### Metadata Resources (3, local dev only)
    - `metadata://templates` - Template list
    - `metadata://examples` - Metadata examples
    - `metadata://troubleshooting` - Troubleshooting guide

    ### Workflow Resources (1, local dev only)
    - `workflow://workflows` - Workflow list

    ### Tabulator Resources (1)
    - `tabulator://buckets` - Bucket list

    Args:
        uri: Resource URI to access, or None/empty for discovery mode

    Returns:
        GetResourceSuccess with resource data, or GetResourceError on failure

    Examples:
        >>> # List all resources
        >>> result = await get_resource()
        >>> print(f"Found {len(result.data['resources'])} resources")

        >>> # Read authentication status
        >>> result = await get_resource(uri="auth://status")
        >>> if result.success:
        >>>     print(result.data)
    """
    import asyncio
    import json
    from importlib import import_module

    try:
        # Discovery mode - list all available resources
        if uri is None or uri == "":
            resources_list = []
            resource_map = _get_resource_service_map()
            for resource_uri in resource_map.keys():
                resources_list.append(
                    {
                        "uri": resource_uri,
                        "description": _get_resource_description(resource_uri),
                    }
                )

            return GetResourceSuccess(
                uri="discovery://resources",
                resource_name="Available Resources",
                data={"resources": resources_list, "count": len(resources_list)},
                mime_type="application/json",
            )

        # Validate URI exists
        resource_map = _get_resource_service_map()
        if uri not in resource_map:
            return GetResourceError(
                error=f"Resource not found: {uri}",
                cause="KeyError",
                valid_uris=list(resource_map.keys()),
                possible_fixes=[
                    "Use discovery mode (no URI) to list available resources",
                    "Check the URI for typos",
                ],
            )

        # Get service function details
        module_path, function_name, is_async = resource_map[uri]

        # Handle static responses
        if module_path is None or function_name is None:
            if uri == "metadata://troubleshooting":
                data = {
                    "status": "info",
                    "message": "For metadata troubleshooting, use fix_metadata_validation_issues()",
                }
                return GetResourceSuccess(
                    uri=uri,
                    resource_name="Metadata Troubleshooting",
                    data=data,
                    mime_type="application/json",
                )
            # Shouldn't reach here - all static URIs should be handled above
            return GetResourceError(
                error=f"Static resource not implemented: {uri}",
                cause="NotImplementedError",
                possible_fixes=["Report this issue - static resource handler missing"],
            )

        # Import and invoke the service function (module_path and function_name are guaranteed non-None here)
        module = import_module(module_path)
        service_func = getattr(module, function_name)

        # Handle async vs sync
        if is_async:
            result = await service_func()
        else:
            # Run sync functions in thread pool to avoid blocking
            result = await asyncio.to_thread(service_func)

        # Handle special cases with parameters
        if uri == "athena://query/history":
            # This function needs default parameters
            from quilt_mcp.services.athena_read_service import athena_query_history

            result = await asyncio.to_thread(
                athena_query_history,
                max_results=50,
                status_filter=None,
                start_time=None,
                end_time=None,
                service=None,
            )

        # Serialize result
        if hasattr(result, 'model_dump'):
            data = result.model_dump()
        elif isinstance(result, dict):
            data = result
        else:
            data = {"result": str(result)}

        return GetResourceSuccess(
            uri=uri,
            resource_name=_get_resource_name(uri),
            data=data,
            mime_type="application/json",
        )

    except Exception as e:
        error_msg = str(e)

        # Check for authorization errors
        if any(keyword in error_msg.lower() for keyword in ["unauthorized", "403", "401", "permission"]):
            return GetResourceError(
                error=error_msg,
                cause=type(e).__name__,
                suggested_actions=[
                    "Verify you have the required privileges",
                    "For admin resources, ensure you have admin role",
                    "Check authentication with auth://status",
                ],
            )

        return GetResourceError(
            error=error_msg,
            cause=type(e).__name__,
            possible_fixes=[
                "Check server logs for details",
                "Verify the resource is properly configured",
                "Report this issue if it persists",
            ],
        )


def _get_resource_name(uri: str) -> str:
    """Get human-readable name for a resource URI."""
    names = {
        "auth://status": "Auth Status",
        "auth://catalog/info": "Catalog Info",
        "auth://filesystem/status": "Filesystem Status",
        "permissions://recommendations": "Bucket Recommendations",
        "admin://users": "Admin Users List",
        "admin://roles": "Admin Roles List",
        "admin://config/sso": "SSO Configuration",
        "admin://config/tabulator": "Tabulator Configuration",
        "athena://databases": "Athena Databases",
        "athena://workgroups": "Athena Workgroups",
        "athena://query/history": "Athena Query History",
        "metadata://templates": "Metadata Templates",
        "metadata://examples": "Metadata Examples",
        "metadata://troubleshooting": "Metadata Troubleshooting",
        "workflow://workflows": "Workflows List",
        "tabulator://buckets": "Tabulator Buckets",
    }
    return names.get(uri, uri)


def _get_resource_description(uri: str) -> str:
    """Get description for a resource URI."""
    descriptions = {
        "auth://status": "Check authentication status and catalog configuration",
        "auth://catalog/info": "Get catalog configuration details",
        "auth://filesystem/status": "Check filesystem permissions and writability",
        "permissions://recommendations": "Smart bucket recommendations based on permissions",
        "admin://users": "List all users with roles and status (requires admin)",
        "admin://roles": "List all available roles (requires admin)",
        "admin://config/sso": "Current SSO configuration (requires admin)",
        "admin://config/tabulator": "Tabulator open query configuration (requires admin)",
        "athena://databases": "List available Athena databases",
        "athena://workgroups": "List available Athena workgroups",
        "athena://query/history": "Recent Athena query execution history",
        "metadata://templates": "List available metadata templates",
        "metadata://examples": "Example metadata configurations",
        "metadata://troubleshooting": "Common metadata issues and solutions",
        "workflow://workflows": "List all tracked workflows",
        "tabulator://buckets": "List buckets with tabulator tables",
    }
    return descriptions.get(uri, "")
