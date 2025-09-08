"""AWS S3 operations utilities.

This module provides composable utilities for S3 operations including:
- Client creation from sessions
- Object listing with pagination support
- Object retrieval with streaming support
- Object upload with metadata support
- Object deletion and existence checking
- Retry logic with exponential backoff

Features:
- Uses injected sessions for testability
- Comprehensive error handling
- Streaming support for large objects
- Retry logic with exponential backoff
- Type annotations and documentation
"""

from __future__ import annotations

import time
import logging
from typing import Any, Dict, Iterator, List, Optional, Union

import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


class S3Error(Exception):
    """Custom exception for S3-related errors."""

    pass


def create_client(session: boto3.Session, region: Optional[str] = None) -> Any:
    """Create an S3 client from a boto3 session.

    Args:
        session: A boto3 session
        region: AWS region for the client (overrides session region)

    Returns:
        Configured S3 client

    Examples:
        >>> session = create_session()
        >>> s3_client = create_client(session)
        >>> s3_client = create_client(session, region='us-west-2')
    """
    if region:
        return session.client('s3', region_name=region)
    return session.client('s3')


def list_objects(
    client: Any,
    bucket: str,
    prefix: str = "",
    max_keys: int = 1000,
    continuation_token: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """List objects in an S3 bucket with optional prefix filtering.

    Args:
        client: S3 client instance
        bucket: S3 bucket name
        prefix: Filter objects by prefix (default: "")
        max_keys: Maximum number of objects to return (default: 1000)
        continuation_token: Token for pagination (default: None)
        **kwargs: Additional parameters to pass to list_objects_v2

    Returns:
        Dict with objects list and pagination information

    Raises:
        S3Error: When listing objects fails

    Examples:
        >>> s3_client = create_client(session)
        >>> result = list_objects(s3_client, 'my-bucket', prefix='data/')
        >>> for obj in result['objects']:
        ...     print(obj['key'])
    """
    params: Dict[str, Any] = {"Bucket": bucket, "MaxKeys": max_keys, **kwargs}

    if prefix:
        params["Prefix"] = prefix
    if continuation_token:
        params["ContinuationToken"] = continuation_token

    try:
        response = client.list_objects_v2(**params)
    except Exception as e:
        raise S3Error(f"Failed to list objects in bucket '{bucket}': {e}") from e

    objects = []
    for item in response.get("Contents", []):
        objects.append(
            {
                "key": item.get("Key"),
                "size": item.get("Size"),
                "last_modified": item.get("LastModified"),
                "etag": item.get("ETag"),
                "storage_class": item.get("StorageClass", "STANDARD"),
            }
        )

    return {
        "bucket": bucket,
        "prefix": prefix,
        "objects": objects,
        "truncated": response.get("IsTruncated", False),
        "next_token": response.get("NextContinuationToken"),
        "key_count": response.get("KeyCount", len(objects)),
        "max_keys": max_keys,
    }


def get_object(
    client: Any, bucket: str, key: str, stream: bool = False, max_retries: int = 3, **kwargs: Any
) -> Dict[str, Any] | Iterator[bytes]:
    """Get an object from S3 with optional streaming support.

    Args:
        client: S3 client instance
        bucket: S3 bucket name
        key: Object key
        stream: Whether to return streaming iterator (default: False)
        max_retries: Maximum number of retry attempts (default: 3)
        **kwargs: Additional parameters to pass to get_object

    Returns:
        Dict with object data and metadata, or streaming iterator if stream=True

    Raises:
        S3Error: When getting object fails after retries

    Examples:
        >>> # Get small object
        >>> result = get_object(s3_client, 'bucket', 'file.txt')
        >>> content = result['data']

        >>> # Stream large object
        >>> for chunk in get_object(s3_client, 'bucket', 'large.dat', stream=True):
        ...     process_chunk(chunk)
    """
    params = {"Bucket": bucket, "Key": key, **kwargs}

    def _get_with_retry() -> Any:
        """Internal function to get object with retry logic."""
        for attempt in range(max_retries + 1):
            try:
                return client.get_object(**params)
            except Exception as e:
                if attempt == max_retries:
                    raise S3Error(
                        f"Failed to get object '{key}' from bucket '{bucket}' after {max_retries} retries: {e}"
                    ) from e

                # Exponential backoff: 1s, 2s, 4s, 8s...
                delay = 2**attempt
                logger.debug(f"S3 get_object attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                time.sleep(delay)

    response = _get_with_retry()

    if stream:
        # Return streaming iterator for large objects
        def stream_chunks(chunk_size: int = 8192) -> Iterator[bytes]:
            try:
                body = response['Body']
                if hasattr(body, 'iter_chunks'):
                    # Use native streaming if available
                    yield from body.iter_chunks(chunk_size)
                else:
                    # Fallback to manual chunking
                    while True:
                        chunk = body.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
            finally:
                body.close()

        return stream_chunks()
    else:
        # Return all data for small objects
        body = response['Body']
        try:
            data = body.read()
        finally:
            body.close()

        return {
            "data": data,
            "content_length": response.get("ContentLength"),
            "content_type": response.get("ContentType"),
            "etag": response.get("ETag"),
            "last_modified": response.get("LastModified"),
            "metadata": response.get("Metadata", {}),
        }


def put_object(
    client: Any,
    bucket: str,
    key: str,
    data: bytes | str,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Put an object to S3 with optional metadata.

    Args:
        client: S3 client instance
        bucket: S3 bucket name
        key: Object key
        data: Object data (bytes or string)
        content_type: Content type for the object (default: None)
        metadata: Custom metadata dict (default: None)
        **kwargs: Additional parameters to pass to put_object

    Returns:
        Dict with upload result

    Raises:
        S3Error: When putting object fails

    Examples:
        >>> result = put_object(s3_client, 'bucket', 'file.txt', b'content')
        >>> print(result['etag'])

        >>> # With metadata
        >>> result = put_object(
        ...     s3_client, 'bucket', 'data.json',
        ...     data=json.dumps(data).encode(),
        ...     content_type='application/json',
        ...     metadata={'version': '1.0'}
        ... )
    """
    params: Dict[str, Any] = {"Bucket": bucket, "Key": key, "Body": data, **kwargs}

    if content_type:
        params["ContentType"] = content_type
    if metadata:
        params["Metadata"] = metadata

    try:
        response = client.put_object(**params)
        return {
            "success": True,
            "etag": response.get("ETag"),
            "version_id": response.get("VersionId"),
            "size": len(data) if isinstance(data, (bytes, str)) else None,
        }
    except Exception as e:
        raise S3Error(f"Failed to put object '{key}' to bucket '{bucket}': {e}") from e


def delete_object(client: Any, bucket: str, key: str, **kwargs: Any) -> Dict[str, Any]:
    """Delete an object from S3.

    Args:
        client: S3 client instance
        bucket: S3 bucket name
        key: Object key
        **kwargs: Additional parameters to pass to delete_object

    Returns:
        Dict with deletion result

    Raises:
        S3Error: When deleting object fails

    Examples:
        >>> result = delete_object(s3_client, 'bucket', 'old-file.txt')
        >>> print(result['deleted'])
    """
    params = {"Bucket": bucket, "Key": key, **kwargs}

    try:
        response = client.delete_object(**params)
        return {
            "deleted": True,
            "delete_marker": response.get("DeleteMarker", False),
            "version_id": response.get("VersionId"),
        }
    except Exception as e:
        raise S3Error(f"Failed to delete object '{key}' from bucket '{bucket}': {e}") from e


def object_exists(client: Any, bucket: str, key: str, **kwargs: Any) -> bool:
    """Check if an object exists in S3.

    Args:
        client: S3 client instance
        bucket: S3 bucket name
        key: Object key
        **kwargs: Additional parameters to pass to head_object

    Returns:
        True if object exists, False otherwise

    Examples:
        >>> if object_exists(s3_client, 'bucket', 'file.txt'):
        ...     print("File exists")
    """
    params = {"Bucket": bucket, "Key": key, **kwargs}

    try:
        client.head_object(**params)
        return True
    except Exception:
        return False
