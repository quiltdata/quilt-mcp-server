"""Package creation workflows and utilities.

This module consolidates all package creation functionality, providing:
- Base package creation from S3 URIs
- S3-to-package bulk processing with smart organization
- Unified creation interface with metadata templates
- Package deletion

All creation logic is centralized here to eliminate circular dependencies
and provide clear separation from read operations (in packages.py).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from ..constants import DEFAULT_REGISTRY
from ..services.quilt_service import QuiltService
from ..utils import (
    get_s3_client,
    validate_package_name,
    format_error_response,
    generate_signed_url,
    suppress_stdout,
)
from .permissions import bucket_recommendations_get, bucket_access_check
from .metadata_templates import metadata_template_get, metadata_validate_structure

logger = logging.getLogger(__name__)

# Constants for dry-run preview generation
PLACEHOLDER_FILE_SIZE = 1024
DEFAULT_PREVIEW_SIZE_LIMIT = 500

# Smart Organization and Template System
FOLDER_MAPPING = {
    # Data files
    "csv": "data/processed",
    "tsv": "data/processed",
    "parquet": "data/processed",
    "json": "data/processed",
    "xml": "data/processed",
    "jsonl": "data/processed",
    # Raw data
    "log": "data/raw",
    "txt": "data/raw",
    "raw": "data/raw",
    # Documentation
    "md": "docs",
    "rst": "docs",
    "pdf": "docs",
    "docx": "docs",
    # Schema and config
    "schema": "docs/schemas",
    "yml": "metadata",
    "yaml": "metadata",
    "toml": "metadata",
    "ini": "metadata",
    "conf": "metadata",
    # Media
    "png": "data/media",
    "jpg": "data/media",
    "jpeg": "data/media",
    "mp4": "data/media",
    "avi": "data/media",
}

REGISTRY_PATTERNS = {
    "ml": ["model", "training", "ml", "ai", "neural", "tensorflow", "pytorch"],
    "analytics": ["analytics", "reports", "metrics", "dashboard", "bi"],
    "data": ["data", "dataset", "warehouse", "lake"],
    "research": ["research", "experiment", "study", "analysis"],
}


def _normalize_registry(bucket_or_uri: str) -> str:
    """Normalize registry input to s3:// URI format."""
    if bucket_or_uri.startswith("s3://"):
        return bucket_or_uri
    return f"s3://{bucket_or_uri}"


# ============================================================================
# BASE PACKAGE CREATION
# ============================================================================


def _base_package_create(
    package_name: str,
    s3_uris: list[str],
    registry: str = DEFAULT_REGISTRY,
    metadata: dict[str, Any] | None = None,
    message: str = "Created via create_package tool",
    flatten: bool = True,
    copy_mode: str = "all",
) -> dict[str, Any]:
    """Create a new Quilt package from S3 objects.

    This is the foundational package creation function used by higher-level interfaces.
    """
    if metadata is None:
        metadata = {}
    elif isinstance(metadata, str):
        try:
            import json

            metadata = json.loads(metadata)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": "Invalid metadata format",
                "provided": metadata,
                "expected": "Valid JSON object or Python dict",
                "json_error": str(e),
            }
    elif not isinstance(metadata, dict):
        return {
            "success": False,
            "error": "Invalid metadata type",
            "provided_type": type(metadata).__name__,
            "expected": "Dictionary object or JSON string",
        }

    warnings: list[str] = []
    if not s3_uris:
        return {"error": "No S3 URIs provided"}
    if not package_name:
        return {"error": "Package name is required"}

    # Process metadata to ensure README content is handled correctly
    processed_metadata = metadata.copy() if metadata else {}

    # Extract README content from metadata
    if "readme_content" in processed_metadata:
        processed_metadata.pop("readme_content")
        warnings.append("README content moved from metadata to package file (README.md)")
    elif "readme" in processed_metadata:
        processed_metadata.pop("readme")
        warnings.append("README content moved from metadata to package file (README.md)")

    # Remove any remaining README fields to avoid duplication
    if "readme" in processed_metadata:
        processed_metadata.pop("readme")
        warnings.append("Removed duplicate 'readme' field from metadata")

    normalized_registry = _normalize_registry(registry)

    try:
        quilt_service = QuiltService()
        result = quilt_service.create_package_revision(
            package_name=package_name,
            s3_uris=s3_uris,
            metadata=processed_metadata,
            registry=normalized_registry,
            message=message,
            auto_organize=False,  # Preserve flattening behavior
            copy=copy_mode,
        )

        if result.get("error"):
            return {
                "error": result["error"],
                "package_name": package_name,
                "warnings": warnings,
            }

        top_hash = result.get("top_hash")
        entries_added = result.get("entries_added", len(s3_uris))

    except Exception as e:
        return {
            "error": f"Failed to create package: {e}",
            "package_name": package_name,
            "warnings": warnings,
        }

    return {
        "status": "success",
        "action": "created",
        "package_name": str(package_name),
        "registry": str(registry),
        "top_hash": str(top_hash),
        "entries_added": entries_added,
        "files": result.get("files", []),
        "metadata_provided": bool(metadata),
        "warnings": warnings,
        "message": str(message),
    }


