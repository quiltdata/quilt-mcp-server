from __future__ import annotations

import logging
import base64
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import boto3
import requests
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ..clients import catalog as catalog_client
from ..constants import DEFAULT_BUCKET
from ..runtime import get_active_token
from ..utils import (
    format_error_response,
    resolve_catalog_url,
    fetch_catalog_session_for_request,
)
from ..types.navigation import (
    NavigationContext,
    get_context_bucket,
    get_context_path,
    get_context_version,
    is_object_context,
)

logger = logging.getLogger(__name__)

# Helpers


def _normalize_bucket(uri_or_name: str) -> str:
    if uri_or_name.startswith("s3://"):
        return uri_or_name[5:].split("/", 1)[0]
    return uri_or_name


def _aws_credentials_unavailable(action_name: str, s3_uri_or_bucket: str = "") -> dict[str, Any]:
    """Return a user-friendly error message for actions that require AWS credentials."""
    return {
        "success": False,
        "error": f"The '{action_name}' action requires AWS S3 credentials which are not currently available.",
        "message": (
            "This action needs direct S3 access, but the current JWT token is authentication-only "
            "and doesn't include AWS credentials. "
            "This feature will be available once backend proxy endpoints are implemented."
        ),
        "alternatives": {
            "search_files": "Use search.unified_search to find and list files",
            "view_packages": "Use packaging.list and packaging.browse to explore package contents",
            "upload_files": "Upload files through the Quilt web interface, then use packaging.create",
            "web_interface": "Access files directly through the Quilt catalog web UI",
        },
        "status": "awaiting_backend_support",
        "requested_resource": s3_uri_or_bucket or "unknown",
    }
def _build_s3_client_for_upload(bucket_name: str) -> Tuple[Optional[Any], Dict[str, Any]]:
    """Build an S3 client using catalog-provided credentials with ambient fallback."""

    metadata: Dict[str, Any] = {"bucket": bucket_name}
    attempts: list[str] = []
    session: Optional[boto3.Session] = None

    try:
        session, session_meta = fetch_catalog_session_for_request()
        metadata.update(session_meta)
    except Exception as exc:  # pragma: no cover - catalog may be unreachable in tests
        attempts.append(f"catalog_credentials: {exc}")

    if session is None:
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials is None:
                raise RuntimeError("No AWS credentials available in the default boto3 session")
            metadata.setdefault("source", "ambient")
        except Exception as exc:  # pragma: no cover - only hit when no ambient creds
            attempts.append(f"ambient_credentials: {exc}")
            metadata["credential_attempts"] = attempts
            return None, metadata

    proxy_url = os.getenv("QUILT_S3_PROXY_URL") or os.getenv("S3_PROXY_URL")
    client_kwargs: Dict[str, Any] = {}
    if proxy_url:
        client_kwargs["endpoint_url"] = proxy_url.rstrip("/")
        metadata["proxy_endpoint"] = proxy_url.rstrip("/")

    if attempts:
        metadata["credential_attempts"] = attempts

    client = session.client("s3", config=Config(signature_version="s3v4"), **client_kwargs)
    return client, metadata


def _prepare_upload_body(item: Dict[str, Any]) -> bytes:
    """Convert an upload item payload into raw bytes."""
    if "data" in item and item["data"] is not None:
        try:
            return base64.b64decode(item["data"])
        except Exception as exc:
            raise ValueError(f"Invalid base64 data: {exc}") from exc

    if "text" in item and item["text"] is not None:
        encoding = item.get("encoding") or "utf-8"
        try:
            return item["text"].encode(encoding)
        except Exception as exc:
            raise ValueError(f"Failed to encode text using {encoding}: {exc}") from exc

    body = item.get("body") or item.get("bytes")
    if isinstance(body, bytes):
        return body

    raise ValueError("Upload item must include 'text', 'data', or raw 'body' bytes")


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

            formatted_buckets.append(
                {
                    "name": bucket["name"],
                    "title": bucket.get("title", ""),
                    "description": bucket.get("description", ""),
                    "browsable": bucket.get("browsable", False),
                    "last_indexed": bucket.get("lastIndexed"),
                    "permission_level": permission_level,
                    "accessible": True,
                }
            )

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


