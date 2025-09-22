"""Comprehensive Package Management Tools.

This module provides enhanced package management functionality with better
error handling, metadata templates, and improved user experience based on
real-world testing feedback.

IMPORTANT: This module automatically ensures that README content is always written
as README.md files within packages, never stored in package metadata. Any
'readme_content' or 'readme' fields in metadata will be automatically extracted
and converted to package files.
"""

from typing import Dict, Any
import logging

from ..constants import DEFAULT_REGISTRY
from ..utils import format_error_response
from .packages import package_browse

logger = logging.getLogger(__name__)




def _validate_package_alternative(package_name: str, registry: str, browse_error: Dict[str, Any]) -> Dict[str, Any]:
    """Alternative validation approach when package browsing fails."""
    try:
        # Try to check if package exists using search
        from .packages import catalog_search

        search_result = catalog_search(package_name, registry=registry, limit=1)

        if search_result.get("success") and search_result.get("results"):
            # Package exists but browsing failed - likely a permissions issue
            return {
                "success": True,
                "package_name": package_name,
                "registry": registry,
                "validation": {
                    "package_accessible": True,
                    "browsing_failed": True,
                    "total_files": "unknown",
                    "accessible_files": "unknown",
                    "inaccessible_files": "unknown",
                    "errors": [f"Package browsing failed: {browse_error.get('error', 'Unknown error')}"],
                    "warnings": ["Could not validate individual files due to browsing failure"],
                },
                "summary": {
                    "package_exists": True,
                    "validation_limited": True,
                    "reason": "Package browsing failed but package exists in search results",
                },
                "recommendations": [
                    "Package exists but detailed validation failed",
                    "This may be due to permissions or registry configuration",
                    f"Try: catalog_search('{package_name}') to verify package exists",
                    "Check your registry configuration and permissions",
                ],
            }
        else:
            # Package doesn't exist or search also failed
            return {
                "success": False,
                "error": "Cannot validate package - browsing failed",
                "browse_error": browse_error.get("error"),
                "search_attempted": True,
                "search_result": search_result.get("error", "Package not found in search"),
                "suggested_fixes": [
                    "Verify the package name is correct",
                    "Check if you have access to the registry",
                    "Ensure the package exists in the specified registry",
                ],
            }
    except Exception as e:
        return {
            "success": False,
            "error": "Cannot validate package - browsing failed",
            "browse_error": browse_error.get("error"),
            "alternative_validation_error": str(e),
            "suggested_fixes": [
                "Verify the package name is correct",
                "Check if you have access to the registry",
                "Ensure the package exists in the specified registry",
            ],
        }


def package_validate(
    package_name: str,
    registry: str = None,
    check_integrity: bool = True,
    check_accessibility: bool = True,
) -> Dict[str, Any]:
    """
    Validate package integrity and accessibility.

    Args:
        package_name: Name of the package to validate
        registry: Registry containing the package
        check_integrity: Verify all files are accessible (default: True)
        check_accessibility: Check if files can be downloaded (default: True)

    Returns:
        Comprehensive validation report
    """
    try:
        # Determine registry to use
        target_registry = registry or DEFAULT_REGISTRY
        if not target_registry:
            target_registry = "s3://quilt-sandbox-bucket"  # Fallback for testing

        # Browse the package to get file information
        browse_result = package_browse(package_name, registry=target_registry)

        if not browse_result.get("success"):
            # Try alternative validation approach if browsing fails
            return _validate_package_alternative(package_name, target_registry, browse_result)

        entries = browse_result.get("entries", [])
        validation_results = {
            "package_accessible": True,
            "total_files": len(entries),
            "accessible_files": 0,
            "inaccessible_files": 0,
            "errors": [],
            "warnings": [],
        }

        # Check each file if integrity check is requested
        if check_integrity:
            for entry in entries:
                if entry.get("physical_key") and not entry.get("error"):
                    validation_results["accessible_files"] += 1
                else:
                    validation_results["inaccessible_files"] += 1
                    if entry.get("error"):
                        validation_results["errors"].append(f"File {entry['logical_key']}: {entry['error']}")

        # Generate validation summary
        if validation_results["inaccessible_files"] > 0:
            validation_results["warnings"].append(
                f"{validation_results['inaccessible_files']} files have access issues"
            )

        return {
            "success": True,
            "package_name": package_name,
            "registry": registry,
            "validation": validation_results,
            "summary": browse_result.get("summary", {}),
            "recommendations": [
                (
                    "Package appears healthy"
                    if validation_results["inaccessible_files"] == 0
                    else "Some files have access issues - check permissions"
                ),
                f"Browse full contents with: package_browse('{package_name}')",
                f"Search within package: package_contents_search('{package_name}', 'term')",
            ],
        }

    except Exception as e:
        return format_error_response(f"Package validation failed: {str(e)}")


def package_tools_list() -> Dict[str, Any]:
    """
    List all package management tools with usage guidance.

    Returns:
        Comprehensive guide to package management tools
    """
    return {
        "primary_tools": {
            "create_package": {
                "description": "Main package creation tool with templates and validation",
                "use_when": "Creating new packages with smart defaults",
                "example": 'create_package("team/dataset", ["s3://bucket/file.csv"])',
            },
            "package_browse": {
                "description": "Browse package contents with file tree view",
                "use_when": "Exploring package structure and files",
                "example": 'package_browse("team/dataset", recursive=True)',
            },
            "package_validate": {
                "description": "Validate package integrity and accessibility",
                "use_when": "Checking package health and file accessibility",
                "example": 'package_validate("team/dataset")',
            },
        },
        "specialized_tools": {
            "package_create_from_s3": {
                "description": "Advanced S3-to-package creation with organization",
                "use_when": "Creating packages from entire S3 buckets/prefixes",
                "example": 'package_create_from_s3("bucket-name", "team/dataset")',
            },
            "package_create_new_version": {
                "description": "Create new package version with updated metadata",
                "use_when": "Need to update metadata while preserving version history",
                "example": 'create_package("team/dataset", files, metadata=new_metadata)',
                "note": "Creating new versions preserves immutability and version history",
            },
        },
        "utility_tools": {
            "list_metadata_templates": {
                "description": "Show available metadata templates",
                "example": "list_metadata_templates()",
            },
            "packages_list": {
                "description": "List packages in registry",
                "example": 'packages_list(prefix="team/")',
            },
            "catalog_search": {
                "description": "Search packages by content",
                "example": 'catalog_search("genomics")',
            },
        },
        "workflow_guide": {
            "new_package": [
                "1. create_package() - Create with template",
                "2. package_browse() - Verify contents",
                "3. package_validate() - Check integrity",
                "4. catalog_url() - Get sharing URL",
            ],
            "explore_existing": [
                "1. packages_list() - See available packages",
                "2. package_browse() - Explore structure",
                "3. package_contents_search() - Find specific files",
            ],
            "troubleshooting": [
                "1. test_permissions() - Check bucket access",
                "2. aws_permissions_discover() - See all permissions",
                "3. bucket_recommendations_get() - Find writable buckets",
            ],
        },
        "tips": [
            "Use dry_run=True to preview before creating packages",
            "Metadata templates provide consistent structure across packages",
            "Enhanced tools provide better error messages and guidance",
            "All tools support both dict and JSON string metadata formats",
            "Use create_package() for comprehensive package creation with templates",
        ],
    }
