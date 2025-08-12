from __future__ import annotations

from typing import Any

import quilt3

from ..constants import DEFAULT_REGISTRY
from ..server import mcp


@mcp.tool()
def packages_list(registry: str = DEFAULT_REGISTRY, limit: int = 0, prefix: str = "") -> dict[str, Any]:
    """List all available Quilt packages in a registry.
    
    Args:
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        limit: Maximum number of packages to return, 0 for unlimited (default: 0)
        prefix: Filter packages by name prefix (default: "")
    
    Returns:
        Dict with list of package names.
    """
    # Pass registry to quilt3.list_packages(), then apply filtering
    pkgs = list(quilt3.list_packages(registry=registry))  # Convert generator to list

    # Apply prefix filtering if specified
    if prefix:
        pkgs = [pkg for pkg in pkgs if pkg.startswith(prefix)]

    # Apply limit if specified
    if limit > 0:
        pkgs = pkgs[:limit]

    return {"packages": pkgs}

@mcp.tool()
def packages_search(query: str, registry: str = DEFAULT_REGISTRY, limit: int = 10) -> dict[str, Any]:
    """Search for Quilt packages by content and metadata.
    
    Args:
        query: Search query string to find packages
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)  
        limit: Maximum number of search results (default: 10)
    
    Returns:
        Dict with search results including package names and metadata.
    """
    # quilt3.search() only supports query and limit, not registry
    effective_limit = limit if limit > 0 else 10
    results = quilt3.search(query, limit=effective_limit)
    return {"results": results}

@mcp.tool()
def package_browse(package_name: str, registry: str = DEFAULT_REGISTRY, top: int = 0, include: list[str] = [], exclude: list[str] = []) -> dict[str, Any]:
    """Browse the contents of a Quilt package.
    
    Args:
        package_name: Name of the package to browse (e.g., "username/package-name")
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        top: Limit number of entries returned, 0 for unlimited (default: 0)
        include: Include patterns (currently unused, reserved for future)
        exclude: Exclude patterns (currently unused, reserved for future)
    
    Returns:
        Dict with list of package contents (file/folder paths).
    """
    # Use the provided registry
    pkg = quilt3.Package.browse(package_name, registry=registry)
    contents = list(pkg.keys())

    # Apply top limit if specified
    if top > 0:
        contents = contents[:top]

    return {"contents": contents}

@mcp.tool()
def package_contents_search(package_name: str, query: str, registry: str = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Search within a package's contents by filename or path.
    
    Args:
        package_name: Name of the package to search (e.g., "username/package-name")
        query: Search query to match against file/folder names
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
    
    Returns:
        Dict with matching paths and count of results.
    """
    # Use the provided registry
    pkg = quilt3.Package.browse(package_name, registry=registry)
    matches = [k for k in pkg.keys() if query.lower() in k.lower()]
    return {"matches": matches, "count": len(matches)}
