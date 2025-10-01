"""Authentication and filesystem access tools."""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, Optional
from urllib.parse import quote, urlparse

from ..runtime import get_active_token
from ..utils import resolve_catalog_url


def _extract_catalog_name_from_url(url: str) -> str:
    """Extract a human-readable catalog name from a Quilt catalog URL.

    Args:
        url: The catalog URL (e.g., 'https://nightly.quilttest.com')

    Returns:
        A simplified catalog name (e.g., 'nightly.quilttest.com')
    """
    if not url:
        return "unknown"

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or parsed.netloc
        if hostname:
            # Remove common subdomain prefixes that don't add semantic value
            if hostname.startswith("www."):
                hostname = hostname[4:]
            return hostname
        return url
    except Exception:
        return url


def _extract_bucket_from_registry(registry: str) -> str:
    """Extract bucket name from registry URL.

    Args:
        registry: Registry URL (e.g., 's3://bucket-name')

    Returns:
        Bucket name without s3:// prefix
    """
    if registry.startswith("s3://"):
        return registry[5:]
    return registry


def _resolved_catalog_base(explicit: str | None = None) -> str:
    base = resolve_catalog_url(explicit)
    if base:
        return base.rstrip("/")
    return "https://demo.quiltdata.com"


def _resolved_catalog_host(explicit: str | None = None) -> str:
    base = _resolved_catalog_base(explicit)
    parsed = urlparse(base)
    if parsed.hostname:
        return parsed.hostname
    return base.replace("https://", "").replace("http://", "")


def catalog_url(
    registry: str,
    package_name: str | None = None,
    path: str | None = None,
    catalog_host: str | None = None,
) -> dict[str, Any]:
    """Generate a catalog URL for viewing packages or bucket objects.

    Args:
        registry: Registry URL (e.g., 's3://bucket-name')
        package_name: Package name (e.g., 'user/package') for package view, None for bucket view
        path: Path within package or bucket (default: None)
        catalog_host: Catalog hostname, will auto-detect if not provided

    Returns:
        Dict with generated catalog URL and metadata
    """
    try:
        bucket = _extract_bucket_from_registry(registry)

        base_url = _resolved_catalog_base(catalog_host)
        catalog_host = _resolved_catalog_host(catalog_host)

        # Build URL based on whether it's a package or bucket view
        if package_name:
            # Package view: https://{catalog_host}/b/{bucket}/packages/{package_name}/tree/latest/{path}
            url_parts = [
                base_url,
                "b",
                bucket,
                "packages",
                package_name,
                "tree",
                "latest",
            ]
            if path:
                # URL encode the path components
                path_parts = [quote(part, safe="") for part in path.strip("/").split("/") if part]
                url_parts.extend(path_parts)
            url = "/".join(url_parts)
            view_type = "package"
        else:
            # Bucket view: https://{catalog_host}/b/{bucket}/tree/{path}
            url_parts = [base_url, "b", bucket, "tree"]
            if path:
                # URL encode the path components
                path_parts = [quote(part, safe="") for part in path.strip("/").split("/") if part]
                url_parts.extend(path_parts)
            url = "/".join(url_parts)
            view_type = "bucket"

        return {
            "status": "success",
            "catalog_url": url,
            "view_type": view_type,
            "bucket": bucket,
            "package_name": package_name,
            "path": path,
            "catalog_host": catalog_host,
        }

    except Exception as e:
        return {"status": "error", "error": f"Failed to generate catalog URL: {e}"}


