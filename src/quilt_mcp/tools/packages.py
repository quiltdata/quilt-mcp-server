from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from ..constants import DEFAULT_REGISTRY
from .quilt_summary import create_quilt_summary_files
from ..services.permissions_service import bucket_recommendations_get, check_bucket_access
from ..services.quilt_service import QuiltService
from ..utils import format_error_response, generate_signed_url, get_s3_client, validate_package_name
from .auth_helpers import AuthorizationContext, check_package_authorization
from ..models import (
    PackageBrowseParams,
    PackageBrowseSuccess,
    PackageCreateParams,
    PackageCreateSuccess,
    PackageCreateError,
    PackageUpdateParams,
    PackageUpdateSuccess,
    PackageUpdateError,
    PackageDeleteParams,
    PackageDeleteSuccess,
    PackageDeleteError,
    PackagesListParams,
    PackagesListSuccess,
    PackagesListError,
    PackageDiffParams,
    PackageDiffSuccess,
    PackageDiffError,
    PackageCreateFromS3Params,
    PackageCreateFromS3Success,
    PackageCreateFromS3Error,
    PackageSummary,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

# Initialize service
quilt_service = QuiltService()

# Export quilt3 module for backward compatibility with tests
quilt3 = quilt_service.get_quilt3_module()

# Helpers


def _normalize_registry(bucket_or_uri: str) -> str:
    """Normalize registry input to s3:// URI format.

    Args:
        bucket_or_uri: Either a bucket name (e.g., "my-bucket") or s3:// URI (e.g., "s3://my-bucket")

    Returns:
        Full s3:// URI format (e.g., "s3://my-bucket")
    """
    if bucket_or_uri.startswith("s3://"):
        return bucket_or_uri
    return f"s3://{bucket_or_uri}"


def _authorize_package(
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    context: dict[str, Any],
) -> tuple[AuthorizationContext | None, dict[str, Any] | None]:
    auth_ctx = check_package_authorization(tool_name, tool_args)
    if not auth_ctx.authorized:
        error_payload = auth_ctx.error_response()
        error_payload.update(context)
        return None, error_payload
    return auth_ctx, None


def _attach_auth_metadata(payload: dict[str, Any], auth_ctx: AuthorizationContext | None) -> dict[str, Any]:
    if auth_ctx and auth_ctx.auth_type:
        payload.setdefault("auth_type", auth_ctx.auth_type)
    return payload


def _collect_objects_into_package(
    pkg: Any, s3_uris: list[str], flatten: bool, warnings: list[str]
) -> list[dict[str, Any]]:
    added: list[dict[str, Any]] = []
    for uri in s3_uris:
        if not uri.startswith("s3://"):
            warnings.append(f"Skipping non-S3 URI: {uri}")
            continue
        without_scheme = uri[5:]
        if "/" not in without_scheme:
            warnings.append(f"Skipping bucket-only URI (no key): {uri}")
            continue
        bucket, key = without_scheme.split("/", 1)
        if not key or key.endswith("/"):
            warnings.append(f"Skipping URI that appears to be a 'directory': {uri}")
            continue
        logical_path = os.path.basename(key) if flatten else key
        original_logical_path = logical_path
        counter = 1
        while logical_path in pkg:
            logical_path = f"{counter}_{original_logical_path}"
            counter += 1
        try:
            pkg.set(logical_path, uri)
            added.append({"logical_path": logical_path, "source": uri})
        except Exception as e:
            warnings.append(f"Failed to add {uri}: {e}")
            continue
    return added


def _build_selector_fn(copy_mode: str, target_registry: str):
    """Build a Quilt selector_fn based on desired copy behavior.

    copy_mode options:
    - "all": copy all objects to target (default Quilt behavior)
    - "none": copy none; keep references to external locations
    - "same_bucket": copy only objects whose physical_key bucket matches target bucket
    """
    # Normalize and extract target bucket
    target_bucket = target_registry.replace("s3://", "").split("/", 1)[0]

    def selector_all(_logical_key, _entry):
        return True

    def selector_none(_logical_key, _entry):
        return False

    def selector_same_bucket(_logical_key, entry):
        try:
            physical_key = str(getattr(entry, "physical_key", ""))
        except Exception:
            physical_key = ""
        if not physical_key.startswith("s3://"):
            return False
        try:
            bucket = physical_key.split("/", 3)[2]
        except Exception:
            return False
        return bucket == target_bucket

    if copy_mode == "none":
        return selector_none
    if copy_mode == "same_bucket":
        return selector_same_bucket
    # Default
    return selector_all


# S3-to-package helpers and constants

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


def _organize_file_structure(objects: list[dict[str, Any]], auto_organize: bool) -> dict[str, list[dict[str, Any]]]:
    """Organize files into logical folder structure."""
    if not auto_organize:
        return {"": objects}  # No organization, flat structure

    organized: dict[str, list[dict[str, Any]]] = {}

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
    organized_structure: dict[str, list[dict[str, Any]]],
    total_size: int,
    source_info: dict[str, str],
    metadata_template: str,
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
# Browse the package using Quilt
# pkg = Package.browse("{package_name}")

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
    source_info: dict[str, Any],
    organized_structure: dict[str, list[dict[str, Any]]],
    metadata_template: str,
    user_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate comprehensive package metadata following Quilt standards.

    NOTE: This function should NEVER include README content in the metadata.
    README content should only be added as files to the package, not as metadata.
    """
    total_objects = sum(len(files) for files in organized_structure.values())
    total_size = sum(sum(obj.get("Size", 0) for obj in files) for files in organized_structure.values())

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

    # Add template-specific metadata
    if metadata_template == "ml":
        metadata["ml"] = {
            "type": "machine_learning",
            "data_stage": "processed",
            "model_ready": True,  # type: ignore[dict-item]
        }
    elif metadata_template == "analytics":
        metadata["analytics"] = {
            "type": "business_analytics",
            "analysis_ready": True,  # type: ignore[dict-item]
            "report_generated": True,  # type: ignore[dict-item]
        }

    # Add user metadata
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
    include_patterns: list[str] | None,
    exclude_patterns: list[str] | None,
) -> list[dict[str, Any]]:
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
    include_patterns: list[str] | None,
    exclude_patterns: list[str] | None,
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
    organized_structure: dict[str, list[dict[str, Any]]],
    source_bucket: str,
    package_name: str,
    target_registry: str,
    description: str,
    enhanced_metadata: dict[str, Any],
    readme_content: str | None = None,
    summary_files: dict[str, Any] | None = None,
    copy_mode: str = "all",
    force: bool = False,
) -> dict[str, Any]:
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

        # Prepare metadata - README content and other files will be handled by create_package_revision
        # IMPORTANT: README content should NEVER be added to package metadata
        # The create_package_revision method will handle README content automatically
        processed_metadata = enhanced_metadata.copy()

        # If readme_content exists, add it to metadata for processing by create_package_revision
        if readme_content:
            processed_metadata["readme_content"] = readme_content
            logger.info("Added README content to metadata for processing")

        # Prepare message
        message = (
            f"Created via enhanced S3-to-package tool: {description}"
            if description
            else "Created via enhanced S3-to-package tool"
        )

        # Create package using create_package_revision with auto_organize=True
        # This preserves the smart organization behavior of s3_package.py
        quilt_service = QuiltService()
        result = quilt_service.create_package_revision(
            package_name=package_name,
            s3_uris=s3_uris,
            metadata=processed_metadata,
            registry=target_registry,
            message=message,
            auto_organize=True,  # Preserve smart organization behavior
            copy=copy_mode,
        )

        # Handle the result
        if result.get("error"):
            logger.error(f"Package creation failed: {result['error']}")
            raise Exception(result["error"])

        top_hash = result.get("top_hash")
        logger.info(f"Successfully created package {package_name} with hash {top_hash}")

        # TODO: Handle summary files and visualizations in future enhancement
        # For now, basic package creation with README is supported
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


def packages_list(params: PackagesListParams) -> PackagesListSuccess | PackagesListError:
    """List all available Quilt packages in a registry - Quilt package discovery and comparison tasks

    Args:
        params: PackagesListParams with registry, limit, and prefix

    Returns:
        PackagesListSuccess with list of package names, or PackagesListError on failure.

    Next step:
        Surface package details to the user or feed identifiers into downstream package tools.

    Example:
        ```python
        from quilt_mcp.tools import packages
        from quilt_mcp.models import PackagesListParams

        params = PackagesListParams(registry="s3://my-bucket", limit=10)
        result = packages.packages_list(params)
        # Next step: Surface package details to the user or feed identifiers into downstream package tools.
        ```
    """
    try:
        # Normalize registry and pass to QuiltService.list_packages(), then apply filtering
        normalized_registry = _normalize_registry(params.registry)
        # Suppress stdout during list_packages to avoid JSON-RPC interference
        from ..utils import suppress_stdout

        quilt_service = QuiltService()
        with suppress_stdout():
            pkgs = list(quilt_service.list_packages(registry=normalized_registry))  # Convert generator to list

        # Apply prefix filtering if specified
        if params.prefix:
            pkgs = [pkg for pkg in pkgs if pkg.startswith(params.prefix)]

        # Apply limit if specified
        if params.limit > 0:
            pkgs = pkgs[:params.limit]

        return PackagesListSuccess(
            packages=pkgs,
            count=len(pkgs),
            registry=params.registry,
            prefix_filter=params.prefix if params.prefix else None,
        )
    except Exception as e:
        return PackagesListError(
            error=f"Failed to list packages: {str(e)}",
            registry=params.registry,
        )


def package_browse(params: PackageBrowseParams) -> PackageBrowseSuccess | ErrorResponse:
    """Browse the contents of a Quilt package with enhanced file information - Quilt package discovery and comparison tasks

    Args:
        params: PackageBrowseParams with package_name, registry, and browsing options

    Returns:
        PackageBrowseSuccess with comprehensive package contents, or ErrorResponse on failure.

    Examples:
        Basic browsing:
        package_browse(PackageBrowseParams(package_name="team/dataset"))

        Flat view (top-level only):
        package_browse(PackageBrowseParams(package_name="team/dataset", recursive=False))

        Limited depth:
        package_browse(PackageBrowseParams(package_name="team/dataset", max_depth=2))

    Next step:
        Surface package details to the user or feed identifiers into downstream package tools.

    Example:
        ```python
        from quilt_mcp.tools import packages
        from quilt_mcp.models import PackageBrowseParams

        params = PackageBrowseParams(package_name="team/dataset")
        result = packages.package_browse(params)
        # Next step: Surface package details to the user or feed identifiers into downstream package tools.
        ```
    """
    # Use the provided registry
    normalized_registry = _normalize_registry(params.registry)
    try:
        # Suppress stdout during browse to avoid JSON-RPC interference
        from ..utils import suppress_stdout

        quilt_service = QuiltService()
        with suppress_stdout():
            pkg = quilt_service.browse_package(params.package_name, registry=normalized_registry)

    except Exception as e:
        return ErrorResponse(
            error=f"Failed to browse package '{params.package_name}'",
            cause=str(e),
            possible_fixes=[
                "Verify the package name is correct",
                "Check if you have access to the registry",
                "Ensure the package exists in the specified registry",
            ],
            suggested_actions=[
                f"Try: packages_list(registry='{params.registry}') to see available packages",
                f"Try: unified_search(query='{params.package_name.split('/')[-1]}', scope='catalog') to find similar packages",
            ],
        )

    # Get detailed information about each entry
    entries = []
    file_tree: dict[str, Any] | None = {} if params.recursive else None
    keys = list(pkg.keys())
    total_size = 0
    file_types = set()

    # Apply top limit if specified
    if params.top > 0:
        keys = keys[:params.top]

    for logical_key in keys:
        try:
            entry = pkg[logical_key]

            # Get file information
            file_size = getattr(entry, "size", None)
            file_hash = str(getattr(entry, "hash", ""))
            physical_key = str(entry.physical_key) if hasattr(entry, "physical_key") else None

            # Determine file type and properties
            file_ext = logical_key.split(".")[-1].lower() if "." in logical_key else "unknown"
            file_types.add(file_ext)
            is_directory = logical_key.endswith("/") or file_size is None

            # Track total size
            if file_size:
                total_size += file_size

            entry_data = {
                "logical_key": logical_key,
                "physical_key": physical_key,
                "size": file_size,
                "size_human": _format_file_size(file_size) if file_size else None,
                "hash": file_hash,
                "file_type": file_ext,
                "is_directory": is_directory,
            }

            # Add enhanced file info if requested
            if params.include_file_info and physical_key and physical_key.startswith("s3://"):
                try:
                    # Try to get additional S3 metadata
                    import boto3

                    from ..utils import get_s3_client

                    s3_client = get_s3_client()
                    bucket_name = physical_key.split("/")[2]
                    object_key = "/".join(physical_key.split("/")[3:])

                    obj_info = s3_client.head_object(Bucket=bucket_name, Key=object_key)
                    entry_data.update(
                        {
                            "last_modified": str(obj_info.get("LastModified")),
                            "content_type": obj_info.get("ContentType"),
                            "storage_class": obj_info.get("StorageClass", "STANDARD"),
                        }
                    )
                except Exception:
                    # Don't fail if we can't get additional info
                    pass

            # Add S3 URI and signed URL if this is an S3 object
            if physical_key and physical_key.startswith("s3://"):
                entry_data["s3_uri"] = physical_key

                if params.include_signed_urls:
                    signed_url = generate_signed_url(physical_key)
                    if signed_url:
                        entry_data["download_url"] = signed_url

            entries.append(entry_data)

            # Build file tree structure for recursive view
            if params.recursive and file_tree is not None:
                _add_to_file_tree(file_tree, logical_key, entry_data, params.max_depth)

        except Exception as e:
            # Include entry with error info
            entries.append(
                {
                    "logical_key": logical_key,
                    "physical_key": None,
                    "size": None,
                    "hash": "",
                    "error": str(e),
                    "file_type": "error",
                }
            )

    # Prepare comprehensive response
    summary = PackageSummary(
        total_size=total_size,
        total_size_human=_format_file_size(total_size),
        file_types=sorted(list(file_types)),
        total_files=len([e for e in entries if not e.get("is_directory", False)]),
        total_directories=len([e for e in entries if e.get("is_directory", False)]),
    )

    # Get package metadata if available
    pkg_metadata = None
    try:
        pkg_metadata = dict(pkg.meta) if hasattr(pkg, "meta") else None
    except Exception:
        # Don't fail if we can't get metadata
        pass

    return PackageBrowseSuccess(
        package_name=params.package_name,
        registry=params.registry,
        total_entries=len(entries),
        summary=summary,
        view_type="recursive" if params.recursive else "flat",
        file_tree=file_tree if params.recursive and file_tree else None,
        entries=entries,
        metadata=pkg_metadata,
    )


def _add_to_file_tree(tree: dict, path: str, entry_data: dict, max_depth: int):
    """Add an entry to the file tree structure."""
    if max_depth > 0:
        depth = path.count("/")
        if depth >= max_depth:
            return

    parts = path.split("/")
    current = tree

    # Navigate to the correct position in the tree
    for i, part in enumerate(parts[:-1]):
        if part not in current:
            current[part] = {"type": "directory", "children": {}}
        current = current[part]["children"]

    # Add the final entry
    final_part = parts[-1]
    current[final_part] = {
        "type": "file" if not entry_data.get("is_directory") else "directory",
        "size": entry_data.get("size"),
        "size_human": entry_data.get("size_human"),
        "file_type": entry_data.get("file_type"),
        "physical_key": entry_data.get("physical_key"),
        "download_url": entry_data.get("download_url"),
    }


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes is None:
        return "Unknown"

    size_float = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_float < 1024.0:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024.0
    return f"{size_float:.1f} PB"


def package_diff(params: PackageDiffParams) -> PackageDiffSuccess | PackageDiffError:
    """Compare two package versions and show differences - Quilt package discovery and comparison tasks

    Args:
        params: PackageDiffParams with package names, registry, and optional hashes

    Returns:
        PackageDiffSuccess with differences, or PackageDiffError on failure.

    Next step:
        Surface package details to the user or feed identifiers into downstream package tools.

    Example:
        ```python
        from quilt_mcp.tools import packages
        from quilt_mcp.models import PackageDiffParams

        params = PackageDiffParams(
            package1_name="team/dataset-v1",
            package2_name="team/dataset-v2",
        )
        result = packages.package_diff(params)
        # Next step: Surface package details to the user or feed identifiers into downstream package tools.
        ```
    """
    normalized_registry = _normalize_registry(params.registry)

    try:
        # Browse packages with optional hash specification
        # Suppress stdout during browse operations to avoid JSON-RPC interference
        from ..utils import suppress_stdout

        quilt_service = QuiltService()
        with suppress_stdout():
            if params.package1_hash:
                pkg1 = quilt_service.browse_package(
                    params.package1_name, registry=normalized_registry, top_hash=params.package1_hash
                )
            else:
                pkg1 = quilt_service.browse_package(params.package1_name, registry=normalized_registry)

            if params.package2_hash:
                pkg2 = quilt_service.browse_package(
                    params.package2_name, registry=normalized_registry, top_hash=params.package2_hash
                )
            else:
                pkg2 = quilt_service.browse_package(params.package2_name, registry=normalized_registry)

    except Exception as e:
        return PackageDiffError(
            error=f"Failed to browse packages: {e}",
            package1=params.package1_name,
            package2=params.package2_name,
        )

    try:
        # Use quilt3's built-in diff functionality
        diff_result = pkg1.diff(pkg2)

        # Convert the diff result to a more readable format
        return PackageDiffSuccess(
            package1=params.package1_name,
            package2=params.package2_name,
            package1_hash=params.package1_hash if params.package1_hash else "latest",
            package2_hash=params.package2_hash if params.package2_hash else "latest",
            registry=params.registry,
            diff=diff_result,
        )

    except Exception as e:
        return PackageDiffError(
            error=f"Failed to diff packages: {e}",
            package1=params.package1_name,
            package2=params.package2_name,
        )


def package_create(params: PackageCreateParams) -> PackageCreateSuccess | PackageCreateError:
    """Create a new Quilt package from S3 objects - Core package creation, update, and deletion workflows

    Args:
        params: PackageCreateParams with package details and S3 URIs

    Returns:
        PackageCreateSuccess with package details, or PackageCreateError on failure.

    Examples:
        Basic package creation:
        package_create(PackageCreateParams(package_name="my-team/dataset", s3_uris=["s3://bucket/file.csv"]))

        With metadata:
        package_create(PackageCreateParams(
            package_name="my-team/dataset",
            s3_uris=["s3://bucket/file.csv"],
            metadata={"description": "My dataset", "type": "research"}
        ))

    Next step:
        Report the package operation result or continue the workflow (e.g., metadata updates).

    Example:
        ```python
        from quilt_mcp.tools import packages
        from quilt_mcp.models import PackageCreateParams

        params = PackageCreateParams(
            package_name="team/dataset",
            s3_uris=["s3://example-bucket/data.csv"],
        )
        result = packages.package_create(params)
        # Next step: Report the package operation result or continue the workflow (e.g., metadata updates).
        ```
    """
    # Initialize auth_ctx to avoid fragile locals() checks in exception handlers
    auth_ctx: AuthorizationContext | None = None

    warnings: list[str] = []
    if not params.s3_uris:
        return PackageCreateError(
            error="No S3 URIs provided",
            package_name=params.package_name,
            suggestions=["Provide at least one S3 URI", "Example: s3://bucket/path/to/file.csv"],
        )
    if not params.package_name:
        return PackageCreateError(
            error="Package name is required",
            package_name="",
            suggestions=["Provide a package name in format: namespace/name", "Example: team/dataset"],
        )

    # Process metadata to ensure README content is handled correctly
    processed_metadata = params.metadata.copy() if params.metadata else {}

    # Extract README content from metadata (it will be handled by create_package_revision)
    # readme_content takes priority if both fields exist
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

    normalized_registry = _normalize_registry(params.registry)

    auth_ctx, error = _authorize_package(
        "package_create",
        {"package_name": params.package_name, "registry": normalized_registry},
        context={"package_name": params.package_name, "registry": normalized_registry},
    )
    if error:
        return PackageCreateError(
            error=error.get("error", "Authorization failed"),
            package_name=params.package_name,
            registry=params.registry,
            suggestions=["Check your permissions", "Verify package name format", "Confirm registry access"],
        )

    try:
        # Use the new create_package_revision method with auto_organize=False
        # to preserve the existing flattening behavior
        result = quilt_service.create_package_revision(
            package_name=params.package_name,
            s3_uris=params.s3_uris,
            metadata=processed_metadata,
            registry=normalized_registry,
            message=params.message,
            auto_organize=False,  # Preserve flattening behavior like _collect_objects_into_package
            copy=params.copy_mode,
        )

        # Handle the result based on its structure
        if result.get("error"):
            return PackageCreateError(
                error=result["error"],
                package_name=params.package_name,
                registry=params.registry,
                suggestions=[
                    "Verify S3 URIs are valid and accessible",
                    "Check write permissions for the registry",
                    "Ensure no duplicate logical paths exist",
                ],
                warnings=warnings,
            )

        # Extract the top_hash from the result
        top_hash = result.get("top_hash")
        entries_added = result.get("entries_added", len(params.s3_uris))
        files = result.get("files", [])

        # Build package URL
        from .catalog import catalog_url
        from ..models import CatalogUrlParams
        catalog_params = CatalogUrlParams(
            registry=normalized_registry,
            package_name=params.package_name,
        )
        catalog_result = catalog_url(catalog_params)
        package_url = catalog_result.catalog_url if hasattr(catalog_result, 'catalog_url') else ""

        return PackageCreateSuccess(
            package_name=params.package_name,
            registry=params.registry,
            top_hash=str(top_hash),
            files_added=entries_added,
            package_url=package_url,
            files=files,
            message=params.message,
            warnings=warnings,
            auth_type=auth_ctx.auth_type if auth_ctx else None,
        )

    except Exception as e:
        return PackageCreateError(
            error=f"Failed to create package: {e}",
            package_name=params.package_name,
            registry=params.registry,
            suggestions=[
                "Check S3 permissions for source files",
                "Verify registry write access",
                "Ensure package name is valid",
                "Check network connectivity",
            ],
            warnings=warnings,
        )


def package_update(params: PackageUpdateParams) -> PackageUpdateSuccess | PackageUpdateError:
    """Update an existing Quilt package by adding new S3 objects - Core package creation, update, and deletion workflows

    Args:
        params: PackageUpdateParams with package details and S3 URIs to add

    Returns:
        PackageUpdateSuccess with update details, or PackageUpdateError on failure.

    Next step:
        Report the package operation result or continue the workflow (e.g., metadata updates).

    Example:
        ```python
        from quilt_mcp.tools import packages
        from quilt_mcp.models import PackageUpdateParams

        params = PackageUpdateParams(
            package_name="team/dataset",
            s3_uris=["s3://example-bucket/data.csv"],
        )
        result = packages.package_update(params)
        # Next step: Report the package operation result or continue the workflow (e.g., metadata updates).
        ```
    """
    # Initialize auth_ctx to avoid fragile locals() checks in exception handlers
    auth_ctx: AuthorizationContext | None = None

    if not params.s3_uris:
        return PackageUpdateError(
            error="No S3 URIs provided",
            package_name=params.package_name,
            suggestions=["Provide at least one S3 URI", "Example: s3://bucket/path/to/file.csv"],
        )
    if not params.package_name:
        return PackageUpdateError(
            error="package_name is required for package_update",
            package_name="",
            suggestions=["Provide a package name in format: namespace/name", "Example: team/dataset"],
        )
    warnings: list[str] = []
    normalized_registry = _normalize_registry(params.registry)
    auth_ctx, error = _authorize_package(
        "package_update",
        {"package_name": params.package_name, "registry": normalized_registry},
        context={"package_name": params.package_name, "registry": normalized_registry},
    )
    if error:
        return PackageUpdateError(
            error=error.get("error", "Authorization failed"),
            package_name=params.package_name,
            registry=params.registry,
            suggestions=["Check your permissions", "Verify package exists", "Confirm registry access"],
        )
    try:
        # Suppress stdout during browse to avoid JSON-RPC interference
        from ..utils import suppress_stdout

        with suppress_stdout():
            quilt_service = QuiltService()
            existing_pkg = quilt_service.browse_package(params.package_name, registry=normalized_registry)
    except Exception as e:
        return PackageUpdateError(
            error=f"Failed to browse existing package '{params.package_name}': {e}",
            package_name=params.package_name,
            registry=params.registry,
            suggestions=[
                "Verify package exists in the registry",
                "Check package name format",
                "Ensure you have read permissions",
            ],
        )
    # Use the existing package as the base instead of creating a new one
    updated_pkg = existing_pkg
    added = _collect_objects_into_package(updated_pkg, params.s3_uris, params.flatten, warnings)
    if not added:
        return PackageUpdateError(
            error="No new S3 objects were added",
            package_name=params.package_name,
            registry=params.registry,
            suggestions=[
                "Check that S3 URIs are valid and accessible",
                "Verify URIs point to actual files, not directories",
                "Ensure files don't already exist in package",
            ],
            warnings=warnings,
        )
    if params.metadata:
        try:
            combined = {}
            try:
                combined.update(existing_pkg.meta)
            except Exception:
                pass
            combined.update(params.metadata)
            updated_pkg.set_meta(combined)
        except Exception as e:
            warnings.append(f"Failed to set merged metadata: {e}")
    try:
        # Suppress stdout during push to avoid JSON-RPC interference
        from ..utils import suppress_stdout

        with suppress_stdout():
            selector_fn = _build_selector_fn(params.copy_mode, normalized_registry)
            top_hash = updated_pkg.push(
                params.package_name,
                registry=normalized_registry,
                message=params.message,
                selector_fn=selector_fn,
                force=True,
            )

    except Exception as e:
        return PackageUpdateError(
            error=f"Failed to push updated package: {e}",
            package_name=params.package_name,
            registry=params.registry,
            suggestions=[
                "Check write permissions for the registry",
                "Verify network connectivity",
                "Ensure no conflicts with existing package state",
            ],
            warnings=warnings,
        )

    # Build package URL
    from .catalog import catalog_url
    from ..models import CatalogUrlParams
    catalog_params = CatalogUrlParams(
        registry=normalized_registry,
        package_name=params.package_name,
    )
    catalog_result = catalog_url(catalog_params)
    package_url = catalog_result.catalog_url if hasattr(catalog_result, 'catalog_url') else ""

    return PackageUpdateSuccess(
        package_name=params.package_name,
        registry=params.registry,
        top_hash=str(top_hash),
        files_added=len(added),
        package_url=package_url,
        files=added,
        message=params.message,
        warnings=warnings,
        auth_type=auth_ctx.auth_type if auth_ctx else None,
    )


def package_delete(params: PackageDeleteParams) -> PackageDeleteSuccess | PackageDeleteError:
    """Delete a Quilt package from the registry - Core package creation, update, and deletion workflows

    Args:
        params: PackageDeleteParams with package name and registry

    Returns:
        PackageDeleteSuccess with confirmation, or PackageDeleteError on failure.

    Next step:
        Report the package operation result or continue the workflow (e.g., metadata updates).

    Example:
        ```python
        from quilt_mcp.tools import packages
        from quilt_mcp.models import PackageDeleteParams

        params = PackageDeleteParams(package_name="team/dataset")
        result = packages.package_delete(params)
        # Next step: Report the package operation result or continue the workflow (e.g., metadata updates).
        ```
    """
    # Initialize auth_ctx to avoid fragile locals() checks in exception handlers
    auth_ctx: AuthorizationContext | None = None

    if not params.package_name:
        return PackageDeleteError(
            error="package_name is required for package deletion",
            package_name="",
            suggestions=["Provide a package name in format: namespace/name", "Example: team/dataset"],
        )

    try:
        normalized_registry = _normalize_registry(params.registry)
        auth_ctx, error = _authorize_package(
            "package_delete",
            {"package_name": params.package_name, "registry": normalized_registry},
            context={"package_name": params.package_name, "registry": normalized_registry},
        )
        if error:
            return PackageDeleteError(
                error=error.get("error", "Authorization failed"),
                package_name=params.package_name,
                registry=params.registry,
                suggestions=["Check your permissions", "Verify package exists", "Confirm registry access"],
            )

        # Suppress stdout during delete to avoid JSON-RPC interference
        from ..utils import suppress_stdout

        with suppress_stdout():
            quilt3.delete_package(params.package_name, registry=normalized_registry)

        return PackageDeleteSuccess(
            package_name=params.package_name,
            registry=params.registry,
            message=f"Package {params.package_name} deleted successfully",
            auth_type=auth_ctx.auth_type if auth_ctx else None,
        )
    except Exception as e:
        return PackageDeleteError(
            error=f"Failed to delete package '{params.package_name}': {e}",
            package_name=params.package_name,
            registry=params.registry,
            suggestions=[
                "Verify package exists in the registry",
                "Check delete permissions for the registry",
                "Ensure package name is correct",
                "Verify network connectivity",
            ],
        )


def package_create_from_s3(params: PackageCreateFromS3Params) -> PackageCreateFromS3Success | PackageCreateFromS3Error:
    """Create a well-organized Quilt package from S3 bucket contents with smart organization - Bulk S3-to-package ingestion workflows

    Args:
        params: PackageCreateFromS3Params with all configuration options

    Returns:
        PackageCreateFromS3Success with package details, or PackageCreateFromS3Error on failure.

    Next step:
        Review the dry-run output then hand the planned manifest to package_ops.create_package.

    Example:
        ```python
        from quilt_mcp.tools import packages
        from quilt_mcp.models import PackageCreateFromS3Params

        params = PackageCreateFromS3Params(
            source_bucket="my-data-bucket",
            package_name="team/dataset",
        )
        result = packages.package_create_from_s3(params)
        # Next step: Review the dry-run output then hand the planned manifest to package_ops.create_package.
        ```
    """
    try:
        # Validate inputs
        if not validate_package_name(params.package_name):
            return PackageCreateFromS3Error(
                error="Invalid package name format. Use 'namespace/name'",
                package_name=params.package_name,
                suggestions=["Package name must be in format: namespace/name", "Example: team/dataset"],
            )

        if not params.source_bucket:
            return PackageCreateFromS3Error(
                error="source_bucket is required",
                package_name=params.package_name,
                suggestions=["Provide a valid S3 bucket name", "Example: my-data-bucket"],
            )

        # Handle metadata parameter
        processed_metadata = params.metadata.copy() if params.metadata else {}
        readme_content = None

        # Extract README content from metadata and store for later addition as package file
        # readme_content takes priority if both fields exist
        if "readme_content" in processed_metadata:
            readme_content = processed_metadata.pop("readme_content")
        elif "readme" in processed_metadata:
            readme_content = processed_metadata.pop("readme")

        # Validate and normalize bucket name
        if params.source_bucket.startswith("s3://"):
            return PackageCreateFromS3Error(
                error="Invalid bucket name format",
                package_name=params.package_name,
                suggestions=[
                    "Use bucket name only, not full S3 URI",
                    f"Try using: {params.source_bucket.replace('s3://', '')}",
                    "Example: my-bucket (not s3://my-bucket)",
                ],
            )

        # Suggest target registry if not provided using permissions discovery
        target_registry = params.target_registry
        if not target_registry:
            # Try to get smart recommendations based on actual permissions
            try:
                recommendations = bucket_recommendations_get(
                    source_bucket=params.source_bucket, operation_type="package_creation"
                )

                if recommendations.get("success") and recommendations.get("recommendations", {}).get(
                    "primary_recommendations"
                ):
                    # Use the top recommendation
                    top_rec = recommendations["recommendations"]["primary_recommendations"][0]
                    target_registry = f"s3://{top_rec['bucket_name']}"
                    logger.info(f"Using permission-based recommendation: {target_registry}")
                else:
                    # Fallback to pattern-based suggestion
                    target_registry = _suggest_target_registry(params.source_bucket, params.source_prefix)
                    logger.info(f"Using pattern-based suggestion: {target_registry}")

            except Exception as e:
                logger.warning(f"Permission-based recommendation failed, using pattern-based: {e}")
                target_registry = _suggest_target_registry(params.source_bucket, params.source_prefix)
                logger.info(f"Fallback suggestion: {target_registry}")

        # Validate target registry permissions
        target_bucket_name = target_registry.replace("s3://", "")
        try:
            access_check = check_bucket_access(target_bucket_name)
            if not access_check.get("success") or not access_check.get("access_summary", {}).get("can_write"):
                return PackageCreateFromS3Error(
                    error="Cannot create package in target registry",
                    package_name=params.package_name,
                    registry=target_registry,
                    suggestions=[
                        f"Verify you have s3:PutObject permissions for {target_bucket_name}",
                        "Check if you're connected to the right catalog",
                        "Try a different bucket you own",
                        "Try: bucket_recommendations_get() to find writable buckets",
                    ],
                )
        except Exception as e:
            logger.warning(f"Could not validate target registry permissions: {e}")
            # Continue anyway - the user might have permissions that we can't detect

        # Initialize clients
        s3_client = get_s3_client()

        # Validate source bucket access
        try:
            _validate_bucket_access(s3_client, params.source_bucket)
        except Exception as e:
            # Provide friendly error message with helpful suggestions
            error_msg = str(e)
            if "Access denied" in error_msg or "AccessDenied" in error_msg:
                return PackageCreateFromS3Error(
                    error="Cannot access source bucket - insufficient permissions",
                    package_name=params.package_name,
                    suggestions=[
                        f"Verify you have s3:ListBucket and s3:GetObject permissions for {params.source_bucket}",
                        "Check if the bucket name is correct",
                        "Ensure your AWS credentials are properly configured",
                        "Try: check_bucket_access() to diagnose specific permission issues",
                        "Try: bucket_recommendations_get() to find buckets you can access",
                    ],
                )
            else:
                return PackageCreateFromS3Error(
                    error=f"Cannot access source bucket {params.source_bucket}: {str(e)}",
                    package_name=params.package_name,
                    suggestions=["Check bucket name", "Verify AWS credentials", "Check network connectivity"],
                )

        # Discover source objects
        logger.info(f"Discovering objects in s3://{params.source_bucket}/{params.source_prefix}")
        objects = _discover_s3_objects(
            s3_client, params.source_bucket, params.source_prefix, params.include_patterns, params.exclude_patterns
        )

        if not objects:
            return PackageCreateFromS3Error(
                error="No objects found matching the specified criteria",
                package_name=params.package_name,
                suggestions=[
                    "Check if source_prefix is correct",
                    "Verify include_patterns and exclude_patterns",
                    "Ensure the bucket contains files",
                ],
            )

        # Organize file structure
        organized_structure = _organize_file_structure(objects, params.auto_organize)
        total_size = sum(obj.get("Size", 0) for obj in objects)

        # Prepare source information
        source_info = {
            "bucket": params.source_bucket,
            "prefix": params.source_prefix,
            "source_description": (
                f"s3://{params.source_bucket}/{params.source_prefix}"
                if params.source_prefix
                else f"s3://{params.source_bucket}"
            ),
        }

        # Generate comprehensive metadata
        enhanced_metadata = _generate_package_metadata(
            package_name=params.package_name,
            source_info=source_info,
            organized_structure=organized_structure,
            metadata_template=params.metadata_template,
            user_metadata=processed_metadata,
        )

        # Generate README content
        # IMPORTANT: README content is added as a FILE to the package, not as metadata
        final_readme_content = None

        # Use extracted README content from metadata if available, otherwise generate new content
        if readme_content:
            final_readme_content = readme_content
            logger.info("Using README content extracted from metadata")
        elif params.generate_readme:
            final_readme_content = _generate_readme_content(
                package_name=params.package_name,
                description=params.description,
                organized_structure=organized_structure,
                total_size=total_size,
                source_info=source_info,
                metadata_template=params.metadata_template,
            )
            logger.info("Generated new README content")

        summary_files = create_quilt_summary_files(
            package_name=params.package_name,
            package_metadata=enhanced_metadata,
            organized_structure=organized_structure,
            readme_content=final_readme_content or "",
            source_info=source_info,
            metadata_template=params.metadata_template,
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
            "organization_applied": params.auto_organize,
            "readme_generated": params.generate_readme,
            "summary_files_generated": summary_files.get("success", False),
            "visualization_count": summary_files.get("visualization_count", 0),
        }

        # If dry run, return preview without creating
        if params.dry_run:
            return PackageCreateFromS3Success(
                package_name=params.package_name,
                registry=target_registry,
                action="preview",
                structure={"folders_created": list(organized_structure.keys()), "files_organized": len(objects)},
                metadata_info={
                    "package_size_mb": round(total_size / (1024 * 1024), 2),
                    "file_types": list(
                        set(
                            Path(obj["Key"]).suffix.lower().lstrip(".")
                            for obj in objects
                            if Path(obj["Key"]).suffix
                        )
                    ),
                },
                confirmation=confirmation_info,
                message="Preview generated. Set dry_run=False to create the package.",
            )

        # User confirmation step (in real implementation, this would be interactive)
        if params.confirm_structure and not params.force:
            # For now, we'll proceed as if confirmed
            # In a real implementation, this would present the preview to the user
            logger.info("Structure confirmation: proceeding with package creation")

        # Create the actual package
        logger.info(f"Creating package {params.package_name} with enhanced structure")
        package_result = _create_enhanced_package(
            s3_client=s3_client,
            organized_structure=organized_structure,
            source_bucket=params.source_bucket,
            package_name=params.package_name,
            target_registry=target_registry,
            description=params.description,
            enhanced_metadata=enhanced_metadata,
            readme_content=final_readme_content,
            summary_files=summary_files,
            copy_mode=params.copy_mode,
            force=params.force,
        )

        return PackageCreateFromS3Success(
            package_name=params.package_name,
            registry=target_registry,
            action="created",
            structure={
                "folders_created": list(organized_structure.keys()),
                "files_organized": len(objects),
                "readme_generated": params.generate_readme,
            },
            metadata_info={
                "package_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": list(
                    set(Path(obj["Key"]).suffix.lower().lstrip(".") for obj in objects if Path(obj["Key"]).suffix)
                ),
                "organization_applied": ("logical_hierarchy" if params.auto_organize else "flat"),
            },
            confirmation=confirmation_info,
            package_hash=package_result.get("top_hash"),
            created_at=datetime.now(timezone.utc).isoformat(),
            summary_files={
                "quilt_summarize.json": summary_files.get("summary_package", {}).get("quilt_summarize.json", {}),
                "visualizations": summary_files.get("summary_package", {}).get("visualizations", {}),
                "files_generated": summary_files.get("files_generated", {}),
                "visualization_count": summary_files.get("visualization_count", 0),
            },
        )

    except NoCredentialsError:
        return PackageCreateFromS3Error(
            error="AWS credentials not found. Please configure AWS authentication.",
            package_name=params.package_name,
            suggestions=[
                "Configure AWS credentials using aws configure",
                "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables",
                "Check your ~/.aws/credentials file",
            ],
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        return PackageCreateFromS3Error(
            error=f"AWS error ({error_code}): {str(e)}",
            package_name=params.package_name,
            suggestions=["Check AWS permissions", "Verify bucket access", "Check network connectivity"],
        )
    except Exception as e:
        logger.error(f"Error creating package from S3: {str(e)}")
        return PackageCreateFromS3Error(
            error=f"Failed to create package: {str(e)}",
            package_name=params.package_name,
            suggestions=["Check logs for details", "Verify all parameters", "Ensure source bucket is accessible"],
        )