def package_delete(package_name: str, registry: str = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Delete a Quilt package from the registry."""
    if not package_name:
        return {"error": "package_name is required for package deletion"}

    try:
        normalized_registry = _normalize_registry(registry)
        quilt_service = QuiltService()

        with suppress_stdout():
            quilt_service.delete_package(package_name, normalized_registry)

        return {
            "status": "success",
            "action": "deleted",
            "package_name": package_name,
            "registry": registry,
            "message": f"Package {package_name} deleted successfully",
        }
    except Exception as e:
        return {
            "error": f"Failed to delete package '{package_name}': {e}",
            "package_name": package_name,
            "registry": registry,
        }


# ============================================================================
# S3-TO-PACKAGE CREATION WITH SMART ORGANIZATION
# ============================================================================


def _suggest_target_registry(source_bucket: str, source_prefix: str) -> str:
    """Suggest appropriate target registry based on source patterns."""
    source_text = f"{source_bucket} {source_prefix}".lower()

    for registry_type, patterns in REGISTRY_PATTERNS.items():
        if any(pattern in source_text for pattern in patterns):
            return f"s3://{registry_type}-packages"

    return "s3://data-packages"


def _organize_file_structure(objects: List[Dict[str, Any]], auto_organize: bool) -> Dict[str, List[Dict[str, Any]]]:
    """Organize files into logical folder structure."""
    if not auto_organize:
        return {"": objects}

    organized = {}

    for obj in objects:
        key = obj["Key"]
        file_ext = Path(key).suffix.lower().lstrip(".")

        # Determine target folder
        target_folder = FOLDER_MAPPING.get(file_ext, "data/misc")

        # Special handling for specific patterns
        if "readme" in key.lower() or "documentation" in key.lower():
            target_folder = "docs"
        elif "schema" in key.lower() or "definition" in key.lower():
            target_folder = "docs/schemas"
        elif "config" in key.lower() or "settings" in key.lower():
            target_folder = "metadata"

        if target_folder not in organized:
            organized[target_folder] = []

        organized[target_folder].append(obj)

    return organized


def _generate_readme_content(
    package_name: str,
    description: str,
    organized_structure: Dict[str, List[Dict[str, Any]]],
    total_size: int,
    source_info: Dict[str, str],
    metadata_template: str,
) -> str:
    """Generate comprehensive README.md content."""
    namespace, name = package_name.split("/")

    total_files = sum(len(files) for files in organized_structure.values())
    total_size_mb = total_size / (1024 * 1024)

    file_types = set()
    for files in organized_structure.values():
        for file_info in files:
            ext = Path(file_info["Key"]).suffix.lower().lstrip(".")
            if ext:
                file_types.add(ext)

    readme_content = f"""# {package_name}

## Overview
{description or f"This package contains data sourced from {source_info.get('source_description', 'S3 bucket')}."}

## Contents

This package is organized into the following structure:

"""

    # Add folder structure
    for folder, files in organized_structure.items():
        if folder:
            readme_content += f"### `{folder}/` ({len(files)} files)\n"
            if folder == "data/processed":
                readme_content += "Cleaned and processed data files ready for analysis.\n\n"
            elif folder == "data/raw":
                readme_content += "Original source data in raw format.\n\n"
            elif folder == "docs":
                readme_content += "Documentation, schemas, and supplementary materials.\n\n"
            elif folder == "metadata":
                readme_content += "Configuration files and package metadata.\n\n"
            else:
                readme_content += f"Files organized in {folder}.\n\n"

    # Add file summary table
    readme_content += """## File Summary

| Folder | File Count | Primary Types |
|--------|------------|---------------|
"""

    for folder, files in organized_structure.items():
        if files:
            folder_types = set()
            for f in files[:5]:
                ext = Path(f["Key"]).suffix.lower().lstrip(".")
                if ext:
                    folder_types.add(ext)
            types_str = ", ".join(sorted(folder_types))
            readme_content += f"| `{folder or 'root'}/` | {len(files)} | {types_str} |\n"

    # Add usage section
    readme_content += f"""
## Usage

```python
# Browse the package using Quilt
# pkg = Package.browse("{package_name}")

# Access specific data files
"""

    for folder, files in organized_structure.items():
        if files and folder:
            example_file = files[0]["Key"]
            logical_path = f"{folder}/{Path(example_file).name}"
            readme_content += f"""
# Access files in {folder}/
data = pkg["{logical_path}"]()
"""

    readme_content += """```

## Package Metadata

"""

    readme_content += f"""- **Created**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
- **Source**: {source_info.get('bucket', 'Unknown')}
- **Total Size**: {total_size_mb:.1f} MB
- **File Count**: {total_files}
- **File Types**: {', '.join(sorted(file_types))}
- **Organization**: Smart folder structure applied
"""

    if metadata_template == "ml":
        readme_content += """
## ML Model Information

This package appears to contain machine learning related data. Key considerations:

- **Training Data**: Located in `data/processed/`
- **Models**: Check for model files in appropriate folders
- **Documentation**: Review `docs/` for model specifications and methodology
"""
    elif metadata_template == "analytics":
        readme_content += """
## Analytics Information

This package contains analytics data. Key features:

- **Processed Data**: Analysis-ready data in `data/processed/`
- **Reports**: Documentation and analysis reports in `docs/`
- **Metrics**: Configuration and metadata in `metadata/`
"""

    readme_content += """
## Data Quality

- ✅ Files organized into logical structure
- ✅ Comprehensive metadata included
- ✅ Source attribution maintained
- ✅ Documentation generated

## Support

For questions about this package, refer to the metadata or contact the package maintainer.
"""

    return readme_content


def _generate_package_metadata(
    package_name: str,
    source_info: Dict[str, Any],
    organized_structure: Dict[str, List[Dict[str, Any]]],
    metadata_template: str,
    user_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate comprehensive package metadata following Quilt standards."""
    total_objects = sum(len(files) for files in organized_structure.values())
    total_size = sum(sum(obj.get("Size", 0) for obj in files) for files in organized_structure.values())

    file_types = set()
    for files in organized_structure.values():
        for obj in files:
            ext = Path(obj["Key"]).suffix.lower().lstrip(".")
            if ext:
                file_types.add(ext)

    metadata = {
        "quilt": {
            "created_by": "mcp-s3-package-tool-enhanced",
            "creation_date": datetime.now(timezone.utc).isoformat() + "Z",
            "package_version": "1.0.0",
            "source": {
                "type": "s3_bucket",
                "bucket": source_info.get("bucket"),
                "prefix": source_info.get("prefix", ""),
                "total_objects": total_objects,
                "total_size_bytes": total_size,
            },
            "organization": {
                "structure_type": "logical_hierarchy",
                "auto_organized": True,
                "folder_mapping": {
                    folder: f"Contains {len(files)} files" for folder, files in organized_structure.items() if files
                },
            },
            "data_profile": {
                "file_types": sorted(list(file_types)),
                "total_files": total_objects,
                "size_mb": round(total_size / (1024 * 1024), 2),
            },
        }
    }

    if metadata_template == "ml":
        metadata["ml"] = {
            "type": "machine_learning",
            "data_stage": "processed",
            "model_ready": True,
        }
    elif metadata_template == "analytics":
        metadata["analytics"] = {
            "type": "business_analytics",
            "analysis_ready": True,
            "report_generated": True,
        }

    if user_metadata:
        metadata["user_metadata"] = user_metadata

    return metadata


def _validate_bucket_access(s3_client, bucket_name: str) -> None:
    """Validate that the user has access to the source bucket."""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "404":
            raise ValueError(f"Bucket {bucket_name} does not exist or you don't have access")
        elif error_code == "403":
            raise ValueError(f"Access denied to bucket {bucket_name}")
        else:
            raise


def _discover_s3_objects(
    s3_client,
    bucket: str,
    prefix: str,
    include_patterns: Optional[List[str]],
    exclude_patterns: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Discover and filter S3 objects based on patterns."""
    objects = []

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

        for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    if _should_include_object(obj["Key"], include_patterns, exclude_patterns):
                        objects.append(obj)
    except ClientError as e:
        logger.error(f"Error listing objects in bucket {bucket}: {str(e)}")
        raise

    return objects


def _should_include_object(
    key: str,
    include_patterns: Optional[List[str]],
    exclude_patterns: Optional[List[str]],
) -> bool:
    """Determine if an object should be included based on patterns."""
    import fnmatch

    if exclude_patterns:
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(key, pattern):
                return False

    if include_patterns:
        for pattern in include_patterns:
            if fnmatch.fnmatch(key, pattern):
                return True
        return False

    return True


def _create_enhanced_package(
    s3_client,
    organized_structure: Dict[str, List[Dict[str, Any]]],
    source_bucket: str,
    package_name: str,
    target_registry: str,
    description: str,
    enhanced_metadata: Dict[str, Any],
    readme_content: Optional[str] = None,
    summary_files: Optional[Dict[str, Any]] = None,
    copy_mode: str = "all",
    force: bool = False,
) -> Dict[str, Any]:
    """Create the enhanced Quilt package with organized structure and documentation."""
    try:
        # Collect all S3 URIs from organized structure
        s3_uris = []
        for folder, objects in organized_structure.items():
            for obj in objects:
                source_key = obj["Key"]
                s3_uri = f"s3://{source_bucket}/{source_key}"
                s3_uris.append(s3_uri)
                logger.debug(f"Collected S3 URI: {s3_uri}")

        processed_metadata = enhanced_metadata.copy()

        if readme_content:
            processed_metadata["readme_content"] = readme_content
            logger.info("Added README content to metadata for processing")

        message = (
            f"Created via enhanced S3-to-package tool: {description}"
            if description
            else "Created via enhanced S3-to-package tool"
        )

        quilt_service = QuiltService()
        result = quilt_service.create_package_revision(
            package_name=package_name,
            s3_uris=s3_uris,
            metadata=processed_metadata,
            registry=target_registry,
            message=message,
            auto_organize=True,
            copy=copy_mode,
        )

        if result.get("error"):
            logger.error(f"Package creation failed: {result['error']}")
            raise Exception(result["error"])

        top_hash = result.get("top_hash")
        logger.info(f"Successfully created package {package_name} with hash {top_hash}")

        if summary_files:
            logger.warning("Summary files and visualizations not yet supported with create_package_revision")

        return {
            "top_hash": top_hash,
            "message": f"Enhanced package {package_name} created successfully",
            "registry": target_registry,
        }

    except Exception as e:
        logger.error(f"Error creating enhanced package: {str(e)}")
        raise


def package_create_from_s3(
    source_bucket: str,
    package_name: str,
    source_prefix: str = "",
    target_registry: Optional[str] = None,
    description: str = "",
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    auto_organize: bool = True,
    generate_readme: bool = True,
    confirm_structure: bool = True,
    metadata_template: str = "standard",
    dry_run: bool = False,
    metadata: dict[str, Any] | None = None,
    copy_mode: str = "all",
    force: bool = False,
) -> Dict[str, Any]:
    """Create a well-organized Quilt package from S3 bucket contents with smart organization.

    This is a specialized tool for bulk processing of S3 bucket contents into packages.
    For simple package creation with specific files, use package_create() instead.
    """
    try:
        if not validate_package_name(package_name):
            return format_error_response("Invalid package name format. Use 'namespace/name'")

        if not source_bucket:
            return format_error_response("source_bucket is required")

        # Handle metadata parameter
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
                    }
            elif isinstance(metadata, dict):
                processed_metadata = metadata.copy()
            else:
                return {
                    "success": False,
                    "error": "Invalid metadata type",
                    "provided_type": type(metadata).__name__,
                    "expected": "Dictionary object or JSON string",
                }

            # Extract README content from metadata
            if "readme_content" in processed_metadata:
                readme_content = processed_metadata.pop("readme_content")
            elif "readme" in processed_metadata:
                readme_content = processed_metadata.pop("readme")

        # Validate bucket name
        if source_bucket.startswith("s3://"):
            return {
                "success": False,
                "error": "Invalid bucket name format",
                "provided": source_bucket,
                "expected": "bucket name only (without s3:// prefix)",
                "fix": f"Try using: {source_bucket.replace('s3://', '')}",
            }

        # Suggest target registry if not provided
        if not target_registry:
            try:
                recommendations = bucket_recommendations_get(
                    source_bucket=source_bucket, operation_type="package_creation"
                )

                if recommendations.get("success") and recommendations.get("recommendations", {}).get(
                    "primary_recommendations"
                ):
                    top_rec = recommendations["recommendations"]["primary_recommendations"][0]
                    target_registry = f"s3://{top_rec['bucket_name']}"
                else:
                    target_registry = _suggest_target_registry(source_bucket, source_prefix)

            except Exception as e:
                logger.warning(f"Permission-based recommendation failed: {e}")
                target_registry = _suggest_target_registry(source_bucket, source_prefix)

        # Validate target registry permissions
        target_bucket_name = target_registry.replace("s3://", "")
        try:
            access_check = bucket_access_check(target_bucket_name)
            if not access_check.get("success") or not access_check.get("access_summary", {}).get("can_write"):
                return {
                    "success": False,
                    "error": "Cannot create package in target registry",
                    "cause": "Insufficient write permissions",
                    "target_registry": target_registry,
                }
        except Exception as e:
            logger.warning(f"Could not validate target registry permissions: {e}")

        # Initialize clients
        s3_client = get_s3_client()

        # Validate source bucket access
        try:
            _validate_bucket_access(s3_client, source_bucket)
        except Exception as e:
            error_msg = str(e)
            if "Access denied" in error_msg or "AccessDenied" in error_msg:
                return {
                    "success": False,
                    "error": "Cannot access source bucket - insufficient permissions",
                    "bucket": source_bucket,
                    "cause": "Missing read permissions for source bucket",
                }
            else:
                return format_error_response(f"Cannot access source bucket {source_bucket}: {str(e)}")

        # Discover source objects
        logger.info(f"Discovering objects in s3://{source_bucket}/{source_prefix}")
        objects = _discover_s3_objects(s3_client, source_bucket, source_prefix, include_patterns, exclude_patterns)

        if not objects:
            return format_error_response("No objects found matching the specified criteria")

        # Organize file structure
        organized_structure = _organize_file_structure(objects, auto_organize)
        total_size = sum(obj.get("Size", 0) for obj in objects)

        # Prepare source information
        source_info = {
            "bucket": source_bucket,
            "prefix": source_prefix,
            "source_description": (
                f"s3://{source_bucket}/{source_prefix}" if source_prefix else f"s3://{source_bucket}"
            ),
        }

        # Generate comprehensive metadata
        enhanced_metadata = _generate_package_metadata(
            package_name=package_name,
            source_info=source_info,
            organized_structure=organized_structure,
            metadata_template=metadata_template,
            user_metadata=processed_metadata,
        )

        # Generate README content
        final_readme_content = None

        if readme_content:
            final_readme_content = readme_content
        elif generate_readme:
            final_readme_content = _generate_readme_content(
                package_name=package_name,
                description=description,
                organized_structure=organized_structure,
                total_size=total_size,
                source_info=source_info,
                metadata_template=metadata_template,
            )

        # Generate Quilt summary files
        from .quilt_summary import create_quilt_summary_files

        summary_files = create_quilt_summary_files(
            package_name=package_name,
            package_metadata=enhanced_metadata,
            organized_structure=organized_structure,
            readme_content=final_readme_content,
            source_info=source_info,
            metadata_template=metadata_template,
        )

        # Prepare confirmation information
        confirmation_info = {
            "bucket_suggested": target_registry,
            "structure_preview": {
                folder: {
                    "file_count": len(files),
                    "sample_files": [f["Key"] for f in files[:3]],
                }
                for folder, files in organized_structure.items()
                if files
            },
            "total_files": len(objects),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "organization_applied": auto_organize,
            "readme_generated": generate_readme,
            "summary_files_generated": summary_files.get("success", False),
            "visualization_count": summary_files.get("visualization_count", 0),
        }

        # If dry run, return preview without creating
        if dry_run:
            return {
                "success": True,
                "action": "preview",
                "package_name": package_name,
                "registry": target_registry,
                "structure_preview": confirmation_info,
                "readme_preview": (final_readme_content[:500] + "..." if final_readme_content else None),
                "metadata_preview": enhanced_metadata,
                "summary_files_preview": {
                    "quilt_summarize.json": summary_files.get("summary_package", {}).get("quilt_summarize.json", {}),
                    "visualizations": summary_files.get("summary_package", {}).get("visualizations", {}),
                    "files_generated": summary_files.get("files_generated", {}),
                },
                "message": "Preview generated. Set dry_run=False to create the package.",
            }

        # Create the actual package
        logger.info(f"Creating package {package_name} with enhanced structure")
        package_result = _create_enhanced_package(
            s3_client=s3_client,
            organized_structure=organized_structure,
            source_bucket=source_bucket,
            package_name=package_name,
            target_registry=target_registry,
            description=description,
            enhanced_metadata=enhanced_metadata,
            readme_content=final_readme_content,
            summary_files=summary_files,
            copy_mode=copy_mode,
            force=force,
        )

        return {
            "success": True,
            "action": "created",
            "package_name": package_name,
            "registry": target_registry,
            "structure": {
                "folders_created": list(organized_structure.keys()),
                "files_organized": len(objects),
                "readme_generated": generate_readme,
            },
            "metadata": {
                "package_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": list(
                    set(Path(obj["Key"]).suffix.lower().lstrip(".") for obj in objects if Path(obj["Key"]).suffix)
                ),
                "organization_applied": ("logical_hierarchy" if auto_organize else "flat"),
            },
            "confirmation": confirmation_info,
            "package_hash": package_result.get("top_hash"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "summary_files": {
                "quilt_summarize.json": summary_files.get("summary_package", {}).get("quilt_summarize.json", {}),
                "visualizations": summary_files.get("summary_package", {}).get("visualizations", {}),
                "files_generated": summary_files.get("files_generated", {}),
                "visualization_count": summary_files.get("visualization_count", 0),
            },
        }

    except NoCredentialsError:
        return format_error_response("AWS credentials not found. Please configure AWS authentication.")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        return format_error_response(f"AWS error ({error_code}): {str(e)}")
    except Exception as e:
        logger.error(f"Error creating package from S3: {str(e)}")
        return format_error_response(f"Failed to create package: {str(e)}")


# ============================================================================
# UNIFIED PACKAGE CREATION INTERFACE
# ============================================================================


def package_create(
    name: str,
    files: List[str],
    description: str = "",
    auto_organize: bool = True,
    dry_run: bool = False,
    target_registry: Optional[str] = None,
    metadata: dict[str, Any] | None = None,
    metadata_template: str = "standard",
    copy_mode: str = "all",
) -> Dict[str, Any]:
    """Primary package creation interface - handles all package creation scenarios.

    This is the main package creation tool that provides intelligent defaults,
    automatic validation, permissions checking, and helpful guidance. Use this
    for most package creation needs. For bulk S3 processing, see package_create_from_s3().
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

        # Prepare metadata using template
        try:
            template_metadata = metadata_template_get(metadata_template)

            if description:
                template_metadata["description"] = description

            # Handle user-provided metadata
            if metadata is not None:
                if isinstance(metadata, str):
                    try:
                        import json

                        user_metadata = json.loads(metadata)
                    except json.JSONDecodeError as e:
                        return {
                            "success": False,
                            "error": "Invalid metadata JSON format",
                            "provided": metadata,
                            "json_error": str(e),
                        }
                elif isinstance(metadata, dict):
                    user_metadata = metadata.copy()
                else:
                    return {
                        "success": False,
                        "error": "Invalid metadata type",
                        "provided_type": type(metadata).__name__,
                        "expected": "Dictionary object or JSON string",
                    }

                # Extract README content from user metadata
                readme_content = None
                if "readme_content" in user_metadata:
                    readme_content = user_metadata.pop("readme_content")
                elif "readme" in user_metadata:
                    readme_content = user_metadata.pop("readme")

                # Remove any remaining README fields
                if "readme" in user_metadata:
                    user_metadata.pop("readme")

                # Merge user metadata with template
                template_metadata.update(user_metadata)

                # Store README content for later addition as package file
                if readme_content:
                    template_metadata["_extracted_readme"] = readme_content

            # Validate final metadata
            validation_result = metadata_validate_structure(template_metadata, metadata_template)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "Metadata validation failed",
                    "validation_result": validation_result,
                    "suggested_fixes": validation_result.get("suggestions", []),
                }

            processed_metadata = template_metadata

        except Exception as e:
            return {
                "success": False,
                "error": "Failed to prepare metadata",
                "cause": str(e),
                "template_used": metadata_template,
            }

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
                metadata_template=metadata_template,
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
            if "/" not in file_path[5:] or file_path.endswith("/"):
                errors.append(f"Invalid S3 URI: {file_path}")
                error_fixes.append("S3 URI must include object key: s3://bucket/path/file.ext")
            else:
                s3_files.append(file_path)
        else:
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
    metadata_template: str,
    copy_mode: str,
) -> Dict[str, Any]:
    """Create package from S3 sources using enhanced S3-to-package tool."""
    try:
        # Extract source bucket and prefix from first S3 file
        first_s3_uri = s3_files[0]
        without_scheme = first_s3_uri[5:]
        source_bucket, first_key = without_scheme.split("/", 1)

        # Try to find common prefix
        source_prefix = ""
        if len(s3_files) > 1:
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
                    "metadata_template_used": metadata_template,
                    "source_analysis": {
                        "source_bucket": source_bucket,
                        "source_prefix": source_prefix,
                        "total_files": len(s3_files),
                    },
                    "user_guidance": _generate_success_guidance(result, "s3"),
                }
            )

            # For dry-run, ensure comprehensive preview fields are present
            if dry_run and result.get("action") == "preview":
                result = _ensure_comprehensive_dry_run_preview(result, metadata, metadata_template, s3_files)

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
    return {
        "status": "not_implemented",
        "message": "Local file package creation not yet implemented",
        "alternative": "Upload files to S3 first, then use S3 URIs",
        "suggested_workflow": [
            "1. Upload files to S3 using: bucket_objects_put()",
            "2. Create package using S3 URIs with: package_create()",
            "3. Or use existing S3 data with: package_create_from_s3()",
        ],
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
    }


