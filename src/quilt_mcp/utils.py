"""Shared utilities for Quilt MCP tools."""

from __future__ import annotations

import boto3


def generate_signed_url(s3_uri: str, expiration: int = 3600) -> str | None:
    """Generate a presigned URL for an S3 URI.
    
    Args:
        s3_uri: S3 URI (e.g., "s3://bucket/key")
        expiration: URL expiration in seconds (default: 3600)
    
    Returns:
        Presigned URL string or None if generation fails
    """
    if not s3_uri.startswith("s3://"):
        return None
    
    without_scheme = s3_uri[5:]
    if '/' not in without_scheme:
        return None
    
    bucket, key = without_scheme.split('/', 1)
    expiration = max(1, min(expiration, 604800))  # 1 sec to 7 days
    
    try:
        client = boto3.client("s3")
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration
        )
        return url
    except Exception:
        return None