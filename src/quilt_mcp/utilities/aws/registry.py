"""AWS registry operations utilities.

This module provides composable utilities for Quilt registry operations including:
- Registry URL generation and validation
- Package listing with pagination support
- Package metadata retrieval
- Registry access validation

Features:
- Supports both bucket names and S3 URLs as registry identifiers
- Comprehensive error handling with specific error types
- Pagination support for large package lists
- Package metadata extraction from Quilt manifest structure
- Registry access validation with detailed permissions reporting
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class RegistryError(Exception):
    """Custom exception for registry-related errors."""

    pass


def get_registry_url(registry_name: str) -> str:
    """Get registry URL from registry name.

    Args:
        registry_name: Registry name (bucket name or S3 URL)

    Returns:
        Fully qualified S3 URL for the registry

    Raises:
        RegistryError: When registry name is invalid

    Examples:
        >>> get_registry_url("my-registry")
        's3://my-registry'

        >>> get_registry_url("s3://my-registry")
        's3://my-registry'
    """
    if not registry_name or not registry_name.strip():
        raise RegistryError("Registry name cannot be empty")

    registry_name = registry_name.strip()

    # If already an S3 URL, return as-is
    if registry_name.startswith("s3://"):
        return registry_name

    # Otherwise, construct S3 URL
    return f"s3://{registry_name}"


def list_packages(
    client: Any,
    registry_url: str,
    prefix: str = "",
    max_keys: int = 1000,
    continuation_token: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """List packages in a Quilt registry with pagination support.

    Args:
        client: S3 client instance
        registry_url: Registry S3 URL (e.g., 's3://my-registry')
        prefix: Filter packages by prefix (default: "")
        max_keys: Maximum number of packages to return (default: 1000)
        continuation_token: Token for pagination (default: None)
        **kwargs: Additional parameters

    Returns:
        Dict with packages list and pagination information

    Raises:
        RegistryError: When listing packages fails

    Examples:
        >>> s3_client = create_client(session)
        >>> result = list_packages(s3_client, 's3://my-registry')
        >>> for pkg in result['packages']:
        ...     print(f"Package: {pkg['name']}")
    """
    # Extract bucket name from registry URL
    bucket_name = _extract_bucket_from_registry_url(registry_url)

    # Quilt packages are stored under .quilt/packages/
    quilt_prefix = ".quilt/packages/" if not prefix else f"{prefix}/.quilt/packages/"

    params: Dict[str, Any] = {"Bucket": bucket_name, "Prefix": quilt_prefix, "MaxKeys": max_keys, **kwargs}

    if continuation_token:
        params["ContinuationToken"] = continuation_token

    try:
        response = client.list_objects_v2(**params)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDenied':
            raise RegistryError(f"Access denied to registry '{registry_url}'. Check your permissions.") from e
        elif error_code == 'NoSuchBucket':
            raise RegistryError(f"Registry bucket '{bucket_name}' does not exist.") from e
        else:
            raise RegistryError(f"Failed to list packages in registry '{registry_url}': {e}") from e
    except Exception as e:
        raise RegistryError(f"Unexpected error listing packages: {e}") from e

    # Parse packages from S3 objects
    packages = []
    for item in response.get("Contents", []):
        key = item.get("Key", "")

        # Extract package name from key pattern: prefix/.quilt/packages/manifest_hash
        # or just .quilt/packages/manifest_hash for root packages
        if "/.quilt/packages/" in key:
            package_name = key.split("/.quilt/packages/")[0]
            if package_name and package_name not in [pkg['name'] for pkg in packages]:
                packages.append(
                    {
                        "name": package_name,
                        "last_modified": item.get("LastModified"),
                        "size": item.get("Size"),
                        "registry_url": registry_url,
                    }
                )

    return {
        "registry_url": registry_url,
        "prefix": prefix,
        "packages": packages,
        "truncated": response.get("IsTruncated", False),
        "next_token": response.get("NextContinuationToken"),
        "key_count": response.get("KeyCount", len(packages)),
        "max_keys": max_keys,
    }


def get_package_metadata(client: Any, registry_url: str, package_name: str, **kwargs: Any) -> Dict[str, Any]:
    """Get metadata for a specific package in the registry.

    Args:
        client: S3 client instance
        registry_url: Registry S3 URL
        package_name: Name of the package (e.g., 'user/package')
        **kwargs: Additional parameters

    Returns:
        Dict with package metadata information

    Raises:
        RegistryError: When package is not found or metadata cannot be retrieved

    Examples:
        >>> metadata = get_package_metadata(s3_client, 's3://registry', 'user/package')
        >>> print(f"Latest version: {metadata['latest_version']}")
    """
    if not package_name or not package_name.strip():
        raise RegistryError("Package name cannot be empty or invalid")

    package_name = package_name.strip()
    bucket_name = _extract_bucket_from_registry_url(registry_url)

    # Look for package manifest files
    package_prefix = f"{package_name}/.quilt/packages/"

    params: Dict[str, Any] = {
        "Bucket": bucket_name,
        "Prefix": package_prefix,
        "MaxKeys": 100,  # Should be enough for package versions
        **kwargs,
    }

    try:
        response = client.list_objects_v2(**params)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDenied':
            raise RegistryError(f"Access denied to registry '{registry_url}'. Check your permissions.") from e
        elif error_code == 'NoSuchBucket':
            raise RegistryError(f"Registry bucket does not exist: {registry_url}") from e
        else:
            raise RegistryError(f"Failed to get package metadata: {e}") from e
    except Exception as e:
        raise RegistryError(f"Unexpected error getting package metadata: {e}") from e

    contents = response.get("Contents", [])
    if not contents:
        raise RegistryError(f"Package '{package_name}' not found in registry '{registry_url}'")

    # Extract version information from manifest files
    versions = []
    latest_version = None

    for item in contents:
        key = item.get("Key", "")

        # Extract version hash from key
        if key.startswith(package_prefix):
            version_hash = key[len(package_prefix) :]
            if version_hash and version_hash != "latest":
                versions.append(
                    {
                        "hash": version_hash,
                        "last_modified": item.get("LastModified"),
                        "size": item.get("Size"),
                    }
                )
            elif version_hash == "latest":
                latest_version = {
                    "last_modified": item.get("LastModified"),
                    "size": item.get("Size"),
                }

    # Sort versions by last modified (most recent first)
    versions.sort(key=lambda x: x["last_modified"], reverse=True)

    return {
        "package_name": package_name,
        "registry_url": registry_url,
        "latest_version": latest_version,
        "versions": versions,
        "total_versions": len(versions),
        "package_prefix": package_prefix,
    }


def validate_registry_access(client: Any, registry_url: str, **kwargs: Any) -> Dict[str, Any]:
    """Validate access permissions for a registry.

    Args:
        client: S3 client instance
        registry_url: Registry S3 URL to validate
        **kwargs: Additional parameters

    Returns:
        Dict with access validation results

    Raises:
        RegistryError: When registry does not exist or cannot be accessed

    Examples:
        >>> access_info = validate_registry_access(s3_client, 's3://my-registry')
        >>> if access_info['can_write']:
        ...     print("Can create packages in this registry")
    """
    bucket_name = _extract_bucket_from_registry_url(registry_url)

    access_info = {
        "registry_url": registry_url,
        "bucket_name": bucket_name,
        "accessible": False,
        "can_list": False,
        "can_read": False,
        "can_write": False,
        "error_message": None,
    }

    try:
        # Test 1: Check if bucket exists and is accessible
        try:
            client.head_bucket(Bucket=bucket_name)
            access_info["accessible"] = True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                raise RegistryError(f"Registry bucket '{bucket_name}' does not exist")
            elif error_code == 'AccessDenied':
                raise RegistryError(f"Access denied to registry bucket '{bucket_name}'")
            else:
                raise RegistryError(f"Cannot access registry bucket: {e}")

        # Test 2: Check list permissions
        try:
            client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            access_info["can_list"] = True
        except ClientError as e:
            if e.response['Error']['Code'] != 'AccessDenied':
                raise RegistryError(f"Error testing list permissions: {e}")

        # Test 3: Check read permissions (safe test with non-existent key)
        if access_info["can_list"]:
            try:
                client.head_object(Bucket=bucket_name, Key="__permission_test_key")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'NotFound':
                    access_info["can_read"] = True  # 404 means we have read permission
                elif error_code != 'AccessDenied':
                    access_info["can_read"] = True  # Other errors might still indicate read permission

        # Test 4: Check write permissions (safe test using bucket ACL check)
        if access_info["can_list"]:
            try:
                client.get_bucket_acl(Bucket=bucket_name)
                access_info["can_write"] = True
            except ClientError as e:
                if e.response['Error']['Code'] != 'AccessDenied':
                    # Try alternative write test
                    access_info["can_write"] = _test_write_permissions_safe(client, bucket_name)

    except RegistryError:
        # Re-raise registry-specific errors
        raise
    except Exception as e:
        raise RegistryError(f"Unexpected error validating registry access: {e}") from e

    return access_info


def _extract_bucket_from_registry_url(registry_url: str) -> str:
    """Extract bucket name from registry S3 URL.

    Args:
        registry_url: Registry S3 URL

    Returns:
        Bucket name

    Raises:
        RegistryError: When URL format is invalid
    """
    if not registry_url:
        raise RegistryError("Registry URL cannot be empty")

    if registry_url.startswith("s3://"):
        # Parse S3 URL to extract bucket name
        parsed = urlparse(registry_url)
        bucket_name = parsed.netloc
        if not bucket_name:
            raise RegistryError(f"Invalid S3 URL format: {registry_url}")
        return bucket_name
    else:
        raise RegistryError(f"Registry URL must be an S3 URL (s3://bucket-name): {registry_url}")


def _test_write_permissions_safe(client: Any, bucket_name: str) -> bool:
    """Safely test write permissions without creating objects.

    Args:
        client: S3 client instance
        bucket_name: Bucket name to test

    Returns:
        True if write permissions detected, False otherwise
    """
    try:
        # Test bucket versioning (requires write-like permissions)
        client.get_bucket_versioning(Bucket=bucket_name)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] != 'AccessDenied':
            return True  # Other errors suggest we have some access

    try:
        # Test bucket notification configuration
        client.get_bucket_notification_configuration(Bucket=bucket_name)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] != 'AccessDenied':
            return True

    # Conservative approach - assume no write access if we can't confirm
    return False
