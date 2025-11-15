"""Backend status helper for search catalog functionality.

This module provides the get_search_backend_status() helper function that
reports on search backend availability, capabilities, and status for
integration into catalog_info resources and search_catalog responses.
"""

from typing import Dict, List, Any, Optional
from ..backends.base import BackendType, BackendStatus, SearchBackend


def get_backend_capabilities(backend_type: BackendType) -> List[str]:
    """Get the capabilities of a specific backend type.

    Args:
        backend_type: The type of backend

    Returns:
        List of capability strings
    """
    capabilities_map = {
        BackendType.ELASTICSEARCH: [
            "metadata_search",
            "content_search",
            "package_search",
            "object_search",
            "natural_language_query",
        ],
        BackendType.GRAPHQL: [
            "metadata_search",
            "advanced_filtering",
            "relationship_queries",
            "package_search",
            "object_search",
            "structured_queries",
        ],
    }

    return capabilities_map.get(backend_type, [])


def get_search_backend_status() -> Dict[str, Any]:
    """Get comprehensive status of all search backends.

    This function checks all registered search backends and returns their
    availability, capabilities, and status. It's used for:
    1. catalog_info resource - discovery
    2. search_catalog responses - debugging

    Returns:
        Dict with the following structure:
        {
            "available": bool,  # True if any backend is available
            "backend": str,     # Primary backend name ("elasticsearch" or "graphql")
            "capabilities": List[str],  # Capabilities of primary backend
            "status": str,      # Overall status ("ready", "unavailable", "error")
            "backends": {       # Detailed status per backend
                "elasticsearch": {
                    "available": bool,
                    "status": str,
                    "capabilities": List[str],
                    "error": Optional[str]
                },
                "graphql": {
                    "available": bool,
                    "status": str,
                    "capabilities": List[str],
                    "error": Optional[str]
                }
            }
        }

    Example:
        ```python
        from quilt_mcp.search.utils.backend_status import get_search_backend_status

        status = get_search_backend_status()
        if status["available"]:
            print(f"Search ready using {status['backend']}")
            print(f"Capabilities: {', '.join(status['capabilities'])}")
        else:
            print(f"Search unavailable: {status['status']}")
        ```
    """
    try:
        # Import here to avoid circular dependency
        from ..tools.unified_search import UnifiedSearchEngine

        # Get the search engine and its registry
        engine = UnifiedSearchEngine()
        registry = engine.registry

        # Ensure all backends are initialized before checking status
        for backend_type in [BackendType.ELASTICSEARCH, BackendType.GRAPHQL]:
            backend = registry.get_backend(backend_type)
            if backend:
                backend.ensure_initialized()

        # Check which backend is selected as primary
        primary_backend = registry._select_primary_backend()

        # Build detailed status for each backend
        backend_details = {}

        for backend_type in [BackendType.ELASTICSEARCH, BackendType.GRAPHQL]:
            backend = registry.get_backend(backend_type)

            if backend:
                is_available = backend.status == BackendStatus.AVAILABLE
                capabilities = get_backend_capabilities(backend_type) if is_available else []

                backend_details[backend_type.value] = {
                    "available": is_available,
                    "status": backend.status.value,
                    "capabilities": capabilities,
                    "error": backend.last_error if backend.last_error else None,
                }
            else:
                # Backend not registered
                backend_details[backend_type.value] = {
                    "available": False,
                    "status": "not_registered",
                    "capabilities": [],
                    "error": "Backend not registered in search engine",
                }

        # Determine overall status
        any_available = any(details["available"] for details in backend_details.values())

        if primary_backend:
            # We have a working primary backend
            primary_backend_name = primary_backend.backend_type.value
            primary_capabilities = get_backend_capabilities(primary_backend.backend_type)
            overall_status = "ready"
        else:
            # No backends available
            primary_backend_name = None
            primary_capabilities = []

            # Check if it's an auth error or just unavailable
            has_auth_error = any(
                backend and hasattr(backend, "_auth_error")
                for backend in [
                    registry.get_backend(BackendType.ELASTICSEARCH),
                    registry.get_backend(BackendType.GRAPHQL),
                ]
            )

            overall_status = "authentication_required" if has_auth_error else "unavailable"

        return {
            "available": any_available,
            "backend": primary_backend_name,
            "capabilities": primary_capabilities,
            "status": overall_status,
            "backends": backend_details,
        }

    except Exception as e:
        # Fallback error response
        return {
            "available": False,
            "backend": None,
            "capabilities": [],
            "status": "error",
            "error": f"Failed to get backend status: {e}",
            "backends": {
                "elasticsearch": {
                    "available": False,
                    "status": "error",
                    "capabilities": [],
                    "error": str(e),
                },
                "graphql": {
                    "available": False,
                    "status": "error",
                    "capabilities": [],
                    "error": str(e),
                },
            },
        }


__all__ = [
    "get_search_backend_status",
    "get_backend_capabilities",
]
