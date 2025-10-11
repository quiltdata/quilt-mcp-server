from __future__ import annotations

from typing import Any

from ..constants import DEFAULT_REGISTRY
from ..services.quilt_service import QuiltService
from ..utils import generate_signed_url

# Helpers


def _normalize_registry(bucket_or_uri: str) -> str:
    """Normalize registry input to s3:// URI format.

    Args:
        bucket_or_uri: Either a bucket name (e.g., "my-bucket") or s3:// URI (e.g., "s3://my-bucket")

    Returns:
        Full s3:// URI format (e.g., "s3://my-bucket")
    """
    if bucket_or_uri.startswith("s3://"):
        return bucket_or_uri
    return f"s3://{bucket_or_uri}"


def packages_list(registry: str = DEFAULT_REGISTRY, limit: int = 0, prefix: str = "") -> dict[str, Any]:
    """List all available Quilt packages in a registry.

    Args:
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        limit: Maximum number of packages to return, 0 for unlimited (default: 0)
        prefix: Filter packages by name prefix (default: "")

    Returns:
        Dict with list of package names.
    """
    # Normalize registry and pass to QuiltService.list_packages(), then apply filtering
    normalized_registry = _normalize_registry(registry)
    # Suppress stdout during list_packages to avoid JSON-RPC interference
    from ..utils import suppress_stdout

    quilt_service = QuiltService()
    with suppress_stdout():
        pkgs = list(quilt_service.list_packages(registry=normalized_registry))  # Convert generator to list

    # Apply prefix filtering if specified
    if prefix:
        pkgs = [pkg for pkg in pkgs if pkg.startswith(prefix)]

    # Apply limit if specified
    if limit > 0:
        pkgs = pkgs[:limit]

    return {"packages": pkgs}


def packages_search(query: str, registry: str = DEFAULT_REGISTRY, limit: int = 10, from_: int = 0) -> dict[str, Any]:
    """Search for Quilt packages by content and metadata.

    Args:
        query: Search query string to find packages
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        limit: Maximum number of search results (default: 10)

    Returns:
        Dict with search results including package names and metadata.
    """
    # HYBRID APPROACH: Use unified search architecture but scope to specified registry
    # This prevents inappropriate searches across buckets not in user's stack
    effective_limit = limit if limit >= 0 else 10

    # Extract bucket name from registry for targeted search
    normalized_registry = _normalize_registry(registry)
    bucket_name = normalized_registry.replace("s3://", "")

    # Suppress stdout during search to avoid JSON-RPC interference
    from ..utils import suppress_stdout

    try:
        with suppress_stdout():
            # UNIFIED SEARCH: Try advanced search API first, but scoped to specific registry
            try:
                quilt_service = QuiltService()
                search_api = quilt_service.get_search_api()

                # For count queries (limit=0), use a simple DSL query with size=0
                if effective_limit == 0:
                    dsl_query = {
                        "size": 0,  # This is the key for fast counts!
                        "query": {"query_string": {"query": query}},
                    }
                else:
                    # Regular query with pagination
                    if isinstance(query, str) and not query.strip().startswith("{"):
                        # Convert string query to DSL with pagination
                        dsl_query = {
                            "from": from_,
                            "size": effective_limit,
                            "query": {"query_string": {"query": query}},
                        }
                    else:
                        # Already a DSL query
                        import json

                        if isinstance(query, str):
                            dsl_query = json.loads(query)
                        else:
                            dsl_query = query

                        # Add pagination
                        dsl_query["from"] = from_
                        dsl_query["size"] = effective_limit

                # STACK SCOPING: Use all buckets in the stack, not just the registry bucket
                # This enables proper cross-bucket search across the entire stack
                from .stack_buckets import build_stack_search_indices

                index_name = build_stack_search_indices()

                # Fallback to single bucket if stack discovery fails
                if not index_name:
                    index_name = f"{bucket_name},{bucket_name}_packages"

                # Use registry-specific index instead of '_all'
                full_result = search_api(query=dsl_query, index=index_name, limit=effective_limit)

                # Return unified search format with bucket context
                hits = full_result.get("hits", {}).get("hits", [])
                total_count = full_result.get("hits", {}).get("total", {})
                if isinstance(total_count, dict):
                    count = total_count.get("value", 0)
                else:
                    count = total_count

                return {
                    "results": hits,
                    "total_count": count,
                    "query": query,
                    "limit": effective_limit,
                    "from": from_,
                    "registry": normalized_registry,
                    "bucket": bucket_name,
                    "took": full_result.get("took", 0),
                    "timed_out": full_result.get("timed_out", False),
                }

            except Exception as search_api_error:
                # FALLBACK: Use bucket-specific search if advanced API fails
                bucket_obj = quilt_service.create_bucket(normalized_registry)
                results = bucket_obj.search(query, limit=effective_limit)

                return {
                    "results": results,
                    "total_count": len(results) if results else 0,
                    "query": query,
                    "limit": effective_limit,
                    "from": from_,
                    "registry": normalized_registry,
                    "bucket": bucket_name,
                    "fallback_used": "bucket_search",
                    "search_api_error": str(search_api_error),
                }

    except Exception as e:
        # Final fallback with error context
        return {
            "results": [],
            "total_count": 0,
            "query": query,
            "limit": effective_limit,
            "from": from_,
            "registry": normalized_registry,
            "bucket": bucket_name,
            "error": f"All search methods failed: {e}",
        }


