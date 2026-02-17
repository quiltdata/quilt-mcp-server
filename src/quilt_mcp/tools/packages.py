"""Backward-compatible package tool exports.

Core package CRUD lives in package_crud.
S3 ingestion workflow lives in s3_package_ingestion.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import Field

from ..context.request_context import RequestContext
from ..services.permissions_service import bucket_recommendations_get, check_bucket_access
from ..utils.common import get_s3_client
from .package_crud import (
    package_browse,
    package_create,
    package_delete,
    package_diff,
    package_update,
    packages_list,
)
from .responses import PackageCreateFromS3Error, PackageCreateFromS3Success
from .s3_discovery import should_include_object as _should_include_object
from . import s3_package_ingestion as _s3_ingestion
from .s3_package_ingestion import _create_enhanced_package, _discover_s3_objects, _validate_bucket_access


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
    """Create a Quilt package from S3 objects - delegates ingestion workflow from the public packages tool module.

    Args:
        source_bucket: S3 bucket name containing source objects (without the ``s3://`` prefix).
        package_name: Destination package name in ``namespace/name`` format.
        source_prefix: Optional source prefix to scope discovered objects.
        description: Human-readable package description.
        target_registry: Optional destination registry URI; if omitted, the workflow suggests one.
        include_patterns: Optional glob patterns for objects to include.
        exclude_patterns: Optional glob patterns for objects to exclude.
        metadata_template: Metadata template profile (``standard``, ``ml``, or ``analytics``).
        copy: Whether to copy source objects to the target registry bucket.
        auto_organize: Whether to apply automatic directory organization.
        generate_readme: Whether to generate README content for the created package.
        confirm_structure: Whether to require user confirmation for discovered structure.
        dry_run: Whether to return a preview without creating the package revision.
        force: Whether to bypass confirmation prompts.
        metadata: Optional user-provided metadata merged into generated metadata.
        context: Request context injected by the MCP runtime.

    Returns:
        PackageCreateFromS3Success when the package is created (or previewed in dry run), otherwise
        PackageCreateFromS3Error with remediation guidance.

    Next step:
        Open the returned ``package_url`` (or inspect ``structure_preview`` in dry-run mode) and then run
        follow-up metadata or visualization tools as needed.

    Example:
        package_create_from_s3(
            source_bucket="my-data-bucket",
            package_name="team/training-dataset",
            source_prefix="raw/2026/",
            dry_run=True,
            context=context,
        )
    """
    _s3_ingestion.get_s3_client = get_s3_client
    _s3_ingestion.bucket_recommendations_get = bucket_recommendations_get
    _s3_ingestion.check_bucket_access = check_bucket_access
    _s3_ingestion._validate_bucket_access = _validate_bucket_access
    _s3_ingestion._discover_s3_objects = _discover_s3_objects
    _s3_ingestion._create_enhanced_package = _create_enhanced_package
    return _s3_ingestion.package_create_from_s3(
        source_bucket=source_bucket,
        package_name=package_name,
        source_prefix=source_prefix,
        description=description,
        target_registry=target_registry,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        metadata_template=metadata_template,
        copy=copy,
        auto_organize=auto_organize,
        generate_readme=generate_readme,
        confirm_structure=confirm_structure,
        dry_run=dry_run,
        force=force,
        metadata=metadata,
        context=context,
    )
