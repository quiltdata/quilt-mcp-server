"""JWT Decompression Utilities for MCP Server

This module provides functions to decompress JWT tokens from the frontend
that use abbreviated permissions and compressed bucket data.
"""

import base64
import json
import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)

# Permission abbreviation mapping
PERMISSION_ABBREVIATIONS = {
    'g': 's3:GetObject',
    'p': 's3:PutObject',
    'd': 's3:DeleteObject',
    'l': 's3:ListBucket',
    'la': 's3:ListAllMyBuckets',
    'gv': 's3:GetObjectVersion',
    'pa': 's3:PutObjectAcl',
    'amu': 's3:AbortMultipartUpload',
    'gm': 's3:GetObjectMetadata',
    'pm': 's3:PutObjectMetadata',
    'dm': 's3:DeleteObjectMetadata',
    'gl': 's3:GetObjectLockConfiguration',
    'pl': 's3:PutObjectLockConfiguration',
    'dl': 's3:DeleteObjectLockConfiguration',
    'gt': 's3:GetObjectTagging',
    'pt': 's3:PutObjectTagging',
    'dt': 's3:DeleteObjectTagging',
    'gr': 's3:GetObjectRetention',
    'pr': 's3:PutObjectRetention',
    'dr': 's3:DeleteObjectRetention',
    'gc': 's3:GetObjectLegalHold',
    'pc': 's3:PutObjectLegalHold',
    'dc': 's3:DeleteObjectLegalHold',
    'gb': 's3:GetBucketLocation',
    'pb': 's3:PutBucketLocation',
    'db': 's3:DeleteBucketLocation',
    'gbl': 's3:GetBucketLifecycle',
    'pbl': 's3:PutBucketLifecycle',
    'dbl': 's3:DeleteBucketLifecycle',
    'gbt': 's3:GetBucketTagging',
    'pbt': 's3:PutBucketTagging',
    'dbt': 's3:DeleteBucketTagging',
    'gba': 's3:GetBucketAcl',
    'pba': 's3:PutBucketAcl',
    'dba': 's3:DeleteBucketAcl',
    'gbp': 's3:GetBucketPolicy',
    'pbp': 's3:PutBucketPolicy',
    'dbp': 's3:DeleteBucketPolicy'
}


def decompress_permissions(abbreviated_permissions: List[str]) -> List[str]:
    """Convert abbreviated permissions back to full AWS permission strings.
    
    Args:
        abbreviated_permissions: List of abbreviated permission strings
        
    Returns:
        List of full AWS permission strings
    """
    if not isinstance(abbreviated_permissions, list):
        logger.warning("Invalid permissions format: expected list, got %s", type(abbreviated_permissions))
        return []
    
    full_permissions = []
    for abbrev in abbreviated_permissions:
        if abbrev in PERMISSION_ABBREVIATIONS:
            full_permissions.append(PERMISSION_ABBREVIATIONS[abbrev])
        else:
            # Fallback for unknown abbreviations
            logger.debug("Unknown permission abbreviation: %s", abbrev)
            full_permissions.append(abbrev)
    
    logger.debug("Decompressed %d permissions from %d abbreviations", len(full_permissions), len(abbreviated_permissions))
    return full_permissions


def decompress_buckets(bucket_data: Union[List[str], Dict[str, Any]]) -> List[str]:
    """Decompress bucket data based on compression type.
    
    Args:
        bucket_data: Compressed bucket data (array or object with _type)
        
    Returns:
        List of full bucket names
    """
    # If it's already an array, no compression was applied
    if isinstance(bucket_data, list):
        logger.debug("Bucket data is already uncompressed: %d buckets", len(bucket_data))
        return bucket_data
    
    # If it's not an object or doesn't have _type, return as-is
    if not isinstance(bucket_data, dict) or '_type' not in bucket_data:
        logger.warning("Invalid bucket data format: expected dict with _type, got %s", type(bucket_data))
        return []
    
    compression_type = bucket_data['_type']
    data = bucket_data.get('_data', {})
    
    logger.debug("Decompressing bucket data with type: %s", compression_type)
    
    if compression_type == 'groups':
        result = _decompress_groups(data)
    elif compression_type == 'patterns':
        result = _decompress_patterns(data)
    elif compression_type == 'compressed':
        result = _decompress_compressed(data)
    else:
        logger.warning("Unknown compression type: %s", compression_type)
        result = []
    
    logger.debug("Decompressed %d buckets from compression type: %s", len(result), compression_type)
    return result


def _decompress_groups(grouped_data: Dict[str, List[str]]) -> List[str]:
    """Decompress grouped bucket data.
    
    Args:
        grouped_data: Object with prefix keys and bucket suffix arrays
        
    Returns:
        List of full bucket names
    """
    buckets = []
    
    for prefix, bucket_suffixes in grouped_data.items():
        if not isinstance(bucket_suffixes, list):
            logger.warning("Invalid bucket suffixes for prefix %s: expected list, got %s", prefix, type(bucket_suffixes))
            continue
            
        for suffix in bucket_suffixes:
            if prefix == 'quilt':
                buckets.append(f"quilt-{suffix}")
            else:
                buckets.append(f"{prefix}-{suffix}")
    
    return buckets