def _find_common_prefix(keys: List[str]) -> str:
    """Find common prefix among a list of S3 keys."""
    if not keys:
        return ""

    if len(keys) == 1:
        return str(Path(keys[0]).parent) + "/" if "/" in keys[0] else ""

    common = keys[0]
    for key in keys[1:]:
        while not key.startswith(common):
            common = common[:-1]
            if not common:
                break

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


def _ensure_comprehensive_dry_run_preview(
    result: Dict[str, Any],
    metadata: Dict[str, Any],
    metadata_template: str,
    s3_files: List[str],
) -> Dict[str, Any]:
    """Ensure dry-run result has comprehensive preview fields."""
    try:
        if "structure_preview" not in result:
            result["structure_preview"] = _generate_basic_structure_preview(s3_files)

        if "metadata_preview" not in result:
            result["metadata_preview"] = _generate_metadata_preview(metadata, metadata_template)

        if "readme_preview" not in result:
            result["readme_preview"] = _generate_readme_preview(metadata, result.get("package_name", "Package"))

        if "summary_files_preview" not in result:
            result["summary_files_preview"] = _generate_summary_files_preview(
                result.get("package_name", "package"), metadata, metadata_template
            )

        return result

    except Exception as e:
        logger.error(f"Error ensuring comprehensive dry-run preview: {e}")
        return result


