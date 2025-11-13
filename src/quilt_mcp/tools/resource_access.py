"""Resource access tool implementation."""

from typing import Any, Callable, TypedDict


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