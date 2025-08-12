from __future__ import annotations
from typing import Any, Dict, List
from ..server import mcp
from ..constants import DEFAULT_BUCKET

# Helpers

def _normalize_bucket(uri_or_name: str) -> str:
    if uri_or_name.startswith("s3://"): return uri_or_name[5:].split('/', 1)[0]
    return uri_or_name

@mcp.tool()
def bucket_objects_list(bucket: str = DEFAULT_BUCKET, prefix: str = "", max_keys: int = 100, continuation_token: str = "") -> Dict[str, Any]:
    """List objects in an S3 bucket with optional prefix filtering.
    
    Args:
        bucket: S3 bucket name or s3:// URI (default: DEFAULT_BUCKET)
        prefix: Filter objects by prefix (default: "")
        max_keys: Maximum number of objects to return, 1-1000 (default: 100)
        continuation_token: Token for paginating through large result sets (default: "")
    
    Returns:
        Dict with bucket info, objects list, and pagination details.
    """
    import boto3
    bkt = _normalize_bucket(bucket)
    max_keys = max(1, min(max_keys, 1000))
    client = boto3.client("s3")
    params: Dict[str, Any] = {"Bucket": bkt, "MaxKeys": max_keys}
    if prefix: params["Prefix"] = prefix
    if continuation_token: params["ContinuationToken"] = continuation_token
    try: resp = client.list_objects_v2(**params)
    except Exception as e: return {"error": f"Failed to list objects: {e}", "bucket": bkt}
    objects: List[Dict[str, Any]] = []
    for item in resp.get("Contents", []) or []:
        objects.append({"key": item.get("Key"), "size": item.get("Size"), "last_modified": str(item.get("LastModified")), "etag": item.get("ETag"), "storage_class": item.get("StorageClass")})
    return {"bucket": bkt, "prefix": prefix, "objects": objects, "truncated": resp.get("IsTruncated", False), "next_token": resp.get("NextContinuationToken", ""), "key_count": resp.get("KeyCount", len(objects)), "max_keys": max_keys}

@mcp.tool()
def bucket_object_info(s3_uri: str) -> Dict[str, Any]:
    """Get metadata information for a specific S3 object.
    
    Args:
        s3_uri: Full S3 URI (e.g., "s3://bucket-name/path/to/object")
    
    Returns:
        Dict with object metadata including size, content type, etag, and modification date.
    """
    import boto3
    if not s3_uri.startswith("s3://"): return {"error": "s3_uri must start with s3://"}
    without = s3_uri[5:]
    if '/' not in without: return {"error": "s3_uri must include a key after the bucket/"}
    bucket, key = without.split('/', 1)
    client = boto3.client("s3")
    try: head = client.head_object(Bucket=bucket, Key=key)
    except Exception as e: return {"error": f"Failed to head object: {e}", "bucket": bucket, "key": key}
    return {"bucket": bucket, "key": key, "size": head.get("ContentLength"), "content_type": head.get("ContentType"), "etag": head.get("ETag"), "last_modified": str(head.get("LastModified")), "metadata": head.get("Metadata", {}), "storage_class": head.get("StorageClass"), "cache_control": head.get("CacheControl")}

@mcp.tool()
def bucket_object_text(s3_uri: str, max_bytes: int = 65536, encoding: str = "utf-8") -> Dict[str, Any]:
    """Read text content from an S3 object.
    
    Args:
        s3_uri: Full S3 URI (e.g., "s3://bucket-name/path/to/file.txt")
        max_bytes: Maximum bytes to read (default: 65536)
        encoding: Text encoding to use (default: "utf-8")
    
    Returns:
        Dict with decoded text content and metadata.
    """
    import boto3
    if not s3_uri.startswith("s3://"): return {"error": "s3_uri must start with s3://"}
    without = s3_uri[5:]
    if '/' not in without: return {"error": "s3_uri must include a key after the bucket/"}
    bucket, key = without.split('/', 1)
    client = boto3.client("s3")
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read(max_bytes + 1)
    except Exception as e:
        return {"error": f"Failed to get object: {e}", "bucket": bucket, "key": key}
    truncated = len(body) > max_bytes
    if truncated: body = body[:max_bytes]
    try: text = body.decode(encoding, errors="replace")
    except Exception as e: return {"error": f"Decode failed: {e}", "bucket": bucket, "key": key}
    return {"bucket": bucket, "key": key, "encoding": encoding, "truncated": truncated, "max_bytes": max_bytes, "text": text}

