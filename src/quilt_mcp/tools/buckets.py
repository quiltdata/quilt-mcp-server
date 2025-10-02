from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..clients import catalog as catalog_client
from ..constants import DEFAULT_BUCKET
from ..runtime import get_active_token
from ..utils import format_error_response, generate_signed_url, get_s3_client, parse_s3_uri, resolve_catalog_url

logger = logging.getLogger(__name__)

# Helpers


def _normalize_bucket(uri_or_name: str) -> str:
    if uri_or_name.startswith("s3://"):
        return uri_or_name[5:].split("/", 1)[0]
    return uri_or_name


def buckets_discover() -> Dict[str, Any]:
    """
    Discover all accessible buckets using GraphQL.
    
    Returns:
        Dict with bucket information including names, titles, descriptions, and access levels.
    """
    token = get_active_token()
    if not token:
        return format_error_response("Authorization token required for bucket discovery")
    
    catalog_url = resolve_catalog_url()
    if not catalog_url:
        return format_error_response("Catalog URL not configured")
    
    try:
        # Query all bucket configs with collaborators to get permission levels
        buckets_query = """
            query BucketConfigs {
                bucketConfigs {
                    name
                    title
                    description
                    browsable
                    lastIndexed
                    collaborators {
                        collaborator {
                            email
                            username
                        }
                        permissionLevel
                    }
                }
            }
        """
        
        buckets_data = catalog_client.catalog_graphql_query(
            registry_url=catalog_url,
            query=buckets_query,
            auth_token=token,
        )
        
        all_buckets = buckets_data.get("bucketConfigs", [])
        
        # Get user email for permission checking
        user_email = None
        try:
            me_data = catalog_client.catalog_graphql_query(
                registry_url=catalog_url,
                query="query { me { email } }",
                auth_token=token,
            )
            user_email = me_data.get("me", {}).get("email")
        except Exception:
            pass
        
        # Format bucket info with actual permission levels
        formatted_buckets = []
        for bucket in all_buckets:
            # Determine actual permission level from collaborators
            permission_level = "read_access"  # Default
            collaborators = bucket.get("collaborators", [])
            
            for collab in collaborators:
                collab_email = collab.get("collaborator", {}).get("email")
                if collab_email == user_email:
                    level = collab.get("permissionLevel")
                    if level == "READ_WRITE":
                        permission_level = "write_access"
                    elif level == "READ":
                        permission_level = "read_access"
                    break
            
            # Check if user is admin (admin users get write access to all buckets)
            if permission_level == "read_access" and user_email:
                try:
                    me_data = catalog_client.catalog_graphql_query(
                        registry_url=catalog_url,
                        query="query { me { isAdmin } }",
                        auth_token=token,
                    )
                    is_admin = me_data.get("me", {}).get("isAdmin", False)
                    if is_admin:
                        permission_level = "write_access"
                except Exception:
                    pass
            
            formatted_buckets.append({
                "name": bucket["name"],
                "title": bucket.get("title", ""),
                "description": bucket.get("description", ""),
                "browsable": bucket.get("browsable", False),
                "last_indexed": bucket.get("lastIndexed"),
                "permission_level": permission_level,
                "accessible": True,
            })
        
        # Categorize buckets by access level
        categorized = {
            "write_access": [b for b in formatted_buckets if b.get("permission_level") == "write_access"],
            "read_access": [b for b in formatted_buckets if b.get("permission_level") == "read_access"],
        }
        
        return {
            "success": True,
            "buckets": formatted_buckets,
            "categorized_buckets": categorized,
            "total_buckets": len(formatted_buckets),
            "user_email": user_email,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
    except Exception as e:
        logger.exception(f"Error discovering buckets: {e}")
        return format_error_response(f"Failed to discover buckets: {str(e)}")


def bucket_objects_list(
    bucket: str = DEFAULT_BUCKET,
    prefix: str = "",
    max_keys: int = 100,
    continuation_token: str = "",
    include_signed_urls: bool = True,
) -> dict[str, Any]:
    """List objects in an S3 bucket with optional prefix filtering.

    Args:
        bucket: S3 bucket name or s3:// URI (default: DEFAULT_BUCKET)
        prefix: Filter objects by prefix (default: "")
        max_keys: Maximum number of objects to return, 1-1000 (default: 100)
        continuation_token: Token for paginating through large result sets (default: "")
        include_signed_urls: Include presigned download URLs for each object (default: True)

    Returns:
        Dict with bucket info, objects list, and pagination details.
    """
    bkt = _normalize_bucket(bucket)
    max_keys = max(1, min(max_keys, 1000))
    client = get_s3_client()
    params: dict[str, Any] = {"Bucket": bkt, "MaxKeys": max_keys}
    if prefix:
        params["Prefix"] = prefix
    if continuation_token:
        params["ContinuationToken"] = continuation_token
    try:
        resp = client.list_objects_v2(**params)
    except Exception as e:
        return {"error": f"Failed to list objects: {e}", "bucket": bkt}
    objects: list[dict[str, Any]] = []
    for item in resp.get("Contents", []) or []:
        key = item.get("Key")
        s3_uri = f"s3://{bkt}/{key}"
        obj_data = {
            "key": key,
            "s3_uri": s3_uri,
            "size": item.get("Size"),
            "last_modified": str(item.get("LastModified")),
            "etag": item.get("ETag"),
            "storage_class": item.get("StorageClass"),
        }
        if include_signed_urls:
            signed_url = generate_signed_url(s3_uri)
            if signed_url:
                obj_data["download_url"] = signed_url
        objects.append(obj_data)
    return {
        "bucket": bkt,
        "prefix": prefix,
        "objects": objects,
        "truncated": resp.get("IsTruncated", False),
        "next_token": resp.get("NextContinuationToken", ""),
        "key_count": resp.get("KeyCount", len(objects)),
        "max_keys": max_keys,
    }


def bucket_object_info(s3_uri: str) -> dict[str, Any]:
    """Get metadata information for a specific S3 object.

    Args:
        s3_uri: Full S3 URI, optionally with versionId query parameter
                Examples:
                - "s3://bucket-name/path/to/object"
                - "s3://bucket-name/path/to/object?versionId=abc123"

    Returns:
        Dict with object metadata including size, content type, etag, and modification date.
        For versioned objects, includes version-specific metadata.

    Version-specific Error Responses:
        - InvalidVersionId: Generic error with operation details
        - NoSuchVersion: "Version {versionId} not found for {s3_uri}"
        - AccessDenied (with versionId): "Access denied for version {versionId} of {s3_uri}"
    """
    try:
        bucket, key, version_id = parse_s3_uri(s3_uri)
    except ValueError as e:
        return {"error": str(e)}

    client = get_s3_client()
    try:
        # Build params dict and conditionally add VersionId
        params = {"Bucket": bucket, "Key": key}
        if version_id:
            params["VersionId"] = version_id
        head = client.head_object(**params)
    except Exception as e:
        # Handle version-specific errors
        if hasattr(e, 'response') and 'Error' in e.response:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchVersion':
                return {"error": f"Version {version_id} not found for {s3_uri}", "bucket": bucket, "key": key}
            elif error_code == 'AccessDenied' and version_id:
                return {"error": f"Access denied for version {version_id} of {s3_uri}", "bucket": bucket, "key": key}
        return {"error": f"Failed to head object: {e}", "bucket": bucket, "key": key}
    return {
        "bucket": bucket,
        "key": key,
        "size": head.get("ContentLength"),
        "content_type": head.get("ContentType"),
        "etag": head.get("ETag"),
        "last_modified": str(head.get("LastModified")),
        "metadata": head.get("Metadata", {}),
        "storage_class": head.get("StorageClass"),
        "cache_control": head.get("CacheControl"),
    }


def bucket_object_text(s3_uri: str, max_bytes: int = 65536, encoding: str = "utf-8") -> dict[str, Any]:
    """Read text content from an S3 object.

    Args:
        s3_uri: Full S3 URI, optionally with versionId query parameter
                Examples:
                - "s3://bucket-name/path/to/file.txt"
                - "s3://bucket-name/path/to/file.txt?versionId=xyz"
        max_bytes: Maximum bytes to read (default: 65536)
        encoding: Text encoding to use (default: "utf-8")

    Returns:
        Dict with decoded text content and metadata.
        For versioned objects, retrieves content from the specific version.

    Version-specific Error Responses:
        - InvalidVersionId: Generic error with operation details
        - NoSuchVersion: "Version {versionId} not found for {s3_uri}"
        - AccessDenied (with versionId): "Access denied for version {versionId} of {s3_uri}"
    """
    try:
        bucket, key, version_id = parse_s3_uri(s3_uri)
    except ValueError as e:
        return {"error": str(e)}

    client = get_s3_client()
    try:
        # Build params dict and conditionally add VersionId
        params = {"Bucket": bucket, "Key": key}
        if version_id:
            params["VersionId"] = version_id
        obj = client.get_object(**params)
        body = obj["Body"].read(max_bytes + 1)
    except Exception as e:
        # Handle version-specific errors
        if hasattr(e, 'response') and 'Error' in e.response:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchVersion':
                return {"error": f"Version {version_id} not found for {s3_uri}", "bucket": bucket, "key": key}
            elif error_code == 'AccessDenied' and version_id:
                return {"error": f"Access denied for version {version_id} of {s3_uri}", "bucket": bucket, "key": key}
        return {"error": f"Failed to get object: {e}", "bucket": bucket, "key": key}
    truncated = len(body) > max_bytes
    if truncated:
        body = body[:max_bytes]
    try:
        text = body.decode(encoding, errors="replace")
    except Exception as e:
        return {"error": f"Decode failed: {e}", "bucket": bucket, "key": key}
    return {
        "bucket": bucket,
        "key": key,
        "encoding": encoding,
        "truncated": truncated,
        "max_bytes": max_bytes,
        "text": text,
    }


def bucket_objects_put(bucket: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Upload multiple objects to an S3 bucket.

    Args:
        bucket: S3 bucket name or s3:// URI
        items: List of objects to upload, each with 'key' and either 'text' or 'data' (base64)
               Optional: 'content_type', 'encoding' (for text), 'metadata' dict

    Returns:
        Dict with upload results and summary statistics.
    """
    import base64

    bkt = _normalize_bucket(bucket)
    if not items:
        return {"error": "items list is empty", "bucket": bkt}
    client = get_s3_client()
    results: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        key = item.get("key")
        if not key or not isinstance(key, str):
            results.append({"index": idx, "error": "missing key"})
            continue
        text = item.get("text")
        data_b64 = item.get("data")
        if (text is None) == (data_b64 is None):
            results.append({"key": key, "error": "provide exactly one of text or data"})
            continue
        if text is not None:
            encoding = item.get("encoding", "utf-8")
            try:
                body = text.encode(encoding)
            except Exception as e:
                results.append({"key": key, "error": f"encode failed: {e}"})
                continue
        else:
            try:
                body = base64.b64decode(str(data_b64), validate=True)
            except Exception as e:
                results.append({"key": key, "error": f"base64 decode failed: {e}"})
                continue
        put_kwargs: dict[str, Any] = {"Bucket": bkt, "Key": key, "Body": body}
        if item.get("content_type"):
            put_kwargs["ContentType"] = item["content_type"]
        if item.get("metadata") and isinstance(item.get("metadata"), dict):
            put_kwargs["Metadata"] = item["metadata"]
        try:
            resp = client.put_object(**put_kwargs)
            results.append(
                {
                    "key": key,
                    "etag": resp.get("ETag"),
                    "size": len(body),
                    "content_type": put_kwargs.get("ContentType"),
                }
            )
        except Exception as e:
            results.append({"key": key, "error": str(e)})
    successes = sum(1 for r in results if "etag" in r)
    return {
        "bucket": bkt,
        "requested": len(items),
        "uploaded": successes,
        "results": results,
    }


def bucket_object_fetch(s3_uri: str, max_bytes: int = 65536, base64_encode: bool = True) -> dict[str, Any]:
    """Fetch binary or text data from an S3 object.

    Args:
        s3_uri: Full S3 URI, optionally with versionId query parameter
                Examples:
                - "s3://bucket-name/path/to/file"
                - "s3://bucket-name/path/to/file?versionId=xyz"
        max_bytes: Maximum bytes to read (default: 65536)
        base64_encode: Return binary data as base64 (default: True)

    Returns:
        Dict with object data as base64 or text, plus metadata.
        For versioned objects, fetches data from the specific version.

    Version-specific Error Responses:
        - InvalidVersionId: Generic error with operation details
        - NoSuchVersion: "Version {versionId} not found for {s3_uri}"
        - AccessDenied (with versionId): "Access denied for version {versionId} of {s3_uri}"
    """
    import base64

    try:
        bucket, key, version_id = parse_s3_uri(s3_uri)
    except ValueError as e:
        return {"error": str(e)}

    client = get_s3_client()
    try:
        # Build params dict and conditionally add VersionId
        params = {"Bucket": bucket, "Key": key}
        if version_id:
            params["VersionId"] = version_id
        obj = client.get_object(**params)
        body = obj["Body"].read(max_bytes + 1)
        content_type = obj.get("ContentType")
    except Exception as e:
        # Handle version-specific errors
        if hasattr(e, 'response') and 'Error' in e.response:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchVersion':
                return {"error": f"Version {version_id} not found for {s3_uri}", "bucket": bucket, "key": key}
            elif error_code == 'AccessDenied' and version_id:
                return {"error": f"Access denied for version {version_id} of {s3_uri}", "bucket": bucket, "key": key}
        return {"error": f"Failed to get object: {e}", "bucket": bucket, "key": key}
    truncated = len(body) > max_bytes
    if truncated:
        body = body[:max_bytes]
    if base64_encode:
        data = base64.b64encode(body).decode("ascii")
        return {
            "bucket": bucket,
            "key": key,
            "truncated": truncated,
            "max_bytes": max_bytes,
            "base64": True,
            "data": data,
            "content_type": content_type,
            "size": len(body),
        }
    try:
        text = body.decode("utf-8")
        return {
            "bucket": bucket,
            "key": key,
            "truncated": truncated,
            "max_bytes": max_bytes,
            "base64": False,
            "text": text,
            "content_type": content_type,
            "size": len(body),
        }
    except Exception:
        data = base64.b64encode(body).decode("ascii")
        return {
            "bucket": bucket,
            "key": key,
            "truncated": truncated,
            "max_bytes": max_bytes,
            "base64": True,
            "data": data,
            "content_type": content_type,
            "size": len(body),
            "note": "Binary data returned as base64 after decode failure",
        }


def bucket_object_link(s3_uri: str, expiration: int = 3600) -> dict[str, Any]:
    """Generate a presigned URL for downloading an S3 object.

    Args:
        s3_uri: Full S3 URI, optionally with versionId query parameter
                Examples:
                - "s3://bucket-name/path/to/file"
                - "s3://bucket-name/path/to/file?versionId=xyz"
        expiration: URL expiration time in seconds (default: 3600, max: 604800)

    Returns:
        Dict with presigned URL and metadata.
        For versioned objects, generates URL for the specific version.

    Version-specific Error Responses:
        - InvalidVersionId: Generic error with operation details
        - NoSuchVersion: "Version {versionId} not found for {s3_uri}"
        - AccessDenied (with versionId): "Access denied for version {versionId} of {s3_uri}"
    """
    try:
        bucket, key, version_id = parse_s3_uri(s3_uri)
    except ValueError as e:
        return {"error": str(e)}

    expiration = max(1, min(expiration, 604800))
    client = get_s3_client()
    try:
        # Build params dict and conditionally add VersionId
        params = {"Bucket": bucket, "Key": key}
        if version_id:
            params["VersionId"] = version_id
        url = client.generate_presigned_url("get_object", Params=params, ExpiresIn=expiration)
        return {
            "bucket": bucket,
            "key": key,
            "presigned_url": url,
            "expires_in": expiration,
        }
    except Exception as e:
        # Handle version-specific errors
        if hasattr(e, 'response') and 'Error' in e.response:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchVersion':
                return {"error": f"Version {version_id} not found for {s3_uri}", "bucket": bucket, "key": key}
            elif error_code == 'AccessDenied' and version_id:
                return {"error": f"Access denied for version {version_id} of {s3_uri}", "bucket": bucket, "key": key}
        return {
            "error": f"Failed to generate presigned URL: {e}",
            "bucket": bucket,
            "key": key,
        }


def bucket_objects_search(
    bucket: str,
    query: str | dict,
    limit: int = 10,
    registry_url: str | None = None,
) -> dict[str, Any]:
    """DEPRECATED: Use search.unified_search instead.
    
    This function is deprecated and will be removed in a future version.
    Use search.unified_search with scope="bucket" and target=bucket for better results.
    
    Args:
        bucket: S3 bucket name or s3:// URI
        query: Search query string or dictionary-based DSL query
        limit: Maximum number of results to return (default: 10)
        registry_url: Registry URL (deprecated parameter)

    Returns:
        Dict with deprecation warning and redirect to unified search.
    """
    from .search import unified_search
    
    bkt = _normalize_bucket(bucket)
    
    # Redirect to unified search
    try:
        search_result = unified_search(
            query=str(query) if isinstance(query, dict) else query,
            scope="bucket",
            target=bkt,
            limit=limit,
            include_metadata=True
        )
        
        return {
            "success": True,
            "deprecated": True,
            "message": "bucket_objects_search is deprecated. Use search.unified_search instead.",
            "bucket": bkt,
            "query": query,
            "limit": limit,
            "redirected_to": "search.unified_search",
            "search_results": search_result
        }
    except Exception as e:
        return {
            "success": False,
            "deprecated": True,
            "error": f"Deprecated function failed to redirect to unified search: {e}",
            "message": "bucket_objects_search is deprecated. Use search.unified_search instead.",
            "bucket": bkt,
            "query": query,
        }


def bucket_objects_search_graphql(
    bucket: str,
    object_filter: dict | None = None,
    first: int = 100,
    after: str = "",
    registry_url: str | None = None,
) -> dict[str, Any]:
    """Search bucket objects via Quilt Catalog GraphQL.

    This is a generic GraphQL-powered search that can express rich filters and
    returns objects with optional package linkage where available.

    Args:
        bucket: S3 bucket name or s3:// URI
        object_filter: Dictionary of filter fields compatible with the catalog schema
        first: Page size (default 100)
        after: Cursor for pagination

    Returns:
        Dict with objects, pagination info, and the effective filter used.
    """
    bkt = _normalize_bucket(bucket)
    token = get_active_token()
    if not token:
        error = format_error_response("Authorization token required for bucket GraphQL search")
        error.update({"bucket": bkt, "objects": []})
        return error

    catalog_url = resolve_catalog_url(registry_url)
    if not catalog_url:
        return {
            "success": False,
            "error": "Catalog URL not configured",
            "bucket": bkt,
            "objects": [],
        }

    try:
        data = catalog_client.catalog_bucket_search_graphql(
            registry_url=catalog_url,
            bucket=bkt,
            object_filter=object_filter,
            first=first,
            after=after or None,
            auth_token=token,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": f"GraphQL request failed: {exc}",
            "bucket": bkt,
            "objects": [],
        }

    conn = data.get("objects", {}) if isinstance(data, dict) else {}
    if isinstance(conn, list):
        edges = conn
        page_info = {}
    else:
        edges = conn.get("edges", []) or []
        page_info = conn.get("pageInfo", {}) or {}
    objects = [
        {
            "key": edge.get("node", {}).get("key"),
            "size": edge.get("node", {}).get("size"),
            "updated": edge.get("node", {}).get("updated"),
            "content_type": edge.get("node", {}).get("contentType"),
            "extension": edge.get("node", {}).get("extension"),
            "package": edge.get("node", {}).get("package"),
        }
        for edge in edges
        if isinstance(edge, dict)
    ]

    return {
        "success": True,
        "bucket": bkt,
        "objects": objects,
        "page_info": {
            "end_cursor": page_info.get("endCursor"),
            "has_next_page": page_info.get("hasNextPage", False),
        },
        "filter": object_filter or {},
    }


def buckets(action: str | None = None, params: Optional[Dict[str, Any]] = None) -> dict[str, Any]:
    """
    S3 bucket operations and object management.

    Available actions:
    - discover: Discover all accessible buckets with permission levels
    - object_fetch: Fetch binary or text data from an S3 object
    - object_info: Get metadata information for an S3 object
    - object_link: Generate presigned URL for an S3 object
    - object_text: Read text content from an S3 object
    - objects_list: List objects in an S3 bucket with filtering
    - objects_put: Upload multiple objects to an S3 bucket
    - objects_search: [DEPRECATED] Search objects (use search.unified_search instead)
    - objects_search_graphql: Search objects via GraphQL

    Args:
        action: The operation to perform. If None, returns available actions.
        params: Action-specific parameters

    Returns:
        Action-specific response dictionary

    Examples:
        # Discovery mode
        result = buckets()

        # Discover buckets
        result = buckets(action="discover")

        # List objects
        result = buckets(action="objects_list", params={"bucket": "my-bucket"})

        # Fetch object
        result = buckets(action="object_fetch", params={"s3_uri": "s3://bucket/key"})

    For detailed parameter documentation, see individual action functions.
    """
    actions = {
        "discover": buckets_discover,
        "object_fetch": bucket_object_fetch,
        "object_info": bucket_object_info,
        "object_link": bucket_object_link,
        "object_text": bucket_object_text,
        "objects_list": bucket_objects_list,
        "objects_put": bucket_objects_put,
        "objects_search": bucket_objects_search,
        "objects_search_graphql": bucket_objects_search_graphql,
    }

    # Discovery mode
    if action is None:
        return {
            "module": "buckets",
            "actions": list(actions.keys()),
            "description": "S3 bucket operations and object management via Quilt Catalog",
        }

    params = params or {}
    
    try:
        if action == "discover":
            return buckets_discover()
        elif action == "object_fetch":
            return bucket_object_fetch(**params)
        elif action == "object_info":
            return bucket_object_info(**params)
        elif action == "object_link":
            return bucket_object_link(**params)
        elif action == "object_text":
            return bucket_object_text(**params)
        elif action == "objects_list":
            # Map frontend parameter names to function parameter names
            mapped_params = {}
            if "limit" in params:
                mapped_params["max_keys"] = params["limit"]
            if "bucket" in params:
                mapped_params["bucket"] = params["bucket"]
            if "prefix" in params:
                mapped_params["prefix"] = params["prefix"]
            if "continuation_token" in params:
                mapped_params["continuation_token"] = params["continuation_token"]
            if "include_signed_urls" in params:
                mapped_params["include_signed_urls"] = params["include_signed_urls"]
            return bucket_objects_list(**mapped_params)
        elif action == "objects_put":
            # Map frontend parameter names to function parameter names
            mapped_params = {}
            if "bucket" in params:
                mapped_params["bucket"] = params["bucket"]
            if "objects" in params:
                mapped_params["items"] = params["objects"]
            return bucket_objects_put(**mapped_params)
        elif action == "objects_search":
            return bucket_objects_search(**params)
        elif action == "objects_search_graphql":
            return bucket_objects_search_graphql(**params)
        else:
            return format_error_response(f"Unknown buckets action: {action}")
    
    except Exception as exc:
        logger.exception(f"Error executing buckets action '{action}': {exc}")
        return format_error_response(f"Failed to execute buckets action '{action}': {str(exc)}")
