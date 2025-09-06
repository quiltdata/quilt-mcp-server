"""Unified Package Creation Tool with Smart Workflows.

This module provides a simplified, intelligent package creation interface
that automatically handles registry detection, validation, permissions checking,
and provides helpful guidance throughout the process.

IMPORTANT: This module automatically ensures that README content is always written
as README.md files within packages, never stored in package metadata. Any
'readme_content' or 'readme' fields in metadata will be automatically extracted
and converted to package files.
"""

from typing import Dict, List, Any, Optional, Union
import asyncio
import logging
from pathlib import Path

from ..utils import validate_package_name, format_error_response
from .permissions import bucket_recommendations_get, bucket_access_check
from .s3_package import package_create_from_s3

logger = logging.getLogger(__name__)


def create_package(
    name: str,
    files: List[str],
    description: str = "",
    auto_organize: bool = True,
    dry_run: bool = False,
    target_registry: Optional[str] = None,
    metadata: dict[str, Any] | None = None,
    copy_mode: str = "all",
) -> Dict[str, Any]:
    """
    Unified package creation tool that handles everything automatically.

    This is the main package creation interface that provides intelligent
    defaults, automatic validation, permissions checking, and helpful guidance.

    Args:
        name: Package name in namespace/packagename format
        files: List of S3 URIs, local files, or mixed sources
        description: Package description
        auto_organize: Enable smart folder organization (default: True)
        dry_run: Preview without creating package (default: False)
        target_registry: Target registry (auto-detected if not provided)
        metadata: Additional package metadata

    Returns:
        Comprehensive package creation result with guidance and next steps
    """
    try:
        # Validate package name
        if not validate_package_name(name):
            return _format_validation_error(
                field="name",
                provided=name,
                expected="namespace/packagename format",
                examples=["my-team/data-analysis", "analytics/quarterly-reports"],
                tip="Use lowercase letters, numbers, hyphens, and underscores only",
            )

        # Validate files list
        if not files or not isinstance(files, list):
            return _format_validation_error(
                field="files",
                provided=str(files),
                expected="List of S3 URIs or file paths",
                examples=["s3://my-bucket/data.csv", "/path/to/local/file.txt"],
                tip="Provide at least one file to include in the package",
            )

        # Handle metadata parameter - support both dict and JSON string for user convenience
        processed_metadata = {}
        readme_content = None

        if metadata is not None:
            if isinstance(metadata, str):
                try:
                    import json

                    processed_metadata = json.loads(metadata)
                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "error": "Invalid metadata JSON format",
                        "provided": metadata,
                        "json_error": str(e),
                        "examples": [
                            '{"description": "My dataset", "type": "research"}',
                            '{"tags": ["analysis", "2024"], "author": "scientist"}',
                        ],
                        "tip": "Use proper JSON format with quotes around keys and string values",
                    }
            elif isinstance(metadata, dict):
                processed_metadata = metadata.copy()
            else:
                return {
                    "success": False,
                    "error": "Invalid metadata type",
                    "provided_type": type(metadata).__name__,
                    "expected": "Dictionary object or JSON string",
                    "examples": [
                        '{"description": "My dataset", "version": "1.0"}',
                        '{"tags": ["research", "2024"], "author": "scientist"}',
                    ],
                    "tip": "Pass metadata as a dictionary object or JSON string",
                }

            # Extract README content from metadata and store for later addition as package file
            # readme_content takes priority if both fields exist
            if "readme_content" in processed_metadata:
                readme_content = processed_metadata.pop("readme_content")
            elif "readme" in processed_metadata:
                readme_content = processed_metadata.pop("readme")

            # Remove any remaining README fields to avoid duplication
            if "readme" in processed_metadata:
                processed_metadata.pop("readme")

        # Analyze file sources
        file_analysis = _analyze_file_sources(files)

        if file_analysis["has_errors"]:
            return {
                "status": "error",
                "error": "Invalid file sources detected",
                "file_analysis": file_analysis,
                "suggested_fixes": file_analysis["error_fixes"],
            }

        # Handle different source types
        if file_analysis["source_type"] == "s3_only":
            return _create_package_from_s3_sources(
                name=name,
                s3_files=file_analysis["s3_files"],
                description=description,
                auto_organize=auto_organize,
                dry_run=dry_run,
                target_registry=target_registry,
                metadata=processed_metadata,
                copy_mode=copy_mode,
            )
        elif file_analysis["source_type"] == "local_only":
            return _create_package_from_local_sources(
                name=name,
                local_files=file_analysis["local_files"],
                description=description,
                auto_organize=auto_organize,
                dry_run=dry_run,
                target_registry=target_registry,
                metadata=processed_metadata,
            )
        elif file_analysis["source_type"] == "mixed":
            return _create_package_from_mixed_sources(
                name=name,
                file_analysis=file_analysis,
                description=description,
                auto_organize=auto_organize,
                dry_run=dry_run,
                target_registry=target_registry,
                metadata=processed_metadata,
            )
        else:
            return format_error_response("Unable to determine file source types")

    except Exception as e:
        logger.error(f"Error in unified package creation: {e}")
        return format_error_response(f"Package creation failed: {str(e)}")


