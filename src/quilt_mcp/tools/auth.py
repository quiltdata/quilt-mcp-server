"""Authentication and filesystem access tools."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from quilt_mcp.services.auth_metadata import (
    _extract_bucket_from_registry,
    _extract_catalog_name_from_url,
    _get_catalog_host_from_config,
    _get_catalog_info,
    auth_status as _auth_status,
    catalog_info as _catalog_info,
    catalog_name as _catalog_name,
    filesystem_status as _filesystem_status,
)

try:
    from ..services.quilt_service import QuiltService
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    class QuiltService:  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError("quilt3 is required for QuiltService") from exc


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
def catalog_info() -> dict[str, Any]:
    """Wrapper around shared catalog_info helper for backward compatibility."""
    return _catalog_info()


def catalog_name() -> dict[str, Any]:
    """Wrapper around shared catalog_name helper for backward compatibility."""
    return _catalog_name()


def auth_status() -> dict[str, Any]:
    """Wrapper around shared auth_status helper for backward compatibility."""
    return _auth_status()


def filesystem_status() -> dict[str, Any]:
    """Wrapper around shared filesystem_status helper for backward compatibility."""
    return _filesystem_status()
