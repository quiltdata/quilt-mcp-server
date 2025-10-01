from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..constants import DEFAULT_REGISTRY
from ..clients import catalog as catalog_client
from ..runtime import get_active_token
from ..utils import format_error_response, generate_signed_url


logger = logging.getLogger(__name__)

# Helpers


def _normalize_registry(bucket_or_uri: str) -> str:
    """Normalize registry input to s3:// URI format.

    Args:
        bucket_or_uri: Either a bucket name (e.g., "my-bucket") or s3:// URI (e.g., "s3://my-bucket")

    Returns:
        Full s3:// URI format (e.g., "s3://my-bucket")
    """
    if not bucket_or_uri:
        return bucket_or_uri

    if bucket_or_uri.startswith(("http://", "https://")):
        # Stateless catalog endpoints use HTTPS
        return bucket_or_uri.rstrip("/")

    if bucket_or_uri.startswith("s3://"):
        return bucket_or_uri.rstrip("/")

    # Backwards compatibility for legacy bucket identifiers
    return f"s3://{bucket_or_uri.strip('/')}"


def packages_list(registry: str = DEFAULT_REGISTRY, limit: int = 0, prefix: str = "") -> dict[str, Any]:
    """List all available Quilt packages in a registry.

    Args:
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        limit: Maximum number of packages to return, 0 for unlimited (default: 0)
        prefix: Filter packages by name prefix (default: "")

    Returns:
        Dict with list of package names.
    """
    normalized_registry = _normalize_registry(registry)
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required to list packages")

    try:
        pkgs = catalog_client.catalog_packages_list(
            registry_url=normalized_registry,
            auth_token=token,
            limit=limit or None,
            prefix=prefix or None,
        )
    except Exception as exc:
        return format_error_response(f"Failed to list packages: {exc}")

    filtered = pkgs or []
    if prefix:
        filtered = [name for name in filtered if isinstance(name, str) and name.startswith(prefix)]

    if limit and limit > 0:
        filtered = filtered[:limit]

    return {"packages": filtered}