@mcp.tool()
def bucket_objects_put(bucket: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Upload multiple objects to an S3 bucket.
    
    Args:
        bucket: S3 bucket name or s3:// URI
        items: List of objects to upload, each with 'key' and either 'text' or 'data' (base64)
               Optional: 'content_type', 'encoding' (for text), 'metadata' dict
    
    Returns:
        Dict with upload results and summary statistics.
    """
    import boto3, base64
    bkt = _normalize_bucket(bucket)
    if not items: return {"error": "items list is empty", "bucket": bkt}
    client = boto3.client("s3")
    results: List[Dict[str, Any]] = []
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
            try: body = text.encode(encoding)
            except Exception as e: results.append({"key": key, "error": f"encode failed: {e}"}); continue
        else:
            try: body = base64.b64decode(str(data_b64), validate=True)
            except Exception as e: results.append({"key": key, "error": f"base64 decode failed: {e}"}); continue
        put_kwargs: Dict[str, Any] = {"Bucket": bkt, "Key": key, "Body": body}
        if item.get("content_type"): put_kwargs["ContentType"] = item["content_type"]
        if item.get("metadata") and isinstance(item.get("metadata"), dict): put_kwargs["Metadata"] = item["metadata"]
        try:
            resp = client.put_object(**put_kwargs)
            results.append({"key": key, "etag": resp.get("ETag"), "size": len(body), "content_type": put_kwargs.get("ContentType")})
        except Exception as e:
            results.append({"key": key, "error": str(e)})
    successes = sum(1 for r in results if "etag" in r)
    return {"bucket": bkt, "requested": len(items), "uploaded": successes, "results": results}

@mcp.tool()
def bucket_object_fetch(s3_uri: str, max_bytes: int = 65536, base64_encode: bool = True) -> Dict[str, Any]:
    """Fetch binary or text data from an S3 object.
    
    Args:
        s3_uri: Full S3 URI (e.g., "s3://bucket-name/path/to/file")
        max_bytes: Maximum bytes to read (default: 65536)
        base64_encode: Return binary data as base64 (default: True)
    
    Returns:
        Dict with object data as base64 or text, plus metadata.
    """
    import boto3, base64
    if not s3_uri.startswith("s3://"): return {"error": "s3_uri must start with s3://"}
    without = s3_uri[5:]
    if '/' not in without: return {"error": "s3_uri must include a key after the bucket/"}
    bucket, key = without.split('/', 1)
    client = boto3.client("s3")
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read(max_bytes + 1)
        content_type = obj.get("ContentType")
    except Exception as e:
        return {"error": f"Failed to get object: {e}", "bucket": bucket, "key": key}
    truncated = len(body) > max_bytes
    if truncated: body = body[:max_bytes]
    if base64_encode:
        data = base64.b64encode(body).decode("ascii")
        return {"bucket": bucket, "key": key, "truncated": truncated, "max_bytes": max_bytes, "base64": True, "data": data, "content_type": content_type, "size": len(body)}
    try:
        text = body.decode("utf-8")
        return {"bucket": bucket, "key": key, "truncated": truncated, "max_bytes": max_bytes, "base64": False, "text": text, "content_type": content_type, "size": len(body)}
    except Exception:
        data = base64.b64encode(body).decode("ascii")
        return {"bucket": bucket, "key": key, "truncated": truncated, "max_bytes": max_bytes, "base64": True, "data": data, "content_type": content_type, "size": len(body), "note": "Binary data returned as base64 after decode failure"}
