"""S3 discovery and organization helpers for package ingestion."""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


FOLDER_MAPPING = {
    "csv": "data/processed",
    "tsv": "data/processed",
    "parquet": "data/processed",
    "json": "data/processed",
    "xml": "data/processed",
    "jsonl": "data/processed",
    "log": "data/raw",
    "txt": "data/raw",
    "raw": "data/raw",
    "md": "docs",
    "rst": "docs",
    "pdf": "docs",
    "docx": "docs",
    "schema": "docs/schemas",
    "yml": "metadata",
    "yaml": "metadata",
    "toml": "metadata",
    "ini": "metadata",
    "conf": "metadata",
    "png": "data/media",
    "jpg": "data/media",
    "jpeg": "data/media",
    "mp4": "data/media",
    "avi": "data/media",
}


def validate_bucket_access(s3_client: Any, bucket_name: str) -> None:
    """Validate that caller can access the source bucket."""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code == "404":
            raise ValueError(f"Bucket {bucket_name} does not exist or you don't have access") from exc
        if error_code == "403":
            raise ValueError(f"Access denied to bucket {bucket_name}") from exc
        raise


def should_include_object(
    key: str,
    include_patterns: list[str] | None,
    exclude_patterns: list[str] | None,
) -> bool:
    """Determine whether an object key should be included."""
    invalid_chars = r'\{}^%`]">[~<#|'
    if any(char in key for char in invalid_chars):
        found_chars = [char for char in invalid_chars if char in key]
        logger.warning("Skipping object with invalid S3 characters %s: %s", found_chars, key)
        return False

    if not key.isprintable():
        logger.warning("Skipping object with non-printable characters: %s", key)
        return False

    if exclude_patterns:
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(key, pattern):
                return False

    if include_patterns:
        for pattern in include_patterns:
            if fnmatch.fnmatch(key, pattern):
                return True
        return False

    return True


def discover_s3_objects(
    s3_client: Any,
    bucket: str,
    prefix: str,
    include_patterns: list[str] | None,
    exclude_patterns: list[str] | None,
) -> list[dict[str, Any]]:
    """Discover and filter objects from S3."""
    objects: list[dict[str, Any]] = []

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj.get("Key", "")
                if key.endswith("/"):
                    continue
                if should_include_object(key, include_patterns, exclude_patterns):
                    objects.append(obj)
    except ClientError:
        logger.exception("Error listing objects in bucket %s", bucket)
        raise

    return objects


def organize_file_structure(objects: list[dict[str, Any]], auto_organize: bool) -> dict[str, list[dict[str, Any]]]:
    """Organize objects into logical folders for package creation."""
    if not auto_organize:
        return {"": objects}

    organized: dict[str, list[dict[str, Any]]] = {}
    for obj in objects:
        key = obj.get("Key", "")
        ext = Path(key).suffix.lower().lstrip(".")
        target_folder = FOLDER_MAPPING.get(ext, "data/misc")

        key_lower = key.lower()
        if "readme" in key_lower or "documentation" in key_lower:
            target_folder = "docs"
        elif "schema" in key_lower or "definition" in key_lower:
            target_folder = "docs/schemas"
        elif "config" in key_lower or "settings" in key_lower:
            target_folder = "metadata"

        organized.setdefault(target_folder, []).append(obj)

    return organized
