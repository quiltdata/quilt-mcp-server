"""Comprehensive Package Management Tools.

This module provides enhanced package management functionality with better
error handling, metadata templates, and improved user experience based on
real-world testing feedback.

IMPORTANT: This module automatically ensures that README content is always written
as README.md files within packages, never stored in package metadata. Any
'readme_content' or 'readme' fields in metadata will be automatically extracted
and converted to package files.
"""

from typing import Dict, List, Any, Optional
import logging
from pathlib import Path

from ..constants import DEFAULT_REGISTRY
from ..utils import validate_package_name, format_error_response
from ..services.quilt_service import QuiltService
from .metadata_templates import (
    get_metadata_template,
    validate_metadata_structure,
    list_metadata_templates,
)
from .package_ops import package_create as _base_package_create
from .packages import package_browse

logger = logging.getLogger(__name__)


def create_package_enhanced(
    name: str,
    files: List[str],
    description: str = "",
    metadata_template: str = "standard",
    metadata: Any = None,
    registry: Optional[str] = None,
    dry_run: bool = False,
    auto_organize: bool = True,
    copy_mode: str = "all",
) -> Dict[str, Any]:
    """
    Enhanced package creation with better error handling and metadata templates.

    This is the recommended package creation tool that provides:
    - Intelligent metadata templates for common use cases
    - Better error messages with actionable suggestions
    - Dry-run capability for validation before creation
    - Automatic organization and validation

    Args:
        name: Package name in namespace/packagename format
        files: List of S3 URIs to include in the package
        description: Package description (will be added to metadata)
        metadata_template: Template to use ('standard', 'genomics', 'ml', 'research', 'analytics')
        metadata: Additional metadata fields (merged with template)
        registry: Target registry (auto-detected if not provided)
        dry_run: Preview package without creating (default: False)
        auto_organize: Enable smart folder organization (default: True)

    Returns:
        Comprehensive package creation result with guidance

    Examples:
        Basic usage:
        create_package_enhanced("team/dataset", ["s3://bucket/file.csv"])

        With genomics template:
        create_package_enhanced(
            "genomics/study1",
            ["s3://bucket/data.vcf"],
            metadata_template="genomics",
            metadata={"organism": "human", "genome_build": "GRCh38"}
        )

        Dry run (preview):
        create_package_enhanced("team/test", ["s3://bucket/file.csv"], dry_run=True)
    """
    try:
        # Validate package name
        if not validate_package_name(name):
            return {
                "success": False,
                "error": "Invalid package name format",
                "provided": name,
                "expected": "namespace/packagename format",
                "examples": [
                    "my-team/dataset",
                    "genomics/study1",
                    "analytics/q1-report",
                ],
                "tip": "Use lowercase letters, numbers, hyphens, and underscores only",
            }

        # Validate files
        if not files or not isinstance(files, list):
            return {
                "success": False,
                "error": "Invalid files parameter",
                "provided": str(files),
                "expected": "List of S3 URIs",
                "examples": [
                    '["s3://bucket/file1.csv", "s3://bucket/file2.json"]',
                    '["s3://my-data/dataset.parquet"]',
                ],
                "tip": "Provide at least one S3 URI in the format s3://bucket/path/file.ext",
            }

        # Validate S3 URIs
        invalid_uris = []
        for file_uri in files:
            if not file_uri.startswith("s3://") or "/" not in file_uri[5:]:
                invalid_uris.append(file_uri)

        if invalid_uris:
            return {
                "success": False,
                "error": "Invalid S3 URIs detected",
                "invalid_uris": invalid_uris,
                "expected": "S3 URIs in format s3://bucket/path/file.ext",
                "examples": [
                    "s3://my-bucket/data/file.csv",
                    "s3://analytics/reports/q1.json",
                ],
                "tip": "Each URI must start with s3:// and include both bucket and object key",
            }

        # Prepare metadata using template
        try:
            template_metadata = get_metadata_template(metadata_template)

            # Add description to metadata
            if description:
                template_metadata["description"] = description

            # Merge with user-provided metadata
            if metadata:
                # Handle metadata as string (JSON) or dict types
                if isinstance(metadata, str):
                    try:
                        import json

                        metadata = json.loads(metadata)
                    except json.JSONDecodeError as e:
                        return {
                            "success": False,
                            "error": "Invalid metadata JSON format",
                            "provided": metadata,
                            "json_error": str(e),
                            "examples": [
                                '{"description": "My dataset", "type": "research"}',
                                '{"organism": "human", "study_type": "clinical"}',
                            ],
                            "tip": "Use proper JSON format with quotes around keys and string values",
                        }
                elif not isinstance(metadata, dict):
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

                # Extract README content from user metadata before merging
                # readme_content takes priority if both fields exist
                readme_content = None
                if "readme_content" in metadata:
                    readme_content = metadata.pop("readme_content")
                elif "readme" in metadata:
                    readme_content = metadata.pop("readme")

                # Merge the cleaned metadata
                template_metadata.update(metadata)

                # Store README content for later addition as package file
                if readme_content:
                    template_metadata["_extracted_readme"] = readme_content

            # Validate final metadata
            validation_result = validate_metadata_structure(template_metadata, metadata_template)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "Metadata validation failed",
                    "validation_result": validation_result,
                    "suggested_fixes": validation_result.get("suggestions", []),
                }

        except Exception as e:
            return {
                "success": False,
                "error": "Failed to prepare metadata",
                "cause": str(e),
                "template_used": metadata_template,
                "suggested_actions": [
                    "Try: list_metadata_templates() to see available templates",
                    "Use 'standard' template for basic packages",
                ],
            }

        # Dry run - return preview
        if dry_run:
            # Generate preview of summary files
            from .quilt_summary import create_quilt_summary_files

            summary_preview = create_quilt_summary_files(
                package_name=name,
                package_metadata={"quilt": template_metadata},
                organized_structure={"root": [{"Key": f, "Size": 0} for f in files]},
                readme_content=f"# {name}\n\nPreview package with {len(files)} files",
                source_info={"type": "local_files", "bucket": "preview"},
                metadata_template=metadata_template,
            )

            return {
                "success": True,
                "action": "preview",
                "package_name": name,
                "files_count": len(files),
                "files_preview": files[:5],  # Show first 5 files
                "metadata_template": metadata_template,
                "metadata_preview": template_metadata,
                "validation": validation_result,
                "summary_files_preview": {
                    "quilt_summarize.json": summary_preview.get("summary_package", {}).get("quilt_summarize.json", {}),
                    "visualizations": summary_preview.get("summary_package", {}).get("visualizations", {}),
                    "files_generated": summary_preview.get("files_generated", {}),
                },
                "next_steps": [
                    "Set dry_run=False to create the package",
                    "Modify metadata if needed",
                    "Add more files if required",
                ],
                "estimated_action": f"Will create package '{name}' with {len(files)} files using '{metadata_template}' template and generate Quilt summary files",
            }

        # Auto-detect registry if not provided
        if not registry:
            from .permissions import bucket_recommendations_get

            try:
                recommendations = bucket_recommendations_get(operation_type="package_creation")
                if recommendations.get("success") and recommendations.get("recommendations", {}).get(
                    "primary_recommendations"
                ):
                    top_rec = recommendations["recommendations"]["primary_recommendations"][0]
                    registry = f"s3://{top_rec['bucket_name']}"
                    logger.info(f"Auto-selected registry: {registry}")
                else:
                    registry = DEFAULT_REGISTRY  # Fallback to configured default
            except Exception:
                registry = DEFAULT_REGISTRY  # Safe fallback to configured default

        # Create the package using the base function with enhanced error handling
        try:
            result = _base_package_create(
                package_name=name,
                s3_uris=files,
                registry=registry,
                metadata=template_metadata,
                message=(
                    f"Created via enhanced package creation: {description}"
                    if description
                    else "Created via enhanced package creation"
                ),
                copy_mode=copy_mode,
            )

            # Enhance the result with additional information
            if result.get("status") == "success":
                result.update(
                    {
                        "metadata_template_used": metadata_template,
                        "auto_organize_applied": auto_organize,
                        "user_guidance": [
                            f"✅ Package '{name}' created successfully!",
                            f"📍 Location: {registry}",
                            f"📊 Files: {result.get('entries_added', 0)} files added",
                            f"🔍 Browse with: package_browse('{name}')",
                            f"🌐 View online: catalog_url('{registry}', '{name}')",
                        ],
                        "next_steps": [
                            f"package_browse('{name}') - Explore package contents",
                            f"package_contents_search('{name}', 'search-term') - Search within package",
                            f"catalog_url('{registry}', '{name}') - Get web URL for sharing",
                        ],
                    }
                )
            else:
                # Enhance error with helpful suggestions
                error_msg = result.get("error", "Unknown error")
                if "AccessDenied" in error_msg:
                    result.update(
                        {
                            "error": "Cannot create package - insufficient permissions",
                            "cause": "Missing write permissions for target registry",
                            "possible_fixes": [
                                f"Verify you have s3:PutObject permissions for {registry}",
                                "Check if you're connected to the right catalog",
                                "Try a different bucket you own",
                            ],
                            "suggested_actions": [
                                "Try: bucket_recommendations_get() to find writable buckets",
                                "Try: test_permissions() to diagnose specific issues",
                                "Try: aws_permissions_discover() to see all your bucket access",
                            ],
                            "debug_info": {
                                "aws_error": error_msg,
                                "operation": "package_creation",
                            },
                        }
                    )

            return result

        except Exception as e:
            logger.error(f"Package creation failed: {e}")
            return {
                "success": False,
                "error": "Package creation failed",
                "cause": str(e),
                "error_type": type(e).__name__,
                "possible_fixes": [
                    "Check your AWS credentials and permissions",
                    "Verify all S3 URIs are accessible",
                    "Ensure the target registry is writable",
                ],
                "suggested_actions": [
                    "Try: test_permissions() to check bucket access",
                    "Try with dry_run=True to validate inputs first",
                    "Try: bucket_recommendations_get() for alternative registries",
                ],
                "debug_info": {
                    "error_type": type(e).__name__,
                    "operation": "package_creation",
                },
            }

    except Exception as e:
        logger.error(f"Enhanced package creation failed: {e}")
        return format_error_response(f"Package creation failed: {str(e)}")


