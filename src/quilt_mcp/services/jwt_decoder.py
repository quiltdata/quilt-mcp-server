"""Utilities for decoding and normalizing Quilt JWT claims."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


def _decode_base64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _load_json(data: str | bytes) -> Any:
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data)


def _expand_permissions(compressed: Iterable[str]) -> List[str]:
    """Expand abbreviated permissions into full AWS action strings."""
    mapping = {
        "g": "s3:GetObject",
        "p": "s3:PutObject",
        "d": "s3:DeleteObject",
        "l": "s3:ListBucket",
        "m": "s3:GetBucketMetadata",
        "a": "athena:StartQueryExecution",
        "s": "athena:GetQueryResults",
        "c": "glue:GetTable",
        "t": "quilt:GetTabulatorTable",
        "u": "quilt:UpdatePackage",
        "r": "quilt:GetPackage",
        "b": "quilt:BrowsePackages",
    }
    expanded: List[str] = []
    for token in compressed:
        if token in mapping:
            expanded.append(mapping[token])
        else:
            expanded.append(token)
    return expanded


def _decompress_pattern_list(config: Dict[str, Any]) -> List[str]:
    """Expand compressed bucket patterns into explicit bucket list."""
    prefixes = config.get("prefixes") or []
    suffixes = config.get("suffixes") or []
    static = config.get("static") or []

    expanded = list(static)
    for prefix in prefixes:
        for suffix in suffixes:
            expanded.append(f"{prefix}{suffix}")
    return expanded


def _decompress_groups(groups: Dict[str, Any]) -> List[str]:
    """Decompress group-based bucket definitions."""
    buckets: List[str] = []
    for group in groups.values():
        if not isinstance(group, dict):
            continue
        buckets.extend(group.get("static", []))
        patterns = group.get("patterns")
        if isinstance(patterns, dict):
            buckets.extend(_decompress_pattern_list(patterns))
    return buckets


def _safe_get(data: Dict[str, Any], key: str) -> Any:
    value = data.get(key)
    if value is None:
        value = data.get(key.lower())
    return value


def safe_decompress_jwt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize Quilt JWT payload into expanded claim structure."""
    claims = dict(payload)

    # Expand permissions if compressed
    permissions = _safe_get(payload, "permissions")
    if isinstance(permissions, list):
        claims["permissions"] = _expand_permissions(permissions)

    # Expand buckets if compressed
    buckets = _safe_get(payload, "buckets")
    if isinstance(buckets, list):
        claims["buckets"] = buckets
    elif isinstance(buckets, dict):
        expanded: List[str] = []
        if "groups" in buckets and isinstance(buckets["groups"], dict):
            expanded.extend(_decompress_groups(buckets["groups"]))
        if "patterns" in buckets and isinstance(buckets["patterns"], dict):
            expanded.extend(_decompress_pattern_list(buckets["patterns"]))
        if "static" in buckets and isinstance(buckets["static"], list):
            expanded.extend(buckets["static"])
        claims["buckets"] = expanded

    return claims


def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    """Decode a JWT payload without verifying the signature."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            logger.warning("Invalid JWT format - expected 3 parts, got %d", len(parts))
            return None
        payload_bytes = _decode_base64(parts[1])
        payload = _load_json(payload_bytes)
        if not isinstance(payload, dict):
            logger.warning("Decoded JWT payload is not a dict")
            return None
        return payload
    except Exception as exc:  # pragma: no cover - diagnostic aid
        logger.error("Failed to decode JWT payload: %s", exc)
        return None
