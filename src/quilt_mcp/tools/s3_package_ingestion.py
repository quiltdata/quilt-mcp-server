"""S3-to-package ingestion entrypoints.

This module isolates S3 bulk-ingestion tool APIs from the core package CRUD
module while preserving existing public behavior.
"""

from __future__ import annotations

from typing import Any, Annotated, Literal, Optional

from pydantic import Field

from .packages import package_create_from_s3 as _package_create_from_s3
from .responses import PackageCreateFromS3Error, PackageCreateFromS3Success
from ..context.request_context import RequestContext


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
        Field(default="", description="Package description"),
    ] = "",
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
    generate_readme: Annotated[
        bool,
        Field(default=True, description="Generate comprehensive README.md"),
    ] = True,
    confirm_structure: Annotated[
        bool,
        Field(default=True, description="Require user confirmation of structure"),
    ] = True,
    dry_run: Annotated[bool, Field(default=False, description="Preview structure without creating package")] = False,
    force: Annotated[bool, Field(default=False, description="Skip confirmation prompts when True")] = False,
    metadata: Annotated[
        Optional[dict[str, Any]], Field(default=None, description="Additional user-provided metadata")
    ] = None,
    *,
    context: RequestContext,
) -> PackageCreateFromS3Success | PackageCreateFromS3Error:
    """Create a package from S3 contents using the existing packages implementation."""
    return _package_create_from_s3(
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