def quick_start() -> Dict[str, Any]:
    """Provide guided onboarding and setup assistance.

    Returns:
        Step-by-step setup guide with current status and next actions.
    """
    try:
        # Check current status
        from .auth import auth_status

        auth_result = auth_status()

        # Determine current step based on auth status
        if auth_result.get("status") == "authenticated":
            # User is authenticated, guide them to package creation
            return {
                "status": "ready",
                "current_step": "package_creation",
                "message": "✅ You're authenticated and ready to create packages!",
                "next_actions": [
                    {
                        "action": "Discover your bucket permissions",
                        "command": "aws_permissions_discover()",
                        "description": "See which buckets you can read from and write to",
                    },
                    {
                        "action": "Create your first package",
                        "command": "create_package(name='my-team/first-package', files=['s3://bucket/file.csv'])",
                        "description": "Create a package from S3 data with smart organization",
                    },
                    {
                        "action": "Explore existing packages",
                        "command": "packages_list()",
                        "description": "Browse packages in your catalog",
                    },
                ],
                "tips": [
                    "Use dry_run=True to preview package structure before creating",
                    "The system will automatically suggest the best target bucket",
                    "All packages get auto-generated README.md files",
                ],
            }
        elif auth_result.get("status") == "not_authenticated":
            # User needs to authenticate
            return {
                "status": "setup_needed",
                "current_step": "authentication",
                "message": "Let's get you set up with Quilt!",
                "setup_flow": [
                    {
                        "step": 1,
                        "action": "Configure catalog",
                        "command": "configure_catalog('https://demo.quiltdata.com')",
                        "description": "Connect to Quilt demo catalog",
                        "alternatives": [
                            "switch_catalog('open') for open.quiltdata.com",
                            "configure_catalog('https://your-org.quiltdata.com') for enterprise",
                        ],
                    },
                    {
                        "step": 2,
                        "action": "Login to catalog",
                        "command": "Run: quilt3 login",
                        "description": "Authenticate with your Quilt account (opens browser)",
                        "note": "This step happens outside the MCP - run in terminal",
                    },
                    {
                        "step": 3,
                        "action": "Verify authentication",
                        "command": "auth_status()",
                        "description": "Confirm you're logged in successfully",
                    },
                    {
                        "step": 4,
                        "action": "Check permissions",
                        "command": "aws_permissions_discover()",
                        "description": "Discover your S3 bucket access levels",
                    },
                ],
                "quick_commands": [
                    "configure_catalog('https://demo.quiltdata.com')",
                    "# Then run in terminal: quilt3 login",
                    "auth_status()",
                    "aws_permissions_discover()",
                ],
            }
        else:
            # Error state
            return {
                "status": "error",
                "current_step": "troubleshooting",
                "message": "There's an issue with your Quilt setup",
                "error": auth_result.get("error", "Unknown authentication error"),
                "troubleshooting_steps": [
                    {
                        "issue": "AWS credentials not configured",
                        "check": "Run: aws sts get-caller-identity",
                        "fix": "Configure AWS credentials with: aws configure",
                    },
                    {
                        "issue": "Quilt not installed",
                        "check": "Run: python -c 'import quilt3; print(quilt3.__version__)'",
                        "fix": "Install with: pip install quilt3",
                    },
                    {
                        "issue": "Network connectivity",
                        "check": "Try: curl https://open.quiltdata.com",
                        "fix": "Check your internet connection and firewall settings",
                    },
                ],
                "recovery_actions": [
                    "test_permissions('quilt-example') to test basic connectivity",
                    "configure_catalog('https://open.quiltdata.com') to reset configuration",
                ],
            }

    except Exception as e:
        return {
            "status": "error",
            "error": f"Quick start failed: {e}",
            "fallback_actions": [
                "Try: auth_status() to check authentication",
                "Try: configure_catalog('https://demo.quiltdata.com') to setup catalog",
                "Visit: https://docs.quiltdata.com/ for detailed setup instructions",
            ],
        }


