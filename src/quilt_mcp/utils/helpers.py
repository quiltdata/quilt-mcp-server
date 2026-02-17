"""General shared helper utilities."""

from __future__ import annotations


def extract_bucket_from_registry(registry: str) -> str:
    """Extract bucket/host token from S3 or URL-style registry strings."""
    if not registry:
        return ""
    if registry.startswith("s3://"):
        return registry.replace("s3://", "").split("/")[0]
    if registry.startswith("http://") or registry.startswith("https://"):
        return registry.split("//", 1)[-1].split("/")[0]
    return registry.split("/")[0]


def normalize_s3_registry(registry: str) -> str:
    """Normalize registry to s3://bucket format when possible."""
    bucket = extract_bucket_from_registry(registry)
    return f"s3://{bucket}" if bucket else ""


def build_s3_key(package_name: str, revision: str) -> str:
    """Build a canonical revision object key."""
    return f"{package_name}/revisions/{revision}"