def catalog_uri(
    registry: str,
    package_name: str | None = None,
    path: str | None = None,
    top_hash: str | None = None,
    tag: str | None = None,
    catalog_host: str | None = None,
) -> dict[str, Any]:
    """Generate a Quilt+ URI for referencing packages or objects.

    Args:
        registry: Registry URL (e.g., 's3://bucket-name')
        package_name: Package name (e.g., 'user/package'), None for bucket-only URI
        path: Path within package or bucket (default: None)
        top_hash: Specific package version hash (default: None)
        tag: Package version tag (default: None)
        catalog_host: Catalog hostname, will auto-detect if not provided

    Returns:
        Dict with generated Quilt+ URI and metadata
    """
    try:
        bucket = _extract_bucket_from_registry(registry)

        # Start building URI: quilt+s3://bucket
        uri_parts = [f"quilt+s3://{bucket}"]

        # Build fragment parameters
        fragment_params = []

        if package_name:
            # Add version specifier to package name if provided
            package_spec = package_name
            if top_hash:
                package_spec += f"@{top_hash}"
            elif tag:
                package_spec += f":{tag}"
            fragment_params.append(f"package={package_spec}")

        if path:
            fragment_params.append(f"path={path}")

        # Auto-detect catalog host if not provided
        if not catalog_host:
            catalog_host = _resolved_catalog_host()

        if catalog_host:
            # Remove protocol if present
            clean_host = catalog_host.replace("https://", "").replace("http://", "")
            fragment_params.append(f"catalog={clean_host}")

        # Add fragment if we have any parameters
        if fragment_params:
            uri_parts.append("#" + "&".join(fragment_params))

        quilt_plus_uri = "".join(uri_parts)

        return {
            "status": "success",
            "quilt_plus_uri": quilt_plus_uri,
            "bucket": bucket,
            "package_name": package_name,
            "path": path,
            "top_hash": top_hash,
            "tag": tag,
            "catalog_host": catalog_host,
        }

    except Exception as e:
        return {"status": "error", "error": f"Failed to generate Quilt+ URI: {e}"}


def catalog_info() -> dict[str, Any]:
    """Get information about the current Quilt catalog configuration.

    Returns:
        Dict with catalog name, URLs, authentication status, and configuration details.
    """
    try:
        base_url = resolve_catalog_url()
        catalog_name = _resolved_catalog_host()

        result = {
            "catalog_name": catalog_name,
            "catalog_url": base_url or "https://demo.quiltdata.com",
            "is_authenticated": bool(get_active_token()),
            "status": "success",
        }

        result["message"] = (
            f"Connected to catalog: {catalog_name}"
            if result["is_authenticated"]
            else f"Configured for catalog: {catalog_name} (not authenticated)"
        )

        return result

    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to get catalog info: {e}",
            "catalog_name": "unknown",
        }


def catalog_name() -> dict[str, Any]:
    """Get the name of the current Quilt catalog.

    Returns:
        Dict with the catalog name and detection method.
    """
    try:
        catalog_name = _resolved_catalog_host()
        return {
            "catalog_name": catalog_name,
            "detection_method": "environment",
            "is_authenticated": bool(get_active_token()),
            "status": "success",
        }

    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to detect catalog name: {e}",
            "catalog_name": "unknown",
            "detection_method": "error",
        }


def auth_status() -> dict[str, Any]:
    """Check Quilt authentication status with rich information and actionable suggestions.

    Returns:
        Dict with comprehensive authentication status, catalog info, permissions, and next steps.
    """
    try:
        token = get_active_token()
        catalog_url = resolve_catalog_url() or "https://demo.quiltdata.com"
        catalog_name = _resolved_catalog_host()

        if token:
            return {
                "status": "authenticated",
                "catalog_url": catalog_url,
                "catalog_name": catalog_name,
                "message": f"Successfully authenticated to {catalog_name}",
                "search_available": True,
                "suggested_actions": [
                    "Try listing packages with: packages_list()",
                    "Test bucket permissions with: permissions_tool(action='discover')",
                ],
            }

        setup_instructions = [
            "Ensure your frontend sends an Authorization bearer token with each request.",
            "If running locally, export QUILT_CATALOG_URL before launching the MCP server.",
        ]

        return {
            "status": "not_authenticated",
            "catalog_name": catalog_name,
            "message": "Authorization token not present",
            "search_available": False,
            "setup_instructions": setup_instructions,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to check authentication: {e}",
            "catalog_name": "unknown",
            "troubleshooting": {
                "common_issues": [
                    "AWS credentials not configured",
                    "Quilt not installed properly",
                    "Network connectivity issues",
                ],
                "suggested_fixes": [
                    "Check AWS credentials with: aws sts get-caller-identity",
                    "Reinstall quilt3: pip install --upgrade quilt3",
                    "Check network connectivity",
                ],
            },
            "setup_instructions": [
                "1. Configure catalog: quilt3 config https://open.quiltdata.com",
                "2. Login: quilt3 login",
            ],
        }


