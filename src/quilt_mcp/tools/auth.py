"""Authentication and filesystem access tools."""

from __future__ import annotations

import os
import tempfile
from typing import Any
from urllib.parse import quote, urlparse

from ..services.quilt_service import QuiltService


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
    service = QuiltService()
    return service.get_catalog_info()


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
        service = QuiltService()

        # Try authenticated URL first
        logged_in_url = service.get_logged_in_url()
        if logged_in_url:
            parsed = urlparse(logged_in_url)
            hostname = parsed.hostname
            return hostname if hostname else None

        # Fall back to navigator_url from config
        config = service.get_config()
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
    """Generate Quilt catalog URL - Quilt authentication and catalog navigation workflows

    WORKFLOW:
        1. Detect or accept the catalog host and assemble the fully qualified URL.
        2. Return structured metadata (bucket, view type, path) so follow-up tools can reason about the link.
        3. Pair with ``auth.catalog_uri`` when the user also needs the Quilt+ URI representation.

    Args:
        registry: Target registry, either ``s3://bucket`` or bare bucket name.
        package_name: Optional ``namespace/package`` for direct package view navigation.
        path: Optional path inside the bucket or package for deep links (e.g., ``data/metrics.csv``).
        catalog_host: Optional override for the catalog host when auto-detection is unavailable.

    Returns:
        Dict containing ``status`` plus URL metadata. When ``status == "success"``, ``catalog_url`` holds the browser
        link to surface back to the user.

        Response format:
        {
            "status": "success",
            "catalog_url": "https://catalog.example.com/b/bucket/packages/ns/pkg/tree/latest/data",
            "view_type": "package",
            "bucket": "bucket",
            "package_name": "ns/pkg",
            "path": "data",
            "catalog_host": "catalog.example.com"
        }

    Next step:
        Share ``result["catalog_url"]`` with the user or feed it into the next navigation helper (for example
        ``auth.catalog_uri`` or messaging back to the MCP client).

    Example:
        ```python
        from quilt_mcp.tools import auth

        catalog_link = auth.catalog_url(
            registry="s3://example-bucket",
            package_name="team/forecast",
            path="reports/summary.pdf",
        )
        next_action = catalog_link["catalog_url"]
        ```
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
            "catalog_host": (catalog_host.replace("https://", "").replace("http://", "") if catalog_host else None),
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
    """Build Quilt+ URI - Quilt authentication and catalog navigation workflows

    WORKFLOW:
        1. Normalize the registry to ``quilt+s3://{bucket}``.
        2. Append package fragments (``package``, ``path``, ``catalog``) based on the supplied context.
        3. Return the URI so downstream tools or clients can reference the same package version consistently.

    Args:
        registry: Registry backing the URI (``s3://bucket`` or bucket name).
        package_name: Optional ``namespace/package`` for linking to a specific package.
        path: Optional package or bucket path fragment to include in the URI.
        top_hash: Optional immutable package hash to lock the reference to a revision.
        tag: Optional human-friendly tag (ignored when ``top_hash`` is provided).
        catalog_host: Optional catalog hostname hint to embed in the fragment.

    Returns:
        Dict containing ``status`` plus the computed ``quilt_plus_uri`` and supporting metadata fields.

        Response format:
        {
            "status": "success",
            "quilt_plus_uri": "quilt+s3://example-bucket#package=team/pkg@1111abcd&path=data/raw",
            "bucket": "example-bucket",
            "package_name": "team/pkg",
            "path": "data/raw",
            "top_hash": "1111abcd",
            "tag": null,
            "catalog_host": "catalog.example.com"
        }

    Next step:
        Combine ``result["quilt_plus_uri"]`` with ``auth.catalog_url`` when the user needs both shareable link formats,
        or return it directly so the client can persist the protocol URI.

    Example:
        ```python
        from quilt_mcp.tools import auth

        uri_result = auth.catalog_uri(
            registry="s3://example-bucket",
            package_name="team/forecast",
            top_hash="1111abcd",
            path="models/best.pkl",
        )
        quilt_plus_reference = uri_result["quilt_plus_uri"]
        ```
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
            "catalog_host": (catalog_host.replace("https://", "").replace("http://", "") if catalog_host else None),
        }

    except Exception as e:
        return {"status": "error", "error": f"Failed to generate Quilt+ URI: {e}"}


