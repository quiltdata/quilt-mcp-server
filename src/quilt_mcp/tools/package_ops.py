"""Stateless package creation, update, and deletion helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..clients import catalog as catalog_client
from ..constants import DEFAULT_REGISTRY
from ..runtime import get_active_token
from ..utils import format_error_response


def _normalize_registry(bucket_or_uri: str) -> str:
    if not bucket_or_uri:
        return bucket_or_uri

    if bucket_or_uri.startswith(("http://", "https://")):
        return bucket_or_uri.rstrip("/")

    if bucket_or_uri.startswith("s3://"):
        return bucket_or_uri.rstrip("/")

    return f"s3://{bucket_or_uri.strip('/')}"


def _prepare_metadata(
    metadata: dict[str, Any] | str | None,
    warnings: list[str],
    *,
    on_error_message: str,
) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    if metadata is None:
        return {}, None

    if isinstance(metadata, str):
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError as exc:
            return None, {
                "success": False,
                "error": on_error_message,
                "provided": metadata,
                "expected": "Valid JSON object or Python dict",
                "json_error": str(exc),
            }
    elif isinstance(metadata, dict):
        metadata_dict = dict(metadata)
    else:
        return None, {
            "success": False,
            "error": on_error_message,
            "provided_type": type(metadata).__name__,
            "expected": "Dictionary object or JSON string",
        }

    if "readme_content" in metadata_dict:
        metadata_dict.pop("readme_content")
        warnings.append("README content moved from metadata to package file (README.md)")

    if "readme" in metadata_dict:
        metadata_dict.pop("readme")
        warnings.append("README content moved from metadata to package file (README.md)")

    return metadata_dict, None


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
    warnings: list[str] = []
    cleaned_metadata, metadata_error = _prepare_metadata(
        metadata,
        warnings,
        on_error_message="Invalid metadata format",
    )
    if metadata_error is not None:
        return metadata_error

    if not s3_uris:
        return {"error": "No S3 URIs provided"}
    if not package_name:
        return {"error": "Package name is required"}

    normalized_registry = _normalize_registry(registry)
    token = get_active_token()
    if not token:
        error = format_error_response("Authorization token required to create packages")
        error.update({"package_name": package_name, "registry": normalized_registry})
        return error

    try:
        response = catalog_client.catalog_package_create(
            registry_url=normalized_registry,
            package_name=package_name,
            auth_token=token,
            s3_uris=s3_uris,
            metadata=cleaned_metadata,
            message=message,
            flatten=flatten,
            copy_mode=copy_mode,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": f"Failed to create package: {exc}",
            "package_name": package_name,
            "warnings": warnings,
        }

    # Check if the catalog client returned an error
    if not response.get("success", True):
        return {
            "success": False,
            "error": response.get("error", "Unknown error from catalog"),
            "error_type": response.get("error_type"),
            "package_name": package_name,
            "warnings": warnings,
        }

    top_hash = response.get("top_hash")
    entries_added = response.get("entries_added", len(s3_uris))
    response_warnings = response.get("warnings", [])
    if response_warnings:
        warnings.extend(response_warnings)

    result_data = {
        "success": True,
        "status": "success",
        "action": "created",
        "package_name": str(package_name),
        "registry": str(registry),
        "top_hash": str(top_hash),
        "entries_added": entries_added,
        "files": response.get("files", []),
        "metadata_provided": bool(cleaned_metadata),
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
    if not s3_uris:
        return {"error": "No S3 URIs provided"}
    if not package_name:
        return {"error": "package_name is required for package_update"}
    warnings: list[str] = []
    cleaned_metadata, metadata_error = _prepare_metadata(
        metadata,
        warnings,
        on_error_message="Invalid metadata format",
    )
    if metadata_error is not None:
        return metadata_error

    normalized_registry = _normalize_registry(registry)
    token = get_active_token()
    if not token:
        error = format_error_response("Authorization token required to update packages")
        error.update({"package_name": package_name, "registry": normalized_registry})
        return error

    try:
        response = catalog_client.catalog_package_update(
            registry_url=normalized_registry,
            package_name=package_name,
            auth_token=token,
            s3_uris=s3_uris,
            metadata=cleaned_metadata,
            message=message,
            copy_mode=copy_mode,
            flatten=flatten,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": f"Failed to update package: {exc}",
            "package_name": package_name,
            "warnings": warnings,
        }

    warnings.extend(response.get("warnings", []))
    files_added = response.get("files_added")
    if files_added is None:
        files_added = [{"logical_path": uri} for uri in s3_uris]

    result = {
        "success": True,
        "status": "success",
        "action": "updated",
        "package_name": str(package_name),
        "registry": str(registry),
        "top_hash": str(response.get("top_hash")),
        "new_entries_added": len(files_added),
        "files_added": files_added,
        "warnings": warnings,
        "message": str(message),
        "metadata_added": bool(cleaned_metadata),
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
    normalized_registry = _normalize_registry(registry)
    token = get_active_token()
    if not token:
        error = format_error_response("Authorization token required to delete packages")
        error.update({"package_name": package_name, "registry": normalized_registry})
        return error

    try:
        catalog_client.catalog_package_delete(
            registry_url=normalized_registry,
            package_name=package_name,
            auth_token=token,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": f"Failed to delete package '{package_name}': {exc}",
            "package_name": package_name,
            "registry": registry,
        }

    return {
        "success": True,
        "status": "success",
        "action": "deleted",
        "package_name": package_name,
        "registry": registry,
        "message": f"Package {package_name} deleted successfully",
    }


def package_ops(action: str | None = None, params: Optional[Dict[str, Any]] = None) -> dict[str, Any]:
    """
    Package creation, update, and deletion operations.

    Available actions:
    - create: Create a new Quilt package from S3 objects
    - update: Update an existing Quilt package by adding new S3 objects
    - delete: Delete a Quilt package from the registry

    Args:
        action: The operation to perform. If None, returns available actions.
        **kwargs: Action-specific parameters

    Returns:
        Action-specific response dictionary

    Examples:
        # Discovery mode
        result = package_ops()

        # Create package
        result = package_ops(action="create", package_name="user/dataset", s3_uris=["s3://bucket/file.csv"])

        # Update package
        result = package_ops(action="update", package_name="user/dataset", s3_uris=["s3://bucket/newfile.csv"])

    For detailed parameter documentation, see individual action functions.
    """
    actions = {
        "create": package_create,
        "delete": package_delete,
        "update": package_update,
    }

    # Discovery mode
    if action is None:
        return {
            "success": True,
            "module": "package_ops",
            "actions": list(actions.keys()),
            "usage": "Call with action='<action_name>' to execute",
        }

    # Validate action
    if action not in actions:
        available = ", ".join(sorted(actions.keys()))
        return {
            "success": False,
            "error": f"Unknown action '{action}' for module 'package_ops'. Available actions: {available}",
        }

    # Dispatch
    try:
        func = actions[action]
        params = params or {}
        return func(**params)
    except TypeError as e:
        import inspect

        sig = inspect.signature(func)
        expected_params = list(sig.parameters.keys())
        return {
            "success": False,
            "error": f"Invalid parameters for action '{action}'. Expected: {expected_params}. Error: {str(e)}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error executing action '{action}': {str(e)}",
        }