def package_browse(
    package_name: str,
    registry: str = DEFAULT_REGISTRY,
    recursive: bool = True,
    include_file_info: bool = True,
    max_depth: int = 0,
    top: int = 0,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
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

    # Use the provided registry
    normalized_registry = _normalize_registry(registry)
    try:
        # Suppress stdout during browse to avoid JSON-RPC interference
        from ..utils import suppress_stdout

        quilt_service = QuiltService()
        with suppress_stdout():
            pkg = quilt_service.browse_package(package_name, registry=normalized_registry)

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to browse package '{package_name}'",
            "cause": str(e),
            "possible_fixes": [
                "Verify the package name is correct",
                "Check if you have access to the registry",
                "Ensure the package exists in the specified registry",
            ],
            "suggested_actions": [
                f"Try: packages_list(registry='{registry}') to see available packages",
                f"Try: packages_search('{package_name.split('/')[-1]}') to find similar packages",
            ],
        }

    # Get detailed information about each entry
    entries = []
    file_tree = {} if recursive else None
    keys = list(pkg.keys())
    total_size = 0
    file_types = set()

    # Apply top limit if specified
    if top > 0:
        keys = keys[:top]

    for logical_key in keys:
        try:
            entry = pkg[logical_key]

            # Get file information
            file_size = getattr(entry, "size", None)
            file_hash = str(getattr(entry, "hash", ""))
            physical_key = str(entry.physical_key) if hasattr(entry, "physical_key") else None

            # Determine file type and properties
            file_ext = logical_key.split(".")[-1].lower() if "." in logical_key else "unknown"
            file_types.add(file_ext)
            is_directory = logical_key.endswith("/") or file_size is None

            # Track total size
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

            # Add enhanced file info if requested
            if include_file_info and physical_key and physical_key.startswith("s3://"):
                try:
                    # Try to get additional S3 metadata
                    import boto3

                    from ..utils import get_s3_client

                    s3_client = get_s3_client()
                    bucket_name = physical_key.split("/")[2]
                    object_key = "/".join(physical_key.split("/")[3:])

                    obj_info = s3_client.head_object(Bucket=bucket_name, Key=object_key)
                    entry_data.update(
                        {
                            "last_modified": str(obj_info.get("LastModified")),
                            "content_type": obj_info.get("ContentType"),
                            "storage_class": obj_info.get("StorageClass", "STANDARD"),
                        }
                    )
                except Exception:
                    # Don't fail if we can't get additional info
                    pass

            # Add S3 URI and signed URL if this is an S3 object
            if physical_key and physical_key.startswith("s3://"):
                entry_data["s3_uri"] = physical_key

                if include_signed_urls:
                    signed_url = generate_signed_url(physical_key)
                    if signed_url:
                        entry_data["download_url"] = signed_url

            entries.append(entry_data)

            # Build file tree structure for recursive view
            if recursive and file_tree is not None:
                _add_to_file_tree(file_tree, logical_key, entry_data, max_depth)

        except Exception as e:
            # Include entry with error info
            entries.append(
                {
                    "logical_key": logical_key,
                    "physical_key": None,
                    "size": None,
                    "hash": "",
                    "error": str(e),
                    "file_type": "error",
                }
            )

    # Prepare comprehensive response
    response = {
        "success": True,
        "package_name": package_name,
        "registry": registry,
        "total_entries": len(entries),
        "summary": {
            "total_size": total_size,
            "total_size_human": _format_file_size(total_size),
            "file_types": sorted(list(file_types)),
            "total_files": len([e for e in entries if not e.get("is_directory", False)]),
            "total_directories": len([e for e in entries if e.get("is_directory", False)]),
        },
        "view_type": "recursive" if recursive else "flat",
    }

    # Get package metadata if available
    try:
        pkg_metadata = dict(pkg.meta) if hasattr(pkg, "meta") else {}
        if pkg_metadata:
            response["metadata"] = pkg_metadata
    except Exception:
        # Don't fail if we can't get metadata
        pass

    if recursive and file_tree:
        response["file_tree"] = file_tree

    response["entries"] = entries

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
    # Use the provided registry
    normalized_registry = _normalize_registry(registry)

    # Suppress stdout during browse to avoid JSON-RPC interference
    from ..utils import suppress_stdout

    quilt_service = QuiltService()
    with suppress_stdout():
        try:
            pkg = quilt_service.browse_package(package_name, registry=normalized_registry)
        except Exception as e:
            # Return empty result for nonexistent or inaccessible packages
            return {
                "package_name": package_name,
                "query": query,
                "matches": [],
                "count": 0,
                "success": False,
                "error": f"Failed to browse package: {e}",
            }

    # Find matching keys
    matching_keys = [k for k in pkg.keys() if query.lower() in k.lower()]

    # Get detailed information for each match
    matches = []
    for logical_key in matching_keys:
        try:
            entry = pkg[logical_key]
            match_data = {
                "logical_key": logical_key,
                "physical_key": (str(entry.physical_key) if hasattr(entry, "physical_key") else None),
                "size": getattr(entry, "size", None),
                "hash": str(getattr(entry, "hash", "")),
            }

            # Add S3 URI and signed URL if this is an S3 object
            if hasattr(entry, "physical_key") and str(entry.physical_key).startswith("s3://"):
                s3_uri = str(entry.physical_key)
                match_data["s3_uri"] = s3_uri

                if include_signed_urls:
                    signed_url = generate_signed_url(s3_uri)
                    if signed_url:
                        match_data["download_url"] = signed_url

            matches.append(match_data)
        except Exception:
            # Fallback to just the logical key if detailed info fails
            matches.append({"logical_key": logical_key})

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

    try:
        # Browse packages with optional hash specification
        # Suppress stdout during browse operations to avoid JSON-RPC interference
        from ..utils import suppress_stdout

        quilt_service = QuiltService()
        with suppress_stdout():
            if package1_hash:
                pkg1 = quilt_service.browse_package(
                    package1_name, registry=normalized_registry, top_hash=package1_hash
                )
            else:
                pkg1 = quilt_service.browse_package(package1_name, registry=normalized_registry)

            if package2_hash:
                pkg2 = quilt_service.browse_package(
                    package2_name, registry=normalized_registry, top_hash=package2_hash
                )
            else:
                pkg2 = quilt_service.browse_package(package2_name, registry=normalized_registry)

    except Exception as e:
        return {"error": f"Failed to browse packages: {e}"}

    try:
        # Use quilt3's built-in diff functionality
        diff_result = pkg1.diff(pkg2)

        # Convert the diff result to a more readable format
        return {
            "package1": package1_name,
            "package2": package2_name,
            "package1_hash": package1_hash if package1_hash else "latest",
            "package2_hash": package2_hash if package2_hash else "latest",
            "registry": registry,
            "diff": diff_result,
        }

    except Exception as e:
        return {"error": f"Failed to diff packages: {e}"}
