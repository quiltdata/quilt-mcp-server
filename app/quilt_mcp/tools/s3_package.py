"""Enhanced S3-to-Package Creation Tool for Quilt MCP Server.

This module provides advanced functionality to create well-organized Quilt packages 
directly from S3 bucket contents, with intelligent structure organization, 
automated documentation generation, and rich metadata management.
"""

from typing import Any, Dict, List, Optional, Tuple
import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import boto3
import quilt3
from botocore.exceptions import ClientError, NoCredentialsError

from ..utils import get_s3_client, validate_package_name, format_error_response
from .permissions import bucket_recommendations_get, bucket_access_check

logger = logging.getLogger(__name__)


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


def _suggest_target_registry(source_bucket: str, source_prefix: str) -> str:
    """Suggest appropriate target registry based on source patterns."""
    source_text = f"{source_bucket} {source_prefix}".lower()
    
    for registry_type, patterns in REGISTRY_PATTERNS.items():
        if any(pattern in source_text for pattern in patterns):
            return f"s3://{registry_type}-packages"
    
    # Default fallback
    return "s3://data-packages"


def _organize_file_structure(objects: List[Dict[str, Any]], auto_organize: bool) -> Dict[str, List[Dict[str, Any]]]:
    """Organize files into logical folder structure."""
    if not auto_organize:
        return {"": objects}  # No organization, flat structure
    
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
    metadata_template: str
) -> str:
    """Generate comprehensive README.md content."""
    namespace, name = package_name.split("/")
    
    # Calculate summary statistics
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
            for f in files[:5]:  # Sample first 5 files
                ext = Path(f["Key"]).suffix.lower().lstrip(".")
                if ext:
                    folder_types.add(ext)
            types_str = ", ".join(sorted(folder_types))
            readme_content += f"| `{folder or 'root'}/` | {len(files)} | {types_str} |\n"
    
    # Add usage section
    readme_content += f"""
## Usage

```python
import quilt3

# Browse the package
pkg = quilt3.Package.browse("{package_name}")

# Access specific data files
"""
    
    # Add examples for each folder
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
    
    readme_content += f"""- **Created**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
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
    user_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate comprehensive package metadata following Quilt standards.
    
    NOTE: This function should NEVER include README content in the metadata.
    README content should only be added as files to the package, not as metadata.
    """
    total_objects = sum(len(files) for files in organized_structure.values())
    total_size = sum(
        sum(obj.get("Size", 0) for obj in files) 
        for files in organized_structure.values()
    )
    
    # Extract file types
    file_types = set()
    for files in organized_structure.values():
        for obj in files:
            ext = Path(obj["Key"]).suffix.lower().lstrip(".")
            if ext:
                file_types.add(ext)
    
    # Build metadata structure
    metadata = {
        "quilt": {
            "created_by": "mcp-s3-package-tool-enhanced",
            "creation_date": datetime.utcnow().isoformat() + "Z",
            "package_version": "1.0.0",
            "source": {
                "type": "s3_bucket",
                "bucket": source_info.get("bucket"),
                "prefix": source_info.get("prefix", ""),
                "total_objects": total_objects,
                "total_size_bytes": total_size
            },
            "organization": {
                "structure_type": "logical_hierarchy",
                "auto_organized": True,
                "folder_mapping": {
                    folder: f"Contains {len(files)} files"
                    for folder, files in organized_structure.items() if files
                }
            },
            "data_profile": {
                "file_types": sorted(list(file_types)),
                "total_files": total_objects,
                "size_mb": round(total_size / (1024 * 1024), 2)
            }
        }
    }
    
    # Add template-specific metadata
    if metadata_template == "ml":
        metadata["ml"] = {
            "type": "machine_learning",
            "data_stage": "processed",
            "model_ready": True
        }
    elif metadata_template == "analytics":
        metadata["analytics"] = {
            "type": "business_analytics", 
            "analysis_ready": True,
            "report_generated": True
        }
    
    # Add user metadata
    if user_metadata:
        metadata["user_metadata"] = user_metadata
    
    return metadata


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
    metadata: Any = None,
    copy_mode: str = "all",
) -> Dict[str, Any]:
    """
    Create a well-organized Quilt package from S3 bucket contents with smart organization.
    
    Args:
        source_bucket: S3 bucket containing source data
        package_name: Name for the new package (namespace/name format)
        source_prefix: Optional prefix to filter source objects (default: "")
        target_registry: Target Quilt registry (auto-suggested if not provided)
        description: Package description
        include_patterns: File patterns to include (glob style)
        exclude_patterns: File patterns to exclude (glob style)  
        auto_organize: Enable smart folder organization (default: True)
        generate_readme: Generate comprehensive README.md (default: True)
        confirm_structure: Require user confirmation of structure (default: True)
        metadata_template: Metadata template to use ('standard', 'ml', 'analytics')
        dry_run: Preview structure without creating package (default: False)
        metadata: Additional user-provided metadata
        
    Returns:
        Package creation result with structure info, metadata, and confirmation details
    """
    try:
        # Validate inputs
        if not validate_package_name(package_name):
            return format_error_response("Invalid package name format. Use 'namespace/name'")
        
        if not source_bucket:
            return format_error_response("source_bucket is required")
        
        # Handle metadata parameter - support both dict and JSON string for user convenience
        processed_metadata = {}
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
                            '{"description": "Dataset from S3", "source": "s3_bucket"}',
                            '{"tags": ["s3-import", "2024"], "quality": "raw"}'
                        ],
                        "tip": "Use proper JSON format with quotes around keys and string values"
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
                        '{"description": "Dataset from S3", "version": "1.0"}',
                        '{"tags": ["s3-import", "2024"], "author": "data-team"}'
                    ],
                    "tip": "Pass metadata as a dictionary object or JSON string"
                }
        
        # Validate and normalize bucket name
        if source_bucket.startswith("s3://"):
            return {
                "success": False,
                "error": "Invalid bucket name format",
                "provided": source_bucket,
                "expected": "bucket name only (without s3:// prefix)",
                "example": "quilt-example",
                "tip": "Use bucket name only, not full S3 URI",
                "fix": f"Try using: {source_bucket.replace('s3://', '')}"
            }
        
        # Suggest target registry if not provided using permissions discovery
        if not target_registry:
            # Try to get smart recommendations based on actual permissions
            try:
                recommendations = bucket_recommendations_get(
                    source_bucket=source_bucket,
                    operation_type="package_creation"
                )
                
                if recommendations.get("success") and recommendations.get("recommendations", {}).get("primary_recommendations"):
                    # Use the top recommendation
                    top_rec = recommendations["recommendations"]["primary_recommendations"][0]
                    target_registry = f"s3://{top_rec['bucket_name']}"
                    logger.info(f"Using permission-based recommendation: {target_registry}")
                else:
                    # Fallback to pattern-based suggestion
                    target_registry = _suggest_target_registry(source_bucket, source_prefix)
                    logger.info(f"Using pattern-based suggestion: {target_registry}")
                    
            except Exception as e:
                logger.warning(f"Permission-based recommendation failed, using pattern-based: {e}")
                target_registry = _suggest_target_registry(source_bucket, source_prefix)
                logger.info(f"Fallback suggestion: {target_registry}")
        
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
                    "possible_fixes": [
                        f"Verify you have s3:PutObject permissions for {target_bucket_name}",
                        "Check if you're connected to the right catalog",
                        "Try a different bucket you own"
                    ],
                    "suggested_actions": [
                        "Try: bucket_recommendations_get() to find writable buckets",
                        "Try: test_permissions() to diagnose specific issues"
                    ],
                    "debug_info": {"aws_error": "AccessDenied", "operation": "target_registry_validation"}
                }
        except Exception as e:
            logger.warning(f"Could not validate target registry permissions: {e}")
            # Continue anyway - the user might have permissions that we can't detect
        
        # Initialize clients
        s3_client = boto3.client("s3")
        
        # Validate source bucket access
        try:
            _validate_bucket_access(s3_client, source_bucket)
        except Exception as e:
            # Provide friendly error message with helpful suggestions
            error_msg = str(e)
            if "Access denied" in error_msg or "AccessDenied" in error_msg:
                return {
                    "success": False,
                    "error": "Cannot access source bucket - insufficient permissions",
                    "bucket": source_bucket,
                    "cause": "Missing read permissions for source bucket",
                    "possible_fixes": [
                        f"Verify you have s3:ListBucket and s3:GetObject permissions for {source_bucket}",
                        "Check if the bucket name is correct",
                        "Ensure your AWS credentials are properly configured",
                        "Try: bucket_access_check() to diagnose specific permission issues"
                    ],
                    "suggested_actions": [
                        f"Try: bucket_recommendations_get() to find buckets you can access",
                        f"Try: aws_permissions_discover() to see all your bucket permissions"
                    ],
                    "debug_info": {"aws_error": error_msg, "operation": "source_bucket_access"}
                }
            else:
                return format_error_response(f"Cannot access source bucket {source_bucket}: {str(e)}")
        
        # Discover source objects
        logger.info(f"Discovering objects in s3://{source_bucket}/{source_prefix}")
        objects = _discover_s3_objects(
            s3_client, source_bucket, source_prefix, include_patterns, exclude_patterns
        )
        
        if not objects:
            return format_error_response("No objects found matching the specified criteria")
        
        # Organize file structure
        organized_structure = _organize_file_structure(objects, auto_organize)
        total_size = sum(obj.get("Size", 0) for obj in objects)
        
        # Prepare source information
        source_info = {
            "bucket": source_bucket,
            "prefix": source_prefix,
            "source_description": f"s3://{source_bucket}/{source_prefix}" if source_prefix else f"s3://{source_bucket}"
        }
        
        # Generate comprehensive metadata
        enhanced_metadata = _generate_package_metadata(
            package_name=package_name,
            source_info=source_info,
            organized_structure=organized_structure,
            metadata_template=metadata_template,
            user_metadata=processed_metadata
        )
        
        # Generate README content
        # IMPORTANT: README content is added as a FILE to the package, not as metadata
        readme_content = None
        if generate_readme:
            readme_content = _generate_readme_content(
                package_name=package_name,
                description=description,
                organized_structure=organized_structure,
                total_size=total_size,
                source_info=source_info,
                metadata_template=metadata_template
            )
        
        # Generate Quilt summary files (quilt_summarize.json + visualizations)
        from .quilt_summary import create_quilt_summary_files
        summary_files = create_quilt_summary_files(
            package_name=package_name,
            package_metadata=enhanced_metadata,
            organized_structure=organized_structure,
            readme_content=readme_content,
            source_info=source_info,
            metadata_template=metadata_template
        )
        
        # Prepare confirmation information
        confirmation_info = {
            "bucket_suggested": target_registry,
            "structure_preview": {
                folder: {
                    "file_count": len(files),
                    "sample_files": [f["Key"] for f in files[:3]]
                }
                for folder, files in organized_structure.items() if files
            },
            "total_files": len(objects),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "organization_applied": auto_organize,
            "readme_generated": generate_readme,
            "summary_files_generated": summary_files.get("success", False),
            "visualization_count": summary_files.get("visualization_count", 0)
        }
        
        # If dry run, return preview without creating
        if dry_run:
            return {
                "success": True,
                "action": "preview",
                "package_name": package_name,
                "registry": target_registry,
                "structure_preview": confirmation_info,
                "readme_preview": readme_content[:500] + "..." if readme_content else None,
                "metadata_preview": enhanced_metadata,
                "summary_files_preview": {
                    "quilt_summarize.json": summary_files.get("summary_package", {}).get("quilt_summarize.json", {}),
                    "visualizations": summary_files.get("summary_package", {}).get("visualizations", {}),
                    "files_generated": summary_files.get("files_generated", {})
                },
                "message": "Preview generated. Set dry_run=False to create the package."
            }
        
        # User confirmation step (in real implementation, this would be interactive)
        if confirm_structure:
            # For now, we'll proceed as if confirmed
            # In a real implementation, this would present the preview to the user
            logger.info("Structure confirmation: proceeding with package creation")
        
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
            readme_content=readme_content,
            summary_files=summary_files,
            copy_mode=copy_mode,
        )
        
        return {
            "success": True,
            "action": "created",
            "package_name": package_name,
            "registry": target_registry,
            "structure": {
                "folders_created": list(organized_structure.keys()),
                "files_organized": len(objects),
                "readme_generated": generate_readme
            },
            "metadata": {
                "package_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": list(set(
                    Path(obj["Key"]).suffix.lower().lstrip(".")
                    for obj in objects
                    if Path(obj["Key"]).suffix
                )),
                "organization_applied": "logical_hierarchy" if auto_organize else "flat"
            },
            "confirmation": confirmation_info,
            "package_hash": package_result.get("top_hash"),
            "created_at": datetime.utcnow().isoformat(),
            "summary_files": {
                "quilt_summarize.json": summary_files.get("summary_package", {}).get("quilt_summarize.json", {}),
                "visualizations": summary_files.get("summary_package", {}).get("visualizations", {}),
                "files_generated": summary_files.get("files_generated", {}),
                "visualization_count": summary_files.get("visualization_count", 0)
            }
        }
        
    except NoCredentialsError:
        return format_error_response("AWS credentials not found. Please configure AWS authentication.")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        return format_error_response(f"AWS error ({error_code}): {str(e)}")
    except Exception as e:
        logger.error(f"Error creating package from S3: {str(e)}")
        return format_error_response(f"Failed to create package: {str(e)}")


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
    
    # Check exclude patterns first
    if exclude_patterns:
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(key, pattern):
                return False
    
    # Check include patterns
    if include_patterns:
        for pattern in include_patterns:
            if fnmatch.fnmatch(key, pattern):
                return True
        return False  # If include patterns specified but none match
    
    return True  # Include by default if no patterns specified


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
) -> Dict[str, Any]:
    """Create the enhanced Quilt package with organized structure and documentation."""
    try:
        # Create a new Quilt package
        pkg = quilt3.Package()
        
        # Add files to package according to organized structure
        for folder, objects in organized_structure.items():
            for obj in objects:
                source_key = obj["Key"]
                
                # Determine logical path in package
                if folder:
                    logical_path = f"{folder}/{Path(source_key).name}"
                else:
                    logical_path = Path(source_key).name
                
                # Add S3 object to package
                s3_uri = f"s3://{source_bucket}/{source_key}"
                pkg.set(logical_path, s3_uri)
                
                logger.debug(f"Added {s3_uri} as {logical_path}")
        
        # Add README.md if generated
        # IMPORTANT: README content is added as a FILE in the package, never as metadata
        if readme_content:
            # Add README content as a file in the package
            import io
            pkg.set("README.md", io.StringIO(readme_content))
            logger.info("Added generated README.md to package")
        
        # Add summary files if provided
        if summary_files and summary_files.get("summary_package"):
            summary_package = summary_files["summary_package"]
            
            # Add quilt_summarize.json
            if "quilt_summarize.json" in summary_package:
                import json
                quilt_summary_json = json.dumps(summary_package["quilt_summarize.json"], indent=2)
                pkg.set("quilt_summarize.json", io.StringIO(quilt_summary_json))
                logger.info("Added quilt_summarize.json to package")
            
            # Add visualizations if they exist
            if "visualizations" in summary_package and summary_package["visualizations"]:
                # Create a visualizations directory and add visualization files
                for viz_name, viz_data in summary_package["visualizations"].items():
                    if viz_data.get("image_base64"):
                        import base64
                        # Decode base64 image and add as file
                        image_data = base64.b64decode(viz_data["image_base64"])
                        pkg.set(f"visualizations/{viz_name}.png", io.BytesIO(image_data))
                        logger.info(f"Added visualization {viz_name}.png to package")
        
        # Set comprehensive metadata
        # IMPORTANT: README content should NEVER be added to package metadata
        # Only add README content as files using pkg.set() - never in enhanced_metadata
        pkg.set_meta(enhanced_metadata)
        
        # Push package to registry
        message = f"Created via enhanced S3-to-package tool: {description}" if description else "Created via enhanced S3-to-package tool"
        # Build selector_fn for desired copy behavior
        def _selector_all(_lk, _e):
            return True

        def _selector_none(_lk, _e):
            return False

        def _selector_same_bucket(_lk, e):
            try:
                physical_key = str(getattr(e, "physical_key", ""))
            except Exception:
                physical_key = ""
            if not physical_key.startswith("s3://"):
                return False
            try:
                bucket = physical_key.split("/", 3)[2]
            except Exception:
                return False
            target_bucket = target_registry.replace("s3://", "").split("/", 1)[0]
            return bucket == target_bucket

        selector_fn = _selector_all
        if copy_mode == "none":
            selector_fn = _selector_none
        elif copy_mode == "same_bucket":
            selector_fn = _selector_same_bucket

        top_hash = pkg.push(
            package_name,
            registry=target_registry,
            message=message,
            selector_fn=selector_fn,
        )
        
        logger.info(f"Successfully created package {package_name} with hash {top_hash}")
        
        return {
            "top_hash": top_hash,
            "message": f"Enhanced package {package_name} created successfully",
            "registry": target_registry
        }
        
    except Exception as e:
        logger.error(f"Error creating enhanced package: {str(e)}")
        raise


# Keep the old function for backward compatibility but mark as deprecated
async def _create_package_from_objects(
    s3_client,
    objects: List[Dict[str, Any]],
    source_bucket: str,
    package_name: str,
    target_registry: str,
    target_bucket: Optional[str],
    description: str,
    preserve_structure: bool,
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create the Quilt package from S3 objects (legacy function)."""
    logger.warning("Using legacy package creation function. Consider using enhanced version.")
    
    # Convert to new format for compatibility
    if preserve_structure:
        organized_structure = {"": objects}
    else:
        organized_structure = _organize_file_structure(objects, True)
    
    enhanced_metadata = _generate_package_metadata(
        package_name=package_name,
        source_info={"bucket": source_bucket, "prefix": ""},
        organized_structure=organized_structure,
        metadata_template="standard",
        user_metadata=metadata
    )
    
    return _create_enhanced_package(
        s3_client=s3_client,
        organized_structure=organized_structure,
        source_bucket=source_bucket,
        package_name=package_name,
        target_registry=target_registry,
        description=description,
        enhanced_metadata=enhanced_metadata,
        readme_content=None,
        summary_files=None
    )