def filesystem_status() -> dict[str, Any]:
    """Check filesystem permissions and environment capabilities.

    Returns:
        Dict with filesystem access status and available tools.
    """
    result: dict[str, Any] = {
        "home_directory": os.path.expanduser("~"),
        "temp_directory": tempfile.gettempdir(),
        "current_directory": os.getcwd(),
    }

    # Test home directory write access
    try:
        test_file = os.path.join(result["home_directory"], ".quilt_test_write")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        result["home_writable"] = True
    except Exception as e:
        result["home_writable"] = False
        result["home_write_error"] = str(e)

    # Test temp directory write access
    try:
        import tempfile as _tf

        with _tf.NamedTemporaryFile(delete=True) as f:
            f.write(b"test")
        result["temp_writable"] = True
    except Exception as e:
        result["temp_writable"] = False
        result["temp_write_error"] = str(e)

    # Determine access level and available tools
    if result.get("home_writable"):
        result.update(
            status="full_access",
            message="Full filesystem access available - all Quilt tools should work",
            tools_available=[
                "auth_status",
                "catalog_info",
                "catalog_name",
                "catalog_url",
                "catalog_uri",
                "filesystem_status",
                "packages_list",
                "packages_search",
                "package_browse",
                "package_contents_search",
                "package_create",
                "package_update",
                "bucket_objects_list",
                "bucket_object_info",
                "bucket_object_text",
                "bucket_objects_put",
                "bucket_object_fetch",
            ],
        )
    elif result.get("temp_writable"):
        result.update(
            status="limited_access",
            message="Limited filesystem access - Quilt tools may work with proper configuration",
            tools_available=[
                "auth_status",
                "catalog_info",
                "catalog_name",
                "catalog_url",
                "catalog_uri",
                "filesystem_status",
                "packages_list",
                "package_browse",
                "package_contents_search",
            ],
            recommendation="Try setting QUILT_CONFIG_DIR environment variable to /tmp",
        )
    else:
        result.update(
            status="read_only",
            message="Read-only filesystem - most Quilt tools will not work",
            tools_available=[
                "auth_status",
                "catalog_info",
                "catalog_name",
                "catalog_url",
                "catalog_uri",
                "filesystem_status",
            ],
        )

    return result


def configure_catalog(catalog_url: str) -> dict[str, Any]:
    """Configure Quilt catalog URL.

    Args:
        catalog_url: Quilt catalog URL (e.g., 'https://demo.quiltdata.com')

    Returns:
        Dict with configuration result and next steps.
    """
    try:
        # Validate URL format
        if not catalog_url.startswith(("http://", "https://")):
            return {
                "status": "error",
                "error": "Invalid catalog URL format",
                "provided": catalog_url,
                "expected": "URL starting with http:// or https://",
                "example": "https://demo.quiltdata.com",
            }

        # Configure the catalog
        os.environ["QUILT_CATALOG_URL"] = catalog_url
        configured_url = catalog_url

        return {
            "status": "success",
            "catalog_url": catalog_url,
            "configured_url": configured_url,
            "message": f"Successfully configured catalog: {_extract_catalog_name_from_url(catalog_url)}",
            "next_steps": [
                "Login with: quilt3 login",
                "Verify with: auth_status()",
                "Start exploring with: packages_list()",
            ],
            "help": {
                "login_command": "quilt3 login",
                "verify_command": "auth_status()",
                "documentation": "https://docs.quiltdata.com/",
            },
        }

    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to configure catalog: {e}",
            "catalog_url": catalog_url,
            "troubleshooting": {
                "common_issues": [
                    "Invalid catalog URL",
                    "Network connectivity problems",
                    "Quilt configuration file permissions",
                ],
                "suggested_fixes": [
                    "Verify the catalog URL is correct and accessible",
                    "Check network connectivity",
                    "Ensure write permissions to Quilt config directory",
                ],
            },
        }