def _generate_basic_structure_preview(s3_files: List[str]) -> Dict[str, Any]:
    """Generate a basic structure preview from S3 files."""
    organized_structure: Dict[str, List[Dict[str, Any]]] = {}
    total_files = len(s3_files)

    for s3_file in s3_files:
        file_name = Path(s3_file).name
        folder = _determine_file_folder(file_name)

        if folder not in organized_structure:
            organized_structure[folder] = []

        organized_structure[folder].append(
            {
                "name": file_name,
                "size": PLACEHOLDER_FILE_SIZE,
                "s3_uri": s3_file,
            }
        )

    total_size_mb = round(total_files * PLACEHOLDER_FILE_SIZE / (1024 * 1024), 3)

    return {
        "organized_structure": organized_structure,
        "total_files": total_files,
        "total_size_mb": total_size_mb,
        "organization_applied": True,
        "preview_note": "This is a basic preview. Actual package creation may differ.",
    }


def _determine_file_folder(file_name: str) -> str:
    """Determine the appropriate folder for a file based on its extension."""
    if "." in file_name:
        ext = file_name.split(".")[-1].lower()
        return f"{ext}_files/" if ext else "data/"
    return "data/"


def _generate_metadata_preview(metadata: Optional[Dict[str, Any]], metadata_template: str) -> Dict[str, Any]:
    """Generate metadata preview with template information."""
    preview = metadata.copy() if metadata else {}

    TEMPLATE_PACKAGE_TYPES = {
        "standard": "data",
        "genomics": "genomics",
        "ml": "ml_dataset",
        "research": "research",
        "analytics": "analytics",
    }

    if "package_type" not in preview:
        preview["package_type"] = TEMPLATE_PACKAGE_TYPES.get(metadata_template, "data")

    if "created_by" not in preview:
        preview["created_by"] = "quilt-mcp-server"

    if "data_type" not in preview and metadata_template != "standard":
        preview["data_type"] = metadata_template

    return preview


