from __future__ import annotations

from typing import Any

from ..constants import DEFAULT_BUCKET
from ..models import (
    BucketObjectFetchError,
    BucketObjectFetchParams,
    BucketObjectFetchResponse,
    BucketObjectFetchSuccess,
    BucketObjectInfoError,
    BucketObjectInfoParams,
    BucketObjectInfoResponse,
    BucketObjectInfoSuccess,
    BucketObjectLinkParams,
    BucketObjectsListError,
    BucketObjectsListParams,
    BucketObjectsListResponse,
    BucketObjectsListSuccess,
    BucketObjectsPutError,
    BucketObjectsPutParams,
    BucketObjectsPutResponse,
    BucketObjectsPutSuccess,
    BucketObjectTextError,
    BucketObjectTextParams,
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
    params: BucketObjectsListParams,
) -> BucketObjectsListResponse:
    """List objects in an S3 bucket with optional prefix filtering - S3 bucket exploration and object retrieval tasks

    Args:
        params: Parameters for listing bucket objects

    Returns:
        BucketObjectsListSuccess on success with bucket info and objects list,
        BucketObjectsListError on failure with error details.

    Next step:
        Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.

    Example:
        ```python
        from quilt_mcp.tools import buckets
        from quilt_mcp.models import BucketObjectsListParams

        params = BucketObjectsListParams(bucket="my-bucket", prefix="data/")
        result = buckets.bucket_objects_list(params)
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    bkt = _normalize_bucket(params.bucket)
    auth_ctx, error = _authorize_s3(
        "bucket_objects_list",
        {"bucket": bkt},
        context={"bucket": bkt, "prefix": params.prefix},
    )
    if error:
        return BucketObjectsListError(
            error=error.get("error", "Authorization failed"),
            bucket=bkt,
            prefix=params.prefix or None,
        )

    client = auth_ctx.s3_client
    s3_params: dict[str, Any] = {"Bucket": bkt, "MaxKeys": params.max_keys}
    if params.prefix:
        s3_params["Prefix"] = params.prefix
    if params.continuation_token:
        s3_params["ContinuationToken"] = params.continuation_token

    try:
        resp = client.list_objects_v2(**s3_params)
    except Exception as e:
        return BucketObjectsListError(
            error=f"Failed to list objects: {e}",
            bucket=bkt,
            prefix=params.prefix or None,
        )

    objects: list[S3Object] = []
    for item in resp.get("Contents", []) or []:
        key = item.get("Key")
        s3_uri = f"s3://{bkt}/{key}"
        signed_url = None
        if params.include_signed_urls:
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
        prefix=params.prefix,
        objects=objects,
        count=len(objects),
        is_truncated=resp.get("IsTruncated", False),
        next_continuation_token=resp.get("NextContinuationToken"),
        auth_type=auth_ctx.auth_type if auth_ctx else None,
    )


def bucket_object_info(params: BucketObjectInfoParams) -> BucketObjectInfoResponse:
    """Get metadata information for a specific S3 object - S3 bucket exploration and object retrieval tasks

    Args:
        params: Parameters for getting object info

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
        from quilt_mcp.models import BucketObjectInfoParams

        params = BucketObjectInfoParams(s3_uri="s3://my-bucket/file.csv")
        result = buckets.bucket_object_info(params)
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    try:
        bucket, key, version_id = parse_s3_uri(params.s3_uri)
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

    client = auth_ctx.s3_client
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
                    error=f"Version {version_id} not found for {params.s3_uri}",
                    bucket=bucket,
                    key=key,
                )
            elif error_code == "AccessDenied" and version_id:
                return BucketObjectInfoError(
                    error=f"Access denied for version {version_id} of {params.s3_uri}",
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
            s3_uri=params.s3_uri,
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


def bucket_object_text(params: BucketObjectTextParams) -> BucketObjectTextResponse:
    """Read text content from an S3 object - S3 bucket exploration and object retrieval tasks

    Args:
        params: Parameters for reading text content

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
        from quilt_mcp.models import BucketObjectTextParams

        params = BucketObjectTextParams(s3_uri="s3://my-bucket/file.txt")
        result = buckets.bucket_object_text(params)
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    try:
        bucket, key, version_id = parse_s3_uri(params.s3_uri)
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

    client = auth_ctx.s3_client
    try:
        # Build params dict and conditionally add VersionId
        get_params = {"Bucket": bucket, "Key": key}
        if version_id:
            get_params["VersionId"] = version_id
        obj = client.get_object(**get_params)
        body = obj["Body"].read(params.max_bytes + 1)
    except Exception as e:
        # Handle version-specific errors
        if hasattr(e, "response") and "Error" in e.response:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchVersion":
                return BucketObjectTextError(
                    error=f"Version {version_id} not found for {params.s3_uri}",
                    bucket=bucket,
                    key=key,
                )
            elif error_code == "AccessDenied" and version_id:
                return BucketObjectTextError(
                    error=f"Access denied for version {version_id} of {params.s3_uri}",
                    bucket=bucket,
                    key=key,
                )
        return BucketObjectTextError(
            error=f"Failed to get object: {e}",
            bucket=bucket,
            key=key,
        )

    truncated = len(body) > params.max_bytes
    if truncated:
        body = body[:params.max_bytes]

    try:
        text = body.decode(params.encoding, errors="replace")
    except Exception as e:
        return BucketObjectTextError(
            error=f"Decode failed: {e}",
            bucket=bucket,
            key=key,
        )

    return BucketObjectTextSuccess(
        bucket=bucket,
        key=key,
        s3_uri=params.s3_uri,
        text=text,
        encoding=params.encoding,
        bytes_read=len(body),
        truncated=truncated,
        auth_type=auth_ctx.auth_type if auth_ctx else None,
    )


def bucket_objects_put(params: BucketObjectsPutParams) -> BucketObjectsPutResponse:
    """Upload multiple objects to an S3 bucket - S3 bucket exploration and object retrieval tasks

    Args:
        params: Parameters for uploading objects

    Returns:
        BucketObjectsPutSuccess on success with upload results,
        BucketObjectsPutError on failure with error details.

    Next step:
        Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.

    Example:
        ```python
        from quilt_mcp.tools import buckets
        from quilt_mcp.models import BucketObjectsPutParams, BucketObjectsPutItem

        items = [BucketObjectsPutItem(key="file.txt", text="Hello World")]
        params = BucketObjectsPutParams(bucket="my-bucket", items=items)
        result = buckets.bucket_objects_put(params)
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    import base64

    bkt = _normalize_bucket(params.bucket)
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

    client = auth_ctx.s3_client
    results: list[UploadResult] = []
    for item in params.items:
        # Validate that exactly one of text or data is provided
        if (item.text is None) == (item.data is None):
            results.append(UploadResult(key=item.key, error="provide exactly one of text or data"))
            continue

        # Encode the body
        if item.text is not None:
            encoding = item.encoding or "utf-8"
            try:
                body = item.text.encode(encoding)
            except Exception as e:
                results.append(UploadResult(key=item.key, error=f"encode failed: {e}"))
                continue
        else:
            try:
                body = base64.b64decode(str(item.data), validate=True)
            except Exception as e:
                results.append(UploadResult(key=item.key, error=f"base64 decode failed: {e}"))
                continue

        # Build put_object kwargs
        put_kwargs: dict[str, Any] = {"Bucket": bkt, "Key": item.key, "Body": body}
        if item.content_type:
            put_kwargs["ContentType"] = item.content_type
        if item.metadata:
            put_kwargs["Metadata"] = item.metadata

        # Upload the object
        try:
            resp = client.put_object(**put_kwargs)
            results.append(
                UploadResult(
                    key=item.key,
                    etag=resp.get("ETag"),
                    size=len(body),
                    content_type=put_kwargs.get("ContentType"),
                )
            )
        except Exception as e:
            results.append(UploadResult(key=item.key, error=str(e)))

    successes = sum(1 for r in results if r.etag is not None)
    failed = len(results) - successes

    return BucketObjectsPutSuccess(
        bucket=bkt,
        requested=len(params.items),
        uploaded=successes,
        failed=failed,
        results=results,
        auth_type=auth_ctx.auth_type if auth_ctx else None,
    )


def bucket_object_fetch(params: BucketObjectFetchParams) -> BucketObjectFetchResponse:
    """Fetch binary or text data from an S3 object - S3 bucket exploration and object retrieval tasks

    Args:
        params: Parameters for fetching object data

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
        from quilt_mcp.models import BucketObjectFetchParams

        params = BucketObjectFetchParams(s3_uri="s3://my-bucket/file.bin")
        result = buckets.bucket_object_fetch(params)
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    import base64

    try:
        bucket, key, version_id = parse_s3_uri(params.s3_uri)
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

    client = auth_ctx.s3_client
    try:
        # Build params dict and conditionally add VersionId
        get_params = {"Bucket": bucket, "Key": key}
        if version_id:
            get_params["VersionId"] = version_id
        obj = client.get_object(**get_params)
        body = obj["Body"].read(params.max_bytes + 1)
        content_type = obj.get("ContentType")
    except Exception as e:
        # Handle version-specific errors
        if hasattr(e, "response") and "Error" in e.response:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchVersion":
                return BucketObjectFetchError(
                    error=f"Version {version_id} not found for {params.s3_uri}",
                    bucket=bucket,
                    key=key,
                )
            elif error_code == "AccessDenied" and version_id:
                return BucketObjectFetchError(
                    error=f"Access denied for version {version_id} of {params.s3_uri}",
                    bucket=bucket,
                    key=key,
                )
        return BucketObjectFetchError(
            error=f"Failed to get object: {e}",
            bucket=bucket,
            key=key,
        )

    truncated = len(body) > params.max_bytes
    if truncated:
        body = body[:params.max_bytes]

    # Return base64-encoded or text data
    if params.base64_encode:
        data = base64.b64encode(body).decode("ascii")
        return BucketObjectFetchSuccess(
            bucket=bucket,
            key=key,
            s3_uri=params.s3_uri,
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
            s3_uri=params.s3_uri,
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
            s3_uri=params.s3_uri,
            data=data,
            content_type=content_type,
            bytes_read=len(body),
            truncated=truncated,
            is_base64=True,
            auth_type=auth_ctx.auth_type if auth_ctx else None,
        )


def bucket_object_link(params: BucketObjectLinkParams) -> PresignedUrlResponse | BucketObjectInfoError:
    """Generate a presigned URL for downloading an S3 object - S3 bucket exploration and object retrieval tasks

    Args:
        params: Parameters for generating presigned URL

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
        from quilt_mcp.models import BucketObjectLinkParams

        params = BucketObjectLinkParams(s3_uri="s3://my-bucket/file.csv")
        result = buckets.bucket_object_link(params)
        # Next step: Use the returned S3 metadata to answer the user's question or pass identifiers into the next bucket tool.
        ```
    """
    from datetime import datetime, timedelta, timezone

    try:
        bucket, key, version_id = parse_s3_uri(params.s3_uri)
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

    client = auth_ctx.s3_client
    try:
        # Build params dict and conditionally add VersionId
        url_params = {"Bucket": bucket, "Key": key}
        if version_id:
            url_params["VersionId"] = version_id
        url = client.generate_presigned_url("get_object", Params=url_params, ExpiresIn=params.expiration)

        # Calculate expiration timestamp
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=params.expiration)

        return PresignedUrlResponse(
            bucket=bucket,
            key=key,
            s3_uri=params.s3_uri,
            signed_url=url,
            expiration_seconds=params.expiration,
            expires_at=expires_at.isoformat(),
            auth_type=auth_ctx.auth_type if auth_ctx else None,
        )
    except Exception as e:
        # Handle version-specific errors
        if hasattr(e, "response") and "Error" in e.response:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchVersion":
                return BucketObjectInfoError(
                    error=f"Version {version_id} not found for {params.s3_uri}",
                    bucket=bucket,
                    key=key,
                )
            elif error_code == "AccessDenied" and version_id:
                return BucketObjectInfoError(
                    error=f"Access denied for version {version_id} of {params.s3_uri}",
                    bucket=bucket,
                    key=key,
                )
        return BucketObjectInfoError(
            error=f"Failed to generate presigned URL: {e}",
            bucket=bucket,
            key=key,
        )