def list_available_resources() -> Dict[str, Any]:
    """Auto-detect user's available buckets and registries.

    Returns:
        Dict with writable buckets, readable buckets, and configured registries.
    """
    try:
        # Use the permissions discovery to get comprehensive bucket information
        from .permissions import aws_permissions_discover

        permissions_result = aws_permissions_discover()

        if not permissions_result.get("success"):
            return {
                "status": "error",
                "error": "Failed to discover available resources",
                "details": permissions_result.get("error", "Unknown error"),
                "suggested_fixes": [
                    "Check your AWS credentials",
                    "Verify network connectivity",
                    "Try: test_permissions('bucket-name') for a specific bucket",
                ],
            }

        categorized = permissions_result.get("categorized_buckets", {})

        # Extract writable and readable buckets
        writable_buckets = []
        readable_buckets = []

        # Full access and read-write buckets are writable
        for bucket_info in categorized.get("full_access", []) + categorized.get("read_write", []):
            writable_buckets.append(
                {
                    "name": bucket_info["name"],
                    "permission_level": bucket_info["permission_level"],
                    "region": bucket_info.get("region", "unknown"),
                    "recommended_for": "package_creation",
                }
            )

        # All accessible buckets are readable
        for category in ["full_access", "read_write", "read_only", "list_only"]:
            for bucket_info in categorized.get(category, []):
                readable_buckets.append(
                    {
                        "name": bucket_info["name"],
                        "permission_level": bucket_info["permission_level"],
                        "region": bucket_info.get("region", "unknown"),
                        "can_read_files": bucket_info.get("can_read", False),
                    }
                )

        # Get catalog information
        from .auth import catalog_info

        catalog_result = catalog_info()
        registries = []
        if catalog_result.get("status") == "success":
            registries.append(
                {
                    "name": catalog_result.get("catalog_name", "current"),
                    "url": catalog_result.get("catalog_url", "unknown"),
                    "authenticated": catalog_result.get("is_authenticated", False),
                }
            )

        return {
            "status": "success",
            "writable_buckets": writable_buckets,
            "readable_buckets": readable_buckets,
            "registries": registries,
            "summary": {
                "total_writable": len(writable_buckets),
                "total_readable": len(readable_buckets),
                "total_registries": len(registries),
            },
            "recommendations": {
                "package_creation": [bucket["name"] for bucket in writable_buckets[:3]],
                "data_exploration": [bucket["name"] for bucket in readable_buckets[:5]],
            },
            "next_steps": [
                "Create packages in any writable bucket",
                "Explore data in readable buckets",
                "Use create_package() for intelligent package creation",
            ],
        }

    except Exception as e:
        logger.error(f"Error listing available resources: {e}")
        return format_error_response(f"Failed to list resources: {str(e)}")


def _format_validation_error(
    field: str, provided: str, expected: str, examples: List[str], tip: str
) -> Dict[str, Any]:
    """Format a helpful validation error message."""
    return {
        "status": "error",
        "error": f"Invalid {field} format",
        "provided": provided,
        "expected": expected,
        "examples": examples,
        "tip": tip,
        "help": f"The {field} parameter should be: {expected}",
        "fix": f"Try one of these examples: {', '.join(examples[:2])}",
    }


def _analyze_file_sources(files: List[str]) -> Dict[str, Any]:
    """Analyze file sources to determine handling strategy."""
    s3_files = []
    local_files = []
    errors = []
    error_fixes = []

    for file_path in files:
        if file_path.startswith("s3://"):
            # S3 URI
            if "/" not in file_path[5:] or file_path.endswith("/"):
                errors.append(f"Invalid S3 URI: {file_path}")
                error_fixes.append("S3 URI must include object key: s3://bucket/path/file.ext")
            else:
                s3_files.append(file_path)
        else:
            # Assume local file
            local_files.append(file_path)

    # Determine source type
    if s3_files and not local_files:
        source_type = "s3_only"
    elif local_files and not s3_files:
        source_type = "local_only"
    elif s3_files and local_files:
        source_type = "mixed"
    else:
        source_type = "unknown"

    return {
        "source_type": source_type,
        "s3_files": s3_files,
        "local_files": local_files,
        "has_errors": bool(errors),
        "errors": errors,
        "error_fixes": error_fixes,
        "total_files": len(files),
        "s3_count": len(s3_files),
        "local_count": len(local_files),
    }


