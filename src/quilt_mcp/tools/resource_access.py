"""Resource access tool implementation."""

import asyncio
from typing import Any, Callable, Optional, TypedDict, Union

from quilt_mcp.models.responses import (
    ResourceMetadata,
    GetResourceSuccess,
    GetResourceError,
)
from quilt_mcp.services.auth_metadata import (
    auth_status,
    catalog_info,
)
from quilt_mcp.services.governance_service import admin_users_list
from quilt_mcp.services.permissions_service import discover_permissions
from quilt_mcp.services.metadata_service import get_metadata_template


class ResourceDefinition(TypedDict):
    """Definition of a single resource in the registry."""

    uri: str  # URI pattern (may contain {variables})
    name: str  # Human-readable name
    description: str  # Functional description
    service_function: Callable[..., Any]  # Function to invoke
    is_async: bool  # Whether service function is async
    is_template: bool  # Whether URI contains variables
    template_variables: list[str]  # Variable names (empty if not templated)
    requires_admin: bool  # Whether admin privileges required
    category: str  # Resource category
    parameter_mapping: dict[str, str]  # URI variable → function parameter


def validate_registry(registry: dict[str, ResourceDefinition]) -> None:
    """Validate registry structure and consistency.

    Args:
        registry: URI → ResourceDefinition mapping

    Raises:
        ValueError: Registry validation failed
    """
    for uri, defn in registry.items():
        # Validate URI matches definition URI
        if uri != defn["uri"]:
            raise ValueError(f"URI mismatch: key={uri}, defn={defn['uri']}")

        # Validate service function is callable
        if not callable(defn["service_function"]):
            raise ValueError(f"Service function not callable: {uri}")

        # Validate template consistency
        has_braces = "{" in uri
        if defn["is_template"] != has_braces:
            raise ValueError(f"Template flag inconsistent with URI: {uri}")

        # Validate template variables
        if defn["is_template"] and not defn["template_variables"]:
            raise ValueError(f"Template URI missing variable list: {uri}")

        # Validate parameter mapping for templates
        if defn["is_template"]:
            for var in defn["template_variables"]:
                if var not in defn["parameter_mapping"]:
                    raise ValueError(f"Template variable not in parameter mapping: {var} in {uri}")


# Build resource registry (Phase 1: 5 representative resources)
RESOURCE_REGISTRY: dict[str, ResourceDefinition] = {
    "auth://status": {
        "uri": "auth://status",
        "name": "Auth Status",
        "description": "Check authentication status and catalog configuration",
        "service_function": auth_status,
        "is_async": False,
        "is_template": False,
        "template_variables": [],
        "requires_admin": False,
        "category": "auth",
        "parameter_mapping": {},
    },
    "auth://catalog/info": {
        "uri": "auth://catalog/info",
        "name": "Catalog Info",
        "description": "Get catalog configuration details",
        "service_function": catalog_info,
        "is_async": False,
        "is_template": False,
        "template_variables": [],
        "requires_admin": False,
        "category": "auth",
        "parameter_mapping": {},
    },
    "admin://users": {
        "uri": "admin://users",
        "name": "Admin Users List",
        "description": "List all users in the Quilt registry with their roles and status (requires admin privileges)",
        "service_function": admin_users_list,
        "is_async": True,
        "is_template": False,
        "template_variables": [],
        "requires_admin": True,
        "category": "admin",
        "parameter_mapping": {},
    },
    "permissions://discover": {
        "uri": "permissions://discover",
        "name": "Permissions Discovery",
        "description": "Discover AWS permissions for current user/role",
        "service_function": discover_permissions,
        "is_async": False,
        "is_template": False,
        "template_variables": [],
        "requires_admin": False,
        "category": "permissions",
        "parameter_mapping": {},
    },
    "metadata://templates/{template}": {
        "uri": "metadata://templates/{template}",
        "name": "Metadata Template",
        "description": "Get specific metadata template by name",
        "service_function": get_metadata_template,
        "is_async": False,
        "is_template": True,
        "template_variables": ["template"],
        "requires_admin": False,
        "category": "metadata",
        "parameter_mapping": {"template": "name"},
    },
}

# Validate registry at module initialization
validate_registry(RESOURCE_REGISTRY)