def _generate_readme_preview(metadata: Optional[Dict[str, Any]], package_name: str) -> str:
    """Generate a basic README preview."""
    extracted_readme = metadata.get("_extracted_readme") if metadata else None
    if extracted_readme:
        return extracted_readme[:DEFAULT_PREVIEW_SIZE_LIMIT] + (
            "..." if len(extracted_readme) > DEFAULT_PREVIEW_SIZE_LIMIT else ""
        )

    description = metadata.get("description", "Data package") if metadata else "Data package"
    return f"# {package_name}\n\n{description}\n\nThis package was created using quilt-mcp-server."


def _generate_summary_files_preview(
    package_name: str, metadata: Optional[Dict[str, Any]], metadata_template: str
) -> Dict[str, Any]:
    """Generate a basic summary files preview."""
    package_type = metadata.get("package_type", "data") if metadata else "data"

    return {
        "quilt_summarize.json": {
            "version": "1.0",
            "name": package_name,
            "metadata_template": metadata_template,
            "package_type": package_type,
            "created_by": "quilt-mcp-server",
        },
        "visualizations": {
            "file_distribution": {"preview": "File distribution chart would be generated"},
        },
        "files_generated": {
            "quilt_summarize.json": True,
            "README.md": True,
        },
    }


# ============================================================================
# PACKAGE VALIDATION
# ============================================================================


