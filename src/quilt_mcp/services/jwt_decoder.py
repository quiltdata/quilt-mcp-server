"""Quilt-style JWT decompression utilities."""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, Iterable, List


PERMISSION_ABBREVIATIONS = {
    "g": "s3:GetObject",
    "p": "s3:PutObject",
    "d": "s3:DeleteObject",
    "l": "s3:ListBucket",
    "la": "s3:ListAllMyBuckets",
    "gv": "s3:GetObjectVersion",
    "pa": "s3:PutObjectAcl",
    "amu": "s3:AbortMultipartUpload",
}


def _decompress_permissions(values: Iterable[str]) -> List[str]:
    return [PERMISSION_ABBREVIATIONS.get(value, value) for value in values]


def _decompress_groups(data: Dict[str, Any]) -> List[str]:
    buckets: List[str] = []
    for prefix, suffixes in (data or {}).items():
        if not isinstance(suffixes, list):
            continue
        if prefix == "quilt":
            buckets.extend(f"quilt-{suffix}" for suffix in suffixes)
        else:
            for suffix in suffixes:
                if isinstance(suffix, str) and "-" in suffix:
                    buckets.append(suffix)
                else:
                    buckets.append(f"{prefix}-{suffix}")
    return buckets


def _decompress_patterns(data: Dict[str, Any]) -> List[str]:
    buckets: List[str] = []
    for pattern, bucket_list in (data or {}).items():
        if not isinstance(bucket_list, list):
            continue
        if pattern == "quilt":
            buckets.extend(f"quilt-{bucket}" for bucket in bucket_list)
        else:
            buckets.extend(bucket_list)
    return buckets


def _decompress_compressed(data: str) -> List[str]:
    try:
        decoded = base64.b64decode(data).decode("utf-8")
        parsed = json.loads(decoded)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _decompress_buckets(raw: Any) -> List[str]:
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, dict):
        return []

    compression_type = raw.get("_type")
    data = raw.get("_data")
    if compression_type == "groups":
        return _decompress_groups(data or {})
    if compression_type == "patterns":
        return _decompress_patterns(data or {})
    if compression_type == "compressed":
        return _decompress_compressed(data or "")
    return []


def process_compressed_jwt(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "scope": "read",
            "permissions": [],
            "roles": [],
            "buckets": [],
            "level": "read",
        }

    explicit_permissions = payload.get("permissions")
    permissions = (
        explicit_permissions
        if isinstance(explicit_permissions, list)
        else _decompress_permissions(payload.get("p", []))
    )

    explicit_roles = payload.get("roles")
    roles = explicit_roles if isinstance(explicit_roles, list) else payload.get("r", [])

    explicit_buckets = payload.get("buckets")
    buckets = (
        explicit_buckets
        if isinstance(explicit_buckets, list)
        else _decompress_buckets(payload.get("b"))
    )

    scope = payload.get("s") or payload.get("scope") or ""
    level = payload.get("l") or payload.get("level") or "read"

    return {
        "scope": scope,
        "permissions": permissions,
        "roles": roles,
        "buckets": buckets,
        "level": level,
        "iss": payload.get("iss"),
        "aud": payload.get("aud"),
        "sub": payload.get("sub"),
        "iat": payload.get("iat"),
        "exp": payload.get("exp"),
        "jti": payload.get("jti"),
    }


def safe_decompress_jwt(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = process_compressed_jwt(payload)
    except Exception:
        result = {
            "scope": payload.get("s") or payload.get("scope") or "read",
            "permissions": payload.get("permissions")
            if isinstance(payload.get("permissions"), list)
            else ["s3:GetObject"],
            "roles": payload.get("roles") if isinstance(payload.get("roles"), list) else [],
            "buckets": payload.get("buckets") if isinstance(payload.get("buckets"), list) else [],
            "level": payload.get("l") or payload.get("level") or "read",
            "iss": payload.get("iss"),
            "aud": payload.get("aud"),
            "sub": payload.get("sub"),
            "iat": payload.get("iat"),
            "exp": payload.get("exp"),
            "jti": payload.get("jti"),
        }

    if not result.get("permissions"):
        result["permissions"] = ["s3:GetObject"]
    if not isinstance(result.get("buckets"), list):
        result["buckets"] = []
    if not result.get("roles"):
        result["roles"] = []
    if not result.get("scope"):
        result["scope"] = "read"
    if not result.get("level"):
        result["level"] = "read"
    return result
