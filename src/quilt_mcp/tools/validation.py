"""Shared validation helpers for package tools."""

from __future__ import annotations

from typing import Any, Optional


def normalize_registry(bucket_or_uri: str) -> str:
    """Normalize registry input to s3:// URI format."""
    if bucket_or_uri.startswith("s3://"):
        return bucket_or_uri
    return f"s3://{bucket_or_uri}"


def validate_registry_required(registry: str, operation: str) -> tuple[bool, str, list[str]]:
    """Validate that registry is present for a package operation."""
    if registry:
        return True, "", []
    return (
        False,
        f"Registry parameter is required for {operation}. Specify target S3 bucket (e.g., registry='s3://my-bucket')",
        [
            "Provide registry parameter",
            f"Example: {operation}(..., registry='s3://my-bucket')",
        ],
    )


def validate_s3_uris_required(s3_uris: list[str]) -> tuple[bool, str, list[str]]:
    """Validate S3 URI inputs for create/update operations."""
    if s3_uris:
        return True, "", []
    return (
        False,
        "No S3 URIs provided",
        ["Provide at least one S3 URI", "Example: s3://bucket/path/to/file.csv"],
    )


def validate_package_name_required(package_name: str, operation: str) -> tuple[bool, str, list[str]]:
    """Validate package name input for create/update operations."""
    if package_name:
        return True, "", []
    return (
        False,
        f"package_name is required for {operation}",
        ["Provide a package name in format: namespace/name", "Example: team/dataset"],
    )


def validate_metadata_dict(
    metadata: Optional[dict[str, Any]],
    *,
    package_name: str,
) -> tuple[bool, str, str, list[str]]:
    """Validate optional metadata payload is a dict."""
    if metadata is None or isinstance(metadata, dict):
        return True, "", "", []
    return (
        False,
        "Metadata must be a dictionary",
        package_name,
        ["Provide metadata as a dict", "Example: {'description': 'My dataset'}"],
    )