def switch_catalog(catalog_name: str) -> dict[str, Any]:
    """Switch to a different Quilt catalog by name.

    Args:
        catalog_name: Catalog name or URL to switch to

    Returns:
        Dict with switch result and status.
    """
    try:
        # Common catalog mappings
        catalog_mappings = {
            "demo": "https://demo.quiltdata.com",
            "sandbox": "https://sandbox.quiltdata.com",
            "open": "https://open.quiltdata.com",
            "example": "https://open.quiltdata.com",
        }

        # Determine target URL
        if catalog_name.lower() in catalog_mappings:
            target_url = catalog_mappings[catalog_name.lower()]
            friendly_name = catalog_name.lower()
        elif catalog_name.startswith(("http://", "https://")):
            target_url = catalog_name
            friendly_name = _extract_catalog_name_from_url(catalog_name)
        else:
            # Try to construct URL
            target_url = f"https://{catalog_name}"
            friendly_name = catalog_name

        # Configure the new catalog
        result = configure_catalog(target_url)

        if result.get("status") == "success":
            result.update(
                {
                    "action": "switched",
                    "from_catalog": "previous",  # Could track previous if needed
                    "to_catalog": friendly_name,
                    "message": f"Successfully switched to catalog: {friendly_name}",
                    "warning": "You may need to login again with: quilt3 login",
                }
            )

        return result

    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to switch catalog: {e}",
            "catalog_name": catalog_name,
            "available_catalogs": list(catalog_mappings.keys()),
            "help": "Use one of the available catalog names or provide a full URL",
        }


def auth(action: str | None = None, params: Optional[Dict[str, Any]] = None) -> dict[str, Any]:
    """
    Authentication and catalog configuration operations.

    Available actions:
    - status: Check Quilt authentication status with rich information
    - catalog_info: Get information about current catalog configuration
    - catalog_name: Get the name of the current catalog
    - catalog_uri: Generate a Quilt+ URI for referencing packages/objects
    - catalog_url: Generate a catalog URL for viewing packages/objects
    - configure_catalog: Configure Quilt catalog URL
    - filesystem_status: Check filesystem permissions and capabilities
    - switch_catalog: Switch to a different Quilt catalog

    Args:
        action: The operation to perform. If None, returns available actions.
        **kwargs: Action-specific parameters

    Returns:
        Action-specific response dictionary

    Examples:
        # Discovery mode
        result = auth()

        # Check status
        result = auth(action="status")

        # Configure catalog
        result = auth(action="configure_catalog", catalog_url="https://example.com")

    For detailed parameter documentation, see individual action functions.
    """
    actions = {
        "status": auth_status,
        "catalog_info": catalog_info,
        "catalog_name": catalog_name,
        "catalog_uri": catalog_uri,
        "catalog_url": catalog_url,
        "configure_catalog": configure_catalog,
        "filesystem_status": filesystem_status,
        "switch_catalog": switch_catalog,
    }

    # Discovery mode
    if action is None:
        return {
            "success": True,
            "module": "auth",
            "actions": list(actions.keys()),
            "usage": "Call with action='<action_name>' to execute",
        }

    # Validate action
    if action not in actions:
        available = ", ".join(sorted(actions.keys()))
        return {
            "status": "error",
            "error": f"Unknown action '{action}' for module 'auth'. Available actions: {available}",
        }

    # Dispatch
    try:
        func = actions[action]
        kwargs = params or {}
        result = func(**kwargs)
        # Normalize status/success fields for consistency
        if "status" in result and "success" not in result:
            result["success"] = result["status"] == "success"
        return result
    except TypeError as e:
        import inspect

        sig = inspect.signature(func)
        expected_params = list(sig.parameters.keys())
        return {
            "status": "error",
            "error": f"Invalid parameters for action '{action}'. Expected: {expected_params}. Error: {str(e)}",
        }
    except Exception as e:
        if isinstance(e, dict):
            return e
        return {
            "status": "error",
            "error": f"Error executing action '{action}': {str(e)}",
        }