def _create_package_from_s3_sources(
    name: str,
    s3_files: List[str],
    description: str,
    auto_organize: bool,
    dry_run: bool,
    target_registry: Optional[str],
    metadata: Optional[Dict[str, Any]],
    copy_mode: str,
) -> Dict[str, Any]:
    """Create package from S3 sources using enhanced S3-to-package tool."""
    try:
        # Extract source bucket and prefix from first S3 file
        first_s3_uri = s3_files[0]
        without_scheme = first_s3_uri[5:]  # Remove s3://
        source_bucket, first_key = without_scheme.split("/", 1)

        # Try to find common prefix
        source_prefix = ""
        if len(s3_files) > 1:
            # Find common prefix among all files
            all_keys = [uri[5:].split("/", 1)[1] for uri in s3_files]
            common_prefix = _find_common_prefix(all_keys)
            if common_prefix:
                source_prefix = common_prefix

        # Use the enhanced S3-to-package creation tool
        result = package_create_from_s3(
            source_bucket=source_bucket,
            package_name=name,
            source_prefix=source_prefix,
            target_registry=target_registry,
            description=description,
            auto_organize=auto_organize,
            dry_run=dry_run,
            metadata=metadata,
            copy_mode=copy_mode,
        )

        # Enhance the result with unified package creation context
        if result.get("success"):
            result.update(
                {
                    "creation_method": "s3_sources",
                    "source_analysis": {
                        "source_bucket": source_bucket,
                        "source_prefix": source_prefix,
                        "total_files": len(s3_files),
                    },
                    "user_guidance": _generate_success_guidance(result, "s3"),
                }
            )

        return result

    except Exception as e:
        logger.error(f"Error creating package from S3 sources: {e}")
        return format_error_response(f"S3 package creation failed: {str(e)}")


def _create_package_from_local_sources(
    name: str,
    local_files: List[str],
    description: str,
    auto_organize: bool,
    dry_run: bool,
    target_registry: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create package from local file sources."""
    # This would be implemented to handle local files
    # For now, return guidance to use S3 sources
    return {
        "status": "not_implemented",
        "message": "Local file package creation not yet implemented",
        "alternative": "Upload files to S3 first, then use S3 URIs",
        "suggested_workflow": [
            "1. Upload files to S3 using: bucket_objects_put()",
            "2. Create package using S3 URIs with: create_package()",
            "3. Or use existing S3 data with: package_create_from_s3()",
        ],
        "help": "Contact support for local file package creation assistance",
    }


def _create_package_from_mixed_sources(
    name: str,
    file_analysis: Dict[str, Any],
    description: str,
    auto_organize: bool,
    dry_run: bool,
    target_registry: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create package from mixed local and S3 sources."""
    return {
        "status": "not_implemented",
        "message": "Mixed source package creation not yet implemented",
        "file_analysis": file_analysis,
        "suggested_approach": [
            "Create separate packages for S3 and local sources",
            "Or upload local files to S3 first, then create unified package",
        ],
        "help": "Use create_package() with either all S3 URIs or all local files",
    }


def _find_common_prefix(keys: List[str]) -> str:
    """Find common prefix among a list of S3 keys."""
    if not keys:
        return ""

    if len(keys) == 1:
        # For single file, use directory path as prefix
        return str(Path(keys[0]).parent) + "/" if "/" in keys[0] else ""

    # Find common prefix
    common = keys[0]
    for key in keys[1:]:
        while not key.startswith(common):
            common = common[:-1]
            if not common:
                break

    # Ensure prefix ends at folder boundary
    if common and "/" in common:
        common = common[: common.rfind("/") + 1]

    return common


def _generate_success_guidance(result: Dict[str, Any], creation_method: str) -> List[str]:
    """Generate helpful guidance after successful package creation."""
    guidance = []

    package_name = result.get("package_name", "your-package")
    registry = result.get("registry", "your-registry")

    guidance.extend(
        [
            f"✅ Package '{package_name}' created successfully!",
            f"📍 Location: {registry}",
            f"🔍 Explore with: package_browse('{package_name}')",
            f"📊 View contents with: package_contents_search('{package_name}', 'search-term')",
        ]
    )

    if creation_method == "s3":
        guidance.append("📁 Files organized automatically with smart folder structure")
        guidance.append("📝 README.md generated with usage examples")

    return guidance