def packages_search(query: str, registry: str = DEFAULT_REGISTRY, limit: int = 10, from_: int = 0) -> dict[str, Any]:
    """Search for Quilt packages via stateless GraphQL API."""
    normalized_registry = _normalize_registry(registry)
    token = get_active_token()
    if not token:
        return {
            "success": False,
            "error": "Authorization token required for package search",
            "results": [],
            "query": query,
            "registry": normalized_registry,
        }

    variables = {
        "query": query,
        "limit": max(0, limit),
        "offset": max(0, from_),
    }

    gql = (
        "query($query: String!, $limit: Int, $offset: Int) {\n"
        "  packages(query: $query, first: $limit, after: $offset) {\n"
        "    edges {\n"
        "      node { name topHash tag updated description owner }\n"
        "    }\n"
        "    pageInfo { endCursor hasNextPage }\n"
        "  }\n"
        "}\n"
    )

    try:
        data = catalog_client.catalog_graphql_query(
            registry_url=normalized_registry,
            query=gql,
            variables=variables,
            auth_token=token,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("GraphQL package search failed: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "results": [],
            "query": query,
            "registry": normalized_registry,
        }

    packages_conn = data.get("packages", {}) if isinstance(data, dict) else {}
    edges = packages_conn.get("edges", []) or []
    page_info = packages_conn.get("pageInfo", {}) or {}
    results = [edge.get("node", {}) for edge in edges if isinstance(edge, dict)]

    return {
        "success": True,
        "results": results,
        "query": query,
        "registry": normalized_registry,
        "pagination": {
            "end_cursor": page_info.get("endCursor"),
            "has_next_page": page_info.get("hasNextPage", False),
        },
    }


def package_browse(
    package_name: str,
    registry: str = DEFAULT_REGISTRY,
    recursive: bool = True,
    include_file_info: bool = True,
    max_depth: int = 0,
    top: int = 0,
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
    include_signed_urls: bool = True,
) -> dict[str, Any]:
    """Browse the contents of a Quilt package with enhanced file information.

    Args:
        package_name: Name of the package to browse (e.g., "username/package-name")
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        recursive: Show full file tree instead of just top-level (default: True)
        include_file_info: Include file sizes, types, and modification dates (default: True)
        max_depth: Maximum directory depth to show, 0 for unlimited (default: 0)
        top: Limit number of entries returned, 0 for unlimited (default: 0)
        include: Include patterns (currently unused, reserved for future)
        exclude: Exclude patterns (currently unused, reserved for future)
        include_signed_urls: Include presigned download URLs for S3 objects (default: True)

    Returns:
        Dict with comprehensive package contents including file tree, sizes, types, and URLs.

    Examples:
        Basic browsing:
        package_browse("team/dataset")

        Flat view (top-level only):
        package_browse("team/dataset", recursive=False)

        Limited depth:
        package_browse("team/dataset", max_depth=2)
    """
    # Initialize mutable defaults
    if include is None:
        include = []
    if exclude is None:
        exclude = []

    normalized_registry = _normalize_registry(registry)
    token = get_active_token()
    if not token:
        return {
            "success": False,
            "error": "Authorization token required to browse packages",
        }

    query = """
    query PackageContents($name: String!, $first: Int) {
      package(name: $name) {
        name
        hash
        updated
        entries(first: $first) {
          edges {
            node {
              logicalKey
              physicalKey
              size
              hash
            }
          }
        }
      }
    }
    """

    try:
        data = catalog_client.catalog_graphql_query(
            registry_url=normalized_registry,
            query=query,
            variables={"name": package_name, "first": top or None},
            auth_token=token,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": "Failed to fetch package contents",
            "cause": str(exc),
        }

    package_info = (data or {}).get("package") if isinstance(data, dict) else None
    if not package_info:
        return {
            "success": False,
            "error": f"Package '{package_name}' not found in registry",
        }

    edges = package_info.get("entries", {}).get("edges", [])
    entries = []
    file_tree = {} if recursive else None
    total_size = 0
    file_types = set()

    # Apply top limit if specified
    for edge in edges[: top or None]:
        try:
            node = edge.get("node", {}) if isinstance(edge, dict) else {}
            logical_key = node.get("logicalKey")
            physical_key = node.get("physicalKey")
            file_size = node.get("size")
            file_hash = node.get("hash")

            if not logical_key:
                continue

            file_ext = logical_key.split(".")[-1].lower() if "." in logical_key else "unknown"
            file_types.add(file_ext)
            is_directory = logical_key.endswith("/") or file_size is None

            if file_size:
                total_size += file_size

            entry_data = {
                "logical_key": logical_key,
                "physical_key": physical_key,
                "size": file_size,
                "size_human": _format_file_size(file_size) if file_size else None,
                "hash": file_hash,
                "file_type": file_ext,
                "is_directory": is_directory,
            }

            if physical_key and physical_key.startswith("s3://"):
                entry_data["s3_uri"] = physical_key
                if include_signed_urls:
                    signed = generate_signed_url(physical_key)
                    if signed:
                        entry_data["download_url"] = signed

            entries.append(entry_data)

            if recursive and file_tree is not None:
                _add_to_file_tree(file_tree, logical_key, entry_data, max_depth)

        except Exception as exc:  # pragma: no cover - defensive logging
            entries.append(
                {
                    "logical_key": logical_key if "logical_key" in locals() else "unknown",
                    "physical_key": None,
                    "size": None,
                    "hash": "",
                    "error": str(exc),
                    "file_type": "error",
                }
            )

    summary = {
        "total_size": total_size,
        "total_size_human": _format_file_size(total_size),
        "file_types": sorted(file_types),
        "total_files": len([e for e in entries if not e.get("is_directory")]),
        "total_directories": len([e for e in entries if e.get("is_directory")]),
    }

    response: dict[str, Any] = {
        "success": True,
        "package_name": package_name,
        "registry": registry,
        "total_entries": len(entries),
        "summary": summary,
        "view_type": "recursive" if recursive else "flat",
        "entries": entries,
    }

    if recursive and file_tree:
        response["file_tree"] = file_tree

    response["package"] = {
        "hash": package_info.get("hash"),
        "updated": package_info.get("updated"),
        "name": package_info.get("name"),
    }

    return response


def _add_to_file_tree(tree: dict, path: str, entry_data: dict, max_depth: int):
    """Add an entry to the file tree structure."""
    if max_depth > 0:
        depth = path.count("/")
        if depth >= max_depth:
            return

    parts = path.split("/")
    current = tree

    # Navigate to the correct position in the tree
    for i, part in enumerate(parts[:-1]):
        if part not in current:
            current[part] = {"type": "directory", "children": {}}
        current = current[part]["children"]

    # Add the final entry
    final_part = parts[-1]
    current[final_part] = {
        "type": "file" if not entry_data.get("is_directory") else "directory",
        "size": entry_data.get("size"),
        "size_human": entry_data.get("size_human"),
        "file_type": entry_data.get("file_type"),
        "physical_key": entry_data.get("physical_key"),
        "download_url": entry_data.get("download_url"),
    }


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes is None:
        return "Unknown"

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def package_contents_search(
    package_name: str,
    query: str,
    registry: str = DEFAULT_REGISTRY,
    include_signed_urls: bool = True,
) -> dict[str, Any]:
    """Search within a package's contents by filename or path.

    Args:
        package_name: Name of the package to search (e.g., "username/package-name")
        query: Search query to match against file/folder names
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        include_signed_urls: Include presigned download URLs for S3 objects (default: True)

    Returns:
        Dict with matching entries including logical keys, S3 URIs, and optional download URLs.
    """
    normalized_registry = _normalize_registry(registry)
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required to search package contents")

    try:
        raw_entries = catalog_client.catalog_package_entries(
            registry_url=normalized_registry,
            package_name=package_name,
            auth_token=token,
        )
    except Exception as exc:
        return {
            "package_name": package_name,
            "query": query,
            "matches": [],
            "count": 0,
            "success": False,
            "error": str(exc),
        }

    matches = []
    for entry in raw_entries:
        logical_key = entry.get("logicalKey")
        if not logical_key or query.lower() not in logical_key.lower():
            continue

        match = {
            "logical_key": logical_key,
            "physical_key": entry.get("physicalKey"),
            "size": entry.get("size"),
            "hash": entry.get("hash"),
        }

        s3_uri = entry.get("physicalKey")
        if s3_uri and s3_uri.startswith("s3://"):
            match["s3_uri"] = s3_uri
            if include_signed_urls:
                signed = generate_signed_url(s3_uri)
                if signed:
                    match["download_url"] = signed

        matches.append(match)

    return {
        "package_name": package_name,
        "query": query,
        "matches": matches,
        "count": len(matches),
    }


def package_diff(
    package1_name: str,
    package2_name: str,
    registry: str = DEFAULT_REGISTRY,
    package1_hash: str = "",
    package2_hash: str = "",
) -> dict[str, Any]:
    """Compare two package versions and show differences.

    Args:
        package1_name: Name of the first package (e.g., "username/package-name")
        package2_name: Name of the second package (e.g., "username/package-name")
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        package1_hash: Optional specific hash for first package (default: latest)
        package2_hash: Optional specific hash for second package (default: latest)

    Returns:
        Dict with differences between the two packages including added, removed, and modified files.
    """
    normalized_registry = _normalize_registry(registry)
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required to diff packages")

    # TODO: Implement package diff via GraphQL/REST API.
    return {
        "success": False,
        "error": "Package diff not yet implemented for stateless backend",
        "package1": package1_name,
        "package2": package2_name,
    }


def packages(action: str | None = None, params: Optional[Dict[str, Any]] = None) -> dict[str, Any]:
    """
    Package browsing, search, and management operations.
    
    Available actions:
    - browse: Browse the contents of a Quilt package with enhanced file information
    - contents_search: Search within a package's contents by filename or path
    - diff: Compare two package versions and show differences
    - list: List all available Quilt packages in a registry
    - search: Search for Quilt packages by content and metadata
    
    Args:
        action: The operation to perform. If None, returns available actions.
        **kwargs: Action-specific parameters
    
    Returns:
        Action-specific response dictionary
    
    Examples:
        # Discovery mode
        result = packages()
        
        # Browse package
        result = packages(action="browse", package_name="user/dataset")
        
        # Search packages
        result = packages(action="search", query="genomics")
    
    For detailed parameter documentation, see individual action functions.
    """
    actions = {
        "browse": package_browse,
        "contents_search": package_contents_search,
        "diff": package_diff,
        "list": packages_list,
        "search": packages_search,
    }
    
    # Discovery mode
    if action is None:
        return {
            "success": True,
            "module": "packages",
            "actions": list(actions.keys()),
            "usage": "Call with action='<action_name>' to execute",
        }
    
    # Validate action
    if action not in actions:
        available = ", ".join(sorted(actions.keys()))
        return {
            "success": False,
            "error": f"Unknown action '{action}' for module 'packages'. Available actions: {available}",
        }
    
    # Dispatch
    try:
        func = actions[action]
        params = params or {}
        return func(**params)
    except TypeError as e:
        import inspect
        sig = inspect.signature(func)
        expected_params = list(sig.parameters.keys())
        return {
            "success": False,
            "error": f"Invalid parameters for action '{action}'. Expected: {expected_params}. Error: {str(e)}",
        }
    except Exception as e:
        if isinstance(e, dict) and not e.get("success"):
            return e
        return {
            "success": False,
            "error": f"Error executing action '{action}': {str(e)}",
        }