def bucket_object_info(path: str = "", s3_uri: str = "", **kwargs) -> dict[str, Any]:
    """Get metadata information for a file using backend proxy.

    Args:
        path: Logical file path within package (e.g., "README.md")
        s3_uri: Alternative: Full S3 URI (legacy, requires AWS creds)
        **kwargs: Additional parameters including _context from frontend

    Returns:
        Dict with object metadata including size, content type, etc.
    """
    import requests

    # Get presigned URL
    link_result = bucket_object_link(path=path, s3_uri=s3_uri, **kwargs)

    if not link_result.get("success"):
        return link_result  # Return error from object_link

    presigned_url = link_result.get("url")
    if not presigned_url:
        return format_error_response("Failed to get presigned URL")

    # HEAD request to get metadata
    try:
        response = requests.head(presigned_url, timeout=10)
        response.raise_for_status()

        return {
            "success": True,
            "path": path or s3_uri,
            "size": int(response.headers.get("Content-Length", 0)),
            "content_type": response.headers.get("Content-Type", ""),
            "etag": response.headers.get("ETag", "").strip('"'),
            "last_modified": response.headers.get("Last-Modified", ""),
            "cache_control": response.headers.get("Cache-Control", ""),
        }
    except Exception as e:
        return format_error_response(f"Failed to get file metadata: {e}")


def bucket_object_text(
    path: str = "", s3_uri: str = "", max_bytes: int = 65536, encoding: str = "utf-8", **kwargs
) -> dict[str, Any]:
    """Read text content from a file using backend proxy.

    Args:
        path: Logical file path within package (e.g., "README.md")
        s3_uri: Alternative: Full S3 URI (legacy, requires AWS creds)
        max_bytes: Maximum bytes to read (default: 65536)
        encoding: Text encoding to use (default: "utf-8")
        **kwargs: Additional parameters including _context from frontend

    Returns:
        Dict with decoded text content and metadata.
    """
    # Use bucket_object_fetch with base64_encode=False to get text
    fetch_result = bucket_object_fetch(path=path, s3_uri=s3_uri, max_bytes=max_bytes, base64_encode=False, **kwargs)

    if not fetch_result.get("success"):
        return fetch_result  # Return error

    # Re-format for text-specific response
    return {
        "success": True,
        "path": fetch_result.get("path"),
        "text": fetch_result.get("text", ""),
        "encoding": encoding,
        "truncated": fetch_result.get("truncated", False),
        "max_bytes": max_bytes,
        "size": fetch_result.get("size", 0),
        "content_type": fetch_result.get("content_type", ""),
    }


