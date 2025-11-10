"""Shared helpers for authentication-oriented resources.

These functions were originally implemented as MCP tools but are read-only in
practice.  Consolidating them here lets resources consume the logic directly
while other call sites (e.g. onboarding flows) can reuse the same helpers
without routing through ``quilt_mcp.tools``.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict
from urllib.parse import urlparse

try:
    from quilt_mcp.services.quilt_service import QuiltService
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    # Provide a stub so tests can patch QuiltService without requiring quilt3.
    class QuiltService:  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError("quilt3 is required for QuiltService")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_catalog_name_from_url(url: str) -> str:
    """Return a human-friendly catalog hostname for status messages."""
    if not url:
        return "unknown"

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or parsed.netloc
        if hostname and hostname.startswith("www."):
            return hostname[4:]
        return hostname or url
    except Exception:
        return url


def _extract_bucket_from_registry(registry: str) -> str:
    """Normalize registry URIs to bare bucket names."""
    if registry.startswith("s3://"):
        return registry[5:].split("/", 1)[0]
    return registry


def _get_catalog_info() -> Dict[str, Any]:
    """Return catalog configuration details by delegating to ``QuiltService``."""
    service = QuiltService()
    return service.get_catalog_info()


def _get_catalog_host_from_config() -> str | None:
    """Detect the catalog hostname from current Quilt configuration."""
    try:
        service = QuiltService()

        logged_in_url = service.get_logged_in_url()
        if logged_in_url:
            parsed = urlparse(logged_in_url)
            hostname = parsed.hostname
            return hostname if hostname else None

        config = service.get_config()
        if config and config.get("navigator_url"):
            nav_url = config["navigator_url"]
            parsed = urlparse(nav_url)
            hostname = parsed.hostname
            return hostname if hostname else None
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public helpers consumed by resources and higher-level workflows
# ---------------------------------------------------------------------------


def catalog_info() -> Dict[str, Any]:
    """Summarize catalog configuration for discovery and troubleshooting."""
    try:
        info = _get_catalog_info()

        # Determine detection method
        if info["logged_in_url"]:
            detection_method = "authentication"
        elif info["navigator_url"]:
            detection_method = "navigator_config"
        elif info["registry_url"]:
            detection_method = "registry_config"
        else:
            detection_method = "unknown"

        result: Dict[str, Any] = {
            "catalog_name": info["catalog_name"],
            "is_authenticated": info["is_authenticated"],
            "detection_method": detection_method,
            "status": "success",
        }

        if info["navigator_url"]:
            result["navigator_url"] = info["navigator_url"]
        if info["registry_url"]:
            result["registry_url"] = info["registry_url"]
        if info["logged_in_url"]:
            result["logged_in_url"] = info["logged_in_url"]
        if info["region"]:
            result["region"] = info["region"]
        if info["tabulator_data_catalog"]:
            result["tabulator_data_catalog"] = info["tabulator_data_catalog"]

        result["message"] = (
            f"Connected to catalog: {info['catalog_name']}"
            if info["is_authenticated"]
            else f"Configured for catalog: {info['catalog_name']} (not authenticated)"
        )

        return result

    except Exception as exc:
        return {
            "status": "error",
            "error": f"Failed to get catalog info: {exc}",
            "catalog_name": "unknown",
            "detection_method": "error",
        }


def auth_status() -> Dict[str, Any]:
    """Audit Quilt authentication status and suggest next actions."""
    try:
        service = QuiltService()
        info = service.get_catalog_info()
        logged_in_url = service.get_logged_in_url()

        if logged_in_url:
            registry_bucket = None
            try:
                config = service.get_config()
                if config and config.get("registryUrl"):
                    registry_bucket = _extract_bucket_from_registry(config["registryUrl"])
            except Exception:
                pass

            try:
                user_info = {
                    "username": "current_user",
                    "email": "user@example.com",
                }
            except Exception:
                user_info = {"username": "unknown", "email": "unknown"}

            return {
                "status": "authenticated",
                "catalog_url": logged_in_url,
                "catalog_name": info.get("catalog_name", "unknown"),
                "registry_bucket": registry_bucket,
                "write_permissions": "unknown",
                "user_info": user_info,
                "suggested_actions": [
                    "Try listing packages with: packages_list()",
                    "Test bucket permissions with: bucket_access_check(bucket_name)",
                    "Discover your writable buckets with: aws_permissions_discover()",
                    "Create your first package with: package_create_from_s3()",
                ],
                "message": f"Successfully authenticated to {info.get('catalog_name', 'Quilt catalog')}",
                "search_available": True,
                "next_steps": {
                    "immediate": "Try: aws_permissions_discover() to see your bucket access",
                    "package_creation": "Try: package_create_from_s3() to create your first package",
                    "exploration": "Try: packages_list() to browse existing packages",
                },
            }

        setup_instructions = [
            "1. Configure catalog: quilt3 config https://open.quiltdata.com",
            "2. Login: quilt3 login",
            "3. Follow the browser authentication flow",
            "4. Verify with: auth_status()",
        ]

        return {
            "status": "not_authenticated",
            "catalog_name": info.get("catalog_name", "none"),
            "message": "Not logged in to Quilt catalog",
            "search_available": False,
            "setup_instructions": setup_instructions,
            "quick_setup": {
                "description": "Get started quickly with Quilt",
                "steps": [
                    {"step": 1, "action": "Configure catalog", "command": "quilt3 config https://open.quiltdata.com"},
                    {"step": 2, "action": "Login", "command": "quilt3 login"},
                    {"step": 3, "action": "Verify", "command": "auth_status()"},
                ],
            },
            "help": {
                "documentation": "https://docs.quiltdata.com/",
                "support": "For help, visit Quilt documentation or contact support",
            },
        }

    except Exception as exc:
        return {
            "status": "error",
            "error": f"Failed to check authentication: {exc}",
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


def filesystem_status() -> Dict[str, Any]:
    """Probe filesystem access for Quilt tooling."""
    result: Dict[str, Any] = {
        "home_directory": os.path.expanduser("~"),
        "temp_directory": tempfile.gettempdir(),
        "current_directory": os.getcwd(),
    }

    try:
        test_file = os.path.join(result["home_directory"], ".quilt_test_write")
        with open(test_file, "w", encoding="utf-8") as handle:
            handle.write("test")
        os.remove(test_file)
        result["home_writable"] = True
    except Exception as exc:
        result["home_writable"] = False
        result["home_write_error"] = str(exc)

    try:
        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            tmp.write(b"test")
        result["temp_writable"] = True
    except Exception as exc:
        result["temp_writable"] = False
        result["temp_write_error"] = str(exc)

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
                "package_browse",
                "package_create",
                "package_update",
                "bucket_objects_list",
                "bucket_object_info",
                "bucket_object_text",
                "bucket_objects_put",
                "bucket_object_fetch",
                "unified_search",
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
                "bucket_objects_list",
                "bucket_object_info",
                "bucket_object_text",
                "packages_list",
                "unified_search",
            ],
        )
    else:
        result.update(
            status="read_only",
            message="Read-only filesystem access - limited Quilt functionality available",
            tools_available=[
                "auth_status",
                "catalog_info",
                "catalog_name",
                "catalog_url",
                "catalog_uri",
                "bucket_objects_list",
                "bucket_object_info",
                "bucket_object_text",
                "packages_list",
                "unified_search",
            ],
        )

    return result


def configure_catalog(catalog_url: str) -> Dict[str, Any]:
    """Configure the Quilt catalog URL.

    Args:
        catalog_url: Full catalog URL or friendly name (demo, sandbox, open).

    Returns:
        Dict containing configuration result with status, catalog_url, and next steps.
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
        original_input = catalog_url
        if catalog_url.lower() in catalog_mappings:
            catalog_url = catalog_mappings[catalog_url.lower()]
            friendly_name = original_input.lower()
        elif catalog_url.startswith(("http://", "https://")):
            friendly_name = _extract_catalog_name_from_url(catalog_url)
        elif not catalog_url.startswith(("http://", "https://")):
            # Try to construct URL
            catalog_url = f"https://{catalog_url}"
            friendly_name = original_input
        else:
            friendly_name = _extract_catalog_name_from_url(catalog_url)

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
            "message": f"Successfully configured catalog: {friendly_name}",
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

    except Exception as exc:
        return {
            "status": "error",
            "error": f"Failed to configure catalog: {exc}",
            "catalog_url": catalog_url,
            "available_catalogs": list(catalog_mappings.keys()) if "catalog_mappings" in locals() else [],
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
                    "Use one of the available catalog names: demo, sandbox, open",
                ],
            },
        }


__all__ = [
    "auth_status",
    "catalog_info",
    "configure_catalog",
    "filesystem_status",
    "_extract_catalog_name_from_url",
    "_extract_bucket_from_registry",
    "_get_catalog_info",
    "_get_catalog_host_from_config",
]
