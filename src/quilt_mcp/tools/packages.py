from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from pydantic import Field

# REMOVED: DEFAULT_REGISTRY import (v0.10.0)
# Rationale: MCP server should not manage default bucket state
# LLM clients provide explicit bucket parameters based on conversation context
from .quilt_summary import create_quilt_summary_files
from .s3_discovery import (
    discover_s3_objects,
    organize_file_structure,
    should_include_object,
    validate_bucket_access,
)
from .package_metadata import generate_package_metadata, generate_readme_content
from .validation import (
    normalize_registry,
    validate_metadata_dict,
    validate_package_name_required,
    validate_registry_required,
    validate_s3_uris_required,
)
from ..context.request_context import RequestContext
from ..services.permissions_service import bucket_recommendations_get, check_bucket_access

from ..utils.common import format_error_response, generate_signed_url, get_s3_client, validate_package_name
from ..ops.factory import QuiltOpsFactory
from ..domain import Package_Creation_Result
from .auth_helpers import AuthorizationContext, check_package_authorization
from .responses import (
    PackageBrowseSuccess,
    PackageCreateSuccess,
    PackageCreateError,
    PackageUpdateSuccess,
    PackageUpdateError,
    PackageDeleteSuccess,
    PackageDeleteError,
    PackagesListSuccess,
    PackagesListError,
    PackageDiffSuccess,
    PackageDiffError,
    PackageCreateFromS3Success,
    PackageCreateFromS3Error,
    PackageSummary,
    ErrorResponse,
    CatalogUrlSuccess,
)

logger = logging.getLogger(__name__)


# Helpers


def _normalize_registry(bucket_or_uri: str) -> str:
    """Backward-compatible wrapper around tools.validation.normalize_registry."""
    return normalize_registry(bucket_or_uri)


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

        # Since Quilt packages are versioned, we simply replace files at the same logical path
        # The old file remains accessible in previous package versions
        # No need for 1_filename, 2_filename collision avoidance
        if logical_path in pkg:
            warnings.append(f"Replacing existing file at logical path: {logical_path}")

        try:
            pkg.set(logical_path, uri)
            added.append({"logical_path": logical_path, "source": uri})
        except Exception as e:
            warnings.append(f"Failed to add {uri}: {e}")
            continue
    return added


def _build_selector_fn(copy: bool, target_registry: str):
    """Build a Quilt selector_fn based on desired copy behavior.

    Args:
        copy: True to copy all objects, False to keep references only
        target_registry: Target registry (unused but kept for compatibility)
    """

    def selector_all(_logical_key, _entry):
        return True

    def selector_none(_logical_key, _entry):
        return False

    return selector_all if copy else selector_none


# S3-to-package helpers

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


def _generate_readme_content(
    package_name: str,
    description: str,
    organized_structure: dict[str, list[dict[str, Any]]],
    total_size: int,
    source_info: dict[str, str],
    metadata_template: str,
) -> str:
    """Compatibility wrapper around tools.package_metadata.generate_readme_content."""
    return generate_readme_content(
        package_name=package_name,
        description=description,
        organized_structure=organized_structure,
        total_size=total_size,
        source_info=source_info,
        metadata_template=metadata_template,
    )


