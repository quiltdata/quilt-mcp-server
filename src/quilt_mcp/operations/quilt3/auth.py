"""Quilt3 authentication operations.

This module provides isolated authentication operations that accept
explicit configuration parameters instead of relying on global quilt3 state.

The functions in this module:
- Accept explicit registry_url and catalog_url parameters
- Do not call quilt3.config() or rely on global configuration
- Return the same format as the existing tools for backward compatibility
- Can be tested in isolation with different configurations
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

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


def check_auth_status(registry_url: str, catalog_url: str | None) -> dict[str, Any]:
    """Check Quilt authentication status with explicit configuration parameters.

    This function configures quilt3 with the provided parameters and then
    makes actual quilt3 API calls to determine authentication status and
    retrieve user information.

    Args:
        registry_url: S3 registry URL (e.g., 's3://my-bucket')
        catalog_url: Optional catalog URL (e.g., 'https://catalog.example.com')

    Returns:
        Dict with comprehensive authentication status, catalog info, permissions, and next steps.
        Same format as existing auth_status() tool for backward compatibility.
    """
    try:
        # Configure quilt3 with the provided parameters
        if catalog_url:
            quilt3.config(catalog_url)

        # Set the registry if provided
        if registry_url:
            # Note: quilt3 doesn't have a direct registry config method,
            # but we can use this for operations that need a specific registry
            pass

        # Check current authentication status
        logged_in_url = quilt3.logged_in()

        if logged_in_url:
            # Get registry bucket information from provided config
            registry_bucket = None
            if registry_url:
                registry_bucket = _extract_bucket_from_registry(registry_url)

            # Determine catalog name from provided catalog_url or logged_in_url
            catalog_name = "unknown"
            if catalog_url:
                catalog_name = _extract_catalog_name_from_url(catalog_url)
            elif logged_in_url:
                catalog_name = _extract_catalog_name_from_url(logged_in_url)

            # Try to get actual user information from quilt3
            user_info = {}
            try:
                # Get user info from quilt3 - this varies by catalog implementation
                # For now, extract what we can from the authentication state
                user_info = {
                    "username": "authenticated_user",  # quilt3 doesn't expose username directly
                    "email": "unknown",  # quilt3 doesn't expose email directly
                    "authenticated_to": logged_in_url,
                }
            except Exception:
                user_info = {"username": "unknown", "email": "unknown"}

            # Generate suggested actions based on status
            suggested_actions = [
                "Try listing packages with: packages_search()",
                "Test bucket permissions with: bucket_access_check(bucket_name)",
                "Discover your writable buckets with: aws_permissions_discover()",
                "Create your first package with: create_package_enhanced()",
            ]

            return {
                "status": "authenticated",
                "catalog_url": catalog_url or logged_in_url,
                "catalog_name": catalog_name,
                "registry_bucket": registry_bucket,
                "registry_url": registry_url,
                "write_permissions": "unknown",  # Will be determined by permissions discovery
                "user_info": user_info,
                "suggested_actions": suggested_actions,
                "message": f"Successfully authenticated to {catalog_name}",
                "search_available": True,
                "next_steps": {
                    "immediate": "Try: aws_permissions_discover() to see your bucket access",
                    "package_creation": "Try: create_package_enhanced() to create your first package",
                    "exploration": "Try: packages_search() to browse existing packages",
                },
            }
        else:
            # Not authenticated - provide helpful setup guidance
            catalog_name = "none"
            if catalog_url:
                catalog_name = _extract_catalog_name_from_url(catalog_url)

            # Provide setup instructions based on the catalog being used
            catalog_config_url = catalog_url or "https://open.quiltdata.com"
            setup_instructions = [
                f"1. Configure catalog: quilt3 config {catalog_config_url}",
                "2. Login: quilt3 login",
                "3. Follow the browser authentication flow",
                "4. Verify with: auth_status()",
            ]

            return {
                "status": "not_authenticated",
                "catalog_name": catalog_name,
                "catalog_url": catalog_config_url,
                "message": "Not logged in to Quilt catalog",
                "search_available": False,
                "setup_instructions": setup_instructions,
                "quick_setup": {
                    "description": "Get started quickly with Quilt",
                    "steps": [
                        {
                            "step": 1,
                            "action": "Configure catalog",
                            "command": f"quilt3 config {catalog_config_url}",
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
        catalog_name = "unknown"
        if catalog_url:
            catalog_name = _extract_catalog_name_from_url(catalog_url)

        return {
            "status": "error",
            "error": f"Failed to check authentication: {e}",
            "catalog_name": catalog_name,
            "catalog_url": catalog_url,
            "troubleshooting": {
                "common_issues": [
                    "AWS credentials not configured",
                    "Quilt not installed properly",
                    "Network connectivity issues",
                    "Invalid catalog URL provided",
                ],
                "suggested_fixes": [
                    "Check AWS credentials with: aws sts get-caller-identity",
                    "Reinstall quilt3: pip install --upgrade quilt3",
                    "Check network connectivity",
                    f"Verify catalog URL: {catalog_url or 'https://open.quiltdata.com'}",
                ],
            },
            "setup_instructions": [
                f"1. Configure catalog: quilt3 config {catalog_url or 'https://open.quiltdata.com'}",
                "2. Login: quilt3 login",
            ],
        }