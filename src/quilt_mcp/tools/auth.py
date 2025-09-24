"""Authentication and filesystem access tools."""

from __future__ import annotations

import os
import tempfile
import logging
from typing import Any
from urllib.parse import quote, urlparse

from ..services.quilt_service import QuiltService
from ..services.auth_service import get_auth_service

logger = logging.getLogger(__name__)


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
            "catalog_host": (catalog_host.replace("https://", "").replace("http://", "") if catalog_host else None),
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
            result["message"] = f"Configured for catalog: {info['catalog_name']} (not authenticated)"

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
    """Check Quilt authentication status with rich information and actionable suggestions.

    Returns:
        Dict with comprehensive authentication status, catalog info, permissions, and next steps.
    """
    try:
        # Use the new authentication service for ECS compatibility
        auth_service = get_auth_service()
        auth_status_result = auth_service.get_auth_status()
        
        # Fall back to QuiltService for local development
        service = QuiltService()
        quilt_catalog_info = service.get_catalog_info()
        logged_in_url = service.get_logged_in_url()

        # Prioritize authentication service results for ECS deployment
        if auth_status_result.get("status") == "authenticated":
            # Use authentication service results
            auth_method = auth_status_result.get("auth_method", "unknown")
            auth_catalog_url = auth_status_result.get("catalog_url")
            aws_credentials = auth_status_result.get("aws_credentials", {})
            
            # Generate suggested actions based on authentication method
            if auth_method == "IAM_ROLE":
                suggested_actions = [
                    "You're authenticated via IAM role - try listing packages with: packages_list()",
                    "Test bucket permissions with: bucket_access_check(bucket_name)",
                    "Discover your writable buckets with: aws_permissions_discover()",
                    "Create your first package with: package_create_from_s3()",
                ]
            else:
                suggested_actions = [
                    "Try listing packages with: packages_list()",
                    "Test bucket permissions with: bucket_access_check(bucket_name)",
                    "Discover your writable buckets with: aws_permissions_discover()",
                    "Create your first package with: package_create_from_s3()",
                ]
            
            return {
                "status": "authenticated",
                "auth_method": auth_method,
                "catalog_url": auth_catalog_url,
                "catalog_name": auth_status_result.get("catalog_name", "unknown"),
                "aws_credentials": aws_credentials,
                "message": f"Successfully authenticated via {auth_method}",
                "suggested_actions": suggested_actions,
                "authentication_service": True,
            }
        elif logged_in_url:
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
                "catalog_name": quilt_catalog_info.get("catalog_name", "unknown"),
                "registry_bucket": registry_bucket,
                "write_permissions": "unknown",  # Will be determined by permissions discovery
                "user_info": user_info,
                "suggested_actions": suggested_actions,
                "message": f"Successfully authenticated to {quilt_catalog_info.get('catalog_name', 'Quilt catalog')}",
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
                "1. Configure catalog: quilt3 config https://demo.quiltdata.com",
                "2. Login: quilt3 login",
                "3. Follow the browser authentication flow",
                "4. Verify with: auth_status()",
            ]

            return {
                "status": "not_authenticated",
                "catalog_name": quilt_catalog_info.get("catalog_name", "none"),
                "message": "Not logged in to Quilt catalog",
                "search_available": False,
                "setup_instructions": setup_instructions,
                "quick_setup": {
                    "description": "Get started quickly with Quilt",
                    "steps": [
                        {
                            "step": 1,
                            "action": "Configure catalog",
                            "command": "quilt3 config https://demo.quiltdata.com",
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
                "1. Configure catalog: quilt3 config https://demo.quiltdata.com",
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

        # Configure the catalog for both local and ECS environments
        # For ECS environment, set environment variable
        os.environ["QUILT_CATALOG_URL"] = catalog_url
        
        # For local environment, try quilt3.config (may fail in ECS)
        service = QuiltService()
        try:
            service.set_config(catalog_url)
            config = service.get_config()
            configured_url = config.get("navigator_url") if config else None
        except Exception as config_error:
            # In ECS environment, quilt3.config may fail due to network restrictions
            # Use environment variable instead
            configured_url = catalog_url
            logger.warning(f"quilt3.config failed (expected in ECS): {config_error}")
        
        # Update AuthenticationService to pick up the new catalog URL
        auth_service = get_auth_service()
        if hasattr(auth_service, 'update_catalog_url'):
            auth_service.update_catalog_url(catalog_url)

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
            "example": "https://demo.quiltdata.com",
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


async def assume_quilt_user_role(role_arn: str = None) -> dict[str, Any]:
    """Assume the Quilt user role for MCP operations.
    
    NOTE: Role assumption is now AUTOMATIC when Quilt headers are present.
    This tool is provided for manual override or testing purposes.
    
    The MCP server automatically assumes the user's role when it receives
    X-Quilt-User-Role headers from the MCP client.
    
    Args:
        role_arn: Optional ARN of the Quilt user role to assume. If not provided,
                 the role will be automatically detected from Quilt headers.
    
    Returns:
        Dict with role assumption result and status information.
    """
    try:
        # Get the authentication service
        from quilt_mcp.services.auth_service import get_auth_service
        auth_service = get_auth_service()
        
        # If no role ARN provided, try to get it from environment (set by Quilt headers)
        if not role_arn:
            role_arn = os.environ.get("QUILT_USER_ROLE_ARN")
            if not role_arn:
                return {
                    "status": "error",
                    "error": "No Quilt user role ARN available",
                    "suggestions": [
                        "Ensure the MCP client is sending X-Quilt-User-Role header",
                        "Provide role_arn parameter directly",
                        "Check that Quilt role switching is working properly",
                    ],
                    "help": {
                        "manual_assumption": "assume_quilt_user_role('arn:aws:iam::ACCOUNT:role/ROLE_NAME')",
                        "header_info": "The MCP client should send X-Quilt-User-Role header with the role ARN",
                    },
                }
        
        # Validate role ARN format
        if not role_arn.startswith("arn:aws:iam::"):
            return {
                "status": "error",
                "error": "Invalid role ARN format",
                "provided": role_arn,
                "expected": "ARN starting with 'arn:aws:iam::'",
                "example": "arn:aws:iam::850787717197:role/quilt-user-role",
            }
        
        # Attempt to assume the specified role
        success = auth_service.assume_quilt_user_role(role_arn)
        
        if success:
            # Get updated authentication status
            auth_status = auth_service.get_auth_status()
            
            return {
                "status": "success",
                "role_arn": role_arn,
                "message": f"Successfully assumed Quilt user role: {role_arn}",
                "authentication_status": auth_status,
                "next_steps": [
                    "MCP operations will now use the assumed role credentials",
                    "Verify access with: auth_status()",
                    "Start using MCP tools with the new role context",
                ],
                "help": {
                    "verify_command": "auth_status()",
                    "documentation": "https://docs.quiltdata.com/",
                },
            }
        else:
            return {
                "status": "error",
                "error": f"Failed to assume role: {role_arn}",
                "role_arn": role_arn,
                "troubleshooting": {
                    "common_issues": [
                        "Role ARN does not exist",
                        "Insufficient permissions to assume role",
                        "Role trust policy does not allow ECS task role",
                        "Role is in a different AWS account",
                    ],
                    "suggested_fixes": [
                        "Verify the role ARN is correct and exists",
                        "Check that the ECS task role has sts:AssumeRole permission",
                        "Ensure the target role's trust policy allows the ECS task role",
                        "Verify the role is in the same AWS account",
                    ],
                },
            }
    
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to assume Quilt user role: {e}",
            "role_arn": role_arn,
            "troubleshooting": {
                "common_issues": [
                    "Invalid role ARN format",
                    "Network connectivity problems",
                    "AWS service errors",
                ],
                "suggested_fixes": [
                    "Verify the role ARN format is correct",
                    "Check network connectivity to AWS",
                    "Review AWS CloudWatch logs for detailed errors",
                ],
            },
        }


async def get_current_quilt_role() -> dict[str, Any]:
    """Get information about the current Quilt user role.
    
    This tool provides information about what role the Quilt user is currently
    using. Role assumption is now AUTOMATIC when Quilt headers are present.
    
    Returns:
        Dict with current role information and detection status.
    """
    try:
        # Check for role information from Quilt headers (set by middleware)
        header_role_arn = os.environ.get("QUILT_USER_ROLE_ARN")
        header_user_id = os.environ.get("QUILT_USER_ID")
        
        if header_role_arn:
            return {
                "status": "success",
                "current_role_arn": header_role_arn,
                "user_id": header_user_id,
                "message": f"Found Quilt user role from headers: {header_role_arn}",
                "detection_method": "quilt_headers",
                "source": "X-Quilt-User-Role header from MCP client",
                "next_steps": [
                    "Role assumption is AUTOMATIC - no action needed!",
                    "The MCP server will automatically assume this role on each request",
                    "All MCP operations will use this role's permissions",
                ],
                "integration_status": {
                    "quilt_headers": "✅ Available",
                    "automatic_assumption": "✅ Ready",
                    "role_switching": "✅ Supported",
                },
            }
        
        # Fallback: Try to get role from Quilt credentials (local development)
        from quilt_mcp.services.auth_service import get_auth_service
        auth_service = get_auth_service()
        
        # Try to get the current Quilt user role from credentials
        current_role_arn = auth_service._get_quilt_user_role_arn()
        
        if current_role_arn:
            return {
                "status": "success",
                "current_role_arn": current_role_arn,
                "message": f"Found Quilt user role from credentials: {current_role_arn}",
                "detection_method": "quilt_credentials",
                "source": "Local Quilt credentials (~/.quilt/)",
                "next_steps": [
                    "Role assumption is AUTOMATIC when headers are present",
                    f"For manual override: assume_quilt_user_role('{current_role_arn}')",
                    "The MCP server will operate with the same permissions as the Quilt user",
                ],
                "integration_status": {
                    "quilt_headers": "❌ Not available (local development mode)",
                    "automatic_assumption": "✅ Ready",
                    "role_switching": "⚠️ Manual only",
                },
            }
        else:
            return {
                "status": "info",
                "message": "Could not detect Quilt user role",
                "detection_method": "none",
                "suggestions": [
                    "Ensure the MCP client is sending X-Quilt-User-Role header",
                    "For local development, ensure you are logged in with 'quilt3 login'",
                    "Check that Quilt credentials are available in ~/.quilt/",
                    "Manually specify the role ARN using assume_quilt_user_role()",
                ],
                "integration_status": {
                    "quilt_headers": "❌ Not available",
                    "automatic_assumption": "❌ Not possible",
                    "role_switching": "❌ Not available",
                },
                "help": {
                    "login_command": "quilt3 login",
                    "manual_assumption": "assume_quilt_user_role('arn:aws:iam::ACCOUNT:role/ROLE_NAME')",
                    "header_requirements": "MCP client should send X-Quilt-User-Role header",
                    "documentation": "https://docs.quiltdata.com/",
                },
            }
    
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to detect Quilt user role: {e}",
            "troubleshooting": {
                "common_issues": [
                    "Quilt not properly authenticated",
                    "Missing Quilt credentials",
                    "MCP client not sending required headers",
                    "Network connectivity problems",
                ],
                "suggested_fixes": [
                    "Run 'quilt3 login' to authenticate (local development)",
                    "Check ~/.quilt/credentials.json exists and is valid",
                    "Verify MCP client is sending X-Quilt-User-Role header",
                    "Verify network connectivity to Quilt services",
                ],
            },
        }
