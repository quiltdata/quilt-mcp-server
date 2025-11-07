from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from ..constants import DEFAULT_BUCKET
from ..models import (
    BucketObjectFetchError,
    BucketObjectFetchResponse,
    BucketObjectFetchSuccess,
    BucketObjectInfoError,
    BucketObjectInfoResponse,
    BucketObjectInfoSuccess,
    BucketObjectsListError,
    BucketObjectsListResponse,
    BucketObjectsListSuccess,
    BucketObjectsPutError,
    BucketObjectsPutResponse,
    BucketObjectsPutSuccess,
    BucketObjectTextError,
    BucketObjectTextResponse,
    BucketObjectTextSuccess,
    ObjectMetadata,
    PresignedUrlResponse,
    S3Object,
    UploadResult,
)
from ..services.quilt_service import QuiltService
from ..utils import generate_signed_url, parse_s3_uri
from .auth_helpers import AuthorizationContext, check_s3_authorization

# Helpers


def _normalize_bucket(uri_or_name: str) -> str:
    if uri_or_name.startswith("s3://"):
        return uri_or_name[5:].split("/", 1)[0]
    return uri_or_name


def _authorize_s3(
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    context: dict[str, Any],
) -> tuple[AuthorizationContext | None, dict[str, Any] | None]:
    auth_ctx = check_s3_authorization(tool_name, tool_args)
    if not auth_ctx.authorized or auth_ctx.s3_client is None:
        error_payload = auth_ctx.error_response()
        error_payload.update(context)
        return None, error_payload
    return auth_ctx, None


def _attach_auth_metadata(payload: dict[str, Any], auth_ctx: AuthorizationContext | None) -> dict[str, Any]:
    if auth_ctx and auth_ctx.auth_type:
        payload.setdefault("auth_type", auth_ctx.auth_type)
    return payload


