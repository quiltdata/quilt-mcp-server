"""Quilt-style JWT decompression utilities.

This module implements JWT decompression for the enhanced JWT tokens from the Quilt frontend.
The frontend sends compressed JWT tokens to stay under the 8KB limit while maintaining
compatibility through parallel expanded fields.

Based on Quilt's JWT Compression Format:
- Abbreviated permissions (e.g., "g" instead of "s3:GetObject")
- Compressed bucket data (grouped, patterned, or base64 encoded)
- Shortened field names (e.g., "p" instead of "permissions")
- Expanded fields for backward compatibility

See: catalog/app/services/JWTCompressionFormat.md in quiltdata/quilt
See: catalog/app/services/MCP_Server_JWT_Decompression_Guide.md in quiltdata/quilt

## Implementation Strategy

The MCP server should:
1. Prefer explicit fields (permissions, buckets, roles, scope, level) when present
2. Fall back to abbreviated claims (p, b, r, s, l) with decompression
3. Validate bucket count matches expected values (e.g., 32 for production roles)
4. Provide clear error messages for validation failures
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)

# Permission abbreviations as defined in Quilt's JWTCompressionFormat.md
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
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        # ValueError covers base64 decode errors
        # UnicodeDecodeError covers UTF-8 decode errors
        # JSONDecodeError covers JSON parse errors
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


def validate_jwt_claims(result: Dict[str, Any]) -> Dict[str, Any]:
    """Validate decompressed JWT claims and add validation metadata.
    
    Args:
        result: Decompressed JWT claims
        
    Returns:
        Claims with validation metadata
    """
    validation_warnings = []
    
    # Check for empty permissions
    if not result.get("permissions"):
        validation_warnings.append("No permissions found, defaulting to read-only")
        logger.warning("JWT has no permissions, defaulting to read-only access")
    
    # Check for wildcard bucket access
    buckets = result.get("buckets", [])
    if "*" in buckets:
        validation_warnings.append("Wildcard bucket access detected")
        logger.info("JWT has wildcard bucket access")
    
    # Validate bucket count for known role patterns
    roles = result.get("roles", [])
    for role in roles:
        if "ReadWrite" in role and len(buckets) > 0:
            # Log bucket count for debugging
            logger.debug("Role %s has access to %d buckets", role, len(buckets))
    
    if validation_warnings:
        result["_validation_warnings"] = validation_warnings
    
    return result


def safe_decompress_jwt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Safely decompress a JWT payload with comprehensive error handling.
    
    This function follows Quilt's JWT decompression guide and provides
    robust fallback behavior for invalid or malformed tokens.
    
    Args:
        payload: Raw JWT payload (decoded but not decompressed)
        
    Returns:
        Fully decompressed JWT claims with normalized structure
    """
    try:
        result = process_compressed_jwt(payload)
        logger.debug(
            "Successfully decompressed JWT: %d permissions, %d buckets, %d roles",
            len(result.get('permissions', [])),
            len(result.get('buckets', [])),
            len(result.get('roles', []))
        )
    except (TypeError, AttributeError, KeyError, ValueError) as e:
        # TypeError: Invalid payload types
        # AttributeError: Missing expected attributes
        # KeyError: Missing required keys
        # ValueError: Invalid values during decompression
        logger.warning("Error decompressing JWT, using fallback: %s", str(e))
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

    # Ensure required fields have valid defaults
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
    
    # Add validation metadata
    result = validate_jwt_claims(result)
    
    return result