class ResourceManager:
    """Manages resource URI routing and service function invocation.

    This class provides a centralized orchestrator for:
    - URI validation and lookup
    - Static URI dispatching (O(1) dict lookup)
    - Template URI expansion (Phase 2+)
    - Service function invocation with proper async handling
    - Result serialization and error handling

    Design Principle: Pure orchestrator - no business logic, only routing.
    """

    def __init__(self, registry: dict[str, ResourceDefinition]):
        """Initialize with resource registry.

        Args:
            registry: URI → ResourceDefinition mapping
        """
        self._registry = registry
        self._static_uris = {uri: defn for uri, defn in registry.items() if not defn["is_template"]}

    async def get_resource(self, uri: Optional[str]) -> dict[str, Any]:
        """Retrieve resource data by URI.

        Args:
            uri: Resource URI or None/empty for discovery mode

        Returns:
            Resource data dict (to be wrapped in GetResourceSuccess/Error)

        Raises:
            ValueError: Invalid URI format
            KeyError: URI not found in registry
            RuntimeError: Service function execution failed
        """
        # Discovery mode
        if uri is None or uri == "":
            return await self.get_discovery_data()

        # Validate URI format
        if not uri or "://" not in uri:
            raise ValueError(f"Invalid URI format: {uri}")

        # Static URI lookup (Phase 1)
        if uri not in self._static_uris:
            raise KeyError(f"Resource URI not recognized: {uri}")

        # Get definition and invoke service function
        defn = self._static_uris[uri]
        result = await self._invoke_service_function(defn, params={})

        return {
            "uri": uri,
            "resource_name": defn["name"],
            "data": result,
            "mime_type": "application/json",
        }

    async def get_discovery_data(self) -> dict[str, list[ResourceMetadata]]:
        """Generate discovery mode response.

        Returns:
            Dict mapping category → list of ResourceMetadata
        """
        # Group resources by category
        by_category: dict[str, list[ResourceMetadata]] = {}

        for uri, defn in self._registry.items():
            metadata = ResourceMetadata(
                uri=uri,
                name=defn["name"],
                description=defn["description"],
                is_template=defn["is_template"],
                template_variables=defn["template_variables"],
                requires_admin=defn["requires_admin"],
                category=defn["category"],
            )

            if metadata.category not in by_category:
                by_category[metadata.category] = []

            by_category[metadata.category].append(metadata)

        # Sort within each category by URI
        for category in by_category:
            by_category[category].sort(key=lambda m: m.uri)

        return by_category

    async def _invoke_service_function(self, defn: ResourceDefinition, params: dict[str, Any]) -> dict[str, Any]:
        """Invoke service function and deserialize result.

        Args:
            defn: Resource definition
            params: Parameters for service function (empty for Phase 1)

        Returns:
            Deserialized result as dict
        """
        func = defn["service_function"]

        # Handle async vs sync functions
        if defn["is_async"]:
            result = await func(**params)
        else:
            # Run sync functions in thread pool
            result = await asyncio.to_thread(func, **params)

        # Deserialize Pydantic models to dict
        if hasattr(result, "model_dump"):
            return dict(result.model_dump())

        # Already a dict
        if isinstance(result, dict):
            return result

        # Fallback: attempt to convert to dict
        try:
            return dict(result)
        except (TypeError, ValueError) as e:
            raise RuntimeError(f"Unable to serialize result: {e}")