def bucket_objects_list(
    bucket: Annotated[
        str,
        Field(
            description="S3 bucket name or s3:// URI",
            examples=["my-bucket", "s3://my-bucket"],
        ),
    ],
    prefix: Annotated[
        str,
        Field(
            default="",
            description="Filter objects by prefix (e.g., 'data/' to list only objects in data folder)",
            examples=["", "data/", "experiments/2024/"],
        ),
    ] = "",
    max_keys: Annotated[
        int,
        Field(
            default=100,
            ge=1,
            le=1000,
            description="Maximum number of objects to return (1-1000)",
        ),
    ] = 100,
    continuation_token: Annotated[
        str,
        Field(
            default="",
            description="Token for paginating through large result sets (from previous response)",
        ),
    ] = "",
    include_signed_urls: Annotated[
        bool,
        Field(
            default=True,
            description="Include presigned download URLs for each object",
        ),
    ] = True,
) -> BucketObjectsListResponse:
    """List objects in an S3 bucket with optional prefix filtering - S3 bucket exploration and object retrieval tasks

    Args:
        bucket: S3 bucket name or s3:// URI
        prefix: Filter objects by prefix (e.g., 'data/' to list only objects in data folder)
        max_keys: Maximum number of objects to return (1-1000)
        continuation_token: Token for paginating through large result sets (from previous response)
        include_signed_urls: Include presigned download URLs for each object

    Returns:
        BucketObjectsListSuccess on success with bucket info and objects list,
        BucketObjectsListError on failure with error details.

    Next step:
        Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.

    Example:
        ```python
        from quilt_mcp.tools import buckets

        result = buckets.bucket_objects_list(bucket="my-bucket", prefix="data/")
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    bkt = _normalize_bucket(bucket)
    auth_ctx, error = _authorize_s3(
        "bucket_objects_list",
        {"bucket": bkt},
        context={"bucket": bkt, "prefix": prefix},
    )
    if error:
        return BucketObjectsListError(
            error=error.get("error", "Authorization failed"),
            bucket=bkt,
            prefix=prefix or None,
        )

    assert auth_ctx is not None, "auth_ctx should not be None after error check"
    client = auth_ctx.s3_client
    assert client is not None, "s3_client should not be None after authorization"
    s3_params: dict[str, Any] = {"Bucket": bkt, "MaxKeys": max_keys}
    if prefix:
        s3_params["Prefix"] = prefix
    if continuation_token:
        s3_params["ContinuationToken"] = continuation_token

    try:
        resp = client.list_objects_v2(**s3_params)
    except Exception as e:
        return BucketObjectsListError(
            error=f"Failed to list objects: {e}",
            bucket=bkt,
            prefix=prefix or None,
        )

    objects: list[S3Object] = []
    for item in resp.get("Contents", []) or []:
        key = item.get("Key")
        s3_uri = f"s3://{bkt}/{key}"
        signed_url = None
        if include_signed_urls:
            signed_url = generate_signed_url(s3_uri)

        objects.append(
            S3Object(
                key=key,
                s3_uri=s3_uri,
                size=item.get("Size", 0),
                last_modified=str(item.get("LastModified")),
                etag=item.get("ETag", ""),
                storage_class=item.get("StorageClass"),
                signed_url=signed_url,
            )
        )

    return BucketObjectsListSuccess(
        bucket=bkt,
        prefix=prefix,
        objects=objects,
        count=len(objects),
        is_truncated=resp.get("IsTruncated", False),
        next_continuation_token=resp.get("NextContinuationToken"),
        auth_type=auth_ctx.auth_type if auth_ctx else None,
    )


def bucket_object_info(
    s3_uri: Annotated[
        str,
        Field(
            description="Full S3 URI to the object, optionally with versionId query parameter",
            examples=[
                "s3://bucket-name/path/to/object",
                "s3://bucket-name/path/to/object?versionId=abc123",
            ],
            pattern=r"^s3://[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]/.+",
        ),
    ],
) -> BucketObjectInfoResponse:
    """Get metadata information for a specific S3 object - S3 bucket exploration and object retrieval tasks

    Args:
        s3_uri: Full S3 URI to the object, optionally with versionId query parameter

    Returns:
        BucketObjectInfoSuccess on success with object metadata,
        BucketObjectInfoError on failure with error details.

    Version-specific Error Responses:
        - InvalidVersionId: Generic error with operation details
        - NoSuchVersion: "Version {versionId} not found for {s3_uri}"
        - AccessDenied (with versionId): "Access denied for version {versionId} of {s3_uri}"

    Next step:
        Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.

    Example:
        ```python
        from quilt_mcp.tools import buckets

        result = buckets.bucket_object_info(s3_uri="s3://my-bucket/file.csv")
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    try:
        bucket, key, version_id = parse_s3_uri(s3_uri)
    except ValueError as e:
        return BucketObjectInfoError(error=str(e))

    auth_ctx, error = _authorize_s3(
        "bucket_object_info",
        {"bucket": bucket, "key": key},
        context={"bucket": bucket, "key": key},
    )
    if error:
        return BucketObjectInfoError(
            error=error.get("error", "Authorization failed"),
            bucket=bucket,
            key=key,
        )

    assert auth_ctx is not None, "auth_ctx should not be None after error check"
    client = auth_ctx.s3_client
    assert client is not None, "s3_client should not be None after authorization"
    try:
        # Build params dict and conditionally add VersionId
        head_params = {"Bucket": bucket, "Key": key}
        if version_id:
            head_params["VersionId"] = version_id
        head = client.head_object(**head_params)
    except Exception as e:
        # Handle version-specific errors
        if hasattr(e, "response") and "Error" in e.response:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchVersion":
                return BucketObjectInfoError(
                    error=f"Version {version_id} not found for {s3_uri}",
                    bucket=bucket,
                    key=key,
                )
            elif error_code == "AccessDenied" and version_id:
                return BucketObjectInfoError(
                    error=f"Access denied for version {version_id} of {s3_uri}",
                    bucket=bucket,
                    key=key,
                )
        return BucketObjectInfoError(
            error=f"Failed to head object: {e}",
            bucket=bucket,
            key=key,
        )

    return BucketObjectInfoSuccess(
        object=ObjectMetadata(
            bucket=bucket,
            key=key,
            s3_uri=s3_uri,
            size=head.get("ContentLength", 0),
            content_type=head.get("ContentType"),
            last_modified=str(head.get("LastModified")),
            etag=head.get("ETag", ""),
            version_id=version_id,
            metadata=head.get("Metadata", {}),
            storage_class=head.get("StorageClass"),
        ),
        auth_type=auth_ctx.auth_type if auth_ctx else None,
    )


def bucket_object_text(
    s3_uri: Annotated[
        str,
        Field(
            description="Full S3 URI to the object",
            examples=["s3://bucket-name/path/to/file.txt"],
            pattern=r"^s3://[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]/.+",
        ),
    ],
    max_bytes: Annotated[
        int,
        Field(
            default=65536,
            ge=1,
            le=10485760,  # 10MB
            description="Maximum bytes to read (1 byte to 10MB)",
        ),
    ] = 65536,
    encoding: Annotated[
        str,
        Field(
            default="utf-8",
            description="Text encoding to use for decoding",
            examples=["utf-8", "latin-1", "ascii"],
        ),
    ] = "utf-8",
) -> BucketObjectTextResponse:
    """Read text content from an S3 object - S3 bucket exploration and object retrieval tasks

    Args:
        s3_uri: Full S3 URI to the object
        max_bytes: Maximum bytes to read (1 byte to 10MB)
        encoding: Text encoding to use for decoding

    Returns:
        BucketObjectTextSuccess on success with decoded text content,
        BucketObjectTextError on failure with error details.

    Version-specific Error Responses:
        - InvalidVersionId: Generic error with operation details
        - NoSuchVersion: "Version {versionId} not found for {s3_uri}"
        - AccessDenied (with versionId): "Access denied for version {versionId} of {s3_uri}"

    Next step:
        Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.

    Example:
        ```python
        from quilt_mcp.tools import buckets

        result = buckets.bucket_object_text(s3_uri="s3://my-bucket/file.txt")
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    try:
        bucket, key, version_id = parse_s3_uri(s3_uri)
    except ValueError as e:
        return BucketObjectTextError(error=str(e))

    auth_ctx, error = _authorize_s3(
        "bucket_object_text",
        {"bucket": bucket, "key": key},
        context={"bucket": bucket, "key": key},
    )
    if error:
        return BucketObjectTextError(
            error=error.get("error", "Authorization failed"),
            bucket=bucket,
            key=key,
        )

    assert auth_ctx is not None, "auth_ctx should not be None after error check"
    client = auth_ctx.s3_client
    assert client is not None, "s3_client should not be None after authorization"
    try:
        # Build params dict and conditionally add VersionId
        get_params = {"Bucket": bucket, "Key": key}
        if version_id:
            get_params["VersionId"] = version_id
        obj = client.get_object(**get_params)
        body = obj["Body"].read(max_bytes + 1)
    except Exception as e:
        # Handle version-specific errors
        if hasattr(e, "response") and "Error" in e.response:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchVersion":
                return BucketObjectTextError(
                    error=f"Version {version_id} not found for {s3_uri}",
                    bucket=bucket,
                    key=key,
                )
            elif error_code == "AccessDenied" and version_id:
                return BucketObjectTextError(
                    error=f"Access denied for version {version_id} of {s3_uri}",
                    bucket=bucket,
                    key=key,
                )
        return BucketObjectTextError(
            error=f"Failed to get object: {e}",
            bucket=bucket,
            key=key,
        )

    truncated = len(body) > max_bytes
    if truncated:
        body = body[:max_bytes]

    try:
        text = body.decode(encoding, errors="replace")
    except Exception as e:
        return BucketObjectTextError(
            error=f"Decode failed: {e}",
            bucket=bucket,
            key=key,
        )

    return BucketObjectTextSuccess(
        bucket=bucket,
        key=key,
        s3_uri=s3_uri,
        text=text,
        encoding=encoding,
        bytes_read=len(body),
        truncated=truncated,
        auth_type=auth_ctx.auth_type if auth_ctx else None,
    )


