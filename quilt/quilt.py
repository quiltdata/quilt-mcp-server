from typing import Any, Optional, Dict, List
import quilt3
import os
import tempfile
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations


# Initialize FastMCP server
mcp = FastMCP("quilt")

# Check if running in Lambda (read-only filesystem environment)
def is_lambda_environment() -> bool:
    """Check if we're running in AWS Lambda environment."""
    return bool(os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))

# Global override for testing - can be set directly in tests
_FORCE_LAMBDA_MODE = None

def set_lambda_mode(force_lambda: bool) -> None:
    """Override Lambda mode for testing purposes.
    
    Args:
        force_lambda: True to force Lambda mode, False to force local mode
    """
    global _FORCE_LAMBDA_MODE
    _FORCE_LAMBDA_MODE = force_lambda
    # Note: Tool registration happens at module import time, so this only affects
    # future imports or dynamic registration

def get_lambda_mode() -> bool:
    """Get current Lambda mode status, respecting test overrides."""
    if _FORCE_LAMBDA_MODE is not None:
        return _FORCE_LAMBDA_MODE
    return is_lambda_environment()

# Create ToolAnnotations for different environments
LAMBDA_COMPATIBLE = ToolAnnotations(
    environment_requirements="lambda_compatible"
)
LOCAL_ONLY = ToolAnnotations(
    environment_requirements="local_only"
)

# Decorator function to conditionally register tools
def conditional_tool(annotations=None, **kwargs):
    """Decorator that conditionally registers tools based on environment requirements."""
    def decorator(func):
        # Check if this tool should be registered in current environment
        if annotations and hasattr(annotations, 'environment_requirements'):
            env_req = annotations.environment_requirements
            if env_req == 'local_only' and get_lambda_mode():
                # Skip registration in Lambda environment
                return func
        
        # Register the tool with FastMCP's built-in decorator
        return mcp.tool(annotations=annotations, **kwargs)(func)
    
    return decorator


@conditional_tool(annotations=LAMBDA_COMPATIBLE)
def check_quilt_auth() -> Dict[str, Any]:
    """
    Check Quilt authentication status and provide setup guidance.
    
    Returns:
        Dictionary with authentication status and setup instructions
    """
    try:
        # Check if logged in
        logged_in_url = quilt3.logged_in()
        
        if logged_in_url:
            return {
                "status": "authenticated",
                "catalog_url": logged_in_url,
                "message": "Successfully authenticated to Quilt catalog",
                "search_available": True
            }
        else:
            return {
                "status": "not_authenticated", 
                "message": "Not logged in to Quilt catalog",
                "search_available": False,
                "setup_instructions": [
                    "1. Configure catalog: quilt3 config https://open.quiltdata.com",
                    "2. Login: quilt3 login", 
                    "3. Follow the browser authentication flow"
                ]
            }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to check authentication: {str(e)}",
            "setup_instructions": [
                "1. Configure catalog: quilt3 config https://open.quiltdata.com",
                "2. Login: quilt3 login"
            ]
        }


@conditional_tool(annotations=LAMBDA_COMPATIBLE)
def check_filesystem_access() -> Dict[str, Any]:
    """
    Check if the current environment has filesystem write access needed for Quilt operations.
    
    Returns:
        Dictionary with filesystem access status and environment information
    """
    result = {
        "is_lambda": is_lambda_environment(),
        "home_directory": os.path.expanduser("~"),
        "temp_directory": tempfile.gettempdir(),
        "current_directory": os.getcwd()
    }
    
    # Test write access to home directory
    home_dir = os.path.expanduser("~")
    try:
        test_file = os.path.join(home_dir, ".quilt_test_write")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        result["home_writable"] = True
        result["home_write_error"] = None
    except Exception as e:
        result["home_writable"] = False
        result["home_write_error"] = str(e)
    
    # Test write access to temp directory
    try:
        with tempfile.NamedTemporaryFile(delete=True) as f:
            f.write(b"test")
        result["temp_writable"] = True
        result["temp_write_error"] = None
    except Exception as e:
        result["temp_writable"] = False
        result["temp_write_error"] = str(e)
    
    # Overall assessment
    if result["home_writable"]:
        result["status"] = "full_access"
        result["message"] = "Full filesystem access available - all Quilt tools should work"
        result["tools_available"] = ["search_packages", "list_packages", "browse_package", "search_package_contents"]
    elif result["temp_writable"]:
        result["status"] = "limited_access"
        result["message"] = "Limited filesystem access - Quilt tools may work with proper configuration"
        result["tools_available"] = ["check_quilt_auth"]
        result["recommendation"] = "Try setting QUILT_CONFIG_DIR environment variable to /tmp"
    else:
        result["status"] = "read_only"
        result["message"] = "Read-only filesystem - most Quilt tools will not work"
        result["tools_available"] = ["check_quilt_auth"]
    
    return result


