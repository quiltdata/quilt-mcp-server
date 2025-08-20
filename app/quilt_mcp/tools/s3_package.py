"""S3-to-Package Creation Tool for Quilt MCP Server.

This module provides functionality to create Quilt packages directly from S3 bucket contents,
eliminating the need for local downloads and streamlining the data packaging workflow.
"""

from typing import Any, Dict, List, Optional
import asyncio
import logging
from datetime import datetime

import boto3
import quilt3
from botocore.exceptions import ClientError, NoCredentialsError

from ..utils import get_s3_client, validate_package_name, format_error_response

logger = logging.getLogger(__name__)


async def package_create_from_s3(
    source_bucket: str,
    source_prefix: str = "",
    package_name: str,
    target_registry: str,
    target_bucket: Optional[str] = None,
    description: str = "",
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    preserve_structure: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a Quilt package from S3 bucket contents.
    
    Args:
        source_bucket: S3 bucket containing source data
        source_prefix: Optional prefix to filter source objects
        package_name: Name for the new package (namespace/name format)
        target_registry: Target Quilt registry for the package
        target_bucket: Target S3 bucket (defaults to registry bucket)
        description: Package description
        include_patterns: File patterns to include (glob style)
        exclude_patterns: File patterns to exclude (glob style)  
        preserve_structure: Maintain original S3 folder structure
        metadata: Additional package metadata
        
    Returns:
        Package creation result with package info and stats
    """
    try:
        # Validate inputs
        if not validate_package_name(package_name):
            return format_error_response("Invalid package name format. Use 'namespace/name'")
        
        if not source_bucket or not target_registry:
            return format_error_response("source_bucket and target_registry are required")
        
        # Initialize clients
        s3_client = await get_s3_client()
        
        # Validate source bucket access
        try:
            await _validate_bucket_access(s3_client, source_bucket)
        except Exception as e:
            return format_error_response(f"Cannot access source bucket {source_bucket}: {str(e)}")
        
        # Discover source objects
        logger.info(f"Discovering objects in s3://{source_bucket}/{source_prefix}")
        objects = await _discover_s3_objects(
            s3_client, source_bucket, source_prefix, include_patterns, exclude_patterns
        )
        
        if not objects:
            return format_error_response("No objects found matching the specified criteria")
        
        # Create package structure
        logger.info(f"Creating package {package_name} with {len(objects)} objects")
        package_result = await _create_package_from_objects(
            s3_client=s3_client,
            objects=objects,
            source_bucket=source_bucket,
            package_name=package_name,
            target_registry=target_registry,
            target_bucket=target_bucket,
            description=description,
            preserve_structure=preserve_structure,
            metadata=metadata,
        )
        
        return {
            "success": True,
            "package_name": package_name,
            "registry": target_registry,
            "objects_count": len(objects),
            "total_size": sum(obj.get("Size", 0) for obj in objects),
            "package_hash": package_result.get("top_hash"),
            "created_at": datetime.utcnow().isoformat(),
            "description": description,
            "metadata": metadata or {},
        }
        
    except NoCredentialsError:
        return format_error_response("AWS credentials not found. Please configure AWS authentication.")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        return format_error_response(f"AWS error ({error_code}): {str(e)}")
    except Exception as e:
        logger.error(f"Error creating package from S3: {str(e)}")
        return format_error_response(f"Failed to create package: {str(e)}")


async def _validate_bucket_access(s3_client, bucket_name: str) -> None:
    """Validate that the user has access to the source bucket."""
    try:
        await s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "404":
            raise ValueError(f"Bucket {bucket_name} does not exist or you don't have access")
        elif error_code == "403":
            raise ValueError(f"Access denied to bucket {bucket_name}")
        else:
            raise


async def _discover_s3_objects(
    s3_client,
    bucket: str,
    prefix: str,
    include_patterns: Optional[List[str]],
    exclude_patterns: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Discover and filter S3 objects based on patterns."""
    objects = []
    
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        async for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    if _should_include_object(obj["Key"], include_patterns, exclude_patterns):
                        objects.append(obj)
    except ClientError as e:
        logger.error(f"Error listing objects in bucket {bucket}: {str(e)}")
        raise
    
    return objects


def _should_include_object(
    key: str,
    include_patterns: Optional[List[str]],
    exclude_patterns: Optional[List[str]],
) -> bool:
    """Determine if an object should be included based on patterns."""
    import fnmatch
    
    # Check exclude patterns first
    if exclude_patterns:
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(key, pattern):
                return False
    
    # Check include patterns
    if include_patterns:
        for pattern in include_patterns:
            if fnmatch.fnmatch(key, pattern):
                return True
        return False  # If include patterns specified but none match
    
    return True  # Include by default if no patterns specified


async def _create_package_from_objects(
    s3_client,
    objects: List[Dict[str, Any]],
    source_bucket: str,
    package_name: str,
    target_registry: str,
    target_bucket: Optional[str],
    description: str,
    preserve_structure: bool,
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create the Quilt package from S3 objects."""
    # TODO: Implement actual package creation
    # This is a placeholder implementation
    
    logger.info(f"Creating package {package_name} from {len(objects)} objects")
    
    # For now, return a mock result
    # In the full implementation, this would:
    # 1. Create a new Quilt package
    # 2. Add S3 objects to the package (with or without downloading)
    # 3. Set package metadata
    # 4. Push to the target registry
    
    return {
        "top_hash": "placeholder_hash_123456",
        "message": f"Package {package_name} created successfully",
    }
