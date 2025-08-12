from __future__ import annotations
from typing import Any, Dict, List
import quilt3, os
from .. import mcp

@mcp.tool()
def packages_list(registry: str | None = None, limit: int | None = None, prefix: str | None = None) -> Dict[str, Any]:
    # quilt3.list_packages() doesn't support these parameters, so we implement the filtering ourselves
    pkgs = list(quilt3.list_packages())  # Convert generator to list
    
    # Apply prefix filtering if specified
    if prefix:
        pkgs = [pkg for pkg in pkgs if pkg.startswith(prefix)]
    
    # Apply limit if specified
    if limit:
        pkgs = pkgs[:limit]
        
    return {"packages": pkgs}

@mcp.tool()
def packages_search(query: str, registry: str | None = None, limit: int | None = None) -> Dict[str, Any]:
    # quilt3.search() only supports query and limit, not registry
    effective_limit = limit if limit else 10
    results = quilt3.search(query, limit=effective_limit)
    return {"results": results}

@mcp.tool()
def package_browse(package_name: str, registry: str | None = None, top: int | None = None, include: List[str] | None = None, exclude: List[str] | None = None) -> Dict[str, Any]:
    # quilt3.Package.browse() doesn't support top, include, exclude parameters
    pkg = quilt3.Package.browse(package_name)
    contents = list(pkg.keys())
    
    # Apply top limit if specified
    if top:
        contents = contents[:top]
        
    return {"contents": contents}

@mcp.tool()
def package_contents_search(package_name: str, query: str, registry: str | None = None) -> Dict[str, Any]:
    # quilt3.Package.browse() doesn't support registry parameter
    pkg = quilt3.Package.browse(package_name)
    matches = [k for k in pkg.keys() if query.lower() in k.lower()]
    return {"matches": matches, "count": len(matches)}