async def get_resource(uri: Optional[str] = None) -> Union[GetResourceSuccess, GetResourceError]:
    """Access MCP resources via URI patterns for structured data discovery and retrieval.

    This tool provides a unified interface for accessing various MCP resources through
    URI-based addressing. It supports both static resources (fixed URIs) and discovery
    mode (listing available resources).

    ## URI Schemes and Resources

    ### Auth Resources (auth://)
    - `auth://status` - Authentication status and catalog configuration
    - `auth://catalog/info` - Catalog configuration details

    ### Admin Resources (admin://) - Requires admin privileges
    - `admin://users` - List all users with roles and status

    ### Permissions Resources (permissions://)
    - `permissions://discover` - Discover AWS permissions for current user/role

    ### Metadata Resources (metadata://)
    - `metadata://templates/{template}` - Get specific metadata template (Phase 2+)

    ## Discovery Mode

    When called without a URI (uri=None or uri=""), returns a categorized list of all
    available resources with their metadata:

    ```python
    # Discover all available resources
    result = await get_resource()
    # or
    result = await get_resource(uri="")

    # Response structure:
    {
        "success": true,
        "uri": "discovery://resources",
        "resource_name": "Available Resources",
        "data": {
            "auth": [
                {
                    "uri": "auth://status",
                    "name": "Auth Status",
                    "description": "Check authentication status",
                    "is_template": false,
                    "template_variables": [],
                    "requires_admin": false,
                    "category": "auth"
                }
            ],
            "admin": [...],
            "permissions": [...],
            "metadata": [...]
        }
    }
    ```

    ## Static Resource Access

    For static resources (Phase 1), provide the exact URI:

    ```python
    # Get authentication status
    result = await get_resource(uri="auth://status")

    # Response:
    {
        "success": true,
        "uri": "auth://status",
        "resource_name": "Auth Status",
        "data": {
            "authenticated": true,
            "catalog_url": "https://demo.quiltdata.com",
            "user": "john.doe@example.com"
        },
        "timestamp": "2024-01-15T10:30:00Z",
        "mime_type": "application/json"
    }
    ```

    ## Error Handling

    The tool returns structured error responses for various failure scenarios:

    ### Invalid URI Format
    ```python
    result = await get_resource(uri="invalid-no-scheme")
    # Returns GetResourceError with suggested fixes
    ```

    ### Unknown Resource URI
    ```python
    result = await get_resource(uri="unknown://resource")
    # Returns GetResourceError with list of valid URIs
    ```

    ### Authorization Failures
    ```python
    result = await get_resource(uri="admin://users")  # Without admin privileges
    # Returns GetResourceError with authorization guidance
    ```

    ## Performance Characteristics

    - **Discovery Mode**: O(n) where n = number of registered resources
    - **Static URI Lookup**: O(1) dictionary lookup
    - **Service Invocation**: Varies by service (typically < 100ms for local, < 500ms for AWS)
    - **Overhead**: < 10% compared to direct service calls

    ## Design Principles

    1. **URI-Based Addressing**: Resources identified by semantic URIs (scheme://path)
    2. **Progressive Enhancement**: Phase 1 supports static URIs, Phase 2+ adds templates
    3. **Fail-Safe Design**: All errors return structured GetResourceError responses
    4. **Zero Business Logic**: Pure orchestration layer, delegates to services
    5. **Type Safety**: Pydantic models for all inputs/outputs

    Args:
        uri: Resource URI to access, or None/empty string for discovery mode.
             Format: "scheme://path" or "scheme://path/{variable}" (Phase 2+)

    Returns:
        GetResourceSuccess: Contains resource data, metadata, and timestamp
        GetResourceError: Contains error details, causes, and suggested fixes

    Examples:
        >>> # Discovery mode - list all available resources
        >>> result = await get_resource()
        >>> if result.success:
        >>>     for category, resources in result.data.items():
        >>>         print(f"{category}: {len(resources)} resources")

        >>> # Access specific resource
        >>> result = await get_resource(uri="auth://status")
        >>> if result.success:
        >>>     print(f"Authenticated: {result.data['authenticated']}")
        >>> else:
        >>>     print(f"Error: {result.error}")

        >>> # Handle authorization errors
        >>> result = await get_resource(uri="admin://users")
        >>> if not result.success and "Unauthorized" in result.error:
        >>>     print("Admin privileges required")

    Raises:
        This function does not raise exceptions. All errors are captured and
        returned as GetResourceError objects with detailed context.
    """
    try:
        # Create resource manager instance
        manager = ResourceManager(RESOURCE_REGISTRY)

        # Discovery mode
        if uri is None or uri == "":
            discovery_data = await manager.get_discovery_data()

            # Convert ResourceMetadata objects to dicts
            serialized_data = {}
            for category, resources in discovery_data.items():
                serialized_data[category] = [
                    r.model_dump() if hasattr(r, 'model_dump') else dict(r) for r in resources
                ]

            return GetResourceSuccess(
                uri="discovery://resources",
                resource_name="Available Resources",
                data=serialized_data,
                mime_type="application/json",
            )

        # Static resource access
        result = await manager.get_resource(uri)

        return GetResourceSuccess(
            uri=result["uri"],
            resource_name=result["resource_name"],
            data=result["data"],
            mime_type=result.get("mime_type", "application/json"),
        )

    except ValueError as e:
        # Invalid URI format
        return GetResourceError(
            error=str(e),
            cause="ValueError",
            possible_fixes=[
                "Ensure URI follows format: scheme://path",
                "Use discovery mode (uri=None) to list available resources",
                "Check for typos in the URI scheme or path",
            ],
        )

    except KeyError as e:
        # Unknown resource URI
        error_msg = str(e).strip("'\"")

        # Get list of valid URIs for helpful error message
        try:
            manager = ResourceManager(RESOURCE_REGISTRY)
            valid_uris = list(RESOURCE_REGISTRY.keys())
        except Exception:
            valid_uris = None

        return GetResourceError(
            error=error_msg,
            cause="KeyError",
            valid_uris=valid_uris,
            possible_fixes=[
                "Use discovery mode to see available resources",
                "Check the URI for typos",
                "Verify the resource is available in this phase",
            ],
        )

    except RuntimeError as e:
        # Service execution error
        error_msg = str(e)

        # Check for authorization errors
        if "Unauthorized" in error_msg or "403" in error_msg or "401" in error_msg:
            return GetResourceError(
                error=error_msg,
                cause="RuntimeError",
                suggested_actions=[
                    "Ensure you have the required privileges",
                    "For admin resources, verify admin role assignment",
                    "Check authentication with auth://status resource",
                ],
            )

        return GetResourceError(
            error=error_msg,
            cause="RuntimeError",
            possible_fixes=[
                "Check service availability",
                "Verify AWS credentials if accessing AWS resources",
                "Review service logs for detailed error information",
            ],
        )

    except Exception as e:
        # Catch-all for unexpected errors
        return GetResourceError(
            error=str(e),
            cause=type(e).__name__,
            possible_fixes=["Check server logs for detailed error information", "Report this issue if it persists"],
        )
