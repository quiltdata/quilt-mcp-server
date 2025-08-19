"""Authentication and filesystem access tools."""

from __future__ import annotations

import os
import tempfile
from typing import Any
from urllib.parse import quote, urlparse

import quilt3


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


def _get_catalog_info() -> dict[str, Any]:
    """Get comprehensive catalog information from Quilt configuration.

    Returns:
        Dict with catalog name, URLs, and configuration details.
    """
    catalog_info: dict[str, Any] = {
        "catalog_name": None,
        "navigator_url": None,
        "registry_url": None,
        "logged_in_url": None,
        "is_authenticated": False,
    }

    try:
        # Get current authentication status
        logged_in_url = quilt3.logged_in()
        if logged_in_url:
            catalog_info["logged_in_url"] = logged_in_url
            catalog_info["is_authenticated"] = True
            catalog_info["catalog_name"] = _extract_catalog_name_from_url(logged_in_url)
    except Exception:
        pass

    try:
        # Get configuration details
        config = quilt3.config()
        if config:
            navigator_url = config.get("navigator_url")
            registry_url = config.get("registryUrl")

            catalog_info["navigator_url"] = navigator_url
            catalog_info["registry_url"] = registry_url

            # If we don't have a catalog name from authentication, try config
            if not catalog_info["catalog_name"] and navigator_url:
                catalog_info["catalog_name"] = _extract_catalog_name_from_url(navigator_url)
            elif not catalog_info["catalog_name"] and registry_url:
                catalog_info["catalog_name"] = _extract_catalog_name_from_url(registry_url)
    except Exception:
        pass

    # Fallback catalog name if nothing found
    if not catalog_info["catalog_name"]:
        catalog_info["catalog_name"] = "unknown"

    return catalog_info


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


def _get_catalog_host_from_config() -> str | None:
    """Get catalog host from Quilt configuration.

    Returns:
        Catalog hostname or None if not found
    """
    try:
        # Try authenticated URL first
        logged_in_url = quilt3.logged_in()
        if logged_in_url:
            parsed = urlparse(logged_in_url)
            hostname = parsed.hostname
            return hostname if hostname else None

        # Fall back to navigator_url from config
        config = quilt3.config()
        if config and config.get("navigator_url"):
            nav_url = config.get("navigator_url")
            if nav_url:
                parsed = urlparse(nav_url)
                hostname = parsed.hostname
                return hostname if hostname else None
    except Exception:
        pass
    return None


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

        # Auto-detect catalog host if not provided
        if not catalog_host:
            catalog_host = _get_catalog_host_from_config()
            if not catalog_host:
                return {
                    "status": "error",
                    "error": "Could not determine catalog host. Please provide catalog_host parameter or ensure Quilt is configured.",
                }

        # Ensure catalog_host has https protocol
        if not catalog_host.startswith("http"):
            catalog_host = f"https://{catalog_host}"

        # Build URL based on whether it's a package or bucket view
        if package_name:
            # Package view: https://{catalog_host}/b/{bucket}/packages/{package_name}/tree/latest/{path}
            url_parts = [
                catalog_host.rstrip("/"),
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
            url_parts = [catalog_host.rstrip("/"), "b", bucket, "tree"]
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
            "catalog_host": (
                catalog_host.replace("https://", "").replace("http://", "")
                if catalog_host
                else None
            ),
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
            catalog_host = _get_catalog_host_from_config()

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
            "catalog_host": (
                catalog_host.replace("https://", "").replace("http://", "")
                if catalog_host
                else None
            ),
        }

    except Exception as e:
        return {"status": "error", "error": f"Failed to generate Quilt+ URI: {e}"}


def catalog_info() -> dict[str, Any]:
    """Get information about the current Quilt catalog configuration.

    Returns:
        Dict with catalog name, URLs, authentication status, and configuration details.
    """
    try:
        info = _get_catalog_info()

        result = {
            "catalog_name": info["catalog_name"],
            "is_authenticated": info["is_authenticated"],
            "status": "success",
        }

        # Add URLs if available
        if info["navigator_url"]:
            result["navigator_url"] = info["navigator_url"]
        if info["registry_url"]:
            result["registry_url"] = info["registry_url"]
        if info["logged_in_url"]:
            result["logged_in_url"] = info["logged_in_url"]

        # Add helpful context
        if info["is_authenticated"]:
            result["message"] = f"Connected to catalog: {info['catalog_name']}"
        else:
            result["message"] = (
                f"Configured for catalog: {info['catalog_name']} (not authenticated)"
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
        info = _get_catalog_info()

        # Determine how the catalog name was detected
        detection_method = "unknown"
        if info["logged_in_url"]:
            detection_method = "authentication"
        elif info["navigator_url"]:
            detection_method = "navigator_config"
        elif info["registry_url"]:
            detection_method = "registry_config"

        return {
            "catalog_name": info["catalog_name"],
            "detection_method": detection_method,
            "is_authenticated": info["is_authenticated"],
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
    """Check Quilt authentication status and provide setup instructions.

    Returns:
        Dict with authentication status, catalog URL, and setup instructions if needed.
    """
    try:
        logged_in_url = quilt3.logged_in()
        if logged_in_url:
            return {
                "status": "authenticated",
                "catalog_url": logged_in_url,
                "message": "Successfully authenticated to Quilt catalog",
                "search_available": True,
            }
        return {
            "status": "not_authenticated",
            "message": "Not logged in to Quilt catalog",
            "search_available": False,
            "setup_instructions": [
                "1. Configure catalog: quilt3 config https://open.quiltdata.com",
                "2. Login: quilt3 login",
                "3. Follow the browser authentication flow",
            ],
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to check authentication: {e}",
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
