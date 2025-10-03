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


def _aws_credentials_unavailable(action_name: str, s3_uri_or_bucket: str = "") -> dict[str, Any]:
    """Return a user-friendly error message for actions that require AWS credentials."""
    return {
        "success": False,
        "error": f"The '{action_name}' action requires AWS S3 credentials which are not currently available.",
        "message": (
            f"This action needs direct S3 access, but the current JWT token is authentication-only "
            f"and doesn't include AWS credentials. "
            f"This feature will be available once backend proxy endpoints are implemented."
        ),
        "alternatives": {
            "search_files": "Use search.unified_search to find and list files",
            "view_packages": "Use packaging.list and packaging.browse to explore package contents",
            "upload_files": "Upload files through the Quilt web interface, then use packaging.create",
            "web_interface": "Access files directly through the Quilt catalog web UI"
        },
        "status": "awaiting_backend_support",
        "requested_resource": s3_uri_or_bucket or "unknown",
    }


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
    continuation_token: str = "",  # noqa: ARG001
    include_signed_urls: bool = True,  # noqa: ARG001
) -> dict[str, Any]:
    """[DEPRECATED] List objects in an S3 bucket.
    
    This function requires AWS credentials in the JWT token, which are not available
    in authentication-only JWT tokens from the Quilt frontend.
    
    **Use search.unified_search instead:**
    
    ```python
    # Instead of:
    # buckets.objects_list(bucket="my-bucket", prefix="data/")
    
    # Use:
    search.unified_search(
        query="*",  # or specific search terms
        scope="bucket",
        target="my-bucket",
        limit=100
    )
    ```
    
    The unified search uses GraphQL which only requires authentication tokens,
    not AWS credentials, and provides richer filtering and metadata.

    Args:
        bucket: S3 bucket name or s3:// URI
        prefix: Filter objects by prefix
        max_keys: Maximum number of objects to return
        continuation_token: [Ignored] Token for pagination
        include_signed_urls: [Ignored] Include presigned URLs

    Returns:
        Error message directing to use search.unified_search instead.
    """
    bkt = _normalize_bucket(bucket)
    
    return {
        "success": False,
        "deprecated": True,
        "error": "buckets.objects_list requires AWS credentials which are not available in JWT tokens.",
        "alternative": "Use search.unified_search instead",
        "example": {
            "action": "unified_search",
            "params": {
                "query": f"{prefix}*" if prefix else "*",
                "scope": "bucket",
                "target": bkt,
                "limit": max_keys
            }
        },
        "message": (
            f"To list objects in bucket '{bkt}', use search.unified_search:\n"
            f"search.unified_search(query='{prefix}*' if prefix else '*', scope='bucket', target='{bkt}', limit={max_keys})"
        )
    }


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
    path: str = "",
    s3_uri: str = "",
    max_bytes: int = 65536,
    encoding: str = "utf-8",
    **kwargs
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
    fetch_result = bucket_object_fetch(
        path=path,
        s3_uri=s3_uri,
        max_bytes=max_bytes,
        base64_encode=False,
        **kwargs
    )
    
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
    """[NOT IMPLEMENTED] Upload multiple objects to an S3 bucket.
    
    This action is not yet implemented because the Quilt backend does not provide
    presigned upload URLs or direct S3 write access via its APIs. This is intentional
    security design - the backend controls all S3 access via IAM roles.

    Args:
        bucket: S3 bucket name or s3:// URI
        items: List of objects to upload, each with 'key' and either 'text' or 'data' (base64)

    Returns:
        Error message with workarounds.
    """
    bkt = _normalize_bucket(bucket)
    
    return {
        "success": False,
        "not_implemented": True,
        "error": "File upload is not yet implemented in the MCP server",
        "message": (
            "The Quilt backend does not provide presigned upload URLs or direct S3 write access. "
            "This is intentional security design - the backend controls all AWS operations via IAM roles. "
            "To implement this feature, the backend would need a new 'generateUploadUrl' GraphQL mutation."
        ),
        "workarounds": {
            "web_ui": f"Upload files via Quilt catalog web interface at {resolve_catalog_url() or 'your catalog URL'}",
            "aws_cli": f"Upload with AWS CLI: aws s3 cp <file> s3://{bkt}/<key>",
            "then_package": "After upload, use packaging.create with the S3 URI to create a package"
        },
        "requested_bucket": bkt,
        "requested_items_count": len(items) if items else 0,
        "backend_feature_needed": "generateUploadUrl GraphQL mutation or presigned POST endpoint",
        "status": "awaiting_backend_api_enhancement"
    }


def bucket_object_fetch(
    path: str = "",
    s3_uri: str = "",
    max_bytes: int = 65536,
    base64_encode: bool = True,
    **kwargs
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
        
        body = response.content[:max_bytes + 1]
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


def bucket_object_link(
    path: str = "",
    s3_uri: str = "",
    expiration: int = 3600,
    **params
) -> dict[str, Any]:
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
    from ..runtime.context_helpers import get_navigation_context, has_package_context
    
    # Extract navigation context
    nav_context = get_navigation_context(params)
    
    # Try to use browsing session if we have package context
    if path and has_package_context(nav_context):
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
                "packaging": "Use packaging.browse to explore package contents"
            }
        }
    
    if not s3_uri:
        return format_error_response("Either 'path' with package context or 's3_uri' required")
    
    # Legacy S3 URI approach (will fail without AWS credentials)
    return _aws_credentials_unavailable("object_link", s3_uri)


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
