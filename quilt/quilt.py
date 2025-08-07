from typing import Any, Optional, Dict, List
import quilt3
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("quilt")


@mcp.tool()
def search_packages(
    query: str, 
    registry: str = "s3://quilt-example",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search for packages in a Quilt registry using text search.
    
    Args:
        query: Search terms to find packages
        registry: S3 bucket URL for the Quilt registry
        limit: Maximum number of results to return
    
    Returns:
        List of package metadata dictionaries
    """
    try:
        results = quilt3.search(query, registry=registry, limit=limit)
        return results
    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]


@mcp.tool()
def list_packages(
    registry: str = "s3://quilt-example",
    prefix: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all packages in a Quilt registry.
    
    Args:
        registry: S3 bucket URL for the Quilt registry
        prefix: Optional prefix to filter package names
    
    Returns:
        List of package metadata dictionaries
    """
    try:
        bucket = quilt3.Bucket(registry)
        packages = []
        
        for pkg_name in bucket.list_packages(prefix=prefix):
            try:
                pkg = quilt3.Package.browse(pkg_name, registry=registry)
                packages.append({
                    "name": pkg_name,
                    "registry": registry,
                    "metadata": pkg.meta
                })
            except Exception as e:
                packages.append({
                    "name": pkg_name,
                    "registry": registry,
                    "error": f"Failed to get metadata: {str(e)}"
                })
        
        return packages
    except Exception as e:
        return [{"error": f"Failed to list packages: {str(e)}"}]


@mcp.tool()
def browse_package(
    package_name: str,
    registry: str = "s3://quilt-example",
    hash_or_tag: Optional[str] = None
) -> Dict[str, Any]:
    """
    Browse a specific package in a Quilt registry.
    
    Args:
        package_name: Name of the package to browse
        registry: S3 bucket URL for the Quilt registry
        hash_or_tag: Specific version hash or tag (optional, defaults to latest)
    
    Returns:
        Package metadata and file listing
    """
    try:
        if hash_or_tag:
            pkg = quilt3.Package.browse(package_name, registry=registry, top_hash=hash_or_tag)
        else:
            pkg = quilt3.Package.browse(package_name, registry=registry)
        
        # Get package structure
        files = []
        for key in pkg:
            try:
                entry = pkg[key]
                files.append({
                    "path": key,
                    "size": getattr(entry, "size", None),
                    "hash": getattr(entry, "hash", None),
                    "meta": getattr(entry, "meta", {})
                })
            except Exception as e:
                files.append({
                    "path": key,
                    "error": f"Failed to read entry: {str(e)}"
                })
        
        return {
            "name": package_name,
            "registry": registry,
            "hash": pkg.top_hash if hasattr(pkg, 'top_hash') else None,
            "metadata": pkg.meta,
            "files": files
        }
    except Exception as e:
        return {"error": f"Failed to browse package '{package_name}': {str(e)}"}


@mcp.tool()
def search_package_contents(
    package_name: str,
    query: str,
    registry: str = "s3://quilt-example",
    hash_or_tag: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search within the contents of a specific package.
    
    Args:
        package_name: Name of the package to search within
        query: Search terms to find files/metadata
        registry: S3 bucket URL for the Quilt registry
        hash_or_tag: Specific version hash or tag (optional, defaults to latest)
    
    Returns:
        List of matching files and metadata
    """
    try:
        if hash_or_tag:
            pkg = quilt3.Package.browse(package_name, registry=registry, top_hash=hash_or_tag)
        else:
            pkg = quilt3.Package.browse(package_name, registry=registry)
        
        matches = []
        query_lower = query.lower()
        
        # Search in package metadata
        pkg_meta_str = str(pkg.meta).lower()
        if query_lower in pkg_meta_str:
            matches.append({
                "type": "package_metadata",
                "path": "",
                "match_type": "metadata",
                "metadata": pkg.meta
            })
        
        # Search in file paths and metadata
        for key in pkg:
            try:
                entry = pkg[key]
                
                # Search in file path
                if query_lower in key.lower():
                    matches.append({
                        "type": "file_path",
                        "path": key,
                        "match_type": "path",
                        "size": getattr(entry, "size", None),
                        "hash": getattr(entry, "hash", None),
                        "metadata": getattr(entry, "meta", {})
                    })
                
                # Search in file metadata
                file_meta = getattr(entry, "meta", {})
                if file_meta and query_lower in str(file_meta).lower():
                    matches.append({
                        "type": "file_metadata",
                        "path": key,
                        "match_type": "metadata",
                        "size": getattr(entry, "size", None),
                        "hash": getattr(entry, "hash", None),
                        "metadata": file_meta
                    })
                    
            except Exception as e:
                continue
        
        return matches
    except Exception as e:
        return [{"error": f"Failed to search package contents: {str(e)}"}]


@mcp.tool()
def get_package_versions(
    package_name: str,
    registry: str = "s3://quilt-example"
) -> List[Dict[str, Any]]:
    """
    Get all versions (hashes) of a package.
    
    Args:
        package_name: Name of the package
        registry: S3 bucket URL for the Quilt registry
    
    Returns:
        List of package versions with metadata
    """
    try:
        bucket = quilt3.Bucket(registry)
        versions = []
        
        # Get package versions
        for version_info in bucket.list_package_versions(package_name):
            versions.append({
                "hash": version_info.get("hash"),
                "modified": version_info.get("modified"),
                "size": version_info.get("size"),
                "metadata": version_info.get("metadata", {})
            })
        
        return versions
    except Exception as e:
        return [{"error": f"Failed to get package versions: {str(e)}"}]


if __name__ == "__main__":
    mcp.run()