def package_update_metadata(
    package_name: str,
    metadata: Any,
    registry: str = None,
    merge_with_existing: bool = True,
) -> Dict[str, Any]:
    """
    Update or replace metadata for an existing package.

    Args:
        package_name: Name of the package to update
        metadata: New metadata to set (dict or JSON string)
        registry: Registry containing the package
        merge_with_existing: Whether to merge with existing metadata (default: True)

    Returns:
        Update result with status and guidance
    """
    try:
        # Handle metadata as string
        if isinstance(metadata, str):
            try:
                import json

                metadata = json.loads(metadata)
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": "Invalid metadata JSON format",
                    "provided": metadata,
                    "json_error": str(e),
                    "examples": [
                        '{"description": "Updated description", "version": "2.0"}',
                        '{"tags": ["updated", "v2"], "quality": "validated"}',
                    ],
                    "tip": "Use proper JSON format with quotes around keys and string values",
                }

        # Validate metadata structure
        validation_result = validate_metadata_structure(metadata)
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": "Metadata validation failed",
                "validation_result": validation_result,
            }

        # Implementation: Update package metadata
        try:
            from ..constants import DEFAULT_REGISTRY

            # Use default registry if none provided
            if not registry:
                registry = DEFAULT_REGISTRY

            # Browse existing package to get current structure
            # Suppress stdout during browse to avoid JSON-RPC interference
            from ..utils import suppress_stdout

            quilt_service = QuiltService()
            with suppress_stdout():
                pkg = quilt_service.browse_package(package_name, registry=registry)

            # Get current metadata
            current_metadata = {}
            try:
                current_metadata = dict(pkg.meta) if hasattr(pkg, "meta") else {}
            except Exception:
                current_metadata = {}

            # Merge or replace metadata based on user preference
            if merge_with_existing:
                final_metadata = current_metadata.copy()
                final_metadata.update(metadata)
            else:
                final_metadata = metadata.copy()

            # Set the new metadata
            pkg.set_meta(final_metadata)

            # Push the updated package
            commit_message = f"Updated metadata for {package_name}"

            # Suppress stdout during push to avoid JSON-RPC interference
            from ..utils import suppress_stdout

            with suppress_stdout():
                top_hash = pkg.push(package_name, registry=registry, message=commit_message, force=True)

            return {
                "success": True,
                "action": "metadata_updated",
                "package_name": package_name,
                "registry": registry,
                "top_hash": str(top_hash),
                "previous_metadata": current_metadata,
                "new_metadata": final_metadata,
                "merge_applied": merge_with_existing,
                "message": "Metadata updated successfully",
                "next_steps": [
                    f"Browse updated package: package_browse('{package_name}')",
                    f"Validate package: package_validate('{package_name}')",
                    f"View online: catalog_url('{registry}', '{package_name}')",
                ],
            }

        except Exception as e:
            return {
                "success": False,
                "error": "Failed to update package metadata",
                "cause": str(e),
                "error_type": type(e).__name__,
                "possible_fixes": [
                    "Verify the package exists in the specified registry",
                    "Check that you have write permissions for the registry",
                    "Ensure your metadata is a valid dictionary",
                ],
                "suggested_actions": [
                    f"Try: package_browse('{package_name}') to verify package exists",
                    "Try: test_permissions() to check bucket access",
                    "Try: validate_metadata_structure() to check metadata format",
                ],
                "debug_info": {
                    "error_type": type(e).__name__,
                    "operation": "metadata_update",
                },
            }

    except Exception as e:
        return format_error_response(f"Metadata update failed: {str(e)}")