@conditional_tool(annotations=LAMBDA_COMPATIBLE)
def list_packages(
    registry: str = "s3://quilt-example",
    prefix: Optional[str] = None,
    limit: int = 12,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    List packages in a Quilt registry with pagination support.
    
    Args:
        registry: S3 bucket URL for the Quilt registry
        prefix: Optional prefix to filter package names
        limit: Maximum number of packages to return (default: 12)
        offset: Number of packages to skip for pagination (default: 0)
    
    Returns:
        List of package metadata dictionaries with pagination info
    """
    try:
        packages = []
        all_package_names = []
        
        # First, get all package names and apply prefix filter
        for pkg_name in quilt3.list_packages(registry=registry):
            if prefix and not pkg_name.startswith(prefix):
                continue
            all_package_names.append(pkg_name)
        
        # Calculate pagination bounds
        total_packages = len(all_package_names)
        start_idx = offset
        end_idx = min(offset + limit, total_packages)
        
        # Process only the requested slice of packages
        paginated_names = all_package_names[start_idx:end_idx]
        
        for pkg_name in paginated_names:
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
        
        # Add pagination metadata
        result = {
            "packages": packages,
            "pagination": {
                "total": total_packages,
                "offset": offset,
                "limit": limit,
                "returned": len(packages),
                "has_more": end_idx < total_packages
            }
        }
        
        return [result]
    except Exception as e:
        return [{"error": f"Failed to list packages: {str(e)}"}]


@conditional_tool(annotations=LOCAL_ONLY)
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
        # Configure the registry for this search
        quilt3.config(navigator_url=registry.replace('s3://', 'https://') + '/')
        results = quilt3.search(query, limit=limit)
        return results
    except Exception as e:
        error_msg = str(e)
        
        # Check for authentication-related errors and provide helpful guidance
        if "Invalid URL" in error_msg and "No scheme supplied" in error_msg:
            return [{
                "error": "Search failed: Quilt catalog not configured",
                "solution": "Please run these commands to enable search:\n1. quilt3 config https://open.quiltdata.com\n2. quilt3 login",
                "details": f"Original error: {error_msg}"
            }]
        elif "401" in error_msg or "403" in error_msg or "Unauthorized" in error_msg or "authentication" in error_msg.lower():
            return [{
                "error": "Search failed: Authentication required",
                "solution": "Please login to the Quilt catalog:\n1. quilt3 config https://open.quiltdata.com\n2. quilt3 login",
                "details": f"Original error: {error_msg}"
            }]
        elif "search" in error_msg.lower() and "endpoint" in error_msg.lower():
            return [{
                "error": "Search failed: Search endpoint not available", 
                "solution": "This registry may not support search, or you need to login:\n1. quilt3 config https://open.quiltdata.com\n2. quilt3 login",
                "details": f"Original error: {error_msg}"
            }]
        else:
            # Generic error with suggestion
            return [{
                "error": f"Search failed: {error_msg}",
                "suggestion": "If this is an authentication issue, try: quilt3 login"
            }]


@conditional_tool(annotations=LOCAL_ONLY)
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


@conditional_tool(annotations=LOCAL_ONLY)
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


# Tools are automatically registered when the module is imported
# due to the @conditional_tool decorators above