def _validate_package_alternative(package_name: str, registry: str, browse_error: Dict[str, Any]) -> Dict[str, Any]:
    """Alternative validation approach when package browsing fails."""
    try:
        from .search import catalog_search

        search_result = catalog_search(package_name, registry=registry, limit=1)

        if search_result.get("success") and search_result.get("results"):
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
            }
        else:
            return {
                "success": False,
                "error": "Cannot validate package - browsing failed",
                "browse_error": browse_error.get("error"),
                "search_attempted": True,
                "search_result": search_result.get("error", "Package not found in search"),
            }
    except Exception as e:
        return {
            "success": False,
            "error": "Cannot validate package - browsing failed",
            "browse_error": browse_error.get("error"),
            "alternative_validation_error": str(e),
        }


def package_validate(
    package_name: str,
    registry: str = None,
    check_integrity: bool = True,
    check_accessibility: bool = True,
) -> Dict[str, Any]:
    """Validate package integrity and accessibility."""
    try:
        from .packages import package_browse

        target_registry = registry or DEFAULT_REGISTRY
        if not target_registry:
            target_registry = "s3://quilt-sandbox-bucket"

        browse_result = package_browse(package_name, registry=target_registry)

        if not browse_result.get("success"):
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

        if check_integrity:
            for entry in entries:
                if entry.get("physical_key") and not entry.get("error"):
                    validation_results["accessible_files"] += 1
                else:
                    validation_results["inaccessible_files"] += 1
                    if entry.get("error"):
                        validation_results["errors"].append(f"File {entry['logical_key']}: {entry['error']}")

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
        }

    except Exception as e:
        return format_error_response(f"Package validation failed: {str(e)}")