def bucket_objects_put(
    bucket: Annotated[
        str,
        Field(
            description="S3 bucket name or s3:// URI",
            examples=["my-bucket", "s3://my-bucket"],
        ),
    ],
    items: Annotated[
        list[dict[str, Any]],
        Field(
            description=(
                "List of objects to upload. Each item is a dict with:\n"
                "- key (str, required): S3 key (path) for the object\n"
                "- text (str, optional): Text content to upload (use this OR data, not both)\n"
                "- data (str, optional): Base64-encoded binary content (use this OR text, not both)\n"
                "- content_type (str, optional): MIME type, defaults to 'application/octet-stream'\n"
                "- encoding (str, optional): Text encoding (e.g., 'utf-8') when uploading text\n"
                "- metadata (dict[str, str], optional): Custom metadata key-value pairs"
            ),
            min_length=1,
            examples=[
                # Minimal example
                [{"key": "hello.txt", "text": "Hello World"}],
                # With content type
                [
                    {
                        "key": "data.csv",
                        "text": "col1,col2\n1,2",
                        "content_type": "text/csv",
                    }
                ],
                # Binary data
                [
                    {
                        "key": "image.png",
                        "data": "iVBORw0KGgo...",
                        "content_type": "image/png",
                    }
                ],
                # With metadata
                [
                    {
                        "key": "report.txt",
                        "text": "Report content",
                        "content_type": "text/plain",
                        "encoding": "utf-8",
                        "metadata": {"author": "system", "version": "1.0"},
                    }
                ],
            ],
        ),
    ],
) -> BucketObjectsPutResponse:
    """Upload multiple objects to an S3 bucket - S3 bucket exploration and object retrieval tasks

    Args:
        bucket: S3 bucket name or s3:// URI
        items: List of objects to upload, each with key and content

    Returns:
        BucketObjectsPutSuccess on success with upload results,
        BucketObjectsPutError on failure with error details.

    Next step:
        Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.

    Example:
        ```python
        from quilt_mcp.tools import buckets

        items = [{"key": "file.txt", "text": "Hello World"}]
        result = buckets.bucket_objects_put(bucket="my-bucket", items=items)
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    import base64

    bkt = _normalize_bucket(bucket)
    auth_ctx, error = _authorize_s3(
        "bucket_objects_put",
        {"bucket": bkt},
        context={"bucket": bkt},
    )
    if error:
        return BucketObjectsPutError(
            error=error.get("error", "Authorization failed"),
            bucket=bkt,
        )

    assert auth_ctx is not None, "auth_ctx should not be None after error check"
    client = auth_ctx.s3_client
    assert client is not None, "s3_client should not be None after authorization"
    results: list[UploadResult] = []
    for item in items:
        # Get item key (validated by Pydantic already)
        key = item["key"]

        # Get content (validated by Pydantic to have exactly one)
        text = item.get("text")
        data = item.get("data")

        # Encode the body
        if text is not None:
            encoding = item.get("encoding", "utf-8")
            try:
                body = text.encode(encoding)
            except Exception as e:
                results.append(UploadResult(key=key, error=f"encode failed: {e}"))
                continue
        else:
            try:
                body = base64.b64decode(str(data), validate=True)
            except Exception as e:
                results.append(UploadResult(key=key, error=f"base64 decode failed: {e}"))
                continue

        # Build put_object kwargs
        put_kwargs: dict[str, Any] = {"Bucket": bkt, "Key": key, "Body": body}
        content_type = item.get("content_type")
        if content_type:
            put_kwargs["ContentType"] = content_type
        metadata = item.get("metadata")
        if metadata:
            put_kwargs["Metadata"] = metadata

        # Upload the object
        try:
            resp = client.put_object(**put_kwargs)
            results.append(
                UploadResult(
                    key=key,
                    etag=resp.get("ETag"),
                    size=len(body),
                    content_type=put_kwargs.get("ContentType"),
                )
            )
        except Exception as e:
            results.append(UploadResult(key=key, error=str(e)))

    successes = sum(1 for r in results if r.etag is not None)
    failed = len(results) - successes

    return BucketObjectsPutSuccess(
        bucket=bkt,
        requested=len(items),
        uploaded=successes,
        failed=failed,
        results=results,
        auth_type=auth_ctx.auth_type if auth_ctx else None,
    )


def bucket_object_fetch(
    s3_uri: Annotated[
        str,
        Field(
            description="Full S3 URI to the object",
            examples=["s3://bucket-name/path/to/file"],
            pattern=r"^s3://[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]/.+",
        ),
    ],
    max_bytes: Annotated[
        int,
        Field(
            default=65536,
            ge=1,
            le=10485760,  # 10MB
            description="Maximum bytes to read (1 byte to 10MB)",
        ),
    ] = 65536,
    base64_encode: Annotated[
        bool,
        Field(
            default=True,
            description="Return binary data as base64 (true) or attempt text decoding (false)",
        ),
    ] = True,
) -> BucketObjectFetchResponse:
    """Fetch binary or text data from an S3 object - S3 bucket exploration and object retrieval tasks

    Args:
        s3_uri: Full S3 URI to the object
        max_bytes: Maximum bytes to read (1 byte to 10MB)
        base64_encode: Return binary data as base64 (true) or attempt text decoding (false)

    Returns:
        BucketObjectFetchSuccess on success with object data (base64 or text),
        BucketObjectFetchError on failure with error details.

    Version-specific Error Responses:
        - InvalidVersionId: Generic error with operation details
        - NoSuchVersion: "Version {versionId} not found for {s3_uri}"
        - AccessDenied (with versionId): "Access denied for version {versionId} of {s3_uri}"

    Next step:
        Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.

    Example:
        ```python
        from quilt_mcp.tools import buckets

        result = buckets.bucket_object_fetch(s3_uri="s3://my-bucket/file.bin")
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    import base64

    try:
        bucket, key, version_id = parse_s3_uri(s3_uri)
    except ValueError as e:
        return BucketObjectFetchError(error=str(e))

    auth_ctx, error = _authorize_s3(
        "bucket_object_fetch",
        {"bucket": bucket, "key": key},
        context={"bucket": bucket, "key": key},
    )
    if error:
        return BucketObjectFetchError(
            error=error.get("error", "Authorization failed"),
            bucket=bucket,
            key=key,
        )

    assert auth_ctx is not None, "auth_ctx should not be None after error check"
    client = auth_ctx.s3_client
    assert client is not None, "s3_client should not be None after authorization"
    try:
        # Build params dict and conditionally add VersionId
        get_params = {"Bucket": bucket, "Key": key}
        if version_id:
            get_params["VersionId"] = version_id
        obj = client.get_object(**get_params)
        body = obj["Body"].read(max_bytes + 1)
        content_type = obj.get("ContentType")
    except Exception as e:
        # Handle version-specific errors
        if hasattr(e, "response") and "Error" in e.response:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchVersion":
                return BucketObjectFetchError(
                    error=f"Version {version_id} not found for {s3_uri}",
                    bucket=bucket,
                    key=key,
                )
            elif error_code == "AccessDenied" and version_id:
                return BucketObjectFetchError(
                    error=f"Access denied for version {version_id} of {s3_uri}",
                    bucket=bucket,
                    key=key,
                )
        return BucketObjectFetchError(
            error=f"Failed to get object: {e}",
            bucket=bucket,
            key=key,
        )

    truncated = len(body) > max_bytes
    if truncated:
        body = body[:max_bytes]

    # Return base64-encoded or text data
    if base64_encode:
        data = base64.b64encode(body).decode("ascii")
        return BucketObjectFetchSuccess(
            bucket=bucket,
            key=key,
            s3_uri=s3_uri,
            data=data,
            content_type=content_type,
            bytes_read=len(body),
            truncated=truncated,
            is_base64=True,
            auth_type=auth_ctx.auth_type if auth_ctx else None,
        )

    # Try to decode as text
    try:
        text = body.decode("utf-8")
        return BucketObjectFetchSuccess(
            bucket=bucket,
            key=key,
            s3_uri=s3_uri,
            data=text,
            content_type=content_type,
            bytes_read=len(body),
            truncated=truncated,
            is_base64=False,
            auth_type=auth_ctx.auth_type if auth_ctx else None,
        )
    except Exception:
        # Fallback to base64 if text decode fails
        data = base64.b64encode(body).decode("ascii")
        return BucketObjectFetchSuccess(
            bucket=bucket,
            key=key,
            s3_uri=s3_uri,
            data=data,
            content_type=content_type,
            bytes_read=len(body),
            truncated=truncated,
            is_base64=True,
            auth_type=auth_ctx.auth_type if auth_ctx else None,
        )


def bucket_object_link(
    s3_uri: Annotated[
        str,
        Field(
            description="Full S3 URI to the object",
            examples=["s3://bucket-name/path/to/file"],
            pattern=r"^s3://[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]/.+",
        ),
    ],
    expiration: Annotated[
        int,
        Field(
            default=3600,
            ge=1,
            le=604800,  # 7 days
            description="URL expiration time in seconds (1 second to 7 days)",
        ),
    ] = 3600,
) -> PresignedUrlResponse | BucketObjectInfoError:
    """Generate a presigned URL for downloading an S3 object - S3 bucket exploration and object retrieval tasks

    Args:
        s3_uri: Full S3 URI to the object
        expiration: URL expiration time in seconds (1 second to 7 days)

    Returns:
        PresignedUrlResponse on success with presigned URL and metadata,
        BucketObjectInfoError on failure with error details.

    Version-specific Error Responses:
        - InvalidVersionId: Generic error with operation details
        - NoSuchVersion: "Version {versionId} not found for {s3_uri}"
        - AccessDenied (with versionId): "Access denied for version {versionId} of {s3_uri}"

    Next step:
        Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.

    Example:
        ```python
        from quilt_mcp.tools import buckets

        result = buckets.bucket_object_link(s3_uri="s3://my-bucket/file.csv")
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    from datetime import datetime, timedelta, timezone

    try:
        bucket, key, version_id = parse_s3_uri(s3_uri)
    except ValueError as e:
        return BucketObjectInfoError(error=str(e))

    auth_ctx, error = _authorize_s3(
        "bucket_object_link",
        {"bucket": bucket, "key": key},
        context={"bucket": bucket, "key": key},
    )
    if error:
        return BucketObjectInfoError(
            error=error.get("error", "Authorization failed"),
            bucket=bucket,
            key=key,
        )

    assert auth_ctx is not None, "auth_ctx should not be None after error check"
    client = auth_ctx.s3_client
    assert client is not None, "s3_client should not be None after authorization"
    try:
        # Build params dict and conditionally add VersionId
        url_params = {"Bucket": bucket, "Key": key}
        if version_id:
            url_params["VersionId"] = version_id
        url = client.generate_presigned_url("get_object", Params=url_params, ExpiresIn=expiration)

        # Calculate expiration timestamp
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiration)

        return PresignedUrlResponse(
            bucket=bucket,
            key=key,
            s3_uri=s3_uri,
            signed_url=url,
            expiration_seconds=expiration,
            expires_at=expires_at.isoformat(),
            auth_type=auth_ctx.auth_type if auth_ctx else None,
        )
    except Exception as e:
        # Handle version-specific errors
        if hasattr(e, "response") and "Error" in e.response:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchVersion":
                return BucketObjectInfoError(
                    error=f"Version {version_id} not found for {s3_uri}",
                    bucket=bucket,
                    key=key,
                )
            elif error_code == "AccessDenied" and version_id:
                return BucketObjectInfoError(
                    error=f"Access denied for version {version_id} of {s3_uri}",
                    bucket=bucket,
                    key=key,
                )
        return BucketObjectInfoError(
            error=f"Failed to generate presigned URL: {e}",
            bucket=bucket,
            key=key,
        )