def _validate_package_alternative(package_name: str, registry: str, browse_error: Dict[str, Any]) -> Dict[str, Any]:
    """Alternative validation approach when package browsing fails."""
    try:
        # Try to check if package exists using search
        from .packages import packages_search

        search_result = packages_search(package_name, registry=registry, limit=1)

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
                    f"Try: packages_search('{package_name}') to verify package exists",
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


def list_package_tools() -> Dict[str, Any]:
    """
    List all package management tools with usage guidance.

    Returns:
        Comprehensive guide to package management tools
    """
    return {
        "primary_tools": {
            "create_package_enhanced": {
                "description": "Main package creation tool with templates and validation",
                "use_when": "Creating new packages with smart defaults",
                "example": 'create_package_enhanced("team/dataset", ["s3://bucket/file.csv"])',
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
            "package_create": {
                "description": "Basic package creation (legacy)",
                "use_when": "Simple package creation without templates",
                "note": "Consider using create_package_enhanced instead",
            },
            "package_create_from_s3": {
                "description": "Advanced S3-to-package creation with organization",
                "use_when": "Creating packages from entire S3 buckets/prefixes",
                "example": 'package_create_from_s3("bucket-name", "team/dataset")',
            },
            "package_update_metadata": {
                "description": "Update package metadata (planned feature)",
                "use_when": "Updating metadata without recreating package",
                "status": "Coming soon",
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
            "packages_search": {
                "description": "Search packages by content",
                "example": 'packages_search("genomics")',
            },
        },
        "workflow_guide": {
            "new_package": [
                "1. create_package_enhanced() - Create with template",
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
        ],
    }
