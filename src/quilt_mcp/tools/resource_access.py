"""Resource access tool implementation."""

from typing import Any, Callable, TypedDict

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
                    raise ValueError(
                        f"Template variable not in parameter mapping: {var} in {uri}"
                    )


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