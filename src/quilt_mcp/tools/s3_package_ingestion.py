"""S3-to-package ingestion workflows extracted from tools.packages."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Annotated, Literal, Optional

from botocore.exceptions import ClientError, NoCredentialsError
from pydantic import Field

from .package_metadata import generate_package_metadata, generate_readme_content
from .quilt_summary import create_quilt_summary_files
from .responses import PackageCreateFromS3Error, PackageCreateFromS3Success
from .s3_discovery import discover_s3_objects, organize_file_structure, should_include_object, validate_bucket_access
from ..context.request_context import RequestContext
from ..ops.factory import QuiltOpsFactory
from ..services.permissions_service import bucket_recommendations_get, check_bucket_access
from ..utils.common import get_s3_client, validate_package_name

logger = logging.getLogger(__name__)

REGISTRY_PATTERNS = {
    "ml": ["model", "training", "ml", "ai", "neural", "tensorflow", "pytorch"],
    "analytics": ["analytics", "reports", "metrics", "dashboard", "bi"],
    "data": ["data", "dataset", "warehouse", "lake"],
    "research": ["research", "experiment", "study", "analysis"],
}


def _suggest_target_registry(source_bucket: str, source_prefix: str) -> str:
    source_text = f"{source_bucket} {source_prefix}".lower()
    for registry_type, patterns in REGISTRY_PATTERNS.items():
        if any(pattern in source_text for pattern in patterns):
            return f"s3://{registry_type}-packages"
    return "s3://data-packages"


def _generate_readme_content(
    package_name: str,
    description: str,
    organized_structure: dict[str, list[dict[str, Any]]],
    total_size: int,
    source_info: dict[str, str],
    metadata_template: str,
) -> str:
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
    s3_client: Any,
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
    try:
        s3_uris = []
        for objects in organized_structure.values():
            for obj in objects:
                source_key = obj["Key"]
                s3_uri = f"s3://{source_bucket}/{source_key}"
                s3_uris.append(s3_uri)
                logger.debug("Collected S3 URI: %s", s3_uri)

        processed_metadata = enhanced_metadata.copy()
        if readme_content:
            processed_metadata["readme_content"] = readme_content
            logger.info("Added README content to metadata for processing")

        message = (
            f"Created via enhanced S3-to-package tool: {description}"
            if description
            else "Created via enhanced S3-to-package tool"
        )

        quilt_ops = QuiltOpsFactory.create()
        result = quilt_ops.create_package_revision(
            package_name=package_name,
            s3_uris=s3_uris,
            metadata=processed_metadata,
            registry=target_registry,
            message=message,
            auto_organize=True,
            copy=copy,
        )
        if not result.success:
            logger.error("Package creation failed: no error details available")
            raise Exception("Package creation failed")

        top_hash = result.top_hash
        logger.info("Successfully created package %s with hash %s", package_name, top_hash)

        if summary_files:
            logger.warning("Summary files and visualizations not yet supported with create_package_revision")

        return {
            "top_hash": top_hash,
            "message": f"Enhanced package {package_name} created successfully",
            "registry": target_registry,
        }
    except Exception as e:
        logger.error("Error creating enhanced package: %s", str(e))
        raise


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
    description: Annotated[str, Field(default="", description="Package description")] = "",
    target_registry: Annotated[
        Optional[str],
        Field(default=None, description="Target Quilt registry (auto-suggested if not provided)"),
    ] = None,
    include_patterns: Annotated[
        Optional[list[str]],
        Field(default=None, description="File patterns to include (glob style)"),
    ] = None,
    exclude_patterns: Annotated[
        Optional[list[str]],
        Field(default=None, description="File patterns to exclude (glob style)"),
    ] = None,
    metadata_template: Annotated[
        Literal["standard", "ml", "analytics"],
        Field(default="standard", description="Metadata template to use"),
    ] = "standard",
    copy: Annotated[
        bool,
        Field(
            default=False, description="Whether to copy files to registry bucket (false=reference only, true=copy all)"
        ),
    ] = False,
    auto_organize: Annotated[bool, Field(default=True, description="Enable smart folder organization")] = True,
    generate_readme: Annotated[bool, Field(default=True, description="Generate comprehensive README.md")] = True,
    confirm_structure: Annotated[
        bool, Field(default=True, description="Require user confirmation of structure")
    ] = True,
    dry_run: Annotated[bool, Field(default=False, description="Preview structure without creating package")] = False,
    force: Annotated[bool, Field(default=False, description="Skip confirmation prompts when True")] = False,
    metadata: Annotated[
        Optional[dict[str, Any]],
        Field(default=None, description="Additional user-provided metadata"),
    ] = None,
    *,
    context: RequestContext,
) -> PackageCreateFromS3Success | PackageCreateFromS3Error:
    try:
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

        processed_metadata = metadata.copy() if metadata else {}
        readme_content = None
        if "readme_content" in processed_metadata:
            readme_value = processed_metadata.pop("readme_content")
            readme_content = str(readme_value) if readme_value is not None else None
        elif "readme" in processed_metadata:
            readme_value = processed_metadata.pop("readme")
            readme_content = str(readme_value) if readme_value is not None else None

        if source_bucket.startswith("s3://"):
            source_bucket = source_bucket.replace("s3://", "").split("/")[0]
            logger.info("Normalized source_bucket from s3:// URI to: %s", source_bucket)

        resolved_target_registry = target_registry
        if not resolved_target_registry:
            try:
                recommendations = bucket_recommendations_get(
                    source_bucket=source_bucket,
                    operation_type="package_creation",
                    context=context,
                )
                if recommendations.get("success") and recommendations.get("recommendations", {}).get(
                    "primary_recommendations"
                ):
                    top_rec = recommendations["recommendations"]["primary_recommendations"][0]
                    resolved_target_registry = f"s3://{top_rec['bucket_name']}"
                    logger.info("Using permission-based recommendation: %s", resolved_target_registry)
                else:
                    resolved_target_registry = _suggest_target_registry(source_bucket, source_prefix)
                    logger.info("Using pattern-based suggestion: %s", resolved_target_registry)
            except Exception as e:
                logger.warning("Permission-based recommendation failed, using pattern-based: %s", e)
                resolved_target_registry = _suggest_target_registry(source_bucket, source_prefix)
                logger.info("Fallback suggestion: %s", resolved_target_registry)

        target_bucket_name = resolved_target_registry.replace("s3://", "")
        try:
            access_check = check_bucket_access(target_bucket_name, context=context)
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
            logger.warning("Could not validate target registry permissions: %s", e)

        s3_client = get_s3_client()
        try:
            _validate_bucket_access(s3_client, source_bucket)
        except Exception as e:
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
            return PackageCreateFromS3Error(
                error=f"Cannot access source bucket {source_bucket}: {str(e)}",
                package_name=package_name,
                suggested_actions=["Check bucket name", "Verify AWS credentials", "Check network connectivity"],
            )

        logger.info("Discovering objects in s3://%s/%s", source_bucket, source_prefix)
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

        organized_structure = _organize_file_structure(objects, auto_organize)
        total_size = sum(obj.get("Size", 0) for obj in objects)

        source_info = {
            "bucket": source_bucket,
            "prefix": source_prefix,
            "source_description": (
                f"s3://{source_bucket}/{source_prefix}" if source_prefix else f"s3://{source_bucket}"
            ),
        }

        enhanced_metadata = _generate_package_metadata(
            package_name=package_name,
            source_info=source_info,
            organized_structure=organized_structure,
            metadata_template=metadata_template,
            user_metadata=processed_metadata,
        )

        final_readme_content = None
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

        if confirm_structure and not force:
            logger.info("Structure confirmation: proceeding with package creation")

        logger.info("Creating package %s with enhanced structure", package_name)
        summary_files_dict = summary_files if isinstance(summary_files, dict) else summary_files.model_dump()
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
        logger.error("Error creating package from S3: %s", str(e))
        return PackageCreateFromS3Error(
            error=f"Failed to create package: {str(e)}",
            package_name=package_name,
            suggested_actions=[
                "Check logs for details",
                "Verify all parameters",
                "Ensure source bucket is accessible",
            ],
        )