def bucket_objects_put(bucket: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Upload multiple objects to an S3 bucket using Quilt-issued credentials."""
    bkt = _normalize_bucket(bucket)

    if not items:
        return format_error_response("No items provided for upload")

    client, client_meta = _build_s3_client_for_upload(bkt)
    if client is None:
        unavailable = _aws_credentials_unavailable("bucket_objects_put", bkt)
        unavailable["details"] = client_meta
        return unavailable

    results: list[Dict[str, Any]] = []
    uploaded = 0

    for item in items:
        key = item.get("key")
        entry_result: Dict[str, Any] = {"key": key}

        if not key or not isinstance(key, str):
            entry_result["error"] = "Each upload item requires a non-empty 'key'"
            results.append(entry_result)
            continue

        try:
            body = _prepare_upload_body(item)
        except ValueError as exc:
            entry_result["error"] = str(exc)
            results.append(entry_result)
            continue

        extra_args: Dict[str, Any] = {}
        content_type = item.get("content_type") or item.get("ContentType")
        if content_type:
            extra_args["ContentType"] = content_type

        metadata = item.get("metadata") or item.get("Metadata")
        if isinstance(metadata, dict):
            cleaned_metadata = {str(k): str(v) for k, v in metadata.items() if v is not None}
            if cleaned_metadata:
                extra_args["Metadata"] = cleaned_metadata

        cache_control = item.get("cache_control") or item.get("CacheControl")
        if cache_control:
            extra_args["CacheControl"] = cache_control

        content_encoding = item.get("content_encoding") or item.get("ContentEncoding")
        if content_encoding:
            extra_args["ContentEncoding"] = content_encoding

        storage_class = item.get("storage_class") or item.get("StorageClass")
        if storage_class:
            extra_args["StorageClass"] = storage_class

        expires = item.get("expires") or item.get("Expires")
        if expires:
            extra_args["Expires"] = expires

        acl = item.get("acl") or item.get("ACL")
        if acl:
            extra_args["ACL"] = acl

        try:
            response = client.put_object(Bucket=bkt, Key=key, Body=body, **extra_args)
            entry_result.update(
                {
                    "success": True,
                    "etag": (response.get("ETag") or "").strip('"'),
                    "version": response.get("VersionId"),
                    "size": len(body),
                }
            )
            if content_type:
                entry_result["content_type"] = content_type
            uploaded += 1
        except (BotoCoreError, ClientError) as exc:
            entry_result["error"] = str(exc)
            error_code = None
            error_message = str(exc)
            if isinstance(exc, ClientError):
                error_code = exc.response.get("Error", {}).get("Code")
                error_message = exc.response.get("Error", {}).get("Message", error_message)

            if error_code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
                entry_result["permission_error"] = True
                entry_result["resolution"] = [
                    f"Verify you have write access to bucket '{bkt}'.",
                    "Run permissions(action='discover', params={'check_buckets': ['%s']}) to inspect access levels." % bkt,
                    "Use the Quilt catalog UI or contact an administrator to request s3:PutObject permissions.",
                ]
                entry_result["error_detail"] = error_message
        except Exception as exc:  # pragma: no cover - defensive catch-all
            entry_result["error"] = str(exc)

        results.append(entry_result)

    overall_success = uploaded == len(results)
    response: Dict[str, Any] = {
        "success": overall_success,
        "bucket": bkt,
        "requested": len(items),
        "uploaded": uploaded,
        "results": results,
    }
    if client_meta:
        response["upload_context"] = client_meta

    if not overall_success:
        if any(res.get("permission_error") for res in results):
            response.setdefault(
                "message",
                "Upload failed due to missing S3 permissions. Request write access and retry.",
            )
        else:
            response.setdefault("message", "Some objects failed to upload; see individual results for details.")

    return response


def bucket_object_fetch(
    path: str = "", s3_uri: str = "", max_bytes: int = 65536, base64_encode: bool = True, **kwargs
) -> dict[str, Any]:
    """Fetch binary or text data from a file using backend proxy.

    Args:
        path: Logical file path within package (e.g., "README.md")
        s3_uri: Alternative: Full S3 URI (legacy, requires AWS creds)
        max_bytes: Maximum bytes to read (default: 65536)
        base64_encode: Return binary data as base64 (default: True)
        **kwargs: Additional parameters including _context from frontend

    Returns:
        Dict with object data as base64 or text, plus metadata.
    """
    import base64
    import requests

    # Get presigned URL using object_link
    link_result = bucket_object_link(path=path, s3_uri=s3_uri, **kwargs)

    if not link_result.get("success"):
        return link_result  # Return error from object_link

    presigned_url = link_result.get("url")
    if not presigned_url:
        return format_error_response("Failed to get presigned URL")

    # Fetch content from presigned URL
    try:
        response = requests.get(presigned_url, timeout=30)
        response.raise_for_status()

        body = response.content[: max_bytes + 1]
        content_type = response.headers.get("Content-Type", "")

        truncated = len(body) > max_bytes
        if truncated:
            body = body[:max_bytes]

        if base64_encode:
            data = base64.b64encode(body).decode("ascii")
            return {
                "success": True,
                "path": path or s3_uri,
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
                "success": True,
                "path": path or s3_uri,
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
                "success": True,
                "path": path or s3_uri,
                "truncated": truncated,
                "max_bytes": max_bytes,
                "base64": True,
                "data": data,
                "content_type": content_type,
                "size": len(body),
                "note": "Binary data returned as base64 after decode failure",
            }
    except Exception as e:
        return format_error_response(f"Failed to fetch file content: {e}")


def bucket_object_link(path: str = "", s3_uri: str = "", expiration: int = 3600, **params) -> dict[str, Any]:
    """Generate a presigned URL for downloading a file using backend proxy.

    This function uses the backend's browsing session mechanism to generate
    presigned URLs without requiring AWS credentials in the JWT token.

    Args:
        path: Logical file path within package (e.g., "README.md", "data/file.csv")
        s3_uri: Alternative: Full S3 URI (legacy support)
        expiration: URL expiration time in seconds (default: 3600, max: 604800)
        **params: Additional parameters including _context from frontend navigation

    Returns:
        Dict with presigned URL and metadata.

    Examples:
        # Using navigation context (preferred)
        bucket_object_link(path="README.md", _context={...})

        # Using explicit S3 URI (legacy)
        bucket_object_link(s3_uri="s3://bucket/path/to/file")
    """
    # Extract navigation context from params
    nav_context = params.get('_context')

    # Try to use browsing session if we have package context
    if path and nav_context:
        # Validate navigation context has required fields
        required_fields = ['bucket', 'package', 'hash']
        missing_fields = [f for f in required_fields if f not in nav_context]

        if missing_fields:
            return {
                "success": False,
                "error": f"Navigation context missing required fields: {', '.join(missing_fields)}",
                "required_fields": required_fields,
                "provided_context": nav_context,
            }

        token = get_active_token()
        if not token:
            return format_error_response("Authorization token required")

        catalog_url = resolve_catalog_url()
        if not catalog_url:
            return format_error_response("Catalog URL not configured")

        try:
            # Create browsing session for current package
            session = catalog_client.catalog_create_browsing_session(
                registry_url=catalog_url,
                bucket=nav_context['bucket'],
                package_name=nav_context['package'],
                package_hash=nav_context['hash'],
                ttl=min(expiration, 180),  # Max 3 minutes for session
                auth_token=token,
            )

            # Get presigned URL for file
            presigned_url = catalog_client.catalog_browse_file(
                registry_url=catalog_url,
                session_id=session['id'],
                path=path,
                auth_token=token,
            )

            return {
                "success": True,
                "url": presigned_url,
                "expires": session['expires'],
                "session_id": session['id'],
                "method": "browsing_session",
                "path": path,
                "package": f"{nav_context['bucket']}/{nav_context['package']}",
            }
        except Exception as e:
            return format_error_response(f"Failed to generate presigned URL: {e}")

    # Fall back to legacy S3 URI approach (requires AWS credentials)
    if not s3_uri and path:
        return {
            "success": False,
            "error": "Package context required for presigned URLs",
            "message": (
                "To generate a presigned URL, you must be viewing a package. "
                "The frontend navigation context provides the necessary package information. "
                "If you're not in a package view, use search.unified_search to find the file."
            ),
            "alternatives": {
                "search": "Use search.unified_search to find files",
                "packaging": "Use packaging.browse to explore package contents",
            },
        }

    if not s3_uri:
        return format_error_response("Either 'path' with package context or 's3_uri' required")

    # Legacy S3 URI approach (will fail without AWS credentials)
    return _aws_credentials_unavailable("object_link", s3_uri)


def buckets(
    action: str | None = None, params: Optional[Dict[str, Any]] = None, _context: Optional[NavigationContext] = None
) -> dict[str, Any]:
    """
    S3 bucket operations and object management.

    Available actions:
    - discover: Discover all accessible buckets with permission levels
    - object_fetch: Fetch binary or text data from an S3 object
    - object_info: Get metadata information for an S3 object
    - object_link: Generate presigned URL for an S3 object
    - object_text: Read text content from an S3 object
    - objects_put: Upload multiple objects to an S3 bucket

    Args:
        action: The operation to perform. If None, returns available actions.
        params: Action-specific parameters
        _context: Navigation context from frontend (optional)

    Returns:
        Action-specific response dictionary

    Examples:
        # Discovery mode
        result = buckets()

        # Discover buckets
        result = buckets(action="discover")

        # Get file info with package context
        result = buckets(action="object_info", params={"path": "README.md", "_context": {...}})

        # Fetch object content
        result = buckets(action="object_fetch", params={"path": "data.csv", "_context": {...}})

    Note:
        For listing or searching objects, use search.unified_search with scope="bucket"

    For detailed parameter documentation, see individual action functions.
    """
    actions = {
        "discover": buckets_discover,
        "object_fetch": bucket_object_fetch,
        "object_info": bucket_object_info,
        "object_link": bucket_object_link,
        "object_text": bucket_object_text,
        "objects_put": bucket_objects_put,
    }

    # Discovery mode
    if action is None:
        return {
            "module": "buckets",
            "actions": list(actions.keys()),
            "description": "S3 bucket operations and object management via Quilt Catalog",
        }

    params = params or {}

    # Inject navigation context into params if provided
    if _context:
        params['_context'] = _context

    try:
        if action == "discover":
            return buckets_discover()
        elif action == "object_fetch":
            return bucket_object_fetch(**params)
        elif action == "object_info":
            # Apply navigation context for smart defaults
            if _context and is_object_context(_context):
                context_bucket = get_context_bucket(_context)
                context_path = get_context_path(_context)

                # If we're viewing the same object, provide enhanced info
                if (
                    context_bucket
                    and context_path
                    and params.get("bucket") == context_bucket
                    and params.get("key") == context_path
                ):
                    return {
                        "success": True,
                        "object": {
                            "bucket": context_bucket,
                            "key": context_path,
                            "version": get_context_version(_context),
                            "native_context": True,
                            "navigation_url": f"/b/{context_bucket}/files/{context_path}",
                            "message": "Object info from current navigation context",
                        },
                    }

            return bucket_object_info(**params)
        elif action == "object_link":
            return bucket_object_link(**params)
        elif action == "object_text":
            return bucket_object_text(**params)
        elif action == "objects_put":
            # Map frontend parameter names to function parameter names
            mapped_params = {}
            if "bucket" in params:
                mapped_params["bucket"] = params["bucket"]
            if "objects" in params:
                mapped_params["items"] = params["objects"]
            return bucket_objects_put(**mapped_params)
        else:
            return format_error_response(f"Unknown buckets action: {action}")

    except Exception as exc:
        logger.exception(f"Error executing buckets action '{action}': {exc}")
        return format_error_response(f"Failed to execute buckets action '{action}': {str(exc)}")
