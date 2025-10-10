from __future__ import annotations

"""
Package creation and management operations.

This module provides core functionality for creating and managing Quilt packages,
including S3 object collection, metadata handling, and package pushing.

IMPORTANT: This module automatically ensures that README content is always written
as README.md files within packages, never stored in package metadata. Any
'readme_content' or 'readme' fields in metadata will be automatically extracted
and converted to package files.
"""

import os
from typing import Any

from ..constants import DEFAULT_REGISTRY
from ..services.quilt_service import QuiltService

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


# Internal helper replicated from monolith (will be removed there)


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


def package_create(
    package_name: str,
    s3_uris: list[str],
    registry: str = DEFAULT_REGISTRY,
    metadata: dict[str, Any] | None = None,
    message: str = "Created via package_create tool",
    flatten: bool = True,
    copy_mode: str = "all",
) -> dict[str, Any]:
    """Create a new Quilt package from S3 objects.

    Args:
        package_name: Name for the new package (e.g., "username/package-name")
        s3_uris: List of S3 URIs to include in the package
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        metadata: Optional metadata dict to attach to the package (JSON object, not string)
        message: Commit message for package creation (default: "Created via package_create tool")
        flatten: Use only filenames as logical paths instead of full S3 keys (default: True)

    Returns:
        Dict with creation status, package details, and list of files added.

    Examples:
        Basic package creation:
        package_create("my-team/dataset", ["s3://bucket/file.csv"])

        With metadata:
        package_create(
            "my-team/dataset",
            ["s3://bucket/file.csv"],
            metadata={"description": "My dataset", "type": "research"}
        )
    """
    # Handle metadata parameter - support both dict and JSON string for user convenience
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
                "examples": [
                    '{"description": "My dataset", "type": "research"}',
                    '{"created_by": "analyst", "project": "Q1-analysis"}',
                ],
                "tip": "Ensure JSON is properly formatted with quotes around keys and string values",
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
            "tip": "Pass metadata as a dictionary object, not as individual parameters",
        }

    warnings: list[str] = []
    if not s3_uris:
        return {"error": "No S3 URIs provided"}
    if not package_name:
        return {"error": "Package name is required"}

    # Process metadata to ensure README content is handled correctly
    processed_metadata = metadata.copy() if metadata else {}

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

    normalized_registry = _normalize_registry(registry)

    try:
        # Use the new create_package_revision method with auto_organize=False
        # to preserve the existing flattening behavior
        result = quilt_service.create_package_revision(
            package_name=package_name,
            s3_uris=s3_uris,
            metadata=processed_metadata,
            registry=normalized_registry,
            message=message,
            auto_organize=False,  # Preserve flattening behavior like _collect_objects_into_package
            copy=copy_mode,
        )

        # Handle the result based on its structure
        if result.get("error"):
            return {
                "error": result["error"],
                "package_name": package_name,
                "warnings": warnings,
            }

        # Extract the top_hash from the result
        top_hash = result.get("top_hash")
        entries_added = result.get("entries_added", len(s3_uris))

    except Exception as e:
        return {
            "error": f"Failed to create package: {e}",
            "package_name": package_name,
            "warnings": warnings,
        }

    # Ensure all values are JSON serializable
    result_data = {
        "status": "success",
        "action": "created",
        "package_name": str(package_name),
        "registry": str(registry),
        "top_hash": str(top_hash),
        "entries_added": entries_added,
        "files": result.get("files", []),  # Use files from create_package_revision if available
        "metadata_provided": bool(metadata),
        "warnings": warnings,
        "message": str(message),
    }
    return result_data