def _decompress_patterns(pattern_data: Dict[str, List[str]]) -> List[str]:
    """Decompress pattern-based bucket data.
    
    Args:
        pattern_data: Object with pattern keys and bucket arrays
        
    Returns:
        List of full bucket names
    """
    buckets = []
    
    for pattern, bucket_list in pattern_data.items():
        if not isinstance(bucket_list, list):
            logger.warning("Invalid bucket list for pattern %s: expected list, got %s", pattern, type(bucket_list))
            continue
            
        if pattern == 'quilt':
            # Add 'quilt-' prefix to each bucket
            for bucket in bucket_list:
                buckets.append(f"quilt-{bucket}")
        elif pattern == 'cell':
            # Keep cell buckets as-is
            buckets.extend(bucket_list)
        else:
            # Other patterns - keep as-is
            buckets.extend(bucket_list)
    
    return buckets


def _decompress_compressed(compressed_data: str) -> List[str]:
    """Decompress base64 encoded bucket data.
    
    Args:
        compressed_data: Base64 encoded JSON string
        
    Returns:
        List of bucket names
    """
    try:
        decoded = base64.b64decode(compressed_data).decode('utf-8')
        parsed = json.loads(decoded)
        if isinstance(parsed, list):
            return parsed
        else:
            logger.warning("Decompressed data is not a list: %s", type(parsed))
            return []
    except Exception as e:
        logger.error("Failed to decompress bucket data: %s", e)
        return []


def process_compressed_jwt(jwt_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process a compressed JWT payload and return standard format.
    
    Args:
        jwt_payload: The JWT payload object
        
    Returns:
        Standard JWT payload with decompressed data
    """
    # Extract compressed fields
    scope = jwt_payload.get('s', '')
    permissions = jwt_payload.get('p', [])
    roles = jwt_payload.get('r', [])
    buckets = jwt_payload.get('b', [])
    level = jwt_payload.get('l', 'read')
    
    # Decompress data
    full_permissions = decompress_permissions(permissions)
    full_buckets = decompress_buckets(buckets)
    
    # Return standard format
    result = {
        'scope': scope,
        'permissions': full_permissions,
        'roles': roles,
        'buckets': full_buckets,
        'level': level,
        'iss': jwt_payload.get('iss'),
        'aud': jwt_payload.get('aud'),
        'sub': jwt_payload.get('sub'),
        'iat': jwt_payload.get('iat'),
        'exp': jwt_payload.get('exp'),
        'jti': jwt_payload.get('jti')
    }
    
    logger.debug("Processed compressed JWT: %d permissions, %d buckets, level: %s", 
                len(full_permissions), len(full_buckets), level)
    
    return result


def safe_decompress_jwt(jwt_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Safely decompress JWT with fallbacks for errors.
    
    Args:
        jwt_payload: The JWT payload object
        
    Returns:
        Standard JWT payload with fallback values
    """
    explicit_permissions = jwt_payload.get('permissions')
    explicit_buckets = jwt_payload.get('buckets')
    explicit_roles = jwt_payload.get('roles')
    explicit_scope = jwt_payload.get('scope')
    explicit_level = jwt_payload.get('level')

    if any(value is not None for value in (explicit_permissions, explicit_buckets, explicit_roles, explicit_scope, explicit_level)):
        return {
            'scope': explicit_scope or jwt_payload.get('s', ''),
            'permissions': list(explicit_permissions) if isinstance(explicit_permissions, list) else (
                decompress_permissions(jwt_payload.get('p', [])) if explicit_permissions is None else [explicit_permissions]
            ),
            'roles': list(explicit_roles) if isinstance(explicit_roles, list) else jwt_payload.get('r', []),
            'buckets': list(explicit_buckets) if isinstance(explicit_buckets, list) else (
                decompress_buckets(jwt_payload.get('b', [])) if explicit_buckets is None else []
            ),
            'level': explicit_level or jwt_payload.get('l', 'read'),
            'iss': jwt_payload.get('iss'),
            'aud': jwt_payload.get('aud'),
            'sub': jwt_payload.get('sub'),
            'iat': jwt_payload.get('iat'),
            'exp': jwt_payload.get('exp'),
            'jti': jwt_payload.get('jti')
        }

    try:
        return process_compressed_jwt(jwt_payload)
    except Exception as e:
        logger.error("JWT decompression failed: %s", e)
        
        # Return minimal valid payload as fallback
        return {
            'scope': jwt_payload.get('s', 'read'),
            'permissions': ['s3:GetObject'],  # Minimal permissions
            'roles': jwt_payload.get('r', []),
            'buckets': [],  # Empty buckets as fallback
            'level': jwt_payload.get('l', 'read'),
            'iss': jwt_payload.get('iss'),
            'aud': jwt_payload.get('aud'),
            'sub': jwt_payload.get('sub'),
            'iat': jwt_payload.get('iat'),
            'exp': jwt_payload.get('exp'),
            'jti': jwt_payload.get('jti')
        }


def is_compressed_jwt(jwt_payload: Dict[str, Any]) -> bool:
    """Check if a JWT payload is in compressed format.
    
    Args:
        jwt_payload: The JWT payload object
        
    Returns:
        True if the payload appears to be compressed
    """
    # Check for compressed field names
    compressed_fields = ['s', 'p', 'r', 'b', 'l']
    has_compressed_fields = any(field in jwt_payload for field in compressed_fields)
    
    # Check for standard field names
    standard_fields = ['scope', 'permissions', 'roles', 'buckets', 'level']
    has_standard_fields = any(field in jwt_payload for field in standard_fields)
    
    # If it has compressed fields but not standard fields, it's likely compressed
    return has_compressed_fields and not has_standard_fields