def catalog_info() -> dict[str, Any]:
    """Summarize catalog configuration - Quilt authentication and catalog navigation workflows

    WORKFLOW:
        1. Query Quilt configuration for catalog identifiers, URLs, and auth state.
        2. Include optional fields (region, tabulator catalog) when authentication succeeds.
        3. Feed the structured response into subsequent troubleshooting or navigation helpers.

    Returns:
        Dict describing catalog connectivity with ``status``, ``catalog_name``, and optional URLs/metadata.

        Response format:
        {
            "status": "success",
            "catalog_name": "nightly.quilttest.com",
            "is_authenticated": true,
            "navigator_url": "https://nightly.quilttest.com",
            "registry_url": "s3://nightly-bucket",
            "region": "us-east-1",
            "message": "Connected to catalog: nightly.quilttest.com"
        }

    Next step:
        Use the returned fields to answer user questions, chain into ``auth.auth_status`` for deeper diagnostics,
        or help select which catalog-specific tool to call next.

    Example:
        ```python
        from quilt_mcp.tools import auth

        info = auth.catalog_info()
        if not info["is_authenticated"]:
            follow_up = auth.auth_status()
        ```
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

        # Add AWS region and tabulator catalog if authenticated
        if info["region"]:
            result["region"] = info["region"]
        if info["tabulator_data_catalog"]:
            result["tabulator_data_catalog"] = info["tabulator_data_catalog"]

        # Add helpful context
        if info["is_authenticated"]:
            result["message"] = f"Connected to catalog: {info['catalog_name']}"
        else:
            result["message"] = f"Configured for catalog: {info['catalog_name']} (not authenticated)"

        return result

    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to get catalog info: {e}",
            "catalog_name": "unknown",
        }


def catalog_name() -> dict[str, Any]:
    """Identify catalog name - Quilt authentication and catalog navigation workflows

    WORKFLOW:
        1. Inspect Quilt configuration to determine the catalog hostname.
        2. Record how the name was derived (authentication, navigator config, or registry fallback).
        3. Provide a lightweight status payload when the user only needs the catalog identifier.

    Returns:
        Dict containing ``catalog_name``, ``detection_method``, ``is_authenticated``, and ``status`` flags.

        Response format:
        {
            "status": "success",
            "catalog_name": "nightly.quilttest.com",
            "detection_method": "authentication",
            "is_authenticated": true
        }

    Next step:
        Surface the catalog name to the user or call ``auth.catalog_url`` / ``auth.catalog_uri`` using this identifier.

    Example:
        ```python
        from quilt_mcp.tools import auth

        name_info = auth.catalog_name()
        catalog_host = name_info["catalog_name"]
        ```
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
    """Audit Quilt authentication - Quilt authentication and catalog navigation workflows

        WORKFLOW:
            1. Query Quilt for the current login session and catalog configuration.
            2. If authenticated, surface recommended tools for package exploration and permission discovery.
            3. If not authenticated, return step-by-step setup instructions to get the user connected.

        Returns:
            Dict describing authentication status, catalog metadata, and recommended next actions.

            Response format:
            {
                "status": "authenticated",
                "catalog_name": "nightly.quilttest.com",
                "catalog_url": "https://nightly.quilttest.com",
                "user_info": {"username": "alice", "email": "alice@example.com"},
                "suggested_actions": ["Try listing packages with: packages_list()"],
                "next_steps": {"immediate": "..."}
            }

        Next step:
            Relay the status summary to the user and follow the suggested actions (e.g., run ``packages_list`` or guide the
            user through login using the returned ``setup_instructions`` when unauthenticated).

        Example:
            ```python
            from quilt_mcp.tools import auth

            status = auth.auth_status()
            if status["status"] != "authenticated":
                guidance = "
    ".join(status["setup_instructions"])
            ```
    
    """
    try:
        # Get comprehensive catalog information
        service = QuiltService()
        catalog_info = service.get_catalog_info()
        logged_in_url = service.get_logged_in_url()

        if logged_in_url:
            # Get registry bucket information
            registry_bucket = None
            try:
                config = service.get_config()
                if config and config.get("registryUrl"):
                    registry_bucket = _extract_bucket_from_registry(config["registryUrl"])
            except Exception:
                pass

            # Try to get user information
            user_info = {}
            try:
                # Try to get user info from quilt3 if available
                # This is a placeholder - actual implementation would depend on Quilt3 API
                user_info = {
                    "username": "current_user",  # Would be extracted from auth token
                    "email": "user@example.com",  # Would be extracted from auth token
                }
            except Exception:
                user_info = {"username": "unknown", "email": "unknown"}

            # Generate suggested actions based on status
            suggested_actions = [
                "Try listing packages with: packages_list()",
                "Test bucket permissions with: bucket_access_check(bucket_name)",
                "Discover your writable buckets with: aws_permissions_discover()",
                "Create your first package with: package_create_from_s3()",
            ]

            return {
                "status": "authenticated",
                "catalog_url": logged_in_url,
                "catalog_name": catalog_info.get("catalog_name", "unknown"),
                "registry_bucket": registry_bucket,
                "write_permissions": "unknown",  # Will be determined by permissions discovery
                "user_info": user_info,
                "suggested_actions": suggested_actions,
                "message": f"Successfully authenticated to {catalog_info.get('catalog_name', 'Quilt catalog')}",
                "search_available": True,
                "next_steps": {
                    "immediate": "Try: aws_permissions_discover() to see your bucket access",
                    "package_creation": "Try: package_create_from_s3() to create your first package",
                    "exploration": "Try: packages_list() to browse existing packages",
                },
            }
        else:
            # Not authenticated - provide helpful setup guidance
            setup_instructions = [
                "1. Configure catalog: quilt3 config https://open.quiltdata.com",
                "2. Login: quilt3 login",
                "3. Follow the browser authentication flow",
                "4. Verify with: auth_status()",
            ]

            return {
                "status": "not_authenticated",
                "catalog_name": catalog_info.get("catalog_name", "none"),
                "message": "Not logged in to Quilt catalog",
                "search_available": False,
                "setup_instructions": setup_instructions,
                "quick_setup": {
                    "description": "Get started quickly with Quilt",
                    "steps": [
                        {
                            "step": 1,
                            "action": "Configure catalog",
                            "command": "quilt3 config https://open.quiltdata.com",
                        },
                        {"step": 2, "action": "Login", "command": "quilt3 login"},
                        {"step": 3, "action": "Verify", "command": "auth_status()"},
                    ],
                },
                "help": {
                    "documentation": "https://docs.quiltdata.com/",
                    "support": "For help, visit Quilt documentation or contact support",
                },
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
    """Probe filesystem access - Quilt authentication and catalog navigation workflows

    WORKFLOW:
        1. Record core directories relevant to Quilt tooling (home, temp, CWD).
        2. Attempt lightweight write tests to confirm whether persistent flows are available.
        3. Recommend which Quilt tools are safe to use given the discovered permissions.

    Returns:
        Dict summarizing access checks (``home_writable``, ``temp_writable``) plus ``status`` and ``tools_available``.

        Response format:
        {
            "home_directory": "/Users/alice",
            "temp_directory": "/var/folders/..",
            "current_directory": "/workspace",
            "home_writable": true,
            "temp_writable": true,
            "status": "full_access",
            "tools_available": ["auth_status", "packages_list", "..."]
        }

    Next step:
        Use ``result["tools_available"]`` to inform the user which commands are safe, or branch to sandbox-safe flows if
        write access is limited.

    Example:
        ```python
        from quilt_mcp.tools import auth

        fs_status = auth.filesystem_status()
        if not fs_status["home_writable"]:
            note = "Falling back to read-only tooling."
        ```
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
    """Configure Quilt catalog URL - Quilt authentication and catalog navigation workflows

    WORKFLOW:
        1. Validate that the provided URL includes an HTTP(S) scheme.
        2. Persist the catalog setting through ``QuiltService.set_config``.
        3. Return confirmation and recommended actions (login, status check, exploration tools).

    Args:
        catalog_url: Full catalog URL such as ``https://demo.quiltdata.com``.

    Returns:
        Dict with ``status``, the normalized catalog URL, and follow-up instructions for login verification.

        Response format:
        {
            "status": "success",
            "catalog_url": "https://demo.quiltdata.com",
            "configured_url": "https://demo.quiltdata.com",
            "next_steps": ["Login with: quilt3 login", "..."]
        }

    Next step:
        Run ``quilt3 login`` (or instruct the user to do so) and confirm connectivity via ``auth.auth_status()``.

    Example:
        ```python
        from quilt_mcp.tools import auth

        outcome = auth.configure_catalog("https://nightly.quilttest.com")
        if outcome["status"] == "success":
            login_hint = outcome["next_steps"][0]
        ```
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
        service = QuiltService()
        service.set_config(catalog_url)

        # Verify configuration
        config = service.get_config()
        configured_url = config.get("navigator_url") if config else None

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
    """Switch Quilt catalog - Quilt authentication and catalog navigation workflows

    WORKFLOW:
        1. Map friendly catalog names (demo, sandbox, open) to their canonical URLs.
        2. Fallback to interpreting the input as a direct URL or construct ``https://{catalog_name}``.
        3. Delegate to ``configure_catalog`` to persist the target and return confirmation metadata.

    Args:
        catalog_name: Friendly name (``demo``) or full URL (``https://demo.quiltdata.com``) of the desired catalog.

    Returns:
        Dict mirroring ``configure_catalog`` output with extra fields describing the switch action.

        Response format:
        {
            "status": "success",
            "catalog_url": "https://sandbox.quiltdata.com",
            "action": "switched",
            "to_catalog": "sandbox",
            "warning": "You may need to login again with: quilt3 login"
        }

    Next step:
        Prompt the user to re-authenticate via ``quilt3 login`` and verify connectivity using ``auth.auth_status()``.

    Example:
        ```python
        from quilt_mcp.tools import auth

        outcome = auth.switch_catalog("demo")
        if outcome["status"] == "success":
            verify = auth.auth_status()
        ```
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