def package_update(
    package_name: str,
    s3_uris: list[str],
    registry: str = DEFAULT_REGISTRY,
    metadata: dict[str, Any] | None = None,
    message: str = "Added objects via package_update tool",
    flatten: bool = True,
    copy_mode: str = "all",
) -> dict[str, Any]:
    """Update an existing Quilt package by adding new S3 objects.

    Args:
        package_name: Name of the existing package to update (e.g., "username/package-name")
        s3_uris: List of S3 URIs to add to the package
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)
        metadata: Optional metadata dict to merge with existing package metadata
        message: Commit message for package update (default: "Added objects via package_update tool")
        flatten: Use only filenames as logical paths instead of full S3 keys (default: True)

    Returns:
        Dict with update status, package details, and list of files added.
    """
    # Handle metadata parameter - support both dict and JSON string for user convenience
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
                "examples": [
                    '{"description": "Updated dataset", "version": "2.0"}',
                    '{"tags": ["updated", "v2"], "quality": "validated"}',
                ],
                "tip": "Ensure JSON is properly formatted with quotes around keys and string values",
            }
    elif not isinstance(metadata, dict):
        return {
            "success": False,
            "error": "Invalid metadata type",
            "provided_type": type(metadata).__name__,
            "expected": "Dictionary object or JSON string",
            "examples": [
                '{"description": "Updated dataset", "version": "2.0"}',
                '{"tags": ["updated", "v2"], "author": "scientist"}',
            ],
            "tip": "Pass metadata as a dictionary object, not as individual parameters",
        }

    if not s3_uris:
        return {"error": "No S3 URIs provided"}
    if not package_name:
        return {"error": "package_name is required for package_update"}
    warnings: list[str] = []
    normalized_registry = _normalize_registry(registry)
    try:
        # Suppress stdout during browse to avoid JSON-RPC interference
        from ..utils import suppress_stdout

        with suppress_stdout():
            quilt_service = QuiltService()
            existing_pkg = quilt_service.browse_package(package_name, registry=normalized_registry)
    except Exception as e:
        return {
            "error": f"Failed to browse existing package '{package_name}': {e}",
            "package_name": package_name,
        }
    # Use the existing package as the base instead of creating a new one
    updated_pkg = existing_pkg
    added = _collect_objects_into_package(updated_pkg, s3_uris, flatten, warnings)
    if not added:
        return {"error": "No new S3 objects were added", "warnings": warnings}
    if metadata:
        try:
            combined = {}
            try:
                combined.update(existing_pkg.meta)  # type: ignore[arg-type]
            except Exception:
                pass
            combined.update(metadata)
            updated_pkg.set_meta(combined)
        except Exception as e:
            warnings.append(f"Failed to set merged metadata: {e}")
    try:
        # Suppress stdout during push to avoid JSON-RPC interference
        from ..utils import suppress_stdout

        with suppress_stdout():
            selector_fn = _build_selector_fn(copy_mode, normalized_registry)
            top_hash = updated_pkg.push(
                package_name,
                registry=normalized_registry,
                message=message,
                selector_fn=selector_fn,
                force=True,
            )

    except Exception as e:
        return {
            "error": f"Failed to push updated package: {e}",
            "package_name": package_name,
            "warnings": warnings,
        }

    # Convert non-string values to ensure JSON serialization
    result = {
        "status": "success",
        "action": "updated",
        "package_name": str(package_name),
        "registry": str(registry),
        "top_hash": str(top_hash),
        "new_entries_added": len(added),
        "files_added": added,
        "warnings": warnings,
        "message": str(message),
        "metadata_added": bool(metadata),
    }
    return result


def package_delete(package_name: str, registry: str = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Delete a Quilt package from the registry.

    Args:
        package_name: Name of the package to delete (e.g., "username/package-name")
        registry: Quilt registry URL (default: DEFAULT_REGISTRY)

    Returns:
        Dict with deletion status and confirmation message.
    """
    if not package_name:
        return {"error": "package_name is required for package deletion"}

    try:
        normalized_registry = _normalize_registry(registry)
        # Suppress stdout during delete to avoid JSON-RPC interference
        from ..utils import suppress_stdout

        with suppress_stdout():
            quilt3.delete_package(package_name, registry=normalized_registry)
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