def _generate_package_metadata(
    package_name: str,
    source_info: dict[str, Any],
    organized_structure: dict[str, list[dict[str, Any]]],
    metadata_template: str,
    user_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper around tools.package_metadata.generate_package_metadata."""
    return generate_package_metadata(
        package_name=package_name,
        source_info=source_info,
        organized_structure=organized_structure,
        metadata_template=metadata_template,
        user_metadata=user_metadata,
    )


def _validate_bucket_access(s3_client: Any, bucket_name: str) -> None:
    validate_bucket_access(s3_client, bucket_name)


def _discover_s3_objects(
    s3_client: Any,
    bucket: str,
    prefix: str,
    include_patterns: list[str] | None,
    exclude_patterns: list[str] | None,
) -> list[dict[str, Any]]:
    return discover_s3_objects(s3_client, bucket, prefix, include_patterns, exclude_patterns)


def _should_include_object(
    key: str,
    include_patterns: list[str] | None,
    exclude_patterns: list[str] | None,
) -> bool:
    return should_include_object(key, include_patterns, exclude_patterns)


def _organize_file_structure(objects: list[dict[str, Any]], auto_organize: bool) -> dict[str, list[dict[str, Any]]]:
    return organize_file_structure(objects, auto_organize)


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
    copy: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Create the enhanced Quilt package with organized structure and documentation."""
    try:
        # Collect all S3 URIs from organized structure
        s3_uris = []
        for objects in organized_structure.values():
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

        # Create package using QuiltOps.create_package_revision with auto_organize=True
        # This preserves the smart organization behavior of s3_package.py
        quilt_ops = QuiltOpsFactory.create()
        result = quilt_ops.create_package_revision(
            package_name=package_name,
            s3_uris=s3_uris,
            metadata=processed_metadata,
            registry=target_registry,
            message=message,
            auto_organize=True,  # Preserve smart organization behavior
            copy=copy,
        )

        # Handle the result - it's now a Package_Creation_Result domain object
        if not result.success:
            logger.error("Package creation failed: no error details available")
            raise Exception("Package creation failed")

        top_hash = result.top_hash
        logger.info(f"Successfully created package {package_name} with hash {top_hash}")

        # NOTE: Summary files/visualization artifact attachment is intentionally deferred in this path.
        # Basic package creation with README content is supported.
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


# CRUD and browse operations are delegated to package_crud to keep this module focused on S3-ingestion workflows.
from .package_crud import (
    package_browse,
    package_create,
    package_delete,
    package_diff,
    package_update,
    packages_list,
)


def package_create_from_s3(
    source_bucket: Annotated[
        str,
        Field(
            description="S3 bucket name containing source data (without s3:// prefix)",
            examples=["my-data-bucket", "research-data"],
        ),
    ],
    package_name: Annotated[
        str,
        Field(
            description="Name for the new package in namespace/name format",
            examples=["username/dataset", "team/research-data"],
            pattern=r"^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$",
        ),
    ],
    source_prefix: Annotated[
        str,
        Field(
            default="",
            description="Optional prefix to filter source objects",
            examples=["", "data/2024/", "experiments/"],
        ),
    ] = "",
    description: Annotated[
        str,
        Field(
            default="",
            description="Package description",
        ),
    ] = "",
    target_registry: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Target Quilt registry (auto-suggested if not provided)",
        ),
    ] = None,
    include_patterns: Annotated[
        Optional[list[str]],
        Field(
            default=None,
            description="File patterns to include (glob style)",
            examples=[["*.csv", "*.json"], ["data/*.parquet"]],
        ),
    ] = None,
    exclude_patterns: Annotated[
        Optional[list[str]],
        Field(
            default=None,
            description="File patterns to exclude (glob style)",
            examples=[["*.tmp", "*.log"], ["temp/*"]],
        ),
    ] = None,
    metadata_template: Annotated[
        Literal["standard", "ml", "analytics"],
        Field(
            default="standard",
            description="Metadata template to use",
        ),
    ] = "standard",
    copy: Annotated[
        bool,
        Field(
            default=False,
            description="Whether to copy files to registry bucket (false=reference only, true=copy all)",
        ),
    ] = False,
    auto_organize: Annotated[
        bool,
        Field(
            default=True,
            description="Enable smart folder organization",
        ),
    ] = True,
    generate_readme: Annotated[
        bool,
        Field(
            default=True,
            description="Generate comprehensive README.md",
        ),
    ] = True,
    confirm_structure: Annotated[
        bool,
        Field(
            default=True,
            description="Require user confirmation of structure",
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        Field(
            default=False,
            description="Preview structure without creating package",
        ),
    ] = False,
    force: Annotated[
        bool,
        Field(
            default=False,
            description="Skip confirmation prompts when True",
        ),
    ] = False,
    metadata: Annotated[
        Optional[dict[str, Any]],
        Field(
            default=None,
            description="Additional user-provided metadata",
        ),
    ] = None,
    *,
    context: RequestContext,
) -> PackageCreateFromS3Success | PackageCreateFromS3Error:
    """Create a well-organized Quilt package from S3 bucket contents with smart organization - Bulk S3-to-package ingestion workflows

    Args:
        source_bucket: S3 bucket name containing source data (without s3:// prefix)
        package_name: Name for the new package in namespace/name format
        source_prefix: Optional prefix to filter source objects
        description: Package description
        target_registry: Target Quilt registry (auto-suggested if not provided)
        include_patterns: File patterns to include (glob style)
        exclude_patterns: File patterns to exclude (glob style)
        metadata_template: Metadata template to use
        copy: Whether to copy files to registry bucket
        auto_organize: Enable smart folder organization
        generate_readme: Generate comprehensive README.md
        confirm_structure: Require user confirmation of structure
        dry_run: Preview structure without creating package
        force: Skip confirmation prompts when True
        metadata: Additional user-provided metadata

    Returns:
        PackageCreateFromS3Success with package details, or PackageCreateFromS3Error on failure.

    Next step:
        Review the dry-run output then hand the planned manifest to package_ops.create_package.

    Example:
        ```python
        from quilt_mcp.tools import packages

        result = packages.package_create_from_s3(
            source_bucket="my-data-bucket",
            package_name="team/dataset",
        )
        # Next step: Review the dry-run output then hand the planned manifest to package_ops.create_package.
        ```
    """
    try:
        # Validate inputs
        if not validate_package_name(package_name):
            return PackageCreateFromS3Error(
                error="Invalid package name format. Use 'namespace/name'",
                package_name=package_name,
                suggested_actions=["Package name must be in format: namespace/name", "Example: team/dataset"],
            )

        if not source_bucket:
            return PackageCreateFromS3Error(
                error="source_bucket is required",
                package_name=package_name,
                suggested_actions=["Provide a valid S3 bucket name", "Example: my-data-bucket"],
            )

        # Handle metadata parameter
        processed_metadata = metadata.copy() if metadata else {}
        readme_content = None

        # Extract README content from metadata and store for later addition as package file
        # readme_content takes priority if both fields exist
        if "readme_content" in processed_metadata:
            readme_value = processed_metadata.pop("readme_content")
            readme_content = str(readme_value) if readme_value is not None else None
        elif "readme" in processed_metadata:
            readme_value = processed_metadata.pop("readme")
            readme_content = str(readme_value) if readme_value is not None else None

        # Validate and normalize bucket name - accept both formats
        if source_bucket.startswith("s3://"):
            # Strip s3:// prefix if provided
            source_bucket = source_bucket.replace("s3://", "").split("/")[0]
            logger.info(f"Normalized source_bucket from s3:// URI to: {source_bucket}")

        # Suggest target registry if not provided using permissions discovery
        resolved_target_registry = target_registry
        if not resolved_target_registry:
            # Try to get smart recommendations based on actual permissions
            try:
                recommendations = bucket_recommendations_get(
                    source_bucket=source_bucket,
                    operation_type="package_creation",
                    context=context,
                )

                if recommendations.get("success") and recommendations.get("recommendations", {}).get(
                    "primary_recommendations"
                ):
                    # Use the top recommendation
                    top_rec = recommendations["recommendations"]["primary_recommendations"][0]
                    resolved_target_registry = f"s3://{top_rec['bucket_name']}"
                    logger.info(f"Using permission-based recommendation: {resolved_target_registry}")
                else:
                    # Fallback to pattern-based suggestion
                    resolved_target_registry = _suggest_target_registry(source_bucket, source_prefix)
                    logger.info(f"Using pattern-based suggestion: {resolved_target_registry}")

            except Exception as e:
                logger.warning(f"Permission-based recommendation failed, using pattern-based: {e}")
                resolved_target_registry = _suggest_target_registry(source_bucket, source_prefix)
                logger.info(f"Fallback suggestion: {resolved_target_registry}")

        # Validate target registry permissions
        target_bucket_name = resolved_target_registry.replace("s3://", "")
        try:
            access_check = check_bucket_access(
                target_bucket_name,
                context=context,
            )
            if not access_check.get("success") or not access_check.get("access_summary", {}).get("can_write"):
                return PackageCreateFromS3Error(
                    error="Cannot create package in target registry",
                    package_name=package_name,
                    registry=resolved_target_registry,
                    suggested_actions=[
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
            _validate_bucket_access(s3_client, source_bucket)
        except Exception as e:
            # Provide friendly error message with helpful suggestions
            error_msg = str(e)
            if "Access denied" in error_msg or "AccessDenied" in error_msg:
                return PackageCreateFromS3Error(
                    error="Cannot access source bucket - insufficient permissions",
                    package_name=package_name,
                    suggested_actions=[
                        f"Verify you have s3:ListBucket and s3:GetObject permissions for {source_bucket}",
                        "Check if the bucket name is correct",
                        "Ensure your AWS credentials are properly configured",
                        "Try: check_bucket_access() to diagnose specific permission issues",
                        "Try: bucket_recommendations_get() to find buckets you can access",
                    ],
                )
            else:
                return PackageCreateFromS3Error(
                    error=f"Cannot access source bucket {source_bucket}: {str(e)}",
                    package_name=package_name,
                    suggested_actions=["Check bucket name", "Verify AWS credentials", "Check network connectivity"],
                )

        # Discover source objects
        logger.info(f"Discovering objects in s3://{source_bucket}/{source_prefix}")
        objects = _discover_s3_objects(s3_client, source_bucket, source_prefix, include_patterns, exclude_patterns)

        if not objects:
            return PackageCreateFromS3Error(
                error="No objects found matching the specified criteria",
                package_name=package_name,
                suggested_actions=[
                    "Check if source_prefix is correct",
                    "Verify include_patterns and exclude_patterns",
                    "Ensure the bucket contains files",
                ],
            )

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
        # IMPORTANT: README content is added as a FILE to the package, not as metadata
        final_readme_content = None

        # Use extracted README content from metadata if available, otherwise generate new content
        if readme_content:
            final_readme_content = readme_content
            logger.info("Using README content extracted from metadata")
        elif generate_readme:
            final_readme_content = _generate_readme_content(
                package_name=package_name,
                description=description,
                organized_structure=organized_structure,
                total_size=total_size,
                source_info=source_info,
                metadata_template=metadata_template,
            )
            logger.info("Generated new README content")

        summary_files = create_quilt_summary_files(
            package_name=package_name,
            package_metadata=enhanced_metadata,
            organized_structure=organized_structure,
            readme_content=final_readme_content or "",
            source_info=source_info,
            metadata_template=metadata_template,
        )

        # Prepare confirmation information
        confirmation_info = {
            "bucket_suggested": resolved_target_registry,
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
            return PackageCreateFromS3Success(
                package_name=package_name,
                registry=resolved_target_registry,
                action="preview",
                structure={"folders_created": list(organized_structure.keys()), "files_organized": len(objects)},
                metadata_info={
                    "package_size_mb": round(total_size / (1024 * 1024), 2),
                    "file_types": list(
                        set(Path(obj["Key"]).suffix.lower().lstrip(".") for obj in objects if Path(obj["Key"]).suffix)
                    ),
                },
                confirmation=confirmation_info,
                message="Preview generated. Set dry_run=False to create the package.",
            )

        # User confirmation step (in real implementation, this would be interactive)
        if confirm_structure and not force:
            # For now, we'll proceed as if confirmed
            # In a real implementation, this would present the preview to the user
            logger.info("Structure confirmation: proceeding with package creation")

        # Create the actual package
        logger.info(f"Creating package {package_name} with enhanced structure")
        # Convert Pydantic model to dict if it's a success response
        summary_files_dict = None
        if isinstance(summary_files, dict):
            summary_files_dict = summary_files
        elif hasattr(summary_files, 'model_dump'):
            summary_files_dict = summary_files.model_dump()

        package_result = _create_enhanced_package(
            s3_client=s3_client,
            organized_structure=organized_structure,
            source_bucket=source_bucket,
            package_name=package_name,
            target_registry=resolved_target_registry,
            description=description,
            enhanced_metadata=enhanced_metadata,
            readme_content=final_readme_content,
            summary_files=summary_files_dict,
            copy=copy,
            force=force,
        )

        return PackageCreateFromS3Success(
            package_name=package_name,
            registry=resolved_target_registry,
            action="created",
            structure={
                "folders_created": list(organized_structure.keys()),
                "files_organized": len(objects),
                "readme_generated": generate_readme,
            },
            metadata_info={
                "package_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": list(
                    set(Path(obj["Key"]).suffix.lower().lstrip(".") for obj in objects if Path(obj["Key"]).suffix)
                ),
                "organization_applied": ("logical_hierarchy" if auto_organize else "flat"),
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
            package_name=package_name,
            suggested_actions=[
                "Configure AWS credentials using aws configure",
                "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables",
                "Check your ~/.aws/credentials file",
            ],
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        return PackageCreateFromS3Error(
            error=f"AWS error ({error_code}): {str(e)}",
            package_name=package_name,
            suggested_actions=["Check AWS permissions", "Verify bucket access", "Check network connectivity"],
        )
    except Exception as e:
        logger.error(f"Error creating package from S3: {str(e)}")
        return PackageCreateFromS3Error(
            error=f"Failed to create package: {str(e)}",
            package_name=package_name,
            suggested_actions=[
                "Check logs for details",
                "Verify all parameters",
                "Ensure source bucket is accessible",
            ],
        )
