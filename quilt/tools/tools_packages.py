from __future__ import annotations
from typing import Any, Dict, List
import quilt3, os
from .. import mcp

@mcp.tool()
def packages_list(registry: str | None = None, limit: int | None = None, prefix: str | None = None) -> Dict[str, Any]:
    try:
        pkgs = quilt3.list_packages(registry=registry, limit=limit, prefix=prefix)
        return {"status": "ok", "packages": pkgs}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
def packages_search(query: str, registry: str | None = None, limit: int | None = None) -> Dict[str, Any]:
    try:
        results = quilt3.search(query, registry=registry, limit=limit)
        return {"status": "ok", "results": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
def package_browse(package_name: str, registry: str | None = None, top: int | None = None, include: List[str] | None = None, exclude: List[str] | None = None) -> Dict[str, Any]:
    try:
        pkg = quilt3.Package.browse(package_name, registry=registry, top=top, include=include, exclude=exclude)
        return {"status": "ok", "contents": pkg.keys()}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
def package_contents_search(package_name: str, query: str, registry: str | None = None) -> Dict[str, Any]:
    try:
        pkg = quilt3.Package.browse(package_name, registry=registry)
        matches = [k for k in pkg.keys() if query.lower() in k.lower()]
        return {"status": "ok", "matches": matches, "count": len(matches)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
