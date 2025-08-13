from __future__ import annotations

from typing import Any

import quilt3

from ..constants import DEFAULT_REGISTRY
from ..server import mcp

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

def _generate_signed_url(s3_uri: str, expiration: int = 3600) -> str | None:
    """Generate a presigned URL for an S3 URI.
    
    Args:
        s3_uri: S3 URI (e.g., "s3://bucket/key")
        expiration: URL expiration in seconds (default: 3600)
    
    Returns:
        Presigned URL string or None if generation fails
    """
    import boto3
    if not s3_uri.startswith("s3://"):
        return None
    
    without_scheme = s3_uri[5:]
    if '/' not in without_scheme:
        return None
    
    bucket, key = without_scheme.split('/', 1)
    expiration = max(1, min(expiration, 604800))  # 1 sec to 7 days
    
    try:
        client = boto3.client("s3")
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration
        )
        return url
    except Exception:
        return None


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
    # Normalize registry and pass to quilt3.list_packages(), then apply filtering
    normalized_registry = _normalize_registry(registry)
    pkgs = list(quilt3.list_packages(registry=normalized_registry))  # Convert generator to list

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
def package_browse(package_name: str, registry: str = DEFAULT_REGISTRY, top: int = 0, include: list[str] = [], exclude: list[str] = [], include_signed_urls: bool = True) -> dict[str, Any]:
    """Browse the contents of a Quilt package.
    
    Args:
        package_name: Name of the package to browse (e.g., "username/package-name")
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        top: Limit number of entries returned, 0 for unlimited (default: 0)
        include: Include patterns (currently unused, reserved for future)
        exclude: Exclude patterns (currently unused, reserved for future)
        include_signed_urls: Include presigned download URLs for S3 objects (default: True)
    
    Returns:
        Dict with list of package contents including logical keys, S3 URIs, and optional download URLs.
    """
    # Use the provided registry
    normalized_registry = _normalize_registry(registry)
    pkg = quilt3.Package.browse(package_name, registry=normalized_registry)
    
    # Get detailed information about each entry
    entries = []
    keys = list(pkg.keys())
    
    # Apply top limit if specified
    if top > 0:
        keys = keys[:top]
    
    for logical_key in keys:
        try:
            entry = pkg[logical_key]
            entry_data = {
                "logical_key": logical_key,
                "physical_key": str(entry.physical_key) if hasattr(entry, 'physical_key') else None,
                "size": getattr(entry, 'size', None),
                "hash": str(getattr(entry, 'hash', ''))
            }
            
            # Add S3 URI and signed URL if this is an S3 object
            if hasattr(entry, 'physical_key') and str(entry.physical_key).startswith('s3://'):
                s3_uri = str(entry.physical_key)
                entry_data["s3_uri"] = s3_uri
                
                if include_signed_urls:
                    signed_url = _generate_signed_url(s3_uri)
                    if signed_url:
                        entry_data["download_url"] = signed_url
            
            entries.append(entry_data)
        except Exception:
            # Fallback to just the logical key if detailed info fails
            entries.append({"logical_key": logical_key})

    return {
        "package_name": package_name,
        "registry": registry,
        "total_entries": len(entries),
        "entries": entries
    }

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
    normalized_registry = _normalize_registry(registry)
    pkg = quilt3.Package.browse(package_name, registry=normalized_registry)
    matches = [k for k in pkg.keys() if query.lower() in k.lower()]
    return {"matches": matches, "count": len(matches)}

@mcp.tool()
def package_diff(package1_name: str, package2_name: str, registry: str = DEFAULT_REGISTRY, package1_hash: str = "", package2_hash: str = "") -> dict[str, Any]:
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
        if package1_hash:
            pkg1 = quilt3.Package.browse(package1_name, registry=normalized_registry, top_hash=package1_hash)
        else:
            pkg1 = quilt3.Package.browse(package1_name, registry=normalized_registry)
            
        if package2_hash:
            pkg2 = quilt3.Package.browse(package2_name, registry=normalized_registry, top_hash=package2_hash)
        else:
            pkg2 = quilt3.Package.browse(package2_name, registry=normalized_registry)
            
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
            "diff": diff_result
        }
        
    except Exception as e:
        return {"error": f"Failed to diff packages: {e}"}
