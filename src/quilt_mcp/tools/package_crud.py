"""Core package CRUD/browse/diff operations extracted from tools.packages."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from pydantic import Field

from .auth_helpers import AuthorizationContext, check_package_authorization
from .responses import (
    CatalogUrlSuccess,
    ErrorResponse,
    PackageBrowseSuccess,
    PackageCreateError,
    PackageCreateSuccess,
    PackageDeleteError,
    PackageDeleteSuccess,
    PackageDiffError,
    PackageDiffSuccess,
    PackageSummary,
    PackageUpdateError,
    PackageUpdateSuccess,
    PackagesListError,
    PackagesListSuccess,
)
from .validation import (
    normalize_registry,
    validate_metadata_dict,
    validate_package_name_required,
    validate_registry_required,
    validate_s3_uris_required,
)
from ..ops.factory import QuiltOpsFactory


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


def _add_to_file_tree(tree: dict, path: str, entry_data: dict, max_depth: int):
    if max_depth > 0 and path.count("/") >= max_depth:
        return
    parts = path.split("/")
    current = tree
    for part in parts[:-1]:
        if part not in current:
            current[part] = {"type": "directory", "children": {}}
        current = current[part]["children"]
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
    if size_bytes is None:
        return "Unknown"
    size_float = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_float < 1024.0:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024.0
    return f"{size_float:.1f} PB"


def packages_list(
    registry: Annotated[
        str,
        Field(
            default="",
            description="Optional Quilt registry S3 URI to list packages from. Empty string lists all accessible packages.",
        ),
    ] = "",
    limit: Annotated[
        int,
        Field(
            default=0,
            ge=0,
            description="Maximum number of packages to return, 0 for unlimited",
        ),
    ] = 0,
    prefix: Annotated[
        str,
        Field(
            default="",
            description="Filter packages by name prefix",
            examples=["", "team/", "user/analysis-"],
        ),
    ] = "",
) -> PackagesListSuccess | PackagesListError:
    if not registry:
        return PackagesListError(
            error="Registry parameter is required for package listing. Specify target S3 bucket (e.g., registry='s3://my-bucket')",
            registry="",
            suggested_actions=[
                "Provide a registry parameter",
                "Example: packages_list(registry='s3://my-bucket')",
                "Use bucket_recommendations_get() to find accessible buckets",
            ],
        )

    normalized_registry = normalize_registry(registry)
    try:
        from ..utils.common import suppress_stdout

        quilt_ops = QuiltOpsFactory.create()
        with suppress_stdout():
            package_infos = quilt_ops.search_packages(query="", registry=normalized_registry)
            package_names = [pkg_info.name for pkg_info in package_infos]

        if prefix:
            package_names = [pkg for pkg in package_names if pkg.startswith(prefix)]
        if limit > 0:
            package_names = package_names[:limit]

        return PackagesListSuccess(
            registry=registry,
            count=len(package_names),
            packages=package_names,
            prefix_filter=prefix if prefix else None,
        )
    except Exception as e:
        return PackagesListError(
            error=f"Failed to list packages: {e}",
            registry=registry,
            suggested_actions=[
                "Verify registry is accessible",
                "Check AWS permissions for the bucket",
                "Ensure registry S3 URI is valid (e.g., s3://my-bucket)",
                "Use bucket_recommendations_get() to find accessible buckets",
            ],
        )


def package_browse(
    package_name: Annotated[
        str,
        Field(
            description="Name of the package in namespace/name format",
            examples=["username/dataset", "team/analysis-results"],
            pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$",
        ),
    ],
    registry: Annotated[
        str,
        Field(
            description="Quilt registry S3 URI (REQUIRED)",
            examples=["s3://my-bucket", "s3://quilt-example"],
        ),
    ],
    recursive: Annotated[
        bool, Field(default=True, description="Show full file tree (true) or just top-level entries (false)")
    ] = True,
    include_file_info: Annotated[
        bool, Field(default=True, description="Include file sizes, types, and modification dates")
    ] = True,
    max_depth: Annotated[
        int, Field(default=0, ge=0, description="Maximum directory depth to show (0 for unlimited)")
    ] = 0,
    top: Annotated[int, Field(default=0, ge=0, description="Limit number of entries returned (0 for unlimited)")] = 0,
    include_signed_urls: Annotated[
        bool, Field(default=True, description="Include presigned download URLs for S3 objects")
    ] = True,
) -> PackageBrowseSuccess | ErrorResponse:
    ok_registry, registry_error, registry_actions = validate_registry_required(registry, "package_browse")
    if not ok_registry:
        return ErrorResponse(
            error=registry_error,
            possible_fixes=registry_actions,
            suggested_actions=[
                "Use bucket_recommendations_get() to find accessible buckets",
                "Check which bucket contains your package",
            ],
        )

    normalized_registry = normalize_registry(registry)
    try:
        from ..utils.common import suppress_stdout

        quilt_ops = QuiltOpsFactory.create()
        with suppress_stdout():
            content_infos = quilt_ops.browse_content(package_name, registry=normalized_registry, path="")
            try:
                pkg_metadata = quilt_ops.get_package_metadata(package_name, registry=normalized_registry)
            except Exception:
                pkg_metadata = None
    except Exception as e:
        return ErrorResponse(error=f"Failed to browse package '{package_name}'", cause=str(e))

    entries = []
    file_tree: dict[str, Any] | None = {} if recursive else None
    total_size = 0
    file_types = set()
    content_list = content_infos[:top] if top > 0 else content_infos

    for content_info in content_list:
        logical_key = content_info.path
        file_size = content_info.size
        is_directory = content_info.type == "directory"
        file_ext = logical_key.split(".")[-1].lower() if "." in logical_key and not is_directory else "unknown"
        file_types.add(file_ext)
        if file_size:
            total_size += file_size
        entry_data = {
            "logical_key": logical_key,
            "physical_key": None,
            "size": file_size,
            "size_human": _format_file_size(file_size) if file_size else None,
            "hash": "unknown",
            "file_type": file_ext,
            "is_directory": is_directory,
        }
        if include_file_info and content_info.download_url:
            entry_data["physical_key"] = content_info.download_url
            if content_info.modified_date:
                entry_data["last_modified"] = content_info.modified_date
        if include_signed_urls and content_info.download_url:
            entry_data["download_url"] = content_info.download_url
            entry_data["s3_uri"] = content_info.download_url
        entries.append(entry_data)
        if recursive and file_tree is not None:
            _add_to_file_tree(file_tree, logical_key, entry_data, max_depth)

    summary = PackageSummary(
        total_size=total_size,
        total_size_human=_format_file_size(total_size),
        file_types=sorted(list(file_types)),
        total_files=len([e for e in entries if not e.get("is_directory", False)]),
        total_directories=len([e for e in entries if e.get("is_directory", False)]),
    )

    return PackageBrowseSuccess(
        package_name=package_name,
        registry=registry,
        total_entries=len(entries),
        summary=summary,
        view_type="recursive" if recursive else "flat",
        file_tree=file_tree if recursive and file_tree else None,
        entries=entries,
        metadata=pkg_metadata,
    )


def package_diff(
    package1_name: str,
    package2_name: str,
    registry: str,
    package1_hash: str = "",
    package2_hash: str = "",
) -> PackageDiffSuccess | PackageDiffError:
    ok_registry, registry_error, registry_actions = validate_registry_required(registry, "package_diff")
    if not ok_registry:
        return PackageDiffError(
            error=registry_error, package1=package1_name, package2=package2_name, suggested_actions=registry_actions
        )
    normalized_registry = normalize_registry(registry)
    try:
        from ..utils.common import suppress_stdout

        quilt_ops = QuiltOpsFactory.create()
        with suppress_stdout():
            diff_dict = quilt_ops.diff_packages(
                package1_name=package1_name,
                package2_name=package2_name,
                registry=normalized_registry,
                package1_hash=package1_hash if package1_hash else None,
                package2_hash=package2_hash if package2_hash else None,
            )
        return PackageDiffSuccess(
            package1=package1_name,
            package2=package2_name,
            package1_hash=package1_hash if package1_hash else "latest",
            package2_hash=package2_hash if package2_hash else "latest",
            registry=registry,
            diff=diff_dict,
        )
    except Exception as e:
        return PackageDiffError(error=f"Failed to diff packages: {e}", package1=package1_name, package2=package2_name)


def package_create(
    package_name: str,
    s3_uris: list[str],
    registry: str,
    metadata: Optional[dict[str, Any]] = None,
    message: str = "Created via package_create tool",
    flatten: bool = True,
    copy: bool = False,
) -> PackageCreateSuccess | PackageCreateError:
    ok_registry, registry_error, registry_actions = validate_registry_required(registry, "package_create")
    if not ok_registry:
        return PackageCreateError(
            error=registry_error, package_name=package_name, registry="", suggested_actions=registry_actions
        )
    ok_uris, uris_error, uris_actions = validate_s3_uris_required(s3_uris)
    if not ok_uris:
        return PackageCreateError(error=uris_error, package_name=package_name, suggested_actions=uris_actions)
    ok_package, package_error, package_actions = validate_package_name_required(package_name, "package_create")
    if not ok_package:
        return PackageCreateError(error=package_error, package_name="", suggested_actions=package_actions)
    ok_meta, meta_error, _, meta_actions = validate_metadata_dict(metadata, package_name=package_name)
    if not ok_meta:
        return PackageCreateError(
            error=meta_error,
            package_name=package_name,
            provided_type=type(metadata).__name__,
            suggested_actions=meta_actions,
        )

    auth_ctx, error = _authorize_package(
        "package_create",
        {"package_name": package_name, "registry": normalize_registry(registry)},
        context={"package_name": package_name, "registry": normalize_registry(registry)},
    )
    if error:
        return PackageCreateError(
            error=error.get("error", "Authorization failed"), package_name=package_name, registry=registry
        )

    try:
        quilt_ops = QuiltOpsFactory.create()
        result = quilt_ops.create_package_revision(
            package_name=package_name,
            s3_uris=s3_uris,
            metadata=(metadata or {}),
            registry=normalize_registry(registry),
            message=message,
            auto_organize=False,
            copy=copy,
        )
        if not result.success:
            return PackageCreateError(error="Package creation failed", package_name=package_name, registry=registry)
        from .catalog import catalog_url

        catalog_result = catalog_url(
            registry=normalize_registry(registry), package_name=package_name, path="", catalog_host=""
        )
        package_url = catalog_result.catalog_url if isinstance(catalog_result, CatalogUrlSuccess) else ""
        return PackageCreateSuccess(
            package_name=package_name,
            registry=registry,
            top_hash=str(result.top_hash),
            files_added=result.file_count,
            package_url=package_url,
            files=[],
            message=message,
            warnings=[],
            auth_type=auth_ctx.auth_type if auth_ctx else None,
        )
    except Exception as e:
        return PackageCreateError(error=f"Failed to create package: {e}", package_name=package_name, registry=registry)


def package_update(
    package_name: str,
    s3_uris: list[str],
    registry: str,
    metadata: Optional[dict[str, Any]] = None,
    message: str = "Added objects via package_update tool",
    flatten: bool = True,
    copy: bool = False,
) -> PackageUpdateSuccess | PackageUpdateError:
    ok_registry, registry_error, registry_actions = validate_registry_required(registry, "package_update")
    if not ok_registry:
        return PackageUpdateError(
            error=registry_error, package_name=package_name, registry="", suggested_actions=registry_actions
        )
    ok_uris, uris_error, uris_actions = validate_s3_uris_required(s3_uris)
    if not ok_uris:
        return PackageUpdateError(error=uris_error, package_name=package_name, suggested_actions=uris_actions)
    ok_package, package_error, package_actions = validate_package_name_required(package_name, "package_update")
    if not ok_package:
        return PackageUpdateError(error=package_error, package_name="", suggested_actions=package_actions)
    ok_meta, meta_error, _, meta_actions = validate_metadata_dict(metadata, package_name=package_name)
    if not ok_meta:
        return PackageUpdateError(error=meta_error, package_name=package_name, suggested_actions=meta_actions)

    auth_ctx, error = _authorize_package(
        "package_update",
        {"package_name": package_name, "registry": normalize_registry(registry)},
        context={"package_name": package_name, "registry": normalize_registry(registry)},
    )
    if error:
        return PackageUpdateError(
            error=error.get("error", "Authorization failed"), package_name=package_name, registry=registry
        )

    try:
        from ..utils.common import suppress_stdout

        quilt_ops = QuiltOpsFactory.create()
        with suppress_stdout():
            result = quilt_ops.update_package_revision(
                package_name=package_name,
                s3_uris=s3_uris,
                registry=normalize_registry(registry),
                metadata=metadata,
                message=message,
                auto_organize=not flatten,
                copy=("all" if copy else "none"),
            )
        if not result.success:
            return PackageUpdateError(
                error="Package update failed - no files were added or push failed",
                package_name=package_name,
                registry=registry,
            )
        return PackageUpdateSuccess(
            package_name=package_name,
            registry=registry,
            top_hash=str(result.top_hash),
            files_added=result.file_count,
            package_url=result.catalog_url or "",
            files=[],
            message=message,
            warnings=[],
            auth_type=auth_ctx.auth_type if auth_ctx else None,
        )
    except Exception as e:
        return PackageUpdateError(error=f"Package update failed: {e}", package_name=package_name, registry=registry)


def package_delete(package_name: str, registry: str) -> PackageDeleteSuccess | PackageDeleteError:
    ok_registry, registry_error, registry_actions = validate_registry_required(registry, "package_delete")
    if not ok_registry:
        return PackageDeleteError(
            error=registry_error, package_name=package_name, registry="", suggested_actions=registry_actions
        )
    normalized_registry = normalize_registry(registry)
    auth_ctx, error = _authorize_package(
        "package_delete",
        {"package_name": package_name, "registry": normalized_registry},
        context={"package_name": package_name, "registry": normalized_registry},
    )
    if error:
        return PackageDeleteError(
            error=error.get("error", "Authorization failed"), package_name=package_name, registry=registry
        )
    try:
        backend = QuiltOpsFactory.create()
        deleted = backend.delete_package(name=package_name, bucket=normalized_registry)
        if not deleted:
            return PackageDeleteError(
                error=f"Failed to delete package '{package_name}'", package_name=package_name, registry=registry
            )
        return PackageDeleteSuccess(
            package_name=package_name,
            registry=registry,
            message=f"Package {package_name} deleted successfully",
            auth_type=auth_ctx.auth_type if auth_ctx else None,
        )
    except Exception as e:
        return PackageDeleteError(
            error=f"Failed to delete package '{package_name}': {e}", package_name=package_name, registry=registry
        )